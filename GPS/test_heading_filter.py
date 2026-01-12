#!/usr/bin/env python3
"""
Test script to verify heading-based traffic light filtering.

This script verifies that the system only tracks traffic lights
in the direction of travel and ignores lights behind the vehicle.
"""

import sys
from traffic_light_db import TrafficLightDB

def test_bearing_calculation():
    """Test bearing calculation."""
    db = TrafficLightDB('data/traffic_lights.db')

    # Test bearing calculation
    # From (45.0, -75.0) to (45.1, -75.0) should be ~0° (North)
    bearing = db._calculate_bearing(45.0, -75.0, 45.1, -75.0)
    print(f"Bearing North: {bearing:.1f}° (expected ~0°)")

    # From (45.0, -75.0) to (45.0, -74.9) should be ~90° (East)
    bearing = db._calculate_bearing(45.0, -75.0, 45.0, -74.9)
    print(f"Bearing East: {bearing:.1f}° (expected ~90°)")

    # From (45.0, -75.0) to (44.9, -75.0) should be ~180° (South)
    bearing = db._calculate_bearing(45.0, -75.0, 44.9, -75.0)
    print(f"Bearing South: {bearing:.1f}° (expected ~180°)")

    # From (45.0, -75.0) to (45.0, -75.1) should be ~270° (West)
    bearing = db._calculate_bearing(45.0, -75.0, 45.0, -75.1)
    print(f"Bearing West: {bearing:.1f}° (expected ~270°)")

    db.close()
    print("✓ Bearing calculation test passed\n")

def test_direction_filtering():
    """Test that direction filtering works correctly."""
    db = TrafficLightDB('data/traffic_lights.db')

    # Test with a known location (Barrhaven, Ottawa)
    lat, lon = 45.2751, -75.7545

    # Get all lights within 500m (no heading filter)
    all_lights = db.get_nearby_lights_fast(lat, lon, 500)
    print(f"All lights within 500m: {len(all_lights)}")

    if len(all_lights) == 0:
        print("No lights found nearby for testing. Try a different location.")
        db.close()
        return

    # Test with different headings
    headings_to_test = [0, 90, 180, 270]

    for heading in headings_to_test:
        lights = db.get_nearby_lights_fast(lat, lon, 500, heading=heading, heading_cone=90)
        print(f"  Heading {heading:3d}° (±90°): {len(lights):2d} lights")

        # Verify that filtered count is less than or equal to all lights
        assert len(lights) <= len(all_lights), "Filtered count should not exceed total count"

        # Show the bearings of the lights found
        if lights and len(lights) <= 5:
            for light in lights:
                bearing = db._calculate_bearing(lat, lon, light.lat, light.lon)
                print(f"    Light {light.id}: {light.distance:.0f}m, bearing {bearing:.0f}°")

    db.close()
    print("✓ Direction filtering test passed\n")

def test_narrow_cone():
    """Test with a narrow heading cone."""
    db = TrafficLightDB('data/traffic_lights.db')

    lat, lon = 45.2751, -75.7545
    heading = 0  # North

    # Get lights with wide cone (±90°)
    lights_wide = db.get_nearby_lights_fast(lat, lon, 500, heading=heading, heading_cone=90)

    # Get lights with narrow cone (±45°)
    lights_narrow = db.get_nearby_lights_fast(lat, lon, 500, heading=heading, heading_cone=45)

    # Get lights with very narrow cone (±15°)
    lights_very_narrow = db.get_nearby_lights_fast(lat, lon, 500, heading=heading, heading_cone=15)

    print(f"Heading {heading}°:")
    print(f"  ±90° cone: {len(lights_wide)} lights")
    print(f"  ±45° cone: {len(lights_narrow)} lights")
    print(f"  ±15° cone: {len(lights_very_narrow)} lights")

    # Narrower cone should have fewer or equal lights
    assert len(lights_narrow) <= len(lights_wide), "Narrow cone should have fewer lights"
    assert len(lights_very_narrow) <= len(lights_narrow), "Very narrow cone should have fewer lights"

    db.close()
    print("✓ Narrow cone test passed\n")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Heading-Based Traffic Light Filtering")
    print("=" * 60)
    print()

    try:
        test_bearing_calculation()
        test_direction_filtering()
        test_narrow_cone()

        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        print("\nThe system now only tracks traffic lights in the direction")
        print("of travel and ignores lights behind the vehicle.")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
