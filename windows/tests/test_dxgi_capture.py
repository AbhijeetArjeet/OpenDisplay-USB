"""Unit tests for DXGI Desktop Duplication capture and fallback mechanism."""

import pytest
import numpy as np
from opendisplay.display.capture import ScreenCapture
from opendisplay.display.dxgi_capture import DxgiScreenCapture


def test_dxgi_direct_capture():
    """Verifies that DxgiScreenCapture initializes and returns valid BGRA frames."""
    dxgi = DxgiScreenCapture(width=1280, height=720, monitor_index=0, target_fps=60.0)
    try:
        assert dxgi.is_dxgi_active is True
        frame = dxgi.capture_bgra_frame()
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.shape[2] == 4  # BGRA
    finally:
        dxgi.release()
        assert dxgi.is_dxgi_active is False


def test_screencapture_dxgi_backend():
    """Verifies ScreenCapture correctly defaults to or uses DXGI backend."""
    cap = ScreenCapture(width=1280, height=720, monitor_index=0, backend="dxgi")
    try:
        assert cap.backend == "dxgi"
        assert cap._dxgi is not None
        assert cap._dxgi.is_dxgi_active is True
        frame = cap.capture_bgra_frame()
        assert frame is not None
        assert frame.shape[2] == 4
    finally:
        cap.close()


def test_screencapture_gdi_backend():
    """Verifies ScreenCapture supports explicit GDI fallback."""
    cap = ScreenCapture(width=1280, height=720, monitor_index=0, backend="gdi")
    try:
        assert cap.backend == "gdi"
        assert cap._dxgi is None
        frame = cap.capture_bgra_frame()
        assert frame is not None
        assert frame.shape[2] == 4
    finally:
        cap.close()
