package com.opendisplay.usb.protocol

import kotlinx.serialization.Serializable

// ─────────────────────────────────────────────────────────────────────────────
// Shared nested types
// ─────────────────────────────────────────────────────────────────────────────

@Serializable
data class VideoCapabilityInfo(
    val codec: String,                 // "H264", "HEVC", "AV1"
    val supported: Boolean,
    val hardwareAccelerated: Boolean,
    val maxWidth: Int,
    val maxHeight: Int,
    val maxFrameRateHz: Float,
    val lowLatencySupported: Boolean
)

@Serializable
data class AudioCapabilityInfo(
    val opusSupported: Boolean,
    val aacSupported: Boolean,
    val pcmSupported: Boolean,
    val supportedSampleRates: List<Int>,
    val supportedChannelCounts: List<Int>,
    val lowLatencyOutput: Boolean
)

@Serializable
data class InputCapabilityInfo(
    val touchSupported: Boolean,
    val maxTouchPoints: Int,
    val stylusSupported: Boolean,
    val pressureSupported: Boolean,
    val tiltSupported: Boolean
)

@Serializable
data class DisplayCapabilityInfo(
    val widthPx: Int,
    val heightPx: Int,
    val densityDpi: Int,
    val refreshRateHz: Float,
    /** 0=portrait, 1=landscape, 2=reverse-portrait, 3=reverse-landscape */
    val orientation: Int
)

@Serializable
data class DeviceCapabilityInfo(
    val hasMicrophone: Boolean,
    val hasCamera: Boolean,
    val hasSpeaker: Boolean,
    /** 0–100, or null if unavailable */
    val batteryLevel: Int?,
    val batteryCharging: Boolean?
)

@Serializable
data class PointerInfo(
    val id: Int,
    /** "DOWN", "MOVE", "UP", "CANCEL" */
    val action: String,
    /** Normalized 0.0 … 1.0 */
    val x: Float,
    /** Normalized 0.0 … 1.0 */
    val y: Float,
    val pressure: Float = 0f,
    val tiltX: Float? = null,
    val tiltY: Float? = null,
    /** "FINGER", "STYLUS", "MOUSE", "UNKNOWN" */
    val toolType: String,
    val buttons: Int = 0
)

// ─────────────────────────────────────────────────────────────────────────────
// Handshake
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Android → Windows: initial identification sent immediately after TCP connection.
 */
@Serializable
data class HelloMessage(
    val type: String = "HELLO",
    val protocol: Int = ProtocolVersion.CURRENT,
    val platform: String = "android",
    val manufacturer: String,
    val model: String,
    val androidVersion: String,
    val sdk: Int,
    /** Stable opaque identifier. NOT the Android hardware device ID. */
    val deviceId: String
)

/**
 * Windows → Android: handshake response.
 * If [accepted] is false, [rejectionReason] MUST be set.
 */
@Serializable
data class HelloAckMessage(
    val type: String = "HELLO_ACK",
    val protocol: Int,
    val accepted: Boolean,
    val rejectionReason: String? = null
)

// ─────────────────────────────────────────────────────────────────────────────
// Capability Negotiation
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Android → Windows: full device capability report.
 * Sent immediately after receiving HELLO_ACK with accepted=true.
 */
@Serializable
data class CapabilitiesMessage(
    val type: String = "CAPABILITIES",
    val display: DisplayCapabilityInfo,
    val video: List<VideoCapabilityInfo>,
    val audio: AudioCapabilityInfo,
    val input: InputCapabilityInfo,
    val device: DeviceCapabilityInfo
)

/**
 * Windows → Android: acknowledge receipt of CAPABILITIES.
 */
@Serializable
data class CapabilitiesAckMessage(
    val type: String = "CAPABILITIES_ACK",
    val accepted: Boolean
)

// ─────────────────────────────────────────────────────────────────────────────
// Display Configuration
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Windows → Android: desired display dimensions, frame rate, and layout.
 * Android MUST either apply this config or return DISPLAY_CONFIG_ACK with accepted=false.
 */
@Serializable
data class DisplayConfigMessage(
    val type: String = "DISPLAY_CONFIG",
    val widthPx: Int,
    val heightPx: Int,
    val frameRateHz: Float,
    /** 0=portrait, 1=landscape, 2=reverse-portrait, 3=reverse-landscape */
    val orientation: Int,
    /** "RGBA_8888" is the only value in v1 */
    val pixelFormat: String = "RGBA_8888",
    /** "FIT", "CROP", "STRETCH" */
    val scaling: String = "FIT"
)

/**
 * Android → Windows: result of applying DISPLAY_CONFIG.
 * If [accepted] is false, [errorCode] and [errorMessage] MUST be set.
 */
@Serializable
data class DisplayConfigAckMessage(
    val type: String = "DISPLAY_CONFIG_ACK",
    val accepted: Boolean,
    val errorCode: Int = 0,
    val errorMessage: String? = null
)

