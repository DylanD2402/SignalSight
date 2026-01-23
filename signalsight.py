#!/usr/bin/env python3
"""
SignalSight - Integrated Traffic Light Detection System
Combines Computer Vision and GPS for comprehensive driver assistance

This integration code acts as glue between CV detection and GPS proximity,
coordinating their execution and managing Arduino communication.
"""

import sys
import os
import time
import threading
import queue
import argparse
import signal
from typing import Optional, Callable
from dataclasses import dataclass

# Add module paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'YOLO_Detection_Model/CNN'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'GPS'))

try:
    import serial
except ImportError:
    serial = None


@dataclass
class SystemState:
    """Combined system state."""
    cv_state: str = "IDLE"
    cv_confidence: float = 0.0
    cv_fps: float = 0.0
    gps_distance: int = 0  # meters
    gps_speed: int = 0  # km/h
    gps_satellites: int = 0
    gps_nearby_lights: int = 0
    gps_has_fix: bool = False
    arduino_connected: bool = False
    timestamp: float = 0.0


class ArduinoInterface:
    """Centralized Arduino serial communication handler."""

    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 115200, no_arduino: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.no_arduino = no_arduino
        self.ser = None
        self.lock = threading.Lock()
        self.connected = False

        if not no_arduino:
            self._connect()

    def _connect(self):
        """Attempt to connect to Arduino."""
        if serial is None:
            print("WARNING: pyserial not installed - Arduino communication disabled")
            return

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            self.connected = True
            print(f"Arduino connected on {self.port}")
        except Exception as e:
            self.connected = False
            self.ser = None
            print(f"WARNING: Arduino not connected: {e}")
            print("   Running in no-data-send mode")

    def send_state(self, state: str, distance: int = 0, speed: int = 0) -> bool:
        """
        Send state to Arduino. Thread-safe.

        Format: STATE,DISTANCE,SPEED\n
        Example: ACTIVE_RED,45,60\n
        """
        if not self.connected or self.ser is None or self.no_arduino:
            return False

        with self.lock:
            try:
                message = f"{state},{distance},{speed}\n"
                self.ser.write(message.encode('utf-8'))
                self.ser.flush()
                return True
            except Exception as e:
                print(f"WARNING: Arduino communication error: {e}")
                self.connected = False
                return False

    def close(self):
        """Close serial connection."""
        if self.ser is not None:
            with self.lock:
                try:
                    self.ser.close()
                except:
                    pass


