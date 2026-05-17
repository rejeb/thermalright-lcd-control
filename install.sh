#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

# System-wide installation script for thermalright-lcd-control.
# The application is installed read-only under /opt and made available to ALL
# users. Each user gets their own writable config under ~/.config on first
# launch (handled by the launcher). udev rules grant non-root device access.
# The GUI is never run as root.

set -e

# Get version from pyproject.toml
get_version() {
    if [ -f "pyproject.toml" ] && command -v python3 >/dev/null 2>&1; then
        # Try with tomllib first (Python 3.11+)
        if python3 -c "import tomllib" 2>/dev/null; then
            python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo "1.0.0"
        # Fallback to toml module
        elif python3 -c "import toml" 2>/dev/null; then
            python3 -c "import toml; print(toml.load('pyproject.toml')['project']['version'])" 2>/dev/null || echo "1.0.0"
        else
            echo "1.0.0"
        fi
    else
        echo "1.0.0"
    fi
}


APP_NAME="thermalright-lcd-control"
VERSION=$(get_version)

# System-wide install locations
APP_DIR="/opt/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
BIN_DIR="/usr/local/bin"
DESKTOP_DIR="/usr/share/applications"
AUTOSTART_DIR="/etc/xdg/autostart"
UDEV_RULES_DST="/etc/udev/rules.d/99-thermalright.rules"

# Legacy locations (only used to detect/clean an old installation)
SYSTEMD_SYSTEM_DIR="/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_sudo() {
    if [[ $EUID -eq 0 ]]; then
        # Script is running as root
        if [ -z "$SUDO_USER" ]; then
            log_error "Please run this script with sudo, not as root directly"
            log_info "Correct usage: sudo ./install.sh"
            exit 1
        fi

        # Keep the invoking user (plugdev membership + per-user data checks).
        ACTUAL_USER="$SUDO_USER"
        ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)

        log_info "Running with sudo as user: $ACTUAL_USER"
        log_info "Installing system-wide to: $APP_DIR"
    else
        log_error "This script must be run with sudo privileges"
        log_info "Installing to /opt, udev rules and launchers requires root access"
        log_info "Please run: sudo ./install.sh"
        exit 1
    fi
}

check_uv_installed() {
    log_info "Checking if uv is installed..."

    if ! command -v uv &> /dev/null; then
        log_warn "uv is not installed. Installing uv system-wide..."

        # Download and install uv directly to /usr/local/bin
        curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh

        # Verify installation
        if ! command -v uv &> /dev/null; then
            log_error "Failed to install uv"
            log_info "Please install uv manually: https://github.com/astral-sh/uv"
            exit 1
        fi

        log_info "uv installed successfully at: $(command -v uv)"
    else
        log_info "uv is already installed at: $(command -v uv)"
    fi
}

check_dependencies() {
    log_info "Checking system dependencies..."

    # Check uv
    check_uv_installed

    # Check hidapi library
    check_hidapi

    log_info "Dependencies check passed"
}

check_hidapi() {
    log_info "Checking hidapi library..."

    HIDAPI_FOUND=false

    # Method 1: Check for header files
    if [ -f "/usr/include/hidapi/hidapi.h" ] || [ -f "/usr/local/include/hidapi/hidapi.h" ]; then
        HIDAPI_FOUND=true
        log_info "hidapi headers found"
    fi

    # Method 2: Check with pkg-config
    if command -v pkg-config &> /dev/null; then
        if pkg-config --exists hidapi-libusb || pkg-config --exists hidapi-hidraw; then
            HIDAPI_FOUND=true
            log_info "hidapi found via pkg-config"
        fi
    fi

    if [ "$HIDAPI_FOUND" = false ]; then
        log_error "hidapi library might not be installed system-wide"
        log_info "If installation fails, install hidapi with:"
        log_info "  Ubuntu/Debian: sudo apt-get install libhidapi-dev"
        log_info "  RHEL/CentOS:   sudo yum install hidapi-devel"
        log_info "  Fedora:        sudo dnf install hidapi-devel"
        log_info "  Arch:          sudo pacman -S hidapi"
        log_info ""
        log_info "Continuing installation..."
        exit 1
    fi
}

