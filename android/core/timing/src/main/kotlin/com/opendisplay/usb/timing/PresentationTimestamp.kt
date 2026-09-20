package com.opendisplay.usb.timing

/**
 * High-resolution presentation timestamp for video frames.
 * Encapsulates nanoseconds and provides microsecond/millisecond accessors.
 */
data class PresentationTimestamp(val ptsNanos: Long) {
    val us: Long get() = ptsNanos / 1_000L
    val ms: Long get() = ptsNanos / 1_000_000L
    val seconds: Double get() = ptsNanos / 1_000_000_000.0

    operator fun plus(other: PresentationTimestamp): PresentationTimestamp =
        PresentationTimestamp(ptsNanos + other.ptsNanos)

    operator fun minus(other: PresentationTimestamp): PresentationTimestamp =
        PresentationTimestamp(ptsNanos - other.ptsNanos)

    companion object {
        val ZERO = PresentationTimestamp(0L)

        fun fromMicros(us: Long): PresentationTimestamp =
            PresentationTimestamp(us * 1_000L)

        fun fromMillis(ms: Long): PresentationTimestamp =
            PresentationTimestamp(ms * 1_000_000L)
    }
}
