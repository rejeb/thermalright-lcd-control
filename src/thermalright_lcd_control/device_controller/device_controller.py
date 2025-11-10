# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
from thermalright_lcd_control.device_controller.display.device_loader import DeviceLoader
from thermalright_lcd_control.common.logging_config import get_service_logger


def run_service(config_dir: str):
    logger = get_service_logger()
    logger.info("Device controller service started")

    try:
        loader = DeviceLoader(config_dir)
        device = loader.load_device()
        if device is None:
            logger.error(f"No device found", exc_info=True)
            exit(1)
        device.reset()
        device.start()
    except KeyboardInterrupt:
        logger.info("Device controller service stopped by user")
    except Exception as e:
        logger.error(f"Device controller service error: {e}", exc_info=True)
        raise
