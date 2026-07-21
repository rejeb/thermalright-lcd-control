# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Network metrics via psutil: aggregate download/upload throughput.

Same rate mechanics as :class:`DiskMetrics` (see :class:`CounterRates`).
"""
import psutil

from thermalright_lcd_control.device_controller.metrics.base import CounterRates, Metrics


class NetworkMetrics(Metrics):
    def __init__(self):
        super().__init__()
        self._rates = CounterRates(n=2)     # (down, up) MiB/s

    def _prepare(self) -> None:
        counters = psutil.net_io_counters()
        if counters is not None:
            self._rates.update((counters.bytes_recv, counters.bytes_sent))

    def metric_net_download_speed(self):
        """Aggregate download throughput in MiB/s."""
        return self._rates.rates[0]

    def metric_net_upload_speed(self):
        """Aggregate upload throughput in MiB/s."""
        return self._rates.rates[1]
