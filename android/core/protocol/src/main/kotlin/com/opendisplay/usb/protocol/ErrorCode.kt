package com.opendisplay.usb.protocol

/**
 * Error codes used in [ErrorMessage.code].
 *
 * These codes are part of the protocol specification. Both Android and Windows
 * implementations MUST use these values when sending ERROR messages.
 */
enum class ErrorCode(val code: Int, val description: String) {

    ERR_NONE(0x0000, "No error"),
    ERR_PROTOCOL_VERSION(0x0001, "Incompatible protocol version"),
    ERR_UNSUPPORTED_CODEC(0x0002, "Requested codec is not supported by this device"),
    ERR_UNSUPPORTED_RESOLUTION(0x0003, "Requested resolution is not supported"),
    ERR_UNSUPPORTED_FRAMERATE(0x0004, "Requested frame rate is not supported"),
    ERR_DECODER_FAILED(0x0005, "Hardware or software decoder failure"),
    ERR_INVALID_PACKET(0x0006, "Malformed or truncated packet received"),
    ERR_STREAM_RESET(0x0007, "Stream reset was requested"),
    ERR_AUTH_FAILED(0x0008, "Authentication failed (reserved for future use)"),
    ERR_INTERNAL(0x00FF, "Unspecified internal error");

    companion object {
        private val byCode: Map<Int, ErrorCode> = entries.associateBy { it.code }

        /**
         * Returns the [ErrorCode] for [code], or [ERR_INTERNAL] if unknown.
         * Unknown codes from future protocol versions are mapped to ERR_INTERNAL.
         */
        fun fromCode(code: Int): ErrorCode = byCode[code] ?: ERR_INTERNAL
    }
}
