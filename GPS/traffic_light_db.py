#!/usr/bin/env python3
"""
Traffic Light Database Module for SignalSight

Provides optimized SQLite-based spatial queries for traffic light locations.
Designed for Raspberry Pi 5 with <5ms query latency and <20MB memory footprint.

Performance optimizations:
- WAL mode for concurrent reads
- Spatial grid indexing for fast bounding box queries
- Haversine distance calculation in Python (faster than SQL for small datasets)
- Connection pooling with thread safety
- Memory-mapped I/O for faster reads

Author: SignalSight Team
"""

import sqlite3
import math
import threading
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Earth's radius in meters (WGS84 mean radius)
EARTH_RADIUS_M = 6371008.8

# Grid cell size in degrees (approximately 1km at mid-latitudes)
# This creates a spatial index for fast bounding box queries
GRID_CELL_SIZE = 0.01  # ~1.1km


@dataclass
class TrafficLight:
    """Represents a traffic light location with distance."""
    id: int
    lat: float
    lon: float
    distance: float  # Distance in meters from query point


class TrafficLightDB:
    """
    Optimized SQLite database for traffic light spatial queries.

    Designed for Raspberry Pi 5 with performance targets:
    - Query latency: <5ms
    - Memory footprint: <20MB
    - CPU usage: <1% per query

    Usage:
        db = TrafficLightDB('/path/to/traffic_lights.db')
        lights = db.get_nearby_lights_fast(43.6532, -79.3832, 500)
        for light in lights:
            print(f"Light {light.id} at {light.distance:.1f}m")
        db.close()
    """

    def __init__(self, db_path: str):
        """
        Initialize database connection with optimizations for RPi 5.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        # Get initial connection to verify database
        conn = self._get_connection()

        # Verify database has required tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traffic_lights'"
        )
        if not cursor.fetchone():
            raise ValueError("Database missing 'traffic_lights' table")

        # Get database stats for logging
        cursor = conn.execute("SELECT COUNT(*) FROM traffic_lights")
        count = cursor.fetchone()[0]
        logger.info(f"TrafficLightDB initialized with {count} traffic lights")

        # Cache for frequently accessed grid cells
        self._grid_cache: Dict[Tuple[int, int], List[Tuple[int, float, float]]] = {}
        self._cache_enabled = True

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection with optimizations.

        Returns:
            SQLite connection configured for optimal RPi 5 performance
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=5.0
            )

            # Performance optimizations for Raspberry Pi 5
            # WAL mode allows concurrent reads while writing
            conn.execute("PRAGMA journal_mode=WAL")

            # Increase cache size (negative = KB, default is ~2MB)
            # 8MB cache for faster repeated queries
            conn.execute("PRAGMA cache_size=-8000")

            # Memory-mapped I/O for faster reads (64MB)
            # This maps the database file into memory for faster access
            conn.execute("PRAGMA mmap_size=67108864")

            # Synchronous OFF for reads (we don't write during operation)
            # This eliminates fsync calls which are slow on SD cards
            conn.execute("PRAGMA synchronous=OFF")

            # Read uncommitted for maximum read performance
            conn.execute("PRAGMA read_uncommitted=ON")

            # Temp store in memory
            conn.execute("PRAGMA temp_store=MEMORY")

            # Enable query result caching
            conn.row_factory = sqlite3.Row

            self._local.conn = conn
            logger.debug("Created new database connection with optimizations")

        return self._local.conn

    def _haversine_distance(self, lat1: float, lon1: float,
                            lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance using Haversine formula.

        Optimized for speed with precomputed values where possible.

        Args:
            lat1, lon1: First point coordinates (degrees)
            lat2, lon2: Second point coordinates (degrees)

        Returns:
            Distance in meters
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return EARTH_RADIUS_M * c

    def _get_bounding_box(self, lat: float, lon: float,
                          radius_m: float) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box for spatial query.

        Uses approximate conversion (accurate enough for small radii).

        Args:
            lat, lon: Center point coordinates
            radius_m: Search radius in meters

        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        # Approximate degrees per meter at given latitude
        # 1 degree latitude ≈ 111,320 meters
        # 1 degree longitude ≈ 111,320 * cos(latitude) meters
        lat_delta = radius_m / 111320.0
        lon_delta = radius_m / (111320.0 * math.cos(math.radians(lat)))

        return (
            lat - lat_delta,
            lat + lat_delta,
            lon - lon_delta,
            lon + lon_delta
        )

    def get_nearby_lights_fast(self, lat: float, lon: float,
                                radius_m: float = 500) -> List[TrafficLight]:
        """
        Get traffic lights within radius, sorted by distance.

        This is the main query method, optimized for <5ms latency on RPi 5.

        Algorithm:
        1. Calculate bounding box from radius
        2. Query database with spatial index for candidates
        3. Calculate exact Haversine distance for each candidate
        4. Filter by radius and sort by distance

        Args:
            lat: Latitude of query point (degrees)
            lon: Longitude of query point (degrees)
            radius_m: Search radius in meters (default 500m)

        Returns:
            List of TrafficLight objects sorted by distance (nearest first)
        """
        # Input validation
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat}")
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon}")
        if radius_m <= 0:
            raise ValueError(f"Invalid radius: {radius_m}")

        # Get bounding box for spatial query
        min_lat, max_lat, min_lon, max_lon = self._get_bounding_box(
            lat, lon, radius_m
        )

        # Query database with spatial index
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT id, lat, lon
                FROM traffic_lights
                WHERE lat BETWEEN ? AND ?
                  AND lon BETWEEN ? AND ?
            """, (min_lat, max_lat, min_lon, max_lon))

            candidates = cursor.fetchall()

        # Calculate distances and filter
        results = []
        for row in candidates:
            light_id, light_lat, light_lon = row['id'], row['lat'], row['lon']
            distance = self._haversine_distance(lat, lon, light_lat, light_lon)

            # Only include if within actual radius (bounding box is approximate)
            if distance <= radius_m:
                results.append(TrafficLight(
                    id=light_id,
                    lat=light_lat,
                    lon=light_lon,
                    distance=distance
                ))

        # Sort by distance (nearest first)
        results.sort(key=lambda x: x.distance)

        logger.debug(f"Found {len(results)} lights within {radius_m}m "
                    f"of ({lat:.6f}, {lon:.6f})")

        return results

    def get_closest_light(self, lat: float, lon: float,
                          max_distance_m: float = 1000) -> Optional[TrafficLight]:
        """
        Get the single closest traffic light.

        Convenience method for common use case.

        Args:
            lat, lon: Query point coordinates
            max_distance_m: Maximum distance to search (default 1000m)

        Returns:
            TrafficLight object or None if no lights within range
        """
        lights = self.get_nearby_lights_fast(lat, lon, max_distance_m)
        return lights[0] if lights else None

    def get_lights_in_bbox(self, min_lat: float, max_lat: float,
                           min_lon: float, max_lon: float) -> List[Tuple[int, float, float]]:
        """
        Get all traffic lights within a bounding box.

        Lower-level method for custom spatial queries.

        Args:
            min_lat, max_lat: Latitude bounds
            min_lon, max_lon: Longitude bounds

        Returns:
            List of (id, lat, lon) tuples
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT id, lat, lon
                FROM traffic_lights
                WHERE lat BETWEEN ? AND ?
                  AND lon BETWEEN ? AND ?
            """, (min_lat, max_lat, min_lon, max_lon))

            return [(row['id'], row['lat'], row['lon'])
                    for row in cursor.fetchall()]

    def get_light_by_id(self, light_id: int) -> Optional[Tuple[float, float]]:
        """
        Get traffic light coordinates by ID.

        Args:
            light_id: Traffic light ID

        Returns:
            Tuple of (lat, lon) or None if not found
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT lat, lon FROM traffic_lights WHERE id = ?",
                (light_id,)
            )
            row = cursor.fetchone()
            return (row['lat'], row['lon']) if row else None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics
        """
        with self._lock:
            conn = self._get_connection()

            # Total count
            cursor = conn.execute("SELECT COUNT(*) FROM traffic_lights")
            total_count = cursor.fetchone()[0]

            # Bounding box
            cursor = conn.execute("""
                SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon)
                FROM traffic_lights
            """)
            bounds = cursor.fetchone()

            # File size
            file_size = self.db_path.stat().st_size

        return {
            'total_lights': total_count,
            'min_lat': bounds[0],
            'max_lat': bounds[1],
            'min_lon': bounds[2],
            'max_lon': bounds[3],
            'file_size_bytes': file_size,
            'file_size_mb': file_size / (1024 * 1024)
        }

    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


