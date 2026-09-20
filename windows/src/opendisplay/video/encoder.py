"""Hardware-accelerated video encoder producing Annex B streams with universal fallback."""

import av
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple
from fractions import Fraction
from .csd import extract_h264_sps_pps
from .capabilities import HardwareCapabilityDetector, EncoderInfo

logger = logging.getLogger(__name__)


@dataclass
class EncodedPacket:
    data: bytes
    is_keyframe: bool
    pts_ns: int
    encode_duration_ns: int = 0


class VideoEncoder:
    """Universal video encoder configured for low-latency streaming across all GPU vendors."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: float = 60.0,
        bitrate_bps: int = 10_000_000,
        keyframe_interval_s: float = 2.0,
        codec: str = "H264"
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate_bps = bitrate_bps
        self.keyframe_interval_s = keyframe_interval_s
        self.codec = codec.upper()

        self._codec_ctx: Optional[av.CodecContext] = None
        self.active_encoder_name: str = ""
        self.is_hardware: bool = False
        self._sps_b64: Optional[str] = None
        self._pps_b64: Optional[str] = None
        self._frame_count = 0
        self._init_encoder()

    def _init_encoder(self):
        caps = HardwareCapabilityDetector.detect()
        candidates = caps.hevc_encoders if self.codec == "HEVC" else caps.h264_encoders

        if not candidates:
            # Fallback to standard software encoder if none detected
            fallback_name = "libx265" if self.codec == "HEVC" else "libx264"
            candidates = [EncoderInfo(fallback_name, self.codec, False, "SOFTWARE", {"preset": "ultrafast", "tune": "zerolatency"})]

        for cand in candidates:
            try:
                c = av.Codec(cand.name, "w")
                ctx = av.CodecContext.create(c)
                ctx.width = self.width
                ctx.height = self.height
                ctx.pix_fmt = "yuv420p"
                ctx.framerate = int(self.fps)
                ctx.time_base = Fraction(1, int(self.fps * 1000))
                options = dict(cand.options)
                ctx.bit_rate = self.bitrate_bps
                options["b:v"] = str(self.bitrate_bps)
                options["maxrate"] = str(int(self.bitrate_bps * 1.5))
                options["bufsize"] = str(int(self.bitrate_bps * 0.5))
                ctx.options = options
                ctx.open()

                self._codec_ctx = ctx
                self.active_encoder_name = cand.name
                self.is_hardware = cand.is_hardware
                logger.info("Successfully initialized %s encoder: %s (HW=%s, vendor=%s)",
                            self.codec, cand.name, cand.is_hardware, cand.vendor)
                return
            except Exception as e:
                logger.debug("Encoder candidate %s failed to open (%s), trying next...", cand.name, e)
                continue

        raise RuntimeError(f"Failed to initialize any {self.codec} encoder on this system")

    @property
    def csd0_base64(self) -> Optional[str]:
        """Base64-encoded SPS."""
        return self._sps_b64

    @property
    def csd1_base64(self) -> Optional[str]:
        """Base64-encoded PPS."""
        return self._pps_b64

    def encode_rgb_frame(self, frame_array: np.ndarray, timestamp_ns: int, format: str = "rgb24") -> List[EncodedPacket]:
        """Encodes a numpy array (height, width, channels) into Annex B packets.

        Supports 'rgb24' (3 channels) or 'bgra' (4 channels, zero-copy direct from DIBSection).
        """
        if self._codec_ctx is None:
            return []

        frame = av.VideoFrame.from_ndarray(frame_array, format=format)
        frame.pts = self._frame_count
        self._frame_count += 1

        packets: List[EncodedPacket] = []
        for av_packet in self._codec_ctx.encode(frame):
            nal_data = bytes(av_packet)
            is_key = bool(av_packet.is_keyframe)

            # If SPS/PPS not yet cached, extract from keyframe
            if is_key and (self._sps_b64 is None or self._pps_b64 is None):
                sps, pps = extract_h264_sps_pps(nal_data)
                if sps:
                    self._sps_b64 = sps
                if pps:
                    self._pps_b64 = pps

            packets.append(EncodedPacket(data=nal_data, is_keyframe=is_key, pts_ns=timestamp_ns))

        return packets

    def flush(self) -> List[EncodedPacket]:
        """Flushes buffered frames from encoder."""
        if self._codec_ctx is None:
            return []
        packets: List[EncodedPacket] = []
        for av_packet in self._codec_ctx.encode(None):
            packets.append(EncodedPacket(
                data=bytes(av_packet),
                is_keyframe=bool(av_packet.is_keyframe),
                pts_ns=0
            ))
        return packets

    def close(self):
        self._codec_ctx = None
