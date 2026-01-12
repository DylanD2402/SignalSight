# GPS Demo & Visualization Tools

This directory contains demonstration and visualization tools for the GPS module using GPSD daemon.

**Note:** These are demo/testing tools only. For the production traffic light detection system, see the main GPS directory.

---

## What's in This Directory

- **`demo.py`** - Live GPS data visualization (great for presentations)
- **`address_demo.py`** - Reverse geocoding demo (GPS coordinates to street address)
- **`setup_gps_complete.sh`** - Automated GPSD setup script
- **`setup_gps_device.sh`** - Install udev rule for persistent GPS naming
- **`update_gpsd_config.sh`** - Configure GPSD daemon
- **`99-gps.rules`** - udev rule for `/dev/gps0` persistent device

---

## Quick Start

### Prerequisites

GPS module must be connected via USB.

### Automated Setup (Recommended)

Run the complete setup script:

```bash
cd demo
./setup_gps_complete.sh
```

This will:
1. Install udev rule for persistent GPS naming (`/dev/gps0`)
2. Prompt you to replug your GPS module
3. Configure GPSD to use `/dev/gps0`
4. Restart GPSD service

### Run the GPS Demo

```bash
python3 demo.py
```

**What you'll see:**
- Real-time GPS position (latitude/longitude)
- Altitude (meters and feet)
- Speed (km/h and mph)
- Heading direction
- Satellite count
- GPS time

**Press Ctrl+C to exit.**

---

## Manual Setup

If you prefer step-by-step setup:

### 1. Verify GPS Module Connected

```bash
ls -l /dev/ttyUSB*
```

You should see `/dev/ttyUSB0` or similar.

### 2. Install GPSD

```bash
sudo apt-get update
sudo apt-get install -y gpsd gpsd-clients python3-gps
```

### 3. Setup Persistent Device Name

```bash
./setup_gps_device.sh
```

Then unplug and replug your GPS module.

Verify:
```bash
ls -l /dev/gps0
# Should show: /dev/gps0 -> ttyUSB0
```

### 4. Configure GPSD

```bash
./update_gpsd_config.sh
```

Or manually edit:
```bash
sudo nano /etc/default/gpsd
```

Set:
```
DEVICES="/dev/gps0"
GPSD_OPTIONS="-n"
USBAUTO="true"
```

### 5. Start GPSD Service

```bash
sudo systemctl enable gpsd
sudo systemctl start gpsd
```

Verify:
```bash
sudo systemctl status gpsd
```

---

## Running the Demos

### Live GPS Display

```bash
python3 demo.py
```

- Displays live GPS data in a clean format
- Updates every second
- Great for presentations and testing

### Address Demo (Reverse Geocoding)

```bash
python3 address_demo.py
```

- Shows GPS coordinates
- Converts to street address (requires internet)
- Displays location information

---

## Testing GPS

### Check GPSD is Receiving Data

```bash
cgps
```

Press Ctrl+C to exit.

### View Raw NMEA Data

```bash
cat /dev/gps0
```

You should see NMEA sentences like:
```
$GNGGA,123456.00,4527.1234,N,07545.6789,W,1,08,1.2,100.0,M,40.0,M,,*5C
```

Press Ctrl+C to stop.

---

## Tips for Best Results

- **Location:** GPS works best outdoors with clear sky view
- **Window placement:** If indoors, place GPS near a window
- **Wait time:** Initial GPS fix can take 30-60 seconds
- **Satellites:** Need at least 4 satellites for a 3D fix
- **Movement:** Speed/heading data only appears when moving

---

## Troubleshooting

### GPS not connecting?

Check GPSD status:
```bash
sudo systemctl status gpsd
```

Restart if needed:
```bash
sudo systemctl restart gpsd
```

### GPS device not found?

Verify device:
```bash
ls -l /dev/ttyUSB* /dev/gps*
```

### Shows "Waiting for GPS fix" forever?

1. Move GPS near window or outdoors
2. Wait 1-2 minutes for initial fix
3. Check satellite visibility with `cgps`

### Permission denied errors?

Add user to dialout group:
```bash
sudo usermod -a -G dialout $USER
```

Log out and back in.

---

## Difference from Main Implementation

**This demo uses GPSD:**
- Runs as system daemon
- Provides GPS data to multiple applications
- Good for testing and visualization
- Higher latency (~50-100ms)

**Main implementation uses direct serial:**
- No daemon dependency
- Lower latency (<5ms)
- Optimized for production use
- See main GPS directory for traffic light detection

---

## Quick Reference

```bash
# Run automated setup
./setup_gps_complete.sh

# Run GPS demo
python3 demo.py

# Run address demo
python3 address_demo.py

# Check GPSD status
sudo systemctl status gpsd

# View live GPS data
cgps

# Check GPS device
ls -l /dev/gps*

# View raw NMEA
cat /dev/gps0
```

---

**For production traffic light detection system, see:** `../README.md`
