# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Pure-logic LED settings model. No Qt, no USB imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class LEDMode(IntEnum):
    STATIC = 0
    BREATHING = 1
    COLORFUL = 2
    RAINBOW = 3
    TEMP_LINKED = 4
    LOAD_LINKED = 5


@dataclass
class LedZoneSettings:
    mode: LEDMode = LEDMode.STATIC
    color: tuple = (255, 0, 0)
    brightness: int = 65
    on: bool = True

    def to_dict(self) -> dict:
        return {"mode": int(self.mode), "color": list(self.color),
                "brightness": self.brightness, "on": self.on}

    @classmethod
    def from_dict(cls, d: dict) -> "LedZoneSettings":
        return cls(mode=LEDMode(d["mode"]), color=tuple(d["color"]),
                   brightness=d["brightness"], on=d["on"])


@dataclass
class LedDeviceSettings:
    mode: LEDMode = LEDMode.STATIC
    color: tuple = (255, 0, 0)
    brightness: int = 65
    global_on: bool = True
    zones: list = field(default_factory=list)
    zone_sync: bool = False
    zone_sync_interval_ticks: int = 13
    selected_zone: int = 0
    test_mode: bool = False
    temp_source: str = "cpu"
    load_source: str = "cpu"
    segment_on: list = field(default_factory=list)
    clock_24h: bool = True
    week_sunday: bool = False
    memory_ratio: int = 2
    disk_index: int = 0

    def to_dict(self) -> dict:
        return {
            "mode": int(self.mode), "color": list(self.color),
            "brightness": self.brightness, "global_on": self.global_on,
            "zones": [z.to_dict() for z in self.zones],
            "zone_sync": self.zone_sync,
            "zone_sync_interval_ticks": self.zone_sync_interval_ticks,
            "selected_zone": self.selected_zone, "test_mode": self.test_mode,
            "temp_source": self.temp_source, "load_source": self.load_source,
            "segment_on": list(self.segment_on), "clock_24h": self.clock_24h,
            "week_sunday": self.week_sunday, "memory_ratio": self.memory_ratio,
            "disk_index": self.disk_index,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LedDeviceSettings":
        return cls(
            mode=LEDMode(d["mode"]), color=tuple(d["color"]),
            brightness=d["brightness"], global_on=d["global_on"],
            zones=[LedZoneSettings.from_dict(z) for z in d["zones"]],
            zone_sync=d["zone_sync"],
            zone_sync_interval_ticks=d["zone_sync_interval_ticks"],
            selected_zone=d["selected_zone"], test_mode=d["test_mode"],
            temp_source=d["temp_source"], load_source=d["load_source"],
            segment_on=list(d["segment_on"]), clock_24h=d["clock_24h"],
            week_sunday=d["week_sunday"], memory_ratio=d["memory_ratio"],
            disk_index=d["disk_index"],
        )
