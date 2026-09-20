"""Audio encoder and AUDIO_FRAME packetizer for Windows host."""

from typing import Tuple
from ..protocol.packet_codec import PacketCodec
from ..protocol.message_type import MessageType


class AudioEncoder:
    """Encodes and packetizes system audio into protocol AUDIO_FRAME packets."""

    def __init__(self, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self._sequence: int = 0

    def packetize_pcm(self, pcm_bytes: bytes, timestamp_ns: int) -> bytes:
        """Packages raw 16-bit PCM stereo audio into a framed AUDIO_FRAME packet.
        
        Header: 11 bytes
        Binary Payload:
          0..7:  TIMESTAMP_NS (int64 LE)
          8..11: SEQUENCE (uint32 LE)
          12..N: Audio bytes
        """
        payload = PacketCodec.encode_audio_frame_payload(
            timestamp_ns=timestamp_ns,
            sequence=self._sequence,
            audio_data=pcm_bytes
        )
        self._sequence = (self._sequence + 1) & 0xFFFFFFFF
        return PacketCodec.encode(MessageType.AUDIO_FRAME, payload)
