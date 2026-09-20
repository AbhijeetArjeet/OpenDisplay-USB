package com.opendisplay.usb.diagnostics

/**
 * Computes frames per second over a rolling time window using monotonic nanoseconds.
 *
 * Thread safety: NOT thread-safe. External synchronization required if called from multiple threads.
 * In [DiagnosticsCollector], all calls are from a single coroutine.
 *
 * @param windowMs  rolling window size in milliseconds (default: 1000ms = 1 second)
 */
class FpsCounter(private val windowMs: Long = 1000L) {

    private val windowNs: Long = windowMs * 1_000_000L
    private val frameTimestamps = ArrayDeque<Long>()  // nanoseconds

    /**
     * Records a decoded frame at [nowNs] (monotonic nanoseconds from [System.nanoTime]).
     */
    @Synchronized
    fun recordFrame(nowNs: Long = System.nanoTime()) {
        frameTimestamps.addLast(nowNs)
        evict(nowNs)
    }

    /**
     * Returns the current FPS over the rolling window.
     * Returns 0.0 if no frames have been recorded recently.
     */
    @Synchronized
    fun getFps(nowNs: Long = System.nanoTime()): Float {
        evict(nowNs)
        if (frameTimestamps.size <= 1) return 0f

        val firstTs = frameTimestamps.firstOrNull() ?: return 0f
        val windowDurationNs = nowNs - firstTs
        if (windowDurationNs <= 0L) return 0f
        return (frameTimestamps.size - 1).toFloat() / (windowDurationNs / 1_000_000_000f)
    }

    /** Clears all recorded frames. */
    @Synchronized
    fun reset() {
        frameTimestamps.clear()
    }

    private fun evict(nowNs: Long) {
        val cutoffNs = nowNs - windowNs
        while (frameTimestamps.isNotEmpty()) {
            val first = frameTimestamps.firstOrNull() ?: break
            if (first >= cutoffNs) break
            frameTimestamps.removeFirstOrNull()
        }
    }
}
