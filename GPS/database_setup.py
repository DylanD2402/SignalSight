#!/usr/bin/env python3
"""
Database Setup Script for SignalSight Traffic Light System

Downloads Ontario OpenStreetMap data and creates an optimized SQLite database
containing only traffic signal locations for fast spatial queries.

Usage:
    python database_setup.py [--region ontario] [--output traffic_lights.db]

Requirements:
    - osmium (pip install osmium)
    - requests
    - ~2GB free disk space for download (temporary)
    - ~50-100MB for final database

Author: SignalSight Team
"""

import os
import sys
import argparse
import logging
import time
import hashlib
import tempfile
import sqlite3
from pathlib import Path
from typing import List, Tuple

import requests
import osmium

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Geofabrik download URLs for Canadian provinces
GEOFABRIK_URLS = {
    'ontario': 'https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf',
    'quebec': 'https://download.geofabrik.de/north-america/canada/quebec-latest.osm.pbf',
    'british-columbia': 'https://download.geofabrik.de/north-america/canada/british-columbia-latest.osm.pbf',
    'alberta': 'https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf',
    'canada': 'https://download.geofabrik.de/north-america/canada-latest.osm.pbf',
}

# Default paths
DEFAULT_DB_NAME = 'traffic_lights.db'
DEFAULT_DATA_DIR = Path(__file__).parent / 'data'


class TrafficSignalHandler(osmium.SimpleHandler):
    """
    Osmium handler to extract traffic signal locations from OSM data.

    Extracts nodes tagged with highway=traffic_signals.
    """

    def __init__(self):
        super().__init__()
        self.traffic_lights: List[Tuple[float, float]] = []
        self.count = 0

    def node(self, n):
        """Process each node in the OSM file."""
        # Check if node is a traffic signal
        if 'highway' in n.tags and n.tags['highway'] == 'traffic_signals':
            self.traffic_lights.append((n.location.lat, n.location.lon))
            self.count += 1

            # Log progress every 10000 signals
            if self.count % 10000 == 0:
                logger.info(f"Processed {self.count} traffic signals...")


def download_osm_data(url: str, output_path: Path, chunk_size: int = 8192) -> bool:
    """
    Download OSM PBF file from Geofabrik with progress indication.

    Args:
        url: URL to download from
        output_path: Path to save file
        chunk_size: Download chunk size

    Returns:
        True if download successful
    """
    logger.info(f"Downloading OSM data from {url}")
    logger.info(f"This may take 10-30 minutes depending on connection speed...")

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_percent = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Show progress
                    if total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        if percent >= last_percent + 5:
                            mb_downloaded = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            logger.info(f"Download progress: {percent}% "
                                      f"({mb_downloaded:.1f}/{mb_total:.1f} MB)")
                            last_percent = percent

        logger.info(f"Download complete: {output_path}")
        return True

    except requests.RequestException as e:
        logger.error(f"Download failed: {e}")
        return False


def extract_traffic_signals(pbf_path: Path) -> List[Tuple[float, float]]:
    """
    Extract traffic signal locations from OSM PBF file.

    Args:
        pbf_path: Path to OSM PBF file

    Returns:
        List of (lat, lon) tuples
    """
    logger.info(f"Extracting traffic signals from {pbf_path}")
    logger.info("This may take 5-10 minutes...")

    start_time = time.time()

    handler = TrafficSignalHandler()
    handler.apply_file(str(pbf_path), locations=True)

    elapsed = time.time() - start_time

    logger.info(f"Extraction complete in {elapsed:.1f}s")
    logger.info(f"Found {len(handler.traffic_lights)} traffic signals")

    return handler.traffic_lights


