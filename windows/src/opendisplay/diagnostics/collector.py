"""Diagnostics and comprehensive latency metrics aggregation (T0 to T10)."""

import time
import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Tuple, Optional, Dict, List


@dataclass
class LatencyPercentiles:
    p50: float = 0.0
    p90: float = 0.0
    p99: float = 0.0
    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0


@dataclass
class DiagnosticsSnapshot:
    fps: float = 0.0
    bitrate_kbps: float = 0.0
    rtt_latency_ms: float = 0.0
    rtt_jitter_ms: float = 0.0
    clock_drift_ppm: float = 0.0

    # Pipeline Latencies (ms)
    capture_latency_ms: Optional[float] = None     # T1 - T0
    encode_latency_ms: Optional[float] = None      # T3 - T2
    transport_latency_ms: Optional[float] = None   # T6 - T5
    decode_latency_ms: Optional[float] = None      # T8 - T7
    render_latency_ms: Optional[float] = None      # T9 - T8
    end_to_end_latency_ms: Optional[float] = None  # T9 - T0

    # Percentiles
    percentiles: Dict[str, LatencyPercentiles] = field(default_factory=dict)

    # Counters
    frames_sent: int = 0
    keyframes_sent: int = 0
    bytes_sent: int = 0
    packets_dropped: int = 0
    reconnect_count: int = 0
    input_events_received: int = 0
    input_latency_ms: Optional[float] = None
    av_drift_ms: Optional[float] = None


