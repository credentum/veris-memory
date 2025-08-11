#!/usr/bin/env python3
"""
Phase 2 Test Runner - Scale & Performance Testing Integration

Orchestrates all Phase 2 testing capabilities including:
- Scale curve testing (1x → 10x corpus)
- Cold vs warm performance validation
- Concurrency soak testing with rolling redeploy
- Real-time latency percentile monitoring

Usage:
    python run_phase2_tests.py --test scale
    python run_phase2_tests.py --test cold-warm
    python run_phase2_tests.py --test soak
    python run_phase2_tests.py --test all
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.datasets import DatasetManager
from evaluation.evaluator import Evaluator
from evaluation.scale_tester import ScaleTester
from evaluation.performance_tester import PerformanceTester
from evaluation.concurrency_tester import ConcurrencyTester
from evaluation.latency_tracker import LatencyTracker, get_global_tracker
from evaluation.tracing import initialize_tracing

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase2TestRunner:
    """Orchestrates Phase 2 scale and performance testing."""
    
    def __init__(self, results_dir: str = "./phase2_results"):
        """Initialize test runner."""
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize core components
        self.dataset_manager = DatasetManager()
        self.evaluator = Evaluator()
        
        # Initialize testing components
        self.scale_tester = ScaleTester(
            self.dataset_manager, 
            self.evaluator,
            base_corpus_size=1000,
            results_dir=str(self.results_dir / "scale_testing")
        )
        
        self.performance_tester = PerformanceTester(
            self.evaluator,
            self.dataset_manager,
            results_dir=str(self.results_dir / "performance_testing")
        )
        
        self.concurrency_tester = ConcurrencyTester(
            self.dataset_manager,
            results_dir=str(self.results_dir / "concurrency_testing")
        )
        
        # Initialize monitoring
        self.latency_tracker = LatencyTracker(
            window_duration_seconds=60,
            snapshot_interval_seconds=10,
            results_dir=str(self.results_dir / "latency_tracking")
        )
        
        # Initialize tracing
        self.trace_manager = initialize_tracing(
            str(self.results_dir / "traces")
        )
        
        # Test results
        self.results: Dict[str, Any] = {}
    
    async def run_scale_testing(self) -> Dict[str, Any]:
        """Run comprehensive scale curve testing."""
        logger.info("🚀 Starting Phase 2: Scale Curve Testing")
        
        # Standard scale test (1x → 10x)
        logger.info("Running standard scale test (1x → 10x)")
        standard_curve = await self.scale_tester.run_scale_curve_test(
            scale_factors=[1, 2, 5, 10],
            test_name="phase2_standard_scale"
        )
        
        # Extended scale test for high-capacity environments
        logger.info("Running extended scale test (1x → 20x)")
        extended_curve = await self.scale_tester.run_scale_curve_test(
            scale_factors=[1, 5, 10, 15, 20],
            test_name="phase2_extended_scale"
        )
        
        # Domain-specific scale testing
        logger.info("Running domain-specific scale tests")
        domain_results = {}
        
        for domain in ['technology', 'science', 'business']:
            domain_curve = await self.scale_tester.run_scale_curve_test(
                scale_factors=[1, 5, 10],
                topics=[domain],
                test_name=f"phase2_scale_{domain}"
            )
            domain_results[domain] = domain_curve.to_dict()
        
        scale_results = {
            'standard_curve': standard_curve.to_dict(),
            'extended_curve': extended_curve.to_dict(),
            'domain_specific': domain_results,
            'summary': {
                'performance_slope': standard_curve.performance_slope,
                'latency_slope': standard_curve.latency_slope,
                'within_tolerance': standard_curve.within_tolerance,
                'recommended_max_scale': standard_curve.recommended_max_scale
            }
        }
        
        logger.info("✅ Scale testing completed")
        return scale_results
    
    async def run_cold_warm_testing(self) -> Dict[str, Any]:
        """Run cold vs warm performance testing."""
        logger.info("🌡️  Starting Phase 2: Cold vs Warm Performance Testing")
        
        # Standard cold-warm comparison
        logger.info("Running standard cold vs warm test")
        standard_comparison = await self.performance_tester.run_cold_warm_comparison(
            test_name="phase2_standard_cold_warm",
            warmup_queries=50,
            measurement_queries=100,
            restart_method="simulation"
        )
        
        # Extended cold-warm comparison with more warmup
        logger.info("Running extended cold vs warm test")
        extended_comparison = await self.performance_tester.run_cold_warm_comparison(
            test_name="phase2_extended_cold_warm",
            warmup_queries=200,
            measurement_queries=200,
            restart_method="simulation"
        )
        
        # Quick cold-warm for CI/CD
        logger.info("Running quick cold vs warm test")
        quick_comparison = await self.performance_tester.run_cold_warm_comparison(
            test_name="phase2_quick_cold_warm",
            warmup_queries=10,
            measurement_queries=25,
            restart_method="simulation"
        )
        
        cold_warm_results = {
            'standard_comparison': standard_comparison.to_dict(),
            'extended_comparison': extended_comparison.to_dict(),
            'quick_comparison': quick_comparison.to_dict(),
            'summary': {
                'standard_latency_multiplier': standard_comparison.latency_multiplier,
                'standard_cache_effectiveness': standard_comparison.cache_effectiveness,
                'standard_within_tolerance': standard_comparison.within_tolerance,
                'optimal_warmup_queries': standard_comparison.optimal_warmup_queries
            }
        }
        
        logger.info("✅ Cold vs warm testing completed")
        return cold_warm_results
    
    async def run_concurrency_testing(self) -> Dict[str, Any]:
        """Run concurrency and soak testing."""
        logger.info("🔥 Starting Phase 2: Concurrency & Soak Testing")
        
        # Start latency monitoring
        self.latency_tracker.start()
        
        try:
            # Standard soak test
            logger.info("Running standard soak test (30 minutes)")
            standard_soak = await self.concurrency_tester.run_soak_test(
                test_name="phase2_standard_soak",
                target_qps=25,
                duration_minutes=30,
                concurrent_users=5,
                enable_rolling_redeploy=False
            )
            
            # Production soak test with rolling redeploy
            logger.info("Running production soak test with rolling redeploy (60 minutes)")
            production_soak = await self.concurrency_tester.run_soak_test(
                test_name="phase2_production_soak",
                target_qps=50,
                duration_minutes=60,
                concurrent_users=10,
                enable_rolling_redeploy=True,
                redeploy_interval_minutes=15
            )
            
            # High load burst test
            logger.info("Running high load burst test (15 minutes)")
            burst_test = await self.concurrency_tester.run_soak_test(
                test_name="phase2_burst_test",
                target_qps=100,
                duration_minutes=15,
                concurrent_users=20,
                enable_rolling_redeploy=False
            )
            
        finally:
            # Stop latency monitoring
            self.latency_tracker.stop()
        
        # Get latency tracking summary
        latency_summary = {
            'global_percentiles': self.latency_tracker.get_current_percentiles(),
            'recent_alerts': [alert.to_dict() for alert in self.latency_tracker.get_recent_alerts(10)],
            'snapshot_count': len(self.latency_tracker.get_snapshot_history(1000)),
            'operations_tracked': self.latency_tracker.get_operation_list()
        }
        
        concurrency_results = {
            'standard_soak': standard_soak.to_dict(),
            'production_soak': production_soak.to_dict(),
            'burst_test': burst_test.to_dict(),
            'latency_tracking': latency_summary,
            'summary': {
                'standard_soak_passed': standard_soak.passed_soak_test,
                'production_soak_passed': production_soak.passed_soak_test,
                'burst_test_passed': burst_test.passed_soak_test,
                'total_redeploys': production_soak.redeploy_count,
                'tail_latency_stable': production_soak.tail_latency_stable
            }
        }
        
        logger.info("✅ Concurrency testing completed")
        return concurrency_results
    
    async def run_comprehensive_phase2_test(self) -> Dict[str, Any]:
        """Run all Phase 2 tests in sequence."""
        logger.info("🎯 Starting Comprehensive Phase 2 Testing Suite")
        
        start_time = time.time()
        
        try:
            # Run all test categories
            self.results['scale_testing'] = await self.run_scale_testing()
            self.results['cold_warm_testing'] = await self.run_cold_warm_testing()
            self.results['concurrency_testing'] = await self.run_concurrency_testing()
            
            # Generate overall summary
            duration_minutes = (time.time() - start_time) / 60
            
            overall_summary = {
                'test_duration_minutes': duration_minutes,
                'timestamp': time.time(),
                'phase': 'Phase 2 - Scale & Performance Testing',
                'categories_tested': ['scale_curve', 'cold_warm', 'concurrency_soak'],
                'overall_status': self._determine_overall_status(),
                'key_findings': self._extract_key_findings(),
                'recommendations': self._generate_recommendations()
            }
            
            self.results['overall_summary'] = overall_summary
            
            # Save comprehensive results
            await self._save_comprehensive_results()
            
            logger.info("🏆 Phase 2 Comprehensive Testing Completed")
            logger.info(f"   Duration: {duration_minutes:.1f} minutes")
            logger.info(f"   Overall Status: {overall_summary['overall_status']}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"Phase 2 testing failed: {str(e)}")
            raise
    
    def _determine_overall_status(self) -> str:
        """Determine overall Phase 2 test status."""
        
        # Check scale testing
        scale_ok = self.results.get('scale_testing', {}).get('summary', {}).get('within_tolerance', False)
        
        # Check cold-warm testing
        cold_warm_ok = self.results.get('cold_warm_testing', {}).get('summary', {}).get('standard_within_tolerance', False)
        
        # Check concurrency testing
        concurrency_ok = all([
            self.results.get('concurrency_testing', {}).get('summary', {}).get('standard_soak_passed', False),
            self.results.get('concurrency_testing', {}).get('summary', {}).get('production_soak_passed', False)
        ])
        
        if scale_ok and cold_warm_ok and concurrency_ok:
            return "PASS"
        elif (scale_ok or cold_warm_ok) and not (not scale_ok and not cold_warm_ok and not concurrency_ok):
            return "PARTIAL_PASS"
        else:
            return "FAIL"
    
    def _extract_key_findings(self) -> List[str]:
        """Extract key findings from all tests."""
        findings = []
        
        # Scale testing findings
        scale_summary = self.results.get('scale_testing', {}).get('summary', {})
        if scale_summary:
            findings.append(f"Scale testing: Performance slope {scale_summary.get('performance_slope', 0):.4f} per 10x")
            findings.append(f"Scale testing: Recommended max scale {scale_summary.get('recommended_max_scale', 1)}x")
        
        # Cold-warm findings
        cold_warm_summary = self.results.get('cold_warm_testing', {}).get('summary', {})
        if cold_warm_summary:
            findings.append(f"Cold start: {cold_warm_summary.get('standard_latency_multiplier', 0):.2f}x latency penalty")
            findings.append(f"Cache effectiveness: {cold_warm_summary.get('standard_cache_effectiveness', 0):.1f}%")
        
        # Concurrency findings
        concurrency_summary = self.results.get('concurrency_testing', {}).get('summary', {})
        if concurrency_summary:
            findings.append(f"Soak tests: Standard passed={concurrency_summary.get('standard_soak_passed', False)}")
            findings.append(f"Rolling redeploys: {concurrency_summary.get('total_redeploys', 0)} completed successfully")
        
        return findings
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        scale_summary = self.results.get('scale_testing', {}).get('summary', {})
        cold_warm_summary = self.results.get('cold_warm_testing', {}).get('summary', {})
        concurrency_summary = self.results.get('concurrency_testing', {}).get('summary', {})
        
        # Scale recommendations
        if not scale_summary.get('within_tolerance', True):
            recommendations.append("Scale performance degradation exceeds tolerance - consider optimization")
        
        max_scale = scale_summary.get('recommended_max_scale', 10)
        if max_scale < 10:
            recommendations.append(f"Recommended max scale is {max_scale}x - plan capacity accordingly")
        
        # Cold-warm recommendations
        latency_mult = cold_warm_summary.get('standard_latency_multiplier', 1)
        if latency_mult > 3:
            recommendations.append("Cold start penalty is high - consider persistent caching")
        
        optimal_warmup = cold_warm_summary.get('optimal_warmup_queries', 50)
        recommendations.append(f"Optimal warmup: {optimal_warmup} queries for best performance")
        
        # Concurrency recommendations
        if not concurrency_summary.get('tail_latency_stable', True):
            recommendations.append("Tail latency instability detected - investigate load balancing")
        
        return recommendations
    
    async def _save_comprehensive_results(self):
        """Save comprehensive test results."""
        timestamp_str = time.strftime('%Y%m%d_%H%M%S')
        filename = f"phase2_comprehensive_results_{timestamp_str}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"Comprehensive results saved: {filepath}")
        
        # Also save summary CSV
        csv_filename = f"phase2_summary_{timestamp_str}.csv"
        await self._save_summary_csv(csv_filename)
    
    async def _save_summary_csv(self, filename: str):
        """Save summary results as CSV."""
        import csv
        
        filepath = self.results_dir / filename
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['Test Category', 'Test Name', 'Status', 'Key Metric', 'Value'])
            
            # Scale testing
            scale_summary = self.results.get('scale_testing', {}).get('summary', {})
            writer.writerow(['Scale', 'Performance Slope', 
                           'PASS' if scale_summary.get('within_tolerance') else 'FAIL',
                           'Slope per 10x', scale_summary.get('performance_slope', 0)])
            
            # Cold-warm testing
            cold_warm_summary = self.results.get('cold_warm_testing', {}).get('summary', {})
            writer.writerow(['Cold-Warm', 'Latency Multiplier',
                           'PASS' if cold_warm_summary.get('standard_within_tolerance') else 'FAIL',
                           'Cold/Warm Ratio', cold_warm_summary.get('standard_latency_multiplier', 0)])
            
            # Concurrency testing
            concurrency_summary = self.results.get('concurrency_testing', {}).get('summary', {})
            writer.writerow(['Concurrency', 'Standard Soak',
                           'PASS' if concurrency_summary.get('standard_soak_passed') else 'FAIL',
                           'Tail Latency Stable', concurrency_summary.get('tail_latency_stable', False)])
        
        logger.info(f"Summary CSV saved: {filepath}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Phase 2 Scale & Performance Testing")
    
    parser.add_argument(
        '--test',
        choices=['scale', 'cold-warm', 'soak', 'all'],
        default='all',
        help='Test category to run'
    )
    
    parser.add_argument(
        '--results-dir',
        default='./phase2_results',
        help='Directory for test results'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick tests for CI/CD'
    )
    
    args = parser.parse_args()
    
    # Create test runner
    runner = Phase2TestRunner(args.results_dir)
    
    try:
        if args.test == 'scale':
            results = await runner.run_scale_testing()
        elif args.test == 'cold-warm':
            results = await runner.run_cold_warm_testing()
        elif args.test == 'soak':
            results = await runner.run_concurrency_testing()
        else:  # all
            results = await runner.run_comprehensive_phase2_test()
        
        logger.info("🎉 Phase 2 testing completed successfully!")
        
        # Print summary
        if 'overall_summary' in results:
            summary = results['overall_summary']
            print(f"\nOverall Status: {summary['overall_status']}")
            print(f"Duration: {summary['test_duration_minutes']:.1f} minutes")
            print("\nKey Findings:")
            for finding in summary['key_findings']:
                print(f"  • {finding}")
            print("\nRecommendations:")
            for rec in summary['recommendations']:
                print(f"  • {rec}")
        
    except Exception as e:
        logger.error(f"Phase 2 testing failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())