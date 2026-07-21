# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.led.styles import (
    LedStyle, STYLES, resolve_pm,
)


def test_all_twelve_styles_present():
    expected = {"AX120", "PA120", "AK120", "LC1", "LF8", "LF12",
                "LF10", "CZ1", "LC2", "LF11", "LF15", "LF13"}
    assert {s.name for s in LedStyle} == expected
    assert set(STYLES.keys()) == set(LedStyle)


def test_style_info_shape():
    info = STYLES[LedStyle.PA120]
    assert info.zone_count >= 1
    assert info.led_count == len(info.wire_remap)
    assert sorted(info.wire_remap) == list(range(info.led_count))


def test_capability_flags_consistent():
    lc2 = STYLES[LedStyle.LC2]
    assert lc2.has_clock is True
    ax = STYLES[LedStyle.AX120]
    assert ax.has_zones == (ax.zone_count > 1)
    assert ax.has_segments == (ax.segment_count > 0)


def test_resolve_pm_unknown_returns_none():
    assert resolve_pm(0xEE, 0) is None
