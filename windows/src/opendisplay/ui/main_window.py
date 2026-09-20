"""Modern desktop UI for OpenDisplay USB Windows client built with PyQt6."""

import sys
import asyncio
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
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette
from ..transport.base import ConnectionState
from ..diagnostics.collector import DiagnosticsCollector, DiagnosticsSnapshot


class MainWindow(QMainWindow):
    """Main window for the OpenDisplay USB Windows desktop client."""

    def __init__(self, diagnostics: DiagnosticsCollector):
        super().__init__()
        self.diagnostics = diagnostics
        self.setWindowTitle("OpenDisplay USB — Windows Client")
        self.resize(560, 680)
        self.setMinimumSize(480, 600)

        self._init_theme()
        self._init_ui()

        # Update diagnostics timer (500ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_metrics)
        self._timer.start(500)

    def _init_theme(self):
        """Sets modern dark theme palette and stylesheet."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(24, 28, 36))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Base, QColor(32, 38, 48))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(24, 28, 36))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Button, QColor(42, 50, 64))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
        self.setPalette(palette)

        self.setStyleSheet("""
            QMainWindow { background-color: #181C24; }
            QGroupBox {
                border: 1px solid #323C4E;
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #81C784;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 4px; }
            QLabel { color: #E0E0E0; }
            QPushButton {
                background-color: #2E7D32;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:pressed { background-color: #1B5E20; }
            QPushButton#disconnectBtn { background-color: #C62828; }
            QPushButton#disconnectBtn:hover { background-color: #D32F2F; }
            QComboBox {
                background-color: #262E3B;
                border: 1px solid #3E4A5F;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #323C4E;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4CAF50;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)

    def _init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title_label = QLabel("OpenDisplay USB")
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Status Bar Card
        status_box = QFrame()
        status_box.setStyleSheet("background-color: #202632; border-radius: 10px; padding: 12px;")
        status_layout = QHBoxLayout(status_box)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #757575; font-size: 16px;")
        self.status_text = QLabel("Not Connected")
        self.status_text.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        layout.addWidget(status_box)

        # Display Settings
        settings_group = QGroupBox("Display & Stream Configuration")
        grid = QGridLayout(settings_group)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Resolution:"), 0, 0)
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["1920x1080 (1080p)", "2000x1200 (Tablet)", "2560x1600 (2K)", "1280x800"])
        grid.addWidget(self.combo_resolution, 0, 1)

        grid.addWidget(QLabel("Frame Rate:"), 1, 0)
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["60 FPS", "120 FPS", "30 FPS"])
        grid.addWidget(self.combo_fps, 1, 1)

        grid.addWidget(QLabel("Bitrate:"), 2, 0)
        self.bitrate_slider = QSlider(Qt.Orientation.Horizontal)
        self.bitrate_slider.setRange(4, 25)
        self.bitrate_slider.setValue(10)
        self.bitrate_label = QLabel("10 Mbps")
        self.bitrate_slider.valueChanged.connect(lambda v: self.bitrate_label.setText(f"{v} Mbps"))

        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(self.bitrate_slider)
        bitrate_layout.addWidget(self.bitrate_label)
        grid.addLayout(bitrate_layout, 2, 1)

        self.check_mock = QCheckBox("Use Mock Loopback Transport (Test Mode)")
        self.check_mock.setChecked(True)
        grid.addWidget(self.check_mock, 3, 0, 1, 2)

        layout.addWidget(settings_group)

        # Diagnostics Panel
        diag_group = QGroupBox("Real-time Stream Diagnostics")
        diag_layout = QGridLayout(diag_group)
        diag_layout.setSpacing(8)

        self.diag_fps = QLabel("0.0 FPS")
        self.diag_bitrate = QLabel("0.0 Mbps")
        self.diag_latency = QLabel("0.0 ms")
        self.diag_frames = QLabel("0 frames (0 key)")

        diag_layout.addWidget(QLabel("Current FPS:"), 0, 0)
        diag_layout.addWidget(self.diag_fps, 0, 1)
        diag_layout.addWidget(QLabel("Video Throughput:"), 1, 0)
        diag_layout.addWidget(self.diag_bitrate, 1, 1)
        diag_layout.addWidget(QLabel("Round-trip Latency:"), 2, 0)
        diag_layout.addWidget(self.diag_latency, 2, 1)
        diag_layout.addWidget(QLabel("Streamed Frames:"), 3, 0)
        diag_layout.addWidget(self.diag_frames, 3, 1)

        layout.addWidget(diag_group)
        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect Display")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setObjectName("disconnectBtn")
        self.btn_disconnect.setEnabled(False)

        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
        layout.addLayout(btn_layout)

        self.setCentralWidget(main_widget)

    def set_connection_state(self, state: ConnectionState):
        """Updates the status dot and text based on connection state."""
        if state == ConnectionState.CONNECTED:
            self.status_dot.setStyleSheet("color: #4CAF50; font-size: 16px;")
            self.status_text.setText("Connected & Streaming")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        elif state == ConnectionState.CONNECTING or state == ConnectionState.RECONNECTING:
            self.status_dot.setStyleSheet("color: #FFC107; font-size: 16px;")
            self.status_text.setText("Connecting...")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        else:
            self.status_dot.setStyleSheet("color: #757575; font-size: 16px;")
            self.status_text.setText("Not Connected")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    def _refresh_metrics(self):
        snap: DiagnosticsSnapshot = self.diagnostics.get_snapshot()
        self.diag_fps.setText(f"{snap.fps:.1f} FPS")
        self.diag_bitrate.setText(f"{snap.bitrate_kbps / 1000.0:.2f} Mbps")
        self.diag_latency.setText(f"{snap.rtt_latency_ms:.1f} ms")
        self.diag_frames.setText(f"{snap.frames_sent} frames ({snap.keyframes_sent} key)")
