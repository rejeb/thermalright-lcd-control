# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.effects import compute, ComputeResult
from thermalright_lcd_control.device_controller.led.led_models import (
    LedDeviceSettings, LEDMode,
)
from thermalright_lcd_control.device_controller.led.styles import STYLES, LedStyle


def test_static_fills_all_leds_with_brightness_baked():
    si = STYLES[LedStyle.AX120]
    s = LedDeviceSettings(mode=LEDMode.STATIC, color=(200, 0, 0), brightness=50)
    res = compute(s, si, tick=0, metrics={})
    assert isinstance(res, ComputeResult)
    assert len(res.colors) == si.led_count
    # brightness 50% baked: 200*0.5=100
    assert res.colors[0] == (100, 0, 0)


def test_global_off_reports_all_off():
    si = STYLES[LedStyle.AX120]
    s = LedDeviceSettings(mode=LEDMode.STATIC, global_on=False)
    res = compute(s, si, tick=0, metrics={})
    assert res.global_on is False
    assert all(v is False for v in res.is_on)


def test_test_mode_cycles_reference_colors():
    si = STYLES[LedStyle.AX120]
    s = LedDeviceSettings(test_mode=True)
    white = compute(s, si, tick=0, metrics={}).colors[0]
    assert white == (255, 255, 255)


def test_zone_colors_are_applied_per_zone():
    from thermalright_lcd_control.device_controller.led.led_models import LedZoneSettings
    si = STYLES[LedStyle.PA120]   # 4 zones
    zones = [
        LedZoneSettings(color=(200, 0, 0), brightness=100),
        LedZoneSettings(color=(0, 200, 0), brightness=100),
        LedZoneSettings(color=(0, 0, 200), brightness=100),
        LedZoneSettings(color=(200, 200, 0), brightness=100),
    ]
    s = LedDeviceSettings(mode=LEDMode.STATIC, zones=zones)
    res = compute(s, si, tick=0, metrics={})
    # first LED belongs to zone 0 (red), last LED to zone 3 (yellow)
    assert res.colors[0] == (200, 0, 0)
    assert res.colors[-1] == (200, 200, 0)


def test_zone_off_darkens_that_zone():
    from thermalright_lcd_control.device_controller.led.led_models import LedZoneSettings
    si = STYLES[LedStyle.PA120]
    zones = [LedZoneSettings(on=(i != 1)) for i in range(4)]   # zone 1 off
    s = LedDeviceSettings(mode=LEDMode.STATIC, zones=zones)
    res = compute(s, si, tick=0, metrics={})
    # Real firmware map: index 0 is in zone 0, index 31 is in zone 1.
    assert res.is_on[0] is True            # zone 0 on
    assert res.is_on[31] is False          # zone 1 off


def test_segment_display_renders_data_mask():
    # PA120 is a digital display: with a metric, only the segments spelling the
    # readout are lit — not every LED. cpu_temp=45 lights fewer than all 84.
    si = STYLES[LedStyle.PA120]
    s = LedDeviceSettings(mode=LEDMode.STATIC)
    for z in s.zones:
        z.on = True
    lit = sum(compute(s, si, tick=0, metrics={"cpu_temp": 45, "gpu_temp": 61}).is_on)
    assert 0 < lit < si.led_count


def test_pure_rgb_style_lights_all_leds():
    # LF13 has no digit display -> every LED lit (subject to segment mask).
    si = STYLES[LedStyle.LF13]
    s = LedDeviceSettings(mode=LEDMode.STATIC, segment_on=[True] * si.segment_count)
    res = compute(s, si, tick=0, metrics={})
    assert all(res.is_on)


def test_temp_linked_uses_metric():
    si = STYLES[LedStyle.AX120]
    s = LedDeviceSettings(mode=LEDMode.TEMP_LINKED, temp_source="cpu")
    cold = compute(s, si, tick=0, metrics={"cpu_temp": 0}).colors[0]
    hot = compute(s, si, tick=0, metrics={"cpu_temp": 100}).colors[0]
    assert cold != hot
    assert hot[0] >= cold[0]   # hotter -> more red
