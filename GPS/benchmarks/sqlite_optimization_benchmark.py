#!/usr/bin/env python3
"""
SQLite Optimization Benchmark for SignalSight

Compares query performance with and without SQLite optimizations
to demonstrate the impact of the optimizations on query latency.

Usage:
    python sqlite_optimization_benchmark.py [--db-path PATH]

Requirements:
    - Traffic light database (created by GPS/setup/database_setup.py)
"""

import sqlite3
import time
import argparse
import sys
from pathlib import Path
from typing import List, Tuple


def get_unoptimized_connection(db_path: str) -> sqlite3.Connection:
    """
    Create database connection WITHOUT optimizations (baseline).

    This represents a standard SQLite connection with default settings.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_optimized_connection(db_path: str) -> sqlite3.Connection:
    """
    Create database connection WITH optimizations (optimized).

    Applies all performance optimizations from traffic_light_db.py:
    - WAL mode for concurrent reads
    - Increased cache size (8MB)
    - Memory-mapped I/O (64MB)
    - Synchronous OFF
    - Read uncommitted
    - Temp store in memory
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)

    # Apply optimizations
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA cache_size=-8000")  # 8MB
    conn.execute("PRAGMA mmap_size=67108864")  # 64MB
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA read_uncommitted=ON")
    conn.execute("PRAGMA temp_store=MEMORY")

    conn.row_factory = sqlite3.Row
    return conn


def get_sample_locations(conn: sqlite3.Connection, count: int = 10) -> List[Tuple[float, float]]:
    """Get random sample locations from database for testing."""
    cursor = conn.execute("""
        SELECT lat, lon FROM traffic_lights
        ORDER BY RANDOM()
        LIMIT ?
    """, (count,))
    return [(row['lat'], row['lon']) for row in cursor.fetchall()]


