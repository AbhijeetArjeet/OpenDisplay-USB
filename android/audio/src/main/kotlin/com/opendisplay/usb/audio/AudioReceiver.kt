package com.opendisplay.usb.audio

import kotlinx.coroutines.channels.Channel

class AudioReceiver(capacity: Int = Channel.UNLIMITED) {
    private val channel = Channel<EncodedAudioFrame>(capacity)

    suspend fun receive(frame: EncodedAudioFrame) {
        channel.send(frame)
    }

    suspend fun getNextFrame(): EncodedAudioFrame {
        return channel.receive()
    }
}
