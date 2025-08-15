#!/bin/bash

# Script to run main_gui.py with virtual environment
# Usage: ./run_gui.sh


# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to virtual environment
VENV_PATH="$SCRIPT_DIR/.venv"

# Path to main_gui.py file
SERVICE_PATH="$SCRIPT_DIR/src/thermalright_lcd_control/main_gui.py"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment does not exist in $VENV_PATH"
    echo "Please create virtual environment with: python -m venv .venv"
    exit 1
fi

# Check if main_gui.py file exists
if [ ! -f "$SERVICE_PATH" ]; then
    echo "Error: main_gui.py file does not exist in $SERVICE_PATH"
    exit 1
fi

# Activate virtual environment and run main_gui.py
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

echo "Running main_gui.py..."
python "$SERVICE_PATH" --config ./resources/gui_config.yaml

# Deactivate virtual environment
deactivate