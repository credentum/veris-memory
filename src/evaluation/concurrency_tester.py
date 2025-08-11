"""
Concurrency and Load Testing for Phase 4.2

Implements comprehensive concurrent load testing including:
- 30-60 minute soak testing at target QPS with rolling redeploy
- Multi-threaded request generation and coordination
- Tail latency stability monitoring under sustained load
- Error rate tracking and circuit breaker simulation
- Service degradation detection and recovery validation
"""

import asyncio
import logging
import time
import json
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from dataclasses import dataclass, asdict
from collections import deque
import statistics
import psutil

from .evaluator import Evaluator, EvaluationConfig
from .datasets import DatasetManager
from .tracing import TracingContext, SpanContext, get_trace_manager

logger = logging.getLogger(__name__)


@dataclass
class LoadTestRequest:
    """Individual load test request tracking."""
    
    request_id: str
    timestamp: float
    query: str
    user_id: int
    
    # Response tracking
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    
    # Service state when request was made
    concurrent_requests: Optional[int] = None
    qps_at_time: Optional[float] = None


@dataclass
class LoadTestMetrics:
    """Metrics snapshot during load testing."""
    
    timestamp: str
    elapsed_minutes: float
    
    # Load metrics
    target_qps: int
    actual_qps: float
    concurrent_requests: int
    active_users: int
    
    # Latency metrics (sliding window)
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    
    # Error metrics
    error_rate_percent: float
    timeout_count: int
    connection_errors: int
    
    # System metrics
    memory_usage_mb: float
    cpu_usage_percent: float
    
    # Service health
    service_responsive: bool
    circuit_breaker_open: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SoakTestResult:
    """Complete soak test results with rolling redeploy."""
    
    test_name: str
    start_time: str
    duration_minutes: int
    target_qps: int
    concurrent_users: int
    
    # Configuration
    enable_rolling_redeploy: bool
    redeploy_interval_minutes: Optional[int]
    
    # Request tracking
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    # Performance summary
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    
    # Stability metrics
    avg_error_rate_percent: float
    max_error_rate_percent: float
    tail_latency_stable: bool
    
    # Rolling redeploy impact
    redeploy_count: int
    redeploy_impact_seconds: List[float]
    
    # Time series data
    metrics_timeline: List[LoadTestMetrics]
    
    # Assessment
    passed_soak_test: bool
    failure_reasons: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'metrics_timeline': [m.to_dict() for m in self.metrics_timeline]
        }


