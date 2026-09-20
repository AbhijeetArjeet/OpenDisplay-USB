package com.opendisplay.usb.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * JSON serialization and deserialization for OpenDisplay Protocol messages.
 *
 * Configuration:
 * - [ignoreUnknownKeys] = true  — forward-compatible: future message fields are silently ignored
 * - [encodeDefaults] = true     — ensures optional fields with defaults are always emitted
 * - [isLenient] = false         — strict JSON parsing
 *
 * Thread safety: all methods are thread-safe. [json] is stateless.
 */
object JsonCodec {

    val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        isLenient = false
        prettyPrint = false
    }

    // ── Encoding ──────────────────────────────────────────────────────────────

    /** Encodes any @Serializable message to a UTF-8 JSON byte array. */
    inline fun <reified T> encode(message: T): ByteArray =
        json.encodeToString(message).toByteArray(Charsets.UTF_8)

    // ── Decoding ──────────────────────────────────────────────────────────────

    /** Decodes a UTF-8 JSON byte array to the specified type. */
    inline fun <reified T> decode(bytes: ByteArray): Result<T> = runCatching {
        json.decodeFromString<T>(bytes.toString(Charsets.UTF_8))
    }

    /**
     * Peeks at the "type" field of a JSON payload without fully deserializing it.
     * Returns null if the field is absent or the bytes are not valid JSON.
     */
    fun peekType(bytes: ByteArray): String? = runCatching {
        val element: JsonElement = json.parseToJsonElement(bytes.toString(Charsets.UTF_8))
        element.jsonObject["type"]?.jsonPrimitive?.content
    }.getOrNull()

    // ── Per-type decode helpers ───────────────────────────────────────────────

    fun decodeHello(bytes: ByteArray): Result<HelloMessage> = decode(bytes)
    fun decodeHelloAck(bytes: ByteArray): Result<HelloAckMessage> = decode(bytes)
    fun decodeCapabilities(bytes: ByteArray): Result<CapabilitiesMessage> = decode(bytes)
    fun decodeCapabilitiesAck(bytes: ByteArray): Result<CapabilitiesAckMessage> = decode(bytes)
    fun decodeDisplayConfig(bytes: ByteArray): Result<DisplayConfigMessage> = decode(bytes)
    fun decodeDisplayConfigAck(bytes: ByteArray): Result<DisplayConfigAckMessage> = decode(bytes)
    fun decodeVideoConfig(bytes: ByteArray): Result<VideoConfigMessage> = decode(bytes)
    fun decodeVideoConfigAck(bytes: ByteArray): Result<VideoConfigAckMessage> = decode(bytes)
    fun decodeAudioConfig(bytes: ByteArray): Result<AudioConfigMessage> = decode(bytes)
    fun decodePing(bytes: ByteArray): Result<PingMessage> = decode(bytes)
    fun decodePong(bytes: ByteArray): Result<PongMessage> = decode(bytes)
    fun decodeStreamReset(bytes: ByteArray): Result<StreamResetMessage> = decode(bytes)
    fun decodeError(bytes: ByteArray): Result<ErrorMessage> = decode(bytes)
    fun decodeDisconnect(bytes: ByteArray): Result<DisconnectMessage> = decode(bytes)
    fun decodeInputEvent(bytes: ByteArray): Result<InputEventMessage> = decode(bytes)
    fun decodeClipboardEvent(bytes: ByteArray): Result<ClipboardEventMessage> = decode(bytes)

    /**
     * Dispatches an incoming JSON payload to the correct message type based on [MessageType].
     *
     * Returns a typed message object as [Any], or [Result.failure] if deserialization fails.
     *
     * VIDEO_FRAME and AUDIO_FRAME carry binary payloads and MUST NOT be passed to this function.
     */
    fun decodeIncoming(bytes: ByteArray, type: MessageType): Result<Any> = when (type) {
        MessageType.HELLO               -> decodeHello(bytes)
        MessageType.HELLO_ACK           -> decodeHelloAck(bytes)
        MessageType.CAPABILITIES        -> decodeCapabilities(bytes)
        MessageType.CAPABILITIES_ACK    -> decodeCapabilitiesAck(bytes)
        MessageType.DISPLAY_CONFIG      -> decodeDisplayConfig(bytes)
        MessageType.DISPLAY_CONFIG_ACK  -> decodeDisplayConfigAck(bytes)
        MessageType.VIDEO_CONFIG        -> decodeVideoConfig(bytes)
        MessageType.VIDEO_CONFIG_ACK    -> decodeVideoConfigAck(bytes)
        MessageType.AUDIO_CONFIG        -> decodeAudioConfig(bytes)
        MessageType.PING                -> decodePing(bytes)
        MessageType.PONG                -> decodePong(bytes)
        MessageType.STREAM_RESET        -> decodeStreamReset(bytes)
        MessageType.ERROR               -> decodeError(bytes)
        MessageType.DISCONNECT          -> decodeDisconnect(bytes)
        MessageType.INPUT_EVENT         -> decodeInputEvent(bytes)
        MessageType.CLIPBOARD_EVENT     -> decodeClipboardEvent(bytes)
        MessageType.VIDEO_FRAME,
        MessageType.AUDIO_FRAME         -> Result.failure(
            IllegalArgumentException(
                "$type carries a binary payload and must not be decoded with JsonCodec. " +
                "Use PacketCodec.decodeVideoFramePayload() or decodeAudioFramePayload() instead."
            )
        )
        MessageType.FILE_TRANSFER       ->
            // TODO(phase2): implement file transfer decoding
            Result.failure(UnsupportedOperationException("FILE_TRANSFER is not implemented in Phase 1"))
    }
}
