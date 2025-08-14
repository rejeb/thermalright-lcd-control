#!/bin/bash

# Script to create tar.gz package for thermalright-lcd-control

set -e


# Get version from pyproject.toml
get_version() {
    if command -v python3 >/dev/null 2>&1; then
        # Try with tomllib first (Python 3.11+)
        if python3 -c "import tomllib" 2>/dev/null; then
            python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
        # Fallback to toml module
        elif python3 -c "import toml" 2>/dev/null; then
            python3 -c "import toml; print(toml.load('pyproject.toml')['project']['version'])"
        else
            echo "1.0.0"
        fi
    else
        echo "1.0.0"
    fi
}

APP_NAME="thermalright-lcd-control"
VERSION=$(get_version)
PACKAGE_NAME="${APP_NAME}-${VERSION}"
BUILD_DIR="build"
PACKAGE_DIR="$BUILD_DIR/$PACKAGE_NAME"
RELEASE_DIR="releases"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

clean_build() {
    log_info "Cleaning build directory..."
    rm -rf "$BUILD_DIR"
    mkdir -p "$PACKAGE_DIR"
}

copy_files() {
    log_info "Copying application files..."

    # Copy source code
    rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' src/thermalright_lcd_control "$PACKAGE_DIR/"


    # Copy resources (includes .desktop and .service files)
    if [ -d "resources" ]; then
        cp -r resources "$PACKAGE_DIR/"
        log_info "Resources copied (including .desktop and .service files)"
    fi

    # Copy debian structure (for the executable)
    if [ -d "debian" ]; then
        cp -r debian/usr "$PACKAGE_DIR/"
        log_info "Debian structure copied (including executable)"
    fi

    # Copy project files
    cp pyproject.toml "$PACKAGE_DIR/"
    cp README.md "$PACKAGE_DIR/"
    cp LICENSE "$PACKAGE_DIR/"

    # Copy installation scripts
    cp install.sh "$PACKAGE_DIR/"
    cp uninstall.sh "$PACKAGE_DIR/"

    # Make scripts executable
    chmod +x "$PACKAGE_DIR/install.sh"
    chmod +x "$PACKAGE_DIR/uninstall.sh"
}

# Create necessary directories
mkdir -p pkg/DEBIAN
mkdir -p pkg/usr/local/share/thermalright-lcd-control/logs

# Create post-install script
cat > pkg/DEBIAN/postinst << 'EOF'
#!/bin/sh
set -e

# Create log directory for each user
for USER_HOME in /home/*; do
    if [ -d "$USER_HOME" ]; then
        USER=$(basename "$USER_HOME")
        LOG_DIR="$USER_HOME/.local/share/thermalright-lcd-control/logs"
        mkdir -p "$LOG_DIR"
        chown -R "$USER:$USER" "$LOG_DIR"
        chmod 755 "$LOG_DIR"
    fi
done
EOF

chmod 755 pkg/DEBIAN/postinst

create_package() {
    log_info "Creating tar.gz package..."
    tar -czvf "$BUILD_DIR/$PACKAGE_NAME.tar.gz" -C "$BUILD_DIR" "$PACKAGE_NAME"
    cp "$BUILD_DIR/$PACKAGE_NAME.tar.gz" $RELEASE_DIR
    log_info "Package created: $BUILD_DIR/$PACKAGE_NAME.tar.gz"
}

main() {
    clean_build
    copy_files
    create_package
}

main "$@"