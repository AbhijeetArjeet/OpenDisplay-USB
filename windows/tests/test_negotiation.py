"""Unit tests for Phase 1 codec negotiation, H.264 level math, refresh normalization, and fallback ladder."""

import pytest
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from opendisplay.session.negotiation import (
    calculate_macroblocks,
    find_required_h264_level,
    normalize_refresh_rate,
    get_next_lower_refresh_tier,
    FallbackLadder,
    H264_LEVELS
)


def test_h264_macroblock_and_level_math():
    # 1. 1920x1200 @ 120 -> ceil(1920/16)=120, ceil(1200/16)=75 -> 9000 MBs/frame
    # 9000 * 120 = 1,080,000 MB/s -> exceeds 5.1 (983,040) -> needs Level 5.2 (2,073,600)
    mbs, mb_s = calculate_macroblocks(1920, 1200, 120.0)
    assert mbs == 9000
    assert mb_s == 1_080_000
    assert find_required_h264_level(1920, 1200, 120.0) == "5.2"

    # 2. 2560x1600 @ 60 -> ceil(2560/16)=160, ceil(1600/16)=100 -> 16,000 MBs/frame
    # 16,000 * 60 = 960,000 MB/s -> fits Level 5.1 (983,040 max)
    mbs_60, mb_s_60 = calculate_macroblocks(2560, 1600, 60.0)
    assert mbs_60 == 16000
    assert mb_s_60 == 960_000
    assert find_required_h264_level(2560, 1600, 60.0) == "5.1"

    # 3. 2560x1600 @ 120 -> 16,000 * 120 = 1,920,000 MB/s -> needs Level 5.2
    mbs_120, mb_s_120 = calculate_macroblocks(2560, 1600, 120.0)
    assert mb_s_120 == 1_920_000
    assert find_required_h264_level(2560, 1600, 120.0) == "5.2"

    # 4. 2880x1800 @ 120 -> ceil(2880/16)=180, ceil(1800/16)=113 -> 20,340 MBs/frame
    # 20,340 * 120 = 2,440,800 MB/s -> EXCEEDS ALL H.264 Levels (5.2 max is 2,073,600)
    mbs_huge, mb_s_huge = calculate_macroblocks(2880, 1800, 120.0)
    assert mb_s_huge > 2_073_600
    assert find_required_h264_level(2880, 1800, 120.0) is None


def test_refresh_rate_normalization():
    # Flagship phone reporting 120.89 Hz or 121 Hz
    assert normalize_refresh_rate(120.89) == 120.0
    assert normalize_refresh_rate(121.0) == 120.0
    assert normalize_refresh_rate(119.88) == 120.0

    # 59.94 Hz -> 60 Hz
    assert normalize_refresh_rate(59.94) == 60.0

    # 90.02 Hz -> 90 Hz
    assert normalize_refresh_rate(90.02) == 90.0

    # 143.99 Hz -> 144 Hz
    assert normalize_refresh_rate(143.99) == 144.0

    # Corner cases
    assert normalize_refresh_rate(0.0) == 60.0
    assert normalize_refresh_rate(-10.0) == 60.0


def test_fallback_ladder_phone_reporting_121hz():
    # When a phone with 1920x1200 reports 121 Hz, it should normalize to 120 Hz and select Level 5.2
    cfg = FallbackLadder.negotiate(
        requested_width=1920,
        requested_height=1200,
        requested_fps=121.0,
        device_hevc_supported=False,
        host_hevc_supported=False
    )
    assert cfg.fps == 120.0
    assert cfg.codec == "H264"
    assert cfg.h264_level == "5.2"
    assert cfg.rung_name == "RUNG_1_REQUESTED"


def test_fallback_ladder_2880x1800_at_120hz_hevc():
    # 2880x1800 @ 120 exceeds H.264 max. If HEVC is supported on both sides, upgrade to HEVC!
    # Wait: Rung 2 checks lower refresh tier first: 2880x1800 @ 90 -> 20340 * 90 = 1,830,600 MB/s (fits Level 5.2!)
    # But if no lower fps or if device requests 120 with HEVC:
    cfg = FallbackLadder.negotiate(
        requested_width=2880,
        requested_height=1800,
        requested_fps=120.0,
        device_hevc_supported=True,
        host_hevc_supported=True
    )
    # At 90 Hz it fits Level 5.2:
    assert cfg.fps == 90.0
    assert cfg.rung_name == "RUNG_2_LOWER_FPS"


def test_fallback_ladder_exceeding_h264_without_lower_fps():
    # Test when requested fps cannot fit even at lower FPS without HEVC
    # 3840x2160 @ 120 -> ceil(3840/16)*ceil(2160/16) = 240*135 = 32400 MBs
    # 32400 * 90 = 2,916,000 > 2,073,600
    # 32400 * 72 = 2,332,800 > 2,073,600
    # 32400 * 60 = 1,944,000 <= 2,073,600 (fits Level 5.2)
    cfg = FallbackLadder.negotiate(
        requested_width=3840,
        requested_height=2160,
        requested_fps=120.0,
        device_hevc_supported=False,
        host_hevc_supported=False
    )
    assert cfg.codec == "H264"
    assert cfg.fps == 60.0
    assert cfg.h264_level == "5.2"


def test_fallback_ladder_baseline_guarantee():
    # If crazy requested values are passed, ensure guaranteed 1080p60 baseline is returned
    cfg = FallbackLadder.negotiate(
        requested_width=8192,
        requested_height=4320,
        requested_fps=240.0,
        device_hevc_supported=False,
        host_hevc_supported=False,
        device_max_width=1920,
        device_max_height=1080,
        device_max_fps=60.0
    )
    assert cfg.width == 1920
    assert cfg.height == 1080
    assert cfg.fps == 60.0
    assert cfg.codec == "H264"
