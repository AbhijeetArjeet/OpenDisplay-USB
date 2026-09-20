import os
import json
import pytest
from opendisplay.protocol import (
    MAGIC,
    PROTOCOL_VERSION,
    HEADER_SIZE,
    MessageType,
    PacketCodec,
    PacketCodecError,
    StreamDecoder,
    JsonCodec,
    HelloMessage,
    HelloAckMessage,
    CapabilitiesMessage,
    DisplayConfigMessage,
    VideoConfigMessage,
    PingMessage,
    PongMessage,
    StreamResetMessage,
    ErrorMessage,
    DisconnectMessage
)

TEST_VECTORS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "protocol", "test-vectors"))

def test_load_hello_vector():
    path = os.path.join(TEST_VECTORS_DIR, "hello.json")
    with open(path, "rb") as f:
        data = f.read()
    msg = JsonCodec.decode_hello(data)
    assert msg.type == "HELLO"
    assert msg.protocol == 1
    assert msg.platform == "android"
    assert msg.model != ""

def test_load_hello_ack_vector():
    path = os.path.join(TEST_VECTORS_DIR, "hello_ack.json")
    with open(path, "rb") as f:
        data = f.read()
    d = JsonCodec.decode(data)
    assert d["type"] == "HELLO_ACK"
    assert d["protocol"] == 1
    assert d["accepted"] is True

def test_load_capabilities_vector():
    path = os.path.join(TEST_VECTORS_DIR, "capabilities.json")
    with open(path, "rb") as f:
        data = f.read()
    msg = JsonCodec.decode_capabilities(data)
    assert msg.type == "CAPABILITIES"
    assert msg.display.widthPx > 0
    assert len(msg.video) > 0
    # Mandatory H264 supported check
    h264_cap = next((v for v in msg.video if v.codec == "H264"), None)
    assert h264_cap is not None
    assert h264_cap.supported is True

def test_load_video_config_vector():
    path = os.path.join(TEST_VECTORS_DIR, "video_config.json")
    with open(path, "rb") as f:
        data = f.read()
    d = JsonCodec.decode(data)
    assert d["type"] == "VIDEO_CONFIG"
    assert d["codec"] == "H264"
    assert d["widthPx"] == 1920
    assert d["heightPx"] == 1080
    assert "csd0Base64" in d
    assert "csd1Base64" in d

def test_load_display_config_vector():
    path = os.path.join(TEST_VECTORS_DIR, "display_config.json")
    with open(path, "rb") as f:
        data = f.read()
    d = JsonCodec.decode(data)
    assert d["type"] == "DISPLAY_CONFIG"
    assert d["widthPx"] > 0
    assert d["scaling"] in ["FIT", "CROP", "STRETCH"]

def test_load_ping_pong_vectors():
    ping_path = os.path.join(TEST_VECTORS_DIR, "ping.json")
    with open(ping_path, "rb") as f:
        ping_d = JsonCodec.decode(f.read())
    assert ping_d["type"] == "PING"
    assert "timestampNs" in ping_d

    pong_path = os.path.join(TEST_VECTORS_DIR, "pong.json")
    with open(pong_path, "rb") as f:
        pong_msg = JsonCodec.decode_pong(f.read())
    assert pong_msg.type == "PONG"
    assert pong_msg.timestampNs == ping_d["timestampNs"]

def test_load_malformed_vectors():
    bad_magic_path = os.path.join(TEST_VECTORS_DIR, "malformed", "bad_magic.txt")
    with open(bad_magic_path, "rb") as f:
        content = f.read()
        # Header with 'BAD!' instead of 'ODSP'
        # Construct packet with bad magic
        bad_frame = b"BAD!" + b"\x01" + b"\x01\x00" + b"\x00\x00\x00\x00"
        with pytest.raises(PacketCodecError, match="Invalid magic"):
            PacketCodec.decode(bad_frame)

    # Overflow length vector
    overflow_frame = MAGIC + b"\x01" + b"\x01\x00" + (17 * 1024 * 1024).to_bytes(4, "little")
    with pytest.raises(PacketCodecError, match="exceeds maximum"):
        PacketCodec.decode(overflow_frame)

    # Unknown type vector
    unknown_type_frame = MAGIC + b"\x01" + (0xFFFF).to_bytes(2, "little") + (2).to_bytes(4, "little") + b"{}"
    with pytest.raises(PacketCodecError, match="Unknown message type ID"):
        PacketCodec.decode(unknown_type_frame)

    # Stream decoder must silently ignore unknown type without disconnecting
    decoder = StreamDecoder()
    packets = decoder.feed(unknown_type_frame)
    assert len(packets) == 0  # Silently discarded per forward-compatibility rule
