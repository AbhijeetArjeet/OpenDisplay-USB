package com.opendisplay.usb.timing

/**
 * Interface for providing monotonic timestamps.
 * Pure Kotlin/JVM, no Android SDK dependency.
 */
interface MonotonicClock {
    fun nowNanos(): Long
    fun nanoTime(): Long = nowNanos()
}

object SystemMonotonicClock : MonotonicClock {
    override fun nowNanos(): Long = System.nanoTime()
    override fun nanoTime(): Long = System.nanoTime()
}
