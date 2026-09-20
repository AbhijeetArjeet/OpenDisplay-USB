package com.opendisplay.usb.video

import android.media.MediaCodecInfo
import android.media.MediaCodecInfo.CodecCapabilities
import android.media.MediaCodecList
import android.os.Build
import android.util.Log

private const val TAG = "CodecSelector"

/**
 * Selects the best available hardware video decoder for a given MIME type.
 *
 * Selection strategy (in priority order):
 *   1. Hardware-accelerated decoders (non-"google", non-"sw" in name; or API 29+ flag)
 *   2. Software decoders as a last resort
 *
 * Hardware preference is important for:
 *   - Power efficiency (hardware decoder draws far less battery than software)
 *   - Performance (hardware decoder runs in parallel with the CPU)
 *   - Thermal headroom (software H.264 decode at 60fps causes device throttling)
 */
object CodecSelector {

    /**
     * Finds the name of the best available decoder for [mimeType].
     *
     * Returns the codec name (e.g., "OMX.qcom.video.decoder.avc") to use with
     * [android.media.MediaCodec.createByCodecName], or null if no decoder is available.
     *
     * Prefers hardware-accelerated decoders over software decoders.
     */
    fun findBestDecoder(mimeType: String): String? {
        return getPrioritizedDecoders(mimeType).firstOrNull()
    }

    /**
     * Returns candidate decoder names for [mimeType] in priority order (hardware first, software fallback).
     * Excludes secure decoders which require DRM.
     */
    fun getPrioritizedDecoders(mimeType: String): List<String> {
        val codecList = MediaCodecList(MediaCodecList.ALL_CODECS)
        val candidates = mutableListOf<MediaCodecInfo>()

        for (info in codecList.codecInfos) {
            if (info.isEncoder) continue
            if (info.name.contains(".secure", ignoreCase = true)) continue
            if (!info.supportedTypes.any { it.equals(mimeType, ignoreCase = true) }) continue
            candidates.add(info)
        }

        if (candidates.isEmpty()) {
            Log.w(TAG, "No decoder found for MIME type: $mimeType")
            return emptyList()
        }

        // Sort: hardware-accelerated first
        val sorted = candidates.sortedByDescending { info ->
            when {
                isHardwareAccelerated(info) -> 2
                else -> 1
            }
        }

        return sorted.map { it.name }
    }

    /**
     * Returns true if [info] represents a hardware-accelerated decoder.
     *
     * On API 29+: uses [MediaCodecInfo.isHardwareAccelerated].
     * On older APIs: uses name heuristics (hardware decoders typically don't contain
     * "google", "sw", "software", or "ffmpeg" in their name).
     */
    fun isHardwareAccelerated(info: MediaCodecInfo): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            info.isHardwareAccelerated
        } else {
            val name = info.name.lowercase()
            !name.contains("google") &&
            !name.contains(".sw.") &&
            !name.contains("software") &&
            !name.contains("ffmpeg")
        }
    }

    /**
     * Returns true if the named decoder supports the low-latency feature for [mimeType].
     * Low-latency mode (API 30+) reduces frame buffering inside the decoder pipeline.
     *
     * On API < 30, this always returns false (feature not available).
     */
    fun supportsLowLatency(decoderName: String, mimeType: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false
        return runCatching {
            val codecList = MediaCodecList(MediaCodecList.ALL_CODECS)
            val info = codecList.codecInfos.find { it.name == decoderName } ?: return false
            val caps: CodecCapabilities = info.getCapabilitiesForType(mimeType)
            caps.isFeatureSupported(CodecCapabilities.FEATURE_LowLatency)
        }.getOrDefault(false)
    }

    /**
     * Returns all available decoders for [mimeType] as a list of names.
     * Useful for diagnostics and capability reporting.
     */
    fun listDecoders(mimeType: String): List<String> {
        val codecList = MediaCodecList(MediaCodecList.ALL_CODECS)
        return codecList.codecInfos
            .filter { !it.isEncoder }
            .filter { info -> info.supportedTypes.any { it.equals(mimeType, ignoreCase = true) } }
            .map { it.name }
    }
}
