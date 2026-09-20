"""Display configuration and virtual monitor mode management."""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class DisplayMode:
    width_px: int
    height_px: int
    refresh_rate_hz: float


# Standard resolutions supported by OpenDisplay USB
STANDARD_MODES: List[DisplayMode] = [
    DisplayMode(1920, 1080, 60.0),
    DisplayMode(1920, 1200, 60.0),
    DisplayMode(2000, 1200, 60.0),  # Common 10.4" Android tablet (e.g. Galaxy Tab A7)
    DisplayMode(2560, 1600, 60.0),  # High-res tablet
    DisplayMode(1280, 800, 60.0),
    DisplayMode(1920, 1080, 120.0), # High refresh rate
]


class DisplayManager:
    """Manages active display configuration and aspect ratio adaptation."""

    def __init__(self, width: int = 1920, height: int = 1080, fps: float = 60.0):
        self.current_width = width
        self.current_height = height
        self.current_fps = fps

    def select_best_mode(self, client_max_w: int, client_max_h: int, client_fps: float) -> DisplayMode:
        """Picks the closest matching standard mode within device capability constraints."""
        for mode in STANDARD_MODES:
            if (
                mode.width_px <= client_max_w
                and mode.height_px <= client_max_h
                and mode.refresh_rate_hz <= client_fps
            ):
                return mode
        # Fallback to requested dimensions directly
        return DisplayMode(min(1920, client_max_w), min(1080, client_max_h), min(60.0, client_fps))
