#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

# Uninstallation script for thermalright-lcd-control

set -e

APP_NAME="thermalright-lcd-control"

# System service directory
SYSTEMD_SYSTEM_DIR="/etc/systemd/system"

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
        # Script is running as root
        if [ -z "$SUDO_USER" ]; then
            log_error "Please run this script with sudo, not as root directly"
            log_info "Correct usage: sudo ./uninstall.sh"
            exit 1
        fi

        # Get the actual user info when running with sudo
        ACTUAL_USER="$SUDO_USER"
        ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)

        log_info "Running with sudo as user: $ACTUAL_USER"
    else
        log_error "This script must be run with sudo privileges"
        log_info "System service removal requires root access"
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

    APP_DIR="$USER_HOME/.local/share/$APP_NAME"
    BIN_DIR="/usr/local/bin"
    CONFIG_DIR="$USER_HOME/.config/$APP_NAME"
    DESKTOP_DIR="$USER_HOME/.local/share/applications"
}

remove_system_service() {
    log_info "Removing system service..."

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

remove_user_installation() {
    log_info "Removing user installation for: $ACTUAL_USER"

    # Remove application directory
    if [ -d "$APP_DIR" ]; then
        rm -rf "$APP_DIR"
        log_info "Application directory removed: $APP_DIR"
    fi

    # Remove gui executable
    if [ -f "$BIN_DIR/$APP_NAME-gui" ]; then
        rm -f "$BIN_DIR/$APP_NAME-gui"
        log_info "Executable removed: $BIN_DIR/$APP_NAME-gui"
    fi

    # Remove service executable
    if [ -f "$BIN_DIR/$APP_NAME-service" ]; then
        rm -f "$BIN_DIR/$APP_NAME-service"
        log_info "Executable removed: $BIN_DIR/$APP_NAME-service"
    fi

    # Remove desktop entry
    if [ -f "$DESKTOP_DIR/$APP_NAME.desktop" ]; then
        rm -f "$DESKTOP_DIR/$APP_NAME.desktop"
        log_info "Desktop entry removed"
    fi
}

cleanup_path() {
    log_info "Cleaning up PATH modifications..."

    # Determine shell and shell RC file
    if [ -n "$ACTUAL_USER" ]; then
        USER_SHELL=$(getent passwd "$ACTUAL_USER" | cut -d: -f7)
    else
        USER_SHELL="$SHELL"
    fi

    if [[ "$USER_SHELL" == *"bash"* ]]; then
        SHELL_RC="$USER_HOME/.bashrc"
    elif [[ "$USER_SHELL" == *"zsh"* ]]; then
        SHELL_RC="$USER_HOME/.zshrc"
    else
        SHELL_RC="$USER_HOME/.profile"
    fi

    if [ -f "$SHELL_RC" ]; then
        # Remove the PATH entry added by the installer
        if grep -q "Added by thermalright-lcd-control installer" "$SHELL_RC"; then
            log_info "Removing PATH entry from $SHELL_RC"

            # Create a temporary file without the installer lines
            grep -v "Added by thermalright-lcd-control installer" "$SHELL_RC" > "$SHELL_RC.tmp"
            grep -v "export PATH=\"$BIN_DIR:\$PATH\"" "$SHELL_RC.tmp" > "$SHELL_RC.tmp2"

            # Remove empty lines that might have been left
            awk '!/^$/ || NR==1 || prev_empty==0 {prev_empty = (/^$/)} {if (!(/^$/ && prev_empty)) print}' "$SHELL_RC.tmp2" > "$SHELL_RC"

            rm -f "$SHELL_RC.tmp" "$SHELL_RC.tmp2"

            # Fix ownership if running as sudo
            if [ -n "$ACTUAL_USER" ]; then
                ACTUAL_UID=$(id -u "$ACTUAL_USER")
                ACTUAL_GID=$(id -g "$ACTUAL_USER")
                chown "$ACTUAL_UID:$ACTUAL_GID" "$SHELL_RC"
            fi

            log_info "PATH cleanup completed"
        fi
    fi
}

remove_other_users() {
    echo -n "Remove installation for ALL users on this system? [y/N]: "
    read -r REPLY
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Removing installation for all users..."

        for user_home in /home/*; do
            if [ -d "$user_home" ]; then
                username=$(basename "$user_home")
                user_app_dir="$user_home/.local/share/$APP_NAME"
                user_config_dir="$user_home/.config/$APP_NAME"
                user_bin_file="$user_home/.local/bin/$APP_NAME"
                user_desktop_file="$user_home/.local/share/applications/$APP_NAME.desktop"

                if [ -d "$user_app_dir" ] || [ -d "$user_config_dir" ] || [ -f "$user_bin_file" ]; then
                    log_info "Removing installation for user: $username"

                    rm -rf "$user_app_dir" 2>/dev/null || true
                    rm -rf "$user_config_dir" 2>/dev/null || true
                    rm -f "$user_bin_file" 2>/dev/null || true
                    rm -f "$user_desktop_file" 2>/dev/null || true
                fi
            fi
        done

        log_info "All user installations removed"
    else
        log_info "Other user installations preserved"
    fi
}

main() {
    log_info "Starting uninstallation of $APP_NAME"

    # Check that script is run with sudo
    check_sudo

    # Get user directories
    get_user_directories

    # Remove system service (requires root)
    remove_system_service

    # Remove user installation
    remove_user_installation

    # Ask about user configs
    remove_user_configs

    # Clean up PATH modifications
    cleanup_path

    # Ask about other users
    remove_other_users

    log_info ""
    log_info "Uninstallation completed!"
    log_info ""
    log_info "What was removed:"
    log_info "  ✅ System service: $SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
    log_info "  ✅ User application: $APP_DIR"
    log_info "  ✅ User executable: $BIN_DIR/$APP_NAME"
    log_info "  ✅ Desktop entry: $DESKTOP_DIR/$APP_NAME.desktop"
    log_info "  ✅ PATH modifications cleaned up"
    log_info ""
    log_info "User $ACTUAL_USER may need to restart their terminal for PATH changes to take effect."
}

# Run main function
main "$@"