# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import os
import yaml
from .usb_detector import detect_usb_device
from .hid_detector import detect_hid_device
from thermalright_lcd_control.device_controller.display.display_device import DEVICE_CLASSES
from thermalright_lcd_control.common.logging_config import get_service_logger


def load_device(config_dir: str):
    logger = get_service_logger()

    # Attempt HID detection first
    try:
        logger.info("Attempting HID detection")
        device = detect_hid_device(config_dir)
        if device:
            logger.info("Device detected via HID")
            return device
        else:
            logger.warning("No HID-compatible device found")
    except Exception as e:
        logger.warning(f"HID detection failed: {e}")

    # Load VID/PID from config
    config_path = os.path.join(config_dir, "device_config.yaml")
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        raise FileNotFoundError(f"Missing config: {config_path}")

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        vid = config["device"]["vid"]
        pid = config["device"]["pid"]
        logger.info(f"Loaded VID/PID from config: {vid:04x}:{pid:04x}")
    except Exception as e:
        logger.error(f"Failed to load VID/PID from config: {e}")
        raise

    # Try to instantiate a known DisplayDevice subclass
    device_class = DEVICE_CLASSES.get((vid, pid))
    if device_class:
        logger.info(f"Instantiating device class for VID={hex(vid)}, PID={hex(pid)}")
        try:
            device = device_class(config_dir)
            logger.info(f"Device class {device_class.__name__} initialized successfully")
            return device
        except Exception as e:
            logger.error(f"Failed to initialize device class {device_class.__name__}: {e}")
            raise
    else:
        logger.warning(f"No matching DisplayDevice class for VID={hex(vid)}, PID={hex(pid)}")

    # Fallback to pyusb detection
    try:
        logger.info(f"Attempting USB detection for VID={hex(vid)}, PID={hex(pid)}")
        device = detect_usb_device(vid, pid, logger)
        if device:
            logger.info("Device detected via USB")
            return device
        else:
            logger.warning("No USB-compatible device found")
    except Exception as e:
        logger.error(f"USB detection failed: {e}")
        raise

    logger.error("Device loading failed. No compatible device found.")
    return None

