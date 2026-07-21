# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Memory (RAM + swap) metrics via psutil."""
import psutil

from thermalright_lcd_control.device_controller.metrics.base import Metrics

_GIB = 1024 ** 3


class MemoryMetrics(Metrics):
    def _prepare(self) -> None:
        self._vmem = psutil.virtual_memory()

    def metric_memory_usage(self):
        """RAM usage in percent."""
        return float(self._vmem.percent)

    def metric_memory_used(self):
        """RAM used in GiB."""
        return self._vmem.used / _GIB

    def metric_memory_available(self):
        """RAM available in GiB."""
        return self._vmem.available / _GIB

    def metric_swap_usage(self):
        """Swap usage in percent (None when the system has no swap)."""
        swap = psutil.swap_memory()
        return float(swap.percent) if swap.total else None
