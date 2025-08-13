# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import hid
import yaml
import os


class HIDDeviceWrapper:
    def __init__(self, device_info):
        self.vid = device_info['vendor_id']
        self.pid = device_info['product_id']
        self.path = device_info['path']
        self.device = hid.device()
        self.device.open_path(self.path)

    def reset(self):
        # Optional: implement if needed
        pass

    def run(self):
        # Optional: implement device-specific logic
        print(f"Running HID device at path {self.path}")


def detect_hid_device(config_dir: str):
    config_path = os.path.join(config_dir, "device_config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    target_vid = config["device"]["vendor_id"]
    target_pid = config["device"]["product_id"]

    for dev in hid.enumerate():
        if dev['vendor_id'] == target_vid and dev['product_id'] == target_pid:
            return HIDDeviceWrapper(dev)

    return None  # No matching HID device found