class CVModule:
    """Wrapper for CV detection module (cnn_system.py)."""

    def __init__(self, state_queue: queue.Queue, debug: bool = False):
        self.state_queue = state_queue
        self.debug = debug
        self.thread = None
        self.stop_event = threading.Event()

    def start(self):
        """Start CV detection in a thread."""
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True, name="CV-Module")
        self.thread.start()

    def _cv_callback(self, cv_data):
        """Callback function called by cnn_system.py with detection results."""
        try:
            self.state_queue.put_nowait({
                'type': 'CV',
                'state': cv_data['state'],
                'confidence': cv_data['confidence'],
                'fps': cv_data['fps']
            })
        except queue.Full:
            pass

    def _run(self):
        """Run CV detection by importing and calling cnn_system.py."""
        try:
            # Save current directory
            original_dir = os.getcwd()

            # Change to CV module directory
            os.chdir(os.path.join(SCRIPT_DIR, 'YOLO_Detection_Model/CNN'))

            # Import the actual CV module
            sys.path.insert(0, os.getcwd())
            import cnn_system

            if self.debug:
                print("CV Module started (using cnn_system.py)")

            # Call the actual function from cnn_system.py
            cnn_system.live_traffic_light_detection(
                state_callback=self._cv_callback,
                no_arduino=True,  # Integration handles Arduino
                no_display=True,  # Integration handles display
                stop_event=self.stop_event
            )

            # Restore directory
            os.chdir(original_dir)

        except Exception as e:
            print(f"ERROR: CV Module Error: {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        """Stop CV module."""
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)


class GPSModule:
    """Wrapper for GPS proximity detection using gps_system.py."""

    def __init__(self, state_queue: queue.Queue, debug: bool = False):
        self.state_queue = state_queue
        self.debug = debug
        self.gps_system = None

    def start(self):
        """Start GPS detection by importing and running gps_system.py."""
        try:
            # Save current directory
            original_dir = os.getcwd()

            # Change to GPS module directory
            os.chdir(os.path.join(SCRIPT_DIR, 'GPS'))

            # Import the actual GPS modules
            sys.path.insert(0, os.getcwd())
            from gps_system import GPSTrafficLightSystem
            import logging

            # Suppress GPS system logging (integration handles display)
            logging.disable(logging.CRITICAL)

            GPS_PORT = "/dev/gps0"
            GPS_BAUDRATE = 9600
            PROXIMITY_THRESHOLD = 100  # meters
            DB_PATH = "data/traffic_lights.db"

            # Create GPS system (no Arduino - integration handles it)
            self.gps_system = GPSTrafficLightSystem(
                gps_port=GPS_PORT,
                gps_baudrate=GPS_BAUDRATE,
                db_path=DB_PATH,
                arduino_port=None,  # Integration layer handles Arduino
                query_interval=0.5,  # 2Hz updates
                search_radius=PROXIMITY_THRESHOLD
            )

            # Set up callback to push GPS data to state queue
            def on_position_update(position):
                """Callback called by GPSTrafficLightSystem on position updates."""
                # Get closest light
                closest = self.gps_system.get_closest_light()
                nearby = self.gps_system.get_nearby_lights()

                # Calculate speed in km/h
                speed_kmh = 0
                if position.speed is not None:
                    speed_kmh = int(round(position.speed * 3.6))

                # Calculate distance in meters
                distance_m = 0
                if closest:
                    distance_m = int(round(closest.distance))

                # Send to queue
                try:
                    self.state_queue.put_nowait({
                        'type': 'GPS',
                        'distance': distance_m,
                        'speed': speed_kmh,
                        'satellites': position.satellites,
                        'nearby_lights': len(nearby),
                        'has_fix': position.fix_quality > 0
                    })
                except queue.Full:
                    pass

            self.gps_system.set_position_callback(on_position_update)

            # Start the GPS system (it manages its own threads)
            if self.gps_system.start():
                if self.debug:
                    print("GPS Module started (using gps_system.py)")
            else:
                print("WARNING: GPS Module failed to start")

            # Restore directory
            os.chdir(original_dir)

        except Exception as e:
            print(f"ERROR: GPS Module Error: {e}")
            import traceback
            traceback.print_exc()

    def stop(self):
        """Stop GPS module."""
        if self.gps_system:
            self.gps_system.stop()


class SignalSight:
    """Main SignalSight system coordinator."""

    def __init__(self, debug: bool = False, arduino_port: str = "/dev/ttyACM0", no_arduino: bool = False):
        self.debug = debug
        self.running = False
        self.state_queue = queue.Queue(maxsize=100)
        self.system_state = SystemState()

        # Arduino interface
        self.arduino = ArduinoInterface(arduino_port, no_arduino=no_arduino)
        self.system_state.arduino_connected = self.arduino.connected

        # Modules
        self.cv_module = CVModule(self.state_queue, debug)
        self.gps_module = GPSModule(self.state_queue, debug)

        # Signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\n\nShutting down SignalSight...")
        self.stop()
        sys.exit(0)

    def start(self):
        """Start the SignalSight system."""
        print("=" * 60)
        print("SignalSight - Integrated Traffic Light Detection System")
        print("=" * 60)
        print(f"Debug Mode: {'ON' if self.debug else 'OFF'}")
        print(f"Arduino: {'Connected' if self.arduino.connected else 'Not Connected (no-data-send mode)'}")
        print()

        self.running = True

        # Start modules
        self.cv_module.start()
        self.gps_module.start()

        if self.debug:
            print()
            print("=" * 60)
            print("LIVE STATUS (Ctrl+C to stop)")
            print("=" * 60)
            print()  # CV line
            print()  # GPS line

        # Main coordination loop
        self._coordination_loop()

    def _coordination_loop(self):
        """Main loop - processes states and sends to Arduino."""
        while self.running:
            try:
                # Get state updates
                try:
                    update = self.state_queue.get(timeout=0.1)

                    if update['type'] == 'CV':
                        self.system_state.cv_state = update['state']
                        self.system_state.cv_confidence = update['confidence']
                        self.system_state.cv_fps = update['fps']
                    elif update['type'] == 'GPS':
                        self.system_state.gps_distance = update['distance']
                        self.system_state.gps_speed = update['speed']
                        self.system_state.gps_satellites = update['satellites']
                        self.system_state.gps_nearby_lights = update['nearby_lights']
                        self.system_state.gps_has_fix = update['has_fix']

                    self.system_state.timestamp = time.time()

                except queue.Empty:
                    pass

                # Send to Arduino (CV state takes priority)
                if self.arduino.send_state(
                    self.system_state.cv_state,
                    self.system_state.gps_distance,
                    self.system_state.gps_speed
                ):
                    if not self.debug:
                        print(f"[{time.strftime('%H:%M:%S')}] → Arduino: "
                              f"{self.system_state.cv_state},{self.system_state.gps_distance}m,"
                              f"{self.system_state.gps_speed}km/h")

                # Debug display
                if self.debug:
                    self._update_debug_display()

                time.sleep(0.05)  # 20Hz update rate

            except KeyboardInterrupt:
                break

    def _update_debug_display(self):
        """Update debug display."""
        CURSOR_UP = '\033[F'
        CLEAR_LINE = '\033[K'

        cv_line = self._format_cv_status()
        gps_line = self._format_gps_status()

        sys.stdout.write(f"{CURSOR_UP}{CURSOR_UP}")
        sys.stdout.write(f"{CLEAR_LINE}{cv_line}\n")
        sys.stdout.write(f"{CLEAR_LINE}{gps_line}\n")
        sys.stdout.flush()

    def _format_cv_status(self) -> str:
        """Format CV status line."""
        state_str = self.system_state.cv_state.replace("ACTIVE_", "")

        arduino_str = f"{self.system_state.cv_state},{self.system_state.gps_distance}m,{self.system_state.gps_speed}km/h"
        if not self.arduino.connected:
            arduino_str = "NOT CONNECTED"

        return (f"CV:  {state_str:12s} | "
                f"Conf: {self.system_state.cv_confidence:.2f} | "
                f"FPS: {self.system_state.cv_fps:.1f} | "
                f"Arduino: {arduino_str}")

    def _format_gps_status(self) -> str:
        """Format GPS status line."""
        if not self.system_state.gps_has_fix:
            return f"GPS: NO FIX | Satellites: {self.system_state.gps_satellites} | Speed: 0 km/h"

        return (f"GPS: FIX | "
                f"Sats: {self.system_state.gps_satellites} | "
                f"Nearby: {self.system_state.gps_nearby_lights} | "
                f"Closest: {self.system_state.gps_distance:>4d}m | "
                f"Speed: {self.system_state.gps_speed:>3d} km/h")

    def stop(self):
        """Stop the system."""
        self.running = False
        self.cv_module.stop()
        self.gps_module.stop()
        self.arduino.close()
        print("\nSignalSight stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SignalSight - Integrated Traffic Light Detection System"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with live status updates"
    )
    parser.add_argument(
        "--arduino-port",
        default="/dev/ttyACM0",
        help="Arduino serial port (default: /dev/ttyACM0)"
    )
    parser.add_argument(
        "--no-arduino",
        action="store_true",
        help="Run without Arduino (no data sending)"
    )

    args = parser.parse_args()

    # Create and start system
    system = SignalSight(
        debug=args.debug,
        arduino_port=args.arduino_port,
        no_arduino=args.no_arduino
    )

    try:
        system.start()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        system.stop()


if __name__ == "__main__":
    main()
