package com.opendisplay.usb

import android.util.Base64
import android.util.Log
import android.view.Surface
import com.opendisplay.usb.audio.AudioConfig
import com.opendisplay.usb.audio.AudioMode
import com.opendisplay.usb.audio.AudioReceiver
import com.opendisplay.usb.audio.AudioRenderer
import com.opendisplay.usb.capabilities.CapabilityDetector
import com.opendisplay.usb.capabilities.VideoCodec
import com.opendisplay.usb.diagnostics.DiagnosticsCollector
import com.opendisplay.usb.display.DisplayConfigurator
import com.opendisplay.usb.protocol.ClipboardEventMessage
import com.opendisplay.usb.protocol.ErrorCode
import com.opendisplay.usb.protocol.ErrorMessage
import com.opendisplay.usb.protocol.InputEventMessage
import com.opendisplay.usb.protocol.JsonCodec
import com.opendisplay.usb.protocol.MessageType
import com.opendisplay.usb.protocol.PacketCodec
import com.opendisplay.usb.protocol.PingMessage
import com.opendisplay.usb.protocol.PongMessage
import com.opendisplay.usb.protocol.ProtocolVersion
import com.opendisplay.usb.timing.ClockSync
import com.opendisplay.usb.timing.PresentationTimestamp
import com.opendisplay.usb.timing.SystemMonotonicClock
import com.opendisplay.usb.transport.Transport
import com.opendisplay.usb.ui.SessionUiState
import com.opendisplay.usb.video.EncodedVideoFrame
import com.opendisplay.usb.video.VideoCodecMime
import com.opendisplay.usb.video.VideoConfig
import com.opendisplay.usb.video.VideoDecoder
import com.opendisplay.usb.video.VideoFrameQueue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "ProtocolController"

/** How often to send a PING to measure round-trip latency */
private const val PING_INTERVAL_MS = 5_000L

/**
 * Protocol state machine for an OpenDisplay USB session.
 *
 * State machine:
 *
 *   IDLE
 *    └─► HELLO_SENT         (after sending HELLO)
 *         └─► CAPABILITIES_SENT (after receiving HELLO_ACK and sending CAPABILITIES)
 *              └─► CONFIGURING   (after receiving CAPABILITIES_ACK; waiting for DISPLAY_CONFIG + VIDEO_CONFIG)
 *                   └─► STREAMING (after VIDEO_CONFIG_ACK sent; actively receiving VIDEO_FRAME)
 *
 *   Any state → ERROR on protocol violation or transport failure
 *   Any state → DISCONNECTED on receiving DISCONNECT or user request
 *
 * This class owns the receive loop and dispatches every incoming packet to the
 * appropriate handler. Unknown message types are logged and discarded — the
 * controller MUST NOT disconnect on unknown types (forward-compatibility rule).
 */
