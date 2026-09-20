package com.opendisplay.usb.audio

import java.nio.ByteBuffer

data class EncodedAudioFrame(
    val data: ByteBuffer,
    val pts: Long
)
