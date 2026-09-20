package com.opendisplay.usb.protocol

import java.io.EOFException
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

// ─────────────────────────────────────────────────────────────────────────────
// Exceptions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Thrown by [PacketCodec.decode] and [PacketCodec.decodeFromStream] when a
 * received byte sequence violates the protocol framing rules.
 *
 * Callers catching this exception MUST NOT disconnect; they should send an
 * ERROR message with [ErrorCode.ERR_INVALID_PACKET] and continue reading.
 */
class PacketDecodeException(
    message: String,
    cause: Throwable? = null
) : Exception(message, cause)

// ─────────────────────────────────────────────────────────────────────────────
// Packet
// ─────────────────────────────────────────────────────────────────────────────

/**
 * A decoded protocol packet.
 *
 * [type]    — the message type (guaranteed non-null from [PacketCodec]).
 * [version] — protocol version byte from the header (should be [ProtocolVersion.CURRENT]).
 * [payload] — raw payload bytes (UTF-8 JSON for most types; binary for VIDEO_FRAME / AUDIO_FRAME).
 */
data class Packet(
    val type: MessageType,
    val version: Byte,
    val payload: ByteArray
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (javaClass != other?.javaClass) return false
        other as Packet
        return type == other.type && version == other.version && payload.contentEquals(other.payload)
    }

    override fun hashCode(): Int {
        var result = type.hashCode()
        result = 31 * result + version
        result = 31 * result + payload.contentHashCode()
        return result
    }

    override fun toString(): String =
        "Packet(type=$type, version=$version, payloadSize=${payload.size})"
}

// ─────────────────────────────────────────────────────────────────────────────
// PacketCodec
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Binary framing encoder and decoder for the OpenDisplay Protocol.
 *
 * Frame layout (all multi-byte integers are LITTLE-ENDIAN except the magic):
 *
 * ```
 * Offset  Size  Type      Field
 * ──────  ────  ────────  ─────────────────────────────────────────────────
 *  0       4    uint32    Magic = 0x4F445350 ("ODSP"), big-endian comparison
 *  4       1    uint8     Protocol version. Must equal [ProtocolVersion.CURRENT].
 *  5       2    uint16LE  Message type ID. See [MessageType].
 *  7       4    uint32LE  Payload length in bytes. 0 .. MAX_PAYLOAD_BYTES.
 * 11       N    bytes     Payload: UTF-8 JSON or binary.
 * ```
 *
 * Total header size: [ProtocolVersion.HEADER_SIZE] = 11 bytes.
 *
 * VIDEO_FRAME binary payload sub-structure:
 * ```
 *  0       8    int64LE   TIMESTAMP_NS — stream-relative monotonic nanoseconds
 *  8       4    uint32LE  FLAGS        — bit 0: 1=keyframe, bits 1–31: reserved
 * 12       N    bytes     DATA         — raw NAL units (H.264 / HEVC / AV1)
 * ```
 *
 * AUDIO_FRAME binary payload sub-structure:
 * ```
 *  0       8    int64LE   TIMESTAMP_NS — presentation nanoseconds
 *  8       4    uint32LE  SEQUENCE     — monotonically increasing packet sequence number
 * 12       N    bytes     DATA         — encoded audio (Opus / AAC / PCM)
 * ```
 */
object PacketCodec {

    // ── Encode ────────────────────────────────────────────────────────────────

    /**
     * Encodes a message into a complete frame (header + payload).
     *
     * @param type    the message type
     * @param payload the raw payload bytes (JSON or binary, caller's responsibility)
     * @return        the complete frame ready to transmit
     */
    fun encode(type: MessageType, payload: ByteArray = ByteArray(0)): ByteArray {
        require(payload.size <= ProtocolVersion.MAX_PAYLOAD_BYTES) {
            "Payload size ${payload.size} exceeds MAX_PAYLOAD_BYTES ${ProtocolVersion.MAX_PAYLOAD_BYTES}"
        }
        val frame = ByteBuffer.allocate(ProtocolVersion.HEADER_SIZE + payload.size)
            .order(ByteOrder.LITTLE_ENDIAN)

        // Magic is written as 4 separate bytes (big-endian order) to avoid byte-order ambiguity
        frame.put(0x4F.toByte())
        frame.put(0x44.toByte())
        frame.put(0x53.toByte())
        frame.put(0x50.toByte())

        frame.put(ProtocolVersion.CURRENT.toByte())             // version
        frame.putShort(type.id.toShort())                       // type LE
        frame.putInt(payload.size)                              // length LE
        frame.put(payload)

        return frame.array()
    }

    // ── Decode from byte array ─────────────────────────────────────────────────

