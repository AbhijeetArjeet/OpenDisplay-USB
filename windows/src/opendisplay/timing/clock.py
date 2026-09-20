import sys
import time
import ctypes
from collections import deque
import statistics
from typing import Optional, List, Deque


class WindowsPrecisionTimer:
    """Configures Windows multimedia timer resolution to 1ms for 60+ FPS pacing."""
    _enabled: bool = False

    @classmethod
    def enable(cls) -> None:
        if sys.platform == "win32" and not cls._enabled:
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)
                cls._enabled = True
            except Exception:
                pass

    @classmethod
    def disable(cls) -> None:
        if sys.platform == "win32" and cls._enabled:
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
                cls._enabled = False
            except Exception:
                pass


class MonotonicClock:
    """High-resolution monotonic clock returning nanoseconds using time.perf_counter_ns()."""

    @staticmethod
    def now_nanos() -> int:
        return time.perf_counter_ns()

    @staticmethod
    def now_micros() -> int:
        return time.perf_counter_ns() // 1_000

    @staticmethod
    def now_millis() -> int:
        return time.perf_counter_ns() // 1_000_000


class ClockSync:
    """Tracks round-trip latency, jitter, clock drift, and offset between Windows host and Android device."""

    def __init__(self, history_size: int = 20):
        self.history_size = history_size
        self._rtt_history: Deque[float] = deque(maxlen=history_size)
        self._offset_history: Deque[int] = deque(maxlen=history_size)

        self.round_trip_latency_ms: float = 0.0
        self.median_rtt_ms: float = 0.0
        self.rtt_jitter_ms: float = 0.0
        self.estimated_latency_ms: float = 0.0
        self.offset_nanos: int = 0
        self.drift_ppm: float = 0.0

        self._first_sync_time_ns: Optional[int] = None
        self._first_offset_nanos: Optional[int] = None
        self.last_ping_sent_ns: Optional[int] = None

    @property
    def is_synced(self) -> bool:
        """Returns True if at least one clock sync exchange with server timestamp has occurred."""
        return len(self._offset_history) > 0

    def on_ping_sent(self) -> int:
        """Records the timestamp when a PING is sent. Returns the timestamp in nanoseconds."""
        now_ns = MonotonicClock.now_nanos()
        self.last_ping_sent_ns = now_ns
        return now_ns

    def on_pong_received(self, ping_timestamp_ns: int, server_timestamp_ns: Optional[int] = None) -> float:
        """Processes an incoming PONG message and updates clock synchronization models."""
        now_ns = MonotonicClock.now_nanos()
        rtt_ns = max(0, now_ns - ping_timestamp_ns)
        rtt_ms = rtt_ns / 1_000_000.0

        self._rtt_history.append(rtt_ms)
        self.round_trip_latency_ms = rtt_ms
        self.median_rtt_ms = statistics.median(self._rtt_history)

        if len(self._rtt_history) > 1:
            self.rtt_jitter_ms = statistics.pstdev(self._rtt_history)
        else:
            self.rtt_jitter_ms = 0.0

        self.estimated_latency_ms = self.median_rtt_ms / 2.0

        if server_timestamp_ns is not None:
            # Device time = Host time - offset_nanos => offset_nanos = Host time - Device time
            one_way_ns = int((self.median_rtt_ms * 1_000_000) / 2)
            calculated_offset = (ping_timestamp_ns + one_way_ns) - server_timestamp_ns
            self._offset_history.append(calculated_offset)

            # Use median offset to reject outlier network jitter
            self.offset_nanos = int(statistics.median(self._offset_history))

            # Drift estimation over session duration
            if self._first_sync_time_ns is None:
                self._first_sync_time_ns = now_ns
                self._first_offset_nanos = self.offset_nanos
            else:
                elapsed_session_ns = now_ns - self._first_sync_time_ns
                if elapsed_session_ns > 10_000_000_000:  # After 10 seconds of session
                    offset_delta = self.offset_nanos - (self._first_offset_nanos or 0)
                    self.drift_ppm = (offset_delta / elapsed_session_ns) * 1_000_000.0

        return self.round_trip_latency_ms

    def host_to_device_ns(self, host_ns: int) -> int:
        """Translates a Windows host monotonic timestamp into estimated Android monotonic timestamp."""
        return host_ns - self.offset_nanos

    def device_to_host_ns(self, device_ns: int) -> int:
        """Translates an Android monotonic timestamp into estimated Windows host monotonic timestamp."""
        return device_ns + self.offset_nanos
