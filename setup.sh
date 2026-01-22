#!/bin/bash
# SignalSight - Automated Setup Script
# Traffic Light Detection System for Raspberry Pi
# This script installs all dependencies, sets up the environment, and prepares the system.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "SignalSight System Setup"
echo "Traffic Light Detection System"
echo "=========================================="
echo ""

# Check if running as root (we need sudo for some operations)
if [ "$EUID" -eq 0 ]; then
    echo "Please run this script as a normal user (not root)."
    echo "The script will use sudo when needed."
    exit 1
fi

# Detect if running on Raspberry Pi
IS_RPI=false
if [ -f /proc/device-tree/model ]; then
    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        IS_RPI=true
        echo "Detected: Raspberry Pi"
    fi
else
    echo "Detected: Desktop/Laptop (not Raspberry Pi)"
fi
echo ""

# Step 1: Install system dependencies
echo "[1/6] Installing system dependencies..."
sudo apt-get update

# Common dependencies
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    sqlite3 \
    git

# OpenCV dependencies
echo "Installing OpenCV dependencies..."
sudo apt-get install -y \
    libopencv-dev \
    python3-opencv \
    libhdf5-dev \
    libharfbuzz0b \
    libwebp7 \
    libtiff6 \
    libgstreamer1.0-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libatlas3-base

# Raspberry Pi specific packages
if [ "$IS_RPI" = true ]; then
    echo "Installing Raspberry Pi specific packages..."
    sudo apt-get install -y \
        python3-picamera2 \
        libcamera-apps \
        python3-libcamera
fi

echo "System dependencies installed."

# Step 2: Add user to dialout group (for serial/Arduino communication)
echo ""
echo "[2/6] Adding user to dialout group for serial access..."
if groups | grep -q dialout; then
    echo "User already in dialout group."
else
    sudo usermod -a -G dialout "$USER"
    echo "Added $USER to dialout group."
    echo "NOTE: You will need to log out and back in for this to take effect."
fi

# Step 3: Create Python virtual environment
echo ""
echo "[3/6] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
    echo "Virtual environment created with system site packages."
    echo "(This allows picamera2 to be accessible in the venv on Raspberry Pi)"
else
    echo "Virtual environment already exists."
fi

# Step 4: Activate venv and upgrade pip
echo ""
echo "[4/6] Activating virtual environment and upgrading pip..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel

# Step 5: Install Python dependencies
echo ""
echo "[5/6] Installing Python dependencies..."
echo "This may take several minutes, especially on Raspberry Pi..."

# Install requirements
pip install -r requirements.txt

# On non-Pi systems, we can install picamera2 via pip if needed (for testing)
# On Pi, we rely on the system package installed earlier
if [ "$IS_RPI" = false ]; then
    echo ""
    echo "Note: Skipping picamera2 installation on non-Raspberry Pi system."
    echo "Some camera-related features will not work without Raspberry Pi hardware."
fi

echo "Python dependencies installed."

# Step 6: Setup GPS subsystem (if needed)
echo ""
echo "[6/6] Setting up GPS subsystem..."
if [ -d "GPS" ]; then
    cd GPS
    if [ -f "setup.sh" ]; then
        echo "Running GPS-specific setup..."
        bash setup.sh
    fi
    cd "$SCRIPT_DIR"
else
    echo "GPS directory not found. Skipping GPS setup."
fi

# Done
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Virtual environment created at: $SCRIPT_DIR/venv"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate when done:"
echo "  deactivate"
echo ""
echo "Quick Start:"
echo ""
echo "1. Activate the virtual environment:"
echo "   cd $SCRIPT_DIR"
echo "   source venv/bin/activate"
echo ""
echo "2. Run YOLO detection (with display):"
echo "   cd YOLO_Detection_Model/CNN"
echo "   python CNNLivecopy3.py"
echo ""
echo "3. Run GPS system:"
echo "   cd GPS"
echo "   python gps_system.py"
echo ""
echo "4. Run tests:"
echo "   cd tests"
echo "   ./run_all_tests.sh"
echo ""
if groups | grep -qv dialout; then
    echo "⚠️  IMPORTANT: You need to log out and back in for serial port access!"
fi
echo ""
