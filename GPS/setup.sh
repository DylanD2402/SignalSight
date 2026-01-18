#!/bin/bash
# SignalSight GPS System - Automated Setup Script
# This script installs all dependencies, sets up the environment, and configures the GPS device.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "SignalSight GPS System Setup"
echo "=========================================="
echo ""

# Check if running as root (we need sudo for some operations)
if [ "$EUID" -eq 0 ]; then
    echo "Please run this script as a normal user (not root)."
    echo "The script will use sudo when needed."
    exit 1
fi

# Step 1: Install system dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential sqlite3

# Step 2: Add user to dialout group
echo ""
echo "[2/5] Adding user to dialout group for serial access..."
if groups | grep -q dialout; then
    echo "User already in dialout group."
else
    sudo usermod -a -G dialout "$USER"
    echo "Added $USER to dialout group."
    echo "NOTE: You will need to log out and back in for this to take effect."
fi

# Step 3: Setup GPS device symlink
echo ""
echo "[3/5] Setting up GPS device symlink (/dev/gps0)..."
if [ -f "setup/99-gps.rules" ]; then
    sudo cp setup/99-gps.rules /etc/udev/rules.d/99-gps.rules
    sudo chmod 644 /etc/udev/rules.d/99-gps.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "GPS udev rule installed. Device will be available at /dev/gps0"
else
    echo "Warning: setup/99-gps.rules not found. Skipping GPS symlink setup."
fi

# Step 4: Create Python virtual environment and install dependencies
echo ""
echo "[4/5] Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r setup/requirements.txt --quiet
echo "Python dependencies installed."

# Step 5: Check for database
echo ""
echo "[5/5] Checking database..."
if [ -f "data/traffic_lights.db" ]; then
    echo "Database found: data/traffic_lights.db"
else
    echo "Database not found. Creating database (this may take a few minutes)..."
    python setup/database_setup.py --region ontario
fi

# Done
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Log out and back in (if you were added to dialout group)"
echo ""
echo "2. Plug in your GPS module and verify it's detected:"
echo "   ls -l /dev/gps0"
echo ""
echo "3. Run the GPS system:"
echo "   cd $SCRIPT_DIR"
echo "   source venv/bin/activate"
echo "   python gps_system.py"
echo ""
echo "   For debug output:"
echo "   python gps_system.py --debug"
echo ""
