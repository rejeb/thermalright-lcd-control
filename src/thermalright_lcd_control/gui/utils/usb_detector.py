
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""
Module for detecting supported USB devices
"""

from typing import Optional, Dict, Any

import usb.core
import yaml

from ...common.logging_config import get_gui_logger


class USBDeviceDetector:
    """Detects supported USB devices defined in configuration"""

    def __init__(self, config_file: str = None):
        self.logger = get_gui_logger()
        self.config_file = config_file
        self.supported_devices = []
        self._load_supported_devices()

    def _load_supported_devices(self):
        """Load the list of supported devices from config file"""
        if not self.config_file:
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.supported_devices = config.get('supported_devices', [])
        except (FileNotFoundError, yaml.YAMLError) as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.supported_devices = []

    def find_connected_device(self) -> Optional[Dict[str, Any]]:
        """
        Search for a supported device connected to the system

        Returns:
            Dict containing the found device information (vid, pid, width, height)
            or None if no supported device is found
        """
        try:
            # Get all connected USB devices
            connected_devices = usb.core.find(find_all=True)

            # Check each supported device
            for device in connected_devices:
                for supported_device in self.supported_devices:
                    supported_vid = supported_device.get('vid')
                    supported_pid = supported_device.get('pid')

                    # Convert hexadecimal values if necessary
                    if isinstance(supported_vid, str):
                        supported_vid = int(supported_vid, 16)
                    if isinstance(supported_pid, str):
                        supported_pid = int(supported_pid, 16)
                    # Search for matching device

                    if device.idVendor == supported_vid and device.idProduct == supported_pid:
                        return {
                            'vid': supported_vid,
                            'pid': supported_pid,
                            'width': supported_device.get('width', 320),
                            'height': supported_device.get('height', 240),
                            'device_config': supported_device
                        }

        except usb.core.NoBackendError:
            self.logger.error("Error: USB backend not available. Install libusb.")
        except Exception as e:
            self.logger.error(f"Error detecting USB devices: {e}")

        return None
