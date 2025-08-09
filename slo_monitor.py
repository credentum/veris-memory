#!/usr/bin/env python3
"""
SLO Monitor - Production Service Level Objectives
Tracks: Recovery ≥95%, Latency P95 ≤300ms, Error Rate ≤0.5%, Index Freshness ≤1s
"""

import time
import json
import asyncio
import logging
import statistics
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SLOMetrics:
    """SLO compliance metrics"""
    timestamp: str
    recovery_rate: float          # Target: ≥0.95
    latency_p95_ms: float        # Target: ≤300
    error_rate: float            # Target: ≤0.005
    index_freshness_ms: float    # Target: ≤1000
    slo_compliance_score: float  # Overall compliance (0-1)

class SLOMonitor:
    """Production SLO monitoring and alerting"""
    
    # SLO Thresholds
    TARGET_RECOVERY_RATE = 0.95      # ≥95% in top-5
    TARGET_P95_LATENCY_MS = 300      # ≤300ms P95 latency
    TARGET_ERROR_RATE = 0.005        # ≤0.5% error rate  
    TARGET_INDEX_FRESHNESS_MS = 1000 # ≤1s post-upsert visibility
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics_history: List[SLOMetrics] = []
        
        # Known-answer test set for recovery measurement
        self.known_answers = [
            {"query": "machine learning best practices", "expected_results": 3},
            {"query": "API design patterns", "expected_results": 3},
            {"query": "database optimization", "expected_results": 3},
            {"query": "microservices architecture", "expected_results": 3},
            {"query": "performance tuning", "expected_results": 3}
        ]
    
    async def measure_recovery_rate(self) -> float:
        """Measure recovery rate using known-answer test set"""
        import requests
        
        successful_queries = 0
        total_queries = len(self.known_answers)
        
        for test_case in self.known_answers:
            try:
                response = requests.post(
                    f"{self.base_url}/tools/retrieve_context",
                    json={"query": test_case["query"], "limit": 5},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    results = result.get("results", [])
                    
                    # Success if we get expected number of results in top-5
                    if len(results) >= min(test_case["expected_results"], 5):
                        successful_queries += 1
                        
            except Exception as e:
                logger.warning(f"Recovery test failed for '{test_case['query']}': {e}")
                continue
        
        recovery_rate = successful_queries / total_queries if total_queries > 0 else 0
        logger.info(f"📈 Recovery rate: {recovery_rate:.1%} ({successful_queries}/{total_queries})")
        return recovery_rate
    
    async def measure_latency_distribution(self) -> Dict[str, float]:
        """Measure latency distribution across test queries"""
        import requests
        
        latencies = []
        
        for test_case in self.known_answers:
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.base_url}/tools/retrieve_context",
                    json={"query": test_case["query"], "limit": 5},
                    timeout=10
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    latencies.append(latency_ms)
                    
            except Exception as e:
                logger.warning(f"Latency test failed for '{test_case['query']}': {e}")
                continue
        
        if latencies:
            p50 = statistics.median(latencies)
            p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 10 else max(latencies)
            p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 50 else max(latencies)
            
            logger.info(f"⏱️ Latency P50: {p50:.1f}ms, P95: {p95:.1f}ms, P99: {p99:.1f}ms")
            
            return {"p50": p50, "p95": p95, "p99": p99}
        else:
            return {"p50": 0, "p95": 0, "p99": 0}
    
    async def measure_error_rate(self) -> float:
        """Measure error rate across test operations"""
        import requests
        
        total_requests = 0
        error_requests = 0
        
        # Test various operations
        operations = [
            ("retrieve", {"query": "test query", "limit": 5}),
            ("store", {
                "type": "design", 
                "content": {"title": "SLO Test", "description": "Error rate measurement"},
                "metadata": {"slo_test": True}
            })
        ]
        
        for op_name, payload in operations:
            for _ in range(5):  # 5 requests per operation type
                try:
                    total_requests += 1
                    
                    if op_name == "retrieve":
                        endpoint = "/tools/retrieve_context"
                    else:
                        endpoint = "/tools/store_context"
                    
                    response = requests.post(
                        f"{self.base_url}{endpoint}",
                        json=payload,
                        timeout=10
                    )
                    
                    # Count 4xx/5xx as errors
                    if response.status_code >= 400:
                        error_requests += 1
                    else:
                        # Check for application-level errors
                        result = response.json()
                        if not result.get("success", True):
                            error_requests += 1
                            
                except Exception:
                    error_requests += 1
                
                # Small delay between requests
                await asyncio.sleep(0.1)
        
        error_rate = error_requests / total_requests if total_requests > 0 else 0
        logger.info(f"❌ Error rate: {error_rate:.1%} ({error_requests}/{total_requests})")
        return error_rate
    
    async def measure_index_freshness(self) -> float:
        """Measure index freshness (store-to-search latency)"""
        import requests
        
        test_content = {
            "type": "trace",
            "content": {
                "title": f"INDEX_FRESHNESS_TEST_{int(time.time())}",
                "description": "Measuring index freshness for SLO compliance"
            },
            "metadata": {"freshness_test": True}
        }
        
        try:
            # Store content
            store_start = time.time()
            store_response = requests.post(
                f"{self.base_url}/tools/store_context",
                json=test_content,
                timeout=10
            )
            
            if store_response.status_code != 200:
                logger.warning("Store failed in freshness test")
                return 9999  # High value to indicate failure
            
            store_result = store_response.json()
            if not store_result.get("success"):
                logger.warning("Store unsuccessful in freshness test")
                return 9999
            
            # Immediately try to search for it
            search_query = test_content["content"]["title"]
            
            max_attempts = 10
            for attempt in range(max_attempts):
                search_response = requests.post(
                    f"{self.base_url}/tools/retrieve_context",
                    json={"query": search_query, "limit": 3},
                    timeout=5
                )
                
                if search_response.status_code == 200:
                    search_result = search_response.json()
                    results = search_result.get("results", [])
                    
                    # Check if our content is found
                    for result in results:
                        content = result.get("payload", {}).get("content", {})
                        if isinstance(content, dict) and content.get("title") == test_content["content"]["title"]:
                            freshness_ms = (time.time() - store_start) * 1000
                            logger.info(f"🔄 Index freshness: {freshness_ms:.1f}ms")
                            return freshness_ms
                
                # Wait before retry
                await asyncio.sleep(0.1)
            
            # If we get here, content wasn't found within reasonable time
            logger.warning("Content not found in freshness test - index may be slow")
            return 9999
            
        except Exception as e:
            logger.warning(f"Index freshness test failed: {e}")
            return 9999
    
    async def collect_metrics(self) -> SLOMetrics:
        """Collect all SLO metrics"""
        logger.info("📊 Collecting SLO metrics...")
        
        start_time = time.time()
        
        # Collect all metrics in parallel where possible
        recovery_task = asyncio.create_task(self.measure_recovery_rate())
        latency_task = asyncio.create_task(self.measure_latency_distribution()) 
        error_task = asyncio.create_task(self.measure_error_rate())
        freshness_task = asyncio.create_task(self.measure_index_freshness())
        
        # Wait for completion
        recovery_rate = await recovery_task
        latency_dist = await latency_task
        error_rate = await error_task
        index_freshness_ms = await freshness_task
        
        # Calculate SLO compliance score (0-1)
        recovery_score = min(recovery_rate / self.TARGET_RECOVERY_RATE, 1.0)
        latency_score = min(self.TARGET_P95_LATENCY_MS / max(latency_dist["p95"], 1), 1.0)
        error_score = min(self.TARGET_ERROR_RATE / max(error_rate, 0.001), 1.0)
        freshness_score = min(self.TARGET_INDEX_FRESHNESS_MS / max(index_freshness_ms, 1), 1.0)
        
        # Weighted overall score
        slo_compliance_score = (
            recovery_score * 0.4 +      # Recovery most important 
            latency_score * 0.3 +       # Latency second
            freshness_score * 0.2 +     # Freshness third
            error_score * 0.1           # Error rate fourth
        )
        
        metrics = SLOMetrics(
            timestamp=datetime.now().isoformat(),
            recovery_rate=recovery_rate,
            latency_p95_ms=latency_dist["p95"],
            error_rate=error_rate,
            index_freshness_ms=index_freshness_ms,
            slo_compliance_score=slo_compliance_score
        )
        
        # Store in history
        self.metrics_history.append(metrics)
        
        # Keep only last 100 measurements
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        collection_time = time.time() - start_time
        logger.info(f"📊 Metrics collected in {collection_time:.1f}s, SLO score: {slo_compliance_score:.1%}")
        
        return metrics
    
    def generate_slo_report(self) -> Dict[str, Any]:
        """Generate comprehensive SLO compliance report"""
        if not self.metrics_history:
            return {"error": "No metrics data available"}
        
        latest = self.metrics_history[-1]
        
        # Calculate trends (last 10 measurements)
        recent_metrics = self.metrics_history[-10:]
        
        avg_recovery = statistics.mean([m.recovery_rate for m in recent_metrics])
        avg_latency = statistics.mean([m.latency_p95_ms for m in recent_metrics]) 
        avg_error_rate = statistics.mean([m.error_rate for m in recent_metrics])
        avg_freshness = statistics.mean([m.index_freshness_ms for m in recent_metrics])
        
        # SLO compliance checks
        slo_status = {
            "recovery": {
                "current": latest.recovery_rate,
                "target": self.TARGET_RECOVERY_RATE,
                "compliant": latest.recovery_rate >= self.TARGET_RECOVERY_RATE,
                "trend_avg": avg_recovery
            },
            "latency_p95": {
                "current": latest.latency_p95_ms,
                "target": self.TARGET_P95_LATENCY_MS,
                "compliant": latest.latency_p95_ms <= self.TARGET_P95_LATENCY_MS,
                "trend_avg": avg_latency
            },
            "error_rate": {
                "current": latest.error_rate,
                "target": self.TARGET_ERROR_RATE,
                "compliant": latest.error_rate <= self.TARGET_ERROR_RATE,
                "trend_avg": avg_error_rate
            },
            "index_freshness": {
                "current": latest.index_freshness_ms,
                "target": self.TARGET_INDEX_FRESHNESS_MS,
                "compliant": latest.index_freshness_ms <= self.TARGET_INDEX_FRESHNESS_MS,
                "trend_avg": avg_freshness
            }
        }
        
        # Overall compliance
        compliant_slos = sum(1 for slo in slo_status.values() if slo["compliant"])
        total_slos = len(slo_status)
        overall_compliance = compliant_slos / total_slos
        
        report = {
            "timestamp": latest.timestamp,
            "overall_compliance": overall_compliance,
            "slo_score": latest.slo_compliance_score,
            "compliant_slos": compliant_slos,
            "total_slos": total_slos,
            "status": "HEALTHY" if overall_compliance >= 0.75 else "DEGRADED",
            "slo_details": slo_status,
            "metrics_history_count": len(self.metrics_history)
        }
        
        return report


# CLI interface
async def main():
    """CLI entry point for SLO monitoring"""
    import sys
    
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    monitor = SLOMonitor(base_url=base_url)
    
    if len(sys.argv) > 2 and sys.argv[2] == "continuous":
        # Continuous monitoring mode
        logger.info("Starting continuous SLO monitoring...")
        while True:
            try:
                await monitor.collect_metrics()
                report = monitor.generate_slo_report()
                print(json.dumps(report, indent=2))
                await asyncio.sleep(300)  # 5-minute intervals
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"SLO monitoring error: {e}")
                await asyncio.sleep(60)
    else:
        # Single measurement
        metrics = await monitor.collect_metrics()
        report = monitor.generate_slo_report()
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    asyncio.run(main())