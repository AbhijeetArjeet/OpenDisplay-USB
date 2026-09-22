"""Virtual display management and programmatic display extension for Windows."""

import ctypes
from ctypes import wintypes
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Win32 Constants
CCHDEVICENAME = 32
CCHFORMNAME = 32

# Display device state flags
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x00000008
DISPLAY_DEVICE_VGA_COMPATIBLE = 0x00000010

# ChangeDisplaySettings flags
CDS_UPDATEREGISTRY = 0x00000001
CDS_TEST = 0x00000002
CDS_FULLSCREEN = 0x00000004
CDS_GLOBAL = 0x00000008
CDS_SET_PRIMARY = 0x00000010
CDS_NORESET = 0x10000000
CDS_RESET = 0x40000000

DISP_CHANGE_SUCCESSFUL = 0
DISP_CHANGE_RESTART = 1
DISP_CHANGE_FAILED = -1
DISP_CHANGE_BADMODE = -2
DISP_CHANGE_NOTUPDATED = -3
DISP_CHANGE_BADFLAGS = -4
DISP_CHANGE_BADPARAM = -5

# DEVMODE fields
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_POSITION = 0x00000020
DM_BITSPERPEL = 0x00040000
DM_DISPLAYFREQUENCY = 0x00400000


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * CCHDEVICENAME),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * CCHDEVICENAME),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", wintypes.LONG),
        ("dmPositionY", wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * CCHFORMNAME),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


@dataclass
class DisplayResolution:
    width: int
    height: int
    refresh_rate: int = 60


@dataclass
class VirtualDisplayInfo:
    device_name: str
    device_string: str
    device_id: str
    is_attached: bool
    is_primary: bool
    current_width: int = 0
    current_height: int = 0
    current_refresh: int = 0
    supported_resolutions: List[DisplayResolution] = field(default_factory=list)


import atexit

class VirtualDisplayManager:
    """Manages discovery, programmatic extension, and lifecycle of virtual display monitors."""

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._attached_by_us = False
        try:
            atexit.register(self.teardown)
        except Exception:
            pass

    def enumerate_displays(self) -> List[VirtualDisplayInfo]:
        """Enumerates all display devices reported by Win32 EnumDisplayDevicesW."""
        displays: List[VirtualDisplayInfo] = []
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        index = 0

        while self._user32.EnumDisplayDevicesW(None, index, ctypes.byref(dd), 0):
            is_attached = bool(dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP)
            is_primary = bool(dd.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE)
            
            # Query current resolution if attached
            cur_w, cur_h, cur_ref = 0, 0, 0
            supported: List[DisplayResolution] = []
            
            dm = DEVMODEW()
            dm.dmSize = ctypes.sizeof(DEVMODEW)
            if self._user32.EnumDisplaySettingsW(dd.DeviceName, -1, ctypes.byref(dm)):
                cur_w = dm.dmPelsWidth
                cur_h = dm.dmPelsHeight
                cur_ref = dm.dmDisplayFrequency

            # Query supported modes
            mode_num = 0
            seen_res = set()
            while self._user32.EnumDisplaySettingsW(dd.DeviceName, mode_num, ctypes.byref(dm)):
                key = (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency)
                if key not in seen_res:
                    seen_res.add(key)
                    supported.append(DisplayResolution(dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency))
                mode_num += 1
                if mode_num > 200:
                    break

            info = VirtualDisplayInfo(
                device_name=dd.DeviceName,
                device_string=dd.DeviceString,
                device_id=dd.DeviceID,
                is_attached=is_attached,
                is_primary=is_primary,
                current_width=cur_w,
                current_height=cur_h,
                current_refresh=cur_ref,
                supported_resolutions=supported,
            )
            displays.append(info)
            index += 1

        return displays

    def find_virtual_displays(self) -> List[VirtualDisplayInfo]:
        """Returns all displays that belong to a virtual display driver (IddCx / MttVDD)."""
        all_displays = self.enumerate_displays()
        vds = []
        for d in all_displays:
            lower_name = d.device_string.lower()
            lower_id = d.device_id.lower()
            if "virtual" in lower_name or "mttvdd" in lower_id or "vdd" in lower_name:
                vds.append(d)
        return vds

    def get_primary_display(self) -> Optional[VirtualDisplayInfo]:
        """Returns the primary active display device."""
        for d in self.enumerate_displays():
            if d.is_primary and d.is_attached:
                return d
        return None

    def is_extended(self) -> bool:
        """Returns True if there is more than 1 display attached to desktop."""
        attached = [d for d in self.enumerate_displays() if d.is_attached]
        return len(attached) > 1

    def enable_extend_mode(self) -> bool:
        """Programmatically instructs Windows to extend desktop across available monitors."""
        try:
            logger.info("Executing displayswitch.exe /extend to enable secondary monitor")
            res = subprocess.run(["displayswitch.exe", "/extend"], check=False, capture_output=True)
            time.sleep(1.0)
            self._attached_by_us = True
            return res.returncode == 0
        except Exception as e:
            logger.warning("Failed to invoke displayswitch /extend: %s", e)
            return False

    def disable_extend_mode(self) -> bool:
        """Restores single primary display topology (teardown)."""
        try:
            logger.info("Restoring single primary desktop topology (displayswitch /internal)")
            res = subprocess.run(["displayswitch.exe", "/internal"], check=False, capture_output=True)
            time.sleep(0.5)
            self._attached_by_us = False
            return res.returncode == 0
        except Exception as e:
            logger.warning("Failed to invoke displayswitch /internal: %s", e)
            return False

    def auto_configure_for_client(self, client_w: int, client_h: int, client_fps: float) -> Optional[DisplayResolution]:
        """Picks the best supported resolution for the virtual display matching the client device."""
        vds = self.find_virtual_displays()
        if not vds:
            return None

        primary_vd = vds[0]
        # Look for exact or close match
        best: Optional[DisplayResolution] = None
        for res in primary_vd.supported_resolutions:
            if res.width == client_w and res.height == client_h:
                if best is None or abs(res.refresh_rate - client_fps) < abs(best.refresh_rate - client_fps):
                    best = res

        if best:
            logger.info("Selected optimal virtual display mode: %dx%d @ %dHz", best.width, best.height, best.refresh_rate)
            return best

        return DisplayResolution(width=min(1920, client_w), height=min(1080, client_h), refresh_rate=60)

    def teardown(self) -> None:
        """Cleanly releases any display configuration managed during session."""
        if self._attached_by_us:
            logger.info("Cleaning up virtual display extension on session end")
            self.disable_extend_mode()
            self._attached_by_us = False
