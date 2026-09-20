package com.opendisplay.usb.video

/**
 * State machine for the [VideoDecoder].
 *
 * Valid transitions:
 *
 *   Idle ──► Configured ──► Running ──► Stopped ──► (re-configure)
 *              │                │
 *              └───────────────►└──► Error ──► Idle (after release)
 *
 * The decoder MUST NOT be used to feed frames while in any state other than [Running].
 */
sealed class DecoderState {

    /** Initial state. No MediaCodec instance exists. */
    object Idle : DecoderState()

    /**
     * MediaCodec has been created and configured but not yet started.
     * CSD (SPS/PPS) has been provided via MediaFormat.
     */
    data class Configured(val config: VideoConfig) : DecoderState()

    /**
     * MediaCodec is running. Frames can be fed via the frame queue.
     */
    data class Running(val config: VideoConfig) : DecoderState()

    /**
     * MediaCodec has been stopped (codec.stop() called).
     * Can be re-configured and restarted after a stream reset.
     */
    data class Stopped(val config: VideoConfig) : DecoderState()

    /**
     * An unrecoverable error occurred. The caller must call [VideoDecoder.release]
     * to return to [Idle].
     */
    data class Error(val cause: Throwable, val config: VideoConfig? = null) : DecoderState()
}
