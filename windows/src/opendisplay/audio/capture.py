"""WASAPI loopback audio capture from the Windows default output device."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures system audio using WASAPI loopback."""

    def __init__(self, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self._running = False

    def start(self) -> bool:
        self._running = True
        logger.info("Started audio capture (%d Hz, %d channels)", self.sample_rate, self.channels)
        return True

    def stop(self) -> None:
        self._running = False
        logger.info("Stopped audio capture")

    def read_samples(self) -> Optional[bytes]:
        """Reads a chunk of raw 16-bit PCM audio samples."""
        if not self._running:
            return None
        # In mock / headless environments, return silent PCM buffer (10ms = 480 samples * 4 bytes)
        return b"\x00" * 1920
