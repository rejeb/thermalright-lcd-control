# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Segment on/off masking. Pure."""
from __future__ import annotations


def segment_is_on_mask(segment_on: list, led_count: int, segment_count: int) -> list:
    if segment_count <= 0 or not segment_on:
        return [True] * led_count
    per = max(1, led_count // segment_count)
    mask = []
    for led in range(led_count):
        seg = min(led // per, segment_count - 1)
        mask.append(bool(segment_on[seg]) if seg < len(segment_on) else True)
    return mask
