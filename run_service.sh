#!/bin/bash

# Script to run service.py with virtual environment
# Usage: sudo ./run_service.sh

# Check if script is run with sudo privileges
if [ $EUID -ne 0 ]; then
    echo "Error: This script must be run with sudo privileges"
    echo "Usage: sudo ./run_service.sh"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to virtual environment
VENV_PATH="$SCRIPT_DIR/.venv"

# Path to service.py file
SERVICE_PATH="$SCRIPT_DIR/src/thermalright_lcd_control/service.py"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment does not exist in $VENV_PATH"
    echo "Please create virtual environment with: python -m venv .venv"
    exit 1
fi

# Check if service.py file exists
if [ ! -f "$SERVICE_PATH" ]; then
    echo "Error: service.py file does not exist in $SERVICE_PATH"
    exit 1
fi

# Activate virtual environment and run service.py
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

echo "Running service.py..."
python "$SERVICE_PATH" "$@" --config ./resources/config

# Deactivate virtual environment
deactivate