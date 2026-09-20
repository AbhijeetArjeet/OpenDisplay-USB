package com.opendisplay.usb.video

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import android.util.Log
import android.view.Surface
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val TAG = "VideoDecoder"

/** Timeout for dequeueInputBuffer: 10ms (keeps the decode loop responsive) */
private const val DEQUEUE_TIMEOUT_US = 10_000L

/**
 * MediaCodec-based hardware-accelerated video decoder.
 *
 * Lifecycle:
 *   configure(config, surface) → start() → startDecoding(queue, scope) → stop() → [reconfigure]
 *                                                                        └→ release()
 *
 * The decoder operates in synchronous mode (dequeueInputBuffer / dequeueOutputBuffer) on a
 * dedicated coroutine dispatched to [Dispatchers.Default] to avoid blocking the main thread.
 *
 * The decoder NEVER knows which transport delivered the data — it only receives
 * [EncodedVideoFrame] objects from a [VideoFrameQueue].
 *
 * Thread safety: [configure], [flush], [stop], [release] MUST be called sequentially
 * (not concurrently). [startDecoding] launches background coroutines.
 */
class VideoDecoder {

    private val _state = MutableStateFlow<DecoderState>(DecoderState.Idle)
    val state: StateFlow<DecoderState> = _state.asStateFlow()

    private var codec: MediaCodec? = null
    private var decodeJob: Job? = null

    // ── Counters ──────────────────────────────────────────────────────────────

    @Volatile var decodedFrameCount: Long = 0L
        private set

    @Volatile var droppedFrameCount: Long = 0L
        private set

    @Volatile var errorCount: Long = 0L
        private set

    @Volatile var lastDecodeLatencyMs: Double = 0.0
        private set

    @Volatile var lastRenderLatencyMs: Double = 0.0
        private set

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    /**
     * Configures the MediaCodec decoder for [config] and attaches it to [surface].
     *
     * Must be called before [start]. Safe to call after [stop] to reconfigure
     * (e.g., after a resolution change).
     *
     * @return [Result.success] on success, [Result.failure] if no suitable decoder was found
     *         or codec configuration failed.
     */
    suspend fun configure(config: VideoConfig, surface: Surface): Result<Unit> =
        withContext(Dispatchers.Default) {
            runCatching {
                // Release any existing codec
                codec?.apply { stop(); release() }
                codec = null

                val decoders = CodecSelector.getPrioritizedDecoders(config.codecMimeType)
                if (decoders.isEmpty()) {
                    throw IllegalStateException("No decoder found for MIME type: ${config.codecMimeType}")
                }

                var configuredCodec: MediaCodec? = null
                var lastException: Throwable? = null

                for (decoderName in decoders) {
                    val canTryLowLatency = Build.VERSION.SDK_INT >= Build.VERSION_CODES.R &&
                            config.lowLatencyMode &&
                            CodecSelector.supportsLowLatency(decoderName, config.codecMimeType)

                    val attempts = if (canTryLowLatency) listOf(true, false) else listOf(false)

                    for (enableLowLatency in attempts) {
                        var candidateCodec: MediaCodec? = null
                        try {
                            val format = MediaFormat.createVideoFormat(
                                config.codecMimeType,
                                config.widthPx,
                                config.heightPx
                            ).apply {
                                setFloat(MediaFormat.KEY_FRAME_RATE, config.frameRateHz)
                                setInteger(MediaFormat.KEY_BIT_RATE, config.bitrateBps)

                                config.csd0?.let { setByteBuffer("csd-0", java.nio.ByteBuffer.wrap(it)) }
                                config.csd1?.let { setByteBuffer("csd-1", java.nio.ByteBuffer.wrap(it)) }

                                if (enableLowLatency && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                                    setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
                                }
                            }

                            Log.i(TAG, "Attempting configuration for $decoderName (${config.widthPx}x${config.heightPx}, lowLatency=$enableLowLatency)")
                            candidateCodec = MediaCodec.createByCodecName(decoderName)
                            candidateCodec.configure(format, surface, null, 0 /* decode */)
                            configuredCodec = candidateCodec
                            Log.i(TAG, "Successfully configured decoder: $decoderName (lowLatency=$enableLowLatency)")
                            break
                        } catch (e: Throwable) {
                            Log.w(TAG, "Failed configuring $decoderName (lowLatency=$enableLowLatency): ${e.message}")
                            candidateCodec?.release()
                            lastException = e
                        }
                    }

                    if (configuredCodec != null) break
                }

                if (configuredCodec == null) {
                    throw lastException ?: IllegalStateException("All decoder candidates failed to configure for ${config.codecMimeType}")
                }

                codec = configuredCodec
                _state.value = DecoderState.Configured(config)
                Unit
            }.onFailure { e ->
                _state.value = DecoderState.Error(e)
                Log.e(TAG, "Failed to configure decoder", e)
            }
        }

    /**
     * Starts the MediaCodec decoder.
     * Must be called after [configure].
     */
    private fun start(config: VideoConfig) {
        val currentCodec = codec ?: return
        currentCodec.start()
        _state.value = DecoderState.Running(config)
        Log.i(TAG, "Decoder started")
    }

