# GPS Module

GPS integration for SignalSight using GPSD daemon.

## Files

- `demo.py` - Live GPS data demo (great for presentations!)
- `99-gps.rules` - udev rule for persistent GPS device naming
- `setup_gps_device.sh` - Install udev rule for /dev/gps0
- `update_gpsd_config.sh` - Update GPSD to use /dev/gps0
- `setup_gps_complete.sh` - Complete setup (runs both scripts above)

## Quick Start Guide

Follow these steps after cloning the repository and plugging in your GPS module:

### Automated Setup (Recommended)

The easiest way to set everything up:

```bash
cd GPS/
./setup_gps_complete.sh
```

This script will:
1. Install udev rule for persistent GPS naming (/dev/gps0)
2. Prompt you to replug your GPS module
3. Update GPSD configuration to use /dev/gps0
4. Restart GPSD service

After running this, skip to **Step 7** to run the demo!

---

### Manual Setup (Alternative)

If you prefer to do it step-by-step:

### Step 1: Verify GPS Module Connected

Check that your GPS module is recognized:
```bash
ls -l /dev/ttyUSB*
```

You should see something like `/dev/ttyUSB0` or `/dev/ttyUSB1`. If not, check your USB connection.

### Step 2: Setup Persistent GPS Device Name (Recommended)

**Why this is needed:** Linux assigns USB serial devices (ttyUSB0, ttyUSB1, etc.) based on plug-in order. This means your GPS might show up as ttyUSB0 one time and ttyUSB1 another time, causing configuration issues.

**Solution:** Create a persistent device name that always points to your GPS module.

Run the automated setup script:
```bash
cd GPS/
./setup_gps_device.sh
```

This creates a udev rule that makes your GPS always available at `/dev/gps0`.

After running the script, unplug and replug your GPS module, then verify:
```bash
ls -l /dev/gps*
```

You should see: `/dev/gps0 -> ttyUSBx` (where x is any number)

**Manual installation (if script doesn't work):**
```bash
sudo cp 99-gps.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then unplug and replug the GPS module.

### Step 3: Install GPSD

Install the GPS daemon and client tools:
```bash
sudo apt-get update
sudo apt-get install gpsd gpsd-clients python3-gps
```

### Step 3: Install Python GPS Library

If not already installed with the system package:
```bash
pip3 install gps
```

### Step 4: Configure GPSD

Stop any existing GPSD service and configure it for your GPS device:
```bash
sudo systemctl stop gpsd.socket
sudo systemctl stop gpsd
```

Edit the GPSD configuration:
```bash
sudo nano /etc/default/gpsd
```

Set the following values (use `/dev/gps0` if you completed Step 2):
```
DEVICES="/dev/gps0"
GPSD_OPTIONS="-n"
USBAUTO="true"
```

**Note:** If you skipped Step 2, use `/dev/ttyUSB0` or `/dev/ttyUSB1` (whichever your GPS is using).

Save and exit (Ctrl+X, then Y, then Enter).

### Step 5: Start GPSD Service

Enable and start GPSD:
```bash
sudo systemctl enable gpsd
sudo systemctl start gpsd
```

Verify it's running:
```bash
sudo systemctl status gpsd
```

### Step 6: Navigate to GPS Folder

```bash
cd GPS/
```

### Step 7: Run the GPS Demo

Now you're ready to run the demo! Make sure you're near a window or outdoors for best results:

```bash
python3 demo.py
```

**What to expect:**
- The screen will clear and show "Waiting for GPS fix..."
- This may take 30-60 seconds (or longer indoors)
- Once satellites are locked, you'll see live GPS data updating every second

**The demo displays:**
- Current location (latitude/longitude)
- Altitude (meters and feet)
- Speed (km/h and mph)
- Heading direction
- Satellite count
- GPS time

**Press Ctrl+C to exit the demo.**

Perfect for showing to professors, friends, and project demonstrations!

## Running the Demo (After Initial Setup)

Once setup is complete, you only need to:
```bash
cd GPS/
python3 demo.py
```

## Testing GPS

### Automated Test Suite (Robot Framework)

The GPS module is tested using Robot Framework with comprehensive unit and integration tests.

**Quick test execution:**

From the project root directory:

```bash
# Run all GPS tests (unit + integration)
./run_gps_tests.sh

# Run only GPS unit tests
./run_unit_tests.sh

# Run only GPS integration tests
./run_integration_tests.sh
```

**The test suite validates:**

**Unit Tests (26 test cases):**
- Connection to GPSD daemon
- Data reception and report types
- TPV/SKY report structure
- Satellite data parsing
- Position data validation
- Speed conversion (m/s to km/h)
- Coordinate formatting and validation
- Timeout handling
- GPS mode detection
- Device path verification

**Integration Tests (14 test cases):**
- GPSD service status and availability
- GPSD configuration verification
- GPS device persistence (/dev/gps0)
- Data flow from GPSD to application
- Concurrent connection handling
- GPS fix acquisition
- Satellite data updates
- Position stability over time
- Error recovery and reconnection

**View test reports:**
After running tests, open the HTML reports:
```bash
firefox tests/reports/report.html
```

For detailed test documentation, see `tests/README.md`.

### Manual Interactive Test

Run the interactive manual test:
```bash
python3 address_demo.py
```

This script will:
- Connect to GPSD
- Wait for GPS fix (requires clear sky view)
- Display latitude, longitude, altitude, speed, heading
- Show satellite information in real-time

**Note:** GPS requires outdoor use or window placement for satellite lock.

## Tips for Best Results

- **Location matters:** GPS works best outdoors with clear sky view
- **Window placement:** If indoors, place GPS module near a window
- **Wait time:** Initial GPS fix can take 30-60 seconds or longer
- **Satellite count:** You need at least 4 satellites for a 3D fix (lat/lon/alt)
- **Movement:** Speed and heading data only appear when moving

## Troubleshooting

### GPS not connecting?

Check GPSD status:
```bash
sudo systemctl status gpsd
```

### GPS device not found?

Verify GPS device connected:
```bash
ls -l /dev/ttyUSB*
# or if you setup persistent naming:
ls -l /dev/gps*
```

If you see a different device (like `/dev/ttyUSB1`), update the GPSD config:
```bash
sudo nano /etc/default/gpsd
```

### GPS shows up as ttyUSB1 instead of ttyUSB0?

This is normal Linux behavior. USB serial devices are assigned numbers based on plug-in order.

**Solution:** Use the persistent device naming setup (see Step 2 in Quick Start Guide).

This creates `/dev/gps0` which always points to your GPS module, regardless of which ttyUSBx number it gets assigned.

### Script shows "Waiting for GPS fix..." forever?

1. Check satellite visibility - move outdoors or near window
2. Verify GPSD is receiving data:
```bash
cgps
```
This shows raw GPS data. Press Ctrl+C to exit.

3. Restart GPSD:
```bash
sudo systemctl restart gpsd
```

### Permission denied errors?

Add your user to the dialout group:
```bash
sudo usermod -a -G dialout $USER
```
Then log out and back in.
