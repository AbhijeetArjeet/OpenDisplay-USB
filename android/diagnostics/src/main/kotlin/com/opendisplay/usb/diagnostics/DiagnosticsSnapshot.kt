package com.opendisplay.usb.diagnostics

/**
 * A point-in-time snapshot of all observable diagnostic metrics.
 *
 * Emitted by [DiagnosticsCollector] on a 500ms cadence.
 * Safe to read from any thread (immutable data class).
 */
data class DiagnosticsSnapshot(
    /** Frames per second over the last 1-second rolling window. */
    val fps: Float,
    /** Total frames decoded successfully since session start. */
    val decodedFrames: Long,
    /** Total frames dropped (frame queue full) since session start. */
    val droppedFrames: Long,
    /** Total decode errors since session start. */
    val decodeErrors: Long,
    /** Average decode latency in milliseconds (from queue to Surface). */
    val decodeLatencyMs: Float,
    /** Current video width in pixels. */
    val currentWidthPx: Int,
    /** Current video height in pixels. */
    val currentHeightPx: Int,
    /** Current codec name (e.g. "H264", "HEVC"). */
    val currentCodec: String,
    /** Current video bitrate estimate in Kbps. */
    val bitrateKbps: Float,
    /** Transport throughput in Kbps (all packet types). */
    val transportThroughputKbps: Float,
    /** Current audio buffer depth in milliseconds. */
    val audioBufferMs: Float,
    /** Estimated audio output latency in milliseconds. */
    val audioLatencyMs: Float,
    /** Estimated audio/video drift in milliseconds (+= audio ahead, -= audio behind). */
    val avDriftMs: Float,
    /** Number of transport reconnections since app start. */
    val reconnectCount: Int,
    /** Monotonic timestamp (System.nanoTime() / 1_000_000) when snapshot was taken. */
    val timestampMs: Long
) {
    companion object {
        val EMPTY = DiagnosticsSnapshot(
            fps = 0f,
            decodedFrames = 0L,
            droppedFrames = 0L,
            decodeErrors = 0L,
            decodeLatencyMs = 0f,
            currentWidthPx = 0,
            currentHeightPx = 0,
            currentCodec = "none",
            bitrateKbps = 0f,
            transportThroughputKbps = 0f,
            audioBufferMs = 0f,
            audioLatencyMs = 0f,
            avDriftMs = 0f,
            reconnectCount = 0,
            timestampMs = 0L
        )
    }
}
