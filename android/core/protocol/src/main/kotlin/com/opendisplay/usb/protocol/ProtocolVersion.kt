package com.opendisplay.usb.protocol

/**
 * Constants for the OpenDisplay Protocol (ODSP), version 1.
 *
 * Both sides MUST agree on CURRENT. If a peer sends a different version, send ERROR
 * with code ERR_PROTOCOL_VERSION and disconnect gracefully.
 *
 * Binary frame header (11 bytes, little-endian for multi-byte fields):
 *
 *   Offset  Size  Field
 *   ------  ----  -----
 *   0       4     Magic bytes: ASCII "ODSP" = 0x4F 0x44 0x53 0x50
 *   4       1     Protocol version (uint8). Currently 0x01.
 *   5       2     Message type ID (uint16, little-endian). See [MessageType].
 *   7       4     Payload length (uint32, little-endian). 0..MAX_PAYLOAD_BYTES.
 *   11      N     Payload: UTF-8 JSON or binary depending on message type.
 *
 * VIDEO_FRAME and AUDIO_FRAME carry binary payloads; all other messages carry UTF-8 JSON.
 */
object ProtocolVersion {

    /** Current protocol version. Both sides MUST match on this value. */
    const val CURRENT: Int = 1

    /**
     * Magic bytes at the start of every frame: ASCII "ODSP".
     * Stored as a big-endian int32: 0x4F445350.
     */
    const val MAGIC: Int = 0x4F445350  // "ODSP"

    /** Magic as a raw byte array for stream-level matching. */
    val MAGIC_BYTES: ByteArray = byteArrayOf(0x4F, 0x44, 0x53, 0x50)

    /** Total size of the frame header in bytes. */
    const val HEADER_SIZE: Int = 11

    /** Maximum allowed payload size in bytes (16 MiB). */
    const val MAX_PAYLOAD_BYTES: Int = 16 * 1024 * 1024

    /** TCP port used for ADB-forwarded connections. Set up with: adb forward tcp:7320 tcp:7320 */
    const val DEFAULT_PORT: Int = 7320
}
