#!/usr/bin/env python3
"""
MCP Performance Benchmarking Suite

This module provides comprehensive performance benchmarking for the Context Store MCP server,
including response time measurements, concurrent connection testing, and comparison with
direct database access.

Usage:
    python mcp_performance_benchmark.py [--concurrent-connections N] [--iterations N]
"""

import asyncio
import json
import logging
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp
import psutil
from tabulate import tabulate

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.neo4j_client import Neo4jInitializer  # noqa: E402
from storage.qdrant_client import VectorDBInitializer  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MCPBenchmark:
    """Main benchmark class for MCP performance testing."""

    def __init__(self, mcp_url: str = "http://localhost:8000/mcp"):
        self.mcp_url = mcp_url
        self.results = {
            "mcp_response_times": [],
            "direct_db_times": [],
            "concurrent_test_results": [],
            "memory_usage": [],
            "timestamp": datetime.now().isoformat(),
        }

    async def measure_mcp_response_time(self, tool_name: str, arguments: Dict[str, Any]) -> float:
        """Measure response time for a single MCP tool call."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1,
        }

        start_time = time.perf_counter()

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.mcp_url}/call", json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()
                    end_time = time.perf_counter()

                    if response.status == 200 and "result" in result:
                        return (end_time - start_time) * 1000  # Convert to milliseconds
                    else:
                        logger.error(f"MCP call failed: {result}")
                        return -1
            except Exception as e:
                logger.error(f"Error during MCP call: {e}")
                return -1

    async def measure_direct_db_access(self, operation: str) -> float:
        """Measure response time for direct database access."""
        start_time = time.perf_counter()

        try:
            if operation == "store_context":
                # Direct Neo4j write
                neo4j_client = Neo4jInitializer()
                await neo4j_client.execute_query(
                    """
                    CREATE (c:Context {
                        id: randomUUID(),
                        type: 'benchmark',
                        content: $content,
                        timestamp: datetime()
                    })
                    """,
                    {"content": {"test": "benchmark data"}},
                )
                neo4j_client.close()

            elif operation == "retrieve_context":
                # Direct Qdrant search
                qdrant_client = VectorDBInitializer()
                # Simulate vector search
                await qdrant_client.search(
                    query_vector=[0.1] * 384,  # Mock embedding
                    limit=5,
                )

            end_time = time.perf_counter()
            return (end_time - start_time) * 1000  # Convert to milliseconds

        except Exception as e:
            logger.error(f"Error during direct DB access: {e}")
            return -1

    async def run_concurrent_connections_test(self, num_connections: int) -> Dict[str, Any]:
        """Test concurrent MCP connections."""
        logger.info(f"Starting concurrent connections test with {num_connections} connections...")

        async def single_connection_test(connection_id: int) -> Dict[str, float]:
            """Run a single connection test."""
            start_time = time.perf_counter()

            # Test multiple operations per connection
            operations = [
                (
                    "store_context",
                    {
                        "type": "benchmark",
                        "content": {"connection_id": connection_id, "test": "concurrent"},
                        "metadata": {"timestamp": datetime.now().isoformat()},
                    },
                ),
                ("retrieve_context", {"query": "benchmark", "limit": 5}),
                ("get_agent_state", {"agent_id": f"benchmark_agent_{connection_id}"}),
            ]

            operation_times = {}
            for op_name, args in operations:
                op_time = await self.measure_mcp_response_time(op_name, args)
                operation_times[op_name] = op_time

            end_time = time.perf_counter()
            total_time = (end_time - start_time) * 1000

            return {
                "connection_id": connection_id,
                "total_time": total_time,
                "operation_times": operation_times,
                "success": all(t > 0 for t in operation_times.values()),
            }

        # Run concurrent tests
        tasks = [single_connection_test(i) for i in range(num_connections)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successful_connections = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_connections = len(results) - len(successful_connections)

        if successful_connections:
            avg_total_time = statistics.mean([r["total_time"] for r in successful_connections])
            p95_total_time = (
                statistics.quantiles([r["total_time"] for r in successful_connections], n=20)[18]
                if len(successful_connections) > 1
                else avg_total_time
            )
        else:
            avg_total_time = p95_total_time = 0

        return {
            "num_connections": num_connections,
            "successful": len(successful_connections),
            "failed": failed_connections,
            "avg_total_time_ms": avg_total_time,
            "p95_total_time_ms": p95_total_time,
            "individual_results": results[:10],  # Sample of results
        }

    def measure_memory_usage(self) -> Dict[str, float]:
        """Measure current memory usage."""
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "available_system_mb": psutil.virtual_memory().available / 1024 / 1024,
        }

    async def run_comprehensive_benchmark(
        self, iterations: int = 100, concurrent_tests: List[int] = None
    ):
        """Run comprehensive performance benchmark."""
        if concurrent_tests is None:
            concurrent_tests = [1, 10, 50, 100]

        logger.info("Starting MCP Performance Benchmark...")
        logger.info(f"MCP URL: {self.mcp_url}")
        logger.info(f"Iterations: {iterations}")

        # 1. Test individual MCP operations
        logger.info("\n1. Testing individual MCP operations...")

        test_operations = [
            (
                "store_context",
                {
                    "type": "benchmark",
                    "content": {"test": "performance", "iteration": 0},
                    "metadata": {"timestamp": datetime.now().isoformat()},
                },
            ),
            ("retrieve_context", {"query": "performance test", "limit": 10}),
            ("query_graph", {"query": "MATCH (n:Context) RETURN COUNT(n) as count LIMIT 1"}),
            ("get_agent_state", {"agent_id": "benchmark_agent"}),
            (
                "update_scratchpad",
                {"content": {"notes": "Performance benchmark test"}, "append": True},
            ),
        ]

        for op_name, args in test_operations:
            times = []
            logger.info(f"  Testing {op_name}...")

            for i in range(min(iterations, 20)):  # Limit iterations for individual tests
                args_copy = args.copy()
                if "content" in args_copy and isinstance(args_copy["content"], dict):
                    args_copy["content"]["iteration"] = i

                response_time = await self.measure_mcp_response_time(op_name, args_copy)
                if response_time > 0:
                    times.append(response_time)

            if times:
                self.results["mcp_response_times"].append(
                    {
                        "operation": op_name,
                        "count": len(times),
                        "min_ms": min(times),
                        "max_ms": max(times),
                        "avg_ms": statistics.mean(times),
                        "median_ms": statistics.median(times),
                        "p95_ms": (
                            statistics.quantiles(times, n=20)[18] if len(times) > 1 else max(times)
                        ),
                        "meets_target": statistics.mean(times) < 50,  # <50ms target
                    }
                )

        # 2. Compare with direct database access
        logger.info("\n2. Comparing with direct database access...")

        direct_db_operations = [
            ("store_context", "Direct Neo4j write"),
            ("retrieve_context", "Direct Qdrant search"),
        ]

        for op_name, description in direct_db_operations:
            times = []
            logger.info(f"  Testing {description}...")

            for i in range(min(iterations, 20)):
                response_time = await self.measure_direct_db_access(op_name)
                if response_time > 0:
                    times.append(response_time)

            if times:
                self.results["direct_db_times"].append(
                    {
                        "operation": op_name,
                        "description": description,
                        "count": len(times),
                        "avg_ms": statistics.mean(times),
                        "median_ms": statistics.median(times),
                    }
                )

        # 3. Test concurrent connections
        logger.info("\n3. Testing concurrent connections...")

        for num_connections in concurrent_tests:
            # Measure memory before test
            memory_before = self.measure_memory_usage()

            result = await self.run_concurrent_connections_test(num_connections)

            # Measure memory after test
            memory_after = self.measure_memory_usage()

            result["memory_delta_mb"] = memory_after["rss_mb"] - memory_before["rss_mb"]
            self.results["concurrent_test_results"].append(result)

            logger.info(
                f"  {num_connections} connections: {result['successful']} successful, "
                f"avg time: {result['avg_total_time_ms']:.2f}ms"
            )

        # 4. Final memory measurement
        self.results["memory_usage"] = self.measure_memory_usage()

        return self.results

    def generate_report(self) -> str:
        """Generate a formatted performance report."""
        report = []
        report.append("=" * 80)
        report.append("MCP PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 80)
        report.append(f"Timestamp: {self.results['timestamp']}")
        report.append("")

        # 1. Individual operation performance
        report.append("1. INDIVIDUAL OPERATION PERFORMANCE")
        report.append("-" * 40)

        if self.results["mcp_response_times"]:
            headers = [
                "Operation",
                "Count",
                "Min (ms)",
                "Avg (ms)",
                "Median (ms)",
                "P95 (ms)",
                "Max (ms)",
                "Target Met",
            ]
            rows = []

            for op in self.results["mcp_response_times"]:
                rows.append(
                    [
                        op["operation"],
                        op["count"],
                        f"{op['min_ms']:.2f}",
                        f"{op['avg_ms']:.2f}",
                        f"{op['median_ms']:.2f}",
                        f"{op['p95_ms']:.2f}",
                        f"{op['max_ms']:.2f}",
                        "✓" if op["meets_target"] else "✗",
                    ]
                )

            report.append(tabulate(rows, headers=headers, tablefmt="grid"))
            report.append("")

        # 2. MCP vs Direct DB comparison
        report.append("2. MCP VS DIRECT DATABASE ACCESS")
        report.append("-" * 40)

        if self.results["mcp_response_times"] and self.results["direct_db_times"]:
            headers = [
                "Operation",
                "MCP Avg (ms)",
                "Direct DB Avg (ms)",
                "Overhead (ms)",
                "Overhead (%)",
            ]
            rows = []

            for mcp_op in self.results["mcp_response_times"]:
                # Find matching direct DB operation
                direct_op = next(
                    (
                        d
                        for d in self.results["direct_db_times"]
                        if d["operation"] == mcp_op["operation"]
                    ),
                    None,
                )

                if direct_op:
                    overhead_ms = mcp_op["avg_ms"] - direct_op["avg_ms"]
                    overhead_pct = (
                        (overhead_ms / direct_op["avg_ms"] * 100) if direct_op["avg_ms"] > 0 else 0
                    )

                    rows.append(
                        [
                            mcp_op["operation"],
                            f"{mcp_op['avg_ms']:.2f}",
                            f"{direct_op['avg_ms']:.2f}",
                            f"{overhead_ms:.2f}",
                            f"{overhead_pct:.1f}%",
                        ]
                    )

            if rows:
                report.append(tabulate(rows, headers=headers, tablefmt="grid"))
                report.append("")

        # 3. Concurrent connections performance
        report.append("3. CONCURRENT CONNECTIONS PERFORMANCE")
        report.append("-" * 40)

        if self.results["concurrent_test_results"]:
            headers = [
                "Connections",
                "Successful",
                "Failed",
                "Avg Time (ms)",
                "P95 Time (ms)",
                "Memory Δ (MB)",
            ]
            rows = []

            for test in self.results["concurrent_test_results"]:
                rows.append(
                    [
                        test["num_connections"],
                        test["successful"],
                        test["failed"],
                        f"{test['avg_total_time_ms']:.2f}",
                        f"{test['p95_total_time_ms']:.2f}",
                        f"{test.get('memory_delta_mb', 0):.2f}",
                    ]
                )

            report.append(tabulate(rows, headers=headers, tablefmt="grid"))
            report.append("")

        # 4. Memory usage
        report.append("4. MEMORY USAGE")
        report.append("-" * 40)

        if self.results["memory_usage"]:
            mem = self.results["memory_usage"]
            report.append(f"RSS Memory: {mem['rss_mb']:.2f} MB")
            report.append(f"VMS Memory: {mem['vms_mb']:.2f} MB")
            report.append(f"Memory Percent: {mem['percent']:.2f}%")
            report.append(f"Available System Memory: {mem['available_system_mb']:.2f} MB")
            report.append("")

        # 5. Summary and recommendations
        report.append("5. SUMMARY AND RECOMMENDATIONS")
        report.append("-" * 40)

        # Check if <50ms target is met
        target_met = (
            all(op["meets_target"] for op in self.results["mcp_response_times"])
            if self.results["mcp_response_times"]
            else False
        )

        if target_met:
            report.append("✅ All operations meet the <50ms response time target")
        else:
            report.append("⚠️  Some operations exceed the <50ms response time target")

        # Check concurrent connection handling
        if self.results["concurrent_test_results"]:
            max_test = max(
                self.results["concurrent_test_results"], key=lambda x: x["num_connections"]
            )
            if max_test["successful"] >= 100:
                report.append("✅ Successfully handled 100+ concurrent connections")
            else:
                report.append(
                    f"⚠️  Maximum successful concurrent connections: {max_test['successful']}"
                )

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def save_results(self, output_dir: str = "benchmark_results") -> Tuple[Path, Path]:
        """Save benchmark results to files."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Save raw JSON results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = output_path / f"mcp_benchmark_{timestamp}.json"

        with open(json_file, "w") as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Results saved to {json_file}")

        # Save formatted report
        report_file = output_path / f"mcp_benchmark_report_{timestamp}.txt"
        report = self.generate_report()

        with open(report_file, "w") as f:
            f.write(report)

        logger.info(f"Report saved to {report_file}")

        return json_file, report_file


async def main():
    """Main entry point for the benchmark."""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Performance Benchmark")
    parser.add_argument("--mcp-url", default="http://localhost:8000/mcp", help="MCP server URL")
    parser.add_argument(
        "--iterations", type=int, default=100, help="Number of iterations for each test"
    )
    parser.add_argument(
        "--concurrent-connections",
        type=int,
        nargs="+",
        default=[1, 10, 50, 100, 200],
        help="Number of concurrent connections to test",
    )
    parser.add_argument(
        "--output-dir", default="benchmark_results", help="Directory to save results"
    )

    args = parser.parse_args()

    # Create benchmark instance
    benchmark = MCPBenchmark(args.mcp_url)

    # Run benchmark
    try:
        await benchmark.run_comprehensive_benchmark(
            iterations=args.iterations, concurrent_tests=args.concurrent_connections
        )

        # Generate and print report
        report = benchmark.generate_report()
        print(report)

        # Save results
        benchmark.save_results(args.output_dir)

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
