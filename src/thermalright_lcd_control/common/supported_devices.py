# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from ..device_controller.display.hid_devices import DisplayDevice04185304, DisplayDevice04165302
from ..device_controller.display.usb_devices import DisplayDevice87AD70DB320, DisplayDevice87AD70DB480

"""
For existing (vid,pid) add your new device in the list:
SUPPORTED_DEVICES: list[tuple[int, int, list[dict]]] = [...
    (vid, pid, [ExistingDevices.info(),YourNewDevice.info()]] ),
    ...
    ]
    
For new (vid,pid) add new line as:
SUPPORTED_DEVICES: list[tuple[int, int, list[dict]]] = [...
    (vid, pid, [YourNewDevice.info()]] ),
    ]
    
"""
SUPPORTED_DEVICES: list[tuple[int, int, list[dict]]] = [
    (0x0418, 0x5304, [DisplayDevice04185304.info()]),
    (0x0416, 0x5302, [DisplayDevice04165302.info()]),
    (0x87AD, 0x70DB, [DisplayDevice87AD70DB320.info(), DisplayDevice87AD70DB480.info()]),
]
