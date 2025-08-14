#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

# User-space installation script for thermalright-lcd-control
# Application in user space, but system service for root execution

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

# User directories
USER_HOME="$HOME"
APP_DIR="$USER_HOME/.local/share/$APP_NAME"
BIN_DIR="$USER_HOME/.local/bin"
CONFIG_DIR="$USER_HOME/.config/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
DESKTOP_DIR="$USER_HOME/.local/share/applications"

# System service directory
SYSTEMD_SYSTEM_DIR="/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO] $(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN] $(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR] $(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

check_sudo() {
    if [[ $EUID -eq 0 ]]; then
        # Script is running as root
        if [ -z "$SUDO_USER" ]; then
            log_error "Please run this script with sudo, not as root directly"
            log_info "Correct usage: sudo ./install.sh"
            exit 1
        fi

        # Get the actual user info when running with sudo
        ACTUAL_USER="$SUDO_USER"
        ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        ACTUAL_UID=$(id -u "$SUDO_USER")
        ACTUAL_GID=$(id -g "$SUDO_USER")

        # Update user paths to use the actual user's home
        USER_HOME="$ACTUAL_HOME"
        APP_DIR="$USER_HOME/.local/share/$APP_NAME"
        BIN_DIR="$USER_HOME/.local/bin"
        CONFIG_DIR="$USER_HOME/.config/$APP_NAME"
        VENV_DIR="$APP_DIR/venv"
        DESKTOP_DIR="$USER_HOME/.local/share/applications"

        log_info "Running with sudo as user: $ACTUAL_USER"
        log_info "Installing to: $USER_HOME"
    else
        log_error "This script must be run with sudo privileges"
        log_info "System service installation requires root access"
        log_info "Please run: sudo ./install.sh"
        exit 1
    fi
}

