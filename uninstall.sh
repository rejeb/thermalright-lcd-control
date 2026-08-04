#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

# Uninstallation script for thermalright-lcd-control.
# Handles BOTH the new system-wide version (/opt + autostart + udev) and the
# old version (root systemd service + per-user ~/.local/share install).

set -e

APP_NAME="thermalright-lcd-control"

# New system-wide install locations
APP_DIR="/opt/$APP_NAME"
BIN_DIR="/usr/bin"
# Older installs put the launcher here; cleaned up too so it cannot shadow.
BIN_DIR_LEGACY="/usr/local/bin"
DESKTOP_DIR="/usr/share/applications"
AUTOSTART_DIR="/etc/xdg/autostart"

# Legacy locations (old version)
SYSTEMD_SYSTEM_DIR="/etc/systemd/system"

# udev rules file (vendor dir) plus the location older installs used.
UDEV_RULES_FILE="/usr/lib/udev/rules.d/99-thermalright.rules"
UDEV_RULES_FILE_LEGACY="/etc/udev/rules.d/99-thermalright.rules"

# Set to 1 when invoked from install.sh (--from-install): preserves user config
# and skips all interactive prompts.
FROM_INSTALL=0

# Colors
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
        # Script is running as root.
        if [ -n "${SUDO_USER:-}" ]; then
            # Get the actual user info when running with sudo
            ACTUAL_USER="$SUDO_USER"
            ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
            log_info "Running with sudo as user: $ACTUAL_USER"
        else
            # Direct root, no invoking user: containers, images, CI. Remove the
            # system files; per-user data is left untouched (we cannot know whose
            # it is, and destroying it silently would be wrong).
            ACTUAL_USER=""
            ACTUAL_HOME=""
            log_warn "Running as root with no SUDO_USER (container/CI):"
            log_warn "removing system files only; per-user config is left in place."
        fi
    else
        log_error "This script must be run with sudo privileges"
        log_info "Removing /opt, udev rules and system entries requires root access"
        log_info "Please run: sudo ./uninstall.sh"
        exit 1
    fi
}

get_user_directories() {
    if [ -n "$ACTUAL_USER" ]; then
        USER_HOME="$ACTUAL_HOME"
    else
        USER_HOME="$HOME"
    fi

    CONFIG_DIR="$USER_HOME/.config/$APP_NAME"

    # Legacy per-user install locations (old version)
    LEGACY_APP_DIR="$USER_HOME/.local/share/$APP_NAME"
    LEGACY_DESKTOP_DIR="$USER_HOME/.local/share/applications"
}

remove_system_service() {
    log_info "Removing system service (old version)..."

    # Stop and disable service
    if systemctl is-active --quiet "$APP_NAME.service" 2>/dev/null; then
        log_info "Stopping $APP_NAME service..."
        systemctl stop "$APP_NAME.service"
    fi

    if systemctl is-enabled --quiet "$APP_NAME.service" 2>/dev/null; then
        log_info "Disabling $APP_NAME service..."
        systemctl disable "$APP_NAME.service"
    fi

    # Remove systemd service file
    if [ -f "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service" ]; then
        rm "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
        systemctl daemon-reload
        log_info "System service removed"
    fi
}

remove_udev_rules() {
    log_info "Removing udev rules..."

    removed=false
    for rules in "$UDEV_RULES_FILE" "$UDEV_RULES_FILE_LEGACY"; do
        if [ -f "$rules" ]; then
            rm -f "$rules"
            log_info "udev rules removed: $rules"
            removed=true
        fi
    done

    if [ "$removed" = true ] && command -v udevadm &> /dev/null; then
        udevadm control --reload-rules || true
        log_info "udev rules reloaded"
    fi

    # The user's 'plugdev' group membership is left intact (it may be used by
    # other tools).
}

remove_system_installation() {
    log_info "Removing system-wide installation..."

    # New version: /opt install
    if [ -d "$APP_DIR" ]; then
        rm -rf "$APP_DIR"
        log_info "Application directory removed: $APP_DIR"
    fi

    # Launchers: new (-app) and legacy (-gui/-service), in both the current
    # location and the /usr/local/bin one older installs used.
    for dir in "$BIN_DIR" "$BIN_DIR_LEGACY"; do
        for exe in "$APP_NAME-app" "$APP_NAME-gui" "$APP_NAME-service"; do
            if [ -f "$dir/$exe" ]; then
                rm -f "$dir/$exe"
                log_info "Executable removed: $dir/$exe"
            fi
        done
    done

    # System desktop entry
    if [ -f "$DESKTOP_DIR/$APP_NAME.desktop" ]; then
        rm -f "$DESKTOP_DIR/$APP_NAME.desktop"
        log_info "Desktop entry removed: $DESKTOP_DIR/$APP_NAME.desktop"
    fi

    # Autostart entry
    if [ -f "$AUTOSTART_DIR/$APP_NAME.desktop" ]; then
        rm -f "$AUTOSTART_DIR/$APP_NAME.desktop"
        log_info "Autostart entry removed: $AUTOSTART_DIR/$APP_NAME.desktop"
    fi
}

