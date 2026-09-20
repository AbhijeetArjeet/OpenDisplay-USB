package com.opendisplay.usb

import android.util.Log
import android.view.Surface
import com.opendisplay.usb.audio.AudioReceiver
import com.opendisplay.usb.capabilities.CapabilityDetector
import com.opendisplay.usb.diagnostics.DiagnosticsCollector
import com.opendisplay.usb.diagnostics.DiagnosticsSnapshot
import com.opendisplay.usb.display.DisplayConfigurator
import com.opendisplay.usb.protocol.InputEventMessage
import com.opendisplay.usb.transport.ConnectionState
import com.opendisplay.usb.transport.Transport
import com.opendisplay.usb.ui.SessionUiState
import com.opendisplay.usb.video.VideoDecoder
import com.opendisplay.usb.video.VideoFrameQueue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

private const val TAG = "SessionManager"

/** Maximum reconnect attempts before giving up */
private const val MAX_RECONNECT_ATTEMPTS = 5

/** Initial reconnect delay in milliseconds */
private const val RECONNECT_INITIAL_DELAY_MS = 2_000L

/** Maximum reconnect delay after exponential backoff */
private const val RECONNECT_MAX_DELAY_MS = 30_000L

/**
 * Central coordinator for an OpenDisplay USB display session.
 *
 * Responsibilities:
 * - Holds references to all subsystems (transport, protocol, video decoder, audio, display)
 * - Drives the reconnect state machine on transport failure
 * - Exposes [uiState] for the UI layer to observe
 * - Manages the coroutine lifecycle for the session
 *
 * Lifecycle:
 *   start(transport) → [active session] → stop() → [idle]
 *   On transport failure: automatic reconnect with exponential backoff
 */
