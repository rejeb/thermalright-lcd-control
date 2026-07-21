# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""System-level metrics via psutil: uptime, load average, process count."""
import time

import psutil

from thermalright_lcd_control.device_controller.metrics.base import Metrics


class SystemMetrics(Metrics):
    def metric_uptime(self):
        """Time since boot in hours."""
        return (time.time() - psutil.boot_time()) / 3600.0

    def metric_load_avg(self):
        """1-minute load average."""
        return float(psutil.getloadavg()[0])

    def metric_process_count(self):
        """Number of running processes."""
        return len(psutil.pids())
