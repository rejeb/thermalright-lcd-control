# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.common.supported_devices import (
    all_device_kinds,
    led_supported_devices,
)


def test_led_entry_present_and_not_mocked():
    leds = led_supported_devices()
    entry = next(e for e in leds if e["vid"] == 0x0416 and e["pid"] == 0x8001)
    assert entry["kind"] == "led"
    assert "mock" not in entry        # no more dummy device
    assert "style" not in entry       # style resolved at detection via handshake


def test_kinds_include_lcd_and_led():
    assert "lcd" in all_device_kinds()
    assert "led" in all_device_kinds()
