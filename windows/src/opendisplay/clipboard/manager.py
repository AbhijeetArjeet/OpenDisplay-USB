"""Windows clipboard integration for OpenDisplay Protocol."""

import ctypes
from ctypes import wintypes
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040


class WindowsClipboard:
    """Reads and writes Windows clipboard text using Win32 API with 64-bit safety."""

    def __init__(self):
        self._user32 = getattr(ctypes.windll, "user32", None)
        self._kernel32 = getattr(ctypes.windll, "kernel32", None)
        self._last_content: Optional[str] = None

        if self._user32 and self._kernel32:
            self._user32.OpenClipboard.argtypes = [wintypes.HWND]
            self._user32.OpenClipboard.restype = wintypes.BOOL
            self._user32.CloseClipboard.argtypes = []
            self._user32.CloseClipboard.restype = wintypes.BOOL
            self._user32.EmptyClipboard.argtypes = []
            self._user32.EmptyClipboard.restype = wintypes.BOOL
            self._user32.GetClipboardData.argtypes = [wintypes.UINT]
            self._user32.GetClipboardData.restype = wintypes.HANDLE
            self._user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            self._user32.SetClipboardData.restype = wintypes.HANDLE

            self._kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            self._kernel32.GlobalLock.restype = ctypes.c_void_p
            self._kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            self._kernel32.GlobalUnlock.restype = wintypes.BOOL
            self._kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            self._kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

    def get_text(self) -> Optional[str]:
        if not self._user32 or not self._kernel32:
            return None
        if not self._user32.OpenClipboard(None):
            return None
        try:
            h_glb = self._user32.GetClipboardData(CF_UNICODETEXT)
            if not h_glb:
                return None
            ptr = self._kernel32.GlobalLock(h_glb)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                self._kernel32.GlobalUnlock(h_glb)
        except Exception as e:
            logger.debug("Failed to read clipboard: %s", e)
            return None
        finally:
            self._user32.CloseClipboard()

    def set_text(self, text: str) -> bool:
        if not self._user32 or not self._kernel32:
            return False
        if not self._user32.OpenClipboard(None):
            return False
        try:
            self._user32.EmptyClipboard()
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            h_glb = self._kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(encoded))
            if not h_glb:
                return False
            ptr = self._kernel32.GlobalLock(h_glb)
            if not ptr:
                return False
            try:
                ctypes.memmove(ptr, encoded, len(encoded))
            finally:
                self._kernel32.GlobalUnlock(h_glb)
            self._user32.SetClipboardData(CF_UNICODETEXT, h_glb)
            self._last_content = text
            return True
        except Exception as e:
            logger.warning("Failed to set clipboard: %s", e)
            return False
        finally:
            self._user32.CloseClipboard()

    def check_for_change(self) -> Optional[str]:
        """Returns new text if clipboard text changed since last check, otherwise None."""
        current = self.get_text()
        if current is not None and current != self._last_content:
            self._last_content = current
            return current
        return None
