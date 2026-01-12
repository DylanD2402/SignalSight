# GPS Traffic Light Detection System

Production GPS system for SignalSight using direct serial communication and local traffic light database for real-time proximity detection.

**Performance:** <5ms query latency | 2Hz updates | <20MB memory | Offline operation

---

## System Overview

The GPS module provides predictive traffic light awareness by:
- Detecting approaching traffic lights up to 500m ahead
- Triggering YOLOv8 computer vision when near intersections
- Sending distance-based alerts to Arduino for driver warnings
- Operating entirely offline with local database

**Distance Zones:**
- **Imminent (0-50m):** Check light NOW - High-priority alerts
- **Near (50-100m):** Prepare to stop - Activate YOLO detection
- **Approaching (100-250m):** Traffic light ahead - Pre-load models
- **Far (250-500m):** Monitoring only - Route analysis

---

## Quick Start

### Prerequisites

1. **Raspberry Pi 5** running Raspberry Pi OS (64-bit)
2. **u-blox NEO-M8N GPS module** connected via USB
3. **Python 3.11+**
4. **Internet connection** (for initial database download only)

### Installation

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential

# Add user to dialout group for serial access
sudo usermod -a -G dialout $USER
# Log out and back in for group changes to take effect

# Create virtual environment
cd ~/SignalSight/GPS
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Create Traffic Light Database

Download and build the local traffic light database from OpenStreetMap:

```bash
# For Ontario (recommended, ~1.9MB, 50,000+ lights)
python database_setup.py --region ontario

# Takes 15-30 minutes on first run:
# - Downloads OSM data (~5.4MB)
# - Extracts traffic signals
# - Creates optimized SQLite database
# - Validates performance (<5ms queries)
```

**Other regions:** `quebec`, `british-columbia`, `alberta`, `canada`

### Run the System

**With real GPS hardware:**
```bash
source venv/bin/activate
python example_integration.py --gps-port /dev/ttyUSB0
```

**Simulation mode (no hardware needed):**
```bash
python example_integration.py --simulate
```

**With Arduino for driver alerts:**
```bash
python example_integration.py --gps-port /dev/ttyUSB0 --arduino-port /dev/ttyACM0
```

---

## Core Components

### `gps_system.py` - GPS Integration System
- Direct serial communication with GPS module (no GPSD dependency)
- Multi-threaded architecture (GPS reader + database query threads)
- Real-time NMEA sentence parsing
- 2Hz database queries (configurable up to 200Hz)
- Arduino serial communication for alerts

### `traffic_light_db.py` - Database Query Engine
- Optimized SQLite spatial queries
- Haversine distance calculations
- Bounding box pre-filtering
- <5ms average query time on RPi5

### `database_setup.py` - Database Builder
- Downloads OpenStreetMap data from Geofabrik
- Extracts traffic signals using osmium library
- Creates indexed SQLite database
- Validates performance benchmarks

### `example_integration.py` - Complete Integration
- Full pipeline demonstration
- Callback-based alert system
- Simulation mode for testing
- Integration template for YOLO system

### `benchmark.py` - Performance Testing
- Query latency benchmarks
- Memory usage monitoring
- Throughput testing
- Performance validation

---

## Integration with SignalSight

### Basic Integration

```python
from gps_system import GPSTrafficLightSystem, ProximityAlert

# Initialize GPS system
gps = GPSTrafficLightSystem(
    gps_port='/dev/ttyUSB0',
    db_path='data/traffic_lights.db',
    arduino_port='/dev/ttyACM0',  # Optional
    query_interval=0.5,  # 2Hz
    search_radius=500.0  # meters
)

# Set up proximity alert callback
def on_alert(alert: ProximityAlert):
    if alert.zone in ['near', 'imminent']:
        # Trigger YOLO detection
        print(f"Traffic light {alert.distance_m:.0f}m ahead - Zone: {alert.zone}")
        yolo_system.prioritize_traffic_lights()

gps.set_alert_callback(on_alert)

# Start the system
gps.start()

# Main application loop
try:
    while running:
        # Check if near traffic light
        if gps.is_approaching_light(threshold_m=100):
            # Activate intensive detection
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

# Get system statistics
stats = gps.get_stats()
# Returns: dict with query_count, avg_query_ms, nearby_lights, etc.
```

---

## Database Management

### Database Location

