# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from thermalright_lcd_control.gui.native.main_window import NativeMainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_led_device_switches_central_to_led(app):
    led = {"vid": 0x0416, "pid": 0x8001, "id": "led_0416_8001",
           "kind": "led", "mock": True, "style": "PA120"}
    win = NativeMainWindow("resources/gui_config.yaml", [led])
    try:
        assert win.central_kind() == "led"
        # PA120 (real trcc counts) has 4 zones; Segments section was removed
        assert win.led_panel.section_visible("zones") is True
    finally:
        win._really_quit = True
        win.close()
