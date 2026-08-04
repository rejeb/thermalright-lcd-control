# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from unittest import mock

from thermalright_lcd_control.device_controller.led import detect as led_detect
from thermalright_lcd_control.device_controller.led.styles import LedStyle
from thermalright_lcd_control.gui.shared.bootstrap import append_led_devices


def test_no_led_hardware_appends_nothing():
    existing = [{"vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240, "id": "t"}]
    with mock.patch.object(led_detect, "_is_present", return_value=False):
        out = append_led_devices(existing)
    assert out == existing   # nothing detected → unchanged


def test_detected_led_device_is_appended_with_resolved_style():
    existing = [{"vid": 0x0416, "pid": 0x5302, "width": 320, "height": 240, "id": "t"}]
    with mock.patch.object(led_detect, "_is_present", return_value=True), \
         mock.patch.object(led_detect, "_handshake_style", return_value=LedStyle.PA120):
        out = append_led_devices(existing)
    led = next(d for d in out if d.get("kind") == "led")
    assert led["id"] == "led_0416_8001"
    assert led["style"] == "PA120"
    assert existing[0] in out   # existing preserved


def test_detection_failure_does_not_break_startup():
    existing = [{"vid": 0x0416, "pid": 0x5302, "id": "t"}]
    with mock.patch.object(led_detect, "detect_led_devices",
                           side_effect=RuntimeError("boom")):
        out = append_led_devices(existing)
    assert out == existing   # error swallowed, existing preserved
