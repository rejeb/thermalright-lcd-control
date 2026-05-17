# SPDX-License-Identifier: Apache-2.0
import importlib


def test_display_loader_imports_without_cycle():
    # Must import without triggering the eager import of run_service.
    mod = importlib.import_module(
        "thermalright_lcd_control.device_controller.display.device_loader")
    assert hasattr(mod, "DeviceLoader")


def test_supported_devices_importable_top_level():
    mod = importlib.import_module(
        "thermalright_lcd_control.common.supported_devices")
    assert hasattr(mod, "find_legacy_class")
