"""Tests for Windows Native AOA Transport and Fallback."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from opendisplay.transport.aoa_transport import AoaTransport
from opendisplay.transport.base import ConnectionState
from opendisplay.protocol import PacketCodec, MessageType


def test_aoa_transport_init():
    async def _run():
        transport = AoaTransport(fallback_to_adb=True)
        assert transport.state == ConnectionState.DISCONNECTED
        assert transport._usb_dev is None

    asyncio.run(_run())


def test_aoa_transport_fallback_to_adb():
    async def _run():
        transport = AoaTransport(fallback_to_adb=True)

        with patch.object(transport, "_try_aoa_connect", return_value=False):
            mock_adb = MagicMock()
            mock_adb.connect = AsyncMock(return_value=True)
            mock_adb.send = AsyncMock()
            mock_adb.disconnect = AsyncMock()

            with patch("opendisplay.transport.aoa_transport.AdbTransport", return_value=mock_adb):
                ok = await transport.connect()
                assert ok is True
                assert transport.state == ConnectionState.CONNECTED
                assert transport._is_using_adb is True

                # Test send delegation
                test_pkt = b"hello"
                await transport.send(test_pkt)
                mock_adb.send.assert_awaited_once_with(test_pkt)

                # Test disconnect delegation
                await transport.disconnect()
                assert transport.state == ConnectionState.DISCONNECTED

    asyncio.run(_run())


def test_aoa_transport_framing_parser():
    """Verify that packet framing handles chunked USB transfers correctly."""
    async def _run():
        transport = AoaTransport(fallback_to_adb=False)

        pkt1 = PacketCodec.encode(MessageType.PING, b'{"t":1}')
        pkt2 = PacketCodec.encode(MessageType.PONG, b'{"t":2}')
        combined = pkt1 + pkt2

        # Verify framing split
        mock_ep_in = MagicMock()
        split_pt = 8
        chunks = [combined[:split_pt], combined[split_pt:], b""]
        chunk_iter = iter(chunks)

        mock_ep_in.read.side_effect = lambda size, timeout: next(chunk_iter, b"")
        transport._ep_in = mock_ep_in

        packets_received = []

        async def reader():
            async for pkt in transport.receive_flow():
                packets_received.append(pkt)
                if len(packets_received) == 2:
                    await transport.disconnect()
                    break

        try:
            await asyncio.wait_for(reader(), timeout=2.0)
        except asyncio.TimeoutError:
            pass

        assert len(packets_received) == 2
        assert packets_received[0] == pkt1
        assert packets_received[1] == pkt2

    asyncio.run(_run())
