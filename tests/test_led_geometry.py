# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.geometry import geometry_for
from thermalright_lcd_control.device_controller.led.styles import STYLES, LedStyle


def test_every_style_has_geometry_within_led_count():
    # Real firmware layouts; the preview may draw fewer rects than the wire
    # led_count for a few styles, never more.
    for style in LedStyle:
        pts = geometry_for(style)
        assert 0 < len(pts) <= STYLES[style].led_count, style.name


def test_rects_normalized_and_within_bounds():
    for style in LedStyle:
        for p in geometry_for(style):
            assert 0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0
            assert 0.0 < p.w <= 1.0 and 0.0 < p.h <= 1.0
            assert p.x + p.w <= 1.001 and p.y + p.h <= 1.001
