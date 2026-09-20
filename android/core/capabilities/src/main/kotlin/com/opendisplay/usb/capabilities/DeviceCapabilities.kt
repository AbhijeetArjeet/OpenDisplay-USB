package com.opendisplay.usb.capabilities

data class DeviceCapabilities(
    val deviceInfo: DeviceInfo,
    val display: DisplayCapabilities,
    val video: VideoCapabilities,
    val audio: AudioCapabilities,
    val input: InputCapabilities
)
