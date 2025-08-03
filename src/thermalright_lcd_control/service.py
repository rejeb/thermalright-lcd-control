# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

import argparse
import os
import sys

# Add the parent directory to Python path for direct execution
if __name__ == "__main__" and __package__ is None:
    # Get the directory containing this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Add the parent directory (src) to the Python path
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Set the package name for relative imports
    __package__ = 'thermalright_lcd_control'


def main():
    parser = argparse.ArgumentParser(description="Thermal Right LCD Control")
    parser.add_argument('--config',
                        required=True,
                        help="Display configuration file")
    args = parser.parse_args()
    from .common.logging_config import get_service_logger
    logger = get_service_logger()
    logger.info("Thermal Right LCD Control starting in device controller mode")

    from .device_controller import run_service
    run_service(args.config)


if __name__ == "__main__":
    main()
