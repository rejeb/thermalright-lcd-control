
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
BIN_DIR="/usr/local/bin"
CONFIG_DIR="$USER_HOME/.config/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
DESKTOP_DIR="$USER_HOME/.local/share/applications"
LOG_DIR="$USER_HOME/.local/state/$APP_NAME"

# System service directory
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

        # Get the actual user info when running with sudo
        ACTUAL_USER="$SUDO_USER"
        ACTUAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        ACTUAL_UID=$(id -u "$SUDO_USER")
        ACTUAL_GID=$(id -g "$SUDO_USER")

        # Update user paths to use the actual user's home
        USER_HOME="$ACTUAL_HOME"
        APP_DIR="$USER_HOME/.local/share/$APP_NAME"
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

install_application() {
    log_info "Installing $APP_NAME in user space..."

    # Create user directories
    mkdir -p "$APP_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DESKTOP_DIR"
    mkdir -p "$LOG_DIR"

    # Copy resources
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

    # Create venv and install with exact versions
    log_info "Creating virtual environment and installing application..."
    log_info "Using locked dependency versions from requirements.txt"

    # Create venv and install wheel as the actual user
    if [ -n "$SUDO_USER" ]; then
        chown -R "$ACTUAL_UID:$ACTUAL_GID" "$APP_DIR"
        # Create venv with uv (uses requires-python from wheel metadata)
        sudo -u "$SUDO_USER" HOME="$USER_HOME" uv venv "$VENV_DIR"
        # Install dependencies with exact versions from requirements.txt
        sudo -u "$SUDO_USER" HOME="$USER_HOME" uv pip install --python "$VENV_DIR" -r requirements.txt

        # Then install the wheel (will use already installed dependencies)
        sudo -u "$SUDO_USER" HOME="$USER_HOME" uv pip install --python "$VENV_DIR" --no-deps "$WHEEL_FILE"
    else
        # Create venv with uv
        uv venv "$VENV_DIR"

        # Install dependencies with exact versions
        uv pip install --python "$VENV_DIR" -r requirements.txt

        # Then install the wheel without dependencies
        uv pip install --python "$VENV_DIR" --no-deps "$WHEEL_FILE"
    fi

    # Verify Python version in the venv
    VENV_PYTHON_VERSION=$("$VENV_DIR/bin/python" --version 2>&1)
    log_info "Virtual environment created with $VENV_PYTHON_VERSION"

    # Verify installation
    if [ -f "$VENV_DIR/bin/thermalright-lcd-control-gui" ]; then
        log_info "Application and all dependencies installed successfully"
    else
        log_error "Application scripts not found after installation"
        exit 1
    fi

    # Copy gui launcher script
    if [ -f "usr/bin/$APP_NAME-gui" ]; then
        cp "usr/bin/$APP_NAME-gui" "$BIN_DIR/"

        # Update paths in the launcher script
        sed -i "s|@user_home@|$USER_HOME|g" "$BIN_DIR/$APP_NAME-gui"

        chmod 755 "$BIN_DIR/$APP_NAME-gui"
        log_info "Launcher script installed"
    fi

    # Copy service launcher script
    if [ -f "usr/bin/$APP_NAME-service" ]; then
        cp "usr/bin/$APP_NAME-service" "$BIN_DIR/"

        # Update paths in the launcher script
        sed -i "s|@user_home@|$USER_HOME|g" "$BIN_DIR/$APP_NAME-service"

        chmod 755 "$BIN_DIR/$APP_NAME-service"
        log_info "Launcher script installed"
    fi

    # Fix ownership if running as sudo
    if [ -n "$SUDO_USER" ]; then
        chown -R "$ACTUAL_UID:$ACTUAL_GID" "$APP_DIR"

        log_info "Fixed ownership for user: $ACTUAL_USER"
    fi

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

    # Method 2: Create a persistent policy (optional, more complex)
    # This would require audit2allow and a custom policy module

    log_info "SELinux configuration completed"
}

install_system_service() {
    log_info "Installing system service..."

    # Copy and adapt the service file from resources
    if [ -f "$APP_NAME.service" ]; then
        cp "$APP_NAME.service" "$SYSTEMD_SYSTEM_DIR/"

        # Update service file for user installation paths but keep root execution
        sed -i "s|@user_home@|$USER_HOME|g" "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
        # Keep User=root for system service
        # Keep After=network.target and WantedBy=multi-user.target for system service

        chmod 644 "$SYSTEMD_SYSTEM_DIR/$APP_NAME.service"

        # Reload systemd and enable service
        systemctl daemon-reload
        systemctl enable "$APP_NAME.service"
        systemctl start $APP_NAME

        log_info "System service installed and enabled"
    else
        log_error "Service file not found in $APP_NAME.service"
        exit 1
    fi
}

