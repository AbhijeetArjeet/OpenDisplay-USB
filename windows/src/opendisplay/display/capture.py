"""Desktop frame capture supporting Win32 GDI interactive desktop capture and PIL fallback."""

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


class ScreenCapture:
    """Acquires frames from the Windows desktop or virtual display."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self._user32 = ctypes.windll.user32
        self._gdi32 = ctypes.windll.gdi32
        self._ensure_default_desktop()

    def _ensure_default_desktop(self) -> None:
        """Ensures the calling thread is attached to the interactive 'Default' desktop."""
        try:
            hdesk = self._user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                self._user32.SetThreadDesktop(hdesk)
        except Exception as e:
            logger.debug("Could not switch to Default desktop: %s", e)

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures a single RGB frame from the desktop."""
        self._ensure_default_desktop()

        try:
            screen_w = self._user32.GetSystemMetrics(0)
            screen_h = self._user32.GetSystemMetrics(1)
            if screen_w <= 0 or screen_h <= 0:
                screen_w, screen_h = 1920, 1080

            screen_dc = self._user32.GetDC(None)
            mem_dc = self._gdi32.CreateCompatibleDC(screen_dc)
            bitmap = self._gdi32.CreateCompatibleBitmap(screen_dc, screen_w, screen_h)
            old_obj = self._gdi32.SelectObject(mem_dc, bitmap)

            # SRCCOPY = 0x00CC0020
            self._gdi32.BitBlt(mem_dc, 0, 0, screen_w, screen_h, screen_dc, 0, 0, 0x00CC0020)

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = screen_w
            bmi.biHeight = -screen_h  # top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buf_size = screen_w * screen_h * 4
            buf = (ctypes.c_char * buf_size)()
            self._gdi32.GetDIBits(mem_dc, bitmap, 0, screen_h, buf, ctypes.byref(bmi), 0)

            # Cleanup GDI handles
            self._gdi32.SelectObject(mem_dc, old_obj)
            self._gdi32.DeleteObject(bitmap)
            self._gdi32.DeleteDC(mem_dc)
            self._user32.ReleaseDC(None, screen_dc)

            arr = np.frombuffer(buf, dtype=np.uint8).reshape((screen_h, screen_w, 4))
            rgb = arr[:, :, [2, 1, 0]]  # BGRA to RGB

            if screen_w != self.width or screen_h != self.height:
                img = Image.fromarray(rgb).resize((self.width, self.height), Image.Resampling.BILINEAR)
                return np.array(img)

            return rgb
        except Exception as e:
            logger.debug("GDI screen capture failed (%s), falling back to PIL", e)
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                if img.size != (self.width, self.height):
                    img = img.resize((self.width, self.height))
                return np.array(img.convert("RGB"))
            except Exception:
                return None