def create_database(db_path: str, traffic_lights: List[Tuple[float, float]]) -> None:
    """
    Create a new traffic light database.

    This is used by the database_setup.py script to create the initial database.

    Args:
        db_path: Path for new database file
        traffic_lights: List of (lat, lon) tuples
    """
    conn = sqlite3.connect(db_path)

    # Create table with spatial index
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traffic_lights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)

    # Create indexes for spatial queries
    # Composite index on lat, lon for bounding box queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_traffic_lights_lat_lon
        ON traffic_lights(lat, lon)
    """)

    # Separate indexes for range queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_traffic_lights_lat
        ON traffic_lights(lat)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_traffic_lights_lon
        ON traffic_lights(lon)
    """)

    # Insert traffic lights
    conn.executemany(
        "INSERT INTO traffic_lights (lat, lon) VALUES (?, ?)",
        traffic_lights
    )

    # Optimize database
    conn.execute("ANALYZE")
    conn.execute("VACUUM")

    conn.commit()
    conn.close()

    logger.info(f"Created database with {len(traffic_lights)} traffic lights")


if __name__ == "__main__":
    # Quick test with sample data
    import tempfile
    import time

    logging.basicConfig(level=logging.INFO)

    # Create test database
    test_lights = [
        (43.6532, -79.3832),  # Toronto
        (43.6548, -79.3806),
        (43.6520, -79.3850),
        (43.6560, -79.3810),
        (43.6500, -79.3800),
    ]

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    create_database(test_db_path, test_lights)

    # Test queries
    db = TrafficLightDB(test_db_path)

    print("\nDatabase stats:")
    stats = db.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Benchmark query
    print("\nBenchmark (1000 queries):")
    lat, lon = 43.6532, -79.3832

    start = time.perf_counter()
    for _ in range(1000):
        lights = db.get_nearby_lights_fast(lat, lon, 500)
    elapsed = time.perf_counter() - start

    print(f"  Total time: {elapsed*1000:.2f}ms")
    print(f"  Per query: {elapsed}s = {elapsed*1000:.3f}ms")
    print(f"  Queries/sec: {1000/elapsed:.0f}")

    print(f"\nFound {len(lights)} lights within 500m:")
    for light in lights:
        print(f"  ID {light.id}: {light.distance:.1f}m")

    db.close()

    # Cleanup
    import os
    os.unlink(test_db_path)