def create_database(db_path: Path, traffic_lights: List[Tuple[float, float]]) -> None:
    """
    Create optimized SQLite database with traffic light locations.

    Args:
        db_path: Path for output database
        traffic_lights: List of (lat, lon) tuples
    """
    logger.info(f"Creating database at {db_path}")

    # Remove existing database
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))

    # Create table
    conn.execute("""
        CREATE TABLE traffic_lights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)

    # Insert data in batches for performance
    batch_size = 10000
    total = len(traffic_lights)

    for i in range(0, total, batch_size):
        batch = traffic_lights[i:i + batch_size]
        conn.executemany(
            "INSERT INTO traffic_lights (lat, lon) VALUES (?, ?)",
            batch
        )
        conn.commit()

        if i > 0 and i % 50000 == 0:
            logger.info(f"Inserted {i}/{total} records...")

    logger.info(f"Inserted all {total} traffic lights")

    # Create spatial indexes for fast queries
    logger.info("Creating spatial indexes...")

    # Composite index on (lat, lon) - primary index for bounding box queries
    conn.execute("""
        CREATE INDEX idx_traffic_lights_lat_lon
        ON traffic_lights(lat, lon)
    """)

    # Individual indexes for range queries
    conn.execute("""
        CREATE INDEX idx_traffic_lights_lat
        ON traffic_lights(lat)
    """)

    conn.execute("""
        CREATE INDEX idx_traffic_lights_lon
        ON traffic_lights(lon)
    """)

    # Analyze for query optimizer
    logger.info("Optimizing database...")
    conn.execute("ANALYZE")

    # Vacuum to reclaim space and optimize
    conn.execute("VACUUM")

    conn.commit()
    conn.close()

    # Report final size
    size_mb = db_path.stat().st_size / (1024 * 1024)
    logger.info(f"Database created: {size_mb:.2f} MB")


def validate_database(db_path: Path) -> bool:
    """
    Validate database and run performance benchmark.

    Args:
        db_path: Path to database

    Returns:
        True if validation passes
    """
    logger.info("Validating database...")

    conn = sqlite3.connect(str(db_path))

    # Check record count
    cursor = conn.execute("SELECT COUNT(*) FROM traffic_lights")
    count = cursor.fetchone()[0]
    logger.info(f"Total traffic lights: {count}")

    if count == 0:
        logger.error("Database is empty!")
        return False

    # Get bounds
    cursor = conn.execute("""
        SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon)
        FROM traffic_lights
    """)
    bounds = cursor.fetchone()
    logger.info(f"Latitude range: {bounds[0]:.4f} to {bounds[1]:.4f}")
    logger.info(f"Longitude range: {bounds[2]:.4f} to {bounds[3]:.4f}")

    # Get a sample point for benchmarking
    cursor = conn.execute("""
        SELECT lat, lon FROM traffic_lights
        ORDER BY RANDOM()
        LIMIT 1
    """)
    sample = cursor.fetchone()
    sample_lat, sample_lon = sample[0], sample[1]

    # Benchmark query performance
    logger.info("\nRunning performance benchmark...")

    # Warm up cache
    for _ in range(10):
        conn.execute("""
            SELECT id, lat, lon FROM traffic_lights
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
        """, (sample_lat - 0.01, sample_lat + 0.01,
              sample_lon - 0.01, sample_lon + 0.01)).fetchall()

    # Benchmark
    iterations = 1000
    start = time.perf_counter()

    for _ in range(iterations):
        cursor = conn.execute("""
            SELECT id, lat, lon FROM traffic_lights
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
        """, (sample_lat - 0.005, sample_lat + 0.005,  # ~1km box
              sample_lon - 0.007, sample_lon + 0.007))
        results = cursor.fetchall()

    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / iterations) * 1000

    logger.info(f"Query benchmark results:")
    logger.info(f"  Iterations: {iterations}")
    logger.info(f"  Total time: {elapsed*1000:.2f}ms")
    logger.info(f"  Average per query: {avg_ms:.3f}ms")
    logger.info(f"  Results per query: {len(results)}")

    conn.close()

    # Check performance target
    if avg_ms > 5:
        logger.warning(f"Query time {avg_ms:.3f}ms exceeds 5ms target")
        logger.warning("Consider running on faster storage or reducing database size")
    else:
        logger.info(f"PASS: Query time {avg_ms:.3f}ms meets <5ms target")

    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Setup traffic light database from OpenStreetMap data'
    )
    parser.add_argument(
        '--region',
        choices=list(GEOFABRIK_URLS.keys()),
        default='ontario',
        help='Region to download (default: ontario)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help=f'Output database path (default: data/{DEFAULT_DB_NAME})'
    )
    parser.add_argument(
        '--keep-pbf',
        action='store_true',
        help='Keep downloaded PBF file after processing'
    )
    parser.add_argument(
        '--pbf-path',
        type=str,
        default=None,
        help='Use existing PBF file instead of downloading'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip database validation'
    )

    args = parser.parse_args()

    # Setup paths
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.output:
        db_path = Path(args.output)
    else:
        db_path = DEFAULT_DATA_DIR / DEFAULT_DB_NAME

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("SignalSight Traffic Light Database Setup")
    logger.info("=" * 60)
    logger.info(f"Region: {args.region}")
    logger.info(f"Output: {db_path}")
    logger.info("")

    # Download or use existing PBF
    if args.pbf_path:
        pbf_path = Path(args.pbf_path)
        if not pbf_path.exists():
            logger.error(f"PBF file not found: {pbf_path}")
            sys.exit(1)
        logger.info(f"Using existing PBF: {pbf_path}")
        cleanup_pbf = False
    else:
        # Download OSM data
        pbf_path = DEFAULT_DATA_DIR / f"{args.region}-latest.osm.pbf"
        url = GEOFABRIK_URLS[args.region]

        if pbf_path.exists():
            logger.info(f"PBF file already exists: {pbf_path}")
            logger.info("Delete it to re-download, or use --pbf-path to specify")
        else:
            if not download_osm_data(url, pbf_path):
                sys.exit(1)

        cleanup_pbf = not args.keep_pbf

    # Extract traffic signals
    try:
        traffic_lights = extract_traffic_signals(pbf_path)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        logger.error("Make sure osmium is installed: pip install osmium")
        sys.exit(1)

    if not traffic_lights:
        logger.error("No traffic signals found in data!")
        sys.exit(1)

    # Create database
    create_database(db_path, traffic_lights)

    # Validate database
    if not args.skip_validation:
        if not validate_database(db_path):
            sys.exit(1)

    # Cleanup
    if cleanup_pbf and pbf_path.exists():
        logger.info(f"Cleaning up PBF file: {pbf_path}")
        pbf_path.unlink()

    logger.info("")
    logger.info("=" * 60)
    logger.info("Setup Complete!")
    logger.info("=" * 60)
    logger.info(f"Database: {db_path}")
    logger.info(f"Size: {db_path.stat().st_size / (1024 * 1024):.2f} MB")
    logger.info("")
    logger.info("Usage:")
    logger.info("  from traffic_light_db import TrafficLightDB")
    logger.info(f"  db = TrafficLightDB('{db_path}')")
    logger.info("  lights = db.get_nearby_lights_fast(lat, lon, 500)")
    logger.info("")


if __name__ == "__main__":
    main()
