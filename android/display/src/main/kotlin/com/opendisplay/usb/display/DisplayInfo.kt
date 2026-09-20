package com.opendisplay.usb.display

/**
 * Validated display configuration active on the device.
 */
data class DisplayInfo(
    val widthPx: Int,
    val heightPx: Int,
    val frameRateHz: Float,
    val orientation: Int = 0,
    val pixelFormat: String = "RGBA_8888",
    val scalingMode: ScalingMode = ScalingMode.FIT,
    val densityDpi: Int = 240
) {
    // Convenient aliases
    val width: Int get() = widthPx
    val height: Int get() = heightPx
    val refreshRate: Float get() = frameRateHz
    val dpi: Int get() = densityDpi
}
