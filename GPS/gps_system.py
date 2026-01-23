#!/usr/bin/env python3
"""
GPS Traffic Light System for SignalSight

Integrates GPS module (u-blox NEO-M8N) with local traffic light database
for real-time proximity detection. Optimized for Raspberry Pi 5.

Features:
- Direct serial communication with GPS module (NMEA parsing)
- Configurable query rate (default 2Hz to reduce overhead)
- Thread-safe database queries
- Arduino serial communication for alerts
- Graceful error handling for GPS signal loss

Author: SignalSight Team
"""

import serial
import threading
import time
import logging
import queue
from typing import Optional, List, Callable
from dataclasses import dataclass

import pynmea2

from traffic_light_db import TrafficLightDB, TrafficLight

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GPSPosition:
    """GPS position data."""
    latitude: float
    longitude: float
    altitude: Optional[float]
    speed: Optional[float]  # m/s
    heading: Optional[float]  # degrees
    satellites: int
    fix_quality: int
    timestamp: float


@dataclass
class ProximityAlert:
    """Proximity alert for nearby traffic light."""
    light_id: int
    distance_m: float
    lat: float
    lon: float
    zone: str  # 'far', 'approaching', 'near', 'imminent'


class GPSTrafficLightSystem:
    """
    GPS-based traffic light proximity detection system.

    Reads GPS data from NEO-M8N module, queries local traffic light database,
    and provides real-time proximity alerts for integration with Arduino.

    Usage:
        system = GPSTrafficLightSystem(
            gps_port='/dev/ttyUSB0',
            db_path='/path/to/traffic_lights.db',
            arduino_port='/dev/ttyACM0'
        )
        system.start()

        # Get current state
        position = system.get_current_position()
        closest = system.get_closest_light()

        # Run for a while
        time.sleep(60)

        system.stop()
    """

    # Distance zones for alerts (meters)
    ZONE_IMMINENT = 50    # Very close, brake check
    ZONE_NEAR = 100       # Prepare to stop
    ZONE_APPROACHING = 250  # Traffic light ahead
    ZONE_FAR = 500        # Monitor

    def __init__(
        self,
        gps_port: str = '/dev/gps0',
        gps_baudrate: int = 9600,
        db_path: str = 'data/traffic_lights.db',
        arduino_port: str = '/dev/ttyACM0',
        arduino_baudrate: int = 115200,
        query_interval: float = 0.5,  # 2Hz queries
        search_radius: float = 500.0,  # meters
    ):
        """
        Initialize GPS Traffic Light System.

        Args:
            gps_port: Serial port for GPS module
            gps_baudrate: GPS serial baud rate (NEO-M8N default 9600)
            db_path: Path to traffic light database
            arduino_port: Serial port for Arduino (None to disable)
            arduino_baudrate: Arduino serial baud rate
            query_interval: Seconds between database queries (0.5 = 2Hz)
            search_radius: Radius in meters to search for lights
        """
        self.gps_port = gps_port
        self.gps_baudrate = gps_baudrate
        self.db_path = db_path
        self.arduino_port = arduino_port
        self.arduino_baudrate = arduino_baudrate
        self.query_interval = query_interval
        self.search_radius = search_radius

        # State
        self._running = False
        self._position: Optional[GPSPosition] = None
        self._nearby_lights: List[TrafficLight] = []
        self._last_query_time = 0.0

        # Thread safety
        self._lock = threading.RLock()
        self._position_lock = threading.Lock()

        # Serial connections
        self._gps_serial: Optional[serial.Serial] = None
        self._arduino_serial: Optional[serial.Serial] = None

        # Database connection
        self._db: Optional[TrafficLightDB] = None

        # Threads
        self._gps_thread: Optional[threading.Thread] = None
        self._query_thread: Optional[threading.Thread] = None

        # Callbacks
        self._on_position_update: Optional[Callable[[GPSPosition], None]] = None
        self._on_proximity_alert: Optional[Callable[[ProximityAlert], None]] = None

        # Stats
        self._query_count = 0
        self._total_query_time = 0.0

        logger.info(f"GPSTrafficLightSystem initialized")
        logger.info(f"  GPS: {gps_port} @ {gps_baudrate}")
        logger.info(f"  Database: {db_path}")
        logger.info(f"  Query interval: {query_interval}s ({1/query_interval:.1f}Hz)")

    def start(self) -> bool:
        """
        Start the GPS tracking and database query system.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("System already running")
            return False

        try:
            # Open database connection
            self._db = TrafficLightDB(self.db_path)
            stats = self._db.get_stats()
            logger.info(f"Database loaded: {stats['total_lights']} lights")

            # Open GPS serial port
            self._gps_serial = serial.Serial(
                port=self.gps_port,
                baudrate=self.gps_baudrate,
                timeout=1.0
            )
            logger.info(f"GPS serial opened: {self.gps_port}")

            # Open Arduino serial port (optional)
            if self.arduino_port:
                self._arduino_serial = serial.Serial(
                    port=self.arduino_port,
                    baudrate=self.arduino_baudrate,
                    timeout=0.1
                )
                logger.info(f"Arduino serial opened: {self.arduino_port}")

            # Start threads
            self._running = True

            self._gps_thread = threading.Thread(
                target=self._gps_reader_loop,
                name="GPS-Reader",
                daemon=True
            )
            self._gps_thread.start()

            self._query_thread = threading.Thread(
                target=self._query_loop,
                name="DB-Query",
                daemon=True
            )
            self._query_thread.start()

            logger.info("System started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start system: {e}")
            self.stop()
            return False

    def stop(self):
        """Stop the system and clean up resources."""
        logger.info("Stopping system...")
        self._running = False

        # Wait for threads
        if self._gps_thread and self._gps_thread.is_alive():
            self._gps_thread.join(timeout=2.0)

        if self._query_thread and self._query_thread.is_alive():
            self._query_thread.join(timeout=2.0)

        # Close serial ports
        if self._gps_serial and self._gps_serial.is_open:
            self._gps_serial.close()
            logger.debug("GPS serial closed")

        if self._arduino_serial and self._arduino_serial.is_open:
            self._arduino_serial.close()
            logger.debug("Arduino serial closed")

        # Close database
        if self._db:
            self._db.close()
            logger.debug("Database closed")

        # Log stats
        if self._query_count > 0:
            avg_ms = (self._total_query_time / self._query_count) * 1000
            logger.info(f"Query stats: {self._query_count} queries, "
                       f"avg {avg_ms:.2f}ms")

        logger.info("System stopped")

    def _gps_reader_loop(self):
        """
        Background thread to read and parse GPS data.

        Reads NMEA sentences from serial port and updates current position.
        """
        logger.debug("GPS reader thread started")

        while self._running:
            try:
                # Read line from GPS
                if not self._gps_serial or not self._gps_serial.is_open:
                    time.sleep(0.1)
                    continue

                line = self._gps_serial.readline()

                if not line:
                    continue

                # Decode and parse
                try:
                    sentence = line.decode('ascii', errors='ignore').strip()
                except UnicodeDecodeError:
                    continue

                if not sentence.startswith('$'):
                    continue

                # Parse NMEA sentence
                try:
                    msg = pynmea2.parse(sentence)
                except pynmea2.ParseError:
                    continue

                # Extract position from GGA sentences (most complete fix data)
                # Support both $GNGGA (multi-constellation) and $GPGGA (GPS only)
                if isinstance(msg, pynmea2.GGA):
                    self._process_gga_message(msg)

                # Extract speed/heading from VTG sentences
                elif isinstance(msg, pynmea2.VTG):
                    self._process_vtg_message(msg)

            except serial.SerialException as e:
                logger.error(f"GPS serial error: {e}")
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"GPS reader error: {e}")
                time.sleep(0.1)

        logger.debug("GPS reader thread stopped")

    def _process_gga_message(self, msg: pynmea2.GGA):
        """Process GGA message to update position."""
        # Check for valid fix
        if not msg.latitude or not msg.longitude:
            return

        fix_quality = int(msg.gps_qual) if msg.gps_qual else 0
        if fix_quality == 0:
            return  # No fix

        # Parse altitude
        altitude = None
        if msg.altitude:
            try:
                altitude = float(msg.altitude)
            except (ValueError, TypeError):
                pass

        # Parse satellite count
        satellites = 0
        if msg.num_sats:
            try:
                satellites = int(msg.num_sats)
            except (ValueError, TypeError):
                pass

        # Get existing speed/heading if available
        speed = None
        heading = None
        with self._position_lock:
            if self._position:
                speed = self._position.speed
                heading = self._position.heading

        # Update position
        position = GPSPosition(
            latitude=msg.latitude,
            longitude=msg.longitude,
            altitude=altitude,
            speed=speed,
            heading=heading,
            satellites=satellites,
            fix_quality=fix_quality,
            timestamp=time.time()
        )

        with self._position_lock:
            self._position = position

        # Call callback if set
        if self._on_position_update:
            try:
                self._on_position_update(position)
            except Exception as e:
                logger.error(f"Position callback error: {e}")

    def _process_vtg_message(self, msg: pynmea2.VTG):
        """Process VTG message to update speed/heading."""
        with self._position_lock:
            if not self._position:
                return

            # Update speed (convert km/h to m/s)
            if msg.spd_over_grnd_kmph:
                try:
                    self._position.speed = float(msg.spd_over_grnd_kmph) / 3.6
                except (ValueError, TypeError):
                    pass

            # Update heading
            if msg.true_track:
                try:
                    self._position.heading = float(msg.true_track)
                except (ValueError, TypeError):
                    pass

    def _query_loop(self):
        """
        Background thread to query database for nearby lights.

        Runs at configured interval (default 2Hz) to balance performance.
        """
        logger.debug("Query thread started")

        while self._running:
            try:
                current_time = time.time()

                # Check if it's time for next query
                if current_time - self._last_query_time < self.query_interval:
                    time.sleep(0.01)
                    continue

                # Get current position
                with self._position_lock:
                    position = self._position

                if not position:
                    time.sleep(0.1)
                    continue

                # Query database
                start_time = time.perf_counter()

                # Only track lights in the direction of travel if heading is available
                lights = self._db.get_nearby_lights_fast(
                    position.latitude,
                    position.longitude,
                    self.search_radius,
                    heading=position.heading,
                    heading_cone=90.0  # Track lights within ±90° of heading
                )

                query_time = time.perf_counter() - start_time

                # Update stats
                self._query_count += 1
                self._total_query_time += query_time

                # Store results
                with self._lock:
                    self._nearby_lights = lights

                self._last_query_time = current_time

                # Process alerts
                if lights:
                    closest = lights[0]
                    zone = self._get_distance_zone(closest.distance)

                    alert = ProximityAlert(
                        light_id=closest.id,
                        distance_m=closest.distance,
                        lat=closest.lat,
                        lon=closest.lon,
                        zone=zone
                    )

                    # Send to Arduino
                    if self._arduino_serial:
                        self._send_arduino_alert(alert)

                    # Call callback
                    if self._on_proximity_alert:
                        try:
                            self._on_proximity_alert(alert)
                        except Exception as e:
                            logger.error(f"Alert callback error: {e}")

                # Log periodic stats
                if self._query_count % 100 == 0:
                    avg_ms = (self._total_query_time / self._query_count) * 1000
                    logger.debug(f"Query stats: {self._query_count} queries, "
                                f"avg {avg_ms:.2f}ms, found {len(lights)} lights")

            except Exception as e:
                logger.error(f"Query loop error: {e}")
                time.sleep(0.1)

        logger.debug("Query thread stopped")

    def _get_distance_zone(self, distance_m: float) -> str:
        """Get zone name for distance."""
        if distance_m <= self.ZONE_IMMINENT:
            return 'imminent'
        elif distance_m <= self.ZONE_NEAR:
            return 'near'
        elif distance_m <= self.ZONE_APPROACHING:
            return 'approaching'
        else:
            return 'far'

    def _send_arduino_alert(self, alert: ProximityAlert):
        """
        Send proximity alert to Arduino via serial.

        Protocol: "LIGHT,<id>,<distance>,<zone>\\n"
        """
        if not self._arduino_serial or not self._arduino_serial.is_open:
            return

        try:
            message = f"LIGHT,{alert.light_id},{alert.distance_m:.1f},{alert.zone}\n"
            self._arduino_serial.write(message.encode('ascii'))
            logger.debug(f"Sent to Arduino: {message.strip()}")
        except serial.SerialException as e:
            logger.error(f"Arduino write error: {e}")

    def get_current_position(self) -> Optional[GPSPosition]:
        """
        Get current GPS position.

        Returns:
            GPSPosition or None if no fix
        """
        with self._position_lock:
            return self._position

    def get_nearby_lights(self) -> List[TrafficLight]:
        """
        Get list of nearby traffic lights.

        Returns:
            List of TrafficLight objects sorted by distance
        """
        with self._lock:
            return self._nearby_lights.copy()

    def get_closest_light(self) -> Optional[TrafficLight]:
        """
        Get the closest traffic light.

        Returns:
            TrafficLight or None if no lights nearby
        """
        with self._lock:
            return self._nearby_lights[0] if self._nearby_lights else None

    def is_approaching_light(self, threshold_m: float = 100) -> bool:
        """
        Check if approaching a traffic light within threshold.

        Args:
            threshold_m: Distance threshold in meters

        Returns:
            True if within threshold of a traffic light
        """
        closest = self.get_closest_light()
        return closest is not None and closest.distance <= threshold_m

    def set_position_callback(self, callback: Callable[[GPSPosition], None]):
        """Set callback for position updates."""
        self._on_position_update = callback

    def set_alert_callback(self, callback: Callable[[ProximityAlert], None]):
        """Set callback for proximity alerts."""
        self._on_proximity_alert = callback

    def send_distance_to_arduino(self, distance_m: float):
        """
        Send raw distance value to Arduino.

        Args:
            distance_m: Distance in meters
        """
        if not self._arduino_serial or not self._arduino_serial.is_open:
            return

        try:
            message = f"DIST,{distance_m:.1f}\n"
            self._arduino_serial.write(message.encode('ascii'))
        except serial.SerialException as e:
            logger.error(f"Arduino write error: {e}")

    def get_stats(self) -> dict:
        """Get system statistics."""
        avg_query_ms = 0
        if self._query_count > 0:
            avg_query_ms = (self._total_query_time / self._query_count) * 1000

        return {
            'running': self._running,
            'has_fix': self._position is not None,
            'query_count': self._query_count,
            'avg_query_ms': avg_query_ms,
            'nearby_lights': len(self._nearby_lights),
            'closest_distance': self._nearby_lights[0].distance if self._nearby_lights else None
        }

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='GPS Traffic Light System')
    parser.add_argument('--db', default='data/traffic_lights.db',
                        help='Path to traffic light database')
    parser.add_argument('--gps-port', default='/dev/gps0',
                        help='GPS serial port')
    parser.add_argument('--arduino-port', default=None,
                        help='Arduino serial port')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output (distance, zone, position)')

    args = parser.parse_args()

    # Suppress all logging - we use custom output in debug mode
    logging.disable(logging.CRITICAL)

    # Create system
    system = GPSTrafficLightSystem(
        gps_port=args.gps_port,
        db_path=args.db,
        arduino_port=args.arduino_port
    )

    # Only set up callbacks and output in debug mode
    if args.debug:
        import sys
        last_zone = [None]  # Use list to allow modification in nested function

        def on_alert(alert: ProximityAlert):
            # Only print new line when zone changes
            if alert.zone != last_zone[0]:
                print(f"\nZone changed: {alert.zone.upper()} ({alert.distance_m:.0f}m)")
                last_zone[0] = alert.zone

        system.set_alert_callback(on_alert)

        print("GPS Traffic Light System (Debug Mode)")
        print("=" * 40)
        print(f"GPS Port: {args.gps_port}")
        print(f"Database: {args.db}")
        print("Press Ctrl+C to stop\n")

    try:
        with system:
            while True:
                time.sleep(0.5)

                if args.debug:
                    pos = system.get_current_position()
                    closest = system.get_closest_light()

                    if pos:
                        speed_kmh = pos.speed * 3.6 if pos.speed else 0
                        heading_str = f"{pos.heading:.0f}" if pos.heading is not None else "N/A"

                        if closest:
                            zone = system._get_distance_zone(closest.distance)
                            status = (f"Pos: {pos.latitude:.5f}, {pos.longitude:.5f} | "
                                     f"Spd: {speed_kmh:.0f}km/h | Hdg: {heading_str} | "
                                     f"Sats: {pos.satellites} | "
                                     f"Light: {closest.distance:.0f}m [{zone.upper()}]")
                        else:
                            status = (f"Pos: {pos.latitude:.5f}, {pos.longitude:.5f} | "
                                     f"Spd: {speed_kmh:.0f}km/h | Hdg: {heading_str} | "
                                     f"Sats: {pos.satellites} | No lights nearby")

                        # Overwrite same line
                        sys.stdout.write(f"\r{status:<80}")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write(f"\rWaiting for GPS fix...{' '*50}")
                        sys.stdout.flush()

    except KeyboardInterrupt:
        if args.debug:
            print("\n\nStopped.")
