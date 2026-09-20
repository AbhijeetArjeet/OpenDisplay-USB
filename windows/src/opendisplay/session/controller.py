"""Protocol handshake controller and session state machine."""

import asyncio
import logging
from enum import Enum
from typing import Optional, Callable
from ..protocol import (
    MessageType,
    PacketCodec,
    JsonCodec,
    HelloMessage,
    HelloAckMessage,
    CapabilitiesMessage,
    CapabilitiesAckMessage,
    DisplayConfigMessage,
    DisplayConfigAckMessage,
    VideoConfigMessage,
    VideoConfigAckMessage,
    PingMessage,
    PongMessage,
    StreamResetMessage,
    ErrorMessage,
    DisconnectMessage,
    ClipboardEventMessage,
    ErrorCode
)
from ..timing.clock import MonotonicClock, ClockSync, WindowsPrecisionTimer
from ..diagnostics.collector import DiagnosticsCollector
from ..input.injector import InputInjector
from ..video.encoder import VideoEncoder
from ..video.capabilities import HardwareCapabilityDetector
from ..video.test_stream import TestPatternGenerator
from ..display.capture import ScreenCapture
from ..audio.capture import AudioCapture
from ..audio.encoder import AudioEncoder
from ..clipboard import WindowsClipboard
from .adaptive import AdaptivePerformanceController, PerformanceProfile