check_user_data_compatibility() {
    # Validate the FORMAT of the invoking user's themes tree: media and presets
    # must live under a per-resolution folder, i.e. themes/backgrounds/<resolution>/,
    # themes/foregrounds/<resolution>/ and themes/presets/<resolution>/
    # (resolution = digits + optional variant letter, e.g. 320240 or 1600720l).
    # themes/user_backgrounds (original uploaded media, flat) is not validated.
    # Missing folders are fine — they are seeded on first launch. Only a tree
    # breaking that format (the old pre-resolution layout) requires the wipe +
    # re-seed — so ask for explicit confirmation BEFORE doing anything.
    local user_config="$ACTUAL_HOME/.config/$APP_NAME"
    local user_themes="$user_config/themes"

    # Nothing to validate: fresh machine.
    [ -d "$user_themes" ] || return 0

    local invalid=""
    local sub entry name
    for sub in backgrounds foregrounds presets; do
        [ -d "$user_themes/$sub" ] || continue
        while IFS= read -r entry; do
            name="$(basename "$entry")"
            if [ -f "$entry" ]; then
                invalid="$invalid  themes/$sub/$name (file outside a resolution folder)\n"
            elif [[ ! "$name" =~ ^[0-9]+[a-z]?$ ]]; then
                invalid="$invalid  themes/$sub/$name (not a resolution folder)\n"
            fi
        done < <(find "$user_themes/$sub" -mindepth 1 -maxdepth 1)
    done

    if [ -z "$invalid" ]; then
        log_info "Existing themes layout matches this version"
        return 0
    fi

    log_warn "The installed themes layout does not follow the per-resolution format:"
    printf '%b' "$invalid" | while IFS= read -r line; do [ -n "$line" ] && log_warn "$line"; done
    log_warn "Continuing the installation will, for user '$ACTUAL_USER':"
    log_warn "  - DELETE the themes directory (except themes/user_backgrounds,"
    log_warn "    which keeps the original uploaded media) — resized copies and"
    log_warn "    saved themes will be permanently LOST"
    log_warn "  - DELETE the device configuration — the device(s) will have to"
    log_warn "    be configured again from the GUI"
    echo -n "Continue the installation? [y/N]: "
    read -r REPLY
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Installation aborted by user"
        exit 1
    fi

    # user_backgrounds holds the originals uploaded by the user: keep it.
    find "$user_themes" -mindepth 1 -maxdepth 1 ! -name user_backgrounds -exec rm -rf {} +
    rm -rf "$user_config/config"
    log_info "Removed outdated themes and device config for user '$ACTUAL_USER' (kept user_backgrounds)"
}

check_existing_installation() {
    log_info "Checking for an existing installation..."

    if [ -d "$APP_DIR" ] \
       || [ -f "$BIN_DIR/$APP_NAME-app" ] \
       || [ -f "$BIN_DIR/$APP_NAME-gui" ] \
       || [ -f "$BIN_DIR/$APP_NAME-service" ] \
       || [ -f "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service" ]; then
        log_warn "An existing installation was detected; uninstalling it first..."

        if [ -f "uninstall.sh" ]; then
            # --from-install preserves user config and skips interactive prompts.
            bash ./uninstall.sh --from-install
            log_info "Previous installation removed"
        else
            log_error "uninstall.sh not found; cannot remove the previous installation"
            exit 1
        fi
    else
        log_info "No existing installation found"
    fi
}

install_udev_rules() {
    log_info "Installing udev rules for non-root device access..."

    local rules_src="99-thermalright.rules"

    if [ ! -f "$rules_src" ]; then
        log_error "udev rules file not found: $rules_src"
        exit 1
    fi

    cp "$rules_src" "$UDEV_RULES_DST"
    chmod 644 "$UDEV_RULES_DST"
    log_info "Installed $UDEV_RULES_DST"

    # Make sure the invoking user is in the plugdev group (create it if needed).
    if [ -n "$ACTUAL_USER" ]; then
        groupadd -f plugdev
        if ! id -nG "$ACTUAL_USER" | grep -qw plugdev; then
            usermod -aG plugdev "$ACTUAL_USER"
            log_info "Added $ACTUAL_USER to the 'plugdev' group (log out/in to take effect)."
        fi
    fi

    # Reload and re-apply rules to already-connected devices when udev is available.
    if command -v udevadm &> /dev/null; then
        udevadm control --reload-rules || true
        udevadm trigger --action=add --subsystem-match=hidraw || true
        udevadm trigger --action=add --subsystem-match=usb || true
        udevadm settle || true
        log_info "udev rules reloaded and re-applied to connected devices"
    else
        log_warn "udevadm not found; rules will apply on next boot/replug"
    fi
}