Default: `/home/your_username/SignalSight/GPS/data/traffic_lights.db`

### Creating Database for Different Regions

```bash
# Ontario (default)
python database_setup.py --region ontario

# Multiple regions available
python database_setup.py --region quebec
python database_setup.py --region british-columbia
python database_setup.py --region alberta

# All of Canada (large download ~500MB, long processing)
python database_setup.py --region canada

# Custom output location
python database_setup.py --region ontario --output /custom/path/db.sqlite

# Keep source data after processing
python database_setup.py --region ontario --keep-pbf

# Use existing OSM file
python database_setup.py --pbf-path data/ontario-latest.osm.pbf
```

### Database Inspection

```bash
# Check database size and stats
ls -lh data/traffic_lights.db

# Query database directly
sqlite3 data/traffic_lights.db

# Inside sqlite3:
SELECT COUNT(*) FROM traffic_lights;
SELECT * FROM traffic_lights LIMIT 5;
.schema traffic_lights
.exit
```

### Database Optimization

The database is automatically optimized during creation with:
- **Spatial indexes** on lat/lon for fast bounding box queries
- **WAL mode** for concurrent read access
- **Memory-mapped I/O** (64MB) for faster access
- **Analyzed statistics** for query optimizer

---

## Performance Tuning

### Query Rate Configuration

```python
# Default: 2Hz (0.5s interval) - Balanced performance
gps = GPSTrafficLightSystem(query_interval=0.5)

# High frequency: 10Hz (0.1s interval) - More responsive
gps = GPSTrafficLightSystem(query_interval=0.1)

# Low frequency: 1Hz (1.0s interval) - Lower CPU usage
gps = GPSTrafficLightSystem(query_interval=1.0)
```

### Search Radius Configuration

```python
# Default: 500m - Long-range detection
gps = GPSTrafficLightSystem(search_radius=500.0)

# Short range: 250m - Faster queries
gps = GPSTrafficLightSystem(search_radius=250.0)

# Extended range: 1000m - Early detection
gps = GPSTrafficLightSystem(search_radius=1000.0)
```

### Performance Benchmarking

```bash
# Run benchmark suite
python benchmark.py

# Expected results on RPi5:
# - Average query time: 2-3ms
# - Queries per second: 200+ Hz capable
# - Memory usage: ~15MB
# - CPU usage: <1% per query
```

---

## GPS Hardware Setup

### Connect GPS Module

1. Plug u-blox NEO-M8N GPS module into USB port
2. Verify detection:
   ```bash
   ls -l /dev/ttyUSB*
   ```
   Should show `/dev/ttyUSB0` or similar

### Test GPS Connection

```bash
# View raw NMEA data
cat /dev/ttyUSB0

# Should show sentences like:
# $GNGGA,123456.00,4527.1234,N,07545.6789,W,1,08,1.2,100.0,M,40.0,M,,*5C
# $GNRMC,123456.00,A,4527.1234,N,07545.6789,W,0.0,0.0,281224,,,A*7E

# Press Ctrl+C to stop
```

### Tips for GPS Signal

- **Outdoor use:** GPS requires clear sky view for best performance
- **Window placement:** If indoors, place GPS near window
- **Initial fix:** First satellite lock takes 30-60 seconds
- **Satellites needed:** Minimum 4 satellites for 3D fix (lat/lon/alt)
- **Obstructions:** Avoid metal surfaces and electromagnetic interference

---

## Auto-Start on Boot (Optional)

Create systemd service for automatic startup:

```bash
# Create service file
sudo nano /etc/systemd/system/signalsight-gps.service
```

Add:
```ini
[Unit]
Description=SignalSight GPS Traffic Light Detection
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/SignalSight/GPS
ExecStart=/home/your_username/SignalSight/GPS/venv/bin/python example_integration.py --gps-port /dev/ttyUSB0
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable signalsight-gps.service
sudo systemctl start signalsight-gps.service

# Check status
sudo systemctl status signalsight-gps.service

# View logs
journalctl -u signalsight-gps.service -f
```

---

## Testing

### Run Performance Benchmark

```bash
python benchmark.py
```

Validates:
- Query latency (<5ms target)
- Throughput (10Hz+ capable)
- Memory usage (<20MB target)
- Database integrity

### Run Integration Test

```bash
# Simulation mode (no hardware needed)
python example_integration.py --simulate

# Real GPS test
python example_integration.py --gps-port /dev/ttyUSB0
```

