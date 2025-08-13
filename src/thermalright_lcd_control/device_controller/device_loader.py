import os
import yaml
from .hid_detector import detect_hid_device
from .usb_detector import detect_usb_device  # renamed import
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

    # Fallback to pyusb detection
    try:
        device = detect_usb_device(vid, pid, logger)
        if device:
            logger.info("Device detected via USB (pyusb)")
            return device
        else:
            logger.warning("No USB-compatible device found")
    except Exception as e:
        logger.error(f"USB detection failed: {e}")

    raise ValueError("No supported device found via HID or USB")

