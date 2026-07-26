# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.led_models import (
    LedDeviceSettings,
    LedZoneSettings,
)
from thermalright_lcd_control.device_controller.led.zones import active_zone


def _settings(n, sync, interval):
    return LedDeviceSettings(
        zones=[LedZoneSettings() for _ in range(n)],
        zone_sync=sync, zone_sync_interval_ticks=interval, selected_zone=1,
    )


def test_no_sync_returns_selected():
    s = _settings(4, sync=False, interval=13)
    assert active_zone(s, tick=999) == 1


def test_sync_rotates_on_interval():
    s = _settings(4, sync=True, interval=10)
    assert active_zone(s, tick=0) == 0
    assert active_zone(s, tick=10) == 1
    assert active_zone(s, tick=45) == 4 % 4  # (45//10)=4 -> zone 0
