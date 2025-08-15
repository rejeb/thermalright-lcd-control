# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import logging
import os
from .device_loader import load_device  # Now handles USB/HID detection internally

def run_service(config_path=None):
    logger = logging.getLogger("thermalright.device_controller")
    logging.basicConfig(level=logging.INFO)

    logger.info("Thermal Right LCD Control starting in device controller mode")

    if config_path is None:
        config_path = os.path.expanduser("~/.config/thermalright-lcd-control/config")
    logger.info(f"Using config path: {config_path}")

    try:
        device = load_device(config_path)
        logger.info("Device successfully loaded and initialized")

        # Optional: start device loop if supported
        if hasattr(device, "run"):
            logger.info("Starting device run loop")
            device.run()
        else:
            logger.warning("Loaded device has no run() method")
    except Exception as e:
        logger.error(f"Device initialization failed: {e}")
