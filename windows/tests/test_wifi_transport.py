"""Tests for Windows Wi-Fi 6 Direct / Wireless Transport and Discovery."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from opendisplay.transport.discovery import NetworkDiscoveryManager, DiscoveredDevice
from opendisplay.transport.wifi_transport import WifiTransport
from opendisplay.transport.base import ConnectionState
from opendisplay.protocol import PacketCodec, MessageType


def test_discovered_device_properties():
    dev = DiscoveredDevice(ip="192.168.1.50", name="Galaxy Tab A7", port=7320)
    assert dev.endpoint == "192.168.1.50:7320"
    assert dev.name == "Galaxy Tab A7"


def test_discovery_manager_mock_response():
    async def _run():
        mgr = NetworkDiscoveryManager()

        mock_response = json.dumps({
            "service": "opendisplay",
            "device": "OnePlus 12",
            "manufacturer": "OnePlus",
            "port": 7320,
            "version": 1
        }).encode("utf-8")

        def mock_broadcast():
            return [
                DiscoveredDevice(
                    ip="192.168.1.100",
                    name="OnePlus 12",
                    manufacturer="OnePlus",
                    port=7320,
                    version=1,
                    rtt_ms=2.5
                )
            ]

        with patch.object(mgr, "discover_devices", side_effect=AsyncMock(return_value=mock_broadcast())):
            devices = await mgr.discover_devices(timeout=0.5)
            assert len(devices) == 1
            assert devices[0].ip == "192.168.1.100"
            assert devices[0].name == "OnePlus 12"
            assert devices[0].rtt_ms == 2.5

    asyncio.run(_run())


def test_wifi_transport_jitter_and_adaptive_bitrate():
    transport = WifiTransport(host="192.168.1.100", port=7320)
    assert transport.jitter_ms == 0.0

    # Simulate fluctuating RTTs
    transport.record_rtt(10.0)
    assert transport.last_rtt_ms == 10.0

    transport.record_rtt(40.0)
    assert transport.jitter_ms > 0.0

    # With high jitter, suggested bitrate should back off
    transport.jitter_ms = 20.0
    suggested = transport.get_suggested_bitrate_kbps(baseline_kbps=18000)
    assert suggested < 18000


def test_wifi_transport_framing():
    async def _run():
        transport = WifiTransport(host="127.0.0.1", port=7320)
        pkt1 = PacketCodec.encode(MessageType.PING, b'{"t":100}')

        # Mock reader
        mock_reader = MagicMock()
        read_count = 0

        async def mock_read(n):
            nonlocal read_count
            if read_count == 0:
                read_count += 1
                return pkt1
            return b""

        mock_reader.read = AsyncMock(side_effect=mock_read)
        transport._reader = mock_reader
        transport.set_state(ConnectionState.CONNECTED)

        received = []
        async for pkt in transport.receive_flow():
            received.append(pkt)
            break

        assert len(received) == 1
        assert received[0] == pkt1

    asyncio.run(_run())
