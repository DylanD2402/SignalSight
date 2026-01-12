# SignalSight GPS Traffic Light Detection System
## Complete Setup Guide for Raspberry Pi 5

This guide walks you through setting up the GPS-based traffic light proximity detection system on a fresh Raspberry Pi 5, from OS installation to running the complete system.

---

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Fresh Raspberry Pi 5 Setup](#fresh-raspberry-pi-5-setup)
3. [System Dependencies Installation](#system-dependencies-installation)
4. [GPS Hardware Setup](#gps-hardware-setup)
5. [Python Environment Setup](#python-environment-setup)
6. [Traffic Light Database Creation](#traffic-light-database-creation)
7. [Running the System](#running-the-system)
8. [System Startup Procedures](#system-startup-procedures)
9. [Testing & Validation](#testing--validation)
10. [Troubleshooting](#troubleshooting)

---

## Hardware Requirements

### Required Components
- **Raspberry Pi 5** (4GB or 8GB RAM recommended)
- **MicroSD Card** (32GB minimum, Class 10 or better)
- **u-blox NEO-M8N GPS Module** (USB interface)
- **Arduino Uno R3** (for driver alerts, optional)
- **Power Supply** (Official Raspberry Pi 5 power supply, 5V/5A)
- **USB Cable** for GPS module
- **Internet Connection** (for initial setup and database download)

### Optional Components
- Case for Raspberry Pi 5
- Cooling fan/heatsink
- External GPS antenna (for better signal)

---

## Fresh Raspberry Pi 5 Setup

### Step 1: Install Raspberry Pi OS

1. **Download Raspberry Pi Imager** on your computer:
   - Visit: https://www.raspberrypi.com/software/
   - Install for Windows, macOS, or Linux

2. **Flash the OS to SD Card:**
   ```
   - Insert SD card into your computer
   - Open Raspberry Pi Imager
   - Choose Device: Raspberry Pi 5
   - Choose OS: Raspberry Pi OS (64-bit) - Recommended
   - Choose Storage: Your SD card
   - Click "Next"
   ```

3. **Configure OS Settings (Important!):**
   ```
   When prompted "Would you like to apply OS customization settings?", select YES

   Configure:
   - Hostname: signalsight (or your preference)
   - Username: your_username
   - Password: your_password
   - WiFi: Enter your network SSID and password
   - Locale: Set timezone and keyboard layout
   - Enable SSH: Check this box for remote access

   Click "Save" then "Yes" to apply settings
   ```

4. **Write the Image:**
   - Click "Yes" to proceed (this will erase the SD card)
   - Wait for writing and verification (5-10 minutes)

5. **Boot the Raspberry Pi:**
   - Insert SD card into Raspberry Pi 5
   - Connect power supply
   - Wait 1-2 minutes for first boot
   - Connect via SSH or directly with monitor/keyboard

### Step 2: First Boot Configuration

**If connecting via SSH:**
```bash
# From your computer
ssh your_username@signalsight.local
# Or use the IP address if .local doesn't work
ssh your_username@192.168.1.xxx
```

**Update the system:**
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get dist-upgrade -y
```

**Reboot after updates:**
```bash
sudo reboot
```

---

## System Dependencies Installation

### Step 1: Install Required System Packages

```bash
# Install GPS daemon and tools (for testing/demo only)
sudo apt-get install -y gpsd gpsd-clients python3-gps

# Install Python development headers
sudo apt-get install -y python3-pip python3-dev python3-venv

# Install build tools (needed for some Python packages)
sudo apt-get install -y build-essential git

# Install serial communication tools
sudo apt-get install -y minicom screen

# Install database tools (optional, for inspection)
sudo apt-get install -y sqlite3
```

### Step 2: Add User to Required Groups

```bash
# Add your user to dialout group (for serial port access)
sudo usermod -a -G dialout $USER

# Add to gpio group (if needed for hardware integration)
sudo usermod -a -G gpio $USER

# Log out and back in for group changes to take effect
# Or reboot
sudo reboot
```

---

## GPS Hardware Setup

### Step 1: Connect GPS Module

1. **Physical Connection:**
   - Plug u-blox NEO-M8N GPS module into any USB port
   - Wait 5 seconds for device recognition

2. **Verify GPS Detected:**
   ```bash
   # Check if GPS appears as USB serial device
   ls -l /dev/ttyUSB*
   ```

   **Expected output:**
   ```
   crw-rw---- 1 root dialout 188, 0 Dec 28 10:00 /dev/ttyUSB0
   ```

   If you see this, GPS is connected! Note which number (0, 1, etc.)

### Step 2: Setup Persistent Device Naming

**Why this is important:** USB device numbers (ttyUSB0, ttyUSB1) can change between reboots. We create a persistent `/dev/gps0` name that always points to the GPS module.

**Automated setup:**
```bash
cd /home/your_username/SignalSight/GPS/demo
chmod +x setup_gps_device.sh
./setup_gps_device.sh
```

**Replug GPS Module:**
- Unplug the GPS USB cable
- Wait 2 seconds
- Plug it back in

**Verify persistent device:**
```bash
ls -l /dev/gps*
```

**Expected output:**
```
lrwxrwxrwx 1 root root 7 Dec 28 10:01 /dev/gps0 -> ttyUSB0
```

### Step 3: Test GPS Hardware (Optional)

**Test raw NMEA data:**
```bash
# Read raw GPS sentences
cat /dev/gps0
```

You should see NMEA sentences like:
```
$GNGGA,123456.00,4527.1234,N,07545.6789,W,1,08,1.2,100.0,M,40.0,M,,*5C
$GNRMC,123456.00,A,4527.1234,N,07545.6789,W,0.0,0.0,281224,,,A*7E
```

Press `Ctrl+C` to stop.

**If you see garbage characters:** GPS baudrate might be different. The default is 9600 for NEO-M8N.

---

## Python Environment Setup

### Step 1: Clone Repository

```bash
# Navigate to home directory
cd ~

# Clone SignalSight repository
git clone https://github.com/yourusername/SignalSight.git
cd SignalSight/GPS
```

**If repository already exists:**
```bash
cd ~/SignalSight
git pull origin main
cd GPS
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Your prompt should now show (venv)
```

**To activate in future sessions:**
```bash
cd ~/SignalSight/GPS
source venv/bin/activate
```

### Step 3: Install Python Dependencies

```bash
# Make sure virtual environment is activated
# Install all required packages
pip install --upgrade pip
pip install -r requirements.txt
```

**Verify installation:**
```bash
pip list | grep -E "(pynmea2|pyserial|osmium|requests)"
```

**Expected output:**
```
osmium              3.7.0
pynmea2             1.19.0
pyserial            3.5
requests            2.31.0
```

---

## Traffic Light Database Creation

### Step 1: Understand the Database

The system uses a local SQLite database containing traffic light locations extracted from OpenStreetMap data. This enables offline operation and sub-5ms query times.

**Database specifications:**
- Format: SQLite3
- Size: ~1.9 MB (Ontario), ~100 MB (all Canada)
- Contains: ~50,000 traffic lights (Ontario)
- Query speed: < 5ms average on RPi5

### Step 2: Create the Database

**For Ontario (recommended for testing):**
```bash
cd ~/SignalSight/GPS

# Ensure virtual environment is activated
source venv/bin/activate

# Run database setup (takes 15-30 minutes)
python database_setup.py --region ontario
```

**What happens during setup:**
1. Downloads Ontario OSM data (~5.4 MB) - 10-20 minutes
2. Extracts traffic signals - 5-10 minutes
3. Creates optimized SQLite database - 1-2 minutes
4. Builds spatial indexes - 1 minute
5. Validates performance - 30 seconds
6. Cleans up temporary files

**For other regions:**
```bash
# Quebec
python database_setup.py --region quebec

# British Columbia
python database_setup.py --region british-columbia

# Alberta
python database_setup.py --region alberta

# All of Canada (Warning: Large download ~500MB, long processing time)
python database_setup.py --region canada
```

### Step 3: Verify Database Creation

```bash
# Check database file exists
ls -lh data/traffic_lights.db
```

**Expected output:**
```
-rw-r--r-- 1 your_username your_username 1.9M Dec 28 13:40 data/traffic_lights.db
```

**Inspect database (optional):**
```bash
sqlite3 data/traffic_lights.db

# Inside sqlite3:
SELECT COUNT(*) FROM traffic_lights;  -- Should show ~50,000+
SELECT * FROM traffic_lights LIMIT 5;
.exit
```

---

## Running the System

### Option 1: Run GPS Demo (Visual Testing)

**Simple demo to verify GPS is working:**
```bash
cd ~/SignalSight/GPS/demo
python demo.py
```

**What you'll see:**
- Real-time GPS position (latitude/longitude)
- Altitude, speed, heading
- Satellite count
- GPS time

**Tips:**
- Move GPS near window or outdoors for best signal
- Wait 30-60 seconds for initial GPS fix
- Press `Ctrl+C` to exit

### Option 2: Run Simulation Mode (No Hardware Required)

**Test the system without GPS hardware:**
```bash
cd ~/SignalSight/GPS
source venv/bin/activate
python example_integration.py --simulate
```

**What happens:**
- Simulates driving through Ottawa/Barrhaven
- Shows proximity to traffic lights
- Demonstrates alert zones (far/approaching/near/imminent)
- Displays distance updates in real-time

### Option 3: Run Full Traffic Light Detection System

**With GPS hardware connected:**
```bash
cd ~/SignalSight/GPS
source venv/bin/activate

# Run with GPS only (no Arduino)
python example_integration.py --gps-port /dev/gps0

# Run with GPS and Arduino
python example_integration.py --gps-port /dev/gps0 --arduino-port /dev/ttyACM0
```

**What the system does:**
1. Opens GPS serial connection (`/dev/gps0`)
2. Loads traffic light database
3. Starts GPS reader thread (parses NMEA sentences)
4. Starts query thread (checks nearby lights at 2Hz)
5. Displays real-time status:
   - Current GPS position
   - Speed (km/h)
   - Distance to nearest traffic light
   - Alert zone (far/approaching/near/imminent)
   - Satellite count

**Alert Zones:**
- **Far (250-500m):** Monitoring only
- **Approaching (100-250m):** Traffic light ahead
- **Near (50-100m):** Prepare to stop
- **Imminent (0-50m):** Check light NOW

**Press `Ctrl+C` to stop the system.**

### Option 4: Integration with Main SignalSight System

**To integrate with YOLOv8 computer vision:**

```python
# In your main SignalSight application
from gps_system import GPSTrafficLightSystem

# Initialize GPS system
gps = GPSTrafficLightSystem(
    gps_port='/dev/gps0',
    db_path='/home/your_username/SignalSight/GPS/data/traffic_lights.db',
    arduino_port='/dev/ttyACM0',  # Optional
    query_interval=0.5,  # 2Hz
    search_radius=500.0  # meters
)

# Set up callbacks
def on_proximity_alert(alert):
    if alert.zone == 'near' or alert.zone == 'imminent':
        # Trigger YOLO detection
        yolo_system.prioritize_traffic_lights()
        print(f"Traffic light {alert.distance_m:.0f}m ahead!")

gps.set_alert_callback(on_proximity_alert)

# Start the system
gps.start()

# Run your main loop
while running:
    # Check if near traffic light
    if gps.is_approaching_light(threshold_m=100):
        # Activate intensive detection
        pass

    time.sleep(0.1)

# Cleanup
gps.stop()
```

---

## System Startup Procedures

### Quick Start Checklist

**Every time you start the system:**

1. **Power on Raspberry Pi 5**
   - Wait 30-60 seconds for boot

2. **Connect GPS module** (if not permanently attached)
   - Plug into USB port
   - Wait 5 seconds for recognition

3. **Connect Arduino** (if using alerts)
   - Plug into USB port

4. **Open terminal/SSH**
   ```bash
   ssh your_username@signalsight.local
   ```

5. **Navigate to GPS directory**
   ```bash
   cd ~/SignalSight/GPS
   ```

6. **Activate Python environment**
   ```bash
   source venv/bin/activate
   ```

7. **Run the system**
   ```bash
   # Choose one:
   python example_integration.py --gps-port /dev/gps0
   # Or simulation mode:
   python example_integration.py --simulate
   ```

### Auto-Start on Boot (Optional)

**Create systemd service for automatic startup:**

1. **Create service file:**
   ```bash
   sudo nano /etc/systemd/system/signalsight-gps.service
   ```

2. **Add the following content:**
   ```ini
   [Unit]
   Description=SignalSight GPS Traffic Light Detection
   After=network.target

   [Service]
   Type=simple
   User=your_username
   WorkingDirectory=/home/your_username/SignalSight/GPS
   ExecStart=/home/your_username/SignalSight/GPS/venv/bin/python example_integration.py --gps-port /dev/gps0
   Restart=on-failure
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable signalsight-gps.service
   sudo systemctl start signalsight-gps.service
   ```

4. **Check status:**
   ```bash
   sudo systemctl status signalsight-gps.service
   ```

5. **View logs:**
   ```bash
   journalctl -u signalsight-gps.service -f
   ```

**To stop auto-start:**
```bash
sudo systemctl stop signalsight-gps.service
sudo systemctl disable signalsight-gps.service
```

---

## Testing & Validation

### Test 1: GPS Hardware Test

```bash
cd ~/SignalSight/GPS/demo
python demo.py
```

**Success criteria:**
- GPS fix obtained within 60 seconds (outdoors)
- Latitude/longitude displayed
- Satellite count shows 4+ satellites
- Position updates every second

### Test 2: Database Query Test

```bash
cd ~/SignalSight/GPS
source venv/bin/activate
python benchmark.py
```

**Success criteria:**
- Average query time < 5ms
- Database contains traffic lights
- No errors during queries

### Test 3: Full System Test

```bash
cd ~/SignalSight/GPS
source venv/bin/activate
python example_integration.py --simulate
```

**Success criteria:**
- Simulation starts successfully
- Displays position updates
- Shows traffic light distances
- Alert zones change appropriately

### Test 4: Robot Framework Test Suite

```bash
cd ~/SignalSight
./run_gps_tests.sh
```

**Success criteria:**
- All unit tests pass (26 tests)
- All integration tests pass (14 tests)
- HTML report generated in `tests/reports/`

---

## Troubleshooting

### Issue: GPS module not detected

**Symptoms:** `ls /dev/ttyUSB*` shows "No such file or directory"

**Solutions:**
1. Check USB cable connection
2. Try different USB port
3. Check if GPS has power LED (should be lit)
4. Run `dmesg | tail -20` to see USB connection logs
5. Try: `lsusb` to see if GPS appears

### Issue: Permission denied on /dev/ttyUSB0

**Symptoms:** `Permission denied` when running GPS scripts

**Solution:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, or reboot
sudo reboot
```

### Issue: GPS shows "Waiting for fix" forever

**Symptoms:** GPS connects but never gets satellite lock

**Solutions:**
1. **Move GPS outdoors** - GPS needs clear sky view
2. **Wait longer** - First fix can take 5-10 minutes
3. **Check antenna** - Ensure GPS antenna is properly connected
4. **Verify GPS is working:**
   ```bash
   cat /dev/gps0
   ```
   Should show NMEA sentences (even without fix)

### Issue: Database download fails

**Symptoms:** `database_setup.py` fails during download

**Solutions:**
1. Check internet connection: `ping google.com`
2. Check available disk space: `df -h`
3. Try again (downloads can timeout)
4. Use existing PBF file if you have one:
   ```bash
   python database_setup.py --pbf-path path/to/file.osm.pbf
   ```

### Issue: Import error for pynmea2 or pyserial

**Symptoms:** `ModuleNotFoundError: No module named 'pynmea2'`

**Solution:**
```bash
# Ensure virtual environment is activated
cd ~/SignalSight/GPS
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Arduino not detected

**Symptoms:** Arduino port `/dev/ttyACM0` not found

**Solutions:**
1. Check Arduino USB connection
2. Find actual port:
   ```bash
   ls -l /dev/ttyACM*
   ls -l /dev/ttyUSB*
   ```
3. Use correct port in command:
   ```bash
   python example_integration.py --gps-port /dev/gps0 --arduino-port /dev/ttyACM1
   ```

### Issue: Slow query performance (>5ms)

**Symptoms:** Benchmark shows average query time > 5ms

**Solutions:**
1. **Check SD card speed** - Use Class 10 or better
2. **Reduce database size** - Use smaller region (Ontario vs Canada)
3. **Check system load:**
   ```bash
   top
   # Press 'q' to exit
   ```
4. **Optimize database:**
   ```bash
   sqlite3 data/traffic_lights.db
   ANALYZE;
   VACUUM;
   .exit
   ```

### Issue: System crashes or freezes

**Symptoms:** Python script stops responding

**Solutions:**
1. **Check power supply** - Raspberry Pi 5 needs 5V/5A
2. **Check temperature:**
   ```bash
   vcgencmd measure_temp
   ```
   Should be < 80°C. Add cooling if needed.
3. **Check memory:**
   ```bash
   free -h
   ```
4. **Check system logs:**
   ```bash
   journalctl -xe
   ```

### Issue: /dev/gps0 not created after setup

**Symptoms:** Persistent device naming doesn't work

**Solutions:**
1. **Check udev rule installed:**
   ```bash
   ls -l /etc/udev/rules.d/99-gps.rules
   ```

2. **Reinstall udev rule:**
   ```bash
   cd ~/SignalSight/GPS/demo
   sudo cp 99-gps.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

3. **Replug GPS module**

4. **Check rule matches your GPS:**
   ```bash
   # Find GPS vendor/product ID
   lsusb

   # Check rule content
   cat /etc/udev/rules.d/99-gps.rules
   ```

### Getting Help

**Check logs:**
```bash
# System logs
journalctl -xe

# GPS service logs (if using systemd)
journalctl -u signalsight-gps.service -f

# USB device logs
dmesg | grep -i usb
```

**Gather system information:**
```bash
# OS version
cat /etc/os-release

# Kernel version
uname -a

# Raspberry Pi model
cat /proc/cpuinfo | grep Model

# Python version
python --version

# Installed packages
pip list
```

---

## Performance Specifications

### Target Performance (Raspberry Pi 5)

| Metric | Target | Typical |
|--------|--------|---------|
| Query Latency | < 5ms | 2-3ms |
| Memory Usage | < 20MB | ~15MB |
| CPU Usage | < 1% per query | ~0.5% |
| Query Rate | 10Hz+ | 2Hz default |
| Database Size | < 100MB | 1.9MB (Ontario) |
| GPS Fix Time | < 60s | 30-45s outdoors |

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 2GB | 4GB+ |
| Storage | 8GB | 32GB+ |
| SD Card Speed | Class 10 | UHS-I/UHS-II |
| Power Supply | 5V/3A | 5V/5A (official) |
| GPS Antenna | Internal | External (better signal) |

---

## Quick Reference Commands

```bash
# System startup
cd ~/SignalSight/GPS
source venv/bin/activate
python example_integration.py --gps-port /dev/gps0

# Simulation mode (no hardware)
python example_integration.py --simulate

# GPS demo (from demo directory)
cd demo && python demo.py

# Database creation
python database_setup.py --region ontario

# Performance benchmark
python benchmark.py

# Check GPS device
ls -l /dev/gps* /dev/ttyUSB*

# Test raw GPS data
cat /dev/gps0

# Check system status
sudo systemctl status signalsight-gps.service

# View logs
journalctl -u signalsight-gps.service -f
```

---

## Next Steps

1. **Integrate with YOLOv8** - Connect GPS alerts to computer vision system
2. **Optimize alert thresholds** - Tune distance zones for your use case
3. **Add data logging** - Record GPS tracks and alert history
4. **Expand database** - Add more regions or all of Canada
5. **Implement route learning** - Predict upcoming traffic lights based on route history

---

## Additional Resources

- **OpenStreetMap**: https://www.openstreetmap.org/
- **Geofabrik Downloads**: https://download.geofabrik.de/
- **u-blox NEO-M8N Datasheet**: Search for "NEO-M8N datasheet"
- **NMEA Protocol**: https://www.nmea.org/
- **Raspberry Pi Documentation**: https://www.raspberrypi.com/documentation/

---

## License

This project is part of SignalSight. See main repository for license information.

## Support

For issues and questions:
- Check this guide's [Troubleshooting](#troubleshooting) section
- Review GPS module README.md
- Check system logs with `journalctl`
- Verify hardware connections

---

**Document Version:** 1.0
**Last Updated:** 2025-12-28
**Compatible with:** Raspberry Pi 5, Raspberry Pi OS (64-bit)
