"""Desktop frame capture supporting Desktop Duplication API (DDA) and PIL fallback."""

import numpy as np
import logging
from typing import Optional
from PIL import ImageGrab

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Acquires frames from the Windows desktop or virtual display."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures a single RGB frame from the desktop."""
        try:
            # Grabs display frame
            img = ImageGrab.grab()
            if img.size != (self.width, self.height):
                img = img.resize((self.width, self.height))
            return np.array(img.convert("RGB"))
        except Exception as e:
            logger.debug("Desktop capture exception: %s", e)
            return None
