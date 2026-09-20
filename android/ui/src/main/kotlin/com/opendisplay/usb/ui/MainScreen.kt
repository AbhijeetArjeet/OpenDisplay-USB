package com.opendisplay.usb.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.Link
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.opendisplay.usb.transport.ConnectionState
import com.opendisplay.usb.ui.theme.OpenDisplayGreen
import com.opendisplay.usb.ui.theme.OpenDisplayAmber
import com.opendisplay.usb.ui.theme.OpenDisplayRed

/**
 * Main status screen shown when the app is launched.
 *
 * Shows:
 * - App title and connection status dot
 * - Device / display / video / audio / touch / latency / bitrate cards (when connected)
 * - Settings, Diagnostics, and Disconnect/Connect action buttons
 */
@Composable
fun MainScreen(
    uiState: SessionUiState,
    onSettingsClick: () -> Unit,
    onDiagnosticsClick: () -> Unit,
    onDisconnectClick: () -> Unit,
    onConnectClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // ── Title ─────────────────────────────────────────────────────────────
        Text(
            text = "OpenDisplay USB",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(top = 24.dp, bottom = 8.dp)
        )

        // ── Status row ────────────────────────────────────────────────────────
        StatusRow(connectionState = uiState.connectionState)

        Spacer(modifier = Modifier.height(24.dp))

        // ── Info cards (visible only when connected or reconnecting) ──────────
        if (uiState.connectionState == ConnectionState.CONNECTED ||
            uiState.connectionState == ConnectionState.RECONNECTING) {
            InfoCardGrid(uiState = uiState)
        } else {
            Text(
                text = when (uiState.connectionState) {
                    ConnectionState.DISCONNECTED -> "Connect a USB cable and enable\nADB debugging to begin."
                    ConnectionState.CONNECTING   -> "Connecting…"
                    ConnectionState.ERROR        -> uiState.errorMessage ?: "Connection error."
                    else                          -> ""
                },
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                modifier = Modifier.padding(horizontal = 32.dp)
            )
        }

        Spacer(modifier = Modifier.weight(1f))

        // ── Action buttons ────────────────────────────────────────────────────
        ActionButtons(
            isConnected = uiState.connectionState == ConnectionState.CONNECTED,
            onSettingsClick = onSettingsClick,
            onDiagnosticsClick = onDiagnosticsClick,
            onDisconnectClick = onDisconnectClick,
            onConnectClick = onConnectClick
        )

        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun StatusRow(connectionState: ConnectionState) {
    val dotColor: Color = when (connectionState) {
        ConnectionState.CONNECTED     -> OpenDisplayGreen
        ConnectionState.CONNECTING    -> OpenDisplayAmber
        ConnectionState.RECONNECTING  -> OpenDisplayAmber
        ConnectionState.DISCONNECTED  -> Color.Gray
        ConnectionState.ERROR         -> OpenDisplayRed
    }
    val statusText: String = when (connectionState) {
        ConnectionState.CONNECTED     -> "Connected"
        ConnectionState.CONNECTING    -> "Connecting…"
        ConnectionState.RECONNECTING  -> "Reconnecting…"
        ConnectionState.DISCONNECTED  -> "Not Connected"
        ConnectionState.ERROR         -> "Error"
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center
    ) {
        Box(
            modifier = Modifier
                .size(12.dp)
                .clip(CircleShape)
                .background(dotColor)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = statusText,
            style = MaterialTheme.typography.titleMedium,
            color = dotColor
        )
    }
}

@Composable
private fun InfoCardGrid(uiState: SessionUiState) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        if (uiState.deviceName.isNotBlank()) {
            InfoCard(label = "Device", value = uiState.deviceName)
        }
        if (uiState.displayResolution.isNotBlank()) {
            InfoCard(
                label = "Display",
                value = "${uiState.displayResolution} • ${uiState.displayFps}"
            )
        }
        if (uiState.videoCodec.isNotBlank()) {
            InfoCard(label = "Video", value = "${uiState.videoCodec} Hardware")
        }
        InfoCard(
            label = "Audio",
            value = if (uiState.audioEnabled) "Connected" else "Disabled"
        )
        InfoCard(
            label = "Touch",
            value = if (uiState.touchEnabled) "Enabled" else "Disabled"
        )
        val latencyMs = uiState.diagnostics.decodeLatencyMs
        if (latencyMs > 0f) {
            InfoCard(
                label = "Latency",
                value = "%.0f ms".format(latencyMs)
            )
        }
        val bitrateKbps = uiState.diagnostics.bitrateKbps
        if (bitrateKbps > 0f) {
            InfoCard(
                label = "Bitrate",
                value = "%.1f Mbps".format(bitrateKbps / 1000f)
            )
        }
    }
}

@Composable
private fun InfoCard(label: String, value: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium
            )
        }
    }
}

@Composable
private fun ActionButtons(
    isConnected: Boolean,
    onSettingsClick: () -> Unit,
    onDiagnosticsClick: () -> Unit,
    onDisconnectClick: () -> Unit,
    onConnectClick: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick = onSettingsClick,
                modifier = Modifier.weight(1f)
            ) {
                Icon(Icons.Default.Settings, contentDescription = null)
                Spacer(Modifier.width(4.dp))
                Text("Settings")
            }
            OutlinedButton(
                onClick = onDiagnosticsClick,
                modifier = Modifier.weight(1f)
            ) {
                Icon(Icons.Default.BarChart, contentDescription = null)
                Spacer(Modifier.width(4.dp))
                Text("Diagnostics")
            }
        }

        if (isConnected) {
            Button(
                onClick = onDisconnectClick,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = OpenDisplayRed
                )
            ) {
                Icon(Icons.Default.LinkOff, contentDescription = null)
                Spacer(Modifier.width(4.dp))
                Text("Disconnect")
            }
        } else {
            Button(
                onClick = onConnectClick,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Link, contentDescription = null)
                Spacer(Modifier.width(4.dp))
                Text("Connect")
            }
        }
    }
}