### Robot Framework Tests

```bash
# From SignalSight root directory
./run_gps_tests.sh

# Runs 40 comprehensive tests:
# - 26 unit tests (NMEA parsing, data structures, etc.)
# - 14 integration tests (system integration, performance)
```

---

## Troubleshooting

### GPS Module Not Detected

```bash
# Check USB devices
lsusb
dmesg | grep -i usb

# Check serial ports
ls -l /dev/ttyUSB* /dev/ttyACM*

# Verify user has serial access
groups | grep dialout
```

### Permission Denied on Serial Port

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, or reboot
sudo reboot
```

### Slow Query Performance

```bash
# Check SD card speed (should be Class 10+)
# Run benchmark to identify issue
python benchmark.py

# Optimize database
sqlite3 data/traffic_lights.db "VACUUM; ANALYZE;"

# Use smaller database region
python database_setup.py --region ontario  # Instead of canada
```

### Database Download Fails

```bash
# Check internet connection
ping google.com

# Check disk space
df -h

# Retry download (may timeout occasionally)
python database_setup.py --region ontario

# Use existing PBF file if you have one
python database_setup.py --pbf-path path/to/file.osm.pbf
```

### Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "(pynmea2|pyserial|osmium)"
```

---

## File Structure

```
GPS/
├── README.md                    # This file - Production system guide
├── requirements.txt             # Python dependencies
├── gps_system.py               # Main GPS integration system
├── traffic_light_db.py         # Database query engine
├── database_setup.py           # Database creation tool
├── example_integration.py      # Integration example/template
├── benchmark.py                # Performance testing suite
├── data/                       # Database storage
│   ├── traffic_lights.db      # Traffic light database
│   └── *.osm.pbf              # Source OSM data (cleaned up after build)
└── demo/                       # GPSD demos (see demo/README.md)
    ├── demo.py                # Live GPS visualization
    ├── address_demo.py        # Reverse geocoding demo
    └── *.sh                   # GPSD setup scripts
```

---

## Performance Specifications

| Metric | Target | Typical (RPi5) |
|--------|--------|----------------|
| Query Latency | <5ms | 2-3ms |
| Query Rate | 10Hz+ | 200Hz capable |
| Memory Usage | <20MB | ~15MB |
| CPU Usage | <1% per query | ~0.5% |
| Database Size | <100MB | 1.9MB (Ontario) |
| GPS Fix Time | <60s outdoor | 30-45s |

---

## Development

### Adding Custom Functionality

```python
# Custom position callback
def my_position_handler(position):
    print(f"New position: {position.latitude}, {position.longitude}")

gps.set_position_callback(my_position_handler)

# Custom alert callback
def my_alert_handler(alert):
    if alert.zone == 'imminent':
        # Custom logic
        pass

gps.set_alert_callback(my_alert_handler)
```

### Extending Database Queries

```python
from traffic_light_db import TrafficLightDB

db = TrafficLightDB('data/traffic_lights.db')

# Custom radius search
lights = db.get_nearby_lights_fast(lat, lon, radius=1000)

# Get all lights in bounding box
lights = db.get_lights_in_bounds(min_lat, max_lat, min_lon, max_lon)

# Database statistics
stats = db.get_stats()
```

---

## Additional Resources

- **Demo/Visualization Tools:** See `demo/README.md` for GPSD-based demos
- **Complete Setup Guide:** See `SETUP_GUIDE.md` for fresh RPi5 installation
- **OpenStreetMap Data:** https://download.geofabrik.de/
- **GPS Module Specs:** Search "u-blox NEO-M8N datasheet"
- **NMEA Protocol:** https://www.nmea.org/

---

## Quick Reference Commands

```bash
# First-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python database_setup.py --region ontario

# Run production system
source venv/bin/activate
python example_integration.py --gps-port /dev/ttyUSB0

# Run simulation (no hardware)
python example_integration.py --simulate

# Run benchmark
python benchmark.py

# Check GPS device
ls -l /dev/ttyUSB*

# Test GPS data
cat /dev/ttyUSB0

# View system logs
journalctl -u signalsight-gps.service -f
```

---

**Version:** 2.0 - Production System
**Last Updated:** 2025-12-28
**Compatible with:** Raspberry Pi 5, Raspberry Pi OS (64-bit), Python 3.11+
