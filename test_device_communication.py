# SPDX-License-Identifier: Apache-2.0
# Test script for device communication

import logging
from thermalright_lcd_control.device_controller.display.display_device import DisplayDevice04023922

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_device_communication")

def main():
    # Path to configuration directory
    config_dir = "./resources/config"

    # Initialize the device
    logger.info("Initializing device...")
    device = DisplayDevice04023922(config_dir)

    # Check if the device is connected
    if not device.is_device_connected():
        logger.error("Device is not connected.")
        return

    logger.info("Device is connected.")

    # Send a test command
    try:
        logger.info("Sending test command...")
        device.send_test_command()
        logger.info("Test command sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send test command: {e}")

    # Test SCSI command
    try:
        logger.info("Sending SCSI command...")
        command = bytes([0x12, 0x34, 0x56, 0x78])  # Example command
        response = device.send_scsi_command(command, data_in_length=16)
        logger.info(f"SCSI command response: {response.hex()}")
    except Exception as e:
        logger.error(f"Failed to send SCSI command: {e}")

if __name__ == "__main__":
    main()
