"""Phase 0: Latency measurement harness and synthetic frame source.

Measures stage-by-stage timestamps in microseconds across the entire pipeline:
- T0: Capture start / acquire
- T1: Capture complete (raw pixel buffer ready)
- T2: Encode start
- T3: Encode complete (NAL buffer ready)
- T4: Packet serialized
- T5: Socket flush complete (transmitted over wire)
- T6: Device received packet
- T7: Device decoder submitted
- T8: Device buffer rendered (Choreographer / vsync)
"""

import time
import json
import csv
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def get_monotonic_us() -> int:
    """Returns monotonic time in microseconds."""
    return time.perf_counter_ns() // 1000


@dataclass
class FrameMetrics:
    frame_id: int
    t0_capture_start_us: int = 0
    t1_capture_end_us: int = 0
    t2_encode_start_us: int = 0
    t3_encode_end_us: int = 0
    t4_packet_ready_us: int = 0
    t5_socket_sent_us: int = 0
    t6_device_recv_us: int = 0
    t7_device_decode_us: int = 0
    t8_device_render_us: int = 0
    is_keyframe: bool = False
    payload_bytes: int = 0

    @property
    def capture_latency_ms(self) -> float:
        return max(0.0, (self.t1_capture_end_us - self.t0_capture_start_us) / 1000.0)

    @property
    def encode_latency_ms(self) -> float:
        return max(0.0, (self.t3_encode_end_us - self.t2_encode_start_us) / 1000.0)

    @property
    def packet_send_latency_ms(self) -> float:
        return max(0.0, (self.t5_socket_sent_us - self.t3_encode_end_us) / 1000.0)

    @property
    def host_total_latency_ms(self) -> float:
        return max(0.0, (self.t5_socket_sent_us - self.t0_capture_start_us) / 1000.0)

    @property
    def device_decode_latency_ms(self) -> float:
        if self.t7_device_decode_us > 0 and self.t6_device_recv_us > 0:
            return max(0.0, (self.t7_device_decode_us - self.t6_device_recv_us) / 1000.0)
        return 0.0

    @property
    def glass_to_glass_latency_ms(self) -> float:
        if self.t8_device_render_us > 0 and self.t0_capture_start_us > 0:
            return max(0.0, (self.t8_device_render_us - self.t0_capture_start_us) / 1000.0)
        return 0.0


