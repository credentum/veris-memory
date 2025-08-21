#!/usr/bin/env python3
"""
Performance Benchmarking Suite for Veris Memory System.

Comprehensive performance testing framework that measures system performance
across various scenarios, configurations, and load patterns.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import random

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.query_dispatcher import QueryDispatcher, SearchMode, DispatchPolicy
from interfaces.memory_result import MemoryResult, ContentType, ResultSource
# Mock backends removed - benchmarks now require real backend configuration


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark test."""
    name: str
    description: str
    query_count: int = 100
    concurrent_users: int = 1
    search_mode: SearchMode = SearchMode.HYBRID
    dispatch_policy: DispatchPolicy = DispatchPolicy.PARALLEL
    result_limit: int = 10
    use_filters: bool = False
    use_ranking: bool = False
    warmup_queries: int = 10


@dataclass
class BenchmarkResult:
    """Results from a benchmark test."""
    config: BenchmarkConfig
    total_queries: int
    successful_queries: int
    failed_queries: int
    total_time_ms: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    throughput_qps: float
    error_rate_percent: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


class PerformanceBenchmark:
    """Main performance benchmarking system."""
    
    def __init__(self, use_real_backends: bool = False):
        """Initialize the benchmark system."""
        self.dispatcher = None
        self.use_real_backends = use_real_backends
        self.benchmark_results: List[BenchmarkResult] = []
        
        # Test queries categorized by complexity
        self.simple_queries = [
            "python function",
            "api endpoint", 
            "database config",
            "user authentication",
            "error handling"
        ]
        
        self.medium_queries = [
            "python authentication function with database",
            "javascript async api call implementation",
            "database configuration with connection pooling",
            "user interface component with state management",
            "error handling middleware for web applications"
        ]
        
        self.complex_queries = [
            "comprehensive user authentication system with role-based access control and JWT token management",
            "scalable microservices architecture with API gateway, service discovery, and distributed caching",
            "real-time data processing pipeline with event streaming, transformation, and analytics",
            "machine learning model deployment with containerization, monitoring, and auto-scaling",
            "distributed database system with sharding, replication, and eventual consistency"
        ]
    
    async def initialize(self):
        """Initialize the benchmark environment."""
        print("🚀 Initializing Performance Benchmark Environment...")
        
        self.dispatcher = QueryDispatcher()
        
        # Mock backends removed for production safety
        print("⚠️ Mock backends removed - benchmarks require real backend configuration")
        print("💡 Configure environment variables for real backends:")
        print("   - NEO4J_PASSWORD for Neo4j")
        print("   - QDRANT_URL for Qdrant")  
        print("   - REDIS_URL for Redis")
        print()
        print("❌ Benchmarks require real backend configuration to prevent deployment issues")
        return
        
        print("✅ Benchmark environment initialized!")
        print(f"📊 Backends: {', '.join(self.dispatcher.list_backends())}")
        print()
    
    async def _populate_backends_with_data(self, vector_backend, graph_backend, kv_backend):
        """Populate backends with realistic test data."""
        sample_data = []
        
        # Generate code samples
        for i in range(200):
            sample_data.append(MemoryResult(
                id=f"code_{i}",
                text=f"def function_{i}(param: str) -> bool:\n    # Implementation for {random.choice(['auth', 'api', 'db', 'ui'])}\n    return True",
                type=ContentType.CODE,
                score=random.uniform(0.7, 1.0),
                source=ResultSource.VECTOR,
                timestamp=datetime.now(timezone.utc),
                tags=[random.choice(['python', 'javascript', 'java', 'go']), 
                      random.choice(['function', 'class', 'method']),
                      random.choice(['auth', 'api', 'database', 'ui'])],
                metadata={"language": random.choice(['python', 'javascript', 'java']), "complexity": random.choice(['simple', 'medium', 'complex'])}
            ))
        
        # Generate documentation samples
        for i in range(150):
            sample_data.append(MemoryResult(
                id=f"docs_{i}",
                text=f"Documentation for API endpoint {i}: This endpoint handles {random.choice(['user authentication', 'data retrieval', 'file upload', 'search functionality'])}",
                type=ContentType.DOCUMENTATION,
                score=random.uniform(0.6, 0.95),
                source=ResultSource.GRAPH,
                timestamp=datetime.now(timezone.utc),
                tags=[random.choice(['api', 'guide', 'reference']),
                      random.choice(['authentication', 'data', 'search', 'upload'])],
                metadata={"section": random.choice(['api', 'guides', 'reference']), "version": "1.0"}
            ))
        
        # Generate configuration samples
        for i in range(100):
            sample_data.append(MemoryResult(
                id=f"config_{i}",
                text=f"Configuration {i}:\nservice:\n  name: service_{i}\n  port: {8000 + i}\n  timeout: 30s",
                type=ContentType.CONFIGURATION,
                score=random.uniform(0.5, 0.9),
                source=ResultSource.KV,
                timestamp=datetime.now(timezone.utc),
                tags=[random.choice(['config', 'service', 'deployment']),
                      random.choice(['development', 'staging', 'production'])],
                metadata={"format": "yaml", "environment": random.choice(['dev', 'staging', 'prod'])}
            ))
        
        # Store in appropriate backends
        for context in sample_data:
            if context.source == ResultSource.VECTOR:
                await vector_backend.store_context(context)
            elif context.source == ResultSource.GRAPH:
                await graph_backend.store_context(context)
            elif context.source == ResultSource.KV:
                await kv_backend.store_context(context)
    
    async def run_benchmark_suite(self, custom_configs: Optional[List[BenchmarkConfig]] = None) -> Dict[str, Any]:
        """Run the complete benchmark suite."""
        print("🏃 Running Performance Benchmark Suite")
        print("=" * 60)
        
        configs = custom_configs if custom_configs else self._get_default_benchmark_configs()
        
        total_start_time = time.time()
        
        for i, config in enumerate(configs, 1):
            print(f"\n📊 Benchmark {i}/{len(configs)}: {config.name}")
            print(f"📝 {config.description}")
            print("-" * 50)
            
            result = await self._run_single_benchmark(config)
            self.benchmark_results.append(result)
            
            # Print immediate results
            self._print_benchmark_result(result)
        
        total_time = time.time() - total_start_time
        
        # Generate comprehensive summary
        summary = self._generate_benchmark_summary(total_time)
        
        print("\n" + "=" * 60)
        print("🏆 BENCHMARK SUITE SUMMARY")
        print("=" * 60)
        self._print_benchmark_summary(summary)
        
        return summary
    
    def _get_default_benchmark_configs(self) -> List[BenchmarkConfig]:
        """Get default benchmark configurations."""
        return [
            # Basic performance tests
            BenchmarkConfig(
                name="baseline_sequential",
                description="Baseline performance with sequential dispatch",
                query_count=50,
                concurrent_users=1,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.SEQUENTIAL
            ),
            BenchmarkConfig(
                name="baseline_parallel",
                description="Baseline performance with parallel dispatch",
                query_count=50,
                concurrent_users=1,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            
            # Search mode comparisons
            BenchmarkConfig(
                name="vector_only",
                description="Vector search performance",
                query_count=100,
                concurrent_users=1,
                search_mode=SearchMode.VECTOR,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            BenchmarkConfig(
                name="graph_only",
                description="Graph search performance",
                query_count=100,
                concurrent_users=1,
                search_mode=SearchMode.GRAPH,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            BenchmarkConfig(
                name="kv_only",
                description="Key-value search performance",
                query_count=100,
                concurrent_users=1,
                search_mode=SearchMode.KV,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            BenchmarkConfig(
                name="hybrid_search",
                description="Hybrid search performance",
                query_count=100,
                concurrent_users=1,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            
            # Concurrency tests
            BenchmarkConfig(
                name="low_concurrency",
                description="Low concurrency stress test",
                query_count=200,
                concurrent_users=5,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            BenchmarkConfig(
                name="medium_concurrency",
                description="Medium concurrency stress test",
                query_count=300,
                concurrent_users=10,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            BenchmarkConfig(
                name="high_concurrency",
                description="High concurrency stress test",
                query_count=500,
                concurrent_users=20,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.PARALLEL
            ),
            
            # Result size tests
            BenchmarkConfig(
                name="small_results",
                description="Small result set performance",
                query_count=100,
                concurrent_users=5,
                result_limit=5,
                search_mode=SearchMode.HYBRID
            ),
            BenchmarkConfig(
                name="large_results",
                description="Large result set performance",
                query_count=100,
                concurrent_users=5,
                result_limit=50,
                search_mode=SearchMode.HYBRID
            ),
            
            # Complex query tests
            BenchmarkConfig(
                name="simple_queries",
                description="Simple query performance",
                query_count=200,
                concurrent_users=10,
                search_mode=SearchMode.HYBRID
            ),
            BenchmarkConfig(
                name="complex_queries",
                description="Complex query performance",
                query_count=100,
                concurrent_users=5,
                search_mode=SearchMode.HYBRID
            ),
            
            # Dispatch policy comparisons
            BenchmarkConfig(
                name="fallback_policy",
                description="Fallback dispatch policy performance",
                query_count=100,
                concurrent_users=5,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.FALLBACK
            ),
            BenchmarkConfig(
                name="smart_policy",
                description="Smart dispatch policy performance",
                query_count=100,
                concurrent_users=5,
                search_mode=SearchMode.HYBRID,
                dispatch_policy=DispatchPolicy.SMART
            )
        ]
    
    async def _run_single_benchmark(self, config: BenchmarkConfig) -> BenchmarkResult:
        """Run a single benchmark configuration."""
        # Warmup phase
        if config.warmup_queries > 0:
            print(f"🔥 Warming up with {config.warmup_queries} queries...")
            await self._run_warmup(config.warmup_queries)
        
        # Select query set based on configuration
        if "simple" in config.name:
            query_pool = self.simple_queries
        elif "complex" in config.name:
            query_pool = self.complex_queries
        else:
            query_pool = self.medium_queries
        
        # Prepare queries
        queries = []
        for _ in range(config.query_count):
            query = random.choice(query_pool)
            queries.append(query)
        
        # Run benchmark
        start_time = time.time()
        response_times = []
        successful_queries = 0
        failed_queries = 0
        
        if config.concurrent_users == 1:
            # Sequential execution
            for query in queries:
                success, response_time = await self._execute_single_query(query, config)
                response_times.append(response_time)
                if success:
                    successful_queries += 1
                else:
                    failed_queries += 1
        else:
            # Concurrent execution
            semaphore = asyncio.Semaphore(config.concurrent_users)
            
            async def execute_query_with_semaphore(query):
                async with semaphore:
                    return await self._execute_single_query(query, config)
            
            tasks = [execute_query_with_semaphore(query) for query in queries]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    failed_queries += 1
                    response_times.append(5000.0)  # Penalty time for failed queries
                else:
                    success, response_time = result
                    response_times.append(response_time)
                    if success:
                        successful_queries += 1
                    else:
                        failed_queries += 1
        
        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000
        
        # Calculate statistics
        valid_response_times = [rt for rt in response_times if rt < 5000.0]  # Exclude penalty times
        
        if valid_response_times:
            avg_response_time = statistics.mean(valid_response_times)
            min_response_time = min(valid_response_times)
            max_response_time = max(valid_response_times)
            
            sorted_times = sorted(valid_response_times)
            p50_response_time = sorted_times[int(len(sorted_times) * 0.50)]
            p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
            p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p50_response_time = p95_response_time = p99_response_time = 0
        
        throughput_qps = config.query_count / (total_time_ms / 1000) if total_time_ms > 0 else 0
        error_rate_percent = (failed_queries / config.query_count) * 100 if config.query_count > 0 else 0
        
        return BenchmarkResult(
            config=config,
            total_queries=config.query_count,
            successful_queries=successful_queries,
            failed_queries=failed_queries,
            total_time_ms=total_time_ms,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            throughput_qps=throughput_qps,
            error_rate_percent=error_rate_percent
        )
    
    async def _run_warmup(self, warmup_queries: int):
        """Run warmup queries to stabilize performance."""
        warmup_query_pool = self.simple_queries
        
        for _ in range(warmup_queries):
            query = random.choice(warmup_query_pool)
            try:
                await self.dispatcher.dispatch_query(
                    query=query,
                    search_mode=SearchMode.HYBRID,
                    limit=5
                )
            except Exception:
                pass  # Ignore warmup failures
    
    async def _execute_single_query(self, query: str, config: BenchmarkConfig) -> Tuple[bool, float]:
        """Execute a single query and return success status and response time."""
        start_time = time.time()
        
        try:
            # Build query parameters
            query_params = {
                'query': query,
                'search_mode': config.search_mode,
                'dispatch_policy': config.dispatch_policy,
                'limit': config.result_limit
            }
            
            if config.use_ranking:
                query_params['ranking_policy'] = 'code_boost'
            
            if config.use_filters:
                query_params['content_types'] = ['code', 'documentation']
                query_params['min_score'] = 0.5
            
            result = await self.dispatcher.dispatch_query(**query_params)
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            return result.success, response_time_ms
            
        except Exception:
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            return False, response_time_ms
    
    def _print_benchmark_result(self, result: BenchmarkResult):
        """Print results from a single benchmark."""
        print(f"✅ Completed: {result.successful_queries}/{result.total_queries} queries")
        print(f"⏱️  Total Time: {result.total_time_ms:.1f}ms")
        print(f"📊 Throughput: {result.throughput_qps:.1f} queries/second")
        print(f"📈 Response Times:")
        print(f"   Average: {result.avg_response_time_ms:.1f}ms")
        print(f"   50th percentile: {result.p50_response_time_ms:.1f}ms")
        print(f"   95th percentile: {result.p95_response_time_ms:.1f}ms")
        print(f"   99th percentile: {result.p99_response_time_ms:.1f}ms")
        print(f"   Range: {result.min_response_time_ms:.1f}ms - {result.max_response_time_ms:.1f}ms")
        
        if result.error_rate_percent > 0:
            print(f"❌ Error Rate: {result.error_rate_percent:.1f}%")
        else:
            print(f"✅ Error Rate: {result.error_rate_percent:.1f}%")
    
    def _generate_benchmark_summary(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive benchmark summary."""
        if not self.benchmark_results:
            return {}
        
        # Overall statistics
        total_queries = sum(r.total_queries for r in self.benchmark_results)
        total_successful = sum(r.successful_queries for r in self.benchmark_results)
        total_failed = sum(r.failed_queries for r in self.benchmark_results)
        
        # Response time statistics across all benchmarks
        all_avg_times = [r.avg_response_time_ms for r in self.benchmark_results if r.avg_response_time_ms > 0]
        all_p95_times = [r.p95_response_time_ms for r in self.benchmark_results if r.p95_response_time_ms > 0]
        all_throughputs = [r.throughput_qps for r in self.benchmark_results if r.throughput_qps > 0]
        
        # Performance rankings
        fastest_benchmark = min(self.benchmark_results, key=lambda r: r.avg_response_time_ms)
        slowest_benchmark = max(self.benchmark_results, key=lambda r: r.avg_response_time_ms)
        highest_throughput = max(self.benchmark_results, key=lambda r: r.throughput_qps)
        most_reliable = min(self.benchmark_results, key=lambda r: r.error_rate_percent)
        
        return {
            'summary': {
                'total_benchmarks': len(self.benchmark_results),
                'total_queries': total_queries,
                'successful_queries': total_successful,
                'failed_queries': total_failed,
                'overall_success_rate': (total_successful / total_queries * 100) if total_queries > 0 else 0,
                'total_execution_time_seconds': total_time
            },
            'performance_metrics': {
                'avg_response_time_ms': statistics.mean(all_avg_times) if all_avg_times else 0,
                'median_response_time_ms': statistics.median(all_avg_times) if all_avg_times else 0,
                'avg_p95_response_time_ms': statistics.mean(all_p95_times) if all_p95_times else 0,
                'avg_throughput_qps': statistics.mean(all_throughputs) if all_throughputs else 0,
                'max_throughput_qps': max(all_throughputs) if all_throughputs else 0
            },
            'performance_rankings': {
                'fastest_benchmark': {
                    'name': fastest_benchmark.config.name,
                    'avg_response_time_ms': fastest_benchmark.avg_response_time_ms
                },
                'slowest_benchmark': {
                    'name': slowest_benchmark.config.name,
                    'avg_response_time_ms': slowest_benchmark.avg_response_time_ms
                },
                'highest_throughput': {
                    'name': highest_throughput.config.name,
                    'throughput_qps': highest_throughput.throughput_qps
                },
                'most_reliable': {
                    'name': most_reliable.config.name,
                    'error_rate_percent': most_reliable.error_rate_percent
                }
            },
            'detailed_results': [asdict(result) for result in self.benchmark_results]
        }
    
    def _print_benchmark_summary(self, summary: Dict[str, Any]):
        """Print comprehensive benchmark summary."""
        s = summary['summary']
        m = summary['performance_metrics']
        r = summary['performance_rankings']
        
        print(f"\n📊 Overall Results:")
        print(f"   Total Benchmarks: {s['total_benchmarks']}")
        print(f"   Total Queries: {s['total_queries']:,}")
        print(f"   Success Rate: {s['overall_success_rate']:.1f}%")
        print(f"   Total Execution Time: {s['total_execution_time_seconds']:.1f}s")
        
        print(f"\n⚡ Performance Metrics:")
        print(f"   Average Response Time: {m['avg_response_time_ms']:.1f}ms")
        print(f"   Median Response Time: {m['median_response_time_ms']:.1f}ms")
        print(f"   Average 95th Percentile: {m['avg_p95_response_time_ms']:.1f}ms")
        print(f"   Average Throughput: {m['avg_throughput_qps']:.1f} queries/second")
        print(f"   Peak Throughput: {m['max_throughput_qps']:.1f} queries/second")
        
        print(f"\n🏆 Performance Rankings:")
        print(f"   🚀 Fastest: {r['fastest_benchmark']['name']} ({r['fastest_benchmark']['avg_response_time_ms']:.1f}ms)")
        print(f"   🐌 Slowest: {r['slowest_benchmark']['name']} ({r['slowest_benchmark']['avg_response_time_ms']:.1f}ms)")
        print(f"   🔥 Highest Throughput: {r['highest_throughput']['name']} ({r['highest_throughput']['throughput_qps']:.1f} qps)")
        print(f"   ✅ Most Reliable: {r['most_reliable']['name']} ({r['most_reliable']['error_rate_percent']:.1f}% errors)")
    
    def export_results(self, filename: str):
        """Export benchmark results to JSON file."""
        if not self.benchmark_results:
            print("❌ No benchmark results to export")
            return
        
        export_data = {
            'benchmark_info': {
                'timestamp': datetime.now().isoformat(),
                'use_real_backends': self.use_real_backends,
                'total_benchmarks': len(self.benchmark_results)
            },
            'summary': self._generate_benchmark_summary(0),  # Summary without timing
            'detailed_results': [asdict(result) for result in self.benchmark_results]
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"✅ Benchmark results exported to: {filename}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    async def run_stress_test(self, duration_seconds: int = 300, target_qps: int = 50) -> Dict[str, Any]:
        """Run a sustained stress test for the specified duration."""
        print(f"🔥 Running Stress Test for {duration_seconds}s at {target_qps} QPS")
        print("-" * 60)
        
        query_interval = 1.0 / target_qps
        queries_executed = 0
        successful_queries = 0
        failed_queries = 0
        response_times = []
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        while time.time() < end_time:
            query_start = time.time()
            
            # Execute query
            query = random.choice(self.medium_queries)
            try:
                result = await self.dispatcher.dispatch_query(
                    query=query,
                    search_mode=SearchMode.HYBRID,
                    limit=10
                )
                
                query_end = time.time()
                response_time = (query_end - query_start) * 1000
                response_times.append(response_time)
                
                if result.success:
                    successful_queries += 1
                else:
                    failed_queries += 1
                    
            except Exception:
                failed_queries += 1
            
            queries_executed += 1
            
            # Rate limiting
            elapsed = time.time() - query_start
            if elapsed < query_interval:
                await asyncio.sleep(query_interval - elapsed)
            
            # Progress update every 10 seconds
            if queries_executed % (target_qps * 10) == 0:
                elapsed_time = time.time() - start_time
                current_qps = queries_executed / elapsed_time
                print(f"⏱️  {elapsed_time:.0f}s elapsed, {queries_executed} queries, {current_qps:.1f} QPS")
        
        total_time = time.time() - start_time
        actual_qps = queries_executed / total_time
        
        # Calculate statistics
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
            max_response_time = max(response_times)
        else:
            avg_response_time = p95_response_time = max_response_time = 0
        
        error_rate = (failed_queries / queries_executed * 100) if queries_executed > 0 else 0
        
        results = {
            'target_qps': target_qps,
            'actual_qps': actual_qps,
            'duration_seconds': total_time,
            'queries_executed': queries_executed,
            'successful_queries': successful_queries,
            'failed_queries': failed_queries,
            'error_rate_percent': error_rate,
            'avg_response_time_ms': avg_response_time,
            'p95_response_time_ms': p95_response_time,
            'max_response_time_ms': max_response_time
        }
        
        print(f"\n🏁 Stress Test Results:")
        print(f"   Target QPS: {target_qps}")
        print(f"   Actual QPS: {actual_qps:.1f}")
        print(f"   Total Queries: {queries_executed}")
        print(f"   Success Rate: {100 - error_rate:.1f}%")
        print(f"   Avg Response Time: {avg_response_time:.1f}ms")
        print(f"   95th Percentile: {p95_response_time:.1f}ms")
        print(f"   Max Response Time: {max_response_time:.1f}ms")
        
        return results


async def main():
    """Main entry point for the performance benchmark suite."""
    parser = argparse.ArgumentParser(description="Veris Memory Performance Benchmark Suite")
    parser.add_argument(
        "command",
        choices=["benchmark", "stress-test", "quick-benchmark"],
        help="Benchmark command to run"
    )
    parser.add_argument(
        "--export",
        help="Export results to JSON file"
    )
    parser.add_argument(
        "--real-backends",
        action="store_true",
        help="Use real backends instead of mock backends"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Stress test duration in seconds"
    )
    parser.add_argument(
        "--target-qps",
        type=int,
        default=50,
        help="Target queries per second for stress test"
    )
    
    args = parser.parse_args()
    
    # Initialize benchmark system
    benchmark = PerformanceBenchmark(use_real_backends=args.real_backends)
    await benchmark.initialize()
    
    if args.command == "benchmark":
        # Full benchmark suite
        results = await benchmark.run_benchmark_suite()
        
        if args.export:
            benchmark.export_results(args.export)
    
    elif args.command == "quick-benchmark":
        # Quick benchmark with reduced test set
        quick_configs = [
            BenchmarkConfig(
                name="quick_baseline",
                description="Quick baseline performance test",
                query_count=20,
                concurrent_users=1
            ),
            BenchmarkConfig(
                name="quick_concurrency",
                description="Quick concurrency test",
                query_count=50,
                concurrent_users=5
            ),
            BenchmarkConfig(
                name="quick_vector",
                description="Quick vector search test",
                query_count=30,
                search_mode=SearchMode.VECTOR
            )
        ]
        
        results = await benchmark.run_benchmark_suite(quick_configs)
        
        if args.export:
            benchmark.export_results(args.export)
    
    elif args.command == "stress-test":
        # Stress testing
        results = await benchmark.run_stress_test(
            duration_seconds=args.duration,
            target_qps=args.target_qps
        )
        
        if args.export:
            with open(args.export, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Stress test results exported to: {args.export}")


if __name__ == "__main__":
    asyncio.run(main())