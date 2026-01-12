#!/usr/bin/env python3
"""
Example Integration for SignalSight GPS Traffic Light System

Demonstrates the complete pipeline:
1. Initialize GPS and database on RPi startup
2. Continuous GPS monitoring
3. Real-time traffic light proximity detection
4. Distance zone alerts
5. Arduino communication for driver alerts

Usage:
    # Full integration with GPS and Arduino
    python example_integration.py

    # Simulation mode (no hardware required)
    python example_integration.py --simulate

    # Specify GPS port
    python example_integration.py --gps-port /dev/ttyUSB0

Author: SignalSight Team
"""

import argparse
import logging
import time
import sys
import random
from pathlib import Path

from traffic_light_db import TrafficLightDB, TrafficLight
from gps_system import (
    GPSTrafficLightSystem,
    GPSPosition,
    ProximityAlert
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalSightGPSIntegration:
    """
    Complete SignalSight GPS Traffic Light Integration.

    This class demonstrates how to integrate the GPS traffic light
    system with the main SignalSight application on Raspberry Pi 5.
    """

    # Alert thresholds (meters)
    ALERT_IMMINENT = 50    # Immediate attention
    ALERT_NEAR = 100       # Prepare to stop
    ALERT_APPROACHING = 250  # Light ahead
    ALERT_FAR = 500        # Monitoring

    def __init__(
        self,
        db_path: str = 'data/traffic_lights.db',
        gps_port: str = '/dev/ttyUSB0',
        arduino_port: str = None
    ):
        """
        Initialize the integration.

        Args:
            db_path: Path to traffic light database
            gps_port: GPS serial port
            arduino_port: Arduino serial port (None to disable)
        """
        self.db_path = db_path

        # Create GPS system
        self.gps_system = GPSTrafficLightSystem(
            gps_port=gps_port,
            db_path=db_path,
            arduino_port=arduino_port,
            query_interval=0.5,  # 2Hz
            search_radius=500.0
        )

        # Set up callbacks
        self.gps_system.set_position_callback(self._on_position_update)
        self.gps_system.set_alert_callback(self._on_proximity_alert)

        # State for tracking
        self._last_zone = None
        self._last_alert_time = 0
        self._alert_cooldown = 2.0  # seconds between alerts

        logger.info("SignalSight GPS Integration initialized")

    def _on_position_update(self, position: GPSPosition):
        """
        Callback for GPS position updates.

        This is called every time we get a new GPS fix.
        """
        # Log significant position changes or periodically
        pass  # Position handled in main loop for clarity

    def _on_proximity_alert(self, alert: ProximityAlert):
        """
        Callback for proximity alerts.

        This is called when a traffic light is detected nearby.
        Use this to trigger driver alerts through the YOLO system.
        """
        current_time = time.time()

        # Check if we should alert (zone changed or cooldown passed)
        should_alert = (
            alert.zone != self._last_zone or
            current_time - self._last_alert_time > self._alert_cooldown
        )

        if should_alert and alert.zone in ['imminent', 'near']:
            self._trigger_driver_alert(alert)
            self._last_alert_time = current_time

        self._last_zone = alert.zone

    def _trigger_driver_alert(self, alert: ProximityAlert):
        """
        Trigger driver alert based on proximity.

        This integrates with the main SignalSight system.
        You would connect this to your YOLO detection and audio alert system.
        """
        if alert.zone == 'imminent':
            logger.warning(f"IMMINENT: Traffic light {alert.light_id} "
                          f"at {alert.distance_m:.0f}m - CHECK FOR LIGHT!")
        elif alert.zone == 'near':
            logger.info(f"NEAR: Traffic light {alert.light_id} "
                       f"at {alert.distance_m:.0f}m - Prepare to stop")

    def start(self) -> bool:
        """
        Start the GPS integration system.

        Returns:
            True if started successfully
        """
        logger.info("Starting SignalSight GPS Integration...")

        if not self.gps_system.start():
            logger.error("Failed to start GPS system")
            return False

        logger.info("GPS Integration started successfully")
        return True

    def stop(self):
        """Stop the GPS integration system."""
        logger.info("Stopping GPS Integration...")
        self.gps_system.stop()
        logger.info("GPS Integration stopped")

    def run_monitoring_loop(self):
        """
        Main monitoring loop.

        This runs continuously, displaying status and handling alerts.
        Call this from your main application loop.
        """
        print("\n" + "=" * 60)
        print("SignalSight GPS Traffic Light Monitor")
        print("=" * 60)
        print("Press Ctrl+C to stop\n")

        last_display = 0
        display_interval = 1.0  # Update display every second

        try:
            while True:
                current_time = time.time()

                # Update display periodically
                if current_time - last_display >= display_interval:
                    self._display_status()
                    last_display = current_time

                # Check for imminent alerts
                closest = self.gps_system.get_closest_light()
                if closest and closest.distance <= self.ALERT_NEAR:
                    # Here you would integrate with YOLO system
                    # For example: yolo_system.prioritize_traffic_lights()
                    pass

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")

    def _display_status(self):
        """Display current status to console."""
        position = self.gps_system.get_current_position()
        closest = self.gps_system.get_closest_light()
        nearby = self.gps_system.get_nearby_lights()
        stats = self.gps_system.get_stats()

        # Clear line and print status
        print("\r" + " " * 80, end="\r")

        if not position:
            print("Waiting for GPS fix...", end="", flush=True)
            return

        # Format position
        pos_str = f"Pos: {position.latitude:.6f}, {position.longitude:.6f}"

        # Format speed if available
        speed_str = ""
        if position.speed is not None:
            speed_kmh = position.speed * 3.6
            speed_str = f" | {speed_kmh:.1f} km/h"

        # Format nearest light
        light_str = ""
        if closest:
            zone = self.gps_system._get_distance_zone(closest.distance)
            light_str = f" | Light: {closest.distance:.0f}m [{zone}]"
        else:
            light_str = " | No lights nearby"

        # Satellites
        sat_str = f" | Sats: {position.satellites}"

        status = f"{pos_str}{speed_str}{light_str}{sat_str}"
        print(status, end="", flush=True)

    def get_traffic_light_distance(self) -> float:
        """
        Get distance to nearest traffic light.

        Use this method from your main SignalSight application.

        Returns:
            Distance in meters, or float('inf') if no light nearby
        """
        closest = self.gps_system.get_closest_light()
        return closest.distance if closest else float('inf')

    def is_near_traffic_light(self, threshold_m: float = 100) -> bool:
        """
        Check if currently near a traffic light.

        Args:
            threshold_m: Distance threshold in meters

        Returns:
            True if within threshold of a traffic light
        """
        return self.gps_system.is_approaching_light(threshold_m)


class SimulatedGPSIntegration(SignalSightGPSIntegration):
    """
    Simulated GPS integration for testing without hardware.

    Generates fake GPS coordinates and simulates approaching traffic lights.
    """

    def __init__(self, db_path: str = 'data/traffic_lights.db'):
        """Initialize simulation mode."""
        self.db_path = db_path
        self._db = None
        self._running = False
        self._simulated_position = None
        self._nearby_lights = []

        # Simulation parameters
        self._speed_mps = 10.0  # 36 km/h
        self._heading = 0  # degrees

        self._last_zone = None
        self._last_alert_time = 0
        self._alert_cooldown = 2.0

        logger.info("Simulated GPS Integration initialized")

    def start(self) -> bool:
        """Start simulation."""
        try:
            self._db = TrafficLightDB(self.db_path)
            stats = self._db.get_stats()

            # Start in Barrhaven, Ottawa, Ontario
            self._simulated_position = {
                'lat': 45.2751,
                'lon': -75.7545
            }

            self._running = True
            logger.info("Simulation started")
            logger.info(f"Starting position: {self._simulated_position}")
            return True

        except Exception as e:
            logger.error(f"Failed to start simulation: {e}")
            return False

    def stop(self):
        """Stop simulation."""
        self._running = False
        if self._db:
            self._db.close()
        logger.info("Simulation stopped")

    def run_monitoring_loop(self):
        """Run simulated monitoring loop."""
        print("\n" + "=" * 60)
        print("SignalSight GPS Simulation Mode")
        print("=" * 60)
        print("Simulating driving through traffic lights")
        print("Press Ctrl+C to stop\n")

        last_update = time.time()

        try:
            while self._running:
                current_time = time.time()
                dt = current_time - last_update
                last_update = current_time

                # Update simulated position
                self._update_simulation(dt)

                # Query database (with heading filtering to track only lights ahead)
                lights = self._db.get_nearby_lights_fast(
                    self._simulated_position['lat'],
                    self._simulated_position['lon'],
                    500,
                    heading=self._heading,
                    heading_cone=90.0
                )
                self._nearby_lights = lights

                # Display status
                self._display_simulation_status()

                # Check alerts
                if lights:
                    closest = lights[0]
                    zone = self._get_zone(closest.distance)

                    if zone in ['imminent', 'near'] and zone != self._last_zone:
                        self._trigger_driver_alert(ProximityAlert(
                            light_id=closest.id,
                            distance_m=closest.distance,
                            lat=closest.lat,
                            lon=closest.lon,
                            zone=zone
                        ))

                    self._last_zone = zone

                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n\nSimulation stopped by user")

    def _update_simulation(self, dt: float):
        """Update simulated position."""
        import math

        # Move in current heading direction
        # 1 degree lat ≈ 111km, 1 degree lon ≈ 111km * cos(lat)
        lat_change = (self._speed_mps * dt / 111320) * math.cos(
            math.radians(self._heading)
        )
        lon_change = (self._speed_mps * dt / 111320) * math.sin(
            math.radians(self._heading)
        ) / math.cos(math.radians(self._simulated_position['lat']))

        self._simulated_position['lat'] += lat_change
        self._simulated_position['lon'] += lon_change

        # Randomly adjust heading occasionally
        if random.random() < 0.05:
            self._heading += random.uniform(-15, 15)
            self._heading = self._heading % 360

    def _get_zone(self, distance: float) -> str:
        """Get zone name for distance."""
        if distance <= 50:
            return 'imminent'
        elif distance <= 100:
            return 'near'
        elif distance <= 250:
            return 'approaching'
        else:
            return 'far'

    def _display_simulation_status(self):
        """Display simulation status."""
        print("\r" + " " * 80, end="\r")

        lat = self._simulated_position['lat']
        lon = self._simulated_position['lon']
        speed_kmh = self._speed_mps * 3.6

        if self._nearby_lights:
            closest = self._nearby_lights[0]
            zone = self._get_zone(closest.distance)
            status = (f"Pos: {lat:.6f}, {lon:.6f} | {speed_kmh:.0f} km/h | "
                     f"Light: {closest.distance:.0f}m [{zone}] | "
                     f"Total nearby: {len(self._nearby_lights)}")
        else:
            status = (f"Pos: {lat:.6f}, {lon:.6f} | {speed_kmh:.0f} km/h | "
                     f"No lights nearby")

        print(status, end="", flush=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='SignalSight GPS Traffic Light Integration Example'
    )
    parser.add_argument(
        '--db',
        default='data/traffic_lights.db',
        help='Path to traffic light database'
    )
    parser.add_argument(
        '--gps-port',
        default='/dev/ttyUSB0',
        help='GPS serial port'
    )
    parser.add_argument(
        '--arduino-port',
        default=None,
        help='Arduino serial port'
    )
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Run in simulation mode (no hardware required)'
    )

    args = parser.parse_args()

    # Check database exists
    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database not found: {args.db}")
        logger.error("Run database_setup.py first to create the database.")
        sys.exit(1)

    # Create integration
    if args.simulate:
        integration = SimulatedGPSIntegration(db_path=args.db)
    else:
        integration = SignalSightGPSIntegration(
            db_path=args.db,
            gps_port=args.gps_port,
            arduino_port=args.arduino_port
        )

    # Start and run
    if integration.start():
        try:
            integration.run_monitoring_loop()
        finally:
            integration.stop()
    else:
        logger.error("Failed to start integration")
        sys.exit(1)


if __name__ == "__main__":
    main()
