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
    VIDEO_FRAME_FLAG_KEYFRAME
)

def test_encode_decode_round_trip():
    hello = HelloMessage(manufacturer="Test", model="Device1")
    payload = JsonCodec.encode(hello)
    framed = PacketCodec.encode(MessageType.HELLO, payload)

    assert len(framed) == HEADER_SIZE + len(payload)
    assert framed[:4] == MAGIC
    assert framed[4] == PROTOCOL_VERSION

    packet = PacketCodec.decode(framed)
    assert packet.msg_type == MessageType.HELLO
    assert packet.version == PROTOCOL_VERSION
    assert packet.payload == payload

def test_all_19_message_types_encode_decode():
    for mtype in MessageType:
        sample_payload = f'{{"type":"{mtype.name}"}}'.encode("utf-8")
        framed = PacketCodec.encode(mtype, sample_payload)
        packet = PacketCodec.decode(framed)
        assert packet.msg_type == mtype
        assert packet.payload == sample_payload

def test_video_frame_binary_payload():
    ts = 1234567890123
    nal_data = b"\x00\x00\x00\x01\x65\x88\x84\x00"
    payload = PacketCodec.encode_video_frame_payload(ts, is_keyframe=True, nal_data=nal_data)
    
    dec_ts, is_key, dec_nal = PacketCodec.decode_video_frame_payload(payload)
    assert dec_ts == ts
    assert is_key is True
    assert dec_nal == nal_data

def test_audio_frame_binary_payload():
    ts = 9876543210
    seq = 42
    audio_data = b"\xFA\xFB\xFC\xFD\xFE\xFF"
    payload = PacketCodec.encode_audio_frame_payload(ts, seq, audio_data)

    dec_ts, dec_seq, dec_audio = PacketCodec.decode_audio_frame_payload(payload)
    assert dec_ts == ts
    assert dec_seq == seq
    assert dec_audio == audio_data

def test_stream_decoder_fragmented_delivery():
    p1 = PacketCodec.encode(MessageType.PING, b'{"type":"PING"}')
    p2 = PacketCodec.encode(MessageType.DISCONNECT, b'{"type":"DISCONNECT"}')
    full_stream = p1 + p2

    decoder = StreamDecoder()
    # Feed byte by byte
    collected = []
    for byte in full_stream:
        collected.extend(decoder.feed(bytes([byte])))

    assert len(collected) == 2
    assert collected[0].msg_type == MessageType.PING
    assert collected[1].msg_type == MessageType.DISCONNECT
