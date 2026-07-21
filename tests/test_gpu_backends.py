# SPDX-License-Identifier: Apache-2.0
from unittest import mock

from thermalright_lcd_control.device_controller.metrics import gpu_metrics as gm


def _metrics_no_detect():
    """A GpuMetrics whose hardware detection is skipped."""
    with mock.patch.object(gm.GpuMetrics, "_detect_gpu", lambda self: None):
        return gm.GpuMetrics()


def test_no_vendor_collects_all_none():
    m = _metrics_no_detect()
    assert m.gpu_vendor is None
    assert m.collect() == {
        "gpu_vendor": None, "gpu_name": None, "gpu_temperature": None,
        "gpu_usage": None, "gpu_frequency": None,
    }


def test_temperature_dispatches_to_vendor_mixin():
    m = _metrics_no_detect()
    m.gpu_vendor = "nvidia"
    with mock.patch.object(m, "_get_nvidia_temperature", return_value=42.0):
        assert m.get_temperature() == 42.0


def test_mixin_methods_present():
    m = _metrics_no_detect()
    for name in ("_get_nvidia_temperature", "_get_amd_temperature",
                 "_get_intel_temperature", "_select_amd_card"):
        assert hasattr(m, name)
