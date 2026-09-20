"""Constants for the OpenDisplay Protocol (ODSP), version 1."""

# Magic bytes at start of every frame: ASCII "ODSP" = 0x4F 0x44 0x53 0x50
MAGIC = b"ODSP"
MAGIC_INT = 0x4F445350

# Protocol version
PROTOCOL_VERSION = 1

# Fixed 11-byte frame header
HEADER_SIZE = 11

# Maximum allowable payload: 16 MB (0x01000000)
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024

# Default ADB-forward TCP port
DEFAULT_PORT = 7320

# Video frame payload offsets
VIDEO_FRAME_TIMESTAMP_OFFSET = 0
VIDEO_FRAME_FLAGS_OFFSET = 8
VIDEO_FRAME_DATA_OFFSET = 12
VIDEO_FRAME_FLAG_KEYFRAME = 0x00000001

# Audio frame payload offsets
AUDIO_FRAME_TIMESTAMP_OFFSET = 0
AUDIO_FRAME_SEQUENCE_OFFSET = 8
AUDIO_FRAME_DATA_OFFSET = 12
