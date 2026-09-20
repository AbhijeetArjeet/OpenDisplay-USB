"""Tests for Windows Virtual Display Manager."""

import pytest
from unittest.mock import MagicMock, patch
from opendisplay.display.virtual_display import (
    VirtualDisplayManager,
    VirtualDisplayInfo,
    DisplayResolution,
)


def test_virtual_display_manager_init():
    vdm = VirtualDisplayManager()
    assert vdm is not None
    assert vdm._attached_by_us is False


def test_virtual_display_discovery_mocked():
    vdm = VirtualDisplayManager()

    mock_displays = [
        VirtualDisplayInfo(
            device_name=r"\\.\DISPLAY1",
            device_string="AMD Radeon(TM) Graphics",
            device_id="PCI\\VEN_1002&DEV_164C",
            is_attached=True,
            is_primary=True,
            current_width=1920,
            current_height=1080,
            current_refresh=144,
        ),
        VirtualDisplayInfo(
            device_name=r"\\.\DISPLAY61",
            device_string="Virtual Display Driver",
            device_id="ROOT\\MttVDD",
            is_attached=False,
            is_primary=False,
            current_width=0,
            current_height=0,
            current_refresh=0,
            supported_resolutions=[
                DisplayResolution(1920, 1080, 60),
                DisplayResolution(2000, 1200, 60),
                DisplayResolution(2560, 1440, 60),
            ],
        ),
    ]

    with patch.object(vdm, "enumerate_displays", return_value=mock_displays):
        primary = vdm.get_primary_display()
        assert primary is not None
        assert primary.device_name == r"\\.\DISPLAY1"
        assert primary.is_primary is True

        vds = vdm.find_virtual_displays()
        assert len(vds) == 1
        assert vds[0].device_name == r"\\.\DISPLAY61"
        assert "Virtual" in vds[0].device_string

        # Test auto_configure_for_client with tablet resolution
        mode = vdm.auto_configure_for_client(2000, 1200, 60.0)
        assert mode is not None
        assert mode.width == 2000
        assert mode.height == 1200
        assert mode.refresh_rate == 60


def test_teardown_cleans_up_when_attached():
    vdm = VirtualDisplayManager()
    vdm._attached_by_us = True

    with patch.object(vdm, "disable_extend_mode", return_value=True) as mock_disable:
        vdm.teardown()
        mock_disable.assert_called_once()
        assert vdm._attached_by_us is False


def test_real_virtual_display_manager_live():
    """Validates that real Windows Win32 API calls execute without error."""
    vdm = VirtualDisplayManager()
    displays = vdm.enumerate_displays()
    assert len(displays) > 0

    primary = vdm.get_primary_display()
    assert primary is not None
    assert primary.current_width > 0
    assert primary.current_height > 0
