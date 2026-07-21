# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Service-side LED tick loop. Drives effects -> protocol -> device sink."""
from __future__ import annotations

from .led import protocol
from .led.effects import compute


class LedController:
    def __init__(self, device, settings_provider, metrics_provider) -> None:
        self._device = device
        self._settings_provider = settings_provider
        self._metrics_provider = metrics_provider
        self._tick = 0

    def tick(self, n: "int | None" = None) -> None:
        t = self._tick if n is None else n
        settings = self._settings_provider()
        metrics = self._metrics_provider()
        si = self._device.style_info
        res = compute(settings, si, t, metrics)
        packet = protocol.build_packet(res.colors, res.is_on, si.wire_remap)
        self._device.send_packet(packet)
        self._tick = t + 1

    def run_ticks(self, count: int) -> None:
        for _ in range(count):
            self.tick()
