package com.opendisplay.usb

import android.os.Bundle
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.opendisplay.usb.audio.AudioReceiver
import com.opendisplay.usb.capabilities.CapabilityDetector
import com.opendisplay.usb.diagnostics.DiagnosticsCollector
import com.opendisplay.usb.display.DisplayConfigurator
import com.opendisplay.usb.input.TouchEncoder
import com.opendisplay.usb.transport.ConnectionState
import com.opendisplay.usb.transport.TcpServerTransport
import com.opendisplay.usb.ui.DiagnosticsScreen
import com.opendisplay.usb.ui.FloatingToolbar
import com.opendisplay.usb.ui.MainScreen
import com.opendisplay.usb.ui.SettingsScreen
import com.opendisplay.usb.ui.theme.OpenDisplayTheme
import com.opendisplay.usb.video.VideoDecoder
import com.opendisplay.usb.video.VideoFrameQueue

/**
 * Main entry point of the OpenDisplay USB application.
 *
 * Responsibilities:
 * - Sets up the Compose UI with Material 3 dark theme
 * - Creates the subsystem instances for display, video decoding, touch input, and transport
 * - Listens for Windows host connection on ADB TCP port 7320
 * - Owns the [SurfaceView] for video rendering and touch event dispatch
 * - Handles configuration changes gracefully
 */
class MainActivity : ComponentActivity() {

    private val videoDecoder = VideoDecoder()
    private val videoFrameQueue = VideoFrameQueue()
    private val audioReceiver = AudioReceiver()
    private val displayConfigurator = DisplayConfigurator()
    private val diagnostics = DiagnosticsCollector()
    private val capabilityDetector by lazy { CapabilityDetector(this) }
    private val touchEncoder = TouchEncoder()

    private val sessionManager by lazy {
        val clipboardManager = getSystemService(CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        SessionManager(
            videoDecoder = videoDecoder,
            videoFrameQueue = videoFrameQueue,
            audioReceiver = audioReceiver,
            displayConfigurator = displayConfigurator,
            diagnostics = diagnostics,
            capabilityDetector = capabilityDetector,
            onClipboardReceived = { text ->
                runOnUiThread {
                    clipboardManager?.setPrimaryClip(
                        android.content.ClipData.newPlainText("OpenDisplay", text)
                    )
                }
            }
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Keep screen on during active display session
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        // Check for USB accessory (AOA mode) or fallback to TCP port 7320
        checkUsbAccessory(intent)

        setContent {
            OpenDisplayTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    val uiState by sessionManager.uiState.collectAsState()

                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        val aspectModifier = if (uiState.displayResolution.contains("×")) {
                            try {
                                val parts = uiState.displayResolution.split("×")
                                val w = parts[0].trim().toFloat()
                                val h = parts[1].trim().toFloat()
                                if (w > 0f && h > 0f) {
                                    Modifier.aspectRatio(w / h, matchHeightConstraintsFirst = false)
                                } else Modifier.fillMaxSize()
                            } catch (e: Exception) {
                                Modifier.fillMaxSize()
                            }
                        } else {
                            Modifier.fillMaxSize()
                        }

                        // Underlying hardware video surface with pixel-perfect aspect ratio letterboxing
                        AndroidView(
                            modifier = Modifier
                                .fillMaxSize()
                                .then(aspectModifier),
                            factory = { context ->
                                SurfaceView(context).apply {
                                    holder.addCallback(object : SurfaceHolder.Callback {
                                        override fun surfaceCreated(holder: SurfaceHolder) {
                                            sessionManager.onSurfaceAvailable(holder.surface)
                                        }

                                        override fun surfaceChanged(
                                            holder: SurfaceHolder,
                                            format: Int,
                                            width: Int,
                                            height: Int
                                        ) {
                                            sessionManager.onSurfaceAvailable(holder.surface)
                                        }

                                        override fun surfaceDestroyed(holder: SurfaceHolder) {
                                            sessionManager.onSurfaceDestroyed()
                                        }
                                    })

                                    setOnTouchListener { view, event ->
                                        val messages = touchEncoder.encodeBatch(event, view.width, view.height)
                                        for (msg in messages) {
                                            sessionManager.sendInputEvent(msg)
                                        }
                                        true
                                    }

                                    setOnHoverListener { view, event ->
                                        val messages = touchEncoder.encodeBatch(event, view.width, view.height)
                                        for (msg in messages) {
                                            sessionManager.sendInputEvent(msg)
                                        }
                                        true
                                    }
                                }
                            }
                        )

                        // If actively streaming, show floating overlay toolbar; otherwise show dashboard
                        val isStreaming = uiState.connectionState == ConnectionState.CONNECTED && uiState.videoCodec.isNotEmpty()
                        if (isStreaming) {
                            FloatingToolbar(
                                diagnostics = uiState.diagnostics,
                                onDisconnect = {
                                    checkUsbAccessory(intent)
                                },
                                modifier = Modifier.align(Alignment.TopEnd)
                            )
                        } else {
                            NavHost(
                                navController = navController,
                                startDestination = "main"
                            ) {
                                composable("main") {
                                    MainScreen(
                                        uiState = uiState,
                                        onSettingsClick = { navController.navigate("settings") },
                                        onDiagnosticsClick = { navController.navigate("diagnostics") },
                                        onDisconnectClick = {
                                            sessionManager.start(TcpServerTransport(port = 7320))
                                        },
                                        onConnectClick = {
                                            sessionManager.start(TcpServerTransport(port = 7320))
                                        }
                                    )
                                }
                                composable("settings") {
                                    SettingsScreen(
                                        onBack = { navController.popBackStack() }
                                    )
                                }
                                composable("diagnostics") {
                                    DiagnosticsScreen(
                                        snapshot = uiState.diagnostics,
                                        onBack = { navController.popBackStack() }
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        checkUsbAccessory(intent)
    }

    private fun checkUsbAccessory(intent: android.content.Intent?) {
        val usbManager = getSystemService(USB_SERVICE) as? android.hardware.usb.UsbManager ?: return
        val accessory = intent?.getParcelableExtra<android.hardware.usb.UsbAccessory>(android.hardware.usb.UsbManager.EXTRA_ACCESSORY)
            ?: usbManager.accessoryList?.firstOrNull()

        if (accessory != null) {
            val pfd = usbManager.openAccessory(accessory)
            if (pfd != null) {
                android.util.Log.i("MainActivity", "AOA USB Accessory connected: ${accessory.description}")
                sessionManager.start(com.opendisplay.usb.transport.AoaTransport(pfd))
                return
            }
        }
        // Fallback to ADB TCP server transport on port 7320
        sessionManager.start(TcpServerTransport(port = 7320))
    }

    override fun onDestroy() {
        super.onDestroy()
        videoDecoder.release()
        videoFrameQueue.close()
    }
}

