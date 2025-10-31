#!/bin/bash
# Complete GPS setup - runs both udev rule and GPSD config setup

echo "=========================================="
echo "Complete GPS Setup for SignalSight"
echo "=========================================="
echo ""
echo "This script will:"
echo "  1. Install udev rule for persistent GPS naming (/dev/gps0)"
echo "  2. Update GPSD configuration to use /dev/gps0"
echo "  3. Restart GPSD service"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi
echo ""

# Step 1: Setup udev rule
echo "=========================================="
echo "STEP 1: Installing udev rule"
echo "=========================================="
./setup_gps_device.sh
if [ $? -ne 0 ]; then
    echo "Error in step 1. Exiting."
    exit 1
fi
echo ""

# Prompt to replug device
echo "=========================================="
echo "IMPORTANT: Replug GPS Module"
echo "=========================================="
echo "Please unplug and replug your GPS module now"
echo "to activate the udev rule."
echo ""
read -p "Press Enter when you've replugged the GPS module..."
echo ""

# Verify /dev/gps0 exists
if [ -e /dev/gps0 ]; then
    echo "/dev/gps0 detected!"
    ls -l /dev/gps0
    echo ""
else
    echo "Warning: /dev/gps0 not found"
    echo "The udev rule may not be active yet."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Update GPSD config
echo "=========================================="
echo "STEP 2: Updating GPSD configuration"
echo "=========================================="
./update_gpsd_config.sh
if [ $? -ne 0 ]; then
    echo "Error in step 2. Exiting."
    exit 1
fi

echo ""
echo "=========================================="
echo "Complete GPS Setup Finished!"
echo "=========================================="
echo ""
echo "Your GPS module is now configured with:"
echo "  - Persistent device name: /dev/gps0"
echo "  - GPSD configured to use /dev/gps0"
echo ""
echo "You can now run the GPS demo:"
echo "  python3 demo.py"
echo ""
echo "=========================================="
