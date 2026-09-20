package com.opendisplay.usb.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import java.nio.ByteBuffer

class AudioRenderer(config: AudioConfig) {
    private var audioTrack: AudioTrack? = null
    
    init {
        val channelConfig = if (config.mode == AudioMode.STEREO) {
            AudioFormat.CHANNEL_OUT_STEREO
        } else {
            AudioFormat.CHANNEL_OUT_MONO
        }
        
        val minBufferSize = AudioTrack.getMinBufferSize(
            config.sampleRate,
            channelConfig,
            AudioFormat.ENCODING_PCM_16BIT
        )
        
        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build())
            .setAudioFormat(AudioFormat.Builder()
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setSampleRate(config.sampleRate)
                .setChannelMask(channelConfig)
                .build())
            .setBufferSizeInBytes(minBufferSize)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
    }

    fun play() {
        audioTrack?.play()
    }

    fun write(data: ByteBuffer, size: Int) {
        audioTrack?.write(data, size, AudioTrack.WRITE_BLOCKING)
    }

    fun write(data: ByteArray, offset: Int, size: Int) {
        audioTrack?.write(data, offset, size, AudioTrack.WRITE_NON_BLOCKING)
    }
    
    fun stop() {
        audioTrack?.stop()
    }
    
    fun release() {
        audioTrack?.release()
        audioTrack = null
    }
}
