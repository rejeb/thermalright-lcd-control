# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Disk metrics via psutil: filesystem usage and aggregate I/O throughput.

Throughputs come from :class:`CounterRates` snapshots taken in
:meth:`_prepare`; the first collect returns 0.0 for the rates.
"""
import psutil

from thermalright_lcd_control.device_controller.metrics.base import CounterRates, Metrics


class DiskMetrics(Metrics):
    def __init__(self, disk_path: str = "/"):
        super().__init__()
        self.disk_path = disk_path
        self._rates = CounterRates(n=2)     # (read, write) MiB/s

    def _prepare(self) -> None:
        counters = psutil.disk_io_counters()
        if counters is not None:
            self._rates.update((counters.read_bytes, counters.write_bytes))

    def metric_disk_usage(self):
        """Filesystem usage of ``disk_path`` in percent."""
        return float(psutil.disk_usage(self.disk_path).percent)

    def metric_disk_read_speed(self):
        """Aggregate disk read throughput in MiB/s."""
        return self._rates.rates[0]

    def metric_disk_write_speed(self):
        """Aggregate disk write throughput in MiB/s."""
        return self._rates.rates[1]
