
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Module for detecting supported USB devices
"""
from pathlib import Path
from typing import Optional, Dict, Any

import usb.core
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
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.config = config
        except (FileNotFoundError, yaml.YAMLError) as e:
            self.logger.error(f"Error loading configuration: {e}")

    def find_connected_device(self) -> Optional[Dict[str, Any]]:
        """
        Search for a supported device connected to the system

        Returns:
            Dict containing the found device information (vid, pid, width, height)
            or None if no supported device is found
        """
        try:
            # Get all connected USB devices
            device_config_file_path = Path(self.config['paths']['service_config'],"device_info.yaml")

            with open(device_config_file_path, 'r', encoding='utf-8') as f:
                device_config = yaml.safe_load(f)
            return device_config

        except (FileNotFoundError, yaml.YAMLError) as e:
            self.logger.error(f"Error loading device configuration file: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error detecting USB devices: {e}")
            return None

        return None
