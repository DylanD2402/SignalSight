#!/usr/bin/env python3
"""
GPS to Street Address Converter
Uses OpenStreetMap Nominatim API for reverse geocoding
Displays current location as a street address
"""

from gps import gps, WATCH_ENABLE
import time
import requests
import json


def reverse_geocode(lat, lon):
    """
    Convert latitude/longitude to street address using OSM Nominatim
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/reverse"

    # Parameters for the request
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'addressdetails': 1,
        'zoom': 18  # High zoom for precise address
    }

    # Headers (Nominatim requires User-Agent)
    headers = {
        'User-Agent': 'SignalSight-GPS-Project/1.0 (Educational)'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error contacting Nominatim API: {e}")
        return None


def format_address(geocode_data):
    """
    Extract and format address from Nominatim response
    """
    if not geocode_data:
        return None

    address = geocode_data.get('address', {})

    # Extract components
    house_number = address.get('house_number', '')
    road = address.get('road', '')
    neighbourhood = address.get('neighbourhood', '')
    suburb = address.get('suburb', '')
    city = address.get('city', address.get('town', address.get('village', '')))
    state = address.get('state', '')
    postcode = address.get('postcode', '')
    country = address.get('country', '')

    # Build formatted address
    street_address = f"{house_number} {road}".strip()

    return {
        'street': street_address,
        'neighbourhood': neighbourhood,
        'suburb': suburb,
        'city': city,
        'state': state,
        'postcode': postcode,
        'country': country,
        'full_display': geocode_data.get('display_name', 'Unknown'),
        'formatted': street_address
    }


def main():
    print("=" * 70)
    print("GPS Street Address Finder")
    print("Using OpenStreetMap Nominatim Reverse Geocoding")
    print("=" * 70)
    print("\nWaiting for GPS fix...")
    print("(This may take 1-3 minutes)\n")

    # Check if requests library is available
    try:
        import requests
    except ImportError:
        print("Error: 'requests' library not installed")
        print("\nInstall it with:")
        print("  pip3 install requests --break-system-packages")
        print("or")
        print("  sudo apt-get install python3-requests")
        return

    try:
        session = gps(mode=WATCH_ENABLE)

        last_lat = None
        last_lon = None
        last_address = None
        fix_obtained = False

        while True:
            report = session.next()

            if report['class'] == 'TPV':
                if hasattr(report, 'lat') and hasattr(report, 'lon'):
                    lat = report.lat
                    lon = report.lon

                    if not fix_obtained:
                        print("GPS FIX OBTAINED")
                        fix_obtained = True

                    # Only query if position changed significantly (>10 meters)
                    if last_lat is None or abs(lat - last_lat) > 0.0001 or abs(lon - last_lon) > 0.0001:
                        last_lat = lat
                        last_lon = lon
                        print("=" * 70)
                        print(f"\nCoordinates: {lat:.6f}, {lon:.6f}")
                        print("Fetching address from OpenStreetMap...")

                        # Get address from coordinates
                        geocode_data = reverse_geocode(lat, lon)

                        if geocode_data:
                            addr = format_address(geocode_data)

                            if addr:
                                print("\n")
                                print("YOUR CURRENT LOCATION:")

                                if addr['street']:
                                    print(f"\nStreet Address: {addr['street']}")
                                else:
                                    print(f"\nLocation: Near {addr['city'] or 'Unknown'}")

                                if addr['neighbourhood']:
                                    print(f"   Neighbourhood:  {addr['neighbourhood']}")

                                if addr['suburb']:
                                    print(f"   Suburb:         {addr['suburb']}")

                                if addr['city']:
                                    print(f"   City:           {addr['city']}")

                                if addr['state']:
                                    print(f"   State/Province: {addr['state']}")

                                if addr['postcode']:
                                    print(f"   Postal Code:    {addr['postcode']}")

                                if addr['country']:
                                    print(f"   Country:        {addr['country']}")

                                print(f"\n   Full Address:")
                                print(f"   {addr['full_display']}")

                                print("\n")

                                # Additional GPS info
                                if hasattr(report, 'alt'):
                                    print(f"   Altitude:  {report.alt:.1f} m")


                                last_address = addr
                        else:
                            print("Could not fetch address (API error)")

                        print("\nMonitoring for position changes...")
                        print("(Will update when you move >10 meters)")
                        print("Press Ctrl+C to stop\n")

            elif report['class'] == 'SKY':
                if hasattr(report, 'satellites') and not fix_obtained:
                    sats = report.satellites
                    visible = len(sats)
                    used = sum(1 for s in sats if hasattr(s, 'used') and s.used)
                    if visible > 0:
                        print(f"Satellites: {used} used / {visible} visible")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n")
        print("Stopped.")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure GPSD is running: sudo systemctl status gpsd")
        print("2. Check GPS connection: gpsmon")
        print("3. Ensure internet connection (for Nominatim API)")
        print("4. Install requests: pip3 install requests --break-system-packages")


if __name__ == "__main__":
    main()