class MeasurementHarness:
    """Collects, analyzes, and exports per-stage latency metrics."""

    def __init__(self):
        self.records: List[FrameMetrics] = []
        self._current: Dict[int, FrameMetrics] = {}
        self._start_wall_time = time.time()

    def start_frame(self, frame_id: int) -> FrameMetrics:
        fm = FrameMetrics(
            frame_id=frame_id,
            t0_capture_start_us=get_monotonic_us()
        )
        self._current[frame_id] = fm
        return fm

    def mark_capture_end(self, frame_id: int):
        if frame_id in self._current:
            self._current[frame_id].t1_capture_end_us = get_monotonic_us()

    def mark_encode_start(self, frame_id: int):
        if frame_id in self._current:
            self._current[frame_id].t2_encode_start_us = get_monotonic_us()

    def mark_encode_end(self, frame_id: int, is_keyframe: bool = False, payload_bytes: int = 0):
        if frame_id in self._current:
            fm = self._current[frame_id]
            fm.t3_encode_end_us = get_monotonic_us()
            fm.is_keyframe = is_keyframe
            fm.payload_bytes = payload_bytes

    def mark_packet_ready(self, frame_id: int):
        if frame_id in self._current:
            self._current[frame_id].t4_packet_ready_us = get_monotonic_us()

    def mark_socket_sent(self, frame_id: int):
        if frame_id in self._current:
            fm = self._current[frame_id]
            fm.t5_socket_sent_us = get_monotonic_us()
            self.records.append(fm)
            # Keep map size bounded
            if len(self._current) > 200:
                del self._current[min(self._current.keys())]

    def record_device_feedback(self, frame_id: int, t6_recv_us: int, t7_decode_us: int, t8_render_us: int):
        """Updates frame record with Android receiver timestamps."""
        for rec in reversed(self.records[-100:]):
            if rec.frame_id == frame_id:
                rec.t6_device_recv_us = t6_recv_us
                rec.t7_device_decode_us = t7_decode_us
                rec.t8_device_render_us = t8_render_us
                break

    def compute_summary(self) -> Dict[str, Any]:
        """Computes p50, p95, p99, min, max, stddev across all stages."""
        if not self.records:
            return {"error": "No records collected"}

        captures = np.array([r.capture_latency_ms for r in self.records])
        encodes = np.array([r.encode_latency_ms for r in self.records])
        transports = np.array([r.packet_send_latency_ms for r in self.records])
        host_totals = np.array([r.host_total_latency_ms for r in self.records])

        # Framerate computation
        if len(self.records) > 1:
            duration_s = (self.records[-1].t5_socket_sent_us - self.records[0].t0_capture_start_us) / 1e6
            fps = len(self.records) / max(0.001, duration_s)
        else:
            fps = 0.0

        def stats(arr: np.ndarray) -> Dict[str, float]:
            if len(arr) == 0:
                return {}
            return {
                "p50": float(np.percentile(arr, 50)),
                "p95": float(np.percentile(arr, 95)),
                "p99": float(np.percentile(arr, 99)),
                "mean": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "std": float(np.std(arr)),
            }

        summary = {
            "total_frames": len(self.records),
            "effective_fps": round(fps, 2),
            "capture_ms": stats(captures),
            "encode_ms": stats(encodes),
            "packet_send_ms": stats(transports),
            "host_total_ms": stats(host_totals),
        }

        # Optional device timings if received
        g2g = np.array([r.glass_to_glass_latency_ms for r in self.records if r.glass_to_glass_latency_ms > 0])
        if len(g2g) > 0:
            summary["glass_to_glass_ms"] = stats(g2g)

        return summary

    def export_csv(self, file_path: str):
        """Exports raw frame metrics to CSV."""
        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "frame_id", "is_keyframe", "payload_bytes",
                "capture_ms", "encode_ms", "send_ms", "host_total_ms",
                "device_decode_ms", "glass_to_glass_ms"
            ])
            for r in self.records:
                writer.writerow([
                    r.frame_id, r.is_keyframe, r.payload_bytes,
                    f"{r.capture_latency_ms:.3f}",
                    f"{r.encode_latency_ms:.3f}",
                    f"{r.packet_send_latency_ms:.3f}",
                    f"{r.host_total_latency_ms:.3f}",
                    f"{r.device_decode_latency_ms:.3f}",
                    f"{r.glass_to_glass_latency_ms:.3f}",
                ])

    def export_json(self, file_path: str):
        """Exports full summary and metadata to JSON."""
        data = {
            "summary": self.compute_summary(),
            "records": [asdict(r) for r in self.records]
        }
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)


class SyntheticFrameSource:
    """Generates synthetic test patterns with burnt-in frame counter and microsecond timestamps."""

    def __init__(self, width: int = 1920, height: int = 1080, target_fps: float = 60.0):
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.frame_count = 0
        self._font = None
        try:
            self._font = ImageFont.load_default()
        except Exception:
            pass

    def generate_frame(self) -> np.ndarray:
        """Generates a high-contrast BGRA test frame with burnt-in precision timestamp."""
        self.frame_count += 1
        now_us = get_monotonic_us()

        # Create dark background image
        img = Image.new("RGBA", (self.width, self.height), color=(20, 24, 32, 255))
        draw = ImageDraw.Draw(img)

        # Draw moving horizontal and vertical sync bars to visually test tearing & smoothness
        pos_x = int((self.frame_count * 8) % self.width)
        pos_y = int((self.frame_count * 5) % self.height)
        draw.line([(pos_x, 0), (pos_x, self.height)], fill=(0, 255, 128, 255), width=3)
        draw.line([(0, pos_y), (self.width, pos_y)], fill=(0, 180, 255, 255), width=3)

        # Draw burnt-in timestamp badge
        badge_text = (
            f"OPENDISPLAY BENCHMARK HARNESS\n"
            f"Frame: {self.frame_count:07d}\n"
            f"Timestamp: {now_us} us\n"
            f"Resolution: {self.width}x{self.height} @ {self.target_fps:.1f} FPS"
        )
        draw.rectangle([40, 40, 520, 160], fill=(0, 0, 0, 200), outline=(0, 255, 200, 255), width=2)
        draw.text((60, 55), badge_text, fill=(255, 255, 255, 255), font=self._font)

        # Convert RGBA to BGRA numpy array
        arr = np.array(img, dtype=np.uint8)
        # Swap R and B channels for BGRA format expected by DIB / PyAV
        bgra = np.empty_like(arr)
        bgra[..., 0] = arr[..., 2]  # B
        bgra[..., 1] = arr[..., 1]  # G
        bgra[..., 2] = arr[..., 0]  # R
        bgra[..., 3] = arr[..., 3]  # A
        return bgra