    /**
     * Decodes a frame from a complete byte array.
     *
     * Returns [Result.failure] with [PacketDecodeException] when:
     * - [data] is shorter than [ProtocolVersion.HEADER_SIZE]
     * - Magic bytes do not match "ODSP"
     * - Payload length field exceeds [ProtocolVersion.MAX_PAYLOAD_BYTES]
     * - [data] does not contain the full declared payload
     * - The message type ID is unknown (the packet should be discarded, not the connection dropped)
     *
     * Returns [Result.success] with the decoded [Packet] otherwise.
     */
    fun decode(data: ByteArray): Result<Packet> = runCatching {
        if (data.size < ProtocolVersion.HEADER_SIZE) {
            throw PacketDecodeException(
                "Frame too short: ${data.size} bytes, need at least ${ProtocolVersion.HEADER_SIZE}"
            )
        }

        val buf = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)

        // Validate magic (read as 4 individual bytes)
        val m0 = buf.get().toInt() and 0xFF
        val m1 = buf.get().toInt() and 0xFF
        val m2 = buf.get().toInt() and 0xFF
        val m3 = buf.get().toInt() and 0xFF
        if (m0 != 0x4F || m1 != 0x44 || m2 != 0x53 || m3 != 0x50) {
            throw PacketDecodeException(
                "Invalid magic bytes: 0x%02X 0x%02X 0x%02X 0x%02X (expected 4F 44 53 50 = \"ODSP\")"
                    .format(m0, m1, m2, m3)
            )
        }

        val version = buf.get()                       // version byte
        val typeId = buf.getShort().toUShort()         // type LE
        val payloadLen = buf.getInt()                  // length LE (read as signed; validate below)

        if (payloadLen < 0 || payloadLen > ProtocolVersion.MAX_PAYLOAD_BYTES) {
            throw PacketDecodeException(
                "Invalid payload length: $payloadLen " +
                        "(max=${ProtocolVersion.MAX_PAYLOAD_BYTES})"
            )
        }

        val expectedTotal = ProtocolVersion.HEADER_SIZE + payloadLen
        if (data.size < expectedTotal) {
            throw PacketDecodeException(
                "Truncated frame: declared payload=$payloadLen bytes " +
                        "but only ${data.size - ProtocolVersion.HEADER_SIZE} payload bytes available"
            )
        }

        val msgType = MessageType.fromId(typeId)
            ?: throw PacketDecodeException(
                "Unknown message type: 0x%04X".format(typeId.toInt())
            )

        val payload = ByteArray(payloadLen)
        buf.get(payload)

