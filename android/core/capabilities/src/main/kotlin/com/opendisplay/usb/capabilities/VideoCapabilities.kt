package com.opendisplay.usb.capabilities

data class VideoCapabilities(
    val supportedCodecs: List<VideoCodec>,
    val maxResolutionWidth: Int,
    val maxResolutionHeight: Int,
    val maxFps: Int
)
