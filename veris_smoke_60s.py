#!/usr/bin/env python3
"""
Veris 60-Second Production Smoke Test Suite
Daily production smoke: health, write→read, paraphrase, index freshness
"""

import asyncio
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import requests
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@dataclass
class SmokeTestResult:
    """Individual smoke test result"""
    id: str
    name: str
    status: str  # pass, fail, skip
    latency_ms: float
    metrics: Dict[str, Any]
    error: Optional[str] = None

@dataclass
class SmokeSummary:
    """Overall smoke test summary"""
    overall_status: str  # pass, fail
    p95_latency_ms: float
    error_rate_pct: float
    recovery_top1_pct: float
    index_freshness_s: float
    failed_tests: List[str]

@dataclass
class SmokeThresholds:
    """SLO thresholds for smoke tests"""
    p95_latency_ms: float = 300
    error_rate_pct: float = 0.5
    recovery_top1_pct: float = 95
    index_freshness_s: float = 1.0

class VerisSmokeTestSuite:
    """60-second production smoke test suite"""
    
    def __init__(self, 
                 base_url: str = "http://localhost:8000",
                 env: str = "local",
                 timeout_ms: int = 60000):
        self.base_url = base_url
        self.env = env
        self.timeout_ms = timeout_ms
        
        # Configuration from schema
        self.config = {
            "RERANKER_ENABLED": True,
            "RERANK_TOP_K": 10,
            "HYBRID_ALPHA": 0.7,
            "HYBRID_BETA": 0.3,
            "QDRANT_WAIT_WRITES": True,
            "TIMEOUT_MS": timeout_ms,
            "NAMESPACE": "smoke",
            "TTL_SECONDS": 120
        }
        
        self.thresholds = SmokeThresholds()
        self.results: List[SmokeTestResult] = []
        self.suite_start_time = time.time()
        
        # Generate unique identifiers
        self.run_id = f"smoke-{datetime.now(timezone.utc).isoformat()}"
        self.needle_doc = {
            "title": "Smoke Needle",
            "text": "Microservices architecture improves scalability and team autonomy.",
            "type": "design",
            "metadata": {
                "namespace": self.config["NAMESPACE"],
                "ttl_seconds": self.config["TTL_SECONDS"],
                "smoke_test": True
            }
        }
        
        logger.info(f"Initialized Veris smoke suite: {self.run_id}")
        logger.info(f"Target environment: {self.env}")
        logger.info(f"Timeout: {timeout_ms}ms")
    
    def _check_timeout(self) -> bool:
        """Check if suite timeout exceeded"""
        elapsed_ms = (time.time() - self.suite_start_time) * 1000
        return elapsed_ms >= self.timeout_ms
    
    async def sm1_health_probe(self) -> SmokeTestResult:
        """SM-1: Health probe"""
        start_time = time.time()
        test_id = "SM-1"
        
        try:
            logger.info(f"Running {test_id}: Health probe")
            
            response = requests.get(f"{self.base_url}/health", timeout=5)
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                health_data = response.json()
                
                # Check for expected dependencies (ignore graph as specified)
                deps_ok = health_data.get("dependencies", {})
                qdrant_ok = deps_ok.get("qdrant", False)
                redis_ok = deps_ok.get("redis", False)
                
                success = qdrant_ok and redis_ok
                status = "pass" if success else "fail"
                error = None if success else f"Dependencies not OK: qdrant={qdrant_ok}, redis={redis_ok}"
                
            else:
                status = "fail" 
                error = f"HTTP {response.status_code}"
            
            return SmokeTestResult(
                id=test_id,
                name="Health probe",
                status=status,
                latency_ms=latency_ms,
                metrics={"http_status": response.status_code},
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="Health probe", 
                status="fail",
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    async def sm2_store_index_count(self) -> SmokeTestResult:
        """SM-2: Store → index → count"""
        start_time = time.time()
        test_id = "SM-2"
        
        try:
            logger.info(f"Running {test_id}: Store → index → count")
            
            # Get initial count
            count_response = requests.get(
                f"{self.base_url}/admin/count",
                params={"namespace": self.config["NAMESPACE"]},
                timeout=3
            )
            initial_count = count_response.json().get("count", 0) if count_response.status_code == 200 else 0
            
            # Store the needle document
            store_response = requests.post(
                f"{self.base_url}/tools/store_context",
                json=self.needle_doc,
                timeout=5
            )
            
            if store_response.status_code != 200:
                raise Exception(f"Store failed: {store_response.status_code}")
            
            store_result = store_response.json()
            if not store_result.get("success", True):
                raise Exception(f"Store unsuccessful: {store_result.get('message')}")
            
            # Wait briefly for indexing (wait=true should make this immediate)
            await asyncio.sleep(0.1)
            
            # Check final count
            final_count_response = requests.get(
                f"{self.base_url}/admin/count",
                params={"namespace": self.config["NAMESPACE"]},
                timeout=3
            )
            
            final_count = final_count_response.json().get("count", 0) if final_count_response.status_code == 200 else 0
            count_increase = final_count - initial_count
            
            latency_ms = (time.time() - start_time) * 1000
            
            success = count_increase == 1
            status = "pass" if success else "fail"
            error = None if success else f"Count increased by {count_increase}, expected 1"
            
            return SmokeTestResult(
                id=test_id,
                name="Store → index → count",
                status=status,
                latency_ms=latency_ms,
                metrics={"count_increase": count_increase, "final_count": final_count},
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="Store → index → count",
                status="fail", 
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    async def sm3_needle_retrieval(self) -> SmokeTestResult:
        """SM-3: Needle retrieval (semantic)"""
        start_time = time.time()
        test_id = "SM-3"
        
        try:
            logger.info(f"Running {test_id}: Needle retrieval")
            
            query = "What are the benefits of microservices?"
            
            response = requests.post(
                f"{self.base_url}/tools/retrieve_context",
                json={
                    "query": query,
                    "limit": 5,
                    "filters": {"namespace": self.config["NAMESPACE"]}
                },
                timeout=5
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                raise Exception(f"Retrieve failed: {response.status_code}")
            
            result = response.json()
            if not result.get("success", True):
                raise Exception(f"Retrieve unsuccessful: {result.get('message')}")
            
            results = result.get("results", [])
            
            # Check if top result is our needle
            top_result = results[0] if results else None
            precision_at_1 = 0.0
            score_top1 = 0.0
            score_gap = 0.0
            
            if top_result:
                score_top1 = top_result.get("score", 0.0)
                
                # Check if this is our needle document
                payload = top_result.get("payload", {})
                content = payload.get("content", {})
                title = content.get("title", "")
                
                if "Smoke Needle" in title:
                    precision_at_1 = 1.0
                
                # Calculate score gap to second result
                if len(results) > 1:
                    score_top2 = results[1].get("score", 0.0)
                    score_gap = score_top1 - score_top2
            
            success = precision_at_1 >= 1.0
            status = "pass" if success else "fail"
            error = None if success else f"Top result is not smoke needle (precision@1={precision_at_1})"
            
            return SmokeTestResult(
                id=test_id,
                name="Needle retrieval (semantic)",
                status=status,
                latency_ms=latency_ms,
                metrics={
                    "precision_at_1": precision_at_1,
                    "score_top1": score_top1,
                    "score_gap_top1_top2": score_gap,
                    "results_count": len(results)
                },
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="Needle retrieval (semantic)",
                status="fail",
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    async def sm4_paraphrase_robustness(self) -> SmokeTestResult:
        """SM-4: Paraphrase robustness (MQE-lite)"""
        start_time = time.time()
        test_id = "SM-4"
        
        try:
            logger.info(f"Running {test_id}: Paraphrase robustness")
            
            paraphrases = [
                "Why do teams choose microservices?",
                "Key advantages of a microservice approach?"
            ]
            
            needle_found_in_paraphrases = 0
            total_paraphrases = len(paraphrases)
            
            for paraphrase in paraphrases:
                response = requests.post(
                    f"{self.base_url}/tools/retrieve_context",
                    json={
                        "query": paraphrase,
                        "limit": 3,
                        "filters": {"namespace": self.config["NAMESPACE"]}
                    },
                    timeout=3
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", True):
                        results = result.get("results", [])
                        
                        # Check if needle is in top results
                        for res in results:
                            payload = res.get("payload", {})
                            content = payload.get("content", {})
                            title = content.get("title", "")
                            
                            if "Smoke Needle" in title:
                                needle_found_in_paraphrases += 1
                                break
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Success if needle found in at least one paraphrase
            success = needle_found_in_paraphrases > 0
            precision_at_1 = needle_found_in_paraphrases / total_paraphrases
            
            status = "pass" if success else "fail"
            error = None if success else f"Needle not found in any paraphrase ({needle_found_in_paraphrases}/{total_paraphrases})"
            
            return SmokeTestResult(
                id=test_id,
                name="Paraphrase robustness (MQE-lite)",
                status=status,
                latency_ms=latency_ms,
                metrics={
                    "precision_at_1": precision_at_1,
                    "paraphrases_passed": needle_found_in_paraphrases,
                    "total_paraphrases": total_paraphrases
                },
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="Paraphrase robustness (MQE-lite)",
                status="fail",
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    async def sm5_index_freshness(self) -> SmokeTestResult:
        """SM-5: Index freshness (visibility < 1s)"""
        start_time = time.time()
        test_id = "SM-5"
        
        try:
            logger.info(f"Running {test_id}: Index freshness")
            
            # Query for our needle immediately after store (should be visible due to wait=true)
            response = requests.post(
                f"{self.base_url}/tools/retrieve_context",
                json={
                    "query": "Microservices architecture improves scalability",
                    "limit": 3,
                    "filters": {"namespace": self.config["NAMESPACE"]}
                },
                timeout=3
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                raise Exception(f"Freshness check failed: {response.status_code}")
            
            result = response.json()
            if not result.get("success", True):
                raise Exception(f"Freshness check unsuccessful: {result.get('message')}")
            
            results = result.get("results", [])
            
            # Check if needle is visible (should be immediate with wait=true)
            needle_visible = False
            for res in results:
                payload = res.get("payload", {})
                content = payload.get("content", {})
                title = content.get("title", "")
                
                if "Smoke Needle" in title:
                    needle_visible = True
                    break
            
            # Since we use wait=true, visibility should be immediate (<< 1s)
            visible_under_seconds = latency_ms / 1000.0
            
            success = needle_visible and visible_under_seconds <= self.thresholds.index_freshness_s
            status = "pass" if success else "fail"
            
            if not needle_visible:
                error = "Needle not visible after store"
            elif visible_under_seconds > self.thresholds.index_freshness_s:
                error = f"Visibility time {visible_under_seconds:.3f}s > {self.thresholds.index_freshness_s}s"
            else:
                error = None
            
            return SmokeTestResult(
                id=test_id,
                name="Index freshness",
                status=status,
                latency_ms=latency_ms,
                metrics={
                    "visible_under_seconds": visible_under_seconds,
                    "needle_visible": needle_visible
                },
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="Index freshness",
                status="fail",
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    async def sm6_slo_spot_check(self) -> SmokeTestResult:
        """SM-6: SLO spot-check"""
        start_time = time.time()
        test_id = "SM-6"
        
        try:
            logger.info(f"Running {test_id}: SLO spot-check")
            
            # Evaluate metrics from previous tests
            latencies = [r.latency_ms for r in self.results if r.status != "skip"]
            
            if not latencies:
                raise Exception("No latency data from previous tests")
            
            # Calculate P95 latency
            latencies_sorted = sorted(latencies)
            p95_index = min(int(len(latencies_sorted) * 0.95), len(latencies_sorted) - 1)
            p95_latency_ms = latencies_sorted[p95_index]
            
            # Calculate error rate
            failed_tests = [r for r in self.results if r.status == "fail"]
            total_tests = [r for r in self.results if r.status != "skip"]
            error_rate_pct = (len(failed_tests) / max(len(total_tests), 1)) * 100
            
            # Recovery rate (based on needle retrieval success)
            needle_test = next((r for r in self.results if r.id == "SM-3"), None)
            recovery_top1 = needle_test.metrics.get("precision_at_1", 0.0) * 100 if needle_test else 0.0
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Check SLO compliance
            slo_checks = [
                p95_latency_ms <= self.thresholds.p95_latency_ms,
                error_rate_pct <= self.thresholds.error_rate_pct,
                recovery_top1 >= self.thresholds.recovery_top1_pct
            ]
            
            success = all(slo_checks)
            status = "pass" if success else "fail"
            
            failed_slos = []
            if p95_latency_ms > self.thresholds.p95_latency_ms:
                failed_slos.append(f"P95 latency {p95_latency_ms:.1f}ms > {self.thresholds.p95_latency_ms}ms")
            if error_rate_pct > self.thresholds.error_rate_pct:
                failed_slos.append(f"Error rate {error_rate_pct:.1f}% > {self.thresholds.error_rate_pct}%")
            if recovery_top1 < self.thresholds.recovery_top1_pct:
                failed_slos.append(f"Recovery {recovery_top1:.1f}% < {self.thresholds.recovery_top1_pct}%")
            
            error = "; ".join(failed_slos) if failed_slos else None
            
            return SmokeTestResult(
                id=test_id,
                name="SLO spot-check",
                status=status,
                latency_ms=latency_ms,
                metrics={
                    "p95_latency_ms": p95_latency_ms,
                    "error_rate_pct": error_rate_pct,
                    "recovery_top1": recovery_top1
                },
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="SLO spot-check",
                status="fail",
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    async def sm7_graph_ro_sanity(self) -> SmokeTestResult:
        """SM-7: Graph RO sanity (optional)"""
        start_time = time.time()
        test_id = "SM-7"
        
        try:
            logger.info(f"Running {test_id}: Graph RO sanity (optional)")
            
            response = requests.post(
                f"{self.base_url}/tools/query_graph",
                json={
                    "query": "RETURN 1 AS ok",
                    "parameters": {},
                    "limit": 1
                },
                timeout=3
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                # Graph might not be available - mark as skip rather than fail
                return SmokeTestResult(
                    id=test_id,
                    name="Graph RO sanity (optional)",
                    status="skip",
                    latency_ms=latency_ms,
                    metrics={},
                    error=f"Graph endpoint unavailable: {response.status_code}"
                )
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                results = result.get("results", [])
                ro_read_ok = len(results) > 0 and results[0].get("ok") == 1
            else:
                ro_read_ok = False
            
            status = "pass" if ro_read_ok else "fail"
            error = None if ro_read_ok else f"Graph read failed: {result.get('error', 'Unknown error')}"
            
            return SmokeTestResult(
                id=test_id,
                name="Graph RO sanity (optional)",
                status=status,
                latency_ms=latency_ms,
                metrics={"ro_read_ok": ro_read_ok},
                error=error
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                id=test_id,
                name="Graph RO sanity (optional)",
                status="skip",  # Optional test - don't fail suite
                latency_ms=latency_ms,
                metrics={},
                error=str(e)
            )
    
    def _calculate_summary(self) -> SmokeSummary:
        """Calculate overall summary from test results"""
        
        # Get metrics from SLO test if available
        slo_test = next((r for r in self.results if r.id == "SM-6"), None)
        
        if slo_test and slo_test.status == "pass":
            p95_latency_ms = slo_test.metrics.get("p95_latency_ms", 0)
            error_rate_pct = slo_test.metrics.get("error_rate_pct", 0)
            recovery_top1_pct = slo_test.metrics.get("recovery_top1", 0)
        else:
            # Fallback calculations
            latencies = [r.latency_ms for r in self.results if r.status != "skip"]
            p95_latency_ms = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
            
            failed_tests = [r for r in self.results if r.status == "fail"]
            total_tests = [r for r in self.results if r.status != "skip"]
            error_rate_pct = (len(failed_tests) / max(len(total_tests), 1)) * 100
            
            needle_test = next((r for r in self.results if r.id == "SM-3"), None)
            recovery_top1_pct = needle_test.metrics.get("precision_at_1", 0) * 100 if needle_test else 0
        
        # Get index freshness
        freshness_test = next((r for r in self.results if r.id == "SM-5"), None)
        index_freshness_s = freshness_test.metrics.get("visible_under_seconds", 999) if freshness_test else 999
        
        # List failed tests (excluding optional skipped tests)
        failed_tests = [r.id for r in self.results if r.status == "fail"]
        
        # Overall status
        critical_tests = [r for r in self.results if r.id != "SM-7"]  # Exclude optional graph test
        overall_status = "pass" if all(r.status == "pass" for r in critical_tests) else "fail"
        
        return SmokeSummary(
            overall_status=overall_status,
            p95_latency_ms=p95_latency_ms,
            error_rate_pct=error_rate_pct,
            recovery_top1_pct=recovery_top1_pct,
            index_freshness_s=index_freshness_s,
            failed_tests=failed_tests
        )
    
    async def run_suite(self) -> Dict[str, Any]:
        """Run complete 60-second smoke test suite"""
        logger.info("🚨 Starting Veris 60-second smoke test suite")
        
        # Run all tests in sequence (fail-fast on critical failures)
        test_sequence = [
            self.sm1_health_probe,
            self.sm2_store_index_count,
            self.sm3_needle_retrieval,
            self.sm4_paraphrase_robustness,
            self.sm5_index_freshness,
            self.sm6_slo_spot_check,
            self.sm7_graph_ro_sanity  # Optional
        ]
        
        for test_func in test_sequence:
            # Check timeout
            if self._check_timeout():
                logger.error("Suite timeout exceeded!")
                break
            
            # Run test
            result = await test_func()
            self.results.append(result)
            
            # Log result
            if result.status == "pass":
                logger.info(f"✅ {result.id}: {result.name} - PASS ({result.latency_ms:.1f}ms)")
            elif result.status == "skip":
                logger.info(f"⏭️ {result.id}: {result.name} - SKIP ({result.error})")
            else:
                logger.error(f"❌ {result.id}: {result.name} - FAIL ({result.latency_ms:.1f}ms) - {result.error}")
                
                # Fail fast on critical tests (not SM-7 which is optional)
                if result.id != "SM-7":
                    logger.error("Critical test failed - aborting suite")
                    break
        
        # Calculate summary
        summary = self._calculate_summary()
        
        # Generate report
        report = {
            "suite_id": "veris-smoke-60s",
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "env": self.env,
            "namespace": self.config["NAMESPACE"],
            "summary": asdict(summary),
            "thresholds": asdict(self.thresholds),
            "tests": [asdict(result) for result in self.results]
        }
        
        # Log final status
        if summary.overall_status == "pass":
            logger.info(f"🎉 Smoke suite PASSED - All critical tests successful")
        else:
            logger.error(f"💥 Smoke suite FAILED - {len(summary.failed_tests)} tests failed")
        
        return report

def gate_logic(report: Dict[str, Any]) -> int:
    """Gate logic for deploy decisions"""
    s = report["summary"]
    t = report.get("thresholds", {})
    
    # Thresholds with sane defaults
    thr_lat = t.get("p95_latency_ms", 300)
    thr_err = t.get("error_rate_pct", 0.5)
    thr_rec = t.get("recovery_top1_pct", 95)
    thr_idx = t.get("index_freshness_s", 1)
    
    checks = [
        s["overall_status"] == "pass",
        s["p95_latency_ms"] <= thr_lat,
        s["error_rate_pct"] <= thr_err,
        s["recovery_top1_pct"] >= thr_rec,
        s["index_freshness_s"] <= thr_idx,
        len(s["failed_tests"]) == 0
    ]
    
    ok = all(checks)
    print("DEPLOY:", "GREEN" if ok else "RED")
    return 0 if ok else 1

async def main():
    """Main entry point for smoke test suite"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Veris 60-second smoke test suite")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--env", default="local", help="Environment name")
    parser.add_argument("--timeout", type=int, default=60000, help="Suite timeout in ms")
    parser.add_argument("--output", help="Output file for JSON report")
    parser.add_argument("--gate", action="store_true", help="Run gate logic and exit with code")
    
    args = parser.parse_args()
    
    if args.gate and args.output:
        # Gate mode - check existing report
        with open(args.output, 'r') as f:
            report = json.load(f)
        sys.exit(gate_logic(report))
    
    # Run smoke test suite
    suite = VerisSmokeTestSuite(
        base_url=args.url,
        env=args.env,
        timeout_ms=args.timeout
    )
    
    report = await suite.run_suite()
    
    # Save report
    output_file = args.output or f"veris_smoke_report_{suite.run_id.split('-')[-1][:19].replace(':', '')}.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Smoke test report saved: {output_file}")
    
    # Exit with appropriate code
    exit_code = 0 if report["summary"]["overall_status"] == "pass" else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())