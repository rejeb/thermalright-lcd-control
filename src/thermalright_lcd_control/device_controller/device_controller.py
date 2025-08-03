# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

from .display.display_device import load_device
from ..common.logging_config import get_service_logger


def run_service(config_file: str):
    logger = get_service_logger()
    logger.info("Device controller service started")

    try:
        device = load_device(config_file)
        device.reset()
        device.run()
    except KeyboardInterrupt:
        logger.info("Device controller service stopped by user")
    except Exception as e:
        logger.error(f"Device controller service error: {e}", exc_info=True)
        raise
