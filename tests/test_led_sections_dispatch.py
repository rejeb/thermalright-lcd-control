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
from thermalright_lcd_control.gui.native.led.color_section import ColorSection
from thermalright_lcd_control.gui.native.led.mode_section import ModeSection


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_color_section_dispatches(app):
    seen = []
    sec = ColorSection(on_change=lambda s: seen.append(s))
    sec.load_settings(LedDeviceSettings())
    sec.set_color(10, 20, 30)
    assert seen[-1].color == (10, 20, 30)


def test_mode_section_dispatches(app):
    seen = []
    sec = ModeSection(on_change=lambda s: seen.append(s))
    sec.load_settings(LedDeviceSettings())
    sec.set_mode(LEDMode.RAINBOW)
    assert seen[-1].mode is LEDMode.RAINBOW