// ─────────────────────────────────────────────────────────────────────────────
// Video
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Windows → Android: video stream parameters.
 *
 * For H.264: [csd0Base64] = base64(SPS NAL), [csd1Base64] = base64(PPS NAL).
 * For HEVC:  [csd0Base64] = base64(VPS+SPS+PPS NAL), [csd1Base64] = null.
 *
 * The CSD must be provided before any VIDEO_FRAME is sent. The first VIDEO_FRAME
 * after VIDEO_CONFIG MUST be a keyframe (IDR for H.264).
 */
@Serializable
data class VideoConfigMessage(
    val type: String = "VIDEO_CONFIG",
    /** "H264", "HEVC", "AV1" */
    val codec: String,
    val widthPx: Int,
    val heightPx: Int,
    val frameRateHz: Float,
    val bitrateBps: Int,
    val keyframeIntervalS: Float = 2f,
    val lowLatencyMode: Boolean = false,
    val csd0Base64: String? = null,
    val csd1Base64: String? = null
)

/**
 * Android → Windows: result of applying VIDEO_CONFIG.
 */
@Serializable
data class VideoConfigAckMessage(
    val type: String = "VIDEO_CONFIG_ACK",
    val accepted: Boolean,
    val errorCode: Int = 0
)

// ─────────────────────────────────────────────────────────────────────────────
// Audio
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Windows → Android: audio stream parameters.
 */
@Serializable
data class AudioConfigMessage(
    val type: String = "AUDIO_CONFIG",
    /** "audio/opus", "audio/mp4a-latm", "audio/raw" */
    val codecMimeType: String,
    val sampleRateHz: Int,
    val channelCount: Int,
    val bitrateBps: Int
)

// ─────────────────────────────────────────────────────────────────────────────
// Input
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Android → Windows: a touch or stylus input event with normalized coordinates.
 *
 * [eventType]: "TOUCH" or "STYLUS"
 * [timestampNs]: monotonic nanosecond timestamp from MotionEvent.eventTime, converted to ns.
 */
@Serializable
data class InputEventMessage(
    val type: String = "INPUT_EVENT",
    /** "TOUCH" or "STYLUS" */
    val eventType: String,
    val timestampNs: Long,
    val pointers: List<PointerInfo>
)

// ─────────────────────────────────────────────────────────────────────────────
// Clipboard
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Bidirectional: clipboard content synchronization.
 *
 * Android MUST NOT silently read clipboard data. On Android 10+ this must be
 * triggered by explicit user interaction. The protocol transports the content
 * but the application layer enforces privacy policy.
 */
@Serializable
data class ClipboardEventMessage(
    val type: String = "CLIPBOARD_EVENT",
    val content: String,
    val mimeType: String = "text/plain"
)

// ─────────────────────────────────────────────────────────────────────────────
// Keep-alive / Latency
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Bidirectional: latency probe. Sender records [timestampNs] at send time.
 */
@Serializable
data class PingMessage(
    val type: String = "PING",
    val timestampNs: Long
)

/**
 * Bidirectional: latency probe response.
 * [timestampNs] echoes the original PING timestamp.
 * [serverTimestampNs] is the responder's monotonic time at response time.
 */
@Serializable
data class PongMessage(
    val type: String = "PONG",
    val timestampNs: Long,
    val serverTimestampNs: Long
)

// ─────────────────────────────────────────────────────────────────────────────
// Stream Control
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Windows → Android: reset the video stream.
 * Android MUST flush its decoder and discard buffered frames.
 * The next VIDEO_CONFIG after STREAM_RESET establishes the new stream.
 * The first VIDEO_FRAME after the new VIDEO_CONFIG MUST be a keyframe.
 */
@Serializable
data class StreamResetMessage(
    val type: String = "STREAM_RESET",
    /**
     * "RESOLUTION_CHANGE", "CODEC_CHANGE", "ENCODER_RESET", "QUALITY_CHANGE",
     * or any future reason string. Receivers MUST tolerate unknown reasons.
     */
    val reason: String,
    val newWidthPx: Int? = null,
    val newHeightPx: Int? = null
)

// ─────────────────────────────────────────────────────────────────────────────
// Error & Disconnect
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Bidirectional: error notification.
 * Sending ERROR does not imply disconnection unless [fatal] is true.
 */
@Serializable
data class ErrorMessage(
    val type: String = "ERROR",
    val code: Int,
    val message: String,
    val fatal: Boolean = false
)

/**
 * Bidirectional: clean session termination.
 * [reason]: "USER_REQUESTED", "TRANSPORT_ERROR", "DECODER_FAILED", or future values.
 */
@Serializable
data class DisconnectMessage(
    val type: String = "DISCONNECT",
    val reason: String
)

// ─────────────────────────────────────────────────────────────────────────────
// File Transfer (stub — future feature)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Bidirectional: file transfer chunk. Not implemented in Phase 1.
 * The message type ID is reserved and the packet will be discarded if received.
 */
@Serializable
data class FileTransferMessage(
    val type: String = "FILE_TRANSFER",
    val transferId: String,
    val chunkIndex: Int,
    val totalChunks: Int,
    val dataBase64: String,
    val checksum: String
)
