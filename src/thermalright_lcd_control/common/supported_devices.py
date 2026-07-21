# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.display.device_0402_3922 import (
    DisplayDevice04023922320320,
)
from thermalright_lcd_control.device_controller.display.hid_devices import (
    DisplayDevice04165302,
    DisplayDevice04185304,
)
from thermalright_lcd_control.device_controller.display.usb_devices import (
    DisplayDevice87AD70DB320,
    DisplayDevice87AD70DB480,
    DisplayDevice87AD70DB640,
)

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
    (0x87AD, 0x70DB, [DisplayDevice87AD70DB320.info(), DisplayDevice87AD70DB480.info(), DisplayDevice87AD70DB640.info()]),
    (0x0402, 0x3922, [DisplayDevice04023922320320.info()]),
]

# Concrete legacy device classes, used to resolve a (vid, pid, width, height)
# devices.yaml entry to the class that drives it (no per-device subclass in the
# generic stack). Resolution is part of the key so ChiZhu's three same-VID:PID
# variants stay distinct.
_LEGACY_CLASSES = [
    DisplayDevice04185304,
    DisplayDevice04165302,
    DisplayDevice87AD70DB320,
    DisplayDevice87AD70DB480,
    DisplayDevice87AD70DB640,
    DisplayDevice04023922320320,
]


def find_legacy_class(vid: int, pid: int, width: int, height: int):
    """Return the legacy device class matching (vid, pid, width, height), or None."""
    for cls in _LEGACY_CLASSES:
        if cls.VID == vid and cls.PID == pid and cls.W == width and cls.H == height:
            return cls
    return None


# --- LED devices (kind: led) ---------------------------------------------
# LED controllers auto-detected over USB. The style is resolved at detection
# time from the device's HID handshake (see device_controller/led/detect.py).
LED_SUPPORTED_DEVICES: list[dict] = [
    {
        "vid": 0x0416,
        "pid": 0x8001,
        "kind": "led",
        "vendor": "Winbond",
        "product": "LED Controller",
    },
]


def led_supported_devices() -> list[dict]:
    """Return LED device descriptors (kind: led)."""
    return [dict(e) for e in LED_SUPPORTED_DEVICES]


def all_device_kinds() -> set:
    """All device kinds known to the registry."""
    kinds = {"lcd"}
    for e in LED_SUPPORTED_DEVICES:
        kinds.add(e.get("kind", "lcd"))
    return kinds


def resolve_led_style(descriptor: dict):
    """Map a descriptor's style name to a LedStyle (default AX120)."""
    from thermalright_lcd_control.device_controller.led.styles import LedStyle
    return LedStyle[descriptor.get("style", "AX120")]