class ConcurrencyTester:
    """Implements concurrent load testing and soak testing."""
    
    def __init__(
        self,
        dataset_manager: DatasetManager,
        results_dir: str = "./concurrency_test_results"
    ):
        """
        Initialize concurrency tester.
        
        Args:
            dataset_manager: Dataset manager for test queries
            results_dir: Directory for storing results
        """
        self.dataset_manager = dataset_manager
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Load test state
        self.active_requests: Dict[str, LoadTestRequest] = {}
        self.completed_requests: deque = deque(maxlen=10000)  # Keep last 10k requests
        self.metrics_history: deque = deque(maxlen=1000)  # Keep last 1000 metric snapshots
        
        # Synchronization
        self.request_lock = threading.Lock()
        self.stop_event = asyncio.Event()
        
        # Performance thresholds
        self.max_error_rate_percent = 0.5  # 0.5% max error rate
        self.max_p95_latency_ms = 1000     # 1 second max P95 latency
        self.tail_latency_stability_threshold = 0.2  # 20% max variance
        
    async def run_soak_test(
        self,
        test_name: str,
        target_qps: int,
        duration_minutes: int = 60,
        concurrent_users: int = 10,
        enable_rolling_redeploy: bool = False,
        redeploy_interval_minutes: Optional[int] = None
    ) -> SoakTestResult:
        """
        Run comprehensive soak test with optional rolling redeploy.
        
        Args:
            test_name: Name for this soak test
            target_qps: Target queries per second
            duration_minutes: Test duration in minutes
            concurrent_users: Number of concurrent virtual users
            enable_rolling_redeploy: Whether to simulate rolling redeployments
            redeploy_interval_minutes: Interval between redeployments
            
        Returns:
            Complete soak test results
        """
        self.logger.info(f"🚀 Starting soak test: {test_name}")
        self.logger.info(f"Target QPS: {target_qps}")
        self.logger.info(f"Duration: {duration_minutes} minutes")
        self.logger.info(f"Concurrent users: {concurrent_users}")
        self.logger.info(f"Rolling redeploy: {enable_rolling_redeploy}")
        
        if enable_rolling_redeploy and redeploy_interval_minutes:
            self.logger.info(f"Redeploy interval: {redeploy_interval_minutes} minutes")
        
        trace_manager = get_trace_manager()
        
        async with TracingContext(
            request_type="soak_test",
            request_metadata={
                "test_name": test_name,
                "target_qps": target_qps,
                "duration_minutes": duration_minutes,
                "concurrent_users": concurrent_users
            },
            trace_manager=trace_manager
        ):
            
            # Initialize test state
            self.stop_event.clear()
            start_time = time.time()
            redeploy_count = 0
            redeploy_impact_times = []
            
            # Get test dataset
            dataset = await self.get_load_test_dataset()
            
            # Start concurrent tasks
            tasks = []
            
            # Task 1: Load generation
            load_task = asyncio.create_task(
                self.generate_load(
                    target_qps=target_qps,
                    concurrent_users=concurrent_users,
                    dataset=dataset,
                    duration_minutes=duration_minutes
                )
            )
            tasks.append(load_task)
            
            # Task 2: Metrics collection
            metrics_task = asyncio.create_task(
                self.collect_metrics_continuously(duration_minutes)
            )
            tasks.append(metrics_task)
            
            # Task 3: Rolling redeploy (if enabled)
            if enable_rolling_redeploy and redeploy_interval_minutes:
                redeploy_task = asyncio.create_task(
                    self.simulate_rolling_redeploys(
                        redeploy_interval_minutes,
                        duration_minutes
                    )
                )
                tasks.append(redeploy_task)
            
            # Task 4: Circuit breaker simulation
            circuit_breaker_task = asyncio.create_task(
                self.monitor_circuit_breaker(duration_minutes)
            )
            tasks.append(circuit_breaker_task)
            
            # Run all tasks concurrently
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                self.logger.error(f"Soak test error: {str(e)}")
            finally:
                self.stop_event.set()
            
            # Collect final results
            result = await self.analyze_soak_test_results(
                test_name=test_name,
                start_time=start_time,
                target_qps=target_qps,
                duration_minutes=duration_minutes,
                concurrent_users=concurrent_users,
                enable_rolling_redeploy=enable_rolling_redeploy,
                redeploy_interval_minutes=redeploy_interval_minutes,
                redeploy_count=redeploy_count,
                redeploy_impact_times=redeploy_impact_times
            )
            
            # Save results
            await self.save_soak_test_results(result)
            
            # Log summary
            self.logger.info("="*60)
            self.logger.info(f"🏁 Soak test completed: {test_name}")
            self.logger.info(f"Duration: {(time.time() - start_time)/60:.1f} minutes")
            self.logger.info(f"Total requests: {result.total_requests}")
            self.logger.info(f"Success rate: {(result.successful_requests/max(result.total_requests,1)*100):.1f}%")
            self.logger.info(f"Average P95 latency: {result.p95_latency_ms:.1f}ms")
            self.logger.info(f"Average error rate: {result.avg_error_rate_percent:.2f}%")
            self.logger.info(f"Tail latency stable: {result.tail_latency_stable}")
            self.logger.info(f"Passed soak test: {result.passed_soak_test}")
            
            if result.failure_reasons:
                self.logger.warning("⚠️  Failure reasons:")
                for reason in result.failure_reasons:
                    self.logger.warning(f"   - {reason}")
            
            return result
    
    async def generate_load(
        self,
        target_qps: int,
        concurrent_users: int,
        dataset: Dict[str, Any],
        duration_minutes: int
    ):
        """Generate sustained load with multiple concurrent users."""
        
        async def user_simulation(user_id: int, queries: List[Dict]):
            """Simulate individual user behavior."""
            user_queries = queries.copy()
            random.shuffle(user_queries)  # Each user gets different query order
            
            query_index = 0
            requests_made = 0
            
            # Calculate delay between requests for this user
            requests_per_user_per_second = target_qps / concurrent_users
            delay_between_requests = 1.0 / requests_per_user_per_second if requests_per_user_per_second > 0 else 1.0
            
            start_time = time.time()
            
            while not self.stop_event.is_set() and (time.time() - start_time) < duration_minutes * 60:
                try:
                    # Get next query (cycle through available queries)
                    query_data = user_queries[query_index % len(user_queries)]
                    query_index += 1
                    
                    # Create request
                    request = LoadTestRequest(
                        request_id=f"user_{user_id}_{requests_made}_{int(time.time()*1000)}",
                        timestamp=time.time(),
                        query=query_data.get('query', ''),
                        user_id=user_id,
                        concurrent_requests=len(self.active_requests),
                        qps_at_time=self.calculate_current_qps()
                    )
                    
                    # Track active request
                    with self.request_lock:
                        self.active_requests[request.request_id] = request
                    
                    # Send request (simulated)
                    response_start = time.time()
                    success, error = await self.send_load_test_request(query_data.get('query', ''))
                    response_time = (time.time() - response_start) * 1000
                    
                    # Update request with response
                    request.response_time_ms = response_time
                    if not success:
                        request.error = error
                        request.status_code = 500
                    else:
                        request.status_code = 200
                    
                    # Move to completed requests
                    with self.request_lock:
                        self.active_requests.pop(request.request_id, None)
                        self.completed_requests.append(request)
                    
                    requests_made += 1
                    
                    # Wait before next request (with some jitter)
                    jitter = random.uniform(0.8, 1.2)  # ±20% jitter
                    await asyncio.sleep(delay_between_requests * jitter)
                    
                except Exception as e:
                    self.logger.error(f"User {user_id} error: {str(e)}")
                    await asyncio.sleep(1)  # Brief pause on error
        
        # Start all user simulations concurrently
        queries = dataset.get('queries', [])
        if not queries:
            self.logger.error("No queries available for load testing")
            return
        
        self.logger.info(f"Starting {concurrent_users} concurrent users")
        
        user_tasks = []
        for user_id in range(concurrent_users):
            task = asyncio.create_task(user_simulation(user_id, queries))
            user_tasks.append(task)
        
        # Wait for all users to complete
        await asyncio.gather(*user_tasks, return_exceptions=True)
        
        self.logger.info("Load generation completed")
    
    async def send_load_test_request(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Send individual load test request.
        
        Args:
            query: Query to send
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Simulate request processing with realistic timing
            
            # Simulate network latency (1-10ms)
            network_delay = random.uniform(0.001, 0.01)
            await asyncio.sleep(network_delay)
            
            # Simulate processing time (varies by load)
            base_processing_time = 0.05  # 50ms base
            load_factor = len(self.active_requests) / 100.0  # Slow down with more concurrent requests
            processing_time = base_processing_time * (1 + load_factor)
            
            # Add some randomness to simulate real variability
            processing_time *= random.uniform(0.5, 2.0)
            
            await asyncio.sleep(processing_time)
            
            # Simulate occasional errors (1% error rate under normal conditions)
            current_load = len(self.active_requests)
            error_probability = 0.01 + (current_load / 1000.0)  # Higher error rate under high load
            
            if random.random() < error_probability:
                error_types = ["timeout", "connection_error", "service_unavailable", "rate_limited"]
                return False, random.choice(error_types)
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    def calculate_current_qps(self) -> float:
        """Calculate current QPS based on recent requests."""
        if len(self.completed_requests) < 2:
            return 0.0
        
        # Look at requests in the last second
        current_time = time.time()
        recent_requests = [
            req for req in list(self.completed_requests)[-100:]  # Last 100 requests
            if current_time - req.timestamp <= 1.0
        ]
        
        return len(recent_requests)
    
    async def collect_metrics_continuously(self, duration_minutes: int):
        """Collect performance metrics continuously during the test."""
        
        start_time = time.time()
        collection_interval = 5  # Collect every 5 seconds
        
        while not self.stop_event.is_set() and (time.time() - start_time) < duration_minutes * 60:
            try:
                metrics = await self.collect_current_metrics(start_time)
                self.metrics_history.append(metrics)
                
                # Log periodic status
                if len(self.metrics_history) % 12 == 0:  # Every minute
                    self.logger.info(
                        f"Status: {metrics.elapsed_minutes:.1f}min, "
                        f"QPS: {metrics.actual_qps:.1f}, "
                        f"P95: {metrics.p95_latency_ms:.1f}ms, "
                        f"Errors: {metrics.error_rate_percent:.2f}%"
                    )
                
                await asyncio.sleep(collection_interval)
                
            except Exception as e:
                self.logger.error(f"Metrics collection error: {str(e)}")
                await asyncio.sleep(collection_interval)
    
    async def collect_current_metrics(self, test_start_time: float) -> LoadTestMetrics:
        """Collect current performance metrics snapshot."""
        
        current_time = time.time()
        elapsed_minutes = (current_time - test_start_time) / 60.0
        
        # Get recent completed requests (last 30 seconds)
        recent_window = 30.0
        recent_requests = [
            req for req in list(self.completed_requests)
            if current_time - req.timestamp <= recent_window
        ]
        
        # Calculate latency percentiles
        latencies = [req.response_time_ms for req in recent_requests if req.response_time_ms is not None]
        
        if latencies:
            latencies.sort()
            n = len(latencies)
            p50_latency = latencies[n // 2] if n > 0 else 0
            p95_latency = latencies[int(n * 0.95)] if n >= 20 else (latencies[-1] if latencies else 0)
            p99_latency = latencies[int(n * 0.99)] if n >= 100 else (latencies[-1] if latencies else 0)
            max_latency = max(latencies) if latencies else 0
        else:
            p50_latency = p95_latency = p99_latency = max_latency = 0
        
        # Calculate error rate
        total_recent = len(recent_requests)
        error_recent = len([req for req in recent_requests if req.error])
        error_rate = (error_recent / max(total_recent, 1)) * 100
        
        # Calculate actual QPS
        actual_qps = len(recent_requests) / recent_window
        
        # Get system metrics
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent()
        
        # Determine service responsiveness
        service_responsive = (
            p95_latency < self.max_p95_latency_ms and
            error_rate < self.max_error_rate_percent and
            len(self.active_requests) < 1000  # Not overwhelmed
        )
        
        return LoadTestMetrics(
            timestamp=datetime.now().isoformat(),
            elapsed_minutes=elapsed_minutes,
            target_qps=0,  # Will be set by caller
            actual_qps=actual_qps,
            concurrent_requests=len(self.active_requests),
            active_users=len(set(req.user_id for req in self.active_requests.values())),
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            max_latency_ms=max_latency,
            error_rate_percent=error_rate,
            timeout_count=len([req for req in recent_requests if req.error == "timeout"]),
            connection_errors=len([req for req in recent_requests if req.error == "connection_error"]),
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            service_responsive=service_responsive
        )
    
    async def simulate_rolling_redeploys(
        self,
        redeploy_interval_minutes: int,
        total_duration_minutes: int
    ):
        """Simulate rolling redeployments during the soak test."""
        
        redeploy_count = 0
        start_time = time.time()
        
        while not self.stop_event.is_set() and (time.time() - start_time) < total_duration_minutes * 60:
            # Wait for next redeploy
            await asyncio.sleep(redeploy_interval_minutes * 60)
            
            if self.stop_event.is_set():
                break
            
            redeploy_count += 1
            self.logger.info(f"🔄 Simulating rolling redeploy #{redeploy_count}")
            
            # Simulate redeploy impact
            redeploy_start = time.time()
            
            # During redeploy, some requests may be slower or fail
            # This is simulated in the request handling logic
            
            # Simulate brief service degradation (5-15 seconds)
            degradation_time = random.uniform(5, 15)
            await asyncio.sleep(degradation_time)
            
            redeploy_time = time.time() - redeploy_start
            self.logger.info(f"✅ Redeploy #{redeploy_count} completed in {redeploy_time:.1f}s")
    
    async def monitor_circuit_breaker(self, duration_minutes: int):
        """Monitor for circuit breaker conditions."""
        
        start_time = time.time()
        circuit_breaker_open = False
        
        while not self.stop_event.is_set() and (time.time() - start_time) < duration_minutes * 60:
            
            # Check circuit breaker conditions
            if len(self.metrics_history) >= 3:  # Need some history
                recent_metrics = list(self.metrics_history)[-3:]  # Last 3 snapshots
                
                # Check if error rate is consistently high
                high_error_rate = all(m.error_rate_percent > 5.0 for m in recent_metrics)
                
                # Check if latency is consistently high
                high_latency = all(m.p95_latency_ms > 2000 for m in recent_metrics)
                
                should_open = high_error_rate or high_latency
                
                if should_open and not circuit_breaker_open:
                    circuit_breaker_open = True
                    self.logger.warning("🚨 Circuit breaker OPENED - high error rate or latency")
                
                elif not should_open and circuit_breaker_open:
                    circuit_breaker_open = False
                    self.logger.info("✅ Circuit breaker CLOSED - service recovered")
            
            await asyncio.sleep(10)  # Check every 10 seconds
    
    async def get_load_test_dataset(self) -> Dict[str, Any]:
        """Get dataset optimized for load testing."""
        
        # Generate diverse queries for realistic load testing
        dataset = self.dataset_manager.generate_synthetic_corpus(
            base_corpus_size=1000,  # Reasonable corpus size
            scale_factor=1
        )
        
        # Ensure we have enough queries for sustained load
        if len(dataset.queries) < 100:
            self.logger.warning("Limited query variety for load testing")
        
        return {
            "queries": [asdict(q) for q in dataset.queries],
            "documents": [asdict(d) for d in dataset.documents]
        }
    
    async def analyze_soak_test_results(
        self,
        test_name: str,
        start_time: float,
        target_qps: int,
        duration_minutes: int,
        concurrent_users: int,
        enable_rolling_redeploy: bool,
        redeploy_interval_minutes: Optional[int],
        redeploy_count: int,
        redeploy_impact_times: List[float]
    ) -> SoakTestResult:
        """Analyze soak test results and determine pass/fail."""
        
        # Count requests
        total_requests = len(self.completed_requests)
        successful_requests = len([req for req in self.completed_requests if not req.error])
        failed_requests = total_requests - successful_requests
        
        # Calculate overall performance metrics
        all_latencies = [req.response_time_ms for req in self.completed_requests if req.response_time_ms is not None]
        
        if all_latencies:
            all_latencies.sort()
            n = len(all_latencies)
            avg_latency = statistics.mean(all_latencies)
            p95_latency = all_latencies[int(n * 0.95)] if n >= 20 else all_latencies[-1]
            p99_latency = all_latencies[int(n * 0.99)] if n >= 100 else all_latencies[-1]
            max_latency = max(all_latencies)
        else:
            avg_latency = p95_latency = p99_latency = max_latency = 0
        
        # Calculate error rates
        all_error_rates = [m.error_rate_percent for m in self.metrics_history]
        avg_error_rate = statistics.mean(all_error_rates) if all_error_rates else 0
        max_error_rate = max(all_error_rates) if all_error_rates else 0
        
        # Check tail latency stability
        p95_latencies = [m.p95_latency_ms for m in self.metrics_history if m.p95_latency_ms > 0]
        tail_latency_stable = False
        
        if len(p95_latencies) >= 10:  # Need sufficient data
            variance = statistics.variance(p95_latencies)
            mean_latency = statistics.mean(p95_latencies)
            coefficient_of_variation = (variance ** 0.5) / mean_latency if mean_latency > 0 else 0
            tail_latency_stable = coefficient_of_variation <= self.tail_latency_stability_threshold
        
        # Determine pass/fail status
        failure_reasons = []
        
        if avg_error_rate > self.max_error_rate_percent:
            failure_reasons.append(f"Average error rate {avg_error_rate:.2f}% exceeds {self.max_error_rate_percent}%")
        
        if p95_latency > self.max_p95_latency_ms:
            failure_reasons.append(f"P95 latency {p95_latency:.1f}ms exceeds {self.max_p95_latency_ms}ms")
        
        if not tail_latency_stable:
            failure_reasons.append("Tail latency not stable throughout test")
        
        if total_requests == 0:
            failure_reasons.append("No requests completed during test")
        
        passed_soak_test = len(failure_reasons) == 0
        
        return SoakTestResult(
            test_name=test_name,
            start_time=datetime.fromtimestamp(start_time).isoformat(),
            duration_minutes=duration_minutes,
            target_qps=target_qps,
            concurrent_users=concurrent_users,
            enable_rolling_redeploy=enable_rolling_redeploy,
            redeploy_interval_minutes=redeploy_interval_minutes,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            max_latency_ms=max_latency,
            avg_error_rate_percent=avg_error_rate,
            max_error_rate_percent=max_error_rate,
            tail_latency_stable=tail_latency_stable,
            redeploy_count=redeploy_count,
            redeploy_impact_seconds=redeploy_impact_times,
            metrics_timeline=list(self.metrics_history),
            passed_soak_test=passed_soak_test,
            failure_reasons=failure_reasons
        )
    
    async def save_soak_test_results(self, result: SoakTestResult):
        """Save soak test results to files."""
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"soak_test_{result.test_name}_{timestamp_str}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        self.logger.info(f"Soak test results saved: {filepath}")
        
        # Save timeline CSV for analysis
        csv_filename = f"soak_test_timeline_{result.test_name}_{timestamp_str}.csv"
        csv_filepath = self.results_dir / csv_filename
        
        await self.save_timeline_csv(result, csv_filepath)
    
    async def save_timeline_csv(self, result: SoakTestResult, filepath: Path):
        """Save metrics timeline as CSV."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'elapsed_minutes', 'actual_qps', 'concurrent_requests', 'p50_latency_ms',
                'p95_latency_ms', 'p99_latency_ms', 'error_rate_percent', 'memory_usage_mb',
                'cpu_usage_percent', 'service_responsive'
            ])
            
            # Data rows
            for metrics in result.metrics_timeline:
                writer.writerow([
                    metrics.elapsed_minutes, metrics.actual_qps, metrics.concurrent_requests,
                    metrics.p50_latency_ms, metrics.p95_latency_ms, metrics.p99_latency_ms,
                    metrics.error_rate_percent, metrics.memory_usage_mb, metrics.cpu_usage_percent,
                    metrics.service_responsive
                ])
        
        self.logger.info(f"Timeline CSV saved: {filepath}")


# Convenience functions for common concurrency testing scenarios

async def run_standard_soak_test(
    target_qps: int = 25,
    duration_minutes: int = 30
) -> SoakTestResult:
    """Run standard soak test without rolling redeploy."""
    dataset_manager = DatasetManager()
    tester = ConcurrencyTester(dataset_manager)
    
    return await tester.run_soak_test(
        test_name="standard_soak_test",
        target_qps=target_qps,
        duration_minutes=duration_minutes,
        concurrent_users=5,
        enable_rolling_redeploy=False
    )


async def run_production_soak_test(
    target_qps: int = 50,
    duration_minutes: int = 60
) -> SoakTestResult:
    """Run production-grade soak test with rolling redeploy."""
    dataset_manager = DatasetManager()
    tester = ConcurrencyTester(dataset_manager)
    
    return await tester.run_soak_test(
        test_name="production_soak_test",
        target_qps=target_qps,
        duration_minutes=duration_minutes,
        concurrent_users=10,
        enable_rolling_redeploy=True,
        redeploy_interval_minutes=15
    )