#!/usr/bin/env python3
"""Phase 0 Baseline Benchmark: Measures current pipeline stages and identifies true bottlenecks."""

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from opendisplay.diagnostics.harness import MeasurementHarness, SyntheticFrameSource, get_monotonic_us
from opendisplay.display.capture import ScreenCapture
from opendisplay.video.encoder import VideoEncoder


def run_benchmark(duration_seconds: int = 10, target_fps: float = 60.0, use_synthetic: bool = False):
    print(f"=== Phase 0 Baseline Benchmark (duration={duration_seconds}s, synthetic={use_synthetic}) ===")
    
    harness = MeasurementHarness()
    
    if use_synthetic:
        frame_source = SyntheticFrameSource(width=1920, height=1080, target_fps=target_fps)
        capture = None
    else:
        capture = ScreenCapture()
        frame_source = None

    encoder = VideoEncoder(
        width=1920,
        height=1080,
        fps=target_fps,
        bitrate_bps=18_000_000,
        codec="H264"
    )
    print(f"Encoder initialized: {encoder.active_encoder_name} (HW={encoder.is_hardware})")

    frame_interval = 1.0 / target_fps
    start_time = time.time()
    frame_id = 0

    print("Benchmarking pipeline stages (Capture -> Format -> NVENC Encode)...")
    while time.time() - start_time < duration_seconds:
        frame_id += 1
        t_loop_start = time.perf_counter()

        # Stage 0-1: Capture
        harness.start_frame(frame_id)
        if use_synthetic:
            frame_bgra = frame_source.generate_frame()
        else:
            frame_bgra = capture.capture_bgra_frame()
        harness.mark_capture_end(frame_id)

        if frame_bgra is None:
            continue

        # Stage 2-3: Encode
        harness.mark_encode_start(frame_id)
        packets = encoder.encode_rgb_frame(frame_bgra, timestamp_ns=time.time_ns(), format="bgra")
        nal_len = sum(len(p.data) for p in packets)
        is_key = any(p.is_keyframe for p in packets)
        harness.mark_encode_end(frame_id, is_keyframe=is_key, payload_bytes=nal_len)

        # Stage 4-5: Packet/Send simulation (memory touch)
        harness.mark_packet_ready(frame_id)
        harness.mark_socket_sent(frame_id)

        # Pace to target FPS
        elapsed = time.perf_counter() - t_loop_start
        sleep_time = frame_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    summary = harness.compute_summary()
    print("\n================ BENCHMARK RESULTS ================")
    print(f"Total Frames Processed: {summary['total_frames']}")
    print(f"Effective Framerate:    {summary['effective_fps']} FPS (Target: {target_fps} FPS)")
    print("---------------------------------------------------")
    print(f"Capture Stage:  p50: {summary['capture_ms']['p50']:5.2f} ms | p95: {summary['capture_ms']['p95']:5.2f} ms | p99: {summary['capture_ms']['p99']:5.2f} ms")
    print(f"Encode Stage:   p50: {summary['encode_ms']['p50']:5.2f} ms | p95: {summary['encode_ms']['p95']:5.2f} ms | p99: {summary['encode_ms']['p99']:5.2f} ms")
    print(f"Host Total:     p50: {summary['host_total_ms']['p50']:5.2f} ms | p95: {summary['host_total_ms']['p95']:5.2f} ms | p99: {summary['host_total_ms']['p99']:5.2f} ms")
    print("===================================================\n")

    out_prefix = "benchmark_phase0_synthetic" if use_synthetic else "benchmark_phase0_gdi_desktop"
    json_path = os.path.join(os.path.dirname(__file__), f"{out_prefix}.json")
    csv_path = os.path.join(os.path.dirname(__file__), f"{out_prefix}.csv")
    harness.export_json(json_path)
    harness.export_csv(csv_path)
    print(f"Exported metrics to {json_path} and {csv_path}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=8, help="Benchmark duration in seconds")
    parser.add_argument("--fps", type=float, default=60.0, help="Target FPS")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic frame source")
    args = parser.parse_args()

    run_benchmark(duration_seconds=args.duration, target_fps=args.fps, use_synthetic=args.synthetic)
