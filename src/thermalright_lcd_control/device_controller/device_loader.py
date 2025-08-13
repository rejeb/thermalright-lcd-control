# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from .hid_detector import detect_hid_device
from .usb_detector import detect_usb_device
from ..common.logging_config import get_service_logger


def load_device(config_dir: str):
    logger = get_service_logger()

    # Attempt HID detection
    try:
        device = detect_hid_device(config_dir)
        if device:
            logger.info("Device detected via HID")
            return device
        else:
            logger.warning("No HID-compatible device found")
    except Exception as e:
        logger.warning(f"HID detection failed: {e}")

    # Fallback to pyusb detection
    try:
        device = detect_usb_device(config_dir)
        if device:
            logger.info("Device detected via USB (pyusb)")
            return device
        else:
            logger.warning("No USB-compatible device found")
    except Exception as e:
        logger.error(f"USB detection failed: {e}")

    # If both fail, raise a clear error
    raise ValueError("No supported device found via HID or USB")

