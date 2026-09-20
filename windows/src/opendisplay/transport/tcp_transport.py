"""Asynchronous TCP socket transport implementation."""

import asyncio
import logging
from typing import AsyncIterator, Optional
from .base import ITransport, ConnectionState
from ..protocol.packet_codec import StreamDecoder, PacketCodec

logger = logging.getLogger(__name__)


class TcpTransport(ITransport):
    """Direct TCP transport connected to Android OpenDisplay Server on host:port."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7320):
        super().__init__()
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._stream_decoder = StreamDecoder()

    async def connect(self) -> bool:
        self.set_state(ConnectionState.CONNECTING)
        try:
            self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
            self._stream_decoder = StreamDecoder()
            self.set_state(ConnectionState.CONNECTED)
            logger.info("Connected TCP transport to %s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to connect TCP to %s:%d: %s", self.host, self.port, e)
            self.set_state(ConnectionState.ERROR)
            return False

    async def disconnect(self) -> None:
        self.set_state(ConnectionState.DISCONNECTED)
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        logger.info("Disconnected TCP transport")

    async def send(self, packet: bytes) -> bool:
        if self._writer is None or self._writer.is_closing():
            return False
        try:
            self._writer.write(packet)
            await self._writer.drain()
            return True
        except Exception as e:
            logger.error("TCP send error: %s", e)
            self.set_state(ConnectionState.ERROR)
            return False

    async def receive_flow(self) -> AsyncIterator[bytes]:
        """Yields complete framed packets parsed from the TCP stream."""
        while self.is_connected() and self._reader is not None:
            try:
                chunk = await self._reader.read(65536)
                if not chunk:
                    # Connection closed by remote peer
                    logger.warning("TCP connection closed by peer")
                    break
                packets = self._stream_decoder.feed(chunk)
                for pkt in packets:
                    # Re-encode to framed packet for downstream consumer
                    yield PacketCodec.encode(pkt.msg_type, pkt.payload)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("TCP read error: %s", e)
                break

        await self.disconnect()
