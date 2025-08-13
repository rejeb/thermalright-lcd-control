# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import usb.core
import usb.util
import usb.backend.libusb1


def detect_usb_device(vid: int, pid: int, logger):
    logger.info(f"Attempting to detect USB device {vid:04x}:{pid:04x}")

    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        raise RuntimeError(f"USB device {vid:04x}:{pid:04x} not found")

    logger.info(f"USB device found at bus {dev.bus}, address {dev.address}")

    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
            logger.info("Detached kernel driver from interface 0")
    except (NotImplementedError, usb.core.USBError) as e:
        logger.warning(f"Could not detach kernel driver: {e}")

    try:
        dev.set_configuration()
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
    except usb.core.USBError as e:
        raise RuntimeError(f"Failed to set configuration or access interface: {e}")

    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )

    ep_in = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    if ep_out is None and ep_in is None:
        raise RuntimeError("No usable endpoints found (IN or OUT)")

    logger.info(f"Endpoints discovered — OUT: {bool(ep_out)}, IN: {bool(ep_in)}")

    return {
        "device": dev,
        "interface": intf,
        "endpoint_out": ep_out,
        "endpoint_in": ep_in,
    }
