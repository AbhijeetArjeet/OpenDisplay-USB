package com.opendisplay.usb.video

/**
 * Configuration for the video decoder, derived from the VIDEO_CONFIG protocol message.
 *
 * [csd0] and [csd1] are the codec-specific data buffers required by MediaCodec:
 *   H.264: csd0 = SPS NAL unit, csd1 = PPS NAL unit
 *   HEVC:  csd0 = VPS+SPS+PPS NAL units combined, csd1 = null
 *   AV1:   csd0 = AV1CodecConfigurationRecord, csd1 = null
 */
data class VideoConfig(
    val codecMimeType: String,
    val widthPx: Int,
    val heightPx: Int,
    val frameRateHz: Float,
    val bitrateBps: Int,
    val lowLatencyMode: Boolean = false,
    /** Codec-specific data buffer 0 (SPS for H.264, VPS+SPS+PPS for HEVC). Null for raw streams. */
    val csd0: ByteArray? = null,
    /** Codec-specific data buffer 1 (PPS for H.264). Null for HEVC/AV1. */
    val csd1: ByteArray? = null
) {
    val isH264: Boolean get() = codecMimeType == VideoCodecMime.H264
    val isHEVC: Boolean get() = codecMimeType == VideoCodecMime.HEVC
    val isAV1: Boolean  get() = codecMimeType == VideoCodecMime.AV1

    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (javaClass != other?.javaClass) return false
        other as VideoConfig
        return codecMimeType == other.codecMimeType &&
                widthPx == other.widthPx &&
                heightPx == other.heightPx &&
                frameRateHz == other.frameRateHz &&
                bitrateBps == other.bitrateBps &&
                lowLatencyMode == other.lowLatencyMode &&
                (csd0?.contentEquals(other.csd0 ?: ByteArray(0)) ?: (other.csd0 == null)) &&
                (csd1?.contentEquals(other.csd1 ?: ByteArray(0)) ?: (other.csd1 == null))
    }

    override fun hashCode(): Int {
        var result = codecMimeType.hashCode()
        result = 31 * result + widthPx
        result = 31 * result + heightPx
        result = 31 * result + frameRateHz.hashCode()
        result = 31 * result + bitrateBps
        result = 31 * result + lowLatencyMode.hashCode()
        result = 31 * result + (csd0?.contentHashCode() ?: 0)
        result = 31 * result + (csd1?.contentHashCode() ?: 0)
        return result
    }

    override fun toString(): String =
        "VideoConfig($codecMimeType ${widthPx}x${heightPx} @ ${frameRateHz}fps, " +
        "${bitrateBps / 1000}kbps, lowLatency=$lowLatencyMode)"
}
