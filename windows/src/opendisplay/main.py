"""Main application entry point for OpenDisplay USB Windows Client."""

import sys
import argparse
import asyncio
import logging
from PyQt6.QtWidgets import QApplication
from .diagnostics.collector import DiagnosticsCollector
from .input.injector import InputInjector
from .transport.mock_transport import MockTransport
from .transport.adb_transport import AdbTransport
from .session.session_manager import SessionManager
from .ui.main_window import MainWindow

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("OpenDisplayMain")


def main():
    parser = argparse.ArgumentParser(description="OpenDisplay USB — Windows Host Client")
    parser.add_argument("--mock", action="store_true", help="Run with MockTransport loopback")
    parser.add_argument("--port", type=int, default=7320, help="Target TCP/ADB port")
    parser.add_argument("--cli", action="store_true", help="Run headless in terminal mode")
    args = parser.parse_args()

    diagnostics = DiagnosticsCollector()
    input_injector = InputInjector()

    if args.cli:
        transport = MockTransport() if args.mock else AdbTransport(port=args.port)
        session = SessionManager(transport=transport, diagnostics=diagnostics, input_injector=input_injector)

        async def run_cli():
            logger.info("Starting OpenDisplay USB in CLI mode (mock=%s)...", args.mock)
            await session.start()
            try:
                while True:
                    await asyncio.sleep(1.0)
                    snap = diagnostics.get_snapshot()
                    logger.info(
                        "Diagnostics: %.1f FPS | %.2f Mbps | Latency: %.1f ms | Frames: %d",
                        snap.fps, snap.bitrate_kbps / 1000.0, snap.rtt_latency_ms, snap.frames_sent
                    )
            except (KeyboardInterrupt, asyncio.CancelledError):
                logger.info("Stopping CLI session...")
                await session.stop()

        asyncio.run(run_cli())
    else:
        app = QApplication(sys.argv)
        window = MainWindow(diagnostics=diagnostics)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
