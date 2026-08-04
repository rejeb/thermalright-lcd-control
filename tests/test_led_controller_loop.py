# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.led_models import (
    LedDeviceSettings,
    LEDMode,
)
from thermalright_lcd_control.device_controller.led.mock import MockLedDevice
from thermalright_lcd_control.device_controller.led.styles import LedStyle
from thermalright_lcd_control.device_controller.led_controller import LedController


def test_loop_sends_frames_to_sink():
    dev = MockLedDevice(LedStyle.AX120)
    dev.handshake()
    s = LedDeviceSettings(mode=LEDMode.STATIC, color=(200, 0, 0), brightness=50)
    ctrl = LedController(dev, lambda: s, lambda: {})
    ctrl.run_ticks(3)
    assert len(dev.sink.frames) == 3
    # static red 50% baked -> 100, then *0.4 scale -> 40
    assert dev.sink.decode_last()[0] == (40, 0, 0)


def test_rainbow_frames_differ_over_ticks():
    dev = MockLedDevice(LedStyle.AX120)
    dev.handshake()
    s = LedDeviceSettings(mode=LEDMode.RAINBOW)
    ctrl = LedController(dev, lambda: s, lambda: {})
    ctrl.tick(0)
    first = dev.sink.decode_last()
    ctrl.tick(5)
    second = dev.sink.decode_last()
    assert first != second