fix_theme_paths() {
    log_info "Fixing paths in theme files and configuration..."

    # Fix paths in config.yaml
    if [ -d "$CONFIG_DIR/config" ]; then
        log_info "Updating paths in config.yaml..."
        find "$CONFIG_DIR/config" -type f \( -name "*.yaml" -o -name "*.yml" \) -exec sed -i "s|./resources/|$CONFIG_DIR/|g" {} \;

    fi

    # Fix paths in all preset files in themes/presets directory
    if [ -d "$CONFIG_DIR/themes/presets" ]; then
        log_info "Updating paths in preset files..."
        find "$CONFIG_DIR/themes/presets" -type f \( -name "*.yaml" -o -name "*.yml" \) -exec sed -i "s|./resources/|$CONFIG_DIR/|g" {} \;

        # Count and report updated files
        PRESET_COUNT=$(find "$CONFIG_DIR/themes/presets" -type f \( -name "*.yaml" -o -name "*.yml" \) | wc -l)
        if [ "$PRESET_COUNT" -gt 0 ]; then
            log_info "Updated paths in $PRESET_COUNT preset files"
        fi
    fi

    # Fix paths in any other YAML files in themes directory
    if [ -d "$CONFIG_DIR/themes" ]; then
        log_info "Updating paths in all theme YAML files..."
        find "$CONFIG_DIR/themes" -type f \( -name "*.yaml" -o -name "*.yml" \) -exec sed -i "s|./resources/|$CONFIG_DIR/|g" {} \;
    fi

    # Fix paths in any JSON files if they exist
    if [ -d "$CONFIG_DIR/themes" ]; then
        FOUND_JSON=$(find "$CONFIG_DIR/themes" -type f -name "*.json" | wc -l)
        if [ "$FOUND_JSON" -gt 0 ]; then
            log_info "Updating paths in JSON configuration files..."
            find "$CONFIG_DIR/themes" -type f -name "*.json" -exec sed -i "s|./resources/|$CONFIG_DIR/|g" {} \;
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
    if [ -f "$APP_NAME.desktop" ]; then
        cp "$APP_NAME.desktop" "$DESKTOP_DIR/"

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
        log_error "Desktop file not found in APP_NAME.desktop"
        exit 1
    fi
}

setup_device() {
    PYTHONPATH="$APP_DIR:$PYTHONPATH"
    export PYTHONPATH
    $VENV_DIR/bin/python -m thermalright_lcd_control.device_init --config "$CONFIG_DIR/config"
}

main() {
    log_info "Starting installation of $APP_NAME v$VERSION"
    log_info "Application: user space, Service: system (root)"
    log_info "Using uv for dependency management"

    # Check that script is run with sudo
    check_sudo

    # Check dependencies
    check_dependencies

    # Install application in user space
    install_application
    setup_user_configs
    install_desktop_entry

    setup_device

    local setup_status=$?

    echo "return status $setup_status"

    if [ $setup_status -eq 0 ]; then
       # Install system service
       configure_selinux
       install_system_service

       log_info ""
       log_info "Installation completed successfully!"
       log_info ""
       log_info "Installation locations:"
       log_info "  User: $ACTUAL_USER"
       log_info "  Application: $APP_DIR"
       log_info "  Virtual Env: $VENV_DIR"
       log_info "  Python Version: Managed by uv (from pyproject.toml)"
       log_info "  Executables: $BIN_DIR"
       log_info "  Config: $CONFIG_DIR"
       log_info "  Service: $SYSTEMD_SYSTEM_DIR/$APP_NAME.service"
       log_info ""
       log_info "Status:"
       log_info "  ✅ GUI application installed (user execution)"
       log_info "  ✅ System service installed (root execution)"
       log_info "  ✅ Dependencies managed with uv"
       log_info "  ✅ Python version auto-detected from pyproject.toml"
       log_info "  ✅ Theme and config paths updated"
       log_info ""
       log_info "Usage:"
       log_info "  GUI: $APP_NAME (as user $ACTUAL_USER)"
       log_info "  Service: sudo systemctl start $APP_NAME"
       log_info "  Status: sudo systemctl status $APP_NAME"
    else
      log_error "No supported device was found or Device configuration aborted!"
    fi

}

# Run main function
main "$@"
