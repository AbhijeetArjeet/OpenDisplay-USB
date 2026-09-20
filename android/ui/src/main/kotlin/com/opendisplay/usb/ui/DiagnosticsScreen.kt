package com.opendisplay.usb.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.opendisplay.usb.diagnostics.DiagnosticsSnapshot

/**
 * Diagnostics screen presenting real-time performance and stream metrics.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiagnosticsScreen(
    snapshot: DiagnosticsSnapshot,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Stream Diagnostics") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        },
        modifier = modifier
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            MetricCard("Video Metrics") {
                MetricRow("Framerate", "%.1f FPS".format(snapshot.fps))
                MetricRow("Resolution", if (snapshot.currentWidthPx > 0) "${snapshot.currentWidthPx}×${snapshot.currentHeightPx}" else "None")
                MetricRow("Codec", snapshot.currentCodec)
                MetricRow("Video Bitrate", "%.1f Mbps".format(snapshot.bitrateKbps / 1000f))
                MetricRow("Decoded Frames", "${snapshot.decodedFrames}")
                MetricRow("Dropped Frames", "${snapshot.droppedFrames}")
                MetricRow("Decode Errors", "${snapshot.decodeErrors}")
            }

            MetricCard("Transport & Network") {
                MetricRow("Throughput", "%.1f Mbps".format(snapshot.transportThroughputKbps / 1000f))
                MetricRow("Reconnect Count", "${snapshot.reconnectCount}")
            }

            MetricCard("Audio & Latency") {
                MetricRow("Decode Latency", "%.1f ms".format(snapshot.decodeLatencyMs))
                MetricRow("Audio Latency", "%.1f ms".format(snapshot.audioLatencyMs))
                MetricRow("Audio Buffer", "%.1f ms".format(snapshot.audioBufferMs))
                MetricRow("A/V Drift", "%.1f ms".format(snapshot.avDriftMs))
            }

            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun MetricCard(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 4.dp)
            )
            content()
        }
    }
}

@Composable
private fun MetricRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = label, style = MaterialTheme.typography.bodyMedium)
        Text(text = value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
    }
}
