"""Touch and mouse input injector for Windows using user32.SendInput."""

import ctypes
import logging
from ctypes import wintypes
from typing import Optional
from ..protocol.messages import InputEventMessage, PointerInfo

logger = logging.getLogger(__name__)

# Windows API Input constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


class InputInjector:
    """Translates normalized Android touch coordinates into Windows virtual desktop inputs."""

    def __init__(
        self,
        virtual_display_x: int = 0,
        virtual_display_y: int = 0,
        virtual_display_w: int = 1920,
        virtual_display_h: int = 1080
    ):
        self.origin_x = virtual_display_x
        self.origin_y = virtual_display_y
        self.width = virtual_display_w
        self.height = virtual_display_h

    def update_bounds(self, x: int, y: int, w: int, h: int) -> None:
        self.origin_x = x
        self.origin_y = y
        self.width = w
        self.height = h

    def inject_event(self, event: InputEventMessage) -> None:
        """Processes an incoming InputEventMessage and sends Windows input events."""
        if not event.pointers:
            return

        # For primary pointer, map coordinates
        primary = event.pointers[0]
        abs_x = self.origin_x + int(primary.x * self.width)
        abs_y = self.origin_y + int(primary.y * self.height)

        # Normalize to Windows 65535 coordinate space across virtual desktop
        try:
            v_left = ctypes.windll.user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            v_top = ctypes.windll.user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            v_width = ctypes.windll.user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
            v_height = ctypes.windll.user32.GetSystemMetrics(79)# SM_CYVIRTUALSCREEN

            norm_x = int((abs_x - v_left) * 65535 / v_width)
            norm_y = int((abs_y - v_top) * 65535 / v_height)
        except Exception:
            norm_x = int(primary.x * 65535)
            norm_y = int(primary.y * 65535)

        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK

        if primary.action == "DOWN":
            flags |= MOUSEEVENTF_LEFTDOWN
        elif primary.action == "UP" or primary.action == "CANCEL":
            flags |= MOUSEEVENTF_LEFTUP

        mi = MOUSEINPUT(
            dx=norm_x,
            dy=norm_y,
            mouseData=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=None
        )
        inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))

        try:
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        except Exception as e:
            logger.debug("SendInput exception (simulated environment): %s", e)
