package com.opendisplay.usb.protocol

/**
 * All message types defined in the OpenDisplay Protocol v1.
 *
 * IDs are uint16 values transmitted little-endian in the frame header at offset 5.
 *
 * Unknown IDs received from the peer MUST be silently discarded — the receiver
 * MUST NOT disconnect on an unknown type. This ensures forward compatibility when
 * a future version adds new message types.
 */
enum class MessageType(val id: UShort) {

    // ── Handshake ──────────────────────────────────────────────────────────────

    /** Android → Windows: initial identification and protocol version announcement. */
    HELLO(0x0001u),

    /** Windows → Android: handshake accepted or rejected. */
    HELLO_ACK(0x0002u),

    // ── Capability Negotiation ─────────────────────────────────────────────────

    /** Android → Windows: full device capability report. */
    CAPABILITIES(0x0003u),

    /** Windows → Android: capability report acknowledged. */
    CAPABILITIES_ACK(0x0004u),

    // ── Display Configuration ──────────────────────────────────────────────────

    /** Windows → Android: desired display resolution, frame rate, orientation. */
    DISPLAY_CONFIG(0x0005u),

    /** Android → Windows: display configuration accepted or rejected. */
    DISPLAY_CONFIG_ACK(0x0006u),

    // ── Video ──────────────────────────────────────────────────────────────────

    /** Windows → Android: video codec, dimensions, and codec-specific data (SPS/PPS). */
    VIDEO_CONFIG(0x0007u),

    /** Android → Windows: video configuration accepted or rejected. */
    VIDEO_CONFIG_ACK(0x0008u),

    /**
     * Windows → Android: a single compressed video frame.
     * Payload is BINARY (not JSON). See [PacketCodec] for structure.
     */
    VIDEO_FRAME(0x0009u),

    // ── Audio ──────────────────────────────────────────────────────────────────

    /** Windows → Android: audio codec, sample rate, channel count. */
    AUDIO_CONFIG(0x000Au),

    /**
     * Windows → Android: a single compressed audio frame.
     * Payload is BINARY (not JSON).
     */
    AUDIO_FRAME(0x000Bu),

    // ── Input ──────────────────────────────────────────────────────────────────

    /**
     * Android → Windows: a touch or stylus input event.
     * Payload is JSON with normalized coordinates.
     */
    INPUT_EVENT(0x000Cu),

    // ── Clipboard ──────────────────────────────────────────────────────────────

    /** Bidirectional: clipboard content synchronization. */
    CLIPBOARD_EVENT(0x000Du),

    // ── File Transfer ──────────────────────────────────────────────────────────

    /** Bidirectional: file transfer chunk. Future feature. */
    FILE_TRANSFER(0x000Eu),

    // ── Keep-alive / Latency ──────────────────────────────────────────────────

    /** Bidirectional: latency probe. The sender records the send timestamp. */
    PING(0x000Fu),

    /** Bidirectional: latency probe response. */
    PONG(0x0010u),

    // ── Stream Control ────────────────────────────────────────────────────────

    /** Windows → Android: reset the video stream (e.g., resolution change). */
    STREAM_RESET(0x0011u),

    // ── Error & Disconnect ────────────────────────────────────────────────────

    /** Bidirectional: report an error condition. Does not imply disconnect. */
    ERROR(0x0012u),

    /** Bidirectional: clean session termination. */
    DISCONNECT(0x0013u);

    companion object {
        private val byId: Map<UShort, MessageType> = entries.associateBy { it.id }

        /**
         * Returns the [MessageType] for the given [id], or null if the id is unknown.
         *
         * Callers receiving null MUST log a warning and discard the packet —
         * they MUST NOT disconnect.
         */
        fun fromId(id: UShort): MessageType? = byId[id]
    }
}
