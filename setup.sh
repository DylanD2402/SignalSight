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

# OpenCV and runtime dependencies
echo "Installing OpenCV and runtime dependencies..."
sudo apt-get install -y \
    python3-opencv \
    libatlas3-base \
    libgstreamer1.0-0 \
    libharfbuzz0b \
    libwebp7 \
    libtiff6

# Raspberry Pi specific packages
if [ "$IS_RPI" = true ]; then
    echo "Installing Raspberry Pi specific packages..."
    sudo apt-get install -y \
        python3-picamera2 \
        rpicam-apps \
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

# CRITICAL: Verify numpy version compatibility with picamera2/simplejpeg
# These system packages are compiled against numpy 1.x and will fail with numpy 2.x
echo ""
echo "Verifying numpy compatibility..."

NUMPY_VERSION=$(python -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "not found")
NUMPY_LOCATION=$(python -c "import numpy; print(numpy.__file__)" 2>/dev/null || echo "not found")

if [[ "$NUMPY_VERSION" == 2.* ]]; then
    echo "WARNING: Detected numpy 2.x ($NUMPY_VERSION) which is incompatible with picamera2!"
    echo "Removing numpy from venv to use system numpy 1.x..."

    # Remove numpy 2.x from venv
    rm -rf venv/lib/python*/site-packages/numpy
    rm -rf venv/lib/python*/site-packages/numpy-*.dist-info
    rm -rf venv/lib/python*/site-packages/numpy.libs

    # Verify fix
    NUMPY_VERSION=$(python -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "not found")
    NUMPY_LOCATION=$(python -c "import numpy; print(numpy.__file__)" 2>/dev/null || echo "not found")

    if [[ "$NUMPY_VERSION" == 1.* ]]; then
        echo "✓ Fixed: Now using system numpy $NUMPY_VERSION"
    else
        echo "ERROR: Could not resolve numpy version issue!"
        echo "Please check your installation manually."
    fi
elif [[ "$NUMPY_VERSION" == 1.* ]]; then
    echo "✓ Numpy version OK: $NUMPY_VERSION (compatible with picamera2)"
else
    echo "⚠ Warning: Could not detect numpy version"
fi

# On non-Pi systems, we can install picamera2 via pip if needed (for testing)
# On Pi, we rely on the system package installed earlier
if [ "$IS_RPI" = false ]; then
    echo ""
    echo "Note: Skipping picamera2 installation on non-Raspberry Pi system."
    echo "Some camera-related features will not work without Raspberry Pi hardware."
fi

echo "Python dependencies installed."

# Step 6: Setup GPS device and database
echo ""
echo "[6/6] Setting up GPS device and database..."

# Setup GPS device symlink
if [ -f "setup/99-gps.rules" ]; then
    echo "Installing GPS udev rule..."
    sudo cp setup/99-gps.rules /etc/udev/rules.d/99-gps.rules
    sudo chmod 644 /etc/udev/rules.d/99-gps.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "GPS udev rule installed. Device will be available at /dev/gps0"
else
    echo "Warning: setup/99-gps.rules not found. Skipping GPS symlink setup."
fi

# Check for GPS database
if [ -d "GPS" ]; then
    if [ -f "GPS/data/traffic_lights.db" ]; then
        echo "GPS database found: GPS/data/traffic_lights.db"
    else
        echo "GPS database not found. You can create it later by running:"
        echo "  cd GPS && python setup/database_setup.py --region ontario"
    fi
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
echo "   python cnn_system.py"
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
    echo "IMPORTANT: You need to log out and back in for serial port access!"
fi
echo ""
