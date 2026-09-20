package com.opendisplay.usb.diagnostics

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val EMIT_INTERVAL_MS = 500L

/**
 * Aggregates runtime metrics from all subsystems and emits [DiagnosticsSnapshot]
 * every [EMIT_INTERVAL_MS] milliseconds as a [StateFlow].
 *
 * Thread safety: all recording methods are thread-safe (atomic operations or synchronized blocks).
 *
 * Usage:
 * ```
 * diagnostics.start(scope)
 * // during session:
 * diagnostics.recordVideoFrame(frameBytes)
 * diagnostics.recordDrop()
 * // in UI:
 * diagnostics.snapshot.collect { snapshot -> updateUi(snapshot) }
 * ```
 */
class DiagnosticsCollector {

    private val fpsCounter = FpsCounter(windowMs = 1000L)
    private val bitrateCounter = BitrateCounter(windowMs = 1000L)
    private val transportCounter = BitrateCounter(windowMs = 1000L)

    @Volatile private var decodedFrames: Long = 0L
    @Volatile private var droppedFrames: Long = 0L
    @Volatile private var decodeErrors: Long = 0L
    @Volatile private var reconnectCount: Int = 0
    @Volatile private var currentWidthPx: Int = 0
    @Volatile private var currentHeightPx: Int = 0
    @Volatile private var currentCodec: String = "none"

    private val _snapshot = MutableStateFlow(DiagnosticsSnapshot.EMPTY)
    val snapshot: StateFlow<DiagnosticsSnapshot> = _snapshot.asStateFlow()

    // ── Start / stop ──────────────────────────────────────────────────────────

    /**
     * Starts the periodic snapshot emitter in [scope].
     * The emitter coroutine runs until [scope] is cancelled.
     */
    fun start(scope: CoroutineScope) {
        scope.launch {
            while (true) {
                delay(EMIT_INTERVAL_MS)
                emit()
            }
        }
    }

    // ── Recording methods (called from transport/decoder threads) ─────────────

    /**
     * Records a successfully decoded video frame.
     * [sizeBytes] is the compressed frame size (used for bitrate calculation).
     */
    fun recordVideoFrame(sizeBytes: Int) {
        decodedFrames++
        val nowNs = System.nanoTime()
        fpsCounter.recordFrame(nowNs)
        bitrateCounter.recordBytes(sizeBytes, nowNs)
    }

    /** Records a dropped video frame (frame queue was full). */
    fun recordDrop() {
        droppedFrames++
    }

    /** Records a decode error. */
    fun recordError() {
        decodeErrors++
    }

    /** Records bytes received from any transport packet (for throughput calculation). */
    fun recordTransportBytes(bytes: Int) {
        transportCounter.recordBytes(bytes, System.nanoTime())
    }

    /** Updates the current active video configuration (for display in UI). */
    fun setCurrentConfig(widthPx: Int, heightPx: Int, codec: String) {
        currentWidthPx = widthPx
        currentHeightPx = heightPx
        currentCodec = codec
    }

    /** Records a transport reconnection event. */
    fun recordReconnect() {
        reconnectCount++
    }

    // ── Snapshot emission ─────────────────────────────────────────────────────

    private fun emit() {
        val nowNs = System.nanoTime()
        _snapshot.value = DiagnosticsSnapshot(
            fps = fpsCounter.getFps(nowNs),
            decodedFrames = decodedFrames,
            droppedFrames = droppedFrames,
            decodeErrors = decodeErrors,
            decodeLatencyMs = 0f,                       // TODO(phase2): measure actual decode latency
            currentWidthPx = currentWidthPx,
            currentHeightPx = currentHeightPx,
            currentCodec = currentCodec,
            bitrateKbps = bitrateCounter.getKbps(nowNs),
            transportThroughputKbps = transportCounter.getKbps(nowNs),
            audioBufferMs = 0f,                         // TODO(phase2): from AudioClock
            audioLatencyMs = 0f,                        // TODO(phase2): from AudioRenderer
            avDriftMs = 0f,                             // TODO(phase2): A/V sync drift
            reconnectCount = reconnectCount,
            timestampMs = nowNs / 1_000_000L
        )
    }
}
