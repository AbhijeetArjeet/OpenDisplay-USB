package com.opendisplay.usb.capabilities

import android.media.MediaCodecInfo
import android.os.Build
import android.util.Log

/**
 * Universal platform compatibility and capability isolation layer.
 *
 * Design Rule:
 * The core OpenDisplay protocol and rendering pipeline MUST NOT contain manufacturer
 * or model string checks (e.g., no "if (Build.MANUFACTURER == ...)").
 *
 * Any platform-specific workaround necessitated by hardware or driver defects
 * is strictly isolated within this provider and queried via capability flags.
 */
object DeviceCompatibilityProvider {

    private const val TAG = "CompatibilityProvider"

    /**
     * Determines whether a given decoder is excluded from general video rendering
     * (e.g., DRM-only / Widevine secure decoders that fail on normal SurfaceView).
     */
    fun isDecoderExcluded(codecName: String): Boolean {
        val lower = codecName.lowercase()
        return lower.contains(".secure") || lower.contains("drm")
    }

    /**
     * Recommends optimal initial queue capacity based on API level and hardware profile.
     * Universal guideline: low-latency interactive display prefers 2–4 frames buffer.
     */
    fun getRecommendedQueueCapacity(): Int {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            2 // Modern low-latency capable
        } else {
            3 // Older devices need 1 frame extra safety margin
        }
    }

    /**
     * Checks if low-latency mode should be requested for a given decoder.
     * Safely queries CodecCapabilities.FEATURE_LowLatency on API 30+ without crashing.
     */
    fun isLowLatencySupported(info: MediaCodecInfo, mimeType: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return false
        return try {
            val caps = info.getCapabilitiesForType(mimeType)
            caps.isFeatureSupported(MediaCodecInfo.CodecCapabilities.FEATURE_LowLatency)
        } catch (e: Exception) {
            Log.d(TAG, "FEATURE_LowLatency query failed for ${info.name}: ${e.message}")
            false
        }
    }
}
