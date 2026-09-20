import pytest
from opendisplay.protocol import (
    MessageType,
    PacketCodec,
    JsonCodec,
    ClipboardEventMessage
)
from opendisplay.clipboard import WindowsClipboard


def test_clipboard_event_codec():
    msg = ClipboardEventMessage(content="Hello World!", mimeType="text/plain")
    encoded_json = JsonCodec.encode(msg)
    decoded = JsonCodec.decode_clipboard_event(encoded_json)
    assert decoded.type == "CLIPBOARD_EVENT"
    assert decoded.content == "Hello World!"
    assert decoded.mimeType == "text/plain"

    packet = PacketCodec.encode(MessageType.CLIPBOARD_EVENT, encoded_json)
    decoded_pkt = PacketCodec.decode(packet)
    assert decoded_pkt.msg_type == MessageType.CLIPBOARD_EVENT
    assert JsonCodec.decode_clipboard_event(decoded_pkt.payload).content == "Hello World!"


def test_windows_clipboard_read_write():
    cb = WindowsClipboard()
    # If clipboard is accessible in this session
    orig = cb.get_text()
    test_str = "OpenDisplay-Phase2-ClipTest"
    success = cb.set_text(test_str)
    if success:
        read_back = cb.get_text()
        assert read_back == test_str
        # Restore if possible
        if orig is not None:
            cb.set_text(orig)
