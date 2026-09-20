package com.opendisplay.usb.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.opendisplay.usb.diagnostics.DiagnosticsSnapshot

enum class InputMode {
    TOUCH,
    STYLUS,
    TRACKPAD
}

/**
 * Modern floating in-stream toolbar overlay for OpenDisplay USB.
 *
 * Provides instant in-session access to:
 * - Live Latency & FPS HUD
 * - Stylus / Touch input mode switching
 * - Virtual productivity shortcuts (Esc, Win, Ctrl+Z)
 * - Clean one-tap disconnect
 */
@Composable
fun FloatingToolbar(
    diagnostics: DiagnosticsSnapshot,
    onDisconnect: () -> Unit,
    onSendShortcut: (String) -> Unit = {},
    modifier: Modifier = Modifier
) {
    var isExpanded by remember { mutableStateOf(false) }
    var selectedMode by remember { mutableStateOf(InputMode.TOUCH) }
    var showHud by remember { mutableStateOf(false) }

    Box(
        modifier = modifier.padding(16.dp),
        contentAlignment = Alignment.TopEnd
    ) {
        Column(
            horizontalAlignment = Alignment.End,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Live Mini-Pill (Always visible or toggleable)
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = Color(0xCC111622),
                shadowElevation = 8.dp,
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .clickable { isExpanded = !isExpanded }
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF00D26A))
                    )
                    Text(
                        text = "${diagnostics.fps.toInt()} FPS",
                        color = Color.White,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "•",
                        color = Color.Gray,
                        fontSize = 10.sp
                    )
                    Text(
                        text = "${diagnostics.decodeLatencyMs.toInt()} ms",
                        color = if (diagnostics.decodeLatencyMs < 20) Color(0xFF00D26A) else Color(0xFFFFB020),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = if (isExpanded) "▲" else "▼",
                        color = Color(0xFF90A4AE),
                        fontSize = 10.sp
                    )
                }
            }

            // Expanded Glassmorphic Drawer
            AnimatedVisibility(
                visible = isExpanded,
                enter = fadeIn() + expandVertically(),
                exit = fadeOut() + shrinkVertically()
            ) {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = Color(0xEB161C28),
                    shadowElevation = 12.dp,
                    modifier = Modifier.width(280.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "Stream Controls",
                            color = Color.White,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold
                        )

                        // Input Mode Selector
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            InputModeButton(
                                label = "Touch",
                                isSelected = selectedMode == InputMode.TOUCH,
                                onClick = { selectedMode = InputMode.TOUCH }
                            )
                            InputModeButton(
                                label = "Stylus",
                                isSelected = selectedMode == InputMode.STYLUS,
                                onClick = { selectedMode = InputMode.STYLUS }
                            )
                            InputModeButton(
                                label = "Trackpad",
                                isSelected = selectedMode == InputMode.TRACKPAD,
                                onClick = { selectedMode = InputMode.TRACKPAD }
                            )
                        }

                        // Productivity Shortcuts Row
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            ShortcutChip("Esc") { onSendShortcut("ESC") }
                            ShortcutChip("Win") { onSendShortcut("WIN") }
                            ShortcutChip("Task") { onSendShortcut("TASK") }
                            ShortcutChip("Undo") { onSendShortcut("UNDO") }
                        }

                        // Detailed HUD Info
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0x40000000),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(modifier = Modifier.padding(8.dp)) {
                                Text(
                                    text = "Throughput: ${(diagnostics.bitrateKbps / 1000f)} Mbps",
                                    color = Color(0xFFCFD8DC),
                                    fontSize = 11.sp
                                )
                                Text(
                                    text = "Frames: ${diagnostics.decodedFrames} decoded (${diagnostics.droppedFrames} dropped)",
                                    color = Color(0xFFCFD8DC),
                                    fontSize = 11.sp
                                )
                            }
                        }

                        // Disconnect Button
                        Button(
                            onClick = onDisconnect,
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFD32F2F)),
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = "Disconnect Display",
                                color = Color.White,
                                fontWeight = FontWeight.Bold,
                                fontSize = 13.sp
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun InputModeButton(
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = if (isSelected) Color(0xFF1976D2) else Color(0x33FFFFFF),
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
    ) {
        Text(
            text = label,
            color = if (isSelected) Color.White else Color(0xFFB0BEC5),
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
        )
    }
}

@Composable
private fun ShortcutChip(
    label: String,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = Color(0x2EFFFFFF),
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .clickable(onClick = onClick)
    ) {
        Text(
            text = label,
            color = Color(0xFFECEFF1),
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}
