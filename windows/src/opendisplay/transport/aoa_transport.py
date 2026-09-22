"""Native Android Open Accessory (AOA 2.0) USB Transport for Windows."""

import asyncio
import logging
import struct
import time
from typing import AsyncGenerator, Optional
from .base import ITransport, ConnectionState
from .adb_transport import AdbTransport

logger = logging.getLogger(__name__)

# Android Open Accessory (AOA) Protocol Constants
AOA_GET_PROTOCOL = 51
AOA_SEND_STRING = 52
AOA_START_ACCESSORY = 53

# Google USB Vendor ID & AOA Product IDs
GOOGLE_VID = 0x18D1
AOA_PID_ACCESSORY = 0x2D00
AOA_PID_ACCESSORY_ADB = 0x2D01

ACCESSORY_STRINGS = [
    "OpenDisplay",                               # 0: Manufacturer
    "OpenDisplay USB",                           # 1: Model
    "OpenDisplay USB Secondary Monitor",         # 2: Description
    "1.0",                                       # 3: Version
    "https://github.com/AbhijeetArjeet/OpenDisplay-USB", # 4: URI
    "ODSP-001",                                  # 5: Serial
]


class AoaTransport(ITransport):
    """Native USB transport using Android Open Accessory protocol with transparent ADB fallback."""

    def __init__(self, fallback_to_adb: bool = True):
        super().__init__()
        self.fallback_to_adb = fallback_to_adb
        self._usb_dev = None
        self._ep_in = None
        self._ep_out = None
        self._adb_fallback: Optional[AdbTransport] = None
        self._is_using_adb = False
        self._stop_event = asyncio.Event()

    async def connect(self) -> bool:
        """Connects directly to Android via AOA USB bulk endpoints, or falls back to ADB."""
        self.set_state(ConnectionState.CONNECTING)

        try:
            connected = await asyncio.to_thread(self._try_aoa_connect)
            if connected:
                logger.info("Connected directly to device via native USB AOA transport!")
                self.set_state(ConnectionState.CONNECTED)
                return True
        except Exception as e:
            logger.info("AOA connection attempt: %s", e)

        if self.fallback_to_adb:
            logger.info("AOA mode not active. Falling back to high-speed ADB TCP bridge on port 7320...")
            self._adb_fallback = AdbTransport(port=7320)
            self._is_using_adb = True
            ok = await self._adb_fallback.connect()
            if ok:
                self.set_state(ConnectionState.CONNECTED)
                return True
            else:
                self.set_state(ConnectionState.DISCONNECTED)
                return False

        self.set_state(ConnectionState.DISCONNECTED)
        return False

    def _try_aoa_connect(self) -> bool:
        """Synchronous AOA probe and initialization."""
        try:
            import usb.core
            import usb.util
            import libusb_package
        except ImportError:
            logger.warning("pyusb or libusb_package not available for native AOA transport")
            return False

        # 1. Check if device is already in AOA mode
        dev = usb.core.find(idVendor=GOOGLE_VID, idProduct=AOA_PID_ACCESSORY)
        if not dev:
            dev = usb.core.find(idVendor=GOOGLE_VID, idProduct=AOA_PID_ACCESSORY_ADB)

        # 2. If not in accessory mode, search for Android device and send AOA handshake
        if not dev:
            all_devs = list(usb.core.find(find_all=True))
            candidate = None
            for d in all_devs:
                # Common Android VIDs: Google (0x18d1), OnePlus/Oppo (0x22d9), Samsung (0x04e8), Xiaomi (0x2717)
                if d.idVendor in (0x18D1, 0x22D9, 0x04E8, 0x2717, 0x0BB4, 0x12D1):
                    candidate = d
                    break

            if candidate:
                logger.info("Found potential Android device VID=0x%04X PID=0x%04X. Querying AOA protocol...",
                            candidate.idVendor, candidate.idProduct)
                try:
                    # Request protocol version
                    proto_ver = candidate.ctrl_transfer(
                        0xC0, AOA_GET_PROTOCOL, 0, 0, 2, timeout=1000
                    )
                    ver = proto_ver[0] + (proto_ver[1] << 8)
                    logger.info("Device supports AOA protocol version: %d", ver)
                    if ver >= 1:
                        # Send identifying strings
                        for idx, s in enumerate(ACCESSORY_STRINGS):
                            candidate.ctrl_transfer(
                                0x40, AOA_SEND_STRING, 0, idx, s.encode("utf-8") + b"\x00", timeout=1000
                            )
                        # Switch to accessory mode
                        candidate.ctrl_transfer(0x40, AOA_START_ACCESSORY, 0, 0, None, timeout=1000)
                        logger.info("AOA START_ACCESSORY command sent. Waiting for re-enumeration...")
                        time.sleep(1.5)

                        dev = usb.core.find(idVendor=GOOGLE_VID, idProduct=AOA_PID_ACCESSORY) or \
                              usb.core.find(idVendor=GOOGLE_VID, idProduct=AOA_PID_ACCESSORY_ADB)
                except Exception as e:
                    logger.debug("AOA handshake probe exception: %s", e)

        if not dev:
            return False

        try:
            # Set active configuration and claim interface
            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0, 0)]

            # Locate bulk endpoints
            self._ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            self._ep_in = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if self._ep_out and self._ep_in:
                self._usb_dev = dev
                self._stop_event.clear()
                return True
        except Exception as e:
            logger.warning("Failed to claim USB AOA endpoints: %s", e)

        return False

    async def disconnect(self) -> None:
        """Closes AOA USB transport or fallback transport."""
        self._stop_event.set()
        if self._is_using_adb and self._adb_fallback:
            await self._adb_fallback.disconnect()
            self._adb_fallback = None

        if self._usb_dev:
            try:
                import usb.util
                usb.util.dispose_resources(self._usb_dev)
            except Exception:
                pass
            self._usb_dev = None
            self._ep_in = None
            self._ep_out = None

        self.set_state(ConnectionState.DISCONNECTED)

    async def send(self, data: bytes) -> None:
        """Sends data over AOA bulk OUT or fallback ADB."""
        if self._is_using_adb and self._adb_fallback:
            await self._adb_fallback.send(data)
            return

        if not self._ep_out:
            raise ConnectionError("AOA OUT endpoint not available")

        await asyncio.to_thread(self._ep_out.write, data, 1000)

    async def receive_flow(self) -> AsyncGenerator[bytes, None]:
        """Asynchronously streams complete framed packets from USB AOA IN or ADB."""
        if self._is_using_adb and self._adb_fallback:
            async for packet in self._adb_fallback.receive_flow():
                yield packet
            return

        header_len = 11
        buf = bytearray()

        while not self._stop_event.is_set() and self._ep_in:
            try:
                # Read chunk from bulk IN endpoint
                data = await asyncio.to_thread(self._ep_in.read, 64 * 1024, 1000)
                if data:
                    buf.extend(data)

                # Process complete packets
                while len(buf) >= header_len:
                    magic, ver, msg_type, length = struct.unpack("<4sBHI", buf[:header_len])
                    if magic != b"ODSP":
                        logger.error("Malformed magic in USB AOA stream: %s", magic)
                        await self.disconnect()
                        return

                    total_len = header_len + length
                    if len(buf) < total_len:
                        break

                    packet = bytes(buf[:total_len])
                    del buf[:total_len]
                    yield packet

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Timeout is normal in USB polling
                if "timeout" not in str(e).lower():
                    logger.debug("AOA read exception: %s", e)
                    break
