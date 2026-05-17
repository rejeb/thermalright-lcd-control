# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Per-vendor GPU metric mixins, combined by :class:`GpuMetrics`."""
from thermalright_lcd_control.device_controller.metrics.gpu.amd import AmdMixin
from thermalright_lcd_control.device_controller.metrics.gpu.intel import IntelMixin
from thermalright_lcd_control.device_controller.metrics.gpu.nvidia import NvidiaMixin

__all__ = ["NvidiaMixin", "AmdMixin", "IntelMixin"]
