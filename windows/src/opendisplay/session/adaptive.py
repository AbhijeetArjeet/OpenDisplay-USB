"""Adaptive performance controller supporting 5 performance profiles."""

from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PerformanceProfile(Enum):
    LOW_LATENCY = "LOW_LATENCY"
    BALANCED = "BALANCED"
    QUALITY = "QUALITY"
    BATTERY_SAVER = "BATTERY_SAVER"
    AUTOMATIC = "AUTOMATIC"


@dataclass
class StreamingParameters:
    target_fps: float
    bitrate_bps: int
    keyframe_interval_s: float
    max_queue_depth: int
    low_latency_flags: bool


class AdaptivePerformanceController:
    """Dynamically determines optimal streaming parameters based on profile and real-time conditions."""

    def __init__(
        self,
        profile: PerformanceProfile = PerformanceProfile.BALANCED,
        display_refresh_rate: float = 60.0
    ):
        self.profile = profile
        self.display_refresh_rate = display_refresh_rate
        self._current_bitrate = self._get_initial_bitrate()

    def _get_initial_bitrate(self) -> int:
        if self.profile == PerformanceProfile.LOW_LATENCY:
            return 18_000_000
        elif self.profile == PerformanceProfile.QUALITY:
            return 25_000_000
        elif self.profile == PerformanceProfile.BATTERY_SAVER:
            return 8_000_000
        else:
            return 20_000_000

    def compute_parameters(self) -> StreamingParameters:
        """Calculates optimal encoding and transmission parameters."""
        if self.profile == PerformanceProfile.BATTERY_SAVER:
            target_fps = min(30.0, self.display_refresh_rate)
            return StreamingParameters(
                target_fps=target_fps,
                bitrate_bps=self._current_bitrate,
                keyframe_interval_s=4.0,
                max_queue_depth=2,
                low_latency_flags=False
            )
        elif self.profile == PerformanceProfile.LOW_LATENCY:
            target_fps = min(120.0, max(60.0, self.display_refresh_rate))
            return StreamingParameters(
                target_fps=target_fps,
                bitrate_bps=self._current_bitrate,
                keyframe_interval_s=1.0,
                max_queue_depth=1,
                low_latency_flags=True
            )
        elif self.profile == PerformanceProfile.QUALITY:
            target_fps = self.display_refresh_rate
            return StreamingParameters(
                target_fps=target_fps,
                bitrate_bps=self._current_bitrate,
                keyframe_interval_s=2.0,
                max_queue_depth=3,
                low_latency_flags=False
            )
        elif self.profile == PerformanceProfile.AUTOMATIC:
            return StreamingParameters(
                target_fps=self.display_refresh_rate,
                bitrate_bps=self._current_bitrate,
                keyframe_interval_s=2.0,
                max_queue_depth=2,
                low_latency_flags=True
            )
        else:  # BALANCED
            return StreamingParameters(
                target_fps=min(60.0, self.display_refresh_rate),
                bitrate_bps=self._current_bitrate,
                keyframe_interval_s=2.0,
                max_queue_depth=2,
                low_latency_flags=True
            )

    def on_network_feedback(self, rtt_ms: float, dropped_frames: int):
        """Adapts bitrate dynamically if in AUTOMATIC mode."""
        if self.profile != PerformanceProfile.AUTOMATIC:
            return

        if rtt_ms > 45.0 or dropped_frames > 2:
            # Back off bitrate to clear transport congestion
            new_bitrate = max(4_000_000, int(self._current_bitrate * 0.85))
            if new_bitrate != self._current_bitrate:
                logger.info("Adaptive: congested (RTT=%.1fms, drops=%d), reducing bitrate %d -> %d bps",
                            rtt_ms, dropped_frames, self._current_bitrate, new_bitrate)
                self._current_bitrate = new_bitrate
        elif rtt_ms < 20.0 and dropped_frames == 0:
            # Channel is clean, step up bitrate gradually
            new_bitrate = min(16_000_000, int(self._current_bitrate * 1.05))
            if new_bitrate != self._current_bitrate:
                self._current_bitrate = new_bitrate
