"""High-Performance Wi-Fi 6 Direct / Wireless Transport for OpenDisplay USB."""

import asyncio
import logging
import socket
import struct
import time
from typing import AsyncGenerator, Optional
from .base import ITransport, ConnectionState
from ..protocol.packet_codec import StreamDecoder, PacketCodec

logger = logging.getLogger(__name__)


class WifiTransport(ITransport):
    """Wireless TCP transport with jitter tracking and adaptive throughput estimation."""

    def __init__(self, host: str, port: int = 7320):
        super().__init__()
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._stream_decoder = StreamDecoder()

        # Network health metrics
        self.last_rtt_ms: float = 0.0
        self.jitter_ms: float = 0.0
        self._rtt_history = []

    async def connect(self) -> bool:
        """Establishes optimized Wi-Fi connection with TCP_NODELAY."""
        self.set_state(ConnectionState.CONNECTING)
        logger.info("Connecting Wi-Fi transport to %s:%d...", self.host, self.port)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5.0
            )

            # Optimize underlying socket for low latency
            sock = writer.get_extra_info("socket")
            if sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)
                except Exception:
                    pass

            self._reader = reader
            self._writer = writer
            self._stream_decoder = StreamDecoder()
            self.set_state(ConnectionState.CONNECTED)
            logger.info("Wi-Fi transport connected successfully to %s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.warning("Wi-Fi connection to %s:%d failed: %s", self.host, self.port, e)
            self.set_state(ConnectionState.DISCONNECTED)
            return False

    async def disconnect(self) -> None:
        """Closes Wi-Fi connection cleanly."""
        self.set_state(ConnectionState.DISCONNECTED)
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        logger.info("Wi-Fi transport disconnected from %s:%d", self.host, self.port)

    async def send(self, data: bytes) -> None:
        """Sends framed packet over Wi-Fi stream."""
        if self._writer is None or self._writer.is_closing():
            raise ConnectionError("Wi-Fi writer not available")

        self._writer.write(data)
        await self._writer.drain()

    async def receive_flow(self) -> AsyncGenerator[bytes, None]:
        """Asynchronously receives complete framed ODSP packets from Wi-Fi stream."""
        header_len = 11
        buf = bytearray()

        while self.is_connected() and self._reader is not None:
            try:
                chunk = await self._reader.read(65536)
                if not chunk:
                    logger.info("Wi-Fi connection closed by peer")
                    break

                buf.extend(chunk)

                while len(buf) >= header_len:
                    magic, ver, msg_type, length = struct.unpack("<4sBHI", buf[:header_len])
                    if magic != b"ODSP":
                        logger.error("Malformed magic in Wi-Fi stream: %s", magic)
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
                logger.debug("Wi-Fi read exception: %s", e)
                break

        await self.disconnect()

    def record_rtt(self, rtt_ms: float) -> None:
        """Updates moving average RTT and jitter."""
        if self._rtt_history:
            prev_rtt = self._rtt_history[-1]
            diff = abs(rtt_ms - prev_rtt)
            # RFC 3550 jitter formula: J = J + ( |D| - J ) / 16
            self.jitter_ms = self.jitter_ms + (diff - self.jitter_ms) / 16.0
        self._rtt_history.append(rtt_ms)
        if len(self._rtt_history) > 30:
            self._rtt_history.pop(0)
        self.last_rtt_ms = rtt_ms

    def get_suggested_bitrate_kbps(self, baseline_kbps: int = 18000) -> int:
        """Provides an adaptive bitrate recommendation based on Wi-Fi jitter and latency."""
        if self.jitter_ms > 15.0 or self.last_rtt_ms > 45.0:
            # High jitter: back off to maintain low latency
            return max(8000, int(baseline_kbps * 0.6))
        elif self.jitter_ms > 8.0 or self.last_rtt_ms > 25.0:
            return max(12000, int(baseline_kbps * 0.85))
        return baseline_kbps
