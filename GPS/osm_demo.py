#!/usr/bin/env python3
"""
GPS + OpenStreetMap Demo Script for SignalSight
Shows live GPS data and finds nearest traffic lights and intersections using OpenStreetMap
"""

from gps import gps, WATCH_ENABLE, WATCH_DISABLE
import time
import os
import requests
import math
import json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_METERS = 500  # Search within 500 meters

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula
    Returns distance in meters
    """
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2)**2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    distance = R * c
    return distance

def query_traffic_signals(lat, lon, radius=SEARCH_RADIUS_METERS):
    """
    Query OpenStreetMap for traffic signals near the given coordinates
    Returns list of traffic signals with their coordinates and tags
    """
    query = f"""
    [out:json];
    node[highway=traffic_signals](around:{radius},{lat},{lon});
    out body;
    """

    try:
        response = requests.get(OVERPASS_URL, params={'data': query}, timeout=10)
        response.raise_for_status()
        data = response.json()

        signals = []
        for element in data.get('elements', []):
            signal_info = {
                'id': element.get('id'),
                'lat': element.get('lat'),
                'lon': element.get('lon'),
                'tags': element.get('tags', {}),
                'distance': calculate_distance(lat, lon, element.get('lat'), element.get('lon'))
            }
            signals.append(signal_info)

        # Sort by distance
        signals.sort(key=lambda x: x['distance'])
        return signals

    except Exception as e:
        print(f"Error querying traffic signals: {e}")
        return []

def query_intersections(lat, lon, radius=SEARCH_RADIUS_METERS):
    """
    Query OpenStreetMap for highway intersections near the given coordinates
    Returns list of intersection nodes
    """
    query = f"""
    [out:json];
    (
      node[highway=crossing](around:{radius},{lat},{lon});
      node[highway=turning_circle](around:{radius},{lat},{lon});
      node[highway=motorway_junction](around:{radius},{lat},{lon});
    );
    out body;
    """

    try:
        response = requests.get(OVERPASS_URL, params={'data': query}, timeout=10)
        response.raise_for_status()
        data = response.json()

        intersections = []
        for element in data.get('elements', []):
            intersection_info = {
                'id': element.get('id'),
                'lat': element.get('lat'),
                'lon': element.get('lon'),
                'tags': element.get('tags', {}),
                'type': element.get('tags', {}).get('highway', 'unknown'),
                'distance': calculate_distance(lat, lon, element.get('lat'), element.get('lon'))
            }
            intersections.append(intersection_info)

        # Sort by distance
        intersections.sort(key=lambda x: x['distance'])
        return intersections

    except Exception as e:
        print(f"Error querying intersections: {e}")
        return []

def format_distance(meters):
    """Format distance in meters or kilometers"""
    if meters < 1000:
        return f"{meters:.1f} m"
    else:
        return f"{meters/1000:.2f} km"

def get_street_name(tags):
    """Extract street name from OSM tags"""
    if 'name' in tags:
        return tags['name']
    elif 'ref' in tags:
        return tags['ref']
    return "Unnamed"

def display_data(report, signals, intersections, query_time):
    """Display GPS data and nearby features"""
    clear_screen()
    print("=" * 70)
    print("      SignalSight GPS + OpenStreetMap - LIVE DATA")
    print("=" * 70)
    print()

    # GPS Location
    print(f"  GPS LOCATION:")
    print(f"    Latitude:   {report.lat:>12.6f}°")
    print(f"    Longitude:  {report.lon:>12.6f}°")
    print()

    # Altitude
    if hasattr(report, 'alt'):
        print(f"  ALTITUDE:")
        print(f"    {report.alt:>12.1f} meters ({report.alt * 3.28084:.1f} feet)")
        print()

    # Speed
    if hasattr(report, 'speed'):
        kmh = report.speed * 3.6
        mph = report.speed * 2.23694
        print(f"  SPEED:")
        print(f"    {kmh:.1f} km/h ({mph:.1f} mph)")
        print()

    # Traffic Signals
    print(f"  NEAREST TRAFFIC LIGHTS (within {SEARCH_RADIUS_METERS}m):")
    if signals:
        for i, signal in enumerate(signals[:3], 1):  # Show top 3
            name = get_street_name(signal['tags'])
            distance = format_distance(signal['distance'])
            print(f"    {i}. {distance:>10} - {name}")
            if 'crossing' in signal['tags']:
                print(f"       Type: {signal['tags']['crossing']} crossing")
    else:
        print(f"    No traffic lights found within {SEARCH_RADIUS_METERS}m")
    print()

    # Intersections/Crossings
    print(f"  NEAREST INTERSECTIONS/CROSSINGS (within {SEARCH_RADIUS_METERS}m):")
    if intersections:
        for i, intersection in enumerate(intersections[:3], 1):  # Show top 3
            name = get_street_name(intersection['tags'])
            distance = format_distance(intersection['distance'])
            itype = intersection['type'].replace('_', ' ').title()
            print(f"    {i}. {distance:>10} - {name}")
            print(f"       Type: {itype}")
    else:
        print(f"    No intersections found within {SEARCH_RADIUS_METERS}m")
    print()

    # Query info
    print(f"  LAST QUERY:")
    print(f"    Search radius: {SEARCH_RADIUS_METERS}m")
    print(f"    Query time: {query_time:.2f}s")
    print()

    print("=" * 70)
    print("  Status: GPS FIX ACTIVE | Press Ctrl+C to exit")
    print("=" * 70)

def main():
    print("=" * 70)
    print("      SignalSight GPS + OpenStreetMap Demo")
    print("=" * 70)
    print("Connecting to GPS module...")
    print("This demo finds the nearest traffic lights and intersections")
    print("using the OpenStreetMap Overpass API")
    print("Press Ctrl+C to exit\n")

    try:
        session = gps(mode=WATCH_ENABLE)
        print("Connected to GPSD daemon")
        print("Waiting for GPS fix...\n")

        fix_obtained = False
        last_query_time = 0
        query_interval = 5  # Query OSM every 5 seconds
        signals = []
        intersections = []
        last_osm_query_duration = 0

        while True:
            report = session.next()

            # Get position data
            if report['class'] == 'TPV':
                if hasattr(report, 'lat') and hasattr(report, 'lon'):
                    if not fix_obtained:
                        fix_obtained = True
                        print("GPS fix obtained! Querying OpenStreetMap...")

                    current_time = time.time()

                    # Query OSM periodically
                    if current_time - last_query_time >= query_interval:
                        query_start = time.time()
                        signals = query_traffic_signals(report.lat, report.lon)
                        intersections = query_intersections(report.lat, report.lon)
                        last_osm_query_duration = time.time() - query_start
                        last_query_time = current_time

                    # Display data
                    display_data(report, signals, intersections, last_osm_query_duration)

                else:
                    # Still waiting for fix
                    if not fix_obtained:
                        clear_screen()
                        print("=" * 70)
                        print("      SignalSight GPS + OpenStreetMap - WAITING FOR FIX")
                        print("=" * 70)
                        print()
                        print("  Status: Connecting to GPS module...")
                        print("  Waiting for GPS fix...")
                        print()
                        print("  TIP: Move GPS module near window or outdoors")
                        print("=" * 70)

            time.sleep(1)

    except KeyboardInterrupt:
        clear_screen()
        print("=" * 70)
        print("      GPS + OpenStreetMap Demo Stopped")
        print("=" * 70)
        print("Thank you for viewing the SignalSight demo!")
        print()
        session = gps(mode=WATCH_DISABLE)

    except Exception as e:
        clear_screen()
        print("=" * 70)
        print("      ERROR")
        print("=" * 70)
        print(f"\nError: {e}\n")
        print("Troubleshooting:")
        print("  1. Check GPSD is running: sudo systemctl status gpsd")
        print("  2. Check GPS connected: ls -l /dev/ttyUSB*")
        print("  3. Restart GPSD: sudo systemctl restart gpsd")
        print("  4. Check internet connection for OpenStreetMap queries")
        print()
        print("=" * 70)

if __name__ == "__main__":
    main()
