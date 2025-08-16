#!/usr/bin/env python3
"""
Test script for Veris Sentinel functionality.

Tests all monitoring checks in isolation and integration.
"""

import asyncio
import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.veris_sentinel import (
    SentinelConfig, SentinelRunner, VerisHealthProbe, 
    GoldenFactRecall, MetricsWiring, SecurityNegatives,
    ConfigParity, CapacitySmoke
)


async def test_individual_checks():
    """Test each check individually."""
    print("🧪 Testing individual Sentinel checks...")
    
    config = SentinelConfig(
        target_base_url="http://localhost:8000",  # Adjust for your setup
        schedule_cadence_sec=30
    )
    
    checks_to_test = [
        ("S1-probes", VerisHealthProbe(config)),
        ("S4-metrics-wiring", MetricsWiring(config)),
        ("S5-security-negatives", SecurityNegatives(config)),
        ("S7-config-parity", ConfigParity(config)),
        ("S8-capacity-smoke", CapacitySmoke(config))
    ]
    
    results = {}
    
    for check_id, check_instance in checks_to_test:
        print(f"\n📋 Testing {check_id}...")
        start_time = time.time()
        
        try:
            result = await check_instance.run_check()
            duration = time.time() - start_time
            
            print(f"  ✅ Status: {result.status}")
            print(f"  ⏱️ Duration: {duration:.2f}s")
            print(f"  📊 Latency: {result.latency_ms:.1f}ms")
            
            if result.metrics:
                print(f"  📈 Metrics: {result.metrics}")
            
            if result.error_message:
                print(f"  ❌ Error: {result.error_message}")
            
            if result.notes:
                print(f"  📝 Notes: {result.notes}")
            
            results[check_id] = {
                "status": result.status,
                "duration_s": duration,
                "latency_ms": result.latency_ms,
                "error": result.error_message,
                "metrics": result.metrics
            }
            
        except Exception as e:
            print(f"  💥 Exception: {e}")
            results[check_id] = {
                "status": "exception",
                "error": str(e)
            }
    
    return results


async def test_golden_fact_recall():
    """Test the golden fact recall functionality."""
    print("\n🎯 Testing Golden Fact Recall in detail...")
    
    config = SentinelConfig(target_base_url="http://localhost:8000")
    check = GoldenFactRecall(config)
    
    result = await check.run_check()
    
    print(f"Golden Fact Recall Result:")
    print(f"  Status: {result.status}")
    print(f"  Latency: {result.latency_ms:.1f}ms")
    
    if result.metrics:
        p_at_1 = result.metrics.get('p_at_1', 0.0)
        print(f"  Precision@1: {p_at_1:.2f}")
    
    print(f"  Notes: {result.notes}")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")


async def test_full_cycle():
    """Test a complete monitoring cycle."""
    print("\n🔄 Testing full monitoring cycle...")
    
    config = SentinelConfig(
        target_base_url="http://localhost:8000",
        max_parallel_checks=2,
        per_check_timeout_sec=15,
        cycle_budget_sec=60
    )
    
    # Use temporary database
    sentinel = SentinelRunner(config, "/tmp/test_sentinel.db")
    
    print("Running single monitoring cycle...")
    cycle_report = await sentinel.run_single_cycle()
    
    print(f"\n📊 Cycle Report:")
    print(f"  Cycle ID: {cycle_report['cycle_id']}")
    print(f"  Total checks: {cycle_report['total_checks']}")
    print(f"  Passed: {cycle_report['passed_checks']}")
    print(f"  Failed: {cycle_report['failed_checks']}")
    print(f"  Duration: {cycle_report['cycle_duration_ms']:.1f}ms")
    
    print(f"\n📋 Individual Results:")
    for result in cycle_report['results']:
        status_emoji = "✅" if result['status'] == "pass" else "⚠️" if result['status'] == "warn" else "❌"
        print(f"  {status_emoji} {result['check_id']}: {result['status']} ({result['latency_ms']:.1f}ms)")
        
        if result.get('error_message'):
            print(f"    Error: {result['error_message']}")
        if result.get('notes'):
            print(f"    Notes: {result['notes']}")
    
    return cycle_report


async def test_api_endpoints():
    """Test the Sentinel API endpoints."""
    print("\n🌐 Testing Sentinel API endpoints...")
    
    # This would require the API server to be running
    # For now, just show the structure
    
    print("API endpoints that would be tested:")
    print("  GET /status - Overall status and last cycle")
    print("  POST /run - Trigger immediate cycle")
    print("  GET /checks - List available checks")
    print("  GET /metrics - Prometheus metrics")
    print("  GET /report?n=5 - Last 5 cycle reports")
    
    print("\n💡 To test API endpoints:")
    print("  1. Run: python scripts/sentinel-main.py")
    print("  2. In another terminal: curl http://localhost:9090/status")


def print_test_summary(results):
    """Print a summary of test results."""
    print(f"\n📊 Test Summary")
    print("=" * 50)
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.get('status') == 'pass')
    warned_tests = sum(1 for r in results.values() if r.get('status') == 'warn')
    failed_tests = sum(1 for r in results.values() if r.get('status') in ['fail', 'exception'])
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Warnings: {warned_tests} ⚠️")
    print(f"Failed: {failed_tests} ❌")
    
    if failed_tests == 0:
        print(f"\n🎉 All tests successful!")
    else:
        print(f"\n⚠️ Some tests failed - check your Veris Memory deployment")
        
        for check_id, result in results.items():
            if result.get('status') in ['fail', 'exception']:
                print(f"  ❌ {check_id}: {result.get('error', 'Unknown error')}")


async def main():
    """Main test function."""
    print("🚀 Veris Sentinel Test Suite")
    print("=" * 50)
    
    print("\n💡 Prerequisites:")
    print("  - Veris Memory running on http://localhost:8000")
    print("  - Dashboard available on http://localhost:8080")
    print("  - All services healthy (Qdrant, Neo4j, Redis)")
    
    # Test individual checks
    check_results = await test_individual_checks()
    
    # Test golden fact recall in detail
    await test_golden_fact_recall()
    
    # Test full monitoring cycle
    await test_full_cycle()
    
    # Show API testing info
    await test_api_endpoints()
    
    # Print summary
    print_test_summary(check_results)
    
    print(f"\n🔍 Next steps:")
    print("  1. Deploy Sentinel: docker-compose -f docker-compose.sentinel.yml up")
    print("  2. Monitor logs: docker logs veris-sentinel -f")
    print("  3. Check API: curl http://localhost:9090/status")
    print("  4. View reports: curl http://localhost:9090/report")


if __name__ == "__main__":
    asyncio.run(main())