remove_legacy_user_installation() {
    log_info "Removing legacy per-user installation (old version) for: $ACTUAL_USER"

    # Old version installed the app under ~/.local/share
    if [ -d "$LEGACY_APP_DIR" ]; then
        rm -rf "$LEGACY_APP_DIR"
        log_info "Legacy application directory removed: $LEGACY_APP_DIR"
    fi

    # Old per-user desktop entry
    if [ -f "$LEGACY_DESKTOP_DIR/$APP_NAME.desktop" ]; then
        rm -f "$LEGACY_DESKTOP_DIR/$APP_NAME.desktop"
        log_info "Legacy desktop entry removed"
    fi
}

remove_user_configs() {
    # When called from install.sh, never touch (or prompt about) user config.
    if [ "$FROM_INSTALL" -eq 1 ]; then
        log_info "Preserving user configuration (called from installer)"
        return
    fi

    if [ ! -d "$CONFIG_DIR" ]; then
        return
    fi

    echo -n "Remove user configuration files in $CONFIG_DIR? [y/N]: "
    read -r REPLY
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        log_info "User configuration removed: $CONFIG_DIR"
    else
        log_info "User configuration preserved: $CONFIG_DIR"
    fi
}

remove_other_users() {
    # Skip any interaction when called from the installer.
    if [ "$FROM_INSTALL" -eq 1 ]; then
        return
    fi

    echo -n "Remove per-user config/legacy install for ALL users on this system? [y/N]: "
    read -r REPLY
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Removing per-user data for all users..."

        for user_home in /home/*; do
            if [ -d "$user_home" ]; then
                username=$(basename "$user_home")
                user_config_dir="$user_home/.config/$APP_NAME"
                user_legacy_app_dir="$user_home/.local/share/$APP_NAME"
                user_legacy_desktop="$user_home/.local/share/applications/$APP_NAME.desktop"

                if [ -d "$user_config_dir" ] || [ -d "$user_legacy_app_dir" ]; then
                    log_info "Removing data for user: $username"

                    rm -rf "$user_config_dir" 2>/dev/null || true
                    rm -rf "$user_legacy_app_dir" 2>/dev/null || true
                    rm -f "$user_legacy_desktop" 2>/dev/null || true
                fi
            fi
        done

        log_info "All per-user data removed"
    else
        log_info "Other users' data preserved"
    fi
}

parse_args() {
    for arg in "$@"; do
        case "$arg" in
            --from-install)
                FROM_INSTALL=1
                ;;
        esac
    done
}

main() {
    parse_args "$@"

    if [ "$FROM_INSTALL" -eq 1 ]; then
        log_info "Starting uninstallation of $APP_NAME (from installer)"
    else
        log_info "Starting uninstallation of $APP_NAME"
    fi

    # Check that script is run with sudo
    check_sudo

    # Resolve user-specific directories
    get_user_directories

    # Remove system service from the old version (requires root; no-op otherwise)
    remove_system_service

    # Remove udev rules
    remove_udev_rules

    # Remove the new system-wide installation
    remove_system_installation

    # Remove the old per-user installation (old version)
    remove_legacy_user_installation

    # Ask about user configs (skipped/preserved when called from installer)
    remove_user_configs

    # Ask about other users (skipped when called from installer)
    remove_other_users

    log_info ""
    log_info "Uninstallation completed!"
    log_info ""
    log_info "What was removed:"
    log_info "  ✅ System service (old version): $SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
    log_info "  ✅ System install: $APP_DIR"
    log_info "  ✅ Launcher(s): $BIN_DIR/$APP_NAME-app (and legacy -gui/-service)"
    log_info "  ✅ Desktop entry: $DESKTOP_DIR/$APP_NAME.desktop"
    log_info "  ✅ Autostart entry: $AUTOSTART_DIR/$APP_NAME.desktop"
    log_info "  ✅ udev rules: $UDEV_RULES_FILE"
    log_info "  ✅ Legacy per-user install: $LEGACY_APP_DIR"
}

# Run main function
main "$@"
