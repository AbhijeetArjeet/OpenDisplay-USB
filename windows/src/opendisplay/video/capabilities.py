"""Runtime hardware capability detection for Windows video encoding."""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import av

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EncoderInfo:
    name: str
    codec: str  # "H264" or "HEVC"
    is_hardware: bool
    vendor: str  # "NVIDIA", "INTEL", "AMD", "SOFTWARE"
    options: Dict[str, str]


@dataclass
class HostVideoCapabilities:
    h264_encoders: List[EncoderInfo] = field(default_factory=list)
    hevc_encoders: List[EncoderInfo] = field(default_factory=list)
    preferred_h264: Optional[EncoderInfo] = None
    preferred_hevc: Optional[EncoderInfo] = None

    @property
    def supports_hevc(self) -> bool:
        return len(self.hevc_encoders) > 0

    @property
    def supports_h264(self) -> bool:
        return len(self.h264_encoders) > 0


class HardwareCapabilityDetector:
    """Discovers available video encoders without hardcoded hardware assumptions."""

    CANDIDATES = [
        # H.264 candidates
        EncoderInfo("h264_nvenc", "H264", True, "NVIDIA", {"preset": "p1", "tune": "ull", "profile": "baseline"}),
        EncoderInfo("h264_qsv", "H264", True, "INTEL", {"preset": "veryfast"}),
        EncoderInfo("h264_amf", "H264", True, "AMD", {"usage": "ultralowlatency"}),
        EncoderInfo("libx264", "H264", False, "SOFTWARE", {"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline", "repeat-headers": "1"}),

        # HEVC candidates
        EncoderInfo("hevc_nvenc", "HEVC", True, "NVIDIA", {"preset": "p1", "tune": "ull", "profile": "main"}),
        EncoderInfo("hevc_qsv", "HEVC", True, "INTEL", {"preset": "veryfast"}),
        EncoderInfo("hevc_amf", "HEVC", True, "AMD", {"usage": "ultralowlatency"}),
        EncoderInfo("libx265", "HEVC", False, "SOFTWARE", {"preset": "ultrafast", "tune": "zerolatency", "repeat-headers": "1"}),
    ]

    _cached_caps: Optional[HostVideoCapabilities] = None

    @classmethod
    def detect(cls, force_refresh: bool = False) -> HostVideoCapabilities:
        """Probes all candidate encoders by attempting test context initialization."""
        if cls._cached_caps is not None and not force_refresh:
            return cls._cached_caps

        caps = HostVideoCapabilities()

        for cand in cls.CANDIDATES:
            if cls._test_encoder(cand):
                if cand.codec == "H264":
                    caps.h264_encoders.append(cand)
                elif cand.codec == "HEVC":
                    caps.hevc_encoders.append(cand)

        # Set preferred (first hardware candidate, or first software candidate)
        caps.preferred_h264 = caps.h264_encoders[0] if caps.h264_encoders else None
        caps.preferred_hevc = caps.hevc_encoders[0] if caps.hevc_encoders else None

        logger.info(
            "Detected host video capabilities: H.264=%s (%s), HEVC=%s (%s)",
            bool(caps.preferred_h264),
            caps.preferred_h264.name if caps.preferred_h264 else "None",
            bool(caps.preferred_hevc),
            caps.preferred_hevc.name if caps.preferred_hevc else "None"
        )

        cls._cached_caps = caps
        return caps

    @classmethod
    def _test_encoder(cls, cand: EncoderInfo) -> bool:
        try:
            codec = av.Codec(cand.name, "w")
            ctx = av.CodecContext.create(codec)
            ctx.width = 640
            ctx.height = 480
            ctx.pix_fmt = "yuv420p"
            ctx.options = cand.options
            ctx.open()
            return True
        except Exception as e:
            logger.debug("Encoder %s probe failed: %s", cand.name, e)
            return False
