# SPDX-License-Identifier: Apache-2.0
# Test script for device communication

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))


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

    # Run the device to ensure proper initialization
    logger.info("Running device initialization...")
    device.run()

    # Check if the device is connected
    if not device.is_device_connected():
        logger.error("Device is not connected.")
        return

    logger.info("Device is connected.")

    # Verify endpoint communication
    try:
        logger.info("Testing basic endpoint communication...")
        test_payload = bytes([0x01, 0x02, 0x03, 0x04])
        logger.debug(f"Sending test payload to Bulk OUT endpoint: {test_payload.hex()}")
        device.write(test_payload)
        logger.info("Test payload sent successfully.")

        logger.debug("Attempting to read response from Bulk IN endpoint...")
        response = device.dev.read(0x81, 16)  # Read 16 bytes from Bulk IN endpoint
        logger.info(f"Response from Bulk IN endpoint: {response.hex()}")
    except Exception as e:
        logger.error(f"Endpoint communication test failed: {e}")

    # Send a test command
    try:
        logger.info("Sending test command...")
        device.send_test_command()
        logger.info("Test command sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send test command: {e}")

    # Test SCSI command with retry mechanism and simpler command
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending SCSI command (Attempt {attempt + 1}/{max_retries})...")
            # Simpler SCSI command for testing
            command = bytes([0x00, 0x00, 0x00, 0x00])  # Simpler command
            logger.debug(f"SCSI command payload: {command.hex()}")
            response = device.send_scsi_command(command, data_in_length=16)
            logger.info(f"SCSI command response: {response.hex()}")
            break
        except Exception as e:
            logger.error(f"Failed to send SCSI command on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.info("Resetting device and retrying...")
                device.reset()
            else:
                logger.error("All attempts to send SCSI command failed.")

if __name__ == "__main__":
    main()
