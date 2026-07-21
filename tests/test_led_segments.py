# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.segments import segment_is_on_mask


def test_no_segments_all_on():
    assert segment_is_on_mask([], led_count=4, segment_count=0) == [True, True, True, True]


def test_segments_map_leds_evenly():
    # 4 leds, 2 segments -> leds [0,1] seg0, [2,3] seg1; seg1 off
    mask = segment_is_on_mask([True, False], led_count=4, segment_count=2)
    assert mask == [True, True, False, False]
