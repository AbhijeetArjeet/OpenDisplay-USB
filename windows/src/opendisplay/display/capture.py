"""Ultra-low-latency desktop frame capture supporting Win32 DIBSection zero-copy memory mapping."""

import ctypes
from ctypes import wintypes
import logging
from typing import Optional
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class ScreenCapture:
    """Acquires frames from the Windows desktop or virtual display with sub-6ms latency.

    Uses persistent Win32 CreateDIBSection memory-mapped buffers so BitBlt writes
    directly into NumPy memory without redundant buffer allocations or GetDIBits copies.
    """

    def __init__(self, width: int = 1920, height: int = 1080, monitor_index: int = 0):
        self.width = width
        self.height = height
        self.monitor_index = monitor_index

        self._user32 = ctypes.windll.user32
        self._gdi32 = ctypes.windll.gdi32

        self._screen_dc = None
        self._mem_dc = None
        self._hbitmap = None
        self._old_obj = None
        self._raw_buf = None
        self._np_bgra = None
        self._allocated_w = 0
        self._allocated_h = 0

        self._ensure_default_desktop()
        self._init_dib_section(self.width, self.height)

    def _ensure_default_desktop(self) -> None:
        """Ensures the calling thread is attached to the interactive 'Default' desktop."""
        try:
            hdesk = self._user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                self._user32.SetThreadDesktop(hdesk)
        except Exception as e:
            logger.debug("Could not switch to Default desktop: %s", e)

    def _init_dib_section(self, w: int, h: int) -> bool:
        """Initializes a persistent DIBSection for direct zero-copy BitBlt."""
        self._cleanup_gdi()
        try:
            self._screen_dc = self._user32.GetDC(None)
            self._mem_dc = self._gdi32.CreateCompatibleDC(self._screen_dc)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h  # top-down DIB
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0  # BI_RGB

            ppv_bits = ctypes.c_void_p()
            self._hbitmap = self._gdi32.CreateDIBSection(
                self._screen_dc,
                ctypes.byref(bmi),
                0,  # DIB_RGB_COLORS
                ctypes.byref(ppv_bits),
                None,
                0
            )

            if not self._hbitmap or not ppv_bits.value:
                logger.warning("CreateDIBSection returned NULL, fallback will be used")
                return False

            self._old_obj = self._gdi32.SelectObject(self._mem_dc, self._hbitmap)

            buf_type = ctypes.c_uint8 * (w * h * 4)
            self._raw_buf = buf_type.from_address(ppv_bits.value)
            self._np_bgra = np.frombuffer(self._raw_buf, dtype=np.uint8).reshape((h, w, 4))
            self._allocated_w = w
            self._allocated_h = h
            logger.info("Initialized high-speed DIBSection capture buffer: %dx%d (32bpp)", w, h)
            return True
        except Exception as e:
            logger.error("Failed to initialize DIBSection capture: %s", e)
            self._cleanup_gdi()
            return False

    def _cleanup_gdi(self) -> None:
        """Frees GDI handles safely."""
        if self._mem_dc and self._old_obj:
            self._gdi32.SelectObject(self._mem_dc, self._old_obj)
            self._old_obj = None
        if self._hbitmap:
            self._gdi32.DeleteObject(self._hbitmap)
            self._hbitmap = None
        if self._mem_dc:
            self._gdi32.DeleteDC(self._mem_dc)
            self._mem_dc = None
        if self._screen_dc:
            self._user32.ReleaseDC(None, self._screen_dc)
            self._screen_dc = None
        self._raw_buf = None
        self._np_bgra = None
        self._allocated_w = 0
        self._allocated_h = 0

    def capture_bgra_frame(self) -> Optional[np.ndarray]:
        """Captures a BGRA frame directly into mapped memory buffer with ZERO copy."""
        try:
            screen_w = self._user32.GetSystemMetrics(0)
            screen_h = self._user32.GetSystemMetrics(1)
            if screen_w <= 0 or screen_h <= 0:
                screen_w, screen_h = self.width, self.height

            if (self._allocated_w != screen_w or self._allocated_h != screen_h) or self._np_bgra is None:
                if not self._init_dib_section(screen_w, screen_h):
                    raise RuntimeError("Failed to reinitialize DIBSection")

            success = self._gdi32.BitBlt(
                self._mem_dc, 0, 0, screen_w, screen_h,
                self._screen_dc, 0, 0, 0x00CC0020
            )
            if not success:
                self._ensure_default_desktop()
                self._screen_dc = self._user32.GetDC(None)
                self._gdi32.BitBlt(
                    self._mem_dc, 0, 0, screen_w, screen_h,
                    self._screen_dc, 0, 0, 0x00CC0020
                )

            return self._np_bgra
        except Exception as e:
            logger.debug("capture_bgra_frame error: %s", e)
            return None

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures a single RGB frame directly from the screen into numpy array."""
        try:
            screen_w = self._user32.GetSystemMetrics(0)
            screen_h = self._user32.GetSystemMetrics(1)
            if screen_w <= 0 or screen_h <= 0:
                screen_w, screen_h = self.width, self.height

            # Reallocate if screen resolution changed
            if (self._allocated_w != screen_w or self._allocated_h != screen_h) or self._np_bgra is None:
                if not self._init_dib_section(screen_w, screen_h):
                    raise RuntimeError("Failed to reinitialize DIBSection")

            # Fast BitBlt directly into mapped memory buffer
            # SRCCOPY = 0x00CC0020
            success = self._gdi32.BitBlt(
                self._mem_dc, 0, 0, screen_w, screen_h,
                self._screen_dc, 0, 0, 0x00CC0020
            )
            if not success:
                # Desktop might have switched (UAC/lock), retry desktop attachment
                self._ensure_default_desktop()
                self._screen_dc = self._user32.GetDC(None)
                self._gdi32.BitBlt(
                    self._mem_dc, 0, 0, screen_w, screen_h,
                    self._screen_dc, 0, 0, 0x00CC0020
                )

            # BGRA to RGB slice (view without full copy when possible)
            rgb = self._np_bgra[:, :, [2, 1, 0]]

            if screen_w != self.width or screen_h != self.height:
                img = Image.fromarray(rgb).resize((self.width, self.height), Image.Resampling.BILINEAR)
                return np.array(img)

            return rgb.copy()
        except Exception as e:
            logger.debug("DIBSection capture error (%s), fallback to PIL ImageGrab", e)
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                if img.size != (self.width, self.height):
                    img = img.resize((self.width, self.height))
                return np.array(img.convert("RGB"))
            except Exception:
                return None

    def close(self):
        """Releases all GDI resources."""
        self._cleanup_gdi()

    def __del__(self):
        self.close()
