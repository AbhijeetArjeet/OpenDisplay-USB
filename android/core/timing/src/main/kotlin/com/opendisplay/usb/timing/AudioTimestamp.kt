package com.opendisplay.usb.timing

/**
 * High-resolution presentation timestamp for audio packets.
 */
data class AudioTimestamp(val ptsNanos: Long) {
    val us: Long get() = ptsNanos / 1_000L
    val ms: Long get() = ptsNanos / 1_000_000L
    val seconds: Double get() = ptsNanos / 1_000_000_000.0

    operator fun plus(other: AudioTimestamp): AudioTimestamp =
        AudioTimestamp(ptsNanos + other.ptsNanos)

    operator fun minus(other: AudioTimestamp): AudioTimestamp =
        AudioTimestamp(ptsNanos - other.ptsNanos)

    companion object {
        val ZERO = AudioTimestamp(0L)

        fun fromMicros(us: Long): AudioTimestamp =
            AudioTimestamp(us * 1_000L)

        fun fromMillis(ms: Long): AudioTimestamp =
            AudioTimestamp(ms * 1_000_000L)
    }
}
