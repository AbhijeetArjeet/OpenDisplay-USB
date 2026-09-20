"""Automated display and latency benchmark runner for OpenDisplay USB."""

import asyncio
import json
import logging
import platform
import time
from dataclasses import asdict
from typing import Optional, Dict, Any

from .collector import DiagnosticsCollector, DiagnosticsSnapshot, LatencyPercentiles
from ..session.adaptive import PerformanceProfile
from ..session.session_manager import SessionManager
from ..transport import TcpTransport
from ..video.capabilities import HardwareCapabilityDetector

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Orchestrates an automated benchmark session and generates a standardized JSON report."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7320,
        duration_s: int = 15,
        profile: PerformanceProfile = PerformanceProfile.LOW_LATENCY,
        preferred_codec: str = "H264",
        use_synthetic_video: bool = True
    ):
        self.host = host
        self.port = port
        self.duration_s = duration_s
        self.profile = profile
        self.preferred_codec = preferred_codec
        self.use_synthetic_video = use_synthetic_video
        self.diagnostics = DiagnosticsCollector()

    async def run(self) -> Dict[str, Any]:
        """Runs the benchmark session for duration_s and returns structured results."""
        logger.info(
            "Starting benchmark: duration=%ds, profile=%s, preferred_codec=%s",
            self.duration_s, self.profile.value, self.preferred_codec
        )

        transport = TcpTransport(host=self.host, port=self.port)
        session_manager = SessionManager(
            transport=transport,
            diagnostics=self.diagnostics,
            use_synthetic_video=self.use_synthetic_video,
            enable_audio=False,
            enable_clipboard=False,
            performance_profile=self.profile,
            preferred_codec=self.preferred_codec
        )

        await session_manager.start()

        # Wait for handshake and connection to reach STREAMING
        logger.info("Waiting for session to connect and negotiate...")
        timeout_start = time.monotonic()
        while time.monotonic() - timeout_start < 10.0:
            if session_manager.controller and session_manager.controller.state.value == "STREAMING":
                break
            await asyncio.sleep(0.1)

        if not session_manager.controller or session_manager.controller.state.value != "STREAMING":
            await session_manager.stop()
            raise RuntimeError("Timed out waiting for session to enter STREAMING state")

        logger.info("Session in STREAMING state. Running benchmark measurement for %ds...", self.duration_s)
        benchmark_start_ts = time.time()
        start_time = time.monotonic()

        # Gather samples during duration
        while time.monotonic() - start_time < self.duration_s:
            await asyncio.sleep(1.0)
            snap = self.diagnostics.get_snapshot()
            logger.info(
                "Benchmark progress: FPS=%.1f, Bitrate=%.0f kbps, RTT=%.2f ms, Frames=%d",
                snap.fps, snap.bitrate_kbps, snap.rtt_latency_ms, snap.frames_sent
            )

        benchmark_end_ts = time.time()
        final_snapshot = self.diagnostics.get_snapshot()
        client_hello = session_manager.controller.client_hello
        client_caps = session_manager.controller.client_capabilities
        active_encoder = session_manager.controller.video_encoder.active_encoder_name if session_manager.controller.video_encoder else "unknown"
        negotiated_codec = session_manager.controller.video_encoder.codec if session_manager.controller.video_encoder else "unknown"

        await session_manager.stop()

        host_caps = HardwareCapabilityDetector.detect()

        report: Dict[str, Any] = {
            "metadata": {
                "timestamp_start": benchmark_start_ts,
                "timestamp_end": benchmark_end_ts,
                "duration_seconds": self.duration_s,
                "benchmark_version": "3.0.0"
            },
            "host": {
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "probed_h264_encoders": [e.name for e in host_caps.h264_encoders],
                "probed_hevc_encoders": [e.name for e in host_caps.hevc_encoders],
                "active_encoder": active_encoder,
                "active_codec": negotiated_codec
            },
            "receiver": {
                "manufacturer": client_hello.manufacturer if client_hello else "unknown",
                "model": client_hello.model if client_hello else "unknown",
                "android_version": client_hello.androidVersion if client_hello else "unknown",
                "sdk_level": client_hello.sdk if client_hello else 0,
                "display_resolution": f"{client_caps.display.widthPx}x{client_caps.display.heightPx}" if client_caps else "unknown",
                "display_density_dpi": client_caps.display.densityDpi if client_caps else 0,
                "display_refresh_rate_hz": client_caps.display.refreshRateHz if client_caps else 0.0
            },
            "configuration": {
                "profile": self.profile.value,
                "preferred_codec": self.preferred_codec,
                "synthetic_video": self.use_synthetic_video
            },
            "streaming_metrics": {
                "frames_sent_total": final_snapshot.frames_sent,
                "keyframes_sent_total": final_snapshot.keyframes_sent,
                "bytes_sent_total": final_snapshot.bytes_sent,
                "average_fps": final_snapshot.fps,
                "average_bitrate_kbps": final_snapshot.bitrate_kbps,
                "packets_dropped": final_snapshot.packets_dropped,
                "reconnect_count": final_snapshot.reconnect_count
            },
            "latency_metrics_ms": {
                "clock_drift_ppm": final_snapshot.clock_drift_ppm,
                "rtt": {
                    "current_ms": final_snapshot.rtt_latency_ms,
                    "jitter_ms": final_snapshot.rtt_jitter_ms
                },
                "capture": asdict(final_snapshot.percentiles["capture"]) if "capture" in final_snapshot.percentiles else None,
                "encode": asdict(final_snapshot.percentiles["encode"]) if "encode" in final_snapshot.percentiles else None,
                "transport": asdict(final_snapshot.percentiles["transport"]) if "transport" in final_snapshot.percentiles else None,
                "decode": asdict(final_snapshot.percentiles["decode"]) if "decode" in final_snapshot.percentiles else None,
                "render": asdict(final_snapshot.percentiles["render"]) if "render" in final_snapshot.percentiles else None,
                "end_to_end": asdict(final_snapshot.percentiles["end_to_end"]) if "end_to_end" in final_snapshot.percentiles else None,
                "input": asdict(final_snapshot.percentiles["input"]) if "input" in final_snapshot.percentiles else None,
                "panel_scanout_t10": "N/A"  # Unmeasurable without physical photodiode instrumentation
            }
        }

        return report
