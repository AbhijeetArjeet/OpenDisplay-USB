"""End-to-end integration and touch input verification script for OpenDisplay USB."""

import os
import sys
import asyncio
import logging
import subprocess

# Ensure src is in python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from opendisplay.transport.adb_transport import AdbTransport
from opendisplay.diagnostics.collector import DiagnosticsCollector
from opendisplay.input.injector import InputInjector
from opendisplay.session.session_manager import SessionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("VerifyE2E")


async def run_test():
    adb_path = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    if not os.path.exists(adb_path):
        adb_path = "adb"

    # Ensure port forward
    logger.info("Configuring ADB forward...")
    subprocess.run([adb_path, "forward", "tcp:7320", "tcp:7320"], check=True)

    diagnostics = DiagnosticsCollector()
    input_injector = InputInjector()
    transport = AdbTransport(port=7320)
    session = SessionManager(transport=transport, diagnostics=diagnostics, input_injector=input_injector)

    input_events_count = 0
    original_inject = input_injector.inject_event

    def tracking_inject(event):
        nonlocal input_events_count
        input_events_count += 1
        logger.info("TRACKED: Touch event #%d (type=%s, pointers=%d)", input_events_count, event.eventType, len(event.pointers))
        original_inject(event)

    input_injector.inject_event = tracking_inject

    logger.info("Starting OpenDisplay USB session...")
    await session.start()

    # Wait for STREAMING state
    for _ in range(50):
        await asyncio.sleep(0.1)
        if session.controller and session.controller.state.value == "STREAMING":
            break

    if not session.controller or session.controller.state.value != "STREAMING":
        logger.error("Session failed to reach STREAMING state! Current state: %s",
                     session.controller.state.value if session.controller else "None")
        await session.stop()
        sys.exit(1)

    logger.info("Session reached STREAMING successfully! Streaming video frames...")

    # Wait 2 seconds for video frames to stream
    await asyncio.sleep(2.0)

    snap = diagnostics.get_snapshot()
    logger.info("Diagnostics mid-stream: %.1f FPS | %.2f Mbps | Latency: %.1f ms | Frames: %d",
                snap.fps, snap.bitrate_kbps / 1000.0, snap.rtt_latency_ms, snap.frames_sent)

    # Trigger simulated touch events on Android emulator screen
    logger.info("Simulating touch taps on Android device via ADB...")
    subprocess.run([adb_path, "shell", "input", "tap", "500", "1200"], check=True)
    await asyncio.sleep(0.3)
    subprocess.run([adb_path, "shell", "input", "swipe", "300", "1000", "600", "1000", "200"], check=True)
    await asyncio.sleep(0.5)

    # Capture Android screen to verify visual rendering
    screenshot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screen_capture_live.png")
    logger.info("Capturing live device screenshot to %s...", screenshot_path)
    screencap_bytes = subprocess.run([adb_path, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, check=True).stdout
    with open(screenshot_path, "wb") as f:
        f.write(screencap_bytes)
    logger.info("Screenshot saved successfully (%d bytes)", len(screencap_bytes))

    # Keep streaming for another second
    await asyncio.sleep(1.0)

    final_snap = diagnostics.get_snapshot()
    logger.info("Final Diagnostics: %.1f FPS | %.2f Mbps | Latency: %.1f ms | Total Frames: %d",
                final_snap.fps, final_snap.bitrate_kbps / 1000.0, final_snap.rtt_latency_ms, final_snap.frames_sent)

    logger.info("Total touch events received: %d", input_events_count)
    logger.info("Stopping session cleanly...")
    await session.stop()

    assert final_snap.frames_sent > 30, f"Expected >30 frames sent, got {final_snap.frames_sent}"
    assert input_events_count > 0, f"Expected >0 touch events received, got {input_events_count}"
    logger.info("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_test())
