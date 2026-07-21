#!/bin/bash
# Install udev rules so the Thermalright LCD can be accessed without root.
# Usage: sudo ./scripts/install-udev-rules.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Error: must be run as root (it writes to /etc/udev/rules.d)."
    echo "Usage: sudo ./scripts/install-udev-rules.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_SRC="$SCRIPT_DIR/99-thermalright.rules"
RULES_DST="/etc/udev/rules.d/99-thermalright.rules"

cp "$RULES_SRC" "$RULES_DST"
echo "Installed $RULES_DST"

# Make sure the invoking user is in plugdev.
TARGET_USER="${SUDO_USER:-$USER}"
if ! id -nG "$TARGET_USER" | grep -qw plugdev; then
    usermod -aG plugdev "$TARGET_USER"
    echo "Added $TARGET_USER to the 'plugdev' group (log out/in to take effect)."
fi

udevadm control --reload-rules
# Re-fire "add" events so MODE/GROUP/TAG get re-applied to already-connected
# devices, avoiding the need to replug or reboot.
udevadm trigger --action=add --subsystem-match=hidraw
udevadm trigger --action=add --subsystem-match=usb
udevadm settle
echo "udev rules reloaded and re-applied to connected devices."
echo "If the device is currently held open by a running service, stop it first."
