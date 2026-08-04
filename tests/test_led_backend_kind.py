# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.device_controller.led.led_models import LEDMode
from thermalright_lcd_control.gui.backend.app_backend import AppBackend
from thermalright_lcd_control.gui.utils.config_loader import load_config


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _led_backend(tmp_path):
    config = load_config("resources/gui_config.yaml")
    config.setdefault("paths", {})["service_config"] = str(tmp_path)
    led = {"vid": 0x0416, "pid": 0x8001, "id": "led_0416_8001",
           "kind": "led", "mock": True, "style": "PA120"}
    return AppBackend(config, [led])


def test_led_device_does_not_crash_and_reports_kind(app, tmp_path):
    backend = _led_backend(tmp_path)
    assert backend.active_device_kind() == "led"


def test_led_settings_default_and_roundtrip(app, tmp_path):
    backend = _led_backend(tmp_path)
    s = backend.get_led_settings()
    assert s is not None
    s.mode = LEDMode.RAINBOW
    backend.update_led_settings(s)
    assert backend.get_led_settings().mode is LEDMode.RAINBOW