check_dependencies() {
    log_info "Checking system dependencies..."

    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
        log_error "pip is required but not installed"
        exit 1
    fi

    # Check venv module
    if ! python3 -c "import venv" &> /dev/null; then
        log_error "python3-venv is required but not installed"
        log_info "Install it with: sudo apt-get install python3-venv"
        exit 1
    fi

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

    # Method 3: Try to import hid in Python
    if python3 -c "import hid" &> /dev/null; then
        HIDAPI_FOUND=true
        log_info "hidapi Python module already available"
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

install_application() {
    log_info "Installing $APP_NAME in user space..."

    # Create user directories
    mkdir -p "$APP_DIR"
    mkdir -p "$BIN_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DESKTOP_DIR"

    # Create log directory
    LOG_DIR="$HOME/.local/share/thermalright-lcd-control/logs"
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    touch "$LOG_DIR/error.log"
    chmod 644 "$LOG_DIR/error.log"

    # Copy source files
    log_info "Copying application files to $APP_DIR..."
    cp -r "thermalright_lcd_control" "$APP_DIR/"
    cp -r resources "$APP_DIR/"
    cp pyproject.toml "$APP_DIR/"
    cp README.md "$APP_DIR/"
    cp LICENSE "$APP_DIR/"

    # Copy and adapt the launcher script from usr/bin
    if [ -f "usr/bin/$APP_NAME" ]; then
        cp "usr/bin/$APP_NAME" "$BIN_DIR/"

        # Update paths in the launcher script for user installation
        sed -i "s|/opt/thermalright-lcd-control/venv|$VENV_DIR|g" "$BIN_DIR/$APP_NAME"
        sed -i "s|/usr/lib/thermalright-lcd-control|$APP_DIR/|g" "$BIN_DIR/$APP_NAME"
        sed -i "s|/etc/thermalright-lcd-control/gui_config.yaml|$CONFIG_DIR/gui_config.yaml|g" "$BIN_DIR/$APP_NAME"

        chmod +x "$BIN_DIR/$APP_NAME"
        log_info "Launcher script adapted and copied to $BIN_DIR"
    else
        log_error "Launcher script not found in usr/bin/$APP_NAME"
        exit 1
    fi

    # Create Python virtual environment
    log_info "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip

    # Install Python dependencies
    log_info "Installing Python dependencies..."
    cd "$APP_DIR"

    # Try to use tomllib for Python 3.11+, fallback for older versions
    if python3 -c "import tomllib" 2>/dev/null; then
        log_info "Using tomllib to parse dependencies"
        DEPS=$("$VENV_DIR/bin/python3" -c "import tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; print(' '.join(deps))")
        "$VENV_DIR/bin/pip" install $DEPS
    else
        log_info "Using fallback dependency list"
        "$VENV_DIR/bin/pip" install requests>=2.0 PySide6>=6.5 "hid~=1.0.8" psutil>=5.8.0 opencv-python>=4.12.0.88 pyusb>=1.3.1 pillow>=11.3.0 pyyaml>=6.0.2
    fi

    cd - > /dev/null

    # Fix ownership if running as sudo
    if [ -n "$SUDO_USER" ]; then
        chown -R "$ACTUAL_UID:$ACTUAL_GID" "$APP_DIR"
        chown -R "$ACTUAL_UID:$ACTUAL_GID" "$BIN_DIR/$APP_NAME"
        log_info "Fixed ownership for user: $ACTUAL_USER"
    fi

    log_info "Application installed successfully"
}

install_system_service() {
    log_info "Installing system service..."

    # Copy and adapt the service file from resources
    if [ -f "resources/$APP_NAME.service" ]; then
        cp "resources/$APP_NAME.service" "$SYSTEMD_SYSTEM_DIR/"

        # Update service file for user installation paths but keep root execution
        sed -i "s|/opt/thermalright-lcd-control/venv/bin/python|$VENV_DIR/bin/python|g" "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
        sed -i "s|/usr/lib/thermalright-lcd-control|$APP_DIR|g" "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
        sed -i "s|WorkingDirectory=.*|WorkingDirectory=$APP_DIR|g" "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
        sed -i "s|Environment=PYTHONPATH=.*|Environment=PYTHONPATH=$APP_DIR|g" "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
        sed -i "s|@config_file@|$CONFIG_DIR/config|g" "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"

        # Keep User=root for system service
        # Keep After=network.target and WantedBy=multi-user.target for system service

        chmod 644 "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"

        # Reload systemd and enable service
        systemctl daemon-reload
        systemctl enable "$APP_NAME.service"
        systemctl start $APP_NAME

        log_info "System service installed and enabled"
    else
        log_error "Service file not found in resources/$APP_NAME.service"
        exit 1
    fi
}

fix_theme_paths() {
    log_info "Fixing paths in theme files and configuration..."

    # Fix paths in config.yaml
    if [ -d "$CONFIG_DIR/config" ]; then
        log_info "Updating paths in config.yaml..."
        find "$CONFIG_DIR/config" -type f \( -name "*.yaml" -o -name "*.yml" \) -exec sed -i "s|/usr/share/thermalright-lcd-control/|$CONFIG_DIR/|g" {} \;

    fi

    # Fix paths in all preset files in themes/presets directory
    if [ -d "$CONFIG_DIR/themes/presets" ]; then
        log_info "Updating paths in preset files..."
        find "$CONFIG_DIR/themes/presets" -type f \( -name "*.yaml" -o -name "*.yml" \) -exec sed -i "s|/usr/share/thermalright-lcd-control/|$CONFIG_DIR/|g" {} \;

        # Count and report updated files
        PRESET_COUNT=$(find "$CONFIG_DIR/themes/presets" -type f \( -name "*.yaml" -o -name "*.yml" \) | wc -l)
        if [ "$PRESET_COUNT" -gt 0 ]; then
            log_info "Updated paths in $PRESET_COUNT preset files"
        fi
    fi

    # Fix paths in any other YAML files in themes directory
    if [ -d "$CONFIG_DIR/themes" ]; then
        log_info "Updating paths in all theme YAML files..."
        find "$CONFIG_DIR/themes" -type f \( -name "*.yaml" -o -name "*.yml" \) -exec sed -i "s|/usr/share/thermalright-lcd-control/|$CONFIG_DIR/|g" {} \;
    fi

    # Fix paths in any JSON files if they exist
    if [ -d "$CONFIG_DIR/themes" ]; then
        FOUND_JSON=$(find "$CONFIG_DIR/themes" -type f -name "*.json" | wc -l)
        if [ "$FOUND_JSON" -gt 0 ]; then
            log_info "Updating paths in JSON configuration files..."
            find "$CONFIG_DIR/themes" -type f -name "*.json" -exec sed -i "s|/usr/share/thermalright-lcd-control/|$CONFIG_DIR/|g" {} \;
        fi
    fi

    log_info "Path fixing completed"
}

setup_user_configs() {
    log_info "Setting up user configurations..."

    # Copy configuration files
    if [ -d "resources/config" ]; then
        cp -r "resources/config" "$CONFIG_DIR/"
    fi

    if [ -f "resources/gui_config.yaml" ]; then
        cp "resources/gui_config.yaml" "$CONFIG_DIR/"

        # Update paths in GUI config
        sed -i "s|themes_dir: \"./resources/themes/presets\"|themes_dir: \"$CONFIG_DIR/themes/presets\"|g" "$CONFIG_DIR/gui_config.yaml"
        sed -i "s|backgrounds_dir: \"./resources/themes/backgrounds\"|backgrounds_dir: \"$CONFIG_DIR/themes/backgrounds\"|g" "$CONFIG_DIR/gui_config.yaml"
        sed -i "s|foregrounds_dir: \"./resources/themes/foregrounds\"|foregrounds_dir: \"$CONFIG_DIR/themes/foregrounds\"|g" "$CONFIG_DIR/gui_config.yaml"
        sed -i "s|service_config: \"./resources/config\"|service_config: \"$CONFIG_DIR/config\"|g" "$CONFIG_DIR/gui_config.yaml"
    fi

    # Copy themes to user directory
    if [ -d "resources/themes" ]; then
        cp -R "resources/themes" "$CONFIG_DIR/"
        log_info "Themes copied to $CONFIG_DIR/themes"
    fi

    # Fix theme and config file paths after copying
    fix_theme_paths

    # Fix ownership if running as sudo
    if [ -n "$SUDO_USER" ]; then
        chown -R "$ACTUAL_UID:$ACTUAL_GID" "$CONFIG_DIR"
    fi

    log_info "User configurations set up in $CONFIG_DIR"
}

install_desktop_entry() {
    log_info "Installing desktop entry..."

    # Copy and adapt desktop file from resources
    if [ -f "resources/$APP_NAME.desktop" ]; then
        cp "resources/$APP_NAME.desktop" "$DESKTOP_DIR/"

        # Update paths in desktop file
        sed -i "s|Exec=.*|Exec=$BIN_DIR/$APP_NAME|g" "$DESKTOP_DIR/$APP_NAME.desktop"

        # Update icon path if it exists in resources
        if [ -f "resources/256x256/icon.png" ]; then
            sed -i "s|Icon=.*|Icon=$APP_DIR/resources/256x256/icon.png|g" "$DESKTOP_DIR/$APP_NAME.desktop"
        elif [ -f "resources/128x128/icon.png" ]; then
            sed -i "s|Icon=.*|Icon=$APP_DIR/resources/128x128/icon.png|g" "$DESKTOP_DIR/$APP_NAME.desktop"
        else
            sed -i "s|Icon=.*|Icon=$APP_NAME|g" "$DESKTOP_DIR/$APP_NAME.desktop"
        fi

        chmod 644 "$DESKTOP_DIR/$APP_NAME.desktop"

        # Fix ownership if running as sudo
        if [ -n "$SUDO_USER" ]; then
            chown "$ACTUAL_UID:$ACTUAL_GID" "$DESKTOP_DIR/$APP_NAME.desktop"
        fi

        log_info "Desktop entry installed in $DESKTOP_DIR"
    else
        log_error "Desktop file not found in resources/$APP_NAME.desktop"
        exit 1
    fi
}

setup_path() {
    log_info "Setting up PATH..."

    # Determine shell and shell RC file
    if [ -n "$SUDO_USER" ]; then
        USER_SHELL=$(getent passwd "$SUDO_USER" | cut -d: -f7)
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

    if [ -f "$SHELL_RC" ] && ! grep -q "$BIN_DIR" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# Added by thermalright-lcd-control installer" >> "$SHELL_RC"
        echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"

        # Fix ownership if running as sudo
        if [ -n "$SUDO_USER" ]; then
            chown "$ACTUAL_UID:$ACTUAL_GID" "$SHELL_RC"
        fi

        log_info "Added $BIN_DIR to PATH in $SHELL_RC"
        log_warn "User may need to restart terminal or run: source $SHELL_RC"
    fi
}

main() {
    log_info "Starting installation of $APP_NAME v$VERSION"
    log_info "Application: user space, Service: system (root)"

    # Check that script is run with sudo
    check_sudo

    # Check dependencies
    check_dependencies

    # Install application in user space
    install_application
    setup_user_configs
    install_desktop_entry
    setup_path

    # Install system service
    install_system_service

    log_info ""
    log_info "Installation completed successfully!"
    log_info ""
    log_info "Installation locations:"
    log_info "  User: $ACTUAL_USER"
    log_info "  Application: $APP_DIR"
    log_info "  Virtual Env: $VENV_DIR"
    log_info "  Executables: $BIN_DIR"
    log_info "  Config: $CONFIG_DIR"
    log_info "  Service: $SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
    log_info ""
    log_info "Status:"
    log_info "  ✅ GUI application installed (user execution)"
    log_info "  ✅ System service installed (root execution)"
    log_info "  ✅ Theme and config paths updated"
    log_info ""
    log_info "Usage:"
    log_info "  GUI: $APP_NAME (as user $ACTUAL_USER)"
    log_info "  Service: sudo systemctl start $APP_NAME"
    log_info "  Status: sudo systemctl status $APP_NAME"
    log_info ""
    log_info "Note: User $ACTUAL_USER may need to restart their terminal or run:"
    log_info "  export PATH=\"$BIN_DIR:\$PATH\""
}

# Run main function
main "$@"