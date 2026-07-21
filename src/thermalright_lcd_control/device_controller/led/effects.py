# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""LED effects engine: mode -> per-LED colors. Pure logic."""
from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass

from . import segment_display
from .led_models import LEDMode
from .segments import segment_is_on_mask
from .zones import active_zone

_TEST_COLORS = [(255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255)]
_TEST_PERIOD = 30   # ticks per reference color
_PHASE_TICKS = 60   # ticks between metric phases on multi-phase displays


class _MetricsView:
    """Adapt a metrics dict to the attribute access the segment displays use.

    The segment renderers read ``getattr(metrics, "cpu_temp", 0)`` etc.; this
    exposes dict keys as attributes and returns 0 for anything absent.
    """

    __slots__ = ("_d",)

    def __init__(self, d: dict) -> None:
        self._d = d or {}

    def __getattr__(self, name):
        return self._d.get(name, 0)


@dataclass
class ComputeResult:
    colors: list
    is_on: list
    global_on: bool


def _bake(color, brightness) -> tuple:
    f = max(0, min(100, brightness)) / 100.0
    r, g, b = color
    return (int(r * f), int(g * f), int(b * f))


def _hue_shift(base, tick, span):
    r, g, b = base
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = (h + (tick % span) / span) % 1.0
    rr, gg, bb = colorsys.hsv_to_rgb(h, max(s, 1.0), 1.0)
    return (int(rr * 255), int(gg * 255), int(bb * 255))


def _temp_to_color(value) -> tuple:
    f = max(0.0, min(1.0, value / 100.0))
    # blue (cold) -> red (hot)
    return (int(255 * f), 0, int(255 * (1 - f)))


def compute(settings, style_info, tick: int, metrics: dict) -> ComputeResult:
    n = style_info.led_count
    if not settings.global_on:
        return ComputeResult([(0, 0, 0)] * n, [False] * n, False)

    if settings.test_mode:
        c = _TEST_COLORS[(tick // _TEST_PERIOD) % len(_TEST_COLORS)]
        colors = [c] * n
        return ComputeResult(colors, [True] * n, True)

    mode = settings.mode

    # Per-LED base colour + brightness. Spatial-zone styles (PA120, LF10) map
    # each LED to its zone via the firmware ``zone_led_map`` — NOT an even index
    # split, which would slice colour across the digits. LEDs outside any zone
    # (and all non-zoned styles) use the global colour.
    style = style_info.style
    zoned = bool(style_info.has_zones and settings.zones)
    led_to_zone: dict = {}
    if zoned:
        display = segment_display.get_display(style)
        zmap = getattr(display, "zone_led_map", None)
        if zmap:
            for zi, leds in enumerate(zmap):
                if zi >= len(settings.zones):
                    break
                for led in leds:
                    led_to_zone[led] = zi
        else:
            zoned = False   # no real spatial map → treat as single global zone

    def _led_zone(led: int) -> int:
        return led_to_zone.get(led, -1)

    def _base_for(led: int):
        zi = _led_zone(led)
        if zi >= 0:
            z = settings.zones[zi]
            return z.color, z.brightness
        return settings.color, settings.brightness

    colors = []
    for i in range(n):
        base, bright = _base_for(i)
        if mode == LEDMode.STATIC:
            colors.append(_bake(base, bright))
        elif mode == LEDMode.BREATHING:
            phase = (math.sin(tick / 10.0) + 1) / 2
            colors.append(_bake(base, int(bright * phase)))
        elif mode == LEDMode.COLORFUL:
            colors.append(_hue_shift(base, tick + i * 4, 60))
        elif mode == LEDMode.RAINBOW:
            colors.append(_hue_shift((255, 0, 0), tick + i, n))
        elif mode == LEDMode.TEMP_LINKED:
            key = "cpu_temp" if settings.temp_source == "cpu" else "gpu_temp"
            colors.append(_temp_to_color(metrics.get(key, 0)))
        elif mode == LEDMode.LOAD_LINKED:
            key = "cpu_usage" if settings.load_source == "cpu" else "gpu_usage"
            colors.append(_temp_to_color(metrics.get(key, 0)))
        else:
            colors.append(_bake(base, bright))

    # per-LED on/off from zones: a zone switched off (or, with the carousel
    # enabled, any zone that isn't the currently-active one) is dark.
    if zoned:
        az = active_zone(settings, tick) if settings.zone_sync else None
        zone_on = []
        for led in range(n):
            z = _led_zone(led)
            if z < 0:
                zone_on.append(True)   # LED outside any zone: global, always on
                continue
            on = settings.zones[z].on
            if az is not None:
                on = on and (z == az)
            zone_on.append(on)
    else:
        zone_on = [True] * n

    # Content mask. Digital-display styles light only the segments that spell
    # out the live readout (temperature digits, clock, memory/disk stats) — the
    # real device output. Pure-RGB styles fall back to the coarse per-segment
    # visibility mask.
    style = style_info.style
    if segment_display.has_segment_display(style):
        display = segment_display.get_display(style)
        phase = (tick // _PHASE_TICKS) % max(1, getattr(display, "phase_count", 1))
        data_mask = segment_display.compute_mask(
            style, _MetricsView(metrics), phase,
            is_24h=settings.clock_24h, week_sunday=settings.week_sunday,
            memory_ratio=settings.memory_ratio,
        )
        if len(data_mask) == n:
            content = data_mask
        else:
            content = [True] * n
    else:
        content = segment_is_on_mask(
            settings.segment_on, n, style_info.segment_count)

    is_on = [z and c for z, c in zip(zone_on, content)]
    return ComputeResult(colors, is_on, True)
