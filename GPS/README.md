# GPS Traffic Light Detection System

GPS-based traffic light proximity detection for SignalSight. Uses direct serial communication with u-blox NEO-M8N GPS module and a local SQLite database for real-time offline operation.

## File Structure

```
GPS/
├── gps_system.py       # Main GPS system - run this
├── traffic_light_db.py # Database engine (includes heading filtering)
├── setup.sh            # Automated setup script
├── README.md
├── data/               # Database storage
│   └── traffic_lights.db
├── setup/              # Setup files
│   ├── database_setup.py
│   ├── requirements.txt
│   └── 99-gps.rules
└── demo/               # GPSD-based demos (optional)
```

## Quick Setup (Automated)

Run the setup script to install everything:

```bash
cd ~/SignalSight/GPS
./setup.sh
```

This will:
- Install system dependencies
- Add user to dialout group
- Set up GPS device symlink (`/dev/gps0`)
- Create Python virtual environment
- Install Python dependencies
- Create traffic light database

After setup, log out and back in, then run:

```bash
source venv/bin/activate
python gps_system.py --debug
```

---

## Manual Setup

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential sqlite3

# Add user to dialout group for serial access
sudo usermod -a -G dialout $USER
# Log out and back in for group changes to take effect
```

### 2. Set Up GPS Device Symlink

Create a persistent `/dev/gps0` symlink so the GPS is always at the same path:

```bash
cd ~/SignalSight/GPS

# Install the udev rule
sudo cp setup/99-gps.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Unplug and replug GPS, then verify
ls -l /dev/gps0
```

If your GPS module is different, find its vendor/product ID:
```bash
udevadm info -a -n /dev/ttyUSB0 | grep -E "(idVendor|idProduct)"
```

Then edit `setup/99-gps.rules` to match your device.

### 3. Create Python Environment

```bash
cd ~/SignalSight/GPS
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r setup/requirements.txt
```

### 4. Create Traffic Light Database

```bash
source venv/bin/activate
python setup/database_setup.py --region ontario
```

Available regions: `ontario`, `quebec`, `british-columbia`, `alberta`, `canada`

### 5. Run the System

```bash
source venv/bin/activate
python gps_system.py
```

With debug output:
```bash
python gps_system.py --debug
```

With Arduino for alerts:
```bash
python gps_system.py --arduino-port /dev/ttyACM0
```

---

## Usage

### Command Line Options

```
python gps_system.py [options]

Options:
  --gps-port      GPS serial port (default: /dev/gps0)
  --arduino-port  Arduino serial port for alerts (optional)
  --db            Path to database (default: data/traffic_lights.db)
  --debug         Enable debug output (position, distance, zone)
```

### Debug Mode

Run with `--debug` to see real-time output:

```bash
python gps_system.py --debug
```

Output:
```
GPS Traffic Light System (Debug Mode)
========================================
GPS Port: /dev/gps0
Database: data/traffic_lights.db
Press Ctrl+C to stop

Pos: 45.27123, -75.75678 | Spd: 45km/h | Hdg: 90 | Sats: 8 | Light: 342m [FAR]

Zone changed: APPROACHING (198m)
Zone changed: NEAR (87m)
Zone changed: IMMINENT (23m)
```

The status line updates in place. New lines only appear when the zone changes.

### Integration with Other Code

```python
from gps_system import GPSTrafficLightSystem, ProximityAlert

gps = GPSTrafficLightSystem(
    gps_port='/dev/gps0',
    db_path='data/traffic_lights.db',
    arduino_port='/dev/ttyACM0',  # Optional
    query_interval=0.5,           # 2Hz
    search_radius=500.0           # meters
)

def on_alert(alert: ProximityAlert):
    if alert.zone in ['near', 'imminent']:
        print(f"Traffic light {alert.distance_m:.0f}m ahead")

gps.set_alert_callback(on_alert)
gps.start()

# Your application loop
try:
    while True:
        if gps.is_approaching_light(threshold_m=100):
            # Activate detection
            pass
        time.sleep(0.1)
finally:
    gps.stop()
```

### API Reference

```python
# Get current GPS position
position = gps.get_current_position()
# Returns: GPSPosition(lat, lon, altitude, speed, heading, satellites, fix_quality, timestamp)

# Get nearby traffic lights
lights = gps.get_nearby_lights()
# Returns: List[TrafficLight] sorted by distance

# Get closest traffic light
closest = gps.get_closest_light()
# Returns: TrafficLight or None

# Check if approaching traffic light
approaching = gps.is_approaching_light(threshold_m=100)
# Returns: bool
```

## Distance Zones

| Zone | Distance | Description |
|------|----------|-------------|
| Imminent | 0-50m | Check light NOW |
| Near | 50-100m | Prepare to stop |
| Approaching | 100-250m | Traffic light ahead |
| Far | 250-500m | Monitoring |

## Troubleshooting

### GPS Not Detected
```bash
# Check USB devices
lsusb
ls -l /dev/ttyUSB* /dev/gps*

# Check user has serial access
groups | grep dialout
```

### Permission Denied
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### /dev/gps0 Not Created
```bash
# Reinstall udev rule
sudo cp setup/99-gps.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Unplug and replug GPS module
```

### No GPS Fix
- Move GPS near window or outdoors
- Wait 30-60 seconds for initial fix
- Check antenna connection

### Test Raw GPS Data
```bash
cat /dev/gps0
# Should show NMEA sentences like:
# $GNGGA,123456.00,4527.1234,N,07545.6789,W,1,08,1.2,100.0,M,...
```

## Auto-Start on Boot (Optional)

Create systemd service:

```bash
sudo nano /etc/systemd/system/signalsight-gps.service
```

Add:
```ini
[Unit]
Description=SignalSight GPS
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/SignalSight/GPS
ExecStart=/home/YOUR_USERNAME/SignalSight/GPS/venv/bin/python gps_system.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable signalsight-gps.service
sudo systemctl start signalsight-gps.service
```
