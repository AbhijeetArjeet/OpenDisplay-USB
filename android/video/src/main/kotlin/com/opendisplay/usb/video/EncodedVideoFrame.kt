package com.opendisplay.usb.video

import com.opendisplay.usb.timing.PresentationTimestamp

/**
 * A single compressed video frame ready to be fed into the MediaCodec decoder.
 *
 * [data]                  — raw compressed NAL units (H.264 / HEVC / AV1).
 *                           For H.264 these are Annex B format (start code prefixed).
 * [presentationTimestamp] — the frame's presentation time as provided by the Windows encoder.
 *                           Used as the MediaCodec presentationTimeUs parameter (converted via .us).
 * [isKeyframe]            — true if this is an IDR frame (H.264) or IRAP frame (HEVC).
 *                           The decoder may skip non-keyframes until the first keyframe arrives.
 */
data class EncodedVideoFrame(
    val data: ByteArray,
    val presentationTimestamp: PresentationTimestamp,
    val isKeyframe: Boolean
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (javaClass != other?.javaClass) return false
        other as EncodedVideoFrame
        return isKeyframe == other.isKeyframe &&
                presentationTimestamp == other.presentationTimestamp &&
                data.contentEquals(other.data)
    }

    override fun hashCode(): Int {
        var result = data.contentHashCode()
        result = 31 * result + presentationTimestamp.hashCode()
        result = 31 * result + isKeyframe.hashCode()
        return result
    }

    override fun toString(): String =
        "EncodedVideoFrame(size=${data.size}, pts=${presentationTimestamp.ms}ms, keyframe=$isKeyframe)"
}
