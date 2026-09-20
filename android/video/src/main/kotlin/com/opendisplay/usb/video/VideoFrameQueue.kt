package com.opendisplay.usb.video

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

/**
 * Thread-safe queue of [EncodedVideoFrame] objects used between the transport/protocol layer
 * and the [VideoDecoder].
 *
 * Exposes atomic [queueDepth], configurable [capacity], and smart drop of non-keyframes
 * when queue depth exceeds the target limit to prevent latency build-up.
 */
class VideoFrameQueue(capacity: Int = 16) {

    @Volatile
    var capacity: Int = capacity

    private val channel = Channel<EncodedVideoFrame>(Channel.UNLIMITED)
    private val _queueDepth = AtomicInteger(0)
    val queueDepth: Int get() = _queueDepth.get()

    private val _droppedFrameCount = AtomicLong(0L)
    val droppedFrameCount: Long get() = _droppedFrameCount.get()

    /**
     * Enqueues a frame. If the queue is at capacity, non-keyframes are dropped immediately.
     * Keyframes are preserved to ensure stream recovery.
     * Returns true if enqueued, false if dropped.
     */
    fun enqueue(frame: EncodedVideoFrame): Boolean {
        if (_queueDepth.get() >= capacity && !frame.isKeyframe) {
            _droppedFrameCount.incrementAndGet()
            return false
        }
        _queueDepth.incrementAndGet()
        channel.trySend(frame)
        return true
    }

    /**
     * Suspending enqueue with smart drop behavior for non-keyframes.
     */
    suspend fun enqueueBlocking(frame: EncodedVideoFrame) {
        if (_queueDepth.get() >= capacity && !frame.isKeyframe) {
            _droppedFrameCount.incrementAndGet()
            return
        }
        _queueDepth.incrementAndGet()
        channel.send(frame)
    }

    /**
     * Returns a [Flow] that emits frames as they are enqueued and decrements [queueDepth].
     */
    fun consumeAsFlow(): Flow<EncodedVideoFrame> = flow {
        for (frame in channel) {
            _queueDepth.decrementAndGet()
            emit(frame)
        }
    }

    /**
     * Discards all frames currently in the queue.
     * Call this on STREAM_RESET before re-starting the decoder.
     */
    fun clear() {
        while (channel.tryReceive().isSuccess) {
            _queueDepth.decrementAndGet()
        }
        _queueDepth.set(0)
    }

    /** Closes the queue. [consumeAsFlow] will complete after all queued frames are consumed. */
    fun close() {
        channel.close()
    }
}
