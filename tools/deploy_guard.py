#!/usr/bin/env python3
"""
Deploy Guard - 60-Second Smoke Test
Validates deployment health before marking "green"
Uses Veris Smoke Test Suite for comprehensive validation
"""

import asyncio
import time
import json
import requests
import logging
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

# Import Veris smoke test suite
try:
    from veris_smoke_60s import VerisSmokeTestSuite, gate_logic
except ImportError:
    # Fallback for standalone execution
    sys.path.append(str(Path(__file__).parent))
    from veris_smoke_60s import VerisSmokeTestSuite, gate_logic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SmokeTestResult:
    """Result of a smoke test operation"""
    test_name: str
    success: bool
    latency_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None

class DeployGuard:
    """Modern 60-second smoke test using Veris smoke test suite"""
    
    def __init__(self, base_url: str = "http://localhost:8000", 
                 qdrant_url: str = "http://localhost:6333",
                 env: str = "deployment"):
        self.base_url = base_url
        self.qdrant_url = qdrant_url
        self.env = env
        self.timeout = 60  # Full suite timeout
    
    async def run_veris_smoke_tests(self) -> Dict[str, Any]:
        """Run Veris 60-second smoke test suite"""
        logger.info("🚨 Deploy Guard: Running Veris smoke test suite")
        
        # Initialize Veris smoke test suite
        suite = VerisSmokeTestSuite(
            base_url=self.base_url,
            env=self.env,
            timeout_ms=self.timeout * 1000
        )
        
        # Run the complete suite
        report = await suite.run_suite()
        
        # Log summary
        summary = report["summary"]
        if summary["overall_status"] == "pass":
            logger.info("✅ DEPLOY GUARD: VERIS SMOKE TESTS PASSED")
            logger.info(f"   P95 Latency: {summary['p95_latency_ms']:.1f}ms")
            logger.info(f"   Error Rate: {summary['error_rate_pct']:.1f}%") 
            logger.info(f"   Recovery: {summary['recovery_top1_pct']:.1f}%")
            logger.info(f"   Index Freshness: {summary['index_freshness_s']:.2f}s")
        else:
            logger.error("❌ DEPLOY GUARD: VERIS SMOKE TESTS FAILED")
            logger.error(f"   Failed tests: {summary['failed_tests']}")
        
        return report
    
    # Legacy compatibility methods (kept for backward compatibility)
        
        # Known-good test cases for needle tests
        self.needle_tests = [
            {
                "name": "config_fix_needle",
                "store": {
                    "type": "design",
                    "content": {
                        "title": "CONFIG FIX SUCCESS NEEDLE",
                        "description": "Specific needle test for deployment validation"
                    },
                    "metadata": {"test": "needle", "deploy_guard": True}
                },
                "query": "CONFIG FIX SUCCESS",
                "expected_in_top": 3
            },
            {
                "name": "api_test_needle", 
                "store": {
                    "type": "trace",
                    "content": {
                        "title": "API TEST DEPLOYMENT NEEDLE",
                        "description": "Deployment validation via API testing needle"
                    },
                    "metadata": {"test": "needle", "deploy_guard": True}
                },
                "query": "API TEST DEPLOYMENT",
                "expected_in_top": 3
            }
        ]
        
        # Paraphrase tests (semantic similarity)
        self.paraphrase_tests = [
            {
                "original": "machine learning best practices",
                "paraphrase": "optimal ML techniques and methodologies",
                "min_similarity": 0.7
            },
            {
                "original": "database optimization strategies", 
                "paraphrase": "improving database performance methods",
                "min_similarity": 0.7
            }
        ]
    
    def _get_model(self):
        """Lazy load embedding model"""
        if self.model is None:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.model
    
    async def test_basic_connectivity(self) -> SmokeTestResult:
        """Test basic API connectivity"""
        start_time = time.time()
        
        try:
            # Test health endpoint
            response = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return SmokeTestResult(
                    test_name="connectivity",
                    success=True,
                    latency_ms=latency_ms,
                    details={"status_code": response.status_code}
                )
            else:
                return SmokeTestResult(
                    test_name="connectivity",
                    success=False,
                    latency_ms=latency_ms,
                    details={"status_code": response.status_code},
                    error=f"Health check failed: {response.status_code}"
                )
                
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                test_name="connectivity",
                success=False,
                latency_ms=latency_ms,
                details={},
                error=str(e)
            )
    
    async def test_point_count(self) -> SmokeTestResult:
        """Verify Qdrant has data points"""
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.qdrant_url}/collections/project_context", timeout=self.timeout)
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                points_count = data["result"]["points_count"]
                
                # Expect at least 1 point for meaningful tests
                success = points_count > 0
                
                return SmokeTestResult(
                    test_name="point_count", 
                    success=success,
                    latency_ms=latency_ms,
                    details={"points_count": points_count},
                    error=None if success else f"No data points found: {points_count}"
                )
            else:
                return SmokeTestResult(
                    test_name="point_count",
                    success=False,
                    latency_ms=latency_ms,
                    details={"status_code": response.status_code},
                    error=f"Collection check failed: {response.status_code}"
                )
                
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                test_name="point_count",
                success=False,
                latency_ms=latency_ms,
                details={},
                error=str(e)
            )
    
    async def test_needle_search(self, test_case: Dict[str, Any]) -> SmokeTestResult:
        """Test exact needle search (store + retrieve specific content)"""
        start_time = time.time()
        
        try:
            # Store needle content
            store_response = requests.post(
                f"{self.base_url}/tools/store_context",
                json=test_case["store"],
                timeout=self.timeout
            )
            
            if store_response.status_code != 200:
                raise Exception(f"Store failed: {store_response.status_code}")
            
            store_result = store_response.json()
            if not store_result.get("success"):
                raise Exception(f"Store failed: {store_result.get('message')}")
            
            # Small delay for index consistency
            await asyncio.sleep(0.5)
            
            # Search for needle
            retrieve_response = requests.post(
                f"{self.base_url}/tools/retrieve_context",
                json={
                    "query": test_case["query"],
                    "limit": test_case["expected_in_top"]
                },
                timeout=self.timeout
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if retrieve_response.status_code != 200:
                raise Exception(f"Retrieve failed: {retrieve_response.status_code}")
            
            retrieve_result = retrieve_response.json()
            
            if not retrieve_result.get("success", True):  # Some APIs don't return success field
                raise Exception(f"Retrieve failed: {retrieve_result.get('message', 'Unknown error')}")
            
            results = retrieve_result.get("results", [])
            
            # Check if needle found in top results
            needle_found = False
            for result in results:
                content = result.get("payload", {}).get("content", {})
                if isinstance(content, dict):
                    title = content.get("title", "")
                    if test_case["store"]["content"]["title"] in title:
                        needle_found = True
                        break
            
            return SmokeTestResult(
                test_name=f"needle_{test_case['name']}",
                success=needle_found,
                latency_ms=latency_ms,
                details={
                    "results_count": len(results),
                    "needle_found": needle_found,
                    "query": test_case["query"]
                },
                error=None if needle_found else "Needle not found in top results"
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                test_name=f"needle_{test_case['name']}",
                success=False,
                latency_ms=latency_ms,
                details={},
                error=str(e)
            )
    
    async def test_paraphrase_search(self, test_case: Dict[str, Any]) -> SmokeTestResult:
        """Test paraphrase semantic search"""
        start_time = time.time()
        
        try:
            model = self._get_model()
            
            # Generate embeddings for original and paraphrase
            original_embedding = model.encode(test_case["original"])
            paraphrase_embedding = model.encode(test_case["paraphrase"])
            
            # Calculate cosine similarity
            import numpy as np
            similarity = np.dot(original_embedding, paraphrase_embedding) / (
                np.linalg.norm(original_embedding) * np.linalg.norm(paraphrase_embedding)
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Check if similarity meets threshold
            success = similarity >= test_case["min_similarity"]
            
            return SmokeTestResult(
                test_name="paraphrase_similarity",
                success=success,
                latency_ms=latency_ms,
                details={
                    "similarity": float(similarity),
                    "threshold": test_case["min_similarity"],
                    "original": test_case["original"],
                    "paraphrase": test_case["paraphrase"]
                },
                error=None if success else f"Similarity {similarity:.3f} below threshold {test_case['min_similarity']}"
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return SmokeTestResult(
                test_name="paraphrase_similarity", 
                success=False,
                latency_ms=latency_ms,
                details={},
                error=str(e)
            )
    
    async def run_smoke_tests(self) -> Dict[str, Any]:
        """Execute complete 60-second smoke test suite"""
        logger.info("🚨 Deploy Guard: Starting 60-second smoke test...")
        
        start_time = time.time()
        results = []
        
        try:
            # 1. Basic connectivity (5 seconds)
            logger.info("Testing basic connectivity...")
            connectivity_result = await self.test_basic_connectivity()
            results.append(connectivity_result)
            
            if not connectivity_result.success:
                raise Exception("Basic connectivity failed - aborting smoke test")
            
            # 2. Point count verification (5 seconds) 
            logger.info("Checking data availability...")
            count_result = await self.test_point_count()
            results.append(count_result)
            
            # 3. Needle tests (20 seconds each = 40 seconds total)
            logger.info("Running needle search tests...")
            for needle_test in self.needle_tests:
                needle_result = await self.test_needle_search(needle_test)
                results.append(needle_result)
            
            # 4. Paraphrase tests (10 seconds)
            logger.info("Running paraphrase semantic tests...")
            for paraphrase_test in self.paraphrase_tests:
                paraphrase_result = await self.test_paraphrase_search(paraphrase_test) 
                results.append(paraphrase_result)
                
        except Exception as e:
            logger.error(f"❌ Smoke test aborted: {e}")
            results.append(SmokeTestResult(
                test_name="smoke_test_abort",
                success=False,
                latency_ms=0,
                details={},
                error=str(e)
            ))
        
        # Calculate summary
        total_time = time.time() - start_time
        successful_tests = sum(1 for r in results if r.success)
        total_tests = len(results)
        
        # Overall pass/fail
        deployment_healthy = (
            successful_tests >= total_tests * 0.8 and  # 80% pass rate
            any(r.test_name.startswith("needle") and r.success for r in results)  # At least 1 needle test passes
        )
        
        summary = {
            "deployment_status": "GREEN" if deployment_healthy else "RED",
            "overall_success": deployment_healthy,
            "total_time_seconds": total_time,
            "tests_passed": successful_tests,
            "tests_total": total_tests,
            "pass_rate": successful_tests / max(total_tests, 1),
            "test_results": [
                {
                    "name": r.test_name,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "details": r.details,
                    "error": r.error
                } for r in results
            ]
        }
        
        if deployment_healthy:
            logger.info(f"✅ Deploy Guard: DEPLOYMENT GREEN ({successful_tests}/{total_tests} tests passed, {total_time:.1f}s)")
        else:
            logger.error(f"❌ Deploy Guard: DEPLOYMENT RED ({successful_tests}/{total_tests} tests passed, {total_time:.1f}s)")
        
        return summary


# CLI interface
async def main():
    """CLI entry point for deploy guard"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy Guard - 60-second smoke test")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--qdrant-url", default="http://localhost:6333", help="Qdrant URL")
    parser.add_argument("--env", default="deployment", help="Environment name")
    parser.add_argument("--veris", action="store_true", help="Use Veris smoke test suite (recommended)")
    parser.add_argument("--legacy", action="store_true", help="Use legacy smoke tests")
    parser.add_argument("--output", help="Output file for JSON report")
    parser.add_argument("--gate", action="store_true", help="Run gate logic on existing report")
    
    args = parser.parse_args()
    
    # Gate mode - check existing report
    if args.gate and args.output:
        with open(args.output, 'r') as f:
            report = json.load(f)
        sys.exit(gate_logic(report))
    
    guard = DeployGuard(base_url=args.url, qdrant_url=args.qdrant_url, env=args.env)
    
    # Use Veris suite by default (or if explicitly requested)
    if args.veris or not args.legacy:
        logger.info("Using Veris smoke test suite (modern)")
        result = await guard.run_veris_smoke_tests()
        
        # Save report if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"📄 Veris smoke report saved: {args.output}")
        else:
            print(json.dumps(result, indent=2))
        
        # Exit code based on Veris suite results
        exit_code = 0 if result["summary"]["overall_status"] == "pass" else 1
        
    else:
        logger.info("Using legacy smoke tests")
        result = await guard.run_smoke_tests()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result, indent=2))
        
        # Exit code for CI/CD integration (legacy format)
        exit_code = 0 if result["deployment_status"] == "GREEN" else 1
    
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())