install_application() {
    log_info "Installing $APP_NAME system-wide under $APP_DIR..."

    # Create the system install directory (root-owned, read-only for users)
    mkdir -p "$APP_DIR"

    # Copy resources and docs
    log_info "Copying application files to $APP_DIR..."
    cp -r resources "$APP_DIR/"
    cp README.md "$APP_DIR/"
    cp LICENSE "$APP_DIR/"

    # Find the wheel file
    WHEEL_FILE=$(ls *.whl 2>/dev/null | head -n 1)
    if [ -z "$WHEEL_FILE" ]; then
        log_error "Wheel file not found. Please run create_package.sh first."
        exit 1
    fi

    log_info "Found wheel: $WHEEL_FILE"

    # Check for requirements.txt with locked versions
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt not found. Package is incomplete."
        exit 1
    fi

    # Create the shared venv (as root) and install with exact versions.
    #
    # The interpreter is a uv-managed Python. By default uv installs managed
    # Pythons under root's home (~/.local/share/uv/python), which is mode 700 and
    # therefore unreadable by other users — the venv's python symlink would then
    # fail with "Permission denied" for normal users. Install the managed Python
    # into a shared, world-readable directory under /opt instead.
    log_info "Creating virtual environment and installing application..."
    log_info "Using locked dependency versions from requirements.txt"

    export UV_PYTHON_INSTALL_DIR="$APP_DIR/python"
    mkdir -p "$UV_PYTHON_INSTALL_DIR"

    # Python version to use (matches requires-python in pyproject.toml).
    PYTHON_VERSION="3.14"

    # Refresh uv (and its managed-Python version index) so the newest patch
    # release required by pyproject.toml is available. Best-effort: only works
    # when uv was installed via the standalone installer.
    log_info "Updating uv to refresh the managed-Python index..."
    uv self update || log_warn "uv self update skipped (uv not managed by its installer)"

    # Ensure the required managed Python is available in the shared location.
    uv python install --python-preference only-managed "$PYTHON_VERSION"

    # Create the venv from the managed Python; --relocatable keeps the venv
    # scripts using paths relative to the venv (robust under /opt).
    uv venv --python "$PYTHON_VERSION" --python-preference only-managed --relocatable "$VENV_DIR"
    uv pip install --python "$VENV_DIR" -r requirements.txt
    uv pip install --python "$VENV_DIR" --no-deps "$WHEEL_FILE"

    # Verify Python version in the venv
    VENV_PYTHON_VERSION=$("$VENV_DIR/bin/python" --version 2>&1)
    log_info "Virtual environment created with $VENV_PYTHON_VERSION"

    # Verify installation
    if [ -f "$VENV_DIR/bin/thermalright-lcd-control-app" ]; then
        log_info "Application and all dependencies installed successfully"
    else
        log_error "Application scripts not found after installation"
        exit 1
    fi

    # Copy the per-user launcher (resolves $HOME and bootstraps config at runtime)
    if [ -f "usr/bin/$APP_NAME-app" ]; then
        cp "usr/bin/$APP_NAME-app" "$BIN_DIR/"
        chmod 755 "$BIN_DIR/$APP_NAME-app"
        log_info "Launcher script installed: $BIN_DIR/$APP_NAME-app"
    else
        log_error "Launcher script not found: usr/bin/$APP_NAME-app"
        exit 1
    fi

    # Keep /opt root-owned and world-readable
    chown -R root:root "$APP_DIR"
    chmod -R a+rX "$APP_DIR"

    log_info "Application installed successfully from wheel"
}

configure_selinux() {
    # Only run on systems with SELinux
    if ! command -v selinuxenabled &> /dev/null || ! selinuxenabled; then
        return
    fi

    log_info "Configuring SELinux policy for thermalright-lcd-control..."

    # Method 1: Simple context change
    chcon -R -t bin_t "$VENV_DIR/bin"
    chcon -R -t lib_t "$VENV_DIR/lib"

    log_info "SELinux configuration completed"
}

