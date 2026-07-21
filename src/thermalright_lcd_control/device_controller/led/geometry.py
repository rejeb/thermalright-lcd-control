# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Per-style LED geometry (normalized rectangles). Pure data.

Real hardware layouts ported from thermalright-trcc-linux (see
``_geometry_data.py``) rather than a synthetic ring: each style draws its
LEDs at the coordinates the firmware UI uses, in a normalized [0,1] square.
The preview may hold fewer rectangles than the wire ``led_count`` for a few
styles (the firmware preview draws a subset); consumers zip against colours
and simply draw what geometry exists.
"""
from __future__ import annotations

from dataclasses import dataclass

from ._geometry_data import RECTS
from .styles import LedStyle


@dataclass
class LedPoint:
    """Normalized LED rectangle: top-left (x, y) + size (w, h), all in [0,1]."""
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


GEOMETRY: dict = {
    style: [LedPoint(x, y, w, h) for (x, y, w, h) in RECTS[style.name]]
    for style in LedStyle
}


def geometry_for(style) -> list:
    return GEOMETRY[style]
