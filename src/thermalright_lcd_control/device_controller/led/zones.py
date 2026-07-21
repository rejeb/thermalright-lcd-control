# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Zone carousel logic. Pure."""
from __future__ import annotations


def active_zone(settings, tick: int) -> int:
    n = len(settings.zones)
    if n == 0:
        return 0
    if not settings.zone_sync:
        return min(settings.selected_zone, n - 1)
    interval = max(1, settings.zone_sync_interval_ticks)
    return (tick // interval) % n


def zone_enabled_mask(settings) -> list:
    return [z.on for z in settings.zones]