class DiagnosticsCollector:
    """Aggregates real-time performance and pipeline latency metrics over rolling windows."""

    def __init__(self, window_seconds: float = 1.0, max_history: int = 100):
        self.window_seconds = window_seconds
        self.max_history = max_history

        self._frame_times: Deque[float] = deque()
        self._byte_records: Deque[Tuple[float, int]] = deque()

        # Latency samples (ms)
        self._capture_latencies: Deque[float] = deque(maxlen=max_history)
        self._encode_latencies: Deque[float] = deque(maxlen=max_history)
        self._transport_latencies: Deque[float] = deque(maxlen=max_history)
        self._decode_latencies: Deque[float] = deque(maxlen=max_history)
        self._render_latencies: Deque[float] = deque(maxlen=max_history)
        self._e2e_latencies: Deque[float] = deque(maxlen=max_history)
        self._input_latencies: Deque[float] = deque(maxlen=max_history)

        self.frames_sent = 0
        self.keyframes_sent = 0
        self.bytes_sent = 0
        self.packets_dropped = 0
        self.reconnect_count = 0
        self.input_events_count = 0

        self.current_rtt_ms = 0.0
        self.current_rtt_jitter_ms = 0.0
        self.current_drift_ppm = 0.0
        self.current_av_drift_ms: Optional[float] = None

    def record_frame(
        self,
        byte_size: int,
        is_keyframe: bool,
        capture_ms: Optional[float] = None,
        encode_ms: Optional[float] = None,
    ) -> None:
        now = time.monotonic()
        self._frame_times.append(now)
        self._byte_records.append((now, byte_size))

        self.frames_sent += 1
        if is_keyframe:
            self.keyframes_sent += 1
        self.bytes_sent += byte_size

        if capture_ms is not None:
            self._capture_latencies.append(capture_ms)
        if encode_ms is not None:
            self._encode_latencies.append(encode_ms)

        self._evict(now)

    def record_rtt(self, rtt_ms: float, jitter_ms: float = 0.0, drift_ppm: float = 0.0) -> None:
        self.current_rtt_ms = rtt_ms
        self.current_rtt_jitter_ms = jitter_ms
        self.current_drift_ppm = drift_ppm

    def record_receiver_telemetry(
        self,
        transport_ms: Optional[float] = None,
        decode_ms: Optional[float] = None,
        render_ms: Optional[float] = None,
        e2e_ms: Optional[float] = None
    ) -> None:
        if transport_ms is not None:
            self._transport_latencies.append(transport_ms)
        if decode_ms is not None:
            self._decode_latencies.append(decode_ms)
        if render_ms is not None:
            self._render_latencies.append(render_ms)
        if e2e_ms is not None:
            self._e2e_latencies.append(e2e_ms)

    def record_input_latency(self, latency_ms: float) -> None:
        self.input_events_count += 1
        self._input_latencies.append(latency_ms)

    def record_av_drift(self, drift_ms: float) -> None:
        self.current_av_drift_ms = drift_ms

    def record_reconnect(self) -> None:
        self.reconnect_count += 1

    def record_drop(self) -> None:
        self.packets_dropped += 1

    def get_snapshot(self) -> DiagnosticsSnapshot:
        now = time.monotonic()
        self._evict(now)

        # FPS calculation
        fps = 0.0
        if len(self._frame_times) > 1:
            duration = now - self._frame_times[0]
            if duration > 0:
                fps = (len(self._frame_times) - 1) / duration

        # Bitrate calculation (Kbps)
        bitrate_kbps = 0.0
        if self._byte_records:
            duration = min(self.window_seconds, max(0.001, now - self._byte_records[0][0]))
            total_bytes = sum(b for _, b in self._byte_records)
            bitrate_kbps = (total_bytes * 8.0) / duration / 1000.0

        percentiles: Dict[str, LatencyPercentiles] = {}
        for name, series in [
            ("capture", self._capture_latencies),
            ("encode", self._encode_latencies),
            ("transport", self._transport_latencies),
            ("decode", self._decode_latencies),
            ("render", self._render_latencies),
            ("e2e", self._e2e_latencies),
            ("input", self._input_latencies)
        ]:
            if series:
                s = sorted(series)
                n = len(s)
                percentiles[name] = LatencyPercentiles(
                    p50=s[int(n * 0.50)],
                    p90=s[min(n - 1, int(n * 0.90))],
                    p99=s[min(n - 1, int(n * 0.99))],
                    min=s[0],
                    max=s[-1],
                    avg=statistics.mean(s)
                )

        # Current point estimates (or average of recent)
        cap_ms = percentiles["capture"].avg if "capture" in percentiles else None
        enc_ms = percentiles["encode"].avg if "encode" in percentiles else None
        trans_ms = percentiles["transport"].avg if "transport" in percentiles else (self.current_rtt_ms / 2.0 if self.current_rtt_ms > 0 else None)
        dec_ms = percentiles["decode"].avg if "decode" in percentiles else None
        rend_ms = percentiles["render"].avg if "render" in percentiles else None

        e2e_calc = None
        if "e2e" in percentiles:
            e2e_calc = percentiles["e2e"].avg
        elif cap_ms and enc_ms and trans_ms:
            e2e_calc = cap_ms + enc_ms + trans_ms + (dec_ms or 0.0) + (rend_ms or 0.0)

        input_lat = percentiles["input"].avg if "input" in percentiles else None

        return DiagnosticsSnapshot(
            fps=fps,
            bitrate_kbps=bitrate_kbps,
            rtt_latency_ms=self.current_rtt_ms,
            rtt_jitter_ms=self.current_rtt_jitter_ms,
            clock_drift_ppm=self.current_drift_ppm,
            capture_latency_ms=cap_ms,
            encode_latency_ms=enc_ms,
            transport_latency_ms=trans_ms,
            decode_latency_ms=dec_ms,
            render_latency_ms=rend_ms,
            end_to_end_latency_ms=e2e_calc,
            percentiles=percentiles,
            frames_sent=self.frames_sent,
            keyframes_sent=self.keyframes_sent,
            bytes_sent=self.bytes_sent,
            packets_dropped=self.packets_dropped,
            reconnect_count=self.reconnect_count,
            input_events_received=self.input_events_count,
            input_latency_ms=input_lat,
            av_drift_ms=self.current_av_drift_ms
        )

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._frame_times and self._frame_times[0] < cutoff:
            self._frame_times.popleft()
        while self._byte_records and self._byte_records[0][0] < cutoff:
            self._byte_records.popleft()