    /**
     * Starts consuming frames from [queue] and feeding them to MediaCodec.
     *
     * Launches two coroutines:
     *   1. Input loop: dequeues MediaCodec input buffers and feeds frames from [queue].
     *   2. Output loop: dequeues rendered output buffers and releases them to [surface].
     *
     * Both loops run on [Dispatchers.Default] to avoid blocking the main thread.
     *
     * @param queue  the frame queue to consume
     * @param scope  the coroutine scope controlling the lifecycle of these loops
     */
    fun startDecoding(queue: VideoFrameQueue, scope: CoroutineScope) {
        val config = (_state.value as? DecoderState.Configured)?.config
            ?: run {
                Log.e(TAG, "startDecoding() called in state ${_state.value}, must be Configured")
                return
            }

        start(config)

        decodeJob = scope.launch(Dispatchers.Default) {
            try {
                runDecodeLoop(queue)
            } catch (e: Exception) {
                Log.e(TAG, "Decode loop exited with exception", e)
                errorCount++
                _state.value = DecoderState.Error(e, config)
            }
        }
    }

    /**
     * Main decode loop. Feeds input from [queue] and drains output buffers back to surface.
     * Runs until the queue's flow completes or the coroutine is cancelled.
     */
    private suspend fun runDecodeLoop(queue: VideoFrameQueue) {
        val bufferInfo = MediaCodec.BufferInfo()
        val inputSubmissionTimes = java.util.concurrent.ConcurrentHashMap<Long, Long>()

        queue.consumeAsFlow().collect { frame ->
            val currentCodec = codec ?: return@collect

            // ── Feed input (T7) ───────────────────────────────────────────────
            val inputBufferId = currentCodec.dequeueInputBuffer(DEQUEUE_TIMEOUT_US)
            if (inputBufferId >= 0) {
                val inputBuffer = currentCodec.getInputBuffer(inputBufferId)
                if (inputBuffer != null) {
                    inputBuffer.clear()
                    inputBuffer.put(frame.data)
                    val flags = if (frame.isKeyframe) MediaCodec.BUFFER_FLAG_KEY_FRAME else 0
                    val presentationUs = frame.presentationTimestamp.us
                    inputSubmissionTimes[presentationUs] = System.nanoTime()
                    currentCodec.queueInputBuffer(
                        inputBufferId,
                        0,
                        frame.data.size,
                        presentationUs,
                        flags
                    )
                }
            } else {
                // Input buffer unavailable — drop the frame
                droppedFrameCount++
                Log.w(TAG, "Input buffer unavailable, frame dropped (total dropped: $droppedFrameCount)")
            }

            // ── Drain output (T8 -> T9) ──────────────────────────────────────
            var outputBufferId = currentCodec.dequeueOutputBuffer(bufferInfo, 0)
            while (outputBufferId >= 0) {
                val outputAvailableNs = System.nanoTime()
                val submitNs = inputSubmissionTimes.remove(bufferInfo.presentationTimeUs)
                if (submitNs != null) {
                    lastDecodeLatencyMs = (outputAvailableNs - submitNs) / 1_000_000.0
                }

                // render = true: releases the frame directly to the Surface (T9)
                val renderStartNs = System.nanoTime()
                currentCodec.releaseOutputBuffer(outputBufferId, true)
                lastRenderLatencyMs = (System.nanoTime() - renderStartNs) / 1_000_000.0

                decodedFrameCount++
                outputBufferId = currentCodec.dequeueOutputBuffer(bufferInfo, 0)
            }

            // Handle format change (resolution change mid-stream)
            if (outputBufferId == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                val newFormat = currentCodec.outputFormat
                val newWidth = newFormat.getInteger(MediaFormat.KEY_WIDTH)
                val newHeight = newFormat.getInteger(MediaFormat.KEY_HEIGHT)
                Log.i(TAG, "Output format changed: ${newWidth}x${newHeight}")
                // The SessionManager observes state changes to handle this
            }
        }

        Log.i(TAG, "Decode loop completed. Decoded: $decodedFrameCount, Dropped: $droppedFrameCount")
    }

    /**
     * Dynamically updates the output surface of an active MediaCodec instance (API 23+).
     */
    fun setOutputSurface(surface: Surface): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                codec?.setOutputSurface(surface)
                Log.i(TAG, "MediaCodec output surface dynamically updated")
                true
            } catch (e: Exception) {
                Log.e(TAG, "Failed to set output surface", e)
                false
            }
        } else {
            false
        }
    }

    /**
     * Flushes pending frames from the decoder without stopping it.
     * Call this on STREAM_RESET. The next frame fed after flush MUST be a keyframe.
     */
    suspend fun flush(): Result<Unit> = withContext(Dispatchers.Default) {
        runCatching {
            codec?.flush() ?: throw IllegalStateException("flush() called with no codec")
            Log.i(TAG, "Decoder flushed")
            Unit
        }.onFailure { e ->
            Log.e(TAG, "Flush failed", e)
            errorCount++
        }
    }

    /**
     * Stops the decoder and cancels the decode coroutine.
     * The codec remains allocated; call [configure] to reuse it for a new stream.
     */
    suspend fun stop() {
        decodeJob?.cancel()
        decodeJob = null
        withContext(Dispatchers.Default) {
            try {
                codec?.stop()
                Log.i(TAG, "Decoder stopped")
            } catch (e: Exception) {
                Log.e(TAG, "Error stopping decoder", e)
            }
        }
        val prevState = _state.value
        _state.value = if (prevState is DecoderState.Running) {
            DecoderState.Stopped(prevState.config)
        } else {
            DecoderState.Idle
        }
    }

    /**
     * Releases all MediaCodec resources. Call when the decoder is no longer needed.
     * Safe to call from any state.
     */
    fun release() {
        decodeJob?.cancel()
        decodeJob = null
        try {
            codec?.release()
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing codec", e)
        }
        codec = null
        _state.value = DecoderState.Idle
        Log.i(TAG, "Decoder released")
    }
}
