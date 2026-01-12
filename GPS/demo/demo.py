#!/usr/bin/env python3
"""
GPS Demo Script for SignalSight
Shows live GPS data in a clean, easy-to-read format
"""

from gps import gps, WATCH_ENABLE, WATCH_DISABLE
import time
import os

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def format_speed(speed_ms):
    """Convert speed from m/s to km/h and mph"""
    kmh = speed_ms * 3.6
    mph = speed_ms * 2.23694
    return f"{kmh:.1f} km/h ({mph:.1f} mph)"

def main():
    print("=" * 60)
    print("           SignalSight GPS Demo")
    print("=" * 60)
    print("Connecting to GPS module...")
    print("Press Ctrl+C to exit\n")

    try:
        session = gps(mode=WATCH_ENABLE)
        print("Connected to GPSD daemon")
        print("Waiting for GPS data...\n")

        fix_obtained = False
        satellite_info = "Searching..."
        wait_counter = 0

        while True:
            report = session.next()

            # Get satellite information
            if report['class'] == 'SKY':
                if hasattr(report, 'satellites'):
                    sat_count = len(report.satellites)
                    used_count = sum(1 for sat in report.satellites if hasattr(sat, 'used') and sat.used)
                    satellite_info = f"{used_count}/{sat_count} satellites"

            # Get position data
            if report['class'] == 'TPV':
                if hasattr(report, 'lat') and hasattr(report, 'lon'):
                    if not fix_obtained:
                        fix_obtained = True
                        clear_screen()

                    # Clear screen and display header
                    clear_screen()
                    print("=" * 60)
                    print("           SignalSight GPS - LIVE DATA")
                    print("=" * 60)
                    print()

                    # Position
                    print(f"  LOCATION:")
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
                        print(f"  SPEED:")
                        print(f"    {format_speed(report.speed)}")
                        print()

                    # Heading
                    if hasattr(report, 'track'):
                        print(f"  HEADING:")
                        print(f"    {report.track:>12.1f}°")
                        print()

                    # Satellites
                    print(f"  SATELLITES:")
                    print(f"    {satellite_info}")
                    print()

                    # GPS Time
                    if hasattr(report, 'time'):
                        print(f"  GPS TIME:")
                        print(f"    {report.time}")

                    print()
                    print("=" * 60)
                    print("  Status: GPS FIX ACTIVE | Press Ctrl+C to exit")
                    print("=" * 60)

                else:
                    # Still waiting for fix
                    if not fix_obtained:
                        wait_counter += 1
                        clear_screen()
                        print("=" * 60)
                        print("           SignalSight GPS - WAITING FOR FIX")
                        print("=" * 60)
                        print()

                        # Show data format with N/A values
                        print(f"  LOCATION:")
                        print(f"    Latitude:   {'N/A':>12}")
                        print(f"    Longitude:  {'N/A':>12}")
                        print()

                        print(f"  ALTITUDE:")
                        print(f"    {'N/A':>12}")
                        print()

                        print(f"  SPEED:")
                        print(f"    N/A")
                        print()

                        print(f"  HEADING:")
                        print(f"    {'N/A':>12}")
                        print()

                        print(f"  SATELLITES:")
                        print(f"    {satellite_info}")
                        print()

                        print(f"  GPS TIME:")
                        print(f"    N/A")

                        print()
                        print("=" * 60)
                        print(f"  Status: Connecting to GPS module{'.' * (wait_counter % 4)}")
                        print(f"  Waiting for GPS fix... ({wait_counter}s elapsed)")
                        print()
                        print("  TIP: Move GPS module near window or outdoors")
                        print("=" * 60)

            time.sleep(1)

    except KeyboardInterrupt:
        clear_screen()
        print("=" * 60)
        print("           GPS Demo Stopped")
        print("=" * 60)
        print("Thank you for viewing the SignalSight GPS demo!")
        print()
        session = gps(mode=WATCH_DISABLE)

    except Exception as e:
        clear_screen()
        print("=" * 60)
        print("           ERROR")
        print("=" * 60)
        print(f"\nError: {e}\n")
        print("Troubleshooting:")
        print("  1. Check GPSD is running: sudo systemctl status gpsd")
        print("  2. Check GPS connected: ls -l /dev/ttyUSB*")
        print("  3. Restart GPSD: sudo systemctl restart gpsd")
        print()
        print("=" * 60)

if __name__ == "__main__":
    main()
