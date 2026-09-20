package com.opendisplay.usb.ui

import com.opendisplay.usb.diagnostics.DiagnosticsSnapshot
import com.opendisplay.usb.transport.ConnectionState

/**
 * Observable UI state for the main display session screen.
 *
 * All properties have sensible defaults so the UI renders correctly before any
 * session data is available (e.g., on first launch, before any transport connects).
 *
 * Immutable data class — the UI observes this via [StateFlow] and the SessionManager
 * emits a new instance whenever anything changes.
 */
data class SessionUiState(
    val connectionState: ConnectionState = ConnectionState.DISCONNECTED,
    /** Display name of the connected device (from Build.MODEL, filled after HELLO). */
    val deviceName: String = "",
    /** Human-readable resolution string, e.g. "1920×1080". */
    val displayResolution: String = "",
    /** Human-readable frame rate string, e.g. "60 FPS". */
    val displayFps: String = "",
    /** Active codec name, e.g. "H264", "HEVC". */
    val videoCodec: String = "",
    /** True if an audio stream is active. */
    val audioEnabled: Boolean = false,
    /** True if touch input forwarding is enabled. */
    val touchEnabled: Boolean = true,
    /** Live diagnostics from [DiagnosticsCollector]. */
    val diagnostics: DiagnosticsSnapshot = DiagnosticsSnapshot.EMPTY,
    /** Non-null when a non-fatal error message should be shown in the UI. */
    val errorMessage: String? = null
)