def benchmark_queries(conn: sqlite3.Connection,
                     test_locations: List[Tuple[float, float]],
                     iterations: int = 100) -> dict:
    """
    Benchmark spatial queries on the given connection.

    Args:
        conn: Database connection (optimized or unoptimized)
        test_locations: List of (lat, lon) tuples to query
        iterations: Number of iterations per location

    Returns:
        Dictionary with benchmark results
    """
    results = []

    # Warm up cache (run queries once)
    for lat, lon in test_locations:
        min_lat, max_lat = lat - 0.005, lat + 0.005
        min_lon, max_lon = lon - 0.007, lon + 0.007
        conn.execute("""
            SELECT id, lat, lon FROM traffic_lights
            WHERE lat BETWEEN ? AND ?
              AND lon BETWEEN ? AND ?
        """, (min_lat, max_lat, min_lon, max_lon)).fetchall()

    # Run benchmark
    total_queries = len(test_locations) * iterations
    start = time.perf_counter()

    for _ in range(iterations):
        for lat, lon in test_locations:
            min_lat, max_lat = lat - 0.005, lat + 0.005
            min_lon, max_lon = lon - 0.007, lon + 0.007

            query_start = time.perf_counter()
            cursor = conn.execute("""
                SELECT id, lat, lon FROM traffic_lights
                WHERE lat BETWEEN ? AND ?
                  AND lon BETWEEN ? AND ?
            """, (min_lat, max_lat, min_lon, max_lon))
            rows = cursor.fetchall()
            query_time = time.perf_counter() - query_start

            results.append({
                'time_ms': query_time * 1000,
                'result_count': len(rows)
            })

    total_time = time.perf_counter() - start

    # Calculate statistics
    times = [r['time_ms'] for r in results]
    times.sort()

    return {
        'total_queries': total_queries,
        'total_time_ms': total_time * 1000,
        'avg_time_ms': sum(times) / len(times),
        'min_time_ms': times[0],
        'max_time_ms': times[-1],
        'median_time_ms': times[len(times) // 2],
        'p95_time_ms': times[int(len(times) * 0.95)],
        'p99_time_ms': times[int(len(times) * 0.99)],
        'queries_per_sec': total_queries / total_time,
        'avg_results': sum(r['result_count'] for r in results) / len(results)
    }


def print_results(label: str, results: dict):
    """Print benchmark results in a formatted table."""
    print(f"\n{'=' * 60}")
    print(f"{label}")
    print(f"{'=' * 60}")
    print(f"  Total queries:        {results['total_queries']}")
    print(f"  Total time:           {results['total_time_ms']:.2f}ms")
    print(f"  Average per query:    {results['avg_time_ms']:.3f}ms")
    print(f"  Median:               {results['median_time_ms']:.3f}ms")
    print(f"  Min:                  {results['min_time_ms']:.3f}ms")
    print(f"  Max:                  {results['max_time_ms']:.3f}ms")
    print(f"  95th percentile:      {results['p95_time_ms']:.3f}ms")
    print(f"  99th percentile:      {results['p99_time_ms']:.3f}ms")
    print(f"  Queries/sec:          {results['queries_per_sec']:.0f}")
    print(f"  Avg results/query:    {results['avg_results']:.1f}")


def print_comparison(unopt_results: dict, opt_results: dict):
    """Print comparison showing improvement from optimizations."""
    print(f"\n{'=' * 60}")
    print("IMPROVEMENT SUMMARY")
    print(f"{'=' * 60}")

    avg_improvement = ((unopt_results['avg_time_ms'] - opt_results['avg_time_ms'])
                       / unopt_results['avg_time_ms'] * 100)
    median_improvement = ((unopt_results['median_time_ms'] - opt_results['median_time_ms'])
                          / unopt_results['median_time_ms'] * 100)
    p95_improvement = ((unopt_results['p95_time_ms'] - opt_results['p95_time_ms'])
                       / unopt_results['p95_time_ms'] * 100)
    throughput_improvement = ((opt_results['queries_per_sec'] - unopt_results['queries_per_sec'])
                              / unopt_results['queries_per_sec'] * 100)

    print(f"  Average query time:   {unopt_results['avg_time_ms']:.3f}ms → {opt_results['avg_time_ms']:.3f}ms ({avg_improvement:+.1f}%)")
    print(f"  Median query time:    {unopt_results['median_time_ms']:.3f}ms → {opt_results['median_time_ms']:.3f}ms ({median_improvement:+.1f}%)")
    print(f"  95th percentile:      {unopt_results['p95_time_ms']:.3f}ms → {opt_results['p95_time_ms']:.3f}ms ({p95_improvement:+.1f}%)")
    print(f"  Throughput:           {unopt_results['queries_per_sec']:.0f} → {opt_results['queries_per_sec']:.0f} queries/sec ({throughput_improvement:+.1f}%)")

    print(f"\n  Performance Target:   <5ms per query")
    if opt_results['avg_time_ms'] < 5.0:
        print(f"  Status:               ✓ PASS (avg: {opt_results['avg_time_ms']:.3f}ms)")
    else:
        print(f"  Status:               ✗ FAIL (avg: {opt_results['avg_time_ms']:.3f}ms)")

    print(f"\n  Speedup Factor:       {unopt_results['avg_time_ms'] / opt_results['avg_time_ms']:.2f}x faster")


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark SQLite optimizations for traffic light queries'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='GPS/data/traffic_lights.db',
        help='Path to traffic lights database'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of iterations per test location (default: 100)'
    )
    parser.add_argument(
        '--test-locations',
        type=int,
        default=10,
        help='Number of random test locations (default: 10)'
    )

    args = parser.parse_args()
    db_path = Path(args.db_path)

    # Verify database exists
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print(f"\nCreate database first:")
        print(f"  cd GPS/setup")
        print(f"  python database_setup.py")
        sys.exit(1)

    print("=" * 60)
    print("SQLite Optimization Benchmark")
    print("=" * 60)
    print(f"Database:         {db_path}")
    print(f"Iterations:       {args.iterations}")
    print(f"Test locations:   {args.test_locations}")
    print(f"Total queries:    {args.iterations * args.test_locations}")

    # Get database info
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM traffic_lights")
    total_lights = cursor.fetchone()[0]
    print(f"Traffic lights:   {total_lights}")
    conn.close()

    # Get random test locations
    print("\nPreparing test data...")
    conn = get_unoptimized_connection(str(db_path))
    test_locations = get_sample_locations(conn, args.test_locations)
    conn.close()

    # Benchmark WITHOUT optimizations (baseline)
    print("\nRunning UNOPTIMIZED benchmark...")
    conn_unopt = get_unoptimized_connection(str(db_path))
    unopt_results = benchmark_queries(conn_unopt, test_locations, args.iterations)
    conn_unopt.close()

    # Benchmark WITH optimizations
    print("Running OPTIMIZED benchmark...")
    conn_opt = get_optimized_connection(str(db_path))
    opt_results = benchmark_queries(conn_opt, test_locations, args.iterations)
    conn_opt.close()

    # Print results
    print_results("UNOPTIMIZED (Baseline)", unopt_results)
    print_results("OPTIMIZED (With PRAGMAs)", opt_results)
    print_comparison(unopt_results, opt_results)

    print(f"\n{'=' * 60}")
    print("Benchmark complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