install_desktop_entry() {
    log_info "Installing system-wide desktop entry..."

    if [ -f "$APP_NAME.desktop" ]; then
        mkdir -p "$DESKTOP_DIR"
        cp "$APP_NAME.desktop" "$DESKTOP_DIR/"

        # Point the icon to the shared install
        if [ -f "$APP_DIR/resources/256x256/icon.png" ]; then
            sed -i "s|Icon=.*|Icon=$APP_DIR/resources/256x256/icon.png|g" "$DESKTOP_DIR/$APP_NAME.desktop"
        elif [ -f "$APP_DIR/resources/128x128/icon.png" ]; then
            sed -i "s|Icon=.*|Icon=$APP_DIR/resources/128x128/icon.png|g" "$DESKTOP_DIR/$APP_NAME.desktop"
        else
            sed -i "s|Icon=.*|Icon=$APP_NAME|g" "$DESKTOP_DIR/$APP_NAME.desktop"
        fi

        chmod 644 "$DESKTOP_DIR/$APP_NAME.desktop"
        log_info "Desktop entry installed in $DESKTOP_DIR"
    else
        log_error "Desktop file not found: $APP_NAME.desktop"
        exit 1
    fi
}

install_autostart() {
    log_info "Installing autostart entry (launch at login for all users)..."

    if [ -f "$APP_NAME.desktop" ]; then
        mkdir -p "$AUTOSTART_DIR"
        cp "$APP_NAME.desktop" "$AUTOSTART_DIR/"

        # Launch minimized to the tray at login.
        sed -i "s|^Exec=.*|Exec=$APP_NAME-app --minimized|g" "$AUTOSTART_DIR/$APP_NAME.desktop"

        # Point the icon to the shared install
        if [ -f "$APP_DIR/resources/256x256/icon.png" ]; then
            sed -i "s|Icon=.*|Icon=$APP_DIR/resources/256x256/icon.png|g" "$AUTOSTART_DIR/$APP_NAME.desktop"
        fi

        # Make sure desktop environments honour the autostart entry.
        if ! grep -q "X-GNOME-Autostart-enabled" "$AUTOSTART_DIR/$APP_NAME.desktop"; then
            echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART_DIR/$APP_NAME.desktop"
        fi

        chmod 644 "$AUTOSTART_DIR/$APP_NAME.desktop"
        log_info "Autostart entry installed in $AUTOSTART_DIR"
    else
        log_error "Desktop file not found: $APP_NAME.desktop"
        exit 1
    fi
}

main() {
    log_info "Starting installation of $APP_NAME v$VERSION"
    log_info "System-wide install (GUI only, no system service); config is per-user"
    log_info "Using uv for dependency management"

    # Check that script is run with sudo
    check_sudo

    # If the per-user themes layout changed, confirm before wiping user data
    check_user_data_compatibility

    # Remove any previous installation (old root service or older version) first
    check_existing_installation

    # Check dependencies
    check_dependencies

    # Install udev rules so the device is reachable without root
    install_udev_rules

    # Install application system-wide
    install_application
    install_desktop_entry
    install_autostart
    configure_selinux

    log_info ""
    log_info "Installation completed successfully!"
    log_info ""
    log_info "Installation locations:"
    log_info "  Application: $APP_DIR (root-owned, read-only)"
    log_info "  Virtual Env: $VENV_DIR"
    log_info "  Launcher:    $BIN_DIR/$APP_NAME-app"
    log_info "  Desktop:     $DESKTOP_DIR/$APP_NAME.desktop"
    log_info "  Autostart:   $AUTOSTART_DIR/$APP_NAME.desktop"
    log_info "  udev rules:  $UDEV_RULES_DST"
    log_info "  Per-user config (created on first launch): ~/.config/$APP_NAME"
    log_info ""
    log_info "Status:"
    log_info "  ✅ GUI application installed system-wide (available to all users)"
    log_info "  ✅ Autostart at login (minimized to tray)"
    log_info "  ✅ udev rules installed (device access without root)"
    log_info "  ✅ Dependencies managed with uv"
    log_info ""
    log_info "Usage:"
    log_info "  GUI: $APP_NAME-app  (configure a device from the window)"
    log_info "  Note: log out/in once so the 'plugdev' group membership and"
    log_info "        the autostart entry take effect."
}

# Run main function
main "$@"
