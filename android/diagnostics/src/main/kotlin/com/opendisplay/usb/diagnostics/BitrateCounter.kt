package com.opendisplay.usb.diagnostics

/**
 * Computes bitrate in Kbps over a rolling time window using monotonic nanoseconds.
 *
 * Thread safety: NOT thread-safe. External synchronization required if called from multiple threads.
 *
 * @param windowMs  rolling window size in milliseconds (default: 1000ms = 1 second)
 */
class BitrateCounter(private val windowMs: Long = 1000L) {

    private val windowNs: Long = windowMs * 1_000_000L

    /** Each entry: (timestampNs, byteCount) */
    private val records = ArrayDeque<Pair<Long, Int>>()

    /**
     * Records [bytes] received at [nowNs] (monotonic nanoseconds).
     */
    @Synchronized
    fun recordBytes(bytes: Int, nowNs: Long = System.nanoTime()) {
        records.addLast(Pair(nowNs, bytes))
        evict(nowNs)
    }

    /**
     * Returns the current throughput in Kbps over the rolling window.
     * Returns 0.0 if no data has been recorded recently.
     */
    @Synchronized
    fun getKbps(nowNs: Long = System.nanoTime()): Float {
        evict(nowNs)
        if (records.isEmpty()) return 0f

        val totalBytes = records.sumOf { it.second.toLong() }
        val firstRecord = records.firstOrNull() ?: return 0f
        val windowDurationMs = windowMs.coerceAtMost((nowNs - firstRecord.first) / 1_000_000L)
        if (windowDurationMs <= 0L) return 0f

        // Kbps = (totalBytes * 8 bits) / (windowDurationMs / 1000 seconds) / 1000
        return (totalBytes * 8L * 1000L / windowDurationMs / 1000f)
    }

    /** Clears all recorded data. */
    @Synchronized
    fun reset() {
        records.clear()
    }

    private fun evict(nowNs: Long) {
        val cutoffNs = nowNs - windowNs
        while (records.isNotEmpty()) {
            val first = records.firstOrNull() ?: break
            if (first.first >= cutoffNs) break
            records.removeFirstOrNull()
        }
    }
}
