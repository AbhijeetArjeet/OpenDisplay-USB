from enum import IntEnum
from typing import Optional

class MessageType(IntEnum):
    """All 19 message types defined in OpenDisplay Protocol v1.
    
    IDs are uint16 values transmitted little-endian in the header at offset 5.
    Unknown IDs must be discarded by receivers without disconnecting.
    """
    HELLO = 0x0001
    HELLO_ACK = 0x0002
    CAPABILITIES = 0x0003
    CAPABILITIES_ACK = 0x0004
    DISPLAY_CONFIG = 0x0005
    DISPLAY_CONFIG_ACK = 0x0006
    VIDEO_CONFIG = 0x0007
    VIDEO_CONFIG_ACK = 0x0008
    VIDEO_FRAME = 0x0009
    AUDIO_CONFIG = 0x000A
    AUDIO_FRAME = 0x000B
    INPUT_EVENT = 0x000C
    CLIPBOARD_EVENT = 0x000D
    FILE_TRANSFER = 0x000E
    PING = 0x000F
    PONG = 0x0010
    STREAM_RESET = 0x0011
    ERROR = 0x0012
    DISCONNECT = 0x0013

    @classmethod
    def from_id(cls, msg_id: int) -> Optional["MessageType"]:
        try:
            return cls(msg_id)
        except ValueError:
            return None
