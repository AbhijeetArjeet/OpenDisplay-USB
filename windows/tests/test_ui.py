"""Smoke and unit tests for OpenDisplay USB commercial UI."""

import sys
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from opendisplay.diagnostics.collector import DiagnosticsCollector
from opendisplay.ui.main_window import MainWindow
from opendisplay.transport.base import ConnectionState

# Shared QApplication instance for test process
app = QApplication.instance() or QApplication(sys.argv)


def test_main_window_creation():
    diagnostics = DiagnosticsCollector()
    window = MainWindow(diagnostics=diagnostics)
    assert window is not None
    assert "OpenDisplay USB" in window.windowTitle()
    assert window.btn_connect.isEnabled() is True
    assert window.btn_disconnect.isEnabled() is False


def test_main_window_state_transitions():
    diagnostics = DiagnosticsCollector()
    window = MainWindow(diagnostics=diagnostics)

    window.set_connection_state(ConnectionState.CONNECTING)
    assert "CONNECTING" in window.status_badge.text()
    assert window.btn_connect.isEnabled() is False

    window.set_connection_state(ConnectionState.CONNECTED)
    assert "STREAMING" in window.status_badge.text()
    assert window.btn_disconnect.isEnabled() is True

    window.set_connection_state(ConnectionState.DISCONNECTED)
    assert "READY" in window.status_badge.text()
    assert window.btn_connect.isEnabled() is True
