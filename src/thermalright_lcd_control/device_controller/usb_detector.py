import yaml
import os
import logging
from .hid_detector import detect_hid_device

def detect_usb_device(vid: int, pid: int, logger):
    import usb.core
    import usb.util

    logger.info(f"Searching for USB device VID={hex(vid)}, PID={hex(pid)}")

    # Debug: list all connected USB devices
    logger.info("Enumerating all connected USB devices:")
    for dev in usb.core.find(find_all=True):
        logger.info(f"Found device: VID={hex(dev.idVendor)}, PID={hex(dev.idProduct)}")

    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        logger.warning("USB device not found.")
        return None

    try:
        if dev.is_kernel_driver_active(0):
            logger.info("Detaching kernel driver.")
            dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError) as e:
        logger.warning(f"Could not detach kernel driver: {e}")

    try:
        dev.set_configuration()
        logger.info("USB device configured.")
    except usb.core.USBError as e:
        logger.error(f"Failed to set USB configuration: {e}")
        raise

    logger.info("USB device successfully detected and configured.")
    return dev

def load_device(config_path=None):
    logger = logging.getLogger("thermalright.device_loader")

    if config_path is None:
        config_path = os.path.expanduser("~/.config/thermalright-lcd-control/config.yaml")

    if not os.path.exists(config_path):
        logger.warning(f"Config file not found at {config_path}")
        return None

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    device_cfg = config.get("device", {})
    mode = device_cfg.get("mode", "hid")
    vid = int(device_cfg.get("vid", "0x0402"), 16)
    pid = int(device_cfg.get("pid", "0x3922"), 16)

    logger.info(f"Loading device in {mode.upper()} mode with VID={hex(vid)}, PID={hex(pid)}")

    if mode == "hid":
        return detect_hid_device(vid, pid, logger)
    elif mode == "usb":
        return detect_usb_device(vid, pid, logger)
    else:
        logger.error(f"Unknown mode '{mode}' in config.")
        return None
