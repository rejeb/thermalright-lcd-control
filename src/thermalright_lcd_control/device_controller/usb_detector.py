# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import usb.core
import usb.util
import yaml
import os


class USBDeviceWrapper:
    def __init__(self, device):
        self.device = device

    def reset(self):
        # Optional: implement device-specific reset logic
        pass

    def run(self):
        # Optional: implement device-specific control logic
        print(f"Running USB device: VID={hex(self.device.idVendor)}, PID={hex(self.device.idProduct)}")


def detect_usb_device(config_dir: str):
    config_path = os.path.join(config_dir, "device_config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    target_vid = config["device"]["vendor_id"]
    target_pid = config["device"]["product_id"]

    device = usb.core.find(idVendor=target_vid, idProduct=target_pid)

    if device is None:
        return None

    # Optional: detach kernel driver if needed
    try:
        if device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass

    return USBDeviceWrapper(device)