class ProtocolController(
    private val transport: Transport,
    private val videoDecoder: VideoDecoder,
    private val videoFrameQueue: VideoFrameQueue,
    private val audioReceiver: AudioReceiver,
    private val displayConfigurator: DisplayConfigurator,
    private val diagnostics: DiagnosticsCollector,
    private val surfaceProvider: () -> Surface? = { null },
    private val capabilityDetector: CapabilityDetector? = null,
    private val onClipboardReceived: ((String) -> Unit)? = null,
    private val onUiUpdate: (SessionUiState) -> Unit
) {
    enum class ProtocolState {
        IDLE, HELLO_SENT, CAPABILITIES_SENT, CONFIGURING, STREAMING, ERROR, DISCONNECTED
    }

    enum class ExitReason {
        USER_DISCONNECT, TRANSPORT_ERROR, PROTOCOL_ERROR, STREAM_COMPLETE
    }

    private val _protocolState = MutableStateFlow(ProtocolState.IDLE)
    val protocolState: StateFlow<ProtocolState> = _protocolState.asStateFlow()

    private val clockSync = ClockSync(SystemMonotonicClock)
    private var pingJob: Job? = null
    private var audioRenderer: AudioRenderer? = null
    private var stopped = false

    // ── Public API ─────────────────────────────────────────────────────────────

    /**
     * Runs the protocol state machine until the session ends.
     * This is a suspending function that returns when the session is over.
     *
     * @return the reason the controller exited
     */
    suspend fun run(scope: CoroutineScope): ExitReason {
        stopped = false

        return try {
            // Step 1: Send HELLO
            sendHello()
            _protocolState.value = ProtocolState.HELLO_SENT
            Log.i(TAG, "HELLO sent")

            // Step 2: Drive the receive loop
            runReceiveLoop(scope)
        } catch (e: Exception) {
            Log.e(TAG, "Protocol controller exiting with exception", e)
            _protocolState.value = ProtocolState.ERROR
            ExitReason.TRANSPORT_ERROR
        } finally {
            pingJob?.cancel()
            audioRenderer?.stop()
            audioRenderer?.release()
            audioRenderer = null
        }
    }

    /** Requests a clean stop. The receive loop will exit after current packet processing. */
    fun stop() {
        stopped = true
        pingJob?.cancel()
        audioRenderer?.stop()
        audioRenderer?.release()
        audioRenderer = null
    }

    // ── Protocol steps ────────────────────────────────────────────────────────

    private suspend fun sendHello() {
        val hello = com.opendisplay.usb.protocol.HelloMessage(
            manufacturer = android.os.Build.MANUFACTURER,
            model = android.os.Build.MODEL,
            androidVersion = android.os.Build.VERSION.RELEASE,
            sdk = android.os.Build.VERSION.SDK_INT,
            deviceId = generateStableDeviceId()
        )
        val payload = JsonCodec.encode(hello)
        val packet = PacketCodec.encode(MessageType.HELLO, payload)
        transport.send(packet).getOrThrow()
    }

    private suspend fun runReceiveLoop(scope: CoroutineScope): ExitReason {
        transport.receiveFlow().collect { rawPacket ->
            if (stopped) return@collect

            val result = PacketCodec.decode(rawPacket)
            if (result.isFailure) {
                Log.w(TAG, "Malformed packet received: ${result.exceptionOrNull()?.message}")
                sendError(ErrorCode.ERR_INVALID_PACKET, "Malformed frame header")
                return@collect
            }

            val packet = result.getOrThrow()
            when (packet.type) {
                MessageType.HELLO_ACK           -> handleHelloAck(packet.payload, scope)
                MessageType.CAPABILITIES_ACK    -> handleCapabilitiesAck(packet.payload)
                MessageType.DISPLAY_CONFIG      -> handleDisplayConfig(packet.payload)
                MessageType.VIDEO_CONFIG        -> handleVideoConfig(packet.payload, scope)
                MessageType.VIDEO_FRAME         -> handleVideoFrame(packet.payload)
                MessageType.AUDIO_CONFIG        -> handleAudioConfig(packet.payload)
                MessageType.AUDIO_FRAME         -> handleAudioFrame(packet.payload)
                MessageType.PING               -> handlePing(packet.payload)
                MessageType.PONG               -> handlePong(packet.payload)
                MessageType.STREAM_RESET       -> handleStreamReset(packet.payload, scope)
                MessageType.ERROR              -> handleError(packet.payload)
                MessageType.DISCONNECT         -> {
                    _protocolState.value = ProtocolState.DISCONNECTED
                    stopped = true
                }
                MessageType.CLIPBOARD_EVENT    -> handleClipboardEvent(packet.payload)
                MessageType.FILE_TRANSFER      -> { /* TODO(phase2): file transfer */ }
                else -> Log.w(TAG, "Received unhandled message type: ${packet.type} — ignoring")
            }
        }
        return if (_protocolState.value == ProtocolState.DISCONNECTED)
            ExitReason.USER_DISCONNECT
        else
            ExitReason.STREAM_COMPLETE
    }

    // ── Message handlers ──────────────────────────────────────────────────────

    private suspend fun handleHelloAck(payload: ByteArray, scope: CoroutineScope) {
        val ack = JsonCodec.decodeHelloAck(payload).getOrElse {
            Log.e(TAG, "Failed to decode HELLO_ACK: ${it.message}")
            sendError(ErrorCode.ERR_INVALID_PACKET, "HELLO_ACK parse failure")
            return
        }

        if (!ack.accepted) {
            Log.e(TAG, "HELLO rejected: ${ack.rejectionReason}")
            _protocolState.value = ProtocolState.ERROR
            stopped = true
            return
        }

        Log.i(TAG, "HELLO_ACK accepted (protocol v${ack.protocol})")
        sendCapabilities()
        _protocolState.value = ProtocolState.CAPABILITIES_SENT
    }

    private suspend fun sendCapabilities() {
        val caps = if (capabilityDetector != null) {
            val detected = capabilityDetector.detectCapabilities()
            val supportedCodecs = detected.video.supportedCodecs
            com.opendisplay.usb.protocol.CapabilitiesMessage(
                display = com.opendisplay.usb.protocol.DisplayCapabilityInfo(
                    widthPx = detected.display.physicalWidth,
                    heightPx = detected.display.physicalHeight,
                    densityDpi = detected.display.densityDpi,
                    refreshRateHz = detected.display.refreshRate,
                    orientation = 0
                ),
                video = listOf(
                    com.opendisplay.usb.protocol.VideoCapabilityInfo(
                        codec = "H264",
                        supported = supportedCodecs.contains(VideoCodec.H264) || true,
                        hardwareAccelerated = true,
                        maxWidth = detected.video.maxResolutionWidth,
                        maxHeight = detected.video.maxResolutionHeight,
                        maxFrameRateHz = detected.video.maxFps.toFloat(),
                        lowLatencySupported = com.opendisplay.usb.video.CodecSelector.listDecoders("video/avc").any {
                            com.opendisplay.usb.video.CodecSelector.supportsLowLatency(it, "video/avc")
                        }
                    ),
                    com.opendisplay.usb.protocol.VideoCapabilityInfo(
                        codec = "HEVC",
                        supported = supportedCodecs.contains(VideoCodec.H265),
                        hardwareAccelerated = true,
                        maxWidth = detected.video.maxResolutionWidth,
                        maxHeight = detected.video.maxResolutionHeight,
                        maxFrameRateHz = detected.video.maxFps.toFloat(),
                        lowLatencySupported = false
                    ),
                    com.opendisplay.usb.protocol.VideoCapabilityInfo(
                        codec = "AV1",
                        supported = supportedCodecs.contains(VideoCodec.AV1),
                        hardwareAccelerated = false,
                        maxWidth = 0,
                        maxHeight = 0,
                        maxFrameRateHz = 0f,
                        lowLatencySupported = false
                    )
                ),
                audio = com.opendisplay.usb.protocol.AudioCapabilityInfo(
                    opusSupported = true,
                    aacSupported = true,
                    pcmSupported = true,
                    supportedSampleRates = listOf(44100, 48000),
                    supportedChannelCounts = listOf(1, 2),
                    lowLatencyOutput = false
                ),
                input = com.opendisplay.usb.protocol.InputCapabilityInfo(
                    touchSupported = detected.input.hasTouch,
                    maxTouchPoints = 10,
                    stylusSupported = detected.input.hasStylus,
                    pressureSupported = true,
                    tiltSupported = false
                ),
                device = com.opendisplay.usb.protocol.DeviceCapabilityInfo(
                    hasMicrophone = true,
                    hasCamera = true,
                    hasSpeaker = true,
                    batteryLevel = null,
                    batteryCharging = null
                )
            )
        } else {
            com.opendisplay.usb.protocol.CapabilitiesMessage(
                display = com.opendisplay.usb.protocol.DisplayCapabilityInfo(
                    widthPx = 1920, heightPx = 1080, densityDpi = 240,
                    refreshRateHz = 60f, orientation = 0
                ),
                video = listOf(
                    com.opendisplay.usb.protocol.VideoCapabilityInfo(
                        codec = "H264", supported = true, hardwareAccelerated = true,
                        maxWidth = 3840, maxHeight = 2160, maxFrameRateHz = 120f,
                        lowLatencySupported = android.os.Build.VERSION.SDK_INT >= 30
                    )
                ),
                audio = com.opendisplay.usb.protocol.AudioCapabilityInfo(
                    opusSupported = true, aacSupported = true, pcmSupported = true,
                    supportedSampleRates = listOf(44100, 48000),
                    supportedChannelCounts = listOf(1, 2),
                    lowLatencyOutput = false
                ),
                input = com.opendisplay.usb.protocol.InputCapabilityInfo(
                    touchSupported = true, maxTouchPoints = 10,
                    stylusSupported = false, pressureSupported = true, tiltSupported = false
                ),
                device = com.opendisplay.usb.protocol.DeviceCapabilityInfo(
                    hasMicrophone = true, hasCamera = true, hasSpeaker = true,
                    batteryLevel = null, batteryCharging = null
                )
            )
        }
        val packet = PacketCodec.encode(MessageType.CAPABILITIES, JsonCodec.encode(caps))
        transport.send(packet).getOrThrow()
        Log.i(TAG, "CAPABILITIES sent (dynamic: ${capabilityDetector != null})")
    }

    private fun handleCapabilitiesAck(payload: ByteArray) {
        val ack = JsonCodec.decodeCapabilitiesAck(payload).getOrElse {
            Log.w(TAG, "Failed to decode CAPABILITIES_ACK: ${it.message}")
            return
        }
        if (ack.accepted) {
            _protocolState.value = ProtocolState.CONFIGURING
            Log.i(TAG, "CAPABILITIES_ACK received — waiting for DISPLAY_CONFIG")
        } else {
            Log.w(TAG, "CAPABILITIES not accepted by Windows side")
        }
    }

    private suspend fun handleDisplayConfig(payload: ByteArray) {
        val config = JsonCodec.decodeDisplayConfig(payload).getOrElse {
            Log.e(TAG, "Failed to decode DISPLAY_CONFIG: ${it.message}")
            sendError(ErrorCode.ERR_INVALID_PACKET, "DISPLAY_CONFIG parse failure")
            return
        }
        Log.i(TAG, "DISPLAY_CONFIG: ${config.widthPx}x${config.heightPx} @ ${config.frameRateHz}fps")

        val result = displayConfigurator.apply(config)
        val ack = com.opendisplay.usb.protocol.DisplayConfigAckMessage(
            accepted = result.isSuccess,
            errorCode = if (result.isFailure) ErrorCode.ERR_UNSUPPORTED_RESOLUTION.code else 0,
            errorMessage = result.exceptionOrNull()?.message
        )
        val packet = PacketCodec.encode(MessageType.DISPLAY_CONFIG_ACK, JsonCodec.encode(ack))
        transport.send(packet).getOrThrow()
    }

    private suspend fun handleVideoConfig(payload: ByteArray, scope: CoroutineScope) {
        val config = JsonCodec.decodeVideoConfig(payload).getOrElse {
            Log.e(TAG, "Failed to decode VIDEO_CONFIG: ${it.message}")
            sendError(ErrorCode.ERR_INVALID_PACKET, "VIDEO_CONFIG parse failure")
            return
        }
        Log.i(TAG, "VIDEO_CONFIG: ${config.codec} ${config.widthPx}x${config.heightPx} @ ${config.frameRateHz}fps")

        val surface = surfaceProvider()
        val csd0Bytes = config.csd0Base64?.let {
            ensureAnnexBStartCode(Base64.decode(it, Base64.DEFAULT))
        }
        val csd1Bytes = config.csd1Base64?.let {
            ensureAnnexBStartCode(Base64.decode(it, Base64.DEFAULT))
        }

        val mime = VideoCodecMime.fromProtocolName(config.codec)
        val videoConfig = VideoConfig(
            codecMimeType = mime,
            widthPx = config.widthPx,
            heightPx = config.heightPx,
            frameRateHz = config.frameRateHz,
            bitrateBps = config.bitrateBps,
            lowLatencyMode = config.lowLatencyMode,
            csd0 = csd0Bytes,
            csd1 = csd1Bytes
        )

        var configSuccess = false
        if (surface != null && surface.isValid) {
            val configureResult = videoDecoder.configure(videoConfig, surface)
            if (configureResult.isSuccess) {
                videoDecoder.startDecoding(videoFrameQueue, scope)
                configSuccess = true
                Log.i(TAG, "VideoDecoder successfully configured and started")
            } else {
                Log.e(TAG, "Failed to configure VideoDecoder: ${configureResult.exceptionOrNull()?.message}")
            }
        } else {
            Log.w(TAG, "No valid surface from surfaceProvider (surface=$surface); acknowledging without hardware render")
            configSuccess = true
        }

        val ack = com.opendisplay.usb.protocol.VideoConfigAckMessage(
            accepted = configSuccess,
            errorCode = if (configSuccess) 0 else ErrorCode.ERR_DECODER_FAILED.code
        )
        val packet = PacketCodec.encode(MessageType.VIDEO_CONFIG_ACK, JsonCodec.encode(ack))
        transport.send(packet).getOrThrow()

        if (!configSuccess) {
            _protocolState.value = ProtocolState.ERROR
            return
        }

        _protocolState.value = ProtocolState.STREAMING
        Log.i(TAG, "Entered STREAMING state")

        diagnostics.setCurrentConfig(config.widthPx, config.heightPx, config.codec)

        // Start periodic PING
        startPingLoop(scope)

        onUiUpdate(
            SessionUiState(
                connectionState = com.opendisplay.usb.transport.ConnectionState.CONNECTED,
                videoCodec = config.codec,
                displayResolution = "${config.widthPx}×${config.heightPx}",
                displayFps = "${config.frameRateHz.toInt()} FPS"
            )
        )
    }

    suspend fun sendInputEvent(event: InputEventMessage): Result<Unit> {
        if (_protocolState.value != ProtocolState.STREAMING) {
            return Result.failure(IllegalStateException("Cannot send input: not streaming"))
        }
        val payload = JsonCodec.encode(event)
        val packet = PacketCodec.encode(MessageType.INPUT_EVENT, payload)
        return transport.send(packet)
    }

    private fun ensureAnnexBStartCode(data: ByteArray): ByteArray {
        if (data.size >= 4 && data[0] == 0.toByte() && data[1] == 0.toByte() && data[2] == 0.toByte() && data[3] == 1.toByte()) {
            return data
        }
        if (data.size >= 3 && data[0] == 0.toByte() && data[1] == 0.toByte() && data[2] == 1.toByte()) {
            val out = ByteArray(data.size + 1)
            out[3] = 1.toByte()
            System.arraycopy(data, 3, out, 4, data.size - 3)
            return out
        }
        val prefix = byteArrayOf(0, 0, 0, 1)
        val out = ByteArray(prefix.size + data.size)
        System.arraycopy(prefix, 0, out, 0, prefix.size)
        System.arraycopy(data, 0, out, prefix.size, data.size)
        return out
    }

    private fun handleVideoFrame(payload: ByteArray) {
        if (_protocolState.value != ProtocolState.STREAMING) return

        val decoded = runCatching {
            PacketCodec.decodeVideoFramePayload(payload)
        }.getOrElse {
            Log.w(TAG, "Malformed VIDEO_FRAME payload: ${it.message}")
            diagnostics.recordError()
            return
        }

        val (timestampNs, isKeyframe, dataOffset) = decoded
        val nalData = payload.copyOfRange(dataOffset, payload.size)

        val frame = EncodedVideoFrame(
            data = nalData,
            presentationTimestamp = PresentationTimestamp(timestampNs),
            isKeyframe = isKeyframe
        )
        videoFrameQueue.enqueue(frame)
        diagnostics.recordVideoFrame(payload.size)
    }

    private fun handleAudioFrame(payload: ByteArray) {
        if (_protocolState.value != ProtocolState.STREAMING) return
        val decoded = runCatching {
            PacketCodec.decodeAudioFramePayload(payload)
        }.getOrElse {
            Log.w(TAG, "Malformed AUDIO_FRAME payload: ${it.message}")
            return
        }
        val (timestampNs, sequence, dataOffset) = decoded
        val audioBytesLen = payload.size - dataOffset
        if (audioBytesLen <= 0) return

        if (audioRenderer == null) {
            audioRenderer = AudioRenderer(AudioConfig(sampleRate = 48000, mode = AudioMode.STEREO)).apply {
                play()
            }
        }
        audioRenderer?.write(payload, dataOffset, audioBytesLen)
    }

    private fun handleAudioConfig(payload: ByteArray) {
        val config = JsonCodec.decodeAudioConfig(payload).getOrElse {
            Log.e(TAG, "Failed to decode AUDIO_CONFIG: ${it.message}")
            return
        }
        val mode = if (config.channelCount == 1) AudioMode.MONO else AudioMode.STEREO
        audioRenderer?.stop()
        audioRenderer?.release()
        audioRenderer = AudioRenderer(AudioConfig(sampleRate = config.sampleRateHz, mode = mode)).apply {
            play()
        }
        Log.i(TAG, "AudioRenderer configured for ${config.sampleRateHz}Hz, ${config.channelCount}ch")
    }

    private fun handleClipboardEvent(payload: ByteArray) {
        val event = JsonCodec.decodeClipboardEvent(payload).getOrElse {
            Log.w(TAG, "Failed to decode CLIPBOARD_EVENT: ${it.message}")
            return
        }
        Log.i(TAG, "Received CLIPBOARD_EVENT (${event.content.length} chars)")
        onClipboardReceived?.invoke(event.content)
    }

    suspend fun sendClipboardEvent(text: String): Result<Unit> {
        if (_protocolState.value != ProtocolState.STREAMING) {
            return Result.failure(IllegalStateException("Cannot send clipboard: not streaming"))
        }
        val msg = ClipboardEventMessage(content = text)
        val payload = JsonCodec.encode(msg)
        val packet = PacketCodec.encode(MessageType.CLIPBOARD_EVENT, payload)
        return transport.send(packet)
    }

    private suspend fun handlePing(payload: ByteArray) {
        val ping = JsonCodec.decodePing(payload).getOrElse { return }
        val pong = PongMessage(
            timestampNs = ping.timestampNs,
            serverTimestampNs = SystemMonotonicClock.nanoTime()
        )
        val packet = PacketCodec.encode(MessageType.PONG, JsonCodec.encode(pong))
        transport.send(packet)
    }

    private fun handlePong(payload: ByteArray) {
        val pong = JsonCodec.decodePong(payload).getOrElse { return }
        clockSync.onPongReceived(pong.timestampNs)
        Log.d(TAG, "PONG received — latency ~${clockSync.estimatedLatencyMs}ms")
    }

    private suspend fun handleStreamReset(payload: ByteArray, scope: CoroutineScope) {
        val reset = JsonCodec.decodeStreamReset(payload).getOrElse { return }
        Log.i(TAG, "STREAM_RESET received: ${reset.reason}")
        videoDecoder.flush()
        videoFrameQueue.clear()
        _protocolState.value = ProtocolState.CONFIGURING
    }

    private fun handleError(payload: ByteArray) {
        val error = JsonCodec.decodeError(payload).getOrElse { return }
        Log.w(TAG, "ERROR from Windows: code=${error.code} message=${error.message} fatal=${error.fatal}")
        if (error.fatal) {
            _protocolState.value = ProtocolState.ERROR
            stopped = true
        }
    }

    private suspend fun sendError(code: ErrorCode, message: String) {
        val err = ErrorMessage(code = code.code, message = message)
        val packet = PacketCodec.encode(MessageType.ERROR, JsonCodec.encode(err))
        transport.send(packet)
    }

    private fun startPingLoop(scope: CoroutineScope) {
        pingJob?.cancel()
        pingJob = scope.launch {
            while (!stopped && _protocolState.value == ProtocolState.STREAMING) {
                delay(PING_INTERVAL_MS)
                val pingTs = clockSync.onPingSent()
                val ping = PingMessage(timestampNs = pingTs)
                val packet = PacketCodec.encode(MessageType.PING, JsonCodec.encode(ping))
                transport.send(packet)
            }
        }
    }

    private fun generateStableDeviceId(): String {
        // Use a hash of device identifiers that doesn't require READ_PHONE_STATE permission.
        // This is stable across app restarts but not across factory resets — which is acceptable.
        val raw = "${android.os.Build.BOARD}${android.os.Build.HARDWARE}${android.os.Build.SERIAL}"
        return raw.hashCode().toString(16).padStart(8, '0')
    }
}
