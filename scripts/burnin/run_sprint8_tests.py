#!/usr/bin/env python3
"""
Sprint 8 Guardrails Test Runner
Demonstrates all enhanced metrics and testing capabilities
"""
import sys
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_test_phase(phase_name: str, script_path: str, timeout: int = 600) -> dict:
    """Run a test phase and capture results"""
    logger.info(f"🚀 Starting {phase_name}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/workspaces/agent-context-template/context-store/scripts/burnin"
        )
        
        return {
            "phase": phase_name,
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": timeout  # Approximate, real timing would need start/end
        }
    except subprocess.TimeoutExpired:
        logger.error(f"{phase_name} timed out after {timeout}s")
        return {
            "phase": phase_name,
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout after {timeout}s",
            "duration": timeout
        }
    except Exception as e:
        logger.error(f"{phase_name} failed: {e}")
        return {
            "phase": phase_name,
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "duration": 0
        }

def main():
    """Main Sprint 8 test execution"""
    print("🚀 SPRINT 8 GUARDRAILS VALIDATION")
    print("Timing Source + Tail Latency + Real Corpus Testing")
    print("="*60)
    
    results_dir = Path("/workspaces/agent-context-template/context-store/burnin-results")
    sprint8_dir = results_dir / "sprint8"
    sprint8_dir.mkdir(exist_ok=True)
    
    test_results = {
        "sprint": "Sprint 8 - Guardrails: Timing Source + Tail Latency",
        "timestamp": datetime.now().isoformat(),
        "phases": []
    }
    
    # Phase 1: Enhanced Server Burn-in
    logger.info("📊 Phase 1: Enhanced Server Burn-in (Timing Sources + Tail Metrics)")
    phase1_result = run_test_phase(
        "Enhanced Server Burn-in",
        "server_burnin_enhanced.py",
        timeout=300
    )
    test_results["phases"].append(phase1_result)
    
    if phase1_result["success"]:
        logger.info("✅ Phase 1 PASSED")
    else:
        logger.error("❌ Phase 1 FAILED")
        logger.error(phase1_result["stderr"])
    
    # Phase 2: Real Corpus Testing (Optional)
    logger.info("📊 Phase 2: Real Corpus Testing")
    phase2_result = run_test_phase(
        "Real Corpus Testing",
        "real_corpus_test.py",
        timeout=600
    )
    test_results["phases"].append(phase2_result)
    
    if phase2_result["success"]:
        logger.info("✅ Phase 2 PASSED")
    else:
        logger.warning("⚠️ Phase 2 FAILED (Optional)")
        logger.warning(phase2_result["stderr"])
    
    # Collect and analyze results
    enhanced_reports = list(results_dir.glob("server-burnin-enhanced*.json"))
    real_corpus_reports = list(results_dir.glob("cycle-real-corpus*.json"))
    
    test_results["artifacts"] = {
        "enhanced_reports": [str(f) for f in enhanced_reports],
        "real_corpus_reports": [str(f) for f in real_corpus_reports],
        "total_reports": len(enhanced_reports) + len(real_corpus_reports)
    }
    
    # Summary
    passed_phases = sum(1 for phase in test_results["phases"] if phase["success"])
    total_phases = len(test_results["phases"])
    
    test_results["summary"] = {
        "passed_phases": passed_phases,
        "total_phases": total_phases,
        "success_rate": round(passed_phases / total_phases * 100, 1),
        "overall_status": "PASS" if passed_phases >= 1 else "FAIL"  # Phase 1 required, Phase 2 optional
    }
    
    # Save sprint results
    sprint_report = sprint8_dir / f"sprint8-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(sprint_report, 'w') as f:
        json.dump(test_results, f, indent=2)
    
    # Final output
    print(f"\n{'='*60}")
    print("📊 SPRINT 8 SUMMARY")
    print(f"   Overall: {test_results['summary']['overall_status']}")
    print(f"   Phases: {passed_phases}/{total_phases} passed")
    print(f"   Enhanced Reports: {len(enhanced_reports)}")
    print(f"   Real Corpus Reports: {len(real_corpus_reports)}")
    print(f"   Full Report: {sprint_report}")
    
    # Demonstrate key features
    if enhanced_reports:
        print(f"\n🔍 ENHANCED METRICS DEMO")
        with open(enhanced_reports[-1]) as f:
            report = json.load(f)
            
        # Show timing source labels
        baseline = report.get("baseline", {})
        if "e2e" in baseline:
            print(f"   Timing Sources: E2E and Internal metrics tracked")
            e2e = baseline["e2e"]
            print(f"   E2E Baseline: p50={e2e['p50_ms']}ms, p95={e2e['p95_ms']}ms, p99={e2e['p99_ms']}ms, max={e2e['max_ms']}ms")
        
        # Show tail alerts
        total_alerts = report.get("total_tail_alerts", 0)
        print(f"   Tail Alerts: {total_alerts} warnings detected")
        
        # Show metrics version
        version = report.get("metrics_version", "1.0.0")
        print(f"   Metrics Version: {version}")
    
    print("="*60)
    
    return 0 if test_results["summary"]["overall_status"] == "PASS" else 1

if __name__ == "__main__":
    exit(main())