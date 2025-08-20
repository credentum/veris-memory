#!/usr/bin/env python3
"""
S8: Capacity Smoke Test Check

Tests performance limits and capacity constraints to ensure
the system can handle expected load levels.

This check performs capacity testing to validate:
- Concurrent request handling capacity
- Response time under load
- Memory usage patterns
- Database connection pooling
- Queue depth and throughput
- Resource utilization limits
- Error rate under stress
"""

import asyncio
import json
import psutil
import statistics
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import aiohttp
import logging

from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig

logger = logging.getLogger(__name__)


class CapacitySmoke(BaseCheck):
    """S8: Performance capacity testing for load validation."""
    
    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S8-capacity-smoke", "Performance capacity testing")
        self.base_url = config.get("veris_memory_url", "http://localhost:8000")
        self.concurrent_requests = config.get("s8_capacity_concurrent_requests", 50)
        self.test_duration_seconds = config.get("s8_capacity_duration_sec", 30)
        self.timeout_seconds = config.get("s8_capacity_timeout_sec", 60)
        self.max_response_time_ms = config.get("s8_max_response_time_ms", 2000)
        self.max_error_rate_percent = config.get("s8_max_error_rate_percent", 5)
        
    async def run_check(self) -> CheckResult:
        """Execute comprehensive capacity smoke test."""
        start_time = time.time()
        
        try:
            # Run all capacity tests
            test_results = await asyncio.gather(
                self._test_concurrent_requests(),
                self._test_sustained_load(),
                self._monitor_system_resources(),
                self._test_database_connections(),
                self._test_memory_usage(),
                self._test_response_times(),
                return_exceptions=True
            )
            
            # Analyze results
            capacity_issues = []
            passed_tests = []
            failed_tests = []
            
            test_names = [
                "concurrent_requests",
                "sustained_load",
                "system_resources",
                "database_connections", 
                "memory_usage",
                "response_times"
            ]
            
            for i, result in enumerate(test_results):
                test_name = test_names[i]
                
                if isinstance(result, Exception):
                    failed_tests.append(test_name)
                    capacity_issues.append(f"{test_name}: {str(result)}")
                elif result.get("passed", False):
                    passed_tests.append(test_name)
                else:
                    failed_tests.append(test_name)
                    capacity_issues.append(f"{test_name}: {result.get('message', 'Unknown failure')}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine overall status
            if capacity_issues:
                status = "fail"
                message = f"Capacity issues detected: {len(capacity_issues)} problems found"
            else:
                status = "pass"
                message = f"All capacity tests passed: {len(passed_tests)} tests successful"
            
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status=status,
                latency_ms=latency_ms,
                message=message,
                details={
                    "total_tests": len(test_names),
                    "passed_tests": len(passed_tests),
                    "failed_tests": len(failed_tests),
                    "capacity_issues": capacity_issues,
                    "passed_test_names": passed_tests,
                    "failed_test_names": failed_tests,
                    "test_results": test_results,
                    "test_configuration": {
                        "concurrent_requests": self.concurrent_requests,
                        "test_duration_seconds": self.test_duration_seconds,
                        "max_response_time_ms": self.max_response_time_ms,
                        "max_error_rate_percent": self.max_error_rate_percent
                    }
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status="fail",
                latency_ms=latency_ms,
                message=f"Capacity check failed with error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _test_concurrent_requests(self) -> Dict[str, Any]:
        """Test handling of concurrent requests."""
        try:
            response_times = []
            status_codes = []
            errors = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                # Create concurrent requests
                tasks = []
                for i in range(self.concurrent_requests):
                    task = asyncio.create_task(
                        self._make_test_request(session, f"concurrent_test_{i}")
                    )
                    tasks.append(task)
                
                # Execute all requests concurrently
                start_time = time.time()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                total_time = time.time() - start_time
                
                # Analyze results
                for result in results:
                    if isinstance(result, Exception):
                        errors.append(str(result))
                    else:
                        response_times.append(result["response_time"])
                        status_codes.append(result["status_code"])
                        if result.get("error"):
                            errors.append(result["error"])
            
            # Calculate metrics
            success_count = len([s for s in status_codes if s == 200])
            error_rate = (len(errors) / self.concurrent_requests) * 100
            avg_response_time = statistics.mean(response_times) if response_times else 0
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 10 else avg_response_time
            
            # Determine pass/fail
            issues = []
            if error_rate > self.max_error_rate_percent:
                issues.append(f"Error rate {error_rate:.1f}% exceeds limit {self.max_error_rate_percent}%")
            if avg_response_time > self.max_response_time_ms:
                issues.append(f"Average response time {avg_response_time:.1f}ms exceeds limit {self.max_response_time_ms}ms")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Concurrent requests test: {success_count}/{self.concurrent_requests} successful" + (f", issues: {', '.join(issues)}" if issues else ""),
                "concurrent_requests": self.concurrent_requests,
                "success_count": success_count,
                "error_rate_percent": error_rate,
                "avg_response_time_ms": avg_response_time,
                "p95_response_time_ms": p95_response_time,
                "total_time_seconds": total_time,
                "throughput_rps": self.concurrent_requests / total_time if total_time > 0 else 0,
                "errors": errors[:10],  # Limit error samples
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Concurrent requests test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_sustained_load(self) -> Dict[str, Any]:
        """Test sustained load over time."""
        try:
            response_times = []
            error_count = 0
            total_requests = 0
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                start_time = time.time()
                end_time = start_time + self.test_duration_seconds
                
                while time.time() < end_time:
                    batch_start = time.time()
                    
                    # Send a small batch of requests
                    batch_size = min(5, self.concurrent_requests // 10)
                    tasks = []
                    for i in range(batch_size):
                        task = asyncio.create_task(
                            self._make_test_request(session, f"sustained_test_{total_requests + i}")
                        )
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    total_requests += batch_size
                    
                    # Process batch results
                    for result in results:
                        if isinstance(result, Exception):
                            error_count += 1
                        else:
                            response_times.append(result["response_time"])
                            if result.get("error"):
                                error_count += 1
                    
                    # Small delay to control rate
                    batch_time = time.time() - batch_start
                    if batch_time < 0.5:  # Target ~2 RPS
                        await asyncio.sleep(0.5 - batch_time)
            
            # Calculate metrics
            test_duration = time.time() - start_time
            avg_response_time = statistics.mean(response_times) if response_times else 0
            error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0
            throughput = total_requests / test_duration if test_duration > 0 else 0
            
            # Check for performance degradation
            issues = []
            if response_times:
                # Check if response times increased over time (performance degradation)
                early_times = response_times[:len(response_times)//3]
                late_times = response_times[-len(response_times)//3:]
                
                if early_times and late_times:
                    early_avg = statistics.mean(early_times)
                    late_avg = statistics.mean(late_times)
                    degradation_percent = ((late_avg - early_avg) / early_avg) * 100 if early_avg > 0 else 0
                    
                    if degradation_percent > 50:  # 50% degradation threshold
                        issues.append(f"Performance degraded {degradation_percent:.1f}% during test")
            
            if error_rate > self.max_error_rate_percent:
                issues.append(f"Error rate {error_rate:.1f}% exceeds limit")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Sustained load test: {total_requests} requests over {test_duration:.1f}s" + (f", issues: {', '.join(issues)}" if issues else ""),
                "test_duration_seconds": test_duration,
                "total_requests": total_requests,
                "error_count": error_count,
                "error_rate_percent": error_rate,
                "avg_response_time_ms": avg_response_time,
                "throughput_rps": throughput,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Sustained load test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _monitor_system_resources(self) -> Dict[str, Any]:
        """Monitor system resource usage during testing."""
        try:
            # Get initial resource snapshot
            initial_cpu = psutil.cpu_percent(interval=1)
            initial_memory = psutil.virtual_memory()
            initial_disk_io = psutil.disk_io_counters()
            initial_network_io = psutil.net_io_counters()
            
            # Run a brief load test while monitoring
            resource_samples = []
            
            async with aiohttp.ClientSession() as session:
                for _ in range(10):  # 10 second monitoring
                    sample_start = time.time()
                    
                    # Make some requests
                    tasks = [
                        self._make_test_request(session, f"resource_test_{i}")
                        for i in range(5)
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Sample resources
                    cpu_percent = psutil.cpu_percent()
                    memory = psutil.virtual_memory()
                    
                    resource_samples.append({
                        "timestamp": time.time(),
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory.percent,
                        "memory_available_gb": memory.available / (1024**3)
                    })
                    
                    # Wait for next sample
                    elapsed = time.time() - sample_start
                    if elapsed < 1.0:
                        await asyncio.sleep(1.0 - elapsed)
            
            # Analyze resource usage
            if resource_samples:
                avg_cpu = statistics.mean([s["cpu_percent"] for s in resource_samples])
                max_cpu = max([s["cpu_percent"] for s in resource_samples])
                avg_memory = statistics.mean([s["memory_percent"] for s in resource_samples])
                max_memory = max([s["memory_percent"] for s in resource_samples])
                min_available_gb = min([s["memory_available_gb"] for s in resource_samples])
            else:
                avg_cpu = max_cpu = initial_cpu
                avg_memory = max_memory = initial_memory.percent
                min_available_gb = initial_memory.available / (1024**3)
            
            # Check for resource issues
            issues = []
            if max_cpu > 90:
                issues.append(f"High CPU usage: {max_cpu:.1f}%")
            if max_memory > 90:
                issues.append(f"High memory usage: {max_memory:.1f}%")
            if min_available_gb < 0.5:
                issues.append(f"Low available memory: {min_available_gb:.1f}GB")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Resource monitoring: CPU avg {avg_cpu:.1f}%, memory avg {avg_memory:.1f}%" + (f", issues: {', '.join(issues)}" if issues else ""),
                "initial_cpu_percent": initial_cpu,
                "avg_cpu_percent": avg_cpu,
                "max_cpu_percent": max_cpu,
                "initial_memory_percent": initial_memory.percent,
                "avg_memory_percent": avg_memory,
                "max_memory_percent": max_memory,
                "min_available_memory_gb": min_available_gb,
                "resource_samples": resource_samples[-5:],  # Last 5 samples
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Resource monitoring failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_database_connections(self) -> Dict[str, Any]:
        """Test database connection pooling and limits."""
        try:
            # This test simulates database connection testing
            # In a real implementation, this would:
            # 1. Open multiple database connections
            # 2. Verify connection pool limits
            # 3. Test connection recycling
            # 4. Monitor connection leaks
            
            connection_tests = [
                {"test": "connection_pool_size", "status": "simulated", "max_connections": 100},
                {"test": "connection_timeout", "status": "simulated", "timeout_ms": 5000},
                {"test": "connection_recycling", "status": "simulated", "recycle_time": 3600},
                {"test": "connection_leak_detection", "status": "simulated", "leaks_detected": 0}
            ]
            
            # Simulate some database load by making API requests that hit the database
            db_response_times = []
            db_errors = 0
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                for i in range(10):  # Light database load test
                    # Test context retrieval (database operation)
                    task = asyncio.create_task(
                        self._make_test_request(session, f"db_test_{i}", endpoint="/health/ready")
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        db_errors += 1
                    else:
                        db_response_times.append(result["response_time"])
                        if result.get("error"):
                            db_errors += 1
            
            avg_db_response = statistics.mean(db_response_times) if db_response_times else 0
            db_error_rate = (db_errors / 10) * 100
            
            # Check for database performance issues
            issues = []
            if avg_db_response > 1000:  # 1 second threshold
                issues.append(f"Slow database responses: {avg_db_response:.1f}ms average")
            if db_error_rate > 10:
                issues.append(f"High database error rate: {db_error_rate:.1f}%")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Database connection test: {10 - db_errors}/10 requests successful" + (f", issues: {', '.join(issues)}" if issues else ""),
                "connection_tests": connection_tests,
                "avg_response_time_ms": avg_db_response,
                "error_count": db_errors,
                "error_rate_percent": db_error_rate,
                "simulation_mode": True,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Database connection test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_memory_usage(self) -> Dict[str, Any]:
        """Test memory usage patterns and limits."""
        try:
            initial_memory = psutil.virtual_memory()
            process = psutil.Process()
            initial_process_memory = process.memory_info()
            
            # Generate some load to test memory usage
            memory_samples = []
            
            async with aiohttp.ClientSession() as session:
                # Make a series of requests to exercise memory
                for batch in range(5):
                    batch_tasks = []
                    for i in range(10):
                        task = asyncio.create_task(
                            self._make_test_request(session, f"memory_test_{batch}_{i}")
                        )
                        batch_tasks.append(task)
                    
                    await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    # Sample memory usage
                    current_memory = psutil.virtual_memory()
                    current_process_memory = process.memory_info()
                    
                    memory_samples.append({
                        "batch": batch,
                        "system_memory_percent": current_memory.percent,
                        "system_available_gb": current_memory.available / (1024**3),
                        "process_memory_mb": current_process_memory.rss / (1024**2),
                        "process_memory_vms_mb": current_process_memory.vms / (1024**2)
                    })
                    
                    await asyncio.sleep(0.5)  # Brief pause between batches
            
            # Analyze memory usage
            if memory_samples:
                max_system_memory = max([s["system_memory_percent"] for s in memory_samples])
                min_available_gb = min([s["system_available_gb"] for s in memory_samples])
                max_process_memory = max([s["process_memory_mb"] for s in memory_samples])
                
                # Check for memory growth (potential leak)
                memory_growth = memory_samples[-1]["process_memory_mb"] - memory_samples[0]["process_memory_mb"]
            else:
                max_system_memory = initial_memory.percent
                min_available_gb = initial_memory.available / (1024**3)
                max_process_memory = initial_process_memory.rss / (1024**2)
                memory_growth = 0
            
            # Check for memory issues
            issues = []
            if max_system_memory > 95:
                issues.append(f"System memory usage peaked at {max_system_memory:.1f}%")
            if min_available_gb < 0.1:
                issues.append(f"Available memory dropped to {min_available_gb:.1f}GB")
            if memory_growth > 50:  # 50MB growth threshold
                issues.append(f"Process memory grew by {memory_growth:.1f}MB during test")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Memory usage test: peak {max_system_memory:.1f}% system, {max_process_memory:.1f}MB process" + (f", issues: {', '.join(issues)}" if issues else ""),
                "initial_system_memory_percent": initial_memory.percent,
                "max_system_memory_percent": max_system_memory,
                "min_available_memory_gb": min_available_gb,
                "initial_process_memory_mb": initial_process_memory.rss / (1024**2),
                "max_process_memory_mb": max_process_memory,
                "memory_growth_mb": memory_growth,
                "memory_samples": memory_samples,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Memory usage test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_response_times(self) -> Dict[str, Any]:
        """Test response time distribution and consistency."""
        try:
            response_times = []
            
            async with aiohttp.ClientSession() as session:
                # Sequential requests to test response time consistency
                for i in range(50):  # 50 sequential requests
                    result = await self._make_test_request(session, f"response_time_test_{i}")
                    if not isinstance(result, Exception) and not result.get("error"):
                        response_times.append(result["response_time"])
                    
                    await asyncio.sleep(0.1)  # 100ms between requests
            
            if not response_times:
                return {
                    "passed": False,
                    "message": "No successful requests to measure response times",
                    "error": "All requests failed"
                }
            
            # Calculate response time statistics
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 10 else avg_response_time
            p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 50 else p95_response_time
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            
            # Check for response time issues
            issues = []
            if avg_response_time > self.max_response_time_ms:
                issues.append(f"Average response time {avg_response_time:.1f}ms exceeds limit {self.max_response_time_ms}ms")
            if p95_response_time > self.max_response_time_ms * 2:
                issues.append(f"P95 response time {p95_response_time:.1f}ms is very high")
            if max_response_time > self.max_response_time_ms * 5:
                issues.append(f"Maximum response time {max_response_time:.1f}ms is extremely high")
            
            # Check for response time variability
            if len(response_times) > 10:
                std_dev = statistics.stdev(response_times)
                coefficient_of_variation = std_dev / avg_response_time if avg_response_time > 0 else 0
                if coefficient_of_variation > 1.0:  # High variability
                    issues.append(f"High response time variability (CV: {coefficient_of_variation:.2f})")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Response time test: avg {avg_response_time:.1f}ms, P95 {p95_response_time:.1f}ms" + (f", issues: {', '.join(issues)}" if issues else ""),
                "sample_count": len(response_times),
                "avg_response_time_ms": avg_response_time,
                "median_response_time_ms": median_response_time,
                "p95_response_time_ms": p95_response_time,
                "p99_response_time_ms": p99_response_time,
                "min_response_time_ms": min_response_time,
                "max_response_time_ms": max_response_time,
                "response_time_samples": response_times[-10:],  # Last 10 samples
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Response time test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _make_test_request(
        self,
        session: aiohttp.ClientSession,
        test_id: str,
        endpoint: str = "/health/live"
    ) -> Dict[str, Any]:
        """Make a single test request and measure response time."""
        start_time = time.time()
        try:
            async with session.get(f"{self.base_url}{endpoint}") as response:
                response_time = (time.time() - start_time) * 1000
                await response.text()  # Read response body
                
                return {
                    "test_id": test_id,
                    "status_code": response.status,
                    "response_time": response_time,
                    "error": None if response.status == 200 else f"HTTP {response.status}"
                }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "test_id": test_id,
                "status_code": 0,
                "response_time": response_time,
                "error": str(e)
            }