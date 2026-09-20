package com.opendisplay.usb.audio

class AudioClock {
    private var baseTime: Long = 0
    private var sampleCount: Long = 0
    
    fun reset(time: Long) {
        baseTime = time
        sampleCount = 0
    }
    
    fun addSamples(samples: Int) {
        sampleCount += samples
    }
    
    fun getCurrentAudioTime(sampleRate: Int): Long {
        return baseTime + (sampleCount * 1_000_000L / sampleRate)
    }
}
