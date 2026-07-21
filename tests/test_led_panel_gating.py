# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from thermalright_lcd_control.gui.native.led.panel import LedPanel
from thermalright_lcd_control.device_controller.led.styles import STYLES, LedStyle


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_single_zone_style_hides_zones(app):
    panel = LedPanel(on_change=lambda s: None)
    panel.apply_style(STYLES[LedStyle.LC2])   # zone_count == 1
    assert panel.section_visible("zones") is False
    assert panel.section_visible("color") is True


def test_lc2_shows_advanced(app):
    panel = LedPanel(on_change=lambda s: None)
    panel.apply_style(STYLES[LedStyle.LC2])   # clock rides in Advanced
    assert panel.section_visible("advanced") is True


def test_multizone_shows_zones(app):
    panel = LedPanel(on_change=lambda s: None)
    panel.apply_style(STYLES[LedStyle.PA120])   # 4 zones
    assert panel.section_visible("zones") is True


def test_no_segments_section(app):
    panel = LedPanel(on_change=lambda s: None)
    panel.apply_style(STYLES[LedStyle.PA120])
    with pytest.raises(KeyError):
        panel.section_visible("segments")   # removed entirely
