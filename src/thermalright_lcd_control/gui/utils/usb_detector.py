
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Module for detecting supported USB devices
"""
from pathlib import Path
from typing import Any

import yaml

from thermalright_lcd_control.common.logging_config import get_gui_logger


class USBDeviceDetector:
    """Detects supported USB devices defined in configuration"""

    def __init__(self, config_file: str = None):
        self.logger = get_gui_logger()
        self.config_file = config_file
        self.config = None
        self._load_config()

    def _load_config(self):
        """Load gui config from config file"""
        if not self.config_file:
            return

        try:
            with open(self.config_file, encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.config = config
        except (FileNotFoundError, yaml.YAMLError) as e:
            self.logger.error(f"Error loading configuration: {e}")

    def get_devices(self) -> list[dict[str, Any]]:
        """Return the configured devices that are currently plugged in.

        Reads the per-device ``device_<id>.yaml`` files first; if none exist,
        falls back to ``device_info.yaml`` (a single device). A configured
        device whose USB hardware isn't currently detected is filtered out —
        its files are left untouched, and DevicePresenceMonitor adds it back
        once it's plugged in. Returns an empty list when neither yields a
        present device.
        """
        config_dir = self.config['paths']['service_config']

        # 1) per-device files device_<id>.yaml — peut contenir plusieurs devices
        from thermalright_lcd_control.device_controller.display import device_registry
        devices = device_registry.list_devices(config_dir)
        if devices:
            present = device_registry.present_device_ids(config_dir)
            return [d for d in devices if str(d.get("id")) in present]

        # 2) repli sur device_info.yaml — un seul device
        info_path = Path(config_dir, "device_info.yaml")
        try:
            with open(info_path, encoding='utf-8') as f:
                device = yaml.safe_load(f)
            if device and self._is_present(device):
                return [device]
        except FileNotFoundError:
            self.logger.error(f"Device configuration file not found: {info_path}")
        except yaml.YAMLError as e:
            self.logger.error(f"Error loading {info_path}: {e}")

        return []

    @staticmethod
    def _is_present(device: dict[str, Any]) -> bool:
        import usb.core

        from thermalright_lcd_control.device_controller.display.device_config import to_int
        try:
            vid, pid = to_int(device["vid"], "vid"), to_int(device["pid"], "pid")
        except (KeyError, ValueError):
            return False
        return usb.core.find(idVendor=vid, idProduct=pid) is not None
