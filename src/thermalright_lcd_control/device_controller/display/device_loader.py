from typing import Optional

import usb.core
import usb.util

from .display_device import DisplayDevice
from .hid_devices import DisplayDevice04185304, DisplayDevice04165302

SUPPORTED_DEVICES = [
    (0x0418, 0x5304, DisplayDevice04185304),
    (0x0416, 0x5302, DisplayDevice04165302),
    # (vid, pid, Your new device class here ),
]


class DeviceLoader:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir

    def load_device(self) -> Optional[DisplayDevice]:
        for vid, pid, class_name in SUPPORTED_DEVICES:
            device = usb.core.find(idVendor=vid, idProduct=pid)
            if device is not None:
                return class_name(self.config_dir)
        return None
