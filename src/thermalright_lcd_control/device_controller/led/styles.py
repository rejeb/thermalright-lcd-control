# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""LED hardware style registry. Pure logic — no Qt, no USB.

NOTE: led_count, zone_count, segment_count, wire_remap and PM values are an
initial data table. Values for styles that cannot be hardware-verified here
are trcc-sourced placeholders that a future hardware bring-up plan confirms.
Each wire_remap is a permutation of range(led_count); identity is used where
the physical order is unverified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class LedStyle(IntEnum):
    AX120 = 1
    PA120 = 2
    AK120 = 3
    LC1 = 4
    LF8 = 5
    LF12 = 6
    LF10 = 7
    CZ1 = 8
    LC2 = 9
    LF11 = 10
    LF15 = 11
    LF13 = 12


@dataclass
class StyleInfo:
    style: LedStyle
    led_count: int
    zone_count: int
    segment_count: int
    layout_ref: str
    wire_remap: list = field(default_factory=list)
    has_zones: bool = False
    has_segments: bool = False
    has_clock: bool = False
    has_memory_disk: bool = False
    has_sensors: bool = True


def _identity(n: int) -> list:
    return list(range(n))


def _mk(style, led_count, zone_count, segment_count, *,
        clock=False, memory_disk=False, remap=None) -> StyleInfo:
    return StyleInfo(
        style=style, led_count=led_count, zone_count=zone_count,
        segment_count=segment_count, layout_ref=style.name.lower(),
        wire_remap=remap if remap is not None else _identity(led_count),
        has_zones=zone_count > 1, has_segments=segment_count > 0,
        has_clock=clock, has_memory_disk=memory_disk, has_sensors=True,
    )


# Counts ported from thermalright-trcc-linux (led_count, segment_count).
#
# zone_count here means SPATIAL zones (independently-colourable LED regions).
# Only PA120 and LF10 have a real spatial ``zone_led_map`` in the firmware;
# every other style's trcc "zone_count" is actually its metric-PHASE count
# (the display rotates through metrics over time), NOT colourable regions —
# so those are single-zone here to avoid slicing colour across the digits.
STYLES: dict = {
    LedStyle.AX120: _mk(LedStyle.AX120, led_count=30,  zone_count=1, segment_count=10),
    LedStyle.PA120: _mk(LedStyle.PA120, led_count=84,  zone_count=4, segment_count=18),
    LedStyle.AK120: _mk(LedStyle.AK120, led_count=64,  zone_count=1, segment_count=10),
    LedStyle.LC1:   _mk(LedStyle.LC1,   led_count=31,  zone_count=1, segment_count=14, memory_disk=True),
    LedStyle.LF8:   _mk(LedStyle.LF8,   led_count=93,  zone_count=1, segment_count=23, memory_disk=True),
    LedStyle.LF12:  _mk(LedStyle.LF12,  led_count=124, zone_count=1, segment_count=72, memory_disk=True),
    LedStyle.LF10:  _mk(LedStyle.LF10,  led_count=116, zone_count=3, segment_count=12, memory_disk=True),
    LedStyle.CZ1:   _mk(LedStyle.CZ1,   led_count=18,  zone_count=1, segment_count=13, memory_disk=True),
    LedStyle.LC2:   _mk(LedStyle.LC2,   led_count=61,  zone_count=1, segment_count=31, clock=True, memory_disk=True),
    LedStyle.LF11:  _mk(LedStyle.LF11,  led_count=38,  zone_count=1, segment_count=17, memory_disk=True),
    LedStyle.LF15:  _mk(LedStyle.LF15,  led_count=93,  zone_count=1, segment_count=72),
    LedStyle.LF13:  _mk(LedStyle.LF13,  led_count=62,  zone_count=1, segment_count=62),
}

# PM byte -> style. Values trcc-sourced; a future bring-up plan confirms.
# Only the mock and real handshake consume this; unknown PM -> None.
PM_TO_STYLE: dict = {
    50: LedStyle.AX120, 51: LedStyle.PA120, 52: LedStyle.AK120,
    53: LedStyle.LC1, 54: LedStyle.LF8, 55: LedStyle.LF12,
    56: LedStyle.LF10, 57: LedStyle.CZ1, 58: LedStyle.LC2,
    59: LedStyle.LF11, 60: LedStyle.LF15, 61: LedStyle.LF13,
}


def resolve_pm(pm: int, sub: int = 0) -> "LedStyle | None":
    return PM_TO_STYLE.get(pm)
