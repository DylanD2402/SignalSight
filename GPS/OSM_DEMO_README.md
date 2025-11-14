# OpenStreetMap Demo - Find Nearest Traffic Lights and Intersections

This demo combines GPS location tracking with the OpenStreetMap Overpass API to find the nearest traffic lights and intersections in real-time.

## Features

- **Live GPS Tracking**: Displays current latitude, longitude, altitude, and speed
- **Traffic Light Detection**: Finds the 3 nearest traffic lights within 500 meters
- **Intersection Detection**: Finds the 3 nearest crossings, intersections, and junctions
- **Distance Calculation**: Shows accurate distance to each feature using the Haversine formula
- **Auto-Refresh**: Queries OpenStreetMap every 5 seconds for updated data
- **Clean Display**: Easy-to-read terminal interface similar to the main GPS demo

## Requirements

### Hardware
- GPS module connected and configured (see main GPS/README.md)
- Internet connection for OpenStreetMap API queries

### Software
```bash
# Python 3 with required packages
sudo apt-get update
sudo apt-get install python3 python3-gps

# Install requests library for API calls
pip3 install requests
```

### GPSD Service
Ensure GPSD is running:
```bash
sudo systemctl status gpsd
# If not running:
sudo systemctl start gpsd
```

## Usage

### Run the Demo
```bash
cd /home/user/SignalSight/GPS
./osm_demo.py
```

Or:
```bash
python3 osm_demo.py
```

### What You'll See

1. **Connection Phase**: Script connects to GPSD daemon
2. **GPS Fix Phase**: Waits for GPS satellite lock (30-60 seconds outdoors)
3. **Live Data Phase**: Shows:
   - Your current GPS coordinates
   - Altitude and speed
   - 3 nearest traffic lights with distances
   - 3 nearest intersections/crossings with distances
   - Query statistics

### Example Output
```
======================================================================
      SignalSight GPS + OpenStreetMap - LIVE DATA
======================================================================

  GPS LOCATION:
    Latitude:      40.748817°
    Longitude:    -73.985428°

  ALTITUDE:
         10.0 meters (32.8 feet)

  SPEED:
    15.0 km/h (9.3 mph)

  NEAREST TRAFFIC LIGHTS (within 500m):
    1.      45.2 m - 5th Avenue
       Type: pedestrian crossing
    2.     123.5 m - Broadway
    3.     234.1 m - W 34th St

  NEAREST INTERSECTIONS/CROSSINGS (within 500m):
    1.      12.3 m - 5th Ave & W 35th St
       Type: Crossing
    2.      89.7 m - Broadway & W 34th St
       Type: Crossing
    3.     156.4 m - 6th Ave & W 35th St
       Type: Crossing

  LAST QUERY:
    Search radius: 500m
    Query time: 1.23s

======================================================================
  Status: GPS FIX ACTIVE | Press Ctrl+C to exit
======================================================================
```

## How It Works

### 1. GPS Data Acquisition
- Connects to GPSD daemon (same as standard GPS demo)
- Waits for GPS fix (requires clear view of sky)
- Continuously reads position, altitude, and speed

### 2. OpenStreetMap Queries
Uses the Overpass API to query for:

**Traffic Signals:**
```
node[highway=traffic_signals](around:500,lat,lon)
```

**Intersections/Crossings:**
```
node[highway=crossing](around:500,lat,lon)
node[highway=turning_circle](around:500,lat,lon)
node[highway=motorway_junction](around:500,lat,lon)
```

### 3. Distance Calculation
- Uses Haversine formula for accurate distance calculation
- Accounts for Earth's curvature
- Results in meters (< 1km) or kilometers (≥ 1km)

### 4. Data Display
- Queries are cached and updated every 5 seconds
- Shows up to 3 nearest features of each type
- Displays street names when available

## Configuration

You can modify these constants in the script:

```python
SEARCH_RADIUS_METERS = 500  # Search radius (default: 500m)
query_interval = 5           # Query frequency (default: 5 seconds)
```

**Note**: The Overpass API has rate limits. Querying too frequently may result in temporary blocks.

## OpenStreetMap Data Tags

### Traffic Signals
- `highway=traffic_signals` - Traffic light nodes
- May include `crossing` type (pedestrian, toucan, etc.)
- `name` or `ref` tags for street names

### Intersections
- `highway=crossing` - Pedestrian crossings
- `highway=turning_circle` - Cul-de-sacs
- `highway=motorway_junction` - Highway junctions
- `name` or `ref` tags for location names

## Troubleshooting

### GPS Not Working
```bash
# Check GPSD status
sudo systemctl status gpsd

# Check GPS device
ls -l /dev/ttyUSB*
ls -l /dev/gps0

# Restart GPSD
sudo systemctl restart gpsd
```

### No Internet Connection
```
Error querying traffic signals: [connection error]
```
- Check internet connection: `ping 8.8.8.8`
- Check DNS resolution: `ping overpass-api.de`
- Check firewall settings

### No Features Found
- Move to an area with more infrastructure
- Increase `SEARCH_RADIUS_METERS` in the script
- Urban areas have better OpenStreetMap coverage

### Slow Queries
- Overpass API can be slow during peak times
- Query time displayed in the output
- Consider increasing `query_interval` if too slow

## API Rate Limits

The Overpass API has usage policies:
- **Limit**: Typically 2 queries per second
- **This script**: Queries every 5 seconds (well within limits)
- **Blocking**: Excessive queries may result in temporary IP blocks

## Project Integration

This demo is part of the **SignalSight** project, which uses:
- GPS for location tracking
- YOLOv8 for traffic light detection
- OpenStreetMap for contextual awareness
- Arduino for driver alerts

This demo shows how GPS location can be enhanced with map data to provide context about nearby traffic infrastructure.

## License

Part of the SignalSight project - AI-powered traffic light detection for safer driving.
