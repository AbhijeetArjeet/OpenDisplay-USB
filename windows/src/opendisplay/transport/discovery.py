"""ZeroConf and UDP Broadcast Network Discovery for OpenDisplay USB."""

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Set

logger = logging.getLogger(__name__)

DISCOVERY_PORT = 7321
DEFAULT_STREAM_PORT = 7320
DISCOVERY_PROBE = b"OPENDISPLAY_DISCOVER_v1"


@dataclass
class DiscoveredDevice:
    ip: str
    name: str
    manufacturer: str = "Android"
    port: int = DEFAULT_STREAM_PORT
    version: int = 1
    rtt_ms: float = 0.0

    @property
    def endpoint(self) -> str:
        return f"{self.ip}:{self.port}"


class NetworkDiscoveryManager:
    """Manages ZeroConf discovery of Android devices on the local Wi-Fi network."""

    def __init__(self):
        self._discovered_devices: dict[str, DiscoveredDevice] = {}
        self._polling_task: Optional[asyncio.Task] = None
        self._on_devices_updated: Optional[Callable[[List[DiscoveredDevice]], None]] = None
        self._running = False

    async def discover_devices(self, timeout: float = 1.0) -> List[DiscoveredDevice]:
        """Broadcasts a discovery query and listens for responses on the LAN."""
        devices: List[DiscoveredDevice] = []
        loop = asyncio.get_running_loop()

        def _do_broadcast() -> List[DiscoveredDevice]:
            found: List[DiscoveredDevice] = []
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)

            t0 = time.monotonic()
            try:
                # Send to universal broadcast and Windows Mobile Hotspot subnet (192.168.137.255)
                sock.sendto(DISCOVERY_PROBE, ("255.255.255.255", DISCOVERY_PORT))
                try:
                    sock.sendto(DISCOVERY_PROBE, ("192.168.137.255", DISCOVERY_PORT))
                except Exception:
                    pass
            except Exception as e:
                logger.debug("Broadcast send exception: %s", e)

            # Listen for responses until timeout
            seen_ips: Set[str] = set()
            while True:
                remaining = timeout - (time.monotonic() - t0)
                if remaining <= 0:
                    break
                sock.settimeout(max(0.05, remaining))
                try:
                    data, (src_ip, src_port) = sock.recvfrom(2048)
                    rtt = (time.monotonic() - t0) * 1000.0

                    if src_ip in seen_ips:
                        continue
                    seen_ips.add(src_ip)

                    payload = json.loads(data.decode("utf-8", errors="ignore"))
                    if payload.get("service") == "opendisplay":
                        dev = DiscoveredDevice(
                            ip=src_ip,
                            name=payload.get("device", "Android Device"),
                            manufacturer=payload.get("manufacturer", "Android"),
                            port=payload.get("port", DEFAULT_STREAM_PORT),
                            version=payload.get("version", 1),
                            rtt_ms=rtt
                        )
                        found.append(dev)
                        logger.info("Discovered OpenDisplay wireless device: %s (%s) RTT=%.1fms",
                                    dev.name, dev.endpoint, rtt)
                except (socket.timeout, TimeoutError):
                    break
                except Exception as e:
                    logger.debug("Discovery parse error from %s: %s", src_ip, e)
            sock.close()
            return found

        try:
            devices = await loop.run_in_executor(None, _do_broadcast)
        except Exception as e:
            logger.warning("Discovery sweep error: %s", e)

        # Update cache
        for d in devices:
            self._discovered_devices[d.ip] = d

        return devices

    def start_polling(self, callback: Callable[[List[DiscoveredDevice]], None], interval: float = 3.0) -> None:
        """Starts background periodic LAN discovery."""
        self._on_devices_updated = callback
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_loop(interval))

    def stop_polling(self) -> None:
        """Stops background periodic LAN discovery."""
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            self._polling_task = None

    async def _poll_loop(self, interval: float) -> None:
        while self._running:
            try:
                devices = await self.discover_devices(timeout=0.8)
                if self._on_devices_updated:
                    self._on_devices_updated(devices)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Polling iteration error: %s", e)
            await asyncio.sleep(interval)