        Packet(type = msgType, version = version, payload = payload)
    }

    // ── Decode from InputStream ────────────────────────────────────────────────

    /**
     * Reads exactly one frame from [input] by reading the 11-byte header first,
     * then reading the declared payload length.
     *
     * Blocks until a complete frame is received or an error occurs.
     *
     * Useful for ADB/TCP connections where data arrives as a stream.
     *
     * Returns [Result.failure] with:
     * - [PacketDecodeException] for protocol violations
     * - [java.io.EOFException] if the stream closes mid-frame
     * - [java.io.IOException] for underlying I/O errors
     */
    fun decodeFromStream(input: InputStream): Result<Packet> = runCatching {
        val header = input.readExactly(ProtocolVersion.HEADER_SIZE)
        val buf = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN)

        // Validate magic
        val m0 = buf.get().toInt() and 0xFF
        val m1 = buf.get().toInt() and 0xFF
        val m2 = buf.get().toInt() and 0xFF
        val m3 = buf.get().toInt() and 0xFF
        if (m0 != 0x4F || m1 != 0x44 || m2 != 0x53 || m3 != 0x50) {
            throw PacketDecodeException(
                "Invalid magic bytes: 0x%02X 0x%02X 0x%02X 0x%02X".format(m0, m1, m2, m3)
            )
        }

        val version = buf.get()
        val typeId = buf.getShort().toUShort()
        val payloadLen = buf.getInt()

        if (payloadLen < 0 || payloadLen > ProtocolVersion.MAX_PAYLOAD_BYTES) {
            throw PacketDecodeException("Invalid payload length: $payloadLen")
        }

        val msgType = MessageType.fromId(typeId)
            ?: throw PacketDecodeException("Unknown message type: 0x%04X".format(typeId.toInt()))

        val payload = if (payloadLen > 0) input.readExactly(payloadLen) else ByteArray(0)

        Packet(type = msgType, version = version, payload = payload)
    }

    // ── VIDEO_FRAME binary payload helpers ────────────────────────────────────

    /** Offset of the TIMESTAMP_NS field within a VIDEO_FRAME or AUDIO_FRAME binary payload. */
    const val BINARY_FRAME_TIMESTAMP_OFFSET: Int = 0

    /** Offset of the FLAGS field within a VIDEO_FRAME binary payload. */
    const val VIDEO_FRAME_FLAGS_OFFSET: Int = 8

    /** Offset of the raw NAL data within a VIDEO_FRAME binary payload. */
    const val VIDEO_FRAME_DATA_OFFSET: Int = 12

    /** Bit mask for the keyframe flag in a VIDEO_FRAME FLAGS field. */
    const val VIDEO_FRAME_FLAG_KEYFRAME: Int = 0x00000001

    /** Offset of the SEQUENCE field within an AUDIO_FRAME binary payload. */
    const val AUDIO_FRAME_SEQUENCE_OFFSET: Int = 8

    /** Offset of the raw audio data within an AUDIO_FRAME binary payload. */
    const val AUDIO_FRAME_DATA_OFFSET: Int = 12

    /**
     * Encodes a VIDEO_FRAME binary payload.
     *
     * @param timestampNs  stream-relative monotonic timestamp in nanoseconds
     * @param isKeyframe   true if this frame is an IDR (H.264) or IRAP (HEVC) frame
     * @param nalData      raw compressed NAL units
     */
    fun encodeVideoFramePayload(
        timestampNs: Long,
        isKeyframe: Boolean,
        nalData: ByteArray
    ): ByteArray {
        val payload = ByteBuffer.allocate(VIDEO_FRAME_DATA_OFFSET + nalData.size)
            .order(ByteOrder.LITTLE_ENDIAN)
        payload.putLong(timestampNs)
        payload.putInt(if (isKeyframe) VIDEO_FRAME_FLAG_KEYFRAME else 0)
        payload.put(nalData)
        return payload.array()
    }

    /**
     * Decodes the header fields of a VIDEO_FRAME binary payload.
     * Returns Triple(timestampNs, isKeyframe, nalDataSliceStartIndex).
     *
     * Throws [PacketDecodeException] if the payload is too short.
     */
    fun decodeVideoFramePayload(payload: ByteArray): Triple<Long, Boolean, Int> {
        if (payload.size < VIDEO_FRAME_DATA_OFFSET) {
            throw PacketDecodeException(
                "VIDEO_FRAME payload too short: ${payload.size} bytes, need at least $VIDEO_FRAME_DATA_OFFSET"
            )
        }
        val buf = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN)
        val timestampNs = buf.getLong()
        val flags = buf.getInt()
        val isKeyframe = (flags and VIDEO_FRAME_FLAG_KEYFRAME) != 0
        return Triple(timestampNs, isKeyframe, VIDEO_FRAME_DATA_OFFSET)
    }

    /**
     * Encodes an AUDIO_FRAME binary payload.
     */
    fun encodeAudioFramePayload(
        timestampNs: Long,
        sequenceNumber: Int,
        audioData: ByteArray
    ): ByteArray {
        val payload = ByteBuffer.allocate(AUDIO_FRAME_DATA_OFFSET + audioData.size)
            .order(ByteOrder.LITTLE_ENDIAN)
        payload.putLong(timestampNs)
        payload.putInt(sequenceNumber)
        payload.put(audioData)
        return payload.array()
    }

    /**
     * Decodes the header fields of an AUDIO_FRAME binary payload.
     * Returns Triple(timestampNs, sequenceNumber, audioDataSliceStartIndex).
     *
     * Throws [PacketDecodeException] if the payload is too short.
     */
    fun decodeAudioFramePayload(payload: ByteArray): Triple<Long, Int, Int> {
        if (payload.size < AUDIO_FRAME_DATA_OFFSET) {
            throw PacketDecodeException(
                "AUDIO_FRAME payload too short: ${payload.size} bytes, need at least $AUDIO_FRAME_DATA_OFFSET"
            )
        }
        val buf = ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN)
        val timestampNs = buf.getLong()
        val sequenceNumber = buf.getInt()
        return Triple(timestampNs, sequenceNumber, AUDIO_FRAME_DATA_OFFSET)
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    /**
     * Reads exactly [n] bytes from this InputStream.
     * Throws [EOFException] if the stream closes before [n] bytes are read.
     */
    private fun InputStream.readExactly(n: Int): ByteArray {
        val buf = ByteArray(n)
        var offset = 0
        while (offset < n) {
            val read = read(buf, offset, n - offset)
            if (read < 0) throw EOFException("Stream closed after $offset of $n bytes")
            offset += read
        }
        return buf
    }
}
