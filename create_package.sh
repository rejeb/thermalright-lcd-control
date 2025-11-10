#!/bin/bash

# Script to create tar.gz package for thermalright-lcd-control with wheel

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
DIST_DIR="dist"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

check_uv() {
    if ! command -v uv &> /dev/null; then
        log_error "uv is not installed. Please install uv first:"
        log_info "curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    log_info "Using uv: $(command -v uv)"
}

clean_build() {
    log_info "Cleaning build directories..."
    rm -rf "$BUILD_DIR"
    rm -rf "$DIST_DIR"
    mkdir -p "$PACKAGE_DIR"
    mkdir -p "$RELEASE_DIR"
}

build_wheel() {
    log_info "Building wheel with uv..."

    # Export exact versions from lock file
    log_info "Exporting locked dependencies..."
    uv export --frozen --no-hashes > "$PACKAGE_DIR/requirements.txt"

    # Build the wheel using uv
    uv build

    # Check if wheel was created
    WHEEL_FILE=$(ls dist/*.whl 2>/dev/null | head -n 1)
    if [ -z "$WHEEL_FILE" ]; then
        log_error "Failed to build wheel"
        exit 1
    fi

    log_info "Wheel built successfully: $WHEEL_FILE"
}

copy_files() {
    log_info "Copying package files..."

    # Copy the wheel file
    cp dist/*.whl "$PACKAGE_DIR/"
    log_info "Wheel file copied"

    # Copy resources
    if [ -d "resources" ]; then
        cp -r resources "$PACKAGE_DIR/"
        log_info "Resources copied"
    fi

    # Copy Scripts structure
    if [ -d "scripts" ]; then
        cp -r scripts/* "$PACKAGE_DIR/"
        log_info "Scripts structure copied"
    fi

    # Copy essential files
    cp README.md "$PACKAGE_DIR/"
    cp LICENSE "$PACKAGE_DIR/"
    cp pyproject.toml "$PACKAGE_DIR/"

    # Copy installation scripts
    cp install.sh "$PACKAGE_DIR/"
    cp uninstall.sh "$PACKAGE_DIR/"

    # Make scripts executable
    chmod +x "$PACKAGE_DIR/install.sh"
    chmod +x "$PACKAGE_DIR/uninstall.sh"

    log_info "All files copied successfully"
}

create_package() {
    log_info "Creating tar.gz package..."
    cd "$BUILD_DIR"
    tar -czvf "$PACKAGE_NAME.tar.gz" "$PACKAGE_NAME"
    cd ..

    # Copy to releases directory
    mkdir -p "$RELEASE_DIR"
    cp "$BUILD_DIR/$PACKAGE_NAME.tar.gz" "$RELEASE_DIR/"

    log_info "Package created: $RELEASE_DIR/$PACKAGE_NAME.tar.gz"
    log_info ""
    log_info "Package contents:"
    log_info "  - Wheel: $(basename dist/*.whl)"
    log_info "  - Resources: themes, configs, icons"
    log_info "  - Scripts: install.sh, uninstall.sh, systemd service"
    log_info "  - Lock file: uv.lock"
}

main() {
    log_info "Creating package for $APP_NAME v$VERSION"

    check_uv
    clean_build
    build_wheel
    copy_files
    create_package

    log_info ""
    log_info "✅ Package creation completed successfully!"
    log_info "📦 Package: $RELEASE_DIR/$PACKAGE_NAME.tar.gz"
}

main "$@"