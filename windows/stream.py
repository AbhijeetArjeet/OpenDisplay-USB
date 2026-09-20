#!/usr/bin/env python3
"""Continuous live desktop streaming script for OpenDisplay USB."""

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from opendisplay.diagnostics.collector import DiagnosticsCollector
from opendisplay.input.injector import InputInjector
from opendisplay.session.adaptive import PerformanceProfile
from opendisplay.session.session_manager import SessionManager
from opendisplay.transport.adb_transport import AdbTransport
from opendisplay.transport.tcp_transport import TcpTransport

logger = logging.getLogger("OpenDisplayStream")


def parse_args():
    parser = argparse.ArgumentParser(description="OpenDisplay USB — Live Desktop Streamer")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host IP (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7320, help="Port (default 7320)")
    parser.add_argument(
        "--mode",
        type=str,
        default="low_latency",
        choices=["low_latency", "balanced", "quality", "battery_saver", "automatic"],
        help="Performance profile"
    )
    parser.add_argument("--codec", type=str, default="H264", choices=["H264", "HEVC"], help="Preferred codec")
    parser.add_argument("--synthetic", action="store_true", help="Use test pattern instead of real screen capture")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio streaming")
    parser.add_argument("--no-clipboard", action="store_true", help="Disable clipboard sync")
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
        "automatic": PerformanceProfile.AUTOMATIC,
    }
    profile = profile_map[args.mode.lower()]

    logger.info("Initializing transport on %s:%d...", args.host, args.port)
    transport = AdbTransport(port=args.port)
    diagnostics = DiagnosticsCollector()
    input_injector = InputInjector()

    session = SessionManager(
        transport=transport,
        diagnostics=diagnostics,
        input_injector=input_injector,
        use_synthetic_video=args.synthetic,
        enable_audio=not args.no_audio,
        enable_clipboard=not args.no_clipboard,
        performance_profile=profile,
        preferred_codec=args.codec
    )

    logger.info("Starting OpenDisplay USB live stream (synthetic=%s, profile=%s)...", args.synthetic, args.mode)
    await session.start()

    try:
        while True:
            await asyncio.sleep(1.0)
            snap = diagnostics.get_snapshot()
            if snap.frames_sent > 0:
                print(
                    f"\r[STREAMING LIVE] FPS: {snap.fps:4.1f} | Bitrate: {snap.bitrate_kbps / 1000.0:4.2f} Mbps | "
                    f"RTT: {snap.rtt_latency_ms:5.1f} ms | Frames: {snap.frames_sent:5d} | Dropped: {snap.packets_dropped}",
                    end="",
                    flush=True
                )
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nStopping streaming session...")
        await session.stop()
        logger.info("Streaming stopped cleanly.")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
