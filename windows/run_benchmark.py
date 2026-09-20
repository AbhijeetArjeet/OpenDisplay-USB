#!/usr/bin/env python3
"""OpenDisplay USB Phase 3 Automated Latency & Hardware Benchmark CLI."""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from opendisplay.diagnostics.benchmark import BenchmarkRunner
from opendisplay.session.adaptive import PerformanceProfile


def parse_args():
    parser = argparse.ArgumentParser(description="OpenDisplay USB Phase 3 Automated Benchmark")
    parser.add_argument(
        "--duration",
        type=int,
        default=15,
        help="Benchmark duration in seconds (e.g. 10, 15, 30, 60, 300)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="low_latency",
        choices=["low_latency", "balanced", "quality", "battery_saver", "automatic"],
        help="Performance profile mode"
    )
    parser.add_argument(
        "--codec",
        type=str,
        default="H264",
        choices=["H264", "HEVC", "h264", "hevc"],
        help="Preferred video codec"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="ADB forwarded host IP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7320,
        help="TCP port (default: 7320)"
    )
    parser.add_argument(
        "--screen-capture",
        action="store_true",
        help="Use desktop screen capture instead of synthetic test pattern"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to output JSON file (defaults to benchmark_results_<timestamp>.json)"
    )
    return parser.parse_args()


async def main_async():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    profile_map = {
        "low_latency": PerformanceProfile.LOW_LATENCY,
        "balanced": PerformanceProfile.BALANCED,
        "quality": PerformanceProfile.QUALITY,
        "battery_saver": PerformanceProfile.BATTERY_SAVER,
        "automatic": PerformanceProfile.AUTOMATIC
    }
    profile = profile_map[args.mode.lower()]
    preferred_codec = args.codec.upper()

    runner = BenchmarkRunner(
        host=args.host,
        port=args.port,
        duration_s=args.duration,
        profile=profile,
        preferred_codec=preferred_codec,
        use_synthetic_video=not args.screen_capture
    )

    try:
        report = await runner.run()
    except Exception as e:
        logging.error("Benchmark failed with error: %s", e, exc_info=True)
        sys.exit(1)

    json_output = json.dumps(report, indent=2)
    print("\n" + "=" * 50 + " BENCHMARK REPORT " + "=" * 50)
    print(json_output)
    print("=" * 118 + "\n")

    output_path = args.output
    if not output_path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = f"benchmark_results_{args.mode}_{ts}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_output)
    logging.info("Benchmark report saved to %s", output_path)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
