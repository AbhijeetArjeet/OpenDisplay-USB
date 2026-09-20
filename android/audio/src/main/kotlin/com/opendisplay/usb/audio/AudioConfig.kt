package com.opendisplay.usb.audio

data class AudioConfig(
    val sampleRate: Int,
    val mode: AudioMode,
    val bitDepth: Int = 16
)
