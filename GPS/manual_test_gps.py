#!/usr/bin/env python3
"""
Simple GPS test script
Tests connection to GPS module via GPSD
"""

from gps import gps, WATCH_ENABLE, WATCH_DISABLE
import time

def main():
    print("=" * 50)
    print("GPS Module Test Script")
    print("=" * 50)
    print("\nConnecting to GPS module...")
    print("Press Ctrl+C to stop\n")

    try:
        # Connect to GPSD
        session = gps(mode=WATCH_ENABLE)
        print("Connected to GPSD daemon")
        print("Waiting for GPS data...\n")

        fix_obtained = False
        no_fix_count = 0
        
        while True:
            # Get next GPS report
            report = session.next()
            
            # Check if this is a position report
            if report['class'] == 'TPV':
                # Check if we have a valid position
                if hasattr(report, 'lat') and hasattr(report, 'lon'):
                    if not fix_obtained:
                        print("\n" + "=" * 50)
                        print("GPS FIX OBTAINED!")
                        print("=" * 50 + "\n")
                        fix_obtained = True
                    
                    print(f"Latitude:  {report.lat:.6f}°")
                    print(f"Longitude: {report.lon:.6f}°")
                    
                    if hasattr(report, 'alt'):
                        print(f"Altitude:  {report.alt:.1f} m")
                    
                    if hasattr(report, 'speed'):
                        speed_kmh = report.speed * 3.6  # Convert m/s to km/h
                        print(f"Speed:     {speed_kmh:.1f} km/h")
                    
                    if hasattr(report, 'track'):
                        print(f"Heading:   {report.track:.1f}°")
                    
                    if hasattr(report, 'time'):
                        print(f"GPS Time:  {report.time}")
                    
                    print("-" * 50)
                    
                else:
                    if not fix_obtained:
                        no_fix_count += 1
                        if no_fix_count == 1 or no_fix_count % 3 == 0:  # Print initially and every 3 seconds
                            print(f"\nConnecting to GPS module{'.' * ((no_fix_count // 3) % 4)}")
                            print(f"Waiting for GPS fix... ({no_fix_count}s elapsed)")
                            print()
                            print(f"Latitude:  N/A")
                            print(f"Longitude: N/A")
                            print(f"Altitude:  N/A")
                            print(f"Speed:     N/A")
                            print(f"Heading:   N/A")
                            print(f"GPS Time:  N/A")
                            print()
                            print("TIP: Move GPS module near window or outdoors")
                            print("-" * 50)
            
            # Also check for satellite info
            elif report['class'] == 'SKY':
                if hasattr(report, 'satellites'):
                    sat_count = len(report.satellites)
                    used_count = sum(1 for sat in report.satellites if hasattr(sat, 'used') and sat.used)
                    if sat_count > 0:
                        print(f"Satellites: {used_count} used / {sat_count} visible")
            
            time.sleep(1)  # Update every second
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 50)
        print("Stopping GPS test...")
        print("=" * 50)
        session = gps(mode=WATCH_DISABLE)
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\n" + "=" * 50)
        print("Troubleshooting:")
        print("=" * 50)
        print("1. Is GPSD running?")
        print("   Check: sudo systemctl status gpsd")
        print("\n2. Is GPS module connected?")
        print("   Check: ls -l /dev/ttyUSB*")
        print("\n3. Try restarting GPSD:")
        print("   Run: ~/restart_gps.sh")
        print("   Or: sudo systemctl restart gpsd")

if __name__ == "__main__":
    main()
