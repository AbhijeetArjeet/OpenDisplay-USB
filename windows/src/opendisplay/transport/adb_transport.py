"""ADB transport manager that handles adb forward and device discovery."""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
from .tcp_transport import TcpTransport
from ..protocol.constants import DEFAULT_PORT

logger = logging.getLogger(__name__)


class AdbTransport(TcpTransport):
    """Transport that sets up ADB port forwarding before establishing TCP connection."""

    def __init__(self, port: int = DEFAULT_PORT, serial: Optional[str] = None):
        super().__init__(host="127.0.0.1", port=port)
        self.serial = serial
        self._forward_established = False

    @staticmethod
    def _get_adb_path() -> str:
        found = shutil.which("adb")
        if found:
            return found
        default_sdk = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
        if default_sdk.exists():
            return str(default_sdk)
        return "adb"

    @classmethod
    def list_devices(cls) -> List[str]:
        """Queries connected Android devices via 'adb devices'."""
        try:
            adb_bin = cls._get_adb_path()
            result = subprocess.run(
                [adb_bin, "devices"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5.0
            )
            devices = []
            for line in result.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])
            return devices
        except Exception as e:
            logger.warning("Could not list adb devices: %s", e)
            return []

    def _setup_forward(self) -> bool:
        cmd = [self._get_adb_path()]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(["forward", f"tcp:{self.port}", f"tcp:{self.port}"])

        try:
            logger.info("Executing adb forward: %s", " ".join(cmd))
            subprocess.run(cmd, check=True, capture_output=True, timeout=5.0)
            self._forward_established = True
            return True
        except Exception as e:
            logger.error("Failed to execute adb forward: %s", e)
            return False

    def _remove_forward(self) -> None:
        if not self._forward_established:
            return
        cmd = [self._get_adb_path()]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(["forward", "--remove", f"tcp:{self.port}"])
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=5.0)
        except Exception:
            pass
        self._forward_established = False

    async def connect(self) -> bool:
        """Configures ADB forward and connects to local forwarded port."""
        if not self._setup_forward():
            # If adb is unavailable or device not ready, try direct connect anyway
            logger.warning("Proceeding with direct TCP connection to 127.0.0.1:%d", self.port)

        return await super().connect()

    async def disconnect(self) -> None:
        await super().disconnect()
        self._remove_forward()
