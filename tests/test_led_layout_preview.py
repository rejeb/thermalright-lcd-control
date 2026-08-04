# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.led.led_models import (
    LedDeviceSettings,
    LEDMode,
)
from thermalright_lcd_control.device_controller.led.styles import STYLES, LedStyle
from thermalright_lcd_control.gui.native.led.layout_preview import LayoutPreview


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_advance_computes_colors(app):
    pv = LayoutPreview()
    pv.set_style(STYLES[LedStyle.AX120])
    pv.set_settings(LedDeviceSettings(mode=LEDMode.STATIC, color=(200, 0, 0), brightness=100))
    pv.set_metrics({})
    pv.show()
    pv.advance()
    colors = pv.current_colors()
    assert len(colors) == STYLES[LedStyle.AX120].led_count
    assert colors[0] == (200, 0, 0)


def test_advance_noop_when_hidden(app):
    pv = LayoutPreview()
    pv.set_style(STYLES[LedStyle.AX120])
    pv.set_settings(LedDeviceSettings())
    pv.hide()
    pv.advance()
    assert pv.current_colors() == []
