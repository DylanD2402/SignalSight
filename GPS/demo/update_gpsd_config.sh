#!/bin/bash
# Update GPSD configuration to use persistent GPS device name

echo "=========================================="
echo "GPSD Configuration Update"
echo "=========================================="
echo ""

# Check if udev rule is installed
if [ ! -f /etc/udev/rules.d/99-gps.rules ]; then
    echo "Warning: udev rule not found!"
    echo "Please run ./setup_gps_device.sh first to create /dev/gps0"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if /dev/gps0 exists
if [ ! -e /dev/gps0 ]; then
    echo "Warning: /dev/gps0 does not exist!"
    echo "You may need to:"
    echo "  1. Run ./setup_gps_device.sh first"
    echo "  2. Unplug and replug your GPS module"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Current GPSD configuration:"
echo "----------------------------"
cat /etc/default/gpsd
echo "----------------------------"
echo ""

echo "Backing up current config..."
sudo cp /etc/default/gpsd /etc/default/gpsd.backup
echo "Backup saved to /etc/default/gpsd.backup"
echo ""

echo "Updating GPSD configuration..."
sudo tee /etc/default/gpsd > /dev/null << 'EOF'
# Devices gpsd should collect to at boot time.
# They need to be read/writeable, either by user gpsd or the group dialout.
DEVICES="/dev/gps0"

# Other options you want to pass to gpsd
GPSD_OPTIONS="-n"

# Automatically hot add/remove USB GPS devices via gpsdctl
USBAUTO="true"
EOF

echo "Configuration updated!"
echo ""

echo "New GPSD configuration:"
echo "----------------------------"
cat /etc/default/gpsd
echo "----------------------------"
echo ""

echo "Stopping GPSD service..."
sudo systemctl stop gpsd.socket
sudo systemctl stop gpsd

echo "Starting GPSD service..."
sudo systemctl start gpsd

echo ""
echo "GPSD restarted with new configuration!"
echo ""

# Check status
echo "GPSD Status:"
sudo systemctl status gpsd --no-pager | head -15
echo ""

echo "=========================================="
echo "Configuration update complete!"
echo ""
echo "Your GPS is now configured to use /dev/gps0"
echo "This will work regardless of which ttyUSBx"
echo "number gets assigned to your GPS module."
echo "=========================================="
