"""Binary framing encoder and decoder for OpenDisplay Protocol v1."""

import struct
from dataclasses import dataclass
from typing import Tuple, Optional, List
from .constants import (
    MAGIC,
    PROTOCOL_VERSION,
    HEADER_SIZE,
    MAX_PAYLOAD_BYTES,
    VIDEO_FRAME_FLAG_KEYFRAME
)
from .message_type import MessageType


class PacketCodecError(Exception):
    """Raised when framing or packet decoding fails."""
    pass


@dataclass(frozen=True)
class Packet:
    """Represents a decoded framed message."""
    msg_type: MessageType
    version: int
    payload: bytes


class PacketCodec:
    """Encodes and decodes framed packets according to the 11-byte header specification."""

    @staticmethod
    def encode(msg_type: MessageType, payload: bytes = b"") -> bytes:
        """Encodes a message into a complete framed packet.
        
        Frame Layout:
          0..3:   MAGIC "ODSP"
          4:      VERSION (0x01)
          5..6:   MSG_TYPE (uint16 LE)
          7..10:  PAYLOAD_LEN (uint32 LE)
          11..N:  PAYLOAD
        """
        payload_len = len(payload)
        if payload_len > MAX_PAYLOAD_BYTES:
            raise PacketCodecError(
                f"Payload size {payload_len} exceeds maximum {MAX_PAYLOAD_BYTES} bytes"
            )

        header = struct.pack(
            "<4sBH I",
            MAGIC,
            PROTOCOL_VERSION,
            int(msg_type),
            payload_len
        )
        return header + payload

    @staticmethod
    def decode(data: bytes) -> Packet:
        """Decodes a single complete packet from bytes."""
        if len(data) < HEADER_SIZE:
            raise PacketCodecError(f"Frame length {len(data)} is less than header size {HEADER_SIZE}")

        magic, version, raw_type, payload_len = struct.unpack("<4sBH I", data[:HEADER_SIZE])

        if magic != MAGIC:
            raise PacketCodecError(f"Invalid magic bytes: {magic!r}, expected {MAGIC!r}")

        if version != PROTOCOL_VERSION:
            raise PacketCodecError(f"Unsupported protocol version: {version}, expected {PROTOCOL_VERSION}")

        if payload_len > MAX_PAYLOAD_BYTES:
            raise PacketCodecError(f"Payload length {payload_len} exceeds maximum allowed {MAX_PAYLOAD_BYTES}")

        total_expected = HEADER_SIZE + payload_len
        if len(data) < total_expected:
            raise PacketCodecError(
                f"Truncated packet: expected {total_expected} bytes, got {len(data)}"
            )

        msg_type = MessageType.from_id(raw_type)
        if msg_type is None:
            raise PacketCodecError(f"Unknown message type ID: 0x{raw_type:04X}")

        payload = data[HEADER_SIZE:total_expected]
        return Packet(msg_type=msg_type, version=version, payload=payload)

    # ── Binary payload helpers ───────────────────────────────────────────────

    @staticmethod
    def encode_video_frame_payload(timestamp_ns: int, is_keyframe: bool, nal_data: bytes) -> bytes:
        """Encodes the 12-byte binary prefix for VIDEO_FRAME followed by NAL data.
        
        Layout:
          0..7:  TIMESTAMP_NS (int64 LE)
          8..11: FLAGS (uint32 LE, bit 0 = keyframe)
          12..N: NAL data
        """
        flags = VIDEO_FRAME_FLAG_KEYFRAME if is_keyframe else 0
        prefix = struct.pack("<qI", timestamp_ns, flags)
        return prefix + nal_data

    @staticmethod
    def decode_video_frame_payload(payload: bytes) -> Tuple[int, bool, bytes]:
        """Decodes VIDEO_FRAME binary payload into (timestamp_ns, is_keyframe, nal_data)."""
        if len(payload) < 12:
            raise PacketCodecError(f"VIDEO_FRAME payload must be at least 12 bytes, got {len(payload)}")

        timestamp_ns, flags = struct.unpack("<qI", payload[:12])
        is_keyframe = bool(flags & VIDEO_FRAME_FLAG_KEYFRAME)
        nal_data = payload[12:]
        return timestamp_ns, is_keyframe, nal_data

    @staticmethod
    def encode_audio_frame_payload(timestamp_ns: int, sequence: int, audio_data: bytes) -> bytes:
        """Encodes the 12-byte binary prefix for AUDIO_FRAME followed by audio data.
        
        Layout:
          0..7:  TIMESTAMP_NS (int64 LE)
          8..11: SEQUENCE (uint32 LE)
          12..N: Audio data
        """
        prefix = struct.pack("<qI", timestamp_ns, sequence)
        return prefix + audio_data

    @staticmethod
    def decode_audio_frame_payload(payload: bytes) -> Tuple[int, int, bytes]:
        """Decodes AUDIO_FRAME binary payload into (timestamp_ns, sequence, audio_data)."""
        if len(payload) < 12:
            raise PacketCodecError(f"AUDIO_FRAME payload must be at least 12 bytes, got {len(payload)}")

        timestamp_ns, sequence = struct.unpack("<qI", payload[:12])
        audio_data = payload[12:]
        return timestamp_ns, sequence, audio_data


class StreamDecoder:
    """Accumulates incoming bytes from a TCP stream and yields complete Packet objects."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes) -> List[Packet]:
        """Feeds raw incoming bytes into buffer and extracts all completed packets."""
        self._buffer.extend(data)
        packets: List[Packet] = []

        while len(self._buffer) >= HEADER_SIZE:
            magic = bytes(self._buffer[:4])
            if magic != MAGIC:
                # Seek forward to next occurrence of MAGIC or discard invalid prefix
                next_magic_idx = self._buffer.find(MAGIC, 1)
                if next_magic_idx == -1:
                    # No magic found in buffer, retain at most 3 bytes in case magic spans boundaries
                    self._buffer = self._buffer[-3:]
                    break
                else:
                    del self._buffer[:next_magic_idx]
                    continue

            # Read payload length
            _, version, raw_type, payload_len = struct.unpack("<4sBH I", self._buffer[:HEADER_SIZE])

            if payload_len > MAX_PAYLOAD_BYTES:
                # Discard corrupted header
                del self._buffer[:HEADER_SIZE]
                continue

            total_size = HEADER_SIZE + payload_len
            if len(self._buffer) < total_size:
                # Incomplete packet, wait for more data
                break

            packet_bytes = bytes(self._buffer[:total_size])
            del self._buffer[:total_size]

            msg_type = MessageType.from_id(raw_type)
            if msg_type is not None:
                payload = packet_bytes[HEADER_SIZE:]
                packets.append(Packet(msg_type=msg_type, version=version, payload=payload))
            else:
                # Forward compatibility: Unknown MSG_TYPE discarded silently without error
                pass

        return packets
