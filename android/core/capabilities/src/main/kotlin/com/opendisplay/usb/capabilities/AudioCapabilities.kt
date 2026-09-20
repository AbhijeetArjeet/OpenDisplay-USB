package com.opendisplay.usb.capabilities

data class AudioCapabilities(
    val supportedCodecs: List<AudioCodec>,
    val maxChannels: Int,
    val maxSampleRate: Int
)
