package com.opendisplay.usb.timing

import kotlin.math.sqrt

/**
 * Clock synchronization, jitter, and round-trip latency tracking between Android and Windows host.
 *
 * Uses PING / PONG timestamps to track:
 * - Round-trip time (RTT)
 * - Jitter (standard deviation of RTT)
 * - One-way network latency estimate
 * - Clock drift / offset between host and device
 */
class ClockSync(
    private val clock: MonotonicClock = SystemMonotonicClock,
    private val historySize: Int = 20
) {

    private val rttHistory = mutableListOf<Float>()
    private val offsetHistory = mutableListOf<Long>()

    /** Current estimated clock offset between device and host in nanoseconds (device - host). */
    var offsetNanos: Long = 0L
        private set

    /** Latest round-trip latency in milliseconds. */
    var roundTripLatencyMs: Float = 0f
        private set

    /** Median round-trip latency across the history window. */
    var medianRttMs: Float = 0f
        private set

    /** Jitter of round-trip latency across the history window in milliseconds. */
    var rttJitterMs: Float = 0f
        private set

    /** Estimated one-way latency in milliseconds (median RTT / 2). */
    val estimatedLatencyMs: Float get() = medianRttMs / 2f

    /** Records the timestamp when a PING is sent. Returns the timestamp sent. */
    fun onPingSent(): Long {
        return clock.nowNanos()
    }

    /**
     * Called when a PONG is received matching an earlier PING.
     *
     * @param pingSendTimestampNs the original timestamp embedded in the PING and echoed by PONG
     * @param hostReceiveTimestampNs optional host timestamp from PONG
     */
    fun onPongReceived(pingSendTimestampNs: Long, hostReceiveTimestampNs: Long? = null) {
        val nowNs = clock.nowNanos()
        val rttNs = (nowNs - pingSendTimestampNs).coerceAtLeast(0L)
        val rttMs = rttNs / 1_000_000f
        roundTripLatencyMs = rttMs

        synchronized(rttHistory) {
            rttHistory.add(rttMs)
            if (rttHistory.size > historySize) rttHistory.removeAt(0)

            val sorted = rttHistory.sorted()
            medianRttMs = sorted[sorted.size / 2]

            if (rttHistory.size > 1) {
                val mean = rttHistory.average()
                val variance = rttHistory.sumOf { (it - mean) * (it - mean) } / rttHistory.size
                rttJitterMs = sqrt(variance).toFloat()
            } else {
                rttJitterMs = 0f
            }
        }

        if (hostReceiveTimestampNs != null) {
            val oneWayNs = (medianRttMs * 1_000_000 / 2).toLong()
            val calculatedOffset = nowNs - (hostReceiveTimestampNs + oneWayNs)

            synchronized(offsetHistory) {
                offsetHistory.add(calculatedOffset)
                if (offsetHistory.size > historySize) offsetHistory.removeAt(0)
                val sortedOffsets = offsetHistory.sorted()
                offsetNanos = sortedOffsets[sortedOffsets.size / 2]
            }
        }
    }

    fun updateOffset(hostNanos: Long, deviceNanos: Long) {
        offsetNanos = deviceNanos - hostNanos
    }

    fun hostToDevice(hostNanos: Long): Long {
        return hostNanos + offsetNanos
    }

    fun deviceToHost(deviceNanos: Long): Long {
        return deviceNanos - offsetNanos
    }
}
