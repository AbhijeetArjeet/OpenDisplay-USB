"""Unit tests for ScreenCapture monitor enumeration and capture functionality."""

import pytest
from opendisplay.display.capture import ScreenCapture


def test_screen_capture_get_monitors():
    """Verifies that get_monitors returns valid monitor structures."""
    monitors = ScreenCapture.get_monitors()
    assert isinstance(monitors, list)
    assert len(monitors) >= 1

    primary = monitors[0]
    assert "index" in primary
    assert "x" in primary
    assert "y" in primary
    assert "width" in primary
    assert "height" in primary
    assert primary["width"] > 0
    assert primary["height"] > 0


def test_screen_capture_initialization_and_bgra():
    """Verifies that ScreenCapture initializes and captures frames."""
    cap = ScreenCapture(width=640, height=360, monitor_index=0)
    try:
        frame = cap.capture_bgra_frame()
        assert frame is not None
        assert frame.ndim == 3
        assert frame.shape[2] == 4  # BGRA
    finally:
        cap.close()