logger = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = "IDLE"
    WAITING_HELLO = "WAITING_HELLO"
    WAITING_CAPABILITIES = "WAITING_CAPABILITIES"
    WAITING_DISPLAY_CONFIG_ACK = "WAITING_DISPLAY_CONFIG_ACK"
    WAITING_VIDEO_CONFIG_ACK = "WAITING_VIDEO_CONFIG_ACK"
    STREAMING = "STREAMING"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class ProtocolController:
    """Implements the 7-stage protocol handshake and message dispatch."""

    def __init__(
        self,
        send_packet_func: Callable[[bytes], asyncio.Future],
        diagnostics: DiagnosticsCollector,
        input_injector: InputInjector,
        use_synthetic_video: bool = True,
        enable_audio: bool = True,
        enable_clipboard: bool = True,
        performance_profile: PerformanceProfile = PerformanceProfile.BALANCED,
        preferred_codec: str = "H264"
    ):
        self.send_packet = send_packet_func
        self.diagnostics = diagnostics
        self.input_injector = input_injector
        self.use_synthetic_video = use_synthetic_video
        self.enable_audio = enable_audio
        self.enable_clipboard = enable_clipboard
        self.performance_profile = performance_profile
        self.preferred_codec = preferred_codec.upper()
        self.adaptive_controller = AdaptivePerformanceController(profile=self.performance_profile)

        self.state = SessionState.IDLE
        self.clock_sync = ClockSync()
        self.client_hello: Optional[HelloMessage] = None
        self.client_capabilities: Optional[CapabilitiesMessage] = None

        self.video_encoder: Optional[VideoEncoder] = None
        self.pattern_generator = TestPatternGenerator()
        self.screen_capture: Optional[ScreenCapture] = None
        self.audio_capture = AudioCapture()
        self.audio_encoder = AudioEncoder()
        self.clipboard = WindowsClipboard()

        self._ping_task: Optional[asyncio.Task] = None
        self._streaming_task: Optional[asyncio.Task] = None
        self._audio_task: Optional[asyncio.Task] = None
        self._clipboard_task: Optional[asyncio.Task] = None
        self._running = False

    async def start_handshake(self) -> None:
        """Enters WAITING_HELLO state waiting for Android to initiate."""
        WindowsPrecisionTimer.enable()
        self.state = SessionState.WAITING_HELLO
        self._running = True
        logger.info("Started handshake, awaiting HELLO from Android receiver")

    async def stop(self) -> None:
        WindowsPrecisionTimer.disable()
        self._running = False
        self.state = SessionState.DISCONNECTED
        if self._ping_task:
            self._ping_task.cancel()
        if self._streaming_task:
            self._streaming_task.cancel()
        if self._audio_task:
            self._audio_task.cancel()
        if self._clipboard_task:
            self._clipboard_task.cancel()
        self.audio_capture.stop()
        if self.video_encoder:
            self.video_encoder.close()
            self.video_encoder = None

    async def handle_packet(self, packet_bytes: bytes) -> None:
        """Dispatches an incoming framed packet according to protocol state."""
        try:
            packet = PacketCodec.decode(packet_bytes)
        except Exception as e:
            logger.warning("Failed to decode incoming packet: %s", e)
            return

        msg_type = packet.msg_type
        payload = packet.payload

        if msg_type == MessageType.HELLO:
            await self._handle_hello(payload)
        elif msg_type == MessageType.CAPABILITIES:
            await self._handle_capabilities(payload)
        elif msg_type == MessageType.DISPLAY_CONFIG_ACK:
            await self._handle_display_config_ack(payload)
        elif msg_type == MessageType.VIDEO_CONFIG_ACK:
            await self._handle_video_config_ack(payload)
        elif msg_type == MessageType.INPUT_EVENT:
            self._handle_input_event(payload)
        elif msg_type == MessageType.CLIPBOARD_EVENT:
            self._handle_clipboard_event(payload)
        elif msg_type == MessageType.PING:
            await self._handle_ping(payload)
        elif msg_type == MessageType.PONG:
            self._handle_pong(payload)
        elif msg_type == MessageType.ERROR:
            self._handle_error(payload)
        elif msg_type == MessageType.DISCONNECT:
            await self._handle_disconnect(payload)
        else:
            # Forward compatibility rule: discard unknown types without disconnecting
            logger.debug("Received message type %s, discarding", msg_type)

    async def _handle_hello(self, payload: bytes) -> None:
        hello = JsonCodec.decode_hello(payload)
        self.client_hello = hello
        logger.info(
            "Received HELLO from %s %s (Android %s, SDK %d)",
            hello.manufacturer,
            hello.model,
            hello.androidVersion,
            hello.sdk
        )

        # Version check
        accepted = (hello.protocol == 1)
        reason = None if accepted else "Protocol version mismatch"

        ack = HelloAckMessage(protocol=1, accepted=accepted, rejectionReason=reason)
        ack_bytes = JsonCodec.encode(ack)
        await self.send_packet(PacketCodec.encode(MessageType.HELLO_ACK, ack_bytes))

        if accepted:
            self.state = SessionState.WAITING_CAPABILITIES
        else:
            self.state = SessionState.ERROR

    async def _handle_capabilities(self, payload: bytes) -> None:
        caps = JsonCodec.decode_capabilities(payload)
        self.client_capabilities = caps
        self.adaptive_controller.display_refresh_rate = caps.display.refreshRateHz
        logger.info(
            "Received CAPABILITIES: Display %dx%d @ %.1f Hz",
            caps.display.widthPx,
            caps.display.heightPx,
            caps.display.refreshRateHz
        )

        # Confirm mandatory H264 codec
        h264_supported = any(v.codec == "H264" and v.supported for v in caps.video)
        if not h264_supported:
            logger.error("Client does not support mandatory H264 codec!")
            self.state = SessionState.ERROR
            return

        # Send CAPABILITIES_ACK
        caps_ack = CapabilitiesAckMessage(accepted=True)
        await self.send_packet(PacketCodec.encode(MessageType.CAPABILITIES_ACK, JsonCodec.encode(caps_ack)))

        # Send DISPLAY_CONFIG
        disp_cfg = DisplayConfigMessage(
            widthPx=caps.display.widthPx,
            heightPx=caps.display.heightPx,
            frameRateHz=caps.display.refreshRateHz,
            orientation=caps.display.orientation,
            pixelFormat="RGBA_8888",
            scaling="FIT"
        )
        self.state = SessionState.WAITING_DISPLAY_CONFIG_ACK
        await self.send_packet(PacketCodec.encode(MessageType.DISPLAY_CONFIG, JsonCodec.encode(disp_cfg)))

    async def _handle_display_config_ack(self, payload: bytes) -> None:
        ack = JsonCodec.decode_display_config_ack(payload)
        if not ack.accepted:
            logger.error("Client rejected DISPLAY_CONFIG: %s", ack.errorMessage)
            self.state = SessionState.ERROR
            return

        # Query adaptive parameters for current profile and display
        params = self.adaptive_controller.compute_parameters()

        # Negotiate codec: HEVC if preferred, supported by client and supported by host hardware/software
        client_supports_hevc = any(v.codec == "HEVC" and v.supported for v in self.client_capabilities.video) if self.client_capabilities else False
        host_caps = HardwareCapabilityDetector.detect()
        negotiated_codec = "H264"
        if self.preferred_codec == "HEVC" and client_supports_hevc and host_caps.supports_hevc:
            negotiated_codec = "HEVC"

        logger.info(
            "Negotiated streaming session: Codec=%s, Target FPS=%.1f, Bitrate=%d bps, LowLatency=%s",
            negotiated_codec, params.target_fps, params.bitrate_bps, params.low_latency_flags
        )

        w = self.client_capabilities.display.widthPx if self.client_capabilities else 1920
        h = self.client_capabilities.display.heightPx if self.client_capabilities else 1080

        self.video_encoder = VideoEncoder(
            width=w,
            height=h,
            fps=params.target_fps,
            bitrate_bps=params.bitrate_bps,
            keyframe_interval_s=params.keyframe_interval_s,
            codec=negotiated_codec
        )
        self.pattern_generator = TestPatternGenerator(width=w, height=h)
        self.screen_capture = ScreenCapture(width=w, height=h)

        # Generate 1 frame to prime encoder and extract SPS/PPS CSD
        test_frame = self.pattern_generator.generate_frame()
        primed_packets = self.video_encoder.encode_rgb_frame(test_frame, timestamp_ns=0)

        csd0 = self.video_encoder.csd0_base64 or "Z0IAKeKQFAe2AAADAAIAAAMAfCA="
        csd1 = self.video_encoder.csd1_base64 or "aM48gA=="

        vid_cfg = VideoConfigMessage(
            codec=negotiated_codec,
            widthPx=w,
            heightPx=h,
            frameRateHz=params.target_fps,
            bitrateBps=params.bitrate_bps,
            keyframeIntervalS=params.keyframe_interval_s,
            lowLatencyMode=params.low_latency_flags,
            csd0Base64=csd0,
            csd1Base64=csd1
        )
        self.state = SessionState.WAITING_VIDEO_CONFIG_ACK
        await self.send_packet(PacketCodec.encode(MessageType.VIDEO_CONFIG, JsonCodec.encode(vid_cfg)))

    async def _handle_video_config_ack(self, payload: bytes) -> None:
        ack = JsonCodec.decode_video_config_ack(payload)
        if not ack.accepted:
            logger.error("Client rejected VIDEO_CONFIG: %s", ack.errorMessage)
            self.state = SessionState.ERROR
            return

        logger.info("Handshake complete. Entering STREAMING state.")
        self.state = SessionState.STREAMING

        # Start background streaming loop, audio loop, clipboard loop & periodic PING
        self._streaming_task = asyncio.create_task(self._streaming_loop())
        if self.enable_audio:
            self.audio_capture.start()
            self._audio_task = asyncio.create_task(self._audio_loop())
        if self.enable_clipboard:
            self._clipboard_task = asyncio.create_task(self._clipboard_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _streaming_loop(self) -> None:
        """Sends video frames continuously at target FPS with high-precision frame pacing."""
        fps = self.video_encoder.fps if self.video_encoder else 60.0
        frame_interval_ns = int(1_000_000_000 / max(1.0, fps))
        start_ns = MonotonicClock.now_nanos()
        target_deadline_ns = start_ns
        frame_idx = 0

        while self._running and self.state == SessionState.STREAMING:
            # T0: Capture start
            t0_capture_start_ns = MonotonicClock.now_nanos()
            stream_ts_ns = t0_capture_start_ns - start_ns

            # Acquire frame (Desktop screen capture or synthetic test pattern)
            rgb_frame = None
            if not self.use_synthetic_video and self.screen_capture:
                rgb_frame = self.screen_capture.capture_frame()
            if rgb_frame is None:
                rgb_frame = self.pattern_generator.generate_frame()

            # T1: Capture end
            t1_capture_end_ns = MonotonicClock.now_nanos()
            capture_duration_ms = (t1_capture_end_ns - t0_capture_start_ns) / 1_000_000.0

            # T2: Encode start
            t2_encode_start_ns = MonotonicClock.now_nanos()
            packets = self.video_encoder.encode_rgb_frame(rgb_frame, stream_ts_ns)
            # T3: Encode end
            t3_encode_end_ns = MonotonicClock.now_nanos()
            encode_duration_ms = (t3_encode_end_ns - t2_encode_start_ns) / 1_000_000.0

            for enc_pkt in packets:
                # Construct binary VIDEO_FRAME packet
                # Offset 0..7: timestamp_ns, Offset 8..11: flags, Offset 12..N: NAL data
                payload = PacketCodec.encode_video_frame_payload(
                    timestamp_ns=stream_ts_ns,
                    is_keyframe=enc_pkt.is_keyframe,
                    nal_data=enc_pkt.data
                )
                framed = PacketCodec.encode(MessageType.VIDEO_FRAME, payload)
                await self.send_packet(framed)
                self.diagnostics.record_frame(
                    byte_size=len(framed),
                    is_keyframe=enc_pkt.is_keyframe,
                    capture_ms=capture_duration_ms,
                    encode_ms=encode_duration_ms
                )

            frame_idx += 1
            target_deadline_ns += frame_interval_ns
            now_after_work_ns = MonotonicClock.now_nanos()
            remaining_ns = target_deadline_ns - now_after_work_ns

            if remaining_ns > 0:
                sleep_s = remaining_ns / 1_000_000_000.0
                if sleep_s > 0.002:
                    await asyncio.sleep(sleep_s - 0.001)
                while MonotonicClock.now_nanos() < target_deadline_ns:
                    pass
            else:
                target_deadline_ns = now_after_work_ns
                await asyncio.sleep(0)

    async def _audio_loop(self) -> None:
        """Continuously captures and packetizes system audio at 20ms intervals."""
        audio_interval_s = 0.020
        start_ns = MonotonicClock.now_nanos()

        while self._running and self.state == SessionState.STREAMING:
            pcm_samples = self.audio_capture.read_samples()
            if pcm_samples:
                ts_ns = MonotonicClock.now_nanos() - start_ns
                framed = self.audio_encoder.packetize_pcm(pcm_samples, ts_ns)
                await self.send_packet(framed)
            await asyncio.sleep(audio_interval_s)

    async def _clipboard_loop(self) -> None:
        """Monitors Windows clipboard for local changes and forwards to Android."""
        while self._running and self.state == SessionState.STREAMING:
            await asyncio.sleep(0.5)
            changed_text = self.clipboard.check_for_change()
            if changed_text:
                logger.info("Local clipboard changed, sending CLIPBOARD_EVENT (%d chars)", len(changed_text))
                msg = ClipboardEventMessage(content=changed_text, mimeType="text/plain")
                payload = JsonCodec.encode(msg)
                await self.send_packet(PacketCodec.encode(MessageType.CLIPBOARD_EVENT, payload))

    async def _ping_loop(self) -> None:
        """Sends periodic PING every 5 seconds to measure RTT latency."""
        while self._running and self.state == SessionState.STREAMING:
            await asyncio.sleep(5.0)
            ping_ts = self.clock_sync.on_ping_sent()
            ping_msg = PingMessage(timestampNs=ping_ts)
            await self.send_packet(PacketCodec.encode(MessageType.PING, JsonCodec.encode(ping_msg)))

    def _handle_pong(self, payload: bytes) -> None:
        pong = JsonCodec.decode_pong(payload)
        rtt_ms = self.clock_sync.on_pong_received(pong.timestampNs, pong.serverTimestampNs)
        self.diagnostics.record_rtt(
            rtt_ms=rtt_ms,
            jitter_ms=self.clock_sync.rtt_jitter_ms,
            drift_ppm=self.clock_sync.drift_ppm
        )
        self.adaptive_controller.on_network_feedback(rtt_ms, self.diagnostics.packets_dropped)
        logger.debug("Received PONG, RTT: %.2f ms (jitter: %.2f ms, drift: %.1f ppm)",
                     rtt_ms, self.clock_sync.rtt_jitter_ms, self.clock_sync.drift_ppm)

    async def _handle_ping(self, payload: bytes) -> None:
        d = JsonCodec.decode(payload)
        pong = PongMessage(
            timestampNs=d.get("timestampNs", 0),
            serverTimestampNs=MonotonicClock.now_nanos()
        )
        await self.send_packet(PacketCodec.encode(MessageType.PONG, JsonCodec.encode(pong)))

    def _handle_input_event(self, payload: bytes) -> None:
        event = JsonCodec.decode_input_event(payload)
        if event.timestampNs and self.clock_sync.is_synced:
            now_ns = MonotonicClock.now_nanos()
            host_event_ns = self.clock_sync.device_to_host_ns(event.timestampNs)
            input_latency_ms = max(0.0, (now_ns - host_event_ns) / 1_000_000.0)
            self.diagnostics.record_input_latency(input_latency_ms)
        logger.info("Received INPUT_EVENT from Android: %s pointers=%d", event.eventType, len(event.pointers))
        self.input_injector.inject_event(event)

    def _handle_clipboard_event(self, payload: bytes) -> None:
        event = JsonCodec.decode_clipboard_event(payload)
        logger.info("Received CLIPBOARD_EVENT from Android: %d chars", len(event.content))
        self.clipboard.set_text(event.content)

    def _handle_error(self, payload: bytes) -> None:
        err = JsonCodec.decode_error(payload)
        logger.warning("Error received from Android: [%d] %s (fatal=%s)", err.code, err.message, err.fatal)
        if err.fatal:
            self.state = SessionState.ERROR

    async def _handle_disconnect(self, payload: bytes) -> None:
        logger.info("DISCONNECT received from client")
        await self.stop()
