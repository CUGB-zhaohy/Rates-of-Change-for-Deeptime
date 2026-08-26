#!/bin/bash

cd "$(dirname "$0")"

echo "============================================================"
echo "RoC Workflow Launcher for macOS"
echo "============================================================"
echo "Project folder:"
pwd
echo ""

PYTHON_CMD=""

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Python was not found on this Mac."
    echo ""
    echo "Please install Python 3.10 or later from:"
    echo "https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Python detected:"
$PYTHON_CMD --version
echo ""

if [ ! -d "venv" ]; then
    echo "No virtual environment was found."
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv

    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo "Virtual environment created successfully."
    echo ""
else
    echo "Existing virtual environment found."
    echo ""
fi

source "venv/bin/activate"

echo "Checking required Python packages..."
python -c "import yaml, numpy, pandas, scipy, matplotlib, openpyxl, pwlf" >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Required packages are missing."
    echo "Installing requirements from requirements.txt..."
    echo ""

    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

    if [ $? -ne 0 ]; then
        echo ""
        echo "Failed to install requirements."
        echo "Please check your internet connection or install manually:"
        echo "python -m pip install -r requirements.txt"
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi

    python -c "import yaml, numpy, pandas, scipy, matplotlib, openpyxl, pwlf" >/dev/null 2>&1

    if [ $? -ne 0 ]; then
        echo ""
        echo "Some required packages are still missing."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo ""
    echo "Requirements installed successfully."
else
    echo "Requirements are already installed."
fi

echo ""
echo "Checking Tkinter GUI support..."
python -c "import tkinter" >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo ""
    echo "Tkinter is not available in this Python environment."
    echo "Please install the official Python from python.org and try again."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "Starting RoC Workflow GUI..."
echo ""

python gui.py

echo ""
echo "GUI closed."
read -p "Press Enter to exit..."