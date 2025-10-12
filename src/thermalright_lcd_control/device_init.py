# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb
import argparse
import os
import sys

import usb
import yaml

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

from .common.supported_devices import SUPPORTED_DEVICES


def _format_device_string(device: dict):
    vid = device.get('vid', 'N/A')
    pid = device.get('pid', 'N/A')
    width = device.get('width', 'N/A')
    height = device.get('height', 'N/A')
    return f"VID: {hex(vid)}, PID: {hex(pid)}  →  {width}×{height}"


def find_devices() -> list[dict]:
    for vid, pid, devices in SUPPORTED_DEVICES:
        device = usb.core.find(idVendor=vid, idProduct=pid)
        if device is not None:
            return devices
    return []


def create_device_info_file(config_dir, device_info):
    print(f"Configuring device: {_format_device_string(device_info)}")
    device_info_file = os.path.join(config_dir, "device_info.yaml")
    print(f"Saving configuration to : {device_info_file}")
    with open(device_info_file, "w") as f:
        yaml.dump(device_info, f)
    print("Configuration complete.")


def print_error_msg():
    error_message = (
        "\n⚠️  No supported Thermalright LCD device detected.\n\n"
        "Supported devices:\n"
    )

    for _, _, devices in SUPPORTED_DEVICES:
        for device in devices:
            error_message += f"  • {_format_device_string(device)}\n"

    error_message += (
        "\n💡 Tips:\n"
        "  - Ensure that your device is in the list below\n"
        "  - Check that your USB cable is connected.\n"
        "  - Ensure you have permission to access USB devices (try running as admin or root).\n"
    )

    print(error_message)


def print_select_message(devices: list):
    select_message = (
        "\n🔍 Multiple compatible devices found:\n\n"
    )

    for idx, device in enumerate(devices, start=1):
        select_message += f"  {idx}) {_format_device_string(device)}"

    select_message += "\nPlease enter the number of the device you want to use."
    print(select_message)


def choose_device(devices: list) -> dict | None:
    print_select_message(devices)
    try:
        selected_device = int(input("\n➡️  Select your device (1–{}): ".format(len(devices))))
        if 1 <= selected_device <= len(devices):
            return devices[selected_device - 1]
        else:
            print("❌ Invalid number. Please select a valid device index.\n")
            choose_device(devices)
    except ValueError:
        print("⚠️  Please enter a number corresponding to a device.\n")
        choose_device(devices)


def select_device() -> dict | None:
    print("Checking for available devices...\n")
    available_devices = find_devices()
    if len(available_devices) == 1:
        print("One Device Found...\n")
        return available_devices[0]
    elif len(available_devices) > 1:
        return choose_device(available_devices)
    else:
        return None


def main():
    parser = argparse.ArgumentParser(description="Thermalright LCD Control GUI")
    parser.add_argument('--config',
                        required=True,
                        help="Path to GUI configuration file (gui_config.yaml)")

    args = parser.parse_args()
    try:
        selected_device = select_device()
        if selected_device:
            create_device_info_file(args.config,
                                    selected_device)
            sys.exit(0)
        else:
            print_error_msg()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
