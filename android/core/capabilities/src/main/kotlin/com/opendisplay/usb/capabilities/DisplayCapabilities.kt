package com.opendisplay.usb.capabilities

data class DisplayCapabilities(
    val physicalWidth: Int,
    val physicalHeight: Int,
    val refreshRate: Float,
    val densityDpi: Int,
    val supportedRefreshRates: List<Float> = listOf(refreshRate)
)