class SessionManager(
    private val videoDecoder: VideoDecoder,
    private val videoFrameQueue: VideoFrameQueue,
    private val audioReceiver: AudioReceiver,
    private val displayConfigurator: DisplayConfigurator,
    private val diagnostics: DiagnosticsCollector,
    private val capabilityDetector: CapabilityDetector? = null,
    private val onClipboardReceived: ((String) -> Unit)? = null
) {
    private val managerScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private var sessionJob: Job? = null
    private var protocolController: ProtocolController? = null
    private var currentTransport: Transport? = null
    @Volatile private var activeSurface: Surface? = null

    private val _uiState = MutableStateFlow(SessionUiState())
    val uiState: StateFlow<SessionUiState> = _uiState.asStateFlow()

    private var reconnectCount = 0

    fun onSurfaceAvailable(surface: Surface) {
        Log.i(TAG, "Surface available: $surface")
        activeSurface = surface
        videoDecoder.setOutputSurface(surface)
    }

    fun onSurfaceDestroyed() {
        Log.i(TAG, "Surface destroyed")
        activeSurface = null
    }

    fun sendInputEvent(event: InputEventMessage) {
        managerScope.launch {
            protocolController?.sendInputEvent(event)
        }
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Starts a display session using [transport].
     *
     * This function launches the session coroutine and returns immediately.
     * The session runs in [managerScope] and survives configuration changes.
     */
    fun start(transport: Transport) {
        if (sessionJob?.isActive == true) {
            Log.w(TAG, "Session already active, ignoring start()")
            return
        }
        currentTransport = transport
        reconnectCount = 0
        sessionJob = managerScope.launch {
            runSessionWithReconnect(transport)
        }
        diagnostics.start(managerScope)
    }

    /**
     * Stops the current session and releases resources.
     * Safe to call even if not started.
     */
    suspend fun stop() {
        Log.i(TAG, "Stopping session")
        sessionJob?.cancelAndJoin()
        sessionJob = null
        protocolController?.stop()
        protocolController = null
        videoDecoder.stop()
        videoFrameQueue.clear()
        currentTransport?.disconnect()
        currentTransport = null
        _uiState.update { it.copy(connectionState = ConnectionState.DISCONNECTED) }
    }

    // ── Private session lifecycle ─────────────────────────────────────────────

    private suspend fun runSessionWithReconnect(transport: Transport) {
        var delayMs = RECONNECT_INITIAL_DELAY_MS

        while (true) {
            Log.i(TAG, "Starting session (reconnect #$reconnectCount)")
            _uiState.update {
                it.copy(connectionState = ConnectionState.CONNECTING)
            }

            val connectResult = transport.connect()
            if (connectResult.isFailure) {
                Log.e(TAG, "Transport connect failed: ${connectResult.exceptionOrNull()?.message}")
                if (!attemptReconnect(transport, delayMs)) return
                delayMs = (delayMs * 2).coerceAtMost(RECONNECT_MAX_DELAY_MS)
                continue
            }

            _uiState.update { it.copy(connectionState = ConnectionState.CONNECTED) }
            delayMs = RECONNECT_INITIAL_DELAY_MS  // Reset on successful connect

            // Start the protocol controller for this session
            val controller = ProtocolController(
                transport = transport,
                videoDecoder = videoDecoder,
                videoFrameQueue = videoFrameQueue,
                audioReceiver = audioReceiver,
                displayConfigurator = displayConfigurator,
                diagnostics = diagnostics,
                surfaceProvider = { activeSurface },
                capabilityDetector = capabilityDetector,
                onClipboardReceived = onClipboardReceived,
                onUiUpdate = { update -> _uiState.update { current -> current.merge(update) } }
            )
            protocolController = controller

            // Run until the controller exits (either normally or on error)
            val reason = controller.run(managerScope)
            Log.i(TAG, "Protocol controller exited: $reason")

            // Check if we should reconnect
            if (reason == ProtocolController.ExitReason.USER_DISCONNECT) {
                Log.i(TAG, "Host disconnected — resetting receiver to await next connection")
                transport.disconnect()
                videoDecoder.stop()
                videoFrameQueue.clear()
                _uiState.update { it.copy(connectionState = ConnectionState.DISCONNECTED, videoCodec = "") }
                reconnectCount = 0
                delay(500L)
                continue
            }

            if (!attemptReconnect(transport, delayMs)) return
            delayMs = (delayMs * 2).coerceAtMost(RECONNECT_MAX_DELAY_MS)
        }
    }

    private suspend fun attemptReconnect(transport: Transport, delayMs: Long): Boolean {
        reconnectCount++
        diagnostics.recordReconnect()

        if (reconnectCount > MAX_RECONNECT_ATTEMPTS) {
            Log.e(TAG, "Exceeded $MAX_RECONNECT_ATTEMPTS reconnect attempts — giving up")
            _uiState.update {
                it.copy(
                    connectionState = ConnectionState.ERROR,
                    errorMessage = "Could not reconnect after $MAX_RECONNECT_ATTEMPTS attempts"
                )
            }
            return false
        }

        Log.i(TAG, "Reconnect attempt $reconnectCount/$MAX_RECONNECT_ATTEMPTS in ${delayMs}ms")
        _uiState.update {
            it.copy(
                connectionState = ConnectionState.RECONNECTING,
                errorMessage = null
            )
        }
        transport.disconnect()
        videoDecoder.stop()
        videoFrameQueue.clear()
        delay(delayMs)
        return true
    }
}

/** Merges a partial UI state update into the current state. */
private fun SessionUiState.merge(update: SessionUiState): SessionUiState = copy(
    connectionState = if (update.connectionState != ConnectionState.DISCONNECTED) update.connectionState else connectionState,
    deviceName = if (update.deviceName.isNotEmpty()) update.deviceName else deviceName,
    displayResolution = if (update.displayResolution.isNotEmpty()) update.displayResolution else displayResolution,
    displayFps = if (update.displayFps.isNotEmpty()) update.displayFps else displayFps,
    videoCodec = if (update.videoCodec.isNotEmpty()) update.videoCodec else videoCodec,
    audioEnabled = update.audioEnabled,
    touchEnabled = update.touchEnabled,
    diagnostics = if (update.diagnostics != DiagnosticsSnapshot.EMPTY) update.diagnostics else diagnostics,
    errorMessage = update.errorMessage
)
