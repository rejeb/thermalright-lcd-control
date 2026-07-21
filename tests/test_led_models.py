# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.led_models import (
    LEDMode, LedDeviceSettings, LedZoneSettings,
)


def test_defaults():
    s = LedDeviceSettings()
    assert s.mode is LEDMode.STATIC
    assert s.color == (255, 0, 0)
    assert s.brightness == 65
    assert s.global_on is True
    assert s.zones == []
    assert s.segment_on == []
    assert s.temp_source == "cpu"
    assert s.memory_ratio == 2


def test_roundtrip_dict():
    s = LedDeviceSettings(
        mode=LEDMode.RAINBOW,
        color=(10, 20, 30),
        zones=[LedZoneSettings(mode=LEDMode.STATIC, color=(1, 2, 3), brightness=50, on=False)],
        segment_on=[True, False, True],
    )
    restored = LedDeviceSettings.from_dict(s.to_dict())
    assert restored == s
