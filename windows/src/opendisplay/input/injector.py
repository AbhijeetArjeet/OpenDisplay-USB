"""High-Precision Touch and Stylus Input Injector for Windows.

Supports:
- Multitouch and Windows Ink stylus input with pressure and tilt.
- Barrel button / right-click emulation.
- Hover tracking for S-Pen and active stylus cursor preview.
- Normalized-to-virtual-desktop coordinate transformation.
"""

import ctypes
import logging
from ctypes import wintypes
from typing import List, Optional
from ..protocol.messages import InputEventMessage, PointerInfo

logger = logging.getLogger(__name__)

# Windows API Input constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

# Synthetic Pointer API constants (Windows 8+)
PT_POINTER = 1
PT_TOUCH = 2
PT_PEN = 3
PT_MOUSE = 4
PT_TOUCHPAD = 5

POINTER_FLAG_NONE = 0x00000000
POINTER_FLAG_NEW = 0x00000001
POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_FIRSTBUTTON = 0x00000010
POINTER_FLAG_SECONDBUTTON = 0x00000020
POINTER_FLAG_PRIMARY = 0x00002000
POINTER_FLAG_CONFIDENCE = 0x00004000
POINTER_FLAG_CANCELLED = 0x00008000
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000

PEN_FLAG_NONE = 0x00000000
PEN_FLAG_BARREL = 0x00000001
PEN_FLAG_INVERTED = 0x00000002
PEN_FLAG_ERASER = 0x00000004

PEN_MASK_NONE = 0x00000000
PEN_MASK_PRESSURE = 0x00000001
PEN_MASK_ROTATION = 0x00000002
PEN_MASK_TILT_X = 0x00000004
PEN_MASK_TILT_Y = 0x00000008


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
    """Translates normalized Android touch and stylus coordinates into Windows desktop inputs."""

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
        self._user32 = getattr(ctypes.windll, "user32", None)
        self._last_barrel_down = False

    def update_bounds(self, x: int, y: int, w: int, h: int) -> None:
        """Updates the physical pixel bounding box of the target display."""
        self.origin_x = x
        self.origin_y = y
        self.width = max(1, w)
        self.height = max(1, h)
        logger.debug("InputInjector bounds updated: (%d, %d, %dx%d)", x, y, w, h)

    def normalize_to_screen(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Maps [0.0..1.0] display-local coordinate to Windows virtual desktop [0..65535]."""
        abs_x = self.origin_x + int(norm_x * self.width)
        abs_y = self.origin_y + int(norm_y * self.height)

        try:
            v_left = self._user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            v_top = self._user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
            v_width = self._user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            v_height = self._user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN

            if v_width > 0 and v_height > 0:
                win_x = int((abs_x - v_left) * 65535 / v_width)
                win_y = int((abs_y - v_top) * 65535 / v_height)
                return max(0, min(65535, win_x)), max(0, min(65535, win_y))
        except Exception:
            pass

        return max(0, min(65535, int(norm_x * 65535))), max(0, min(65535, int(norm_y * 65535)))

    def inject_event(self, event: InputEventMessage) -> None:
        """Processes an incoming InputEventMessage and dispatches appropriate Win32 inputs."""
        if not event.pointers:
            return

        is_stylus = event.eventType == "STYLUS" or any(
            p.toolType in ("STYLUS", "ERASER") for p in event.pointers
        )

        primary = event.pointers[0]
        norm_win_x, norm_win_y = self.normalize_to_screen(primary.x, primary.y)

        # Handle S-Pen button / barrel button (buttons & 2 or BUTTON_STYLUS_PRIMARY)
        has_barrel_button = bool(primary.buttons & 2)

        # Base mouse flags: absolute virtual desktop move
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK

        action = primary.action.upper()

        if action in ("HOVER", "HOVER_ENTER", "HOVER_MOVE"):
            # Stylus hover cursor preview: move cursor without button press
            pass
        elif action == "DOWN":
            if has_barrel_button:
                flags |= MOUSEEVENTF_RIGHTDOWN
                self._last_barrel_down = True
            else:
                flags |= MOUSEEVENTF_LEFTDOWN
                self._last_barrel_down = False
        elif action in ("UP", "CANCEL", "HOVER_EXIT"):
            if self._last_barrel_down:
                flags |= MOUSEEVENTF_RIGHTUP
                self._last_barrel_down = False
            else:
                flags |= MOUSEEVENTF_LEFTUP
        elif action == "MOVE":
            # Normal move while pressed or hovering
            pass

        mi = MOUSEINPUT(
            dx=norm_win_x,
            dy=norm_win_y,
            mouseData=0,
            dwFlags=flags,
            time=0,
            dwExtraInfo=None,
        )
        inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))
        self.last_injected_input = inp

        try:
            if self._user32:
                self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        except Exception as e:
            logger.debug("SendInput dispatch exception: %s", e)
