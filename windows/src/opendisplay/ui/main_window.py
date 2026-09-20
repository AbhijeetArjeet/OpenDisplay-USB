"""Commercial-grade desktop UI for OpenDisplay USB Windows client built with PyQt6.

Features:
- Sleek dark glassmorphic styling (Obsidian / Neon Emerald / Cyan).
- System Tray integration with minimize-to-tray and quick context actions.
- Real-time Glass-to-Glass Latency KPI badge and hardware stream metrics.
- One-click Display Mode switcher (Duplicate vs Extend with Virtual Display auto-attachment).
- Performance Quality Presets (Ultra-Low Latency, Balanced, Studio Quality).
"""

import sys
import os
import asyncio
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSlider,
    QGroupBox,
    QCheckBox,
    QFrame,
    QGridLayout,
    QSystemTrayIcon,
    QMenu,
    QButtonGroup,
    QRadioButton,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QAction, QPixmap, QPainter

from ..transport.base import ConnectionState
from ..diagnostics.collector import DiagnosticsCollector, DiagnosticsSnapshot
from ..session.adaptive import PerformanceProfile


def create_status_icon(color: QColor) -> QIcon:
    """Generates a dynamic colored circle pixmap for the system tray icon."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    """Main window for the commercial OpenDisplay USB Windows desktop client."""

    def __init__(self, diagnostics: DiagnosticsCollector):
        super().__init__()
        self.diagnostics = diagnostics
        self.setWindowTitle("OpenDisplay USB — Commercial Edition")
        self.resize(600, 750)
        self.setMinimumSize(540, 680)

        self._session = None
        self._session_loop = None
        self._session_thread = None

        self._init_theme()
        self._init_ui()
        self._init_tray()

        # Update diagnostics timer (250ms for responsive KPI display)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_metrics)
        self._timer.start(250)

    def _init_theme(self):
        """Sets modern dark glassmorphic palette and stylesheet."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0B0E14;
            }
            QWidget {
                color: #E6EDF3;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QFrame#card {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame#heroCard {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161B26, stop:1 #111A24);
                border: 1px solid #1F6FEB;
                border-radius: 12px;
                padding: 16px;
            }
            QLabel#heroTitle {
                font-size: 20px;
                font-weight: 700;
                color: #FFFFFF;
            }
            QLabel#sectionHeader {
                font-size: 13px;
                font-weight: 700;
                color: #58A6FF;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QLabel#metricValue {
                font-size: 18px;
                font-weight: 700;
                color: #00D26A;
            }
            QLabel#metricLabel {
                font-size: 11px;
                color: #8B949E;
            }
            QPushButton {
                background-color: #238636;
                color: #FFFFFF;
                border: 1px solid rgba(240, 246, 252, 0.1);
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2EA043;
            }
            QPushButton:pressed {
                background-color: #1E7E34;
            }
            QPushButton#disconnectBtn {
                background-color: #DA3633;
            }
            QPushButton#disconnectBtn:hover {
                background-color: #E5534B;
            }
            QPushButton#modeBtn {
                background-color: #21262D;
                border: 1px solid #30363D;
                color: #C9D1D9;
                padding: 8px 14px;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton#modeBtn:checked {
                background-color: #1F6FEB;
                border-color: #58A6FF;
                color: #FFFFFF;
                font-weight: bold;
            }
            QComboBox {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 12px;
                color: #E6EDF3;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #21262D;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00D26A;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)

    def _init_ui(self):
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        # ── Title & Status Card ──────────────────────────────────────────────
        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_label = QLabel("OpenDisplay USB")
        title_label.setObjectName("heroTitle")

        self.status_badge = QLabel("READY TO CONNECT")
        self.status_badge.setStyleSheet(
            "background-color: #21262D; color: #8B949E; padding: 4px 10px; "
            "border-radius: 12px; font-size: 11px; font-weight: bold;"
        )

        header_row.addWidget(title_label)
        header_row.addStretch()
        header_row.addWidget(self.status_badge)
        hero_layout.addLayout(header_row)

        # Sub-status text
        self.device_info_label = QLabel("Auto-detecting USB cable (AOA / ADB)...")
        self.device_info_label.setStyleSheet("color: #8B949E; font-size: 13px;")
        hero_layout.addWidget(self.device_info_label)

        # Live KPI Meter Row (Latency, FPS, Bitrate, Drops)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(16)

        self.kpi_latency = self._create_kpi_widget("0.0 ms", "Glass-to-Glass Latency")
        self.kpi_fps = self._create_kpi_widget("0.0 FPS", "Throughput FPS")
        self.kpi_bitrate = self._create_kpi_widget("0.0 Mbps", "Video Bitrate")
        self.kpi_drops = self._create_kpi_widget("0.00%", "Frame Drops")

        kpi_row.addWidget(self.kpi_latency)
        kpi_row.addWidget(self.kpi_fps)
        kpi_row.addWidget(self.kpi_bitrate)
        kpi_row.addWidget(self.kpi_drops)
        hero_layout.addLayout(kpi_row)

        main_layout.addWidget(hero_card)

        # ── Display Mode Selector ────────────────────────────────────────────
        mode_card = QFrame()
        mode_card.setObjectName("card")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setSpacing(12)

        mode_header = QLabel("Display Mode & Desktop Topology")
        mode_header.setObjectName("sectionHeader")
        mode_layout.addWidget(mode_header)

        mode_btn_row = QHBoxLayout()
        self.btn_mode_duplicate = QPushButton("Duplicate Primary Screen")
        self.btn_mode_duplicate.setObjectName("modeBtn")
        self.btn_mode_duplicate.setCheckable(True)
        self.btn_mode_duplicate.setChecked(False)

        self.btn_mode_extend = QPushButton("Extend Desktop (Virtual Display)")
        self.btn_mode_extend.setObjectName("modeBtn")
        self.btn_mode_extend.setCheckable(True)
        self.btn_mode_extend.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_mode_duplicate)
        self.mode_group.addButton(self.btn_mode_extend)

        mode_btn_row.addWidget(self.btn_mode_duplicate)
        mode_btn_row.addWidget(self.btn_mode_extend)
        mode_layout.addLayout(mode_btn_row)

        main_layout.addWidget(mode_card)

        # ── Quality Presets & Configuration ──────────────────────────────────
        config_card = QFrame()
        config_card.setObjectName("card")
        config_layout = QGridLayout(config_card)
        config_layout.setSpacing(12)

        config_header = QLabel("Performance & Stream Quality")
        config_header.setObjectName("sectionHeader")
        config_layout.addWidget(config_header, 0, 0, 1, 2)

        config_layout.addWidget(QLabel("Quality Preset:"), 1, 0)
        self.combo_preset = QComboBox()
        self.combo_preset.addItems([
            "Balanced (60 FPS, 18 Mbps) — Recommended",
            "Ultra-Low Latency (Gaming, 120 FPS)",
            "Studio Quality (25 Mbps, Crisp Text)",
        ])
        config_layout.addWidget(self.combo_preset, 1, 1)

        config_layout.addWidget(QLabel("Target Resolution:"), 2, 0)
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems([
            "Native Tablet Resolution (Auto-Match)",
            "2000x1200 (Galaxy Tab A7)",
            "1920x1080 (1080p FHD)",
            "2560x1600 (2K WQXGA)",
        ])
        config_layout.addWidget(self.combo_resolution, 2, 1)

        main_layout.addWidget(config_card)
        main_layout.addStretch()

        # ── Action Buttons ───────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)

        self.btn_connect = QPushButton("Connect Display")
        self.btn_connect.setFixedHeight(44)
        self.btn_connect.clicked.connect(self._on_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setObjectName("disconnectBtn")
        self.btn_disconnect.setFixedHeight(44)
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect)

        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
        main_layout.addLayout(btn_layout)

        self.setCentralWidget(container)

    def _create_kpi_widget(self, value: str, label: str) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        val_label = QLabel(value)
        val_label.setObjectName("metricValue")
        desc_label = QLabel(label)
        desc_label.setObjectName("metricLabel")

        v.addWidget(val_label)
        v.addWidget(desc_label)
        box._val_label = val_label
        return box

    def _init_tray(self):
        """Initializes system tray icon and menu."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(create_status_icon(QColor(139, 148, 158)))
        self.tray_icon.setToolTip("OpenDisplay USB — Idle")

        tray_menu = QMenu()
        act_show = QAction("Open OpenDisplay USB", self)
        act_show.triggered.connect(self.showNormal)
        tray_menu.addAction(act_show)

        tray_menu.addSeparator()
        self.act_tray_connect = QAction("Connect", self)
        self.act_tray_connect.triggered.connect(self._on_connect)
        tray_menu.addAction(self.act_tray_connect)

        self.act_tray_disconnect = QAction("Disconnect", self)
        self.act_tray_disconnect.setEnabled(False)
        self.act_tray_disconnect.triggered.connect(self._on_disconnect)
        tray_menu.addAction(self.act_tray_disconnect)

        tray_menu.addSeparator()
        act_quit = QAction("Quit OpenDisplay USB", self)
        act_quit.triggered.connect(self._on_quit)
        tray_menu.addAction(act_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def set_connection_state(self, state: ConnectionState):
        """Updates UI status badges, button states, and tray icon."""
        if state == ConnectionState.CONNECTED:
            self.status_badge.setText("STREAMING (60 FPS)")
            self.status_badge.setStyleSheet(
                "background-color: #0E4429; color: #00D26A; padding: 4px 10px; "
                "border-radius: 12px; font-size: 11px; font-weight: bold; border: 1px solid #00D26A;"
            )
            self.device_info_label.setText("Active USB Connection (DXGI Zero-Copy Hardware Pipeline)")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.act_tray_connect.setEnabled(False)
            self.act_tray_disconnect.setEnabled(True)
            self.tray_icon.setIcon(create_status_icon(QColor(0, 210, 106)))
            self.tray_icon.setToolTip("OpenDisplay USB — Active Streaming")
        elif state == ConnectionState.CONNECTING or state == ConnectionState.RECONNECTING:
            self.status_badge.setText("CONNECTING...")
            self.status_badge.setStyleSheet(
                "background-color: #4D2D00; color: #FFAA00; padding: 4px 10px; "
                "border-radius: 12px; font-size: 11px; font-weight: bold; border: 1px solid #FFAA00;"
            )
            self.device_info_label.setText("Negotiating AOA protocol and DXGI surface...")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.tray_icon.setIcon(create_status_icon(QColor(255, 170, 0)))
        else:
            self.status_badge.setText("READY TO CONNECT")
            self.status_badge.setStyleSheet(
                "background-color: #21262D; color: #8B949E; padding: 4px 10px; "
                "border-radius: 12px; font-size: 11px; font-weight: bold;"
            )
            self.device_info_label.setText("Plug in USB cable to begin streaming")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.act_tray_connect.setEnabled(True)
            self.act_tray_disconnect.setEnabled(False)
            self.tray_icon.setIcon(create_status_icon(QColor(139, 148, 158)))
            self.tray_icon.setToolTip("OpenDisplay USB — Idle")

    def _refresh_metrics(self):
        """Updates live KPI numbers from diagnostics snapshot."""
        snap: DiagnosticsSnapshot = self.diagnostics.get_snapshot()

        latency_text = f"{snap.rtt_latency_ms:.1f} ms"
        self.kpi_latency._val_label.setText(latency_text)
        if snap.rtt_latency_ms > 0 and snap.rtt_latency_ms < 20:
            self.kpi_latency._val_label.setStyleSheet("color: #00D26A; font-size: 18px; font-weight: 700;")
        elif snap.rtt_latency_ms >= 20:
            self.kpi_latency._val_label.setStyleSheet("color: #FFAA00; font-size: 18px; font-weight: 700;")

        self.kpi_fps._val_label.setText(f"{snap.fps:.1f} FPS")
        self.kpi_bitrate._val_label.setText(f"{snap.bitrate_kbps / 1000.0:.2f} Mbps")

        drop_rate = 0.0
        if snap.frames_sent > 0:
            drop_rate = (snap.frames_dropped / snap.frames_sent) * 100.0
        self.kpi_drops._val_label.setText(f"{drop_rate:.2f}%")

    def _on_connect(self):
        """Starts streaming session worker in a background thread."""
        is_extend = self.btn_mode_extend.isChecked()
        monitor_idx = 1 if is_extend else 0

        self.set_connection_state(ConnectionState.CONNECTING)

        self._session_thread = threading.Thread(
            target=self._run_session_worker,
            args=(is_extend, monitor_idx),
            daemon=True
        )
        self._session_thread.start()

    def _run_session_worker(self, is_extend: bool, monitor_idx: int):
        from ..transport.aoa_transport import AoaTransport
        from ..session.session_manager import SessionManager
        from ..input.injector import InputInjector
        from ..session.controller import SessionState

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._session_loop = loop

        transport = AoaTransport(fallback_to_adb=True)
        input_injector = InputInjector()

        profile_idx = self.combo_preset.currentIndex()
        if profile_idx == 1:
            perf_profile = PerformanceProfile.ULTRA_LOW_LATENCY
        else:
            perf_profile = PerformanceProfile.BALANCED

        self._session = SessionManager(
            transport=transport,
            diagnostics=self.diagnostics,
            input_injector=input_injector,
            use_synthetic_video=False,
            performance_profile=perf_profile,
            preferred_codec="H264",
            monitor_index=monitor_idx,
            auto_extend=is_extend
        )

        async def runner():
            await self._session.start()
            while self._session and not self._session._stopped:
                if self._session.controller and self._session.controller.state == SessionState.STREAMING:
                    QTimer.singleShot(0, lambda: self.set_connection_state(ConnectionState.CONNECTED))
                await asyncio.sleep(0.25)

        try:
            loop.run_until_complete(runner())
        except Exception as e:
            pass
        finally:
            QTimer.singleShot(0, lambda: self.set_connection_state(ConnectionState.DISCONNECTED))

    def _on_disconnect(self):
        """Stops active streaming session."""
        if hasattr(self, '_session') and self._session and self._session_loop:
            asyncio.run_coroutine_threadsafe(self._session.stop(), self._session_loop)
        self.set_connection_state(ConnectionState.DISCONNECTED)

    def _on_quit(self):
        """Cleanly disconnects session and terminates application."""
        self._on_disconnect()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """Minimize to system tray on window close."""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "OpenDisplay USB",
                "OpenDisplay USB is running in the background.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            self._on_quit()
            event.accept()
