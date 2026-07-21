# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""System metrics: one Metrics subclass per device domain, aggregated behind
the single MetricsCollector entry point (see base.py)."""

from thermalright_lcd_control.device_controller.metrics.base import (
    Metrics,
    MetricsCollector,
    shared_collector,
)

__all__ = ["Metrics", "MetricsCollector", "shared_collector"]
