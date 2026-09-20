"""Tests for Windows High-Precision Touch and Stylus Input Injector."""

from unittest.mock import MagicMock, patch
from opendisplay.input.injector import (
    InputInjector,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_MOVE,
)
from opendisplay.protocol import InputEventMessage, PointerInfo


def test_input_injector_bounds_update():
    inj = InputInjector(0, 0, 1920, 1080)
    assert inj.origin_x == 0
    assert inj.origin_y == 0
    assert inj.width == 1920
    assert inj.height == 1080

    # Simulate secondary monitor extension beside primary
    inj.update_bounds(1920, 0, 2000, 1200)
    assert inj.origin_x == 1920
    assert inj.origin_y == 0
    assert inj.width == 2000
    assert inj.height == 1200


def test_input_injector_normalization():
    inj = InputInjector(0, 0, 1920, 1080)

    # Test coordinate mapping
    win_x, win_y = inj.normalize_to_screen(0.5, 0.5)
    assert 0 <= win_x <= 65535
    assert 0 <= win_y <= 65535


def test_input_injector_touch_down_up():
    inj = InputInjector(0, 0, 1920, 1080)

    with patch.object(inj._user32, "SendInput") as mock_send:
        # DOWN
        msg_down = InputEventMessage(
            eventType="TOUCH",
            timestampNs=1000,
            pointers=[
                PointerInfo(id=0, action="DOWN", x=0.25, y=0.5, pressure=1.0, toolType="FINGER")
            ],
        )
        inj.inject_event(msg_down)
        assert mock_send.called
        assert inj.last_injected_input.u.mi.dwFlags & MOUSEEVENTF_LEFTDOWN

        # UP
        msg_up = InputEventMessage(
            eventType="TOUCH",
            timestampNs=2000,
            pointers=[
                PointerInfo(id=0, action="UP", x=0.25, y=0.5, pressure=0.0, toolType="FINGER")
            ],
        )
        inj.inject_event(msg_up)
        assert inj.last_injected_input.u.mi.dwFlags & MOUSEEVENTF_LEFTUP


def test_input_injector_stylus_barrel_button_right_click():
    inj = InputInjector(0, 0, 1920, 1080)

    with patch.object(inj._user32, "SendInput") as mock_send:
        # S-Pen DOWN with barrel button pressed (buttons = 2)
        msg_pen = InputEventMessage(
            eventType="STYLUS",
            timestampNs=1000,
            pointers=[
                PointerInfo(
                    id=0, action="DOWN", x=0.5, y=0.5, pressure=0.8,
                    toolType="STYLUS", buttons=2
                )
            ],
        )
        inj.inject_event(msg_pen)
        assert mock_send.called
        assert inj.last_injected_input.u.mi.dwFlags & MOUSEEVENTF_RIGHTDOWN


def test_input_injector_stylus_hover():
    inj = InputInjector(0, 0, 1920, 1080)

    with patch.object(inj._user32, "SendInput") as mock_send:
        # S-Pen HOVER (cursor moves without clicking)
        msg_hover = InputEventMessage(
            eventType="STYLUS",
            timestampNs=1000,
            pointers=[
                PointerInfo(
                    id=0, action="HOVER", x=0.3, y=0.4, pressure=0.0,
                    toolType="STYLUS"
                )
            ],
        )
        inj.inject_event(msg_hover)
        assert mock_send.called
        assert inj.last_injected_input.u.mi.dwFlags & MOUSEEVENTF_MOVE
        assert not (inj.last_injected_input.u.mi.dwFlags & MOUSEEVENTF_LEFTDOWN)
        assert not (inj.last_injected_input.u.mi.dwFlags & MOUSEEVENTF_RIGHTDOWN)
