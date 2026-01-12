#!/bin/bash
# Setup script for GPS device persistent naming
# This ensures the GPS module always shows up with a consistent device name

echo "=========================================="
echo "GPS Device Setup"
echo "=========================================="
echo ""

# Check if GPS is connected
if [ ! -e /dev/ttyUSB1 ]; then
    echo "Warning: GPS device not found at /dev/ttyUSB1"
    echo "Please check that your GPS module is plugged in."
    echo ""
    ls -l /dev/ttyUSB* 2>&1
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Installing udev rule..."
sudo cp 99-gps.rules /etc/udev/rules.d/99-gps.rules

echo "Setting permissions..."
sudo chmod 644 /etc/udev/rules.d/99-gps.rules

echo "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "GPS device setup complete!"
echo ""
echo "Your GPS module will now be available at:"
echo "  /dev/gps0  (recommended - always consistent)"
echo ""
echo "To apply changes, either:"
echo "  1. Unplug and replug your GPS module, OR"
echo "  2. Reboot your system"
echo ""
echo "After reconnecting, verify with:"
echo "  ls -l /dev/gps*"
echo ""
echo "=========================================="
