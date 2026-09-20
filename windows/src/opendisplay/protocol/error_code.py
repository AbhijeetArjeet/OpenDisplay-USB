from enum import IntEnum

class ErrorCode(IntEnum):
    """Standard error codes in OpenDisplay Protocol v1."""
    ERR_NONE = 0x0000
    ERR_PROTOCOL_VERSION = 0x0001
    ERR_UNSUPPORTED_CODEC = 0x0002
    ERR_UNSUPPORTED_RESOLUTION = 0x0003
    ERR_UNSUPPORTED_FRAMERATE = 0x0004
    ERR_DECODER_FAILED = 0x0005
    ERR_INVALID_PACKET = 0x0006
    ERR_STREAM_RESET = 0x0007
    ERR_AUTH_FAILED = 0x0008
    ERR_INTERNAL = 0x00FF

    @classmethod
    def from_code(cls, code: int) -> "ErrorCode":
        try:
            return cls(code)
        except ValueError:
            return cls.ERR_INTERNAL
