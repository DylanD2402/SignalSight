#!/usr/bin/env python3
"""
Demonstration of heading-based traffic light filtering.

Shows how the system filters lights based on direction of travel.
"""

from traffic_light_db import TrafficLightDB

def main():
    """Demonstrate heading filtering."""
    print("=" * 70)
    print("Traffic Light Heading Filter Demonstration")
    print("=" * 70)
    print()

    # Initialize database
    db = TrafficLightDB('data/traffic_lights.db')

    # Use Barrhaven, Ottawa as test location
    lat, lon = 45.2751, -75.7545

    print(f"Vehicle Position: {lat:.6f}, {lon:.6f}")
    print()

    # Scenario 1: No heading filter (original behavior)
    print("SCENARIO 1: No Heading Filter (Original Behavior)")
    print("-" * 70)
    lights = db.get_nearby_lights_fast(lat, lon, 500)
    print(f"Found {len(lights)} traffic lights within 500m (all directions)")

    if lights:
        print("\nAll nearby lights:")
        for i, light in enumerate(lights[:5], 1):
            bearing = db._calculate_bearing(lat, lon, light.lat, light.lon)
            direction = get_direction_name(bearing)
            print(f"  {i}. Light {light.id}: {light.distance:.0f}m away, {direction} (bearing {bearing:.0f}°)")

        if len(lights) > 5:
            print(f"  ... and {len(lights) - 5} more")

    print()

    # Scenario 2: Vehicle heading North
    print("SCENARIO 2: Vehicle Heading North (0°)")
    print("-" * 70)
    heading = 0
    lights = db.get_nearby_lights_fast(lat, lon, 500, heading=heading, heading_cone=90)
    print(f"Vehicle heading: {heading}° (North)")
    print(f"Found {len(lights)} traffic lights ahead (within ±90°)")

    if lights:
        print("\nLights ahead:")
        for i, light in enumerate(lights[:5], 1):
            bearing = db._calculate_bearing(lat, lon, light.lat, light.lon)
            direction = get_direction_name(bearing)
            print(f"  {i}. Light {light.id}: {light.distance:.0f}m away, {direction} (bearing {bearing:.0f}°)")
    else:
        print("  No lights ahead in this direction")

    print()

    # Scenario 3: Vehicle heading East
    print("SCENARIO 3: Vehicle Heading East (90°)")
    print("-" * 70)
    heading = 90
    lights = db.get_nearby_lights_fast(lat, lon, 500, heading=heading, heading_cone=90)
    print(f"Vehicle heading: {heading}° (East)")
    print(f"Found {len(lights)} traffic lights ahead (within ±90°)")

    if lights:
        print("\nLights ahead:")
        for i, light in enumerate(lights[:5], 1):
            bearing = db._calculate_bearing(lat, lon, light.lat, light.lon)
            direction = get_direction_name(bearing)
            print(f"  {i}. Light {light.id}: {light.distance:.0f}m away, {direction} (bearing {bearing:.0f}°)")
    else:
        print("  No lights ahead in this direction")

    print()

    # Scenario 4: Passing an intersection
    print("SCENARIO 4: Simulating Passing an Intersection")
    print("-" * 70)
    print("As you approach and pass a light, it will be filtered out:")
    print()

    # Simulate approaching from the south (heading north)
    heading = 0

    for dist_change in [0, 50, 100, 150]:
        # Simulate moving north by adjusting latitude
        current_lat = lat - (dist_change / 111320.0)
        lights = db.get_nearby_lights_fast(current_lat, lon, 500, heading=heading, heading_cone=90)

        print(f"  After moving {dist_change}m north:")
        if lights:
            closest = lights[0]
            bearing = db._calculate_bearing(current_lat, lon, closest.lat, closest.lon)
            print(f"    Tracking light {closest.id}: {closest.distance:.0f}m away (bearing {bearing:.0f}°)")
        else:
            print(f"    No lights ahead (passed the intersection)")

    print()

    db.close()

    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print("✓ The system now only tracks lights in the direction of travel")
    print("✓ Lights behind the vehicle are automatically filtered out")
    print("✓ After passing an intersection, that light is no longer tracked")
    print("✓ Default cone: ±90° from heading (can be adjusted)")
    print()

def get_direction_name(bearing):
    """Convert bearing to compass direction."""
    if bearing < 22.5 or bearing >= 337.5:
        return "North"
    elif bearing < 67.5:
        return "Northeast"
    elif bearing < 112.5:
        return "East"
    elif bearing < 157.5:
        return "Southeast"
    elif bearing < 202.5:
        return "South"
    elif bearing < 247.5:
        return "Southwest"
    elif bearing < 292.5:
        return "West"
    else:
        return "Northwest"

if __name__ == "__main__":
    main()
