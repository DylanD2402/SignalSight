"""
GPS Library for Robot Framework Testing

This library provides keywords for testing GPS module functionality
including connection, data reception, parsing, and validation.

Usage:
    Library    GPSLibrary.py

Keywords provided:
    - Connect To GPSD
    - Disconnect From GPSD
    - Get GPS Report
    - Get GPS Report Types
    - Verify Report Structure
    - Convert Speed MS To KMH
    - Format Coordinate
    - Get Satellite Data
    - Get Position Data
    - Check Device Path
"""

import time
import signal
from gps import gps, WATCH_ENABLE, WATCH_DISABLE
from robot.api.deco import keyword
from robot.api import logger


class TimeoutException(Exception):
    """Exception raised when operation times out"""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutException("Operation timed out")


class GPSLibrary:
    """Robot Framework library for GPS testing"""

    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    ROBOT_LIBRARY_VERSION = '1.0.0'

    def __init__(self):
        """Initialize GPS Library"""
        self.session = None
        self.connected = False
        logger.info("GPS Library initialized")

    @keyword("Connect To GPSD")
    def connect_to_gpsd(self):
        """
        Connect to GPSD daemon.

        Returns:
            True if connection successful

        Example:
            | Connect To GPSD |
        """
        try:
            self.session = gps(mode=WATCH_ENABLE)
            self.connected = True
            logger.info("Successfully connected to GPSD")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to GPSD: {e}")
            raise Exception(f"GPSD connection failed: {e}")

    @keyword("Disconnect From GPSD")
    def disconnect_from_gpsd(self):
        """
        Disconnect from GPSD daemon.

        Example:
            | Disconnect From GPSD |
        """
        if self.session:
            try:
                self.session = gps(mode=WATCH_DISABLE)
                self.connected = False
                logger.info("Disconnected from GPSD")
            except Exception as e:
                logger.warn(f"Error during disconnect: {e}")
        else:
            logger.warn("No active GPS session to disconnect")

    @keyword("GPSD Should Be Connected")
    def gpsd_should_be_connected(self):
        """
        Verify that GPSD connection is active.

        Raises:
            AssertionError if not connected

        Example:
            | GPSD Should Be Connected |
        """
        if not self.connected or not self.session:
            raise AssertionError("Not connected to GPSD")
        logger.info("GPSD connection verified")

    @keyword("Get GPS Report")
    def get_gps_report(self, timeout=10):
        """
        Get next GPS report from GPSD.

        Args:
            timeout: Maximum wait time in seconds (default: 10)

        Returns:
            GPS report dictionary or None if timeout

        Example:
            | ${report}= | Get GPS Report | timeout=5 |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info(f"Getting GPS report with {timeout}s timeout")
        report = self._get_report_with_timeout(int(timeout))

        if report:
            logger.info(f"Received GPS report: class={report.get('class', 'unknown')}")
            return report
        else:
            logger.warn(f"No GPS report received within {timeout}s timeout")
            return None

    def _get_report_with_timeout(self, timeout_seconds):
        """
        Internal method to get GPS report with timeout.

        Args:
            timeout_seconds: Maximum time to wait

        Returns:
            GPS report or None if timeout
        """
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)

        try:
            report = self.session.next()
            signal.alarm(0)  # Cancel alarm
            return report
        except TimeoutException:
            signal.alarm(0)  # Cancel alarm
            return None
        except Exception as e:
            signal.alarm(0)  # Cancel alarm
            raise e

    @keyword("Get GPS Report Types")
    def get_gps_report_types(self, timeout=10):
        """
        Collect GPS report types received within timeout period.

        Args:
            timeout: Maximum wait time in seconds (default: 10)

        Returns:
            List of report type strings (e.g., ['TPV', 'SKY', 'VERSION'])

        Example:
            | ${types}= | Get GPS Report Types | timeout=15 |
            | Should Contain | ${types} | TPV |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info(f"Collecting GPS report types for {timeout}s")
        received_types = set()
        timeout_time = time.time() + int(timeout)

        while time.time() < timeout_time:
            report = self._get_report_with_timeout(2)
            if report and 'class' in report:
                received_types.add(report['class'])

        result = list(received_types)
        logger.info(f"Received report types: {result}")
        return result

    @keyword("Report Should Have Class Field")
    def report_should_have_class_field(self, report):
        """
        Verify that GPS report has 'class' field.

        Args:
            report: GPS report dictionary

        Raises:
            AssertionError if class field missing

        Example:
            | ${report}= | Get GPS Report |
            | Report Should Have Class Field | ${report} |
        """
        if not report:
            raise AssertionError("Report is None or empty")
        if 'class' not in report:
            raise AssertionError("Report does not have 'class' field")
        logger.info(f"Report has class field: {report['class']}")

    @keyword("Get Report Of Type")
    def get_report_of_type(self, report_type, timeout=10):
        """
        Get a GPS report of specific type (TPV, SKY, etc).

        Args:
            report_type: Type of report to get (e.g., 'TPV', 'SKY')
            timeout: Maximum wait time in seconds (default: 10)

        Returns:
            GPS report of specified type or None

        Example:
            | ${tpv}= | Get Report Of Type | TPV | timeout=15 |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info(f"Getting {report_type} report with {timeout}s timeout")
        timeout_time = time.time() + int(timeout)

        while time.time() < timeout_time:
            report = self._get_report_with_timeout(2)
            if report and report.get('class') == report_type:
                logger.info(f"Found {report_type} report")
                return report

        logger.warn(f"No {report_type} report found within {timeout}s")
        return None

    @keyword("Convert Speed MS To KMH")
    def convert_speed_ms_to_kmh(self, speed_ms):
        """
        Convert speed from meters/second to kilometers/hour.

        Args:
            speed_ms: Speed in meters per second

        Returns:
            Speed in kilometers per hour

        Example:
            | ${kmh}= | Convert Speed MS To KMH | 10 |
            | Should Be Equal | ${kmh} | ${36.0} |
        """
        speed_float = float(speed_ms)
        kmh = speed_float * 3.6
        logger.info(f"Converted {speed_ms} m/s to {kmh} km/h")
        return kmh

    @keyword("Convert Speed MS To MPH")
    def convert_speed_ms_to_mph(self, speed_ms):
        """
        Convert speed from meters/second to miles/hour.

        Args:
            speed_ms: Speed in meters per second

        Returns:
            Speed in miles per hour

        Example:
            | ${mph}= | Convert Speed MS To MPH | 10 |
        """
        speed_float = float(speed_ms)
        mph = speed_float * 2.23694
        logger.info(f"Converted {speed_ms} m/s to {mph} mph")
        return mph

    @keyword("Format Coordinate")
    def format_coordinate(self, coordinate, decimal_places=6):
        """
        Format coordinate to specified decimal places.

        Args:
            coordinate: Coordinate value
            decimal_places: Number of decimal places (default: 6)

        Returns:
            Formatted coordinate string

        Example:
            | ${formatted}= | Format Coordinate | 40.7128 | 6 |
        """
        coord_float = float(coordinate)
        formatted = f"{coord_float:.{decimal_places}f}"
        logger.info(f"Formatted coordinate: {formatted}")
        return formatted

    @keyword("Get Satellite Data")
    def get_satellite_data(self, timeout=15):
        """
        Get satellite data from SKY report.

        Args:
            timeout: Maximum wait time in seconds (default: 15)

        Returns:
            Dictionary with 'total' and 'used' satellite counts, or None

        Example:
            | ${sats}= | Get Satellite Data | timeout=20 |
            | Log | Total: ${sats['total']}, Used: ${sats['used']} |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info("Getting satellite data")
        timeout_time = time.time() + int(timeout)

        while time.time() < timeout_time:
            report = self._get_report_with_timeout(2)
            if report and report.get('class') == 'SKY' and hasattr(report, 'satellites'):
                satellites = report.satellites
                sat_count = len(satellites)
                used_count = sum(1 for sat in satellites if hasattr(sat, 'used') and sat.used)

                result = {'total': sat_count, 'used': used_count}
                logger.info(f"Satellite data: {result}")
                return result

        logger.warn(f"No satellite data found within {timeout}s")
        return None

    @keyword("Get Position Data")
    def get_position_data(self, timeout=15):
        """
        Get position data (lat/lon/alt) from TPV report.

        Args:
            timeout: Maximum wait time in seconds (default: 15)

        Returns:
            Dictionary with 'lat', 'lon', 'alt' or None if no fix

        Example:
            | ${pos}= | Get Position Data | timeout=20 |
            | Log | Lat: ${pos['lat']}, Lon: ${pos['lon']} |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info("Getting position data")
        timeout_time = time.time() + int(timeout)

        while time.time() < timeout_time:
            report = self._get_report_with_timeout(2)
            if report and report.get('class') == 'TPV':
                if hasattr(report, 'lat') and hasattr(report, 'lon'):
                    result = {
                        'lat': report.lat,
                        'lon': report.lon,
                        'alt': report.alt if hasattr(report, 'alt') else None
                    }
                    logger.info(f"Position data: lat={result['lat']}, lon={result['lon']}")
                    return result

        logger.warn(f"No position fix found within {timeout}s")
        return None

    @keyword("Get GPS Mode")
    def get_gps_mode(self, timeout=10):
        """
        Get GPS fix mode from TPV report.

        GPS Modes:
            0 = No mode value seen yet
            1 = No fix
            2 = 2D fix (lat/lon only)
            3 = 3D fix (lat/lon/alt)

        Args:
            timeout: Maximum wait time in seconds (default: 10)

        Returns:
            GPS mode integer (0-3)

        Example:
            | ${mode}= | Get GPS Mode |
            | Should Be Equal | ${mode} | ${1} |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info("Getting GPS mode")
        timeout_time = time.time() + int(timeout)

        while time.time() < timeout_time:
            report = self._get_report_with_timeout(2)
            if report and report.get('class') == 'TPV':
                mode = report.get('mode', 0)
                logger.info(f"GPS mode: {mode}")
                return mode

        logger.warn(f"No GPS mode found within {timeout}s")
        return 0

    @keyword("Get Device Path")
    def get_device_path(self, timeout=10):
        """
        Get GPS device path from report.

        Args:
            timeout: Maximum wait time in seconds (default: 10)

        Returns:
            Device path string (e.g., '/dev/gps0') or None

        Example:
            | ${device}= | Get Device Path |
            | Should Start With | ${device} | /dev/ |
        """
        if not self.connected:
            raise Exception("Not connected to GPSD")

        logger.info("Getting device path")
        timeout_time = time.time() + int(timeout)

        while time.time() < timeout_time:
            report = self._get_report_with_timeout(2)
            if report and report.get('class') in ['TPV', 'SKY']:
                if 'device' in report:
                    device_path = report['device']
                    logger.info(f"Device path: {device_path}")
                    return device_path

        logger.warn(f"No device path found within {timeout}s")
        return None

    @keyword("Coordinate Should Be Valid")
    def coordinate_should_be_valid(self, coordinate, coord_type='latitude'):
        """
        Verify that coordinate is within valid range.

        Args:
            coordinate: Coordinate value to validate
            coord_type: 'latitude' or 'longitude' (default: 'latitude')

        Raises:
            AssertionError if coordinate out of range

        Example:
            | Coordinate Should Be Valid | 40.7128 | latitude |
            | Coordinate Should Be Valid | -74.0060 | longitude |
        """
        coord_float = float(coordinate)

        if coord_type.lower() == 'latitude':
            if coord_float < -90 or coord_float > 90:
                raise AssertionError(f"Latitude {coord_float} out of range (-90 to 90)")
        elif coord_type.lower() == 'longitude':
            if coord_float < -180 or coord_float > 180:
                raise AssertionError(f"Longitude {coord_float} out of range (-180 to 180)")
        else:
            raise ValueError(f"Invalid coord_type: {coord_type}. Must be 'latitude' or 'longitude'")

        logger.info(f"{coord_type.capitalize()} {coord_float} is valid")
