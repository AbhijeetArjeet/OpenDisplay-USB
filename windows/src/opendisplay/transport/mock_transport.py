"""In-memory loopback transport for standalone testing and verification."""

import asyncio
from typing import AsyncIterator, Optional
from .base import ITransport, ConnectionState


class MockTransport(ITransport):
    """Loopback transport using asyncio Queues.
    
    Allows test code to inject incoming packets (simulating Android receiver)
    and inspect outgoing packets (sent by Windows host).
    """

    def __init__(self):
        super().__init__()
        self.incoming_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.sent_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._connected = False

    async def connect(self) -> bool:
        self.set_state(ConnectionState.CONNECTING)
        self._connected = True
        self.set_state(ConnectionState.CONNECTED)
        return True

    async def disconnect(self) -> None:
        self._connected = False
        self.set_state(ConnectionState.DISCONNECTED)
        await self.incoming_queue.put(None)  # Signal EOF to receive_flow

    async def send(self, packet: bytes) -> bool:
        if not self._connected:
            return False
        await self.sent_queue.put(packet)
        return True

    async def receive_flow(self) -> AsyncIterator[bytes]:
        while self._connected:
            packet = await self.incoming_queue.get()
            if packet is None:
                break
            yield packet

    # ── Test / Mock Helpers ──────────────────────────────────────────────────

    async def inject_incoming(self, packet: bytes) -> None:
        """Simulates Android sending a packet to Windows."""
        await self.incoming_queue.put(packet)

    async def consume_sent(self, timeout: float = 2.0) -> bytes:
        """Reads the next packet sent by Windows."""
        return await asyncio.wait_for(self.sent_queue.get(), timeout=timeout)

    def simulate_disconnect(self) -> None:
        """Simulates an abrupt USB cable unplug."""
        self._connected = False
        self.set_state(ConnectionState.DISCONNECTED)
        try:
            self.incoming_queue.put_nowait(None)
        except Exception:
            pass
