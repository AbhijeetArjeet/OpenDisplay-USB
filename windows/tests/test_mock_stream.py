"""End-to-end integration test verifying Windows sender and Android test receiver interoperability."""

import os
import asyncio
import pytest
from opendisplay.protocol import (
    MessageType,
    PacketCodec,
    JsonCodec,
    HelloMessage,
    CapabilitiesMessage,
    DisplayConfigAckMessage,
    VideoConfigAckMessage,
    InputEventMessage,
    PointerInfo,
    PongMessage,
    VIDEO_FRAME_FLAG_KEYFRAME
)
from opendisplay.transport.mock_transport import MockTransport
from opendisplay.diagnostics.collector import DiagnosticsCollector
from opendisplay.input.injector import InputInjector
from opendisplay.session.controller import ProtocolController, SessionState

TEST_VECTORS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "protocol", "test-vectors"))


def test_end_to_end_mock_stream():
    """Simulates a full session between the Windows sender and an Android receiver."""

    async def _run():
        transport = MockTransport()
        diagnostics = DiagnosticsCollector()
        input_injector = InputInjector()

        controller = ProtocolController(
            send_packet_func=transport.send,
            diagnostics=diagnostics,
            input_injector=input_injector,
            use_synthetic_video=True,
            enable_audio=False,
            enable_clipboard=False
        )

        await transport.connect()
        await controller.start_handshake()
        assert controller.state == SessionState.WAITING_HELLO

        # ── Stage 1: Android sends HELLO ──────────────────────────────────────
        with open(os.path.join(TEST_VECTORS_DIR, "hello.json"), "rb") as f:
            hello_payload = f.read()
        await controller.handle_packet(PacketCodec.encode(MessageType.HELLO, hello_payload))

        # Windows must reply with HELLO_ACK
        hello_ack_pkt = PacketCodec.decode(await transport.consume_sent(timeout=2.0))
        assert hello_ack_pkt.msg_type == MessageType.HELLO_ACK
        ack_dict = JsonCodec.decode(hello_ack_pkt.payload)
        assert ack_dict["accepted"] is True
        assert controller.state == SessionState.WAITING_CAPABILITIES

        # ── Stage 2: Android sends CAPABILITIES ───────────────────────────────
        with open(os.path.join(TEST_VECTORS_DIR, "capabilities.json"), "rb") as f:
            caps_payload = f.read()
        await controller.handle_packet(PacketCodec.encode(MessageType.CAPABILITIES, caps_payload))

        # Windows must reply with CAPABILITIES_ACK followed by DISPLAY_CONFIG
        caps_ack_pkt = PacketCodec.decode(await transport.consume_sent(timeout=2.0))
        assert caps_ack_pkt.msg_type == MessageType.CAPABILITIES_ACK
        assert JsonCodec.decode(caps_ack_pkt.payload)["accepted"] is True

        disp_cfg_pkt = PacketCodec.decode(await transport.consume_sent(timeout=2.0))
        assert disp_cfg_pkt.msg_type == MessageType.DISPLAY_CONFIG
        assert controller.state == SessionState.WAITING_DISPLAY_CONFIG_ACK

        # ── Stage 3: Android sends DISPLAY_CONFIG_ACK ─────────────────────────
        disp_ack_payload = JsonCodec.encode(DisplayConfigAckMessage(accepted=True))
        await controller.handle_packet(PacketCodec.encode(MessageType.DISPLAY_CONFIG_ACK, disp_ack_payload))

        # Windows primes H.264 encoder and sends VIDEO_CONFIG
        vid_cfg_pkt = PacketCodec.decode(await transport.consume_sent(timeout=4.0))
        assert vid_cfg_pkt.msg_type == MessageType.VIDEO_CONFIG
        vid_dict = JsonCodec.decode(vid_cfg_pkt.payload)
        assert vid_dict["codec"] == "H264"
        assert "csd0Base64" in vid_dict
        assert "csd1Base64" in vid_dict
        assert controller.state == SessionState.WAITING_VIDEO_CONFIG_ACK

        # ── Stage 4: Android sends VIDEO_CONFIG_ACK ───────────────────────────
        vid_ack_payload = JsonCodec.encode(VideoConfigAckMessage(accepted=True))
        await controller.handle_packet(PacketCodec.encode(MessageType.VIDEO_CONFIG_ACK, vid_ack_payload))

        # Handshake complete! Controller enters STREAMING state
        assert controller.state == SessionState.STREAMING

        # ── Stage 5: Verify Video Streaming ───────────────────────────────────
        # The Windows controller streams VIDEO_FRAME binary packets
        video_pkt = PacketCodec.decode(await transport.consume_sent(timeout=3.0))
        assert video_pkt.msg_type == MessageType.VIDEO_FRAME

        # Validate VIDEO_FRAME binary payload format
        ts_ns, is_key, nal_data = PacketCodec.decode_video_frame_payload(video_pkt.payload)
        assert ts_ns >= 0
        # Rule from ANDROID_INTEGRATION.md: The first frame after VIDEO_CONFIG MUST be a keyframe
        assert is_key is True
        assert len(nal_data) > 0

        # ── Stage 6: Android sends INPUT_EVENT (touch) ────────────────────────
        touch_event = InputEventMessage(
            eventType="TOUCH",
            timestampNs=1000000000,
            pointers=[PointerInfo(id=0, action="DOWN", x=0.5, y=0.5, pressure=0.8)]
        )
        await controller.handle_packet(PacketCodec.encode(MessageType.INPUT_EVENT, JsonCodec.encode(touch_event)))

        # ── Stage 7: Android sends PING, Windows replies PONG ─────────────────
        await controller.handle_packet(PacketCodec.encode(MessageType.PING, b'{"type":"PING","timestampNs":5000}'))
        pong_pkt = PacketCodec.decode(await transport.consume_sent(timeout=2.0))
        assert pong_pkt.msg_type == MessageType.PONG
        pong_dict = JsonCodec.decode(pong_pkt.payload)
        assert pong_dict["timestampNs"] == 5000

        # ── Stage 8: Clean teardown ───────────────────────────────────────────
        await controller.stop()
        await transport.disconnect()
        assert controller.state == SessionState.DISCONNECTED

    asyncio.run(_run())
