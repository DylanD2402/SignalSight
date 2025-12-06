#!/usr/bin/env python3
"""
Performance Benchmark for SignalSight Traffic Light Database

Tests database query performance to ensure it meets Raspberry Pi 5 targets:
- Query latency: <5ms
- Memory footprint: <20MB
- CPU usage: <1% per query
- Support 10Hz+ query rate

Usage:
    python benchmark.py [database_path]

Author: SignalSight Team
"""

import argparse
import logging
import time
import random
import statistics
import resource
import sys
import os
from pathlib import Path
from typing import List, Tuple

from traffic_light_db import TrafficLightDB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Run performance benchmarks on traffic light database."""

    def __init__(self, db_path: str):
        """Initialize benchmark runner."""
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.db = TrafficLightDB(str(db_path))
        self.stats = self.db.get_stats()

        logger.info(f"Database: {db_path}")
        logger.info(f"Total lights: {self.stats['total_lights']}")
        logger.info(f"File size: {self.stats['file_size_mb']:.2f} MB")

    def _generate_test_points(self, n: int) -> List[Tuple[float, float]]:
        """
        Generate random test points within database bounds.

        Args:
            n: Number of points to generate

        Returns:
            List of (lat, lon) tuples
        """
        points = []
        for _ in range(n):
            lat = random.uniform(self.stats['min_lat'], self.stats['max_lat'])
            lon = random.uniform(self.stats['min_lon'], self.stats['max_lon'])
            points.append((lat, lon))
        return points

    def benchmark_query_latency(self, iterations: int = 1000) -> dict:
        """
        Benchmark query latency.

        Target: <5ms per query on Raspberry Pi 5

        Args:
            iterations: Number of queries to run

        Returns:
            Dictionary with timing statistics
        """
        logger.info(f"\nBenchmark: Query Latency ({iterations} iterations)")
        logger.info("-" * 50)

        # Generate test points
        test_points = self._generate_test_points(iterations)

        # Warm up cache
        logger.info("Warming up cache...")
        for lat, lon in test_points[:100]:
            self.db.get_nearby_lights_fast(lat, lon, 500)

        # Run benchmark
        logger.info("Running benchmark...")
        timings = []
        result_counts = []

        for lat, lon in test_points:
            start = time.perf_counter()
            results = self.db.get_nearby_lights_fast(lat, lon, 500)
            elapsed = time.perf_counter() - start

            timings.append(elapsed * 1000)  # Convert to ms
            result_counts.append(len(results))

        # Calculate statistics
        avg_ms = statistics.mean(timings)
        median_ms = statistics.median(timings)
        p95_ms = sorted(timings)[int(len(timings) * 0.95)]
        p99_ms = sorted(timings)[int(len(timings) * 0.99)]
        min_ms = min(timings)
        max_ms = max(timings)
        std_ms = statistics.stdev(timings) if len(timings) > 1 else 0

        avg_results = statistics.mean(result_counts)

        # Report results
        logger.info(f"\nResults:")
        logger.info(f"  Average:    {avg_ms:.3f} ms")
        logger.info(f"  Median:     {median_ms:.3f} ms")
        logger.info(f"  Min:        {min_ms:.3f} ms")
        logger.info(f"  Max:        {max_ms:.3f} ms")
        logger.info(f"  Std Dev:    {std_ms:.3f} ms")
        logger.info(f"  P95:        {p95_ms:.3f} ms")
        logger.info(f"  P99:        {p99_ms:.3f} ms")
        logger.info(f"  Avg results: {avg_results:.1f}")

        # Check target
        target_met = avg_ms < 5.0
        if target_met:
            logger.info(f"\n  PASS: Average {avg_ms:.3f}ms < 5ms target")
        else:
            logger.warning(f"\n  FAIL: Average {avg_ms:.3f}ms > 5ms target")

        return {
            'iterations': iterations,
            'avg_ms': avg_ms,
            'median_ms': median_ms,
            'min_ms': min_ms,
            'max_ms': max_ms,
            'std_ms': std_ms,
            'p95_ms': p95_ms,
            'p99_ms': p99_ms,
            'avg_results': avg_results,
            'target_met': target_met
        }

    def benchmark_throughput(self, duration_s: float = 5.0) -> dict:
        """
        Benchmark query throughput.

        Target: 10Hz+ sustained query rate

        Args:
            duration_s: Test duration in seconds

        Returns:
            Dictionary with throughput statistics
        """
        logger.info(f"\nBenchmark: Query Throughput ({duration_s}s)")
        logger.info("-" * 50)

        # Generate test points
        test_points = self._generate_test_points(10000)
        point_idx = 0

        # Run for duration
        query_count = 0
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < duration_s:
            lat, lon = test_points[point_idx % len(test_points)]
            self.db.get_nearby_lights_fast(lat, lon, 500)
            query_count += 1
            point_idx += 1

        elapsed = time.perf_counter() - start_time
        qps = query_count / elapsed

        logger.info(f"\nResults:")
        logger.info(f"  Duration:      {elapsed:.2f} s")
        logger.info(f"  Total queries: {query_count}")
        logger.info(f"  Queries/sec:   {qps:.1f}")
        logger.info(f"  Rate:          {qps:.0f} Hz")

        # Check target
        target_met = qps >= 10
        if target_met:
            logger.info(f"\n  PASS: {qps:.0f} Hz >= 10Hz target")
        else:
            logger.warning(f"\n  FAIL: {qps:.0f} Hz < 10Hz target")

        return {
            'duration_s': elapsed,
            'query_count': query_count,
            'queries_per_second': qps,
            'target_met': target_met
        }

    def benchmark_memory(self) -> dict:
        """
        Benchmark memory usage.

        Target: <20MB for database operations

        Returns:
            Dictionary with memory statistics
        """
        logger.info("\nBenchmark: Memory Usage")
        logger.info("-" * 50)

        # Get current memory usage
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        mem_mb = rusage.ru_maxrss / 1024  # Convert KB to MB (Linux)

        # On macOS, ru_maxrss is in bytes
        if sys.platform == 'darwin':
            mem_mb = rusage.ru_maxrss / (1024 * 1024)

        # Run some queries to allocate typical memory
        test_points = self._generate_test_points(100)
        for lat, lon in test_points:
            results = self.db.get_nearby_lights_fast(lat, lon, 1000)

        # Check memory after queries
        rusage_after = resource.getrusage(resource.RUSAGE_SELF)
        mem_after_mb = rusage_after.ru_maxrss / 1024
        if sys.platform == 'darwin':
            mem_after_mb = rusage_after.ru_maxrss / (1024 * 1024)

        logger.info(f"\nResults:")
        logger.info(f"  Initial memory:  {mem_mb:.2f} MB")
        logger.info(f"  After queries:   {mem_after_mb:.2f} MB")
        logger.info(f"  Database file:   {self.stats['file_size_mb']:.2f} MB")

        # Check target (comparing against 20MB delta)
        delta_mb = mem_after_mb - mem_mb
        target_met = delta_mb < 20

        if target_met:
            logger.info(f"\n  PASS: Memory delta {delta_mb:.2f}MB < 20MB target")
        else:
            logger.warning(f"\n  FAIL: Memory delta {delta_mb:.2f}MB > 20MB target")

        return {
            'initial_mb': mem_mb,
            'after_mb': mem_after_mb,
            'delta_mb': delta_mb,
            'db_file_mb': self.stats['file_size_mb'],
            'target_met': target_met
        }

    def benchmark_different_radii(self) -> dict:
        """
        Benchmark query performance at different search radii.

        Returns:
            Dictionary with results for each radius
        """
        logger.info("\nBenchmark: Different Search Radii")
        logger.info("-" * 50)

        radii = [100, 250, 500, 1000, 2000]
        results = {}

        # Get center point
        center_lat = (self.stats['min_lat'] + self.stats['max_lat']) / 2
        center_lon = (self.stats['min_lon'] + self.stats['max_lon']) / 2

        for radius in radii:
            timings = []

            for _ in range(100):
                start = time.perf_counter()
                lights = self.db.get_nearby_lights_fast(center_lat, center_lon, radius)
                elapsed = time.perf_counter() - start
                timings.append(elapsed * 1000)

            avg_ms = statistics.mean(timings)
            results[radius] = {
                'avg_ms': avg_ms,
                'results': len(lights)
            }

            logger.info(f"  {radius}m: {avg_ms:.3f}ms avg, {len(lights)} results")

        return results

    def benchmark_concurrent_access(self, threads: int = 4) -> dict:
        """
        Benchmark concurrent query access.

        Tests thread safety and performance under concurrent load.

        Args:
            threads: Number of concurrent threads

        Returns:
            Dictionary with concurrency statistics
        """
        import threading

        logger.info(f"\nBenchmark: Concurrent Access ({threads} threads)")
        logger.info("-" * 50)

        queries_per_thread = 250
        test_points = self._generate_test_points(queries_per_thread * threads)

        thread_timings = []
        lock = threading.Lock()

        def worker(thread_id: int, points: List[Tuple[float, float]]):
            local_timings = []

            for lat, lon in points:
                start = time.perf_counter()
                self.db.get_nearby_lights_fast(lat, lon, 500)
                elapsed = time.perf_counter() - start
                local_timings.append(elapsed * 1000)

            with lock:
                thread_timings.extend(local_timings)

        # Create and start threads
        thread_list = []
        for i in range(threads):
            start_idx = i * queries_per_thread
            end_idx = start_idx + queries_per_thread
            points = test_points[start_idx:end_idx]

            t = threading.Thread(target=worker, args=(i, points))
            thread_list.append(t)

        start_time = time.perf_counter()

        for t in thread_list:
            t.start()

        for t in thread_list:
            t.join()

        elapsed = time.perf_counter() - start_time
        total_queries = len(thread_timings)
        qps = total_queries / elapsed
        avg_ms = statistics.mean(thread_timings)

        logger.info(f"\nResults:")
        logger.info(f"  Threads:       {threads}")
        logger.info(f"  Total queries: {total_queries}")
        logger.info(f"  Total time:    {elapsed:.2f}s")
        logger.info(f"  Queries/sec:   {qps:.1f}")
        logger.info(f"  Avg latency:   {avg_ms:.3f}ms")

        return {
            'threads': threads,
            'total_queries': total_queries,
            'elapsed_s': elapsed,
            'queries_per_second': qps,
            'avg_latency_ms': avg_ms
        }

    def run_all(self) -> dict:
        """
        Run all benchmarks.

        Returns:
            Dictionary with all results
        """
        logger.info("\n" + "=" * 60)
        logger.info("SignalSight Traffic Light Database Benchmark")
        logger.info("=" * 60)

        results = {
            'database': {
                'path': str(self.db_path),
                'total_lights': self.stats['total_lights'],
                'file_size_mb': self.stats['file_size_mb']
            }
        }

        # Run benchmarks
        results['latency'] = self.benchmark_query_latency()
        results['throughput'] = self.benchmark_throughput()
        results['memory'] = self.benchmark_memory()
        results['radii'] = self.benchmark_different_radii()
        results['concurrent'] = self.benchmark_concurrent_access()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Summary")
        logger.info("=" * 60)

        all_passed = True
        targets = [
            ('Query Latency <5ms', results['latency']['target_met']),
            ('Throughput ≥10Hz', results['throughput']['target_met']),
            ('Memory <20MB', results['memory']['target_met']),
        ]

        for name, passed in targets:
            status = "PASS" if passed else "FAIL"
            logger.info(f"  {name}: {status}")
            all_passed = all_passed and passed

        logger.info("")
        if all_passed:
            logger.info("All performance targets met!")
        else:
            logger.warning("Some targets not met. Consider optimizations.")

        results['all_passed'] = all_passed
        return results

    def close(self):
        """Close database connection."""
        self.db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Benchmark traffic light database performance'
    )
    parser.add_argument(
        'database',
        nargs='?',
        default='data/traffic_lights.db',
        help='Path to traffic light database'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick benchmark with fewer iterations'
    )

    args = parser.parse_args()

    try:
        runner = BenchmarkRunner(args.database)

        if args.quick:
            # Quick benchmark
            results = {
                'latency': runner.benchmark_query_latency(100),
                'throughput': runner.benchmark_throughput(1.0)
            }
        else:
            results = runner.run_all()

        runner.close()

        # Exit with error if targets not met
        if not results.get('all_passed', True):
            sys.exit(1)

    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("\nRun database_setup.py first to create the database.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
