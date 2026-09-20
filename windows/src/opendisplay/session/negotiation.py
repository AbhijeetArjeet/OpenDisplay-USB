"""Phase 1: Codec negotiation, H.264 level math, refresh normalization, and fallback ladder.

Implements ITU-T H.264 Annex A level limits, macroblock calculation,
display refresh rate clamping, and multi-tier graceful degradation.
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any

logger = logging.getLogger(__name__)

STANDARD_REFRESH_TIERS: List[float] = [30.0, 45.0, 60.0, 72.0, 90.0, 120.0, 144.0]


@dataclass(frozen=True)
class H264LevelLimit:
    level: str
    max_mb_per_sec: int
    max_mbs_per_frame: int


# ITU-T H.264 Table A-1 – Level limits
H264_LEVELS: List[H264LevelLimit] = [
    H264LevelLimit("4.1", 245_760, 8_192),
    H264LevelLimit("4.2", 522_240, 8_704),
    H264LevelLimit("5.0", 589_824, 22_080),
    H264LevelLimit("5.1", 983_040, 36_864),
    H264LevelLimit("5.2", 2_073_600, 36_864),
]


def calculate_macroblocks(width: int, height: int, fps: float) -> Tuple[int, int]:
    """Calculates (mbs_per_frame, mb_per_sec) according to H.264 specification.
    
    MB size is 16x16.
    mbs_per_frame = ceil(width / 16) * ceil(height / 16)
    mb_per_sec = mbs_per_frame * fps
    """
    mb_width = math.ceil(width / 16)
    mb_height = math.ceil(height / 16)
    mbs_per_frame = mb_width * mb_height
    mb_per_sec = int(round(mbs_per_frame * fps))
    return mbs_per_frame, mb_per_sec


def find_required_h264_level(width: int, height: int, fps: float) -> Optional[str]:
    """Finds the lowest H.264 level supporting (width, height, fps).
    
    Returns level string (e.g. '5.1') or None if it exceeds Level 5.2.
    """
    mbs_per_frame, mb_per_sec = calculate_macroblocks(width, height, fps)
    for limit in H264_LEVELS:
        if mbs_per_frame <= limit.max_mbs_per_frame and mb_per_sec <= limit.max_mb_per_sec:
            return limit.level
    return None


def normalize_refresh_rate(raw_fps: float) -> float:
    """Rounds non-standard reported rates (e.g., 120.89 -> 120, 121.0 -> 120, 59.94 -> 60).
    
    Selects nearest tier in {30, 45, 60, 72, 90, 120, 144}.
    """
    if raw_fps <= 0:
        return 60.0
    best_tier = min(STANDARD_REFRESH_TIERS, key=lambda t: abs(t - raw_fps))
    return best_tier


def get_next_lower_refresh_tier(fps: float) -> Optional[float]:
    """Returns the next lower refresh tier or None if already at minimum."""
    current = normalize_refresh_rate(fps)
    lower = [t for t in STANDARD_REFRESH_TIERS if t < current]
    return max(lower) if lower else None


@dataclass
class NegotiatedConfig:
    codec: str
    width: int
    height: int
    fps: float
    display_refresh_rate_hz: float
    h264_level: Optional[str]
    rung_name: str
    reason: str


class FallbackLadder:
    """Evaluates requested parameters against hardware constraints and steps down gracefully."""

    @classmethod
    def negotiate(
        cls,
        requested_width: int,
        requested_height: int,
        requested_fps: float,
        device_hevc_supported: bool = False,
        host_hevc_supported: bool = False,
        device_max_width: int = 4096,
        device_max_height: int = 4096,
        device_max_fps: float = 144.0,
    ) -> NegotiatedConfig:
        norm_fps = normalize_refresh_rate(requested_fps)
        w = min(requested_width, device_max_width)
        h = min(requested_height, device_max_height)
        norm_fps = min(norm_fps, device_max_fps)

        # Rung 1: Requested resolution and normalized FPS with H.264
        lvl = find_required_h264_level(w, h, norm_fps)
        if lvl is not None:
            return NegotiatedConfig(
                codec="H264",
                width=w,
                height=h,
                fps=norm_fps,
                display_refresh_rate_hz=requested_fps,
                h264_level=lvl,
                rung_name="RUNG_1_REQUESTED",
                reason=f"Fits H.264 Level {lvl} limits at native resolution and {norm_fps} FPS"
            )

        # Rung 2: Same resolution, lower refresh tier with H.264
        lower_fps = get_next_lower_refresh_tier(norm_fps)
        if lower_fps is not None:
            lvl2 = find_required_h264_level(w, h, lower_fps)
            if lvl2 is not None:
                return NegotiatedConfig(
                    codec="H264",
                    width=w,
                    height=h,
                    fps=lower_fps,
                    display_refresh_rate_hz=requested_fps,
                    h264_level=lvl2,
                    rung_name="RUNG_2_LOWER_FPS",
                    reason=f"H.264 limit exceeded at {norm_fps} FPS; stepped down to {lower_fps} FPS (Level {lvl2})"
                )

        # Rung 3: HEVC if both sides support it (HEVC handles higher MB/s up to Level 5.2/6.1)
        if device_hevc_supported and host_hevc_supported:
            return NegotiatedConfig(
                codec="HEVC",
                width=w,
                height=h,
                fps=norm_fps,
                display_refresh_rate_hz=requested_fps,
                h264_level=None,
                rung_name="RUNG_3_HEVC",
                reason=f"Resolution/framerate {w}x{h}@{norm_fps} exceeds H.264 level limits; upgraded to HEVC"
            )

        # Rung 4: 0.75x Resolution at normalized FPS
        w_scaled = int((w * 0.75) // 16 * 16)
        h_scaled = int((h * 0.75) // 16 * 16)
        lvl4 = find_required_h264_level(w_scaled, h_scaled, norm_fps)
        if lvl4 is not None:
            return NegotiatedConfig(
                codec="H264",
                width=w_scaled,
                height=h_scaled,
                fps=norm_fps,
                display_refresh_rate_hz=requested_fps,
                h264_level=lvl4,
                rung_name="RUNG_4_SCALE_075",
                reason=f"Scaled resolution to 75% ({w_scaled}x{h_scaled}) to preserve {norm_fps} FPS within Level {lvl4}"
            )

        # Rung 5: 60 FPS capped at requested resolution
        if norm_fps > 60.0:
            lvl5 = find_required_h264_level(w, h, 60.0)
            if lvl5 is not None:
                return NegotiatedConfig(
                    codec="H264",
                    width=w,
                    height=h,
                    fps=60.0,
                    display_refresh_rate_hz=requested_fps,
                    h264_level=lvl5,
                    rung_name="RUNG_5_60FPS_CAP",
                    reason=f"Capped framerate to 60.0 FPS to fit H.264 Level {lvl5}"
                )

        # Rung 6: Guaranteed baseline 1080p60 H.264 (Level 4.2)
        base_w, base_h = 1920, 1080
        lvl6 = find_required_h264_level(base_w, base_h, 60.0)
        return NegotiatedConfig(
            codec="H264",
            width=base_w,
            height=base_h,
            fps=60.0,
            display_refresh_rate_hz=requested_fps,
            h264_level=lvl6,
            rung_name="RUNG_6_BASELINE_1080P60",
            reason="Guaranteed fallback baseline: 1080p @ 60 FPS (H.264 Level 4.2)"
        )
