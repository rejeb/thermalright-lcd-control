# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
"""Backend detect_devices method: JSON bridge over device_registry.detect_devices."""
import json
import logging

from thermalright_lcd_control.device_controller.display import device_registry
from thermalright_lcd_control.gui.backend.mixins.device_config import (
    DeviceConfigMixin,
)


class _Host(DeviceConfigMixin):
    """Minimal host: only what detect_devices touches."""

    def __init__(self):
        self.logger = logging.getLogger("test")


def test_detect_devices_returns_scan_json(monkeypatch):
    scan = [{"detected": True, "name": "ChiZhu GrandVision family",
             "vid": "0x87AD", "pid": "0x70DB", "bus": 3, "device": 7,
             "pm": 1, "sub": 0, "fbl": 72,
             "config": {"width": 480, "height": 480},
             "message": "Detected 480x480 (PM=1) — matched bundled profile"}]
    monkeypatch.setattr(device_registry, "detect_devices", lambda: scan)
    out = json.loads(_Host().detect_devices())
    assert out == scan


def test_detect_devices_swallows_exceptions(monkeypatch):
    def boom():
        raise RuntimeError("usb exploded")
    monkeypatch.setattr(device_registry, "detect_devices", boom)
    assert json.loads(_Host().detect_devices()) == []
