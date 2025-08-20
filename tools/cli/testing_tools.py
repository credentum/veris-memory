#!/usr/bin/env python3
"""
Testing Tools for Veris Memory System.

Collection of utilities for automated testing, validation, and debugging
of the Veris Memory system components.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import random

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.query_dispatcher import QueryDispatcher, SearchMode, DispatchPolicy
from interfaces.memory_result import MemoryResult, ContentType, ResultSource
from filters.pre_filter import PreFilterEngine, FilterCriteria, FilterOperator
from ranking.ranking_policy import RankingPolicyEngine


@dataclass
class TestCase:
    """Represents a single test case for the system."""
    name: str
    query: str
    expected_result_count: Optional[int] = None
    search_mode: SearchMode = SearchMode.HYBRID
    dispatch_policy: DispatchPolicy = DispatchPolicy.PARALLEL
    ranking_policy: str = "default"
    content_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    timeout_ms: float = 5000.0
    min_score: Optional[float] = None


@dataclass
class TestResult:
    """Results from running a test case."""
    test_case: TestCase
    success: bool
    response_time_ms: float
    result_count: int
    error_message: Optional[str] = None
    backends_used: Optional[List[str]] = None
    search_mode_used: Optional[str] = None


class SystemValidator:
    """Validates system components and configurations."""
    
    def __init__(self, dispatcher: QueryDispatcher):
        self.dispatcher = dispatcher
        self.validation_results: List[Dict[str, Any]] = []
    
    async def validate_all_components(self) -> Dict[str, Any]:
        """Run comprehensive system validation."""
        print("🔍 Running System Validation...")
        print("-" * 40)
        
        results = {
            'backend_health': await self._validate_backend_health(),
            'dispatcher_config': await self._validate_dispatcher_config(),
            'ranking_policies': await self._validate_ranking_policies(),
            'filter_capabilities': await self._validate_filter_capabilities(),
            'performance_baseline': await self._validate_performance_baseline()
        }
        
        # Overall health score
        scores = [r.get('score', 0) for r in results.values() if isinstance(r, dict) and 'score' in r]
        overall_score = sum(scores) / len(scores) if scores else 0
        results['overall_score'] = overall_score
        
        return results
    
    async def _validate_backend_health(self) -> Dict[str, Any]:
        """Validate backend health and connectivity."""
        print("📊 Validating backend health...")
        
        health_results = await self.dispatcher.health_check_all_backends()
        healthy_count = sum(1 for h in health_results.values() if h['status'] == 'healthy')
        total_count = len(health_results)
        
        health_score = (healthy_count / total_count) * 100 if total_count > 0 else 0
        
        print(f"   ✅ {healthy_count}/{total_count} backends healthy")
        for backend, health in health_results.items():
            status_emoji = "✅" if health['status'] == 'healthy' else "❌"
            print(f"   {status_emoji} {backend}: {health['response_time_ms']:.1f}ms")
        
        return {
            'healthy_backends': healthy_count,
            'total_backends': total_count,
            'health_details': health_results,
            'score': health_score
        }
    
    async def _validate_dispatcher_config(self) -> Dict[str, Any]:
        """Validate query dispatcher configuration."""
        print("🔧 Validating dispatcher configuration...")
        
        backends = self.dispatcher.list_backends()
        performance_stats = self.dispatcher.get_performance_stats()
        
        config_issues = []
        
        # Check minimum backend requirements
        if len(backends) < 2:
            config_issues.append("Insufficient backends registered (minimum 2 required)")
        
        # Check backend types
        expected_backends = {"vector", "graph", "kv"}
        missing_backends = expected_backends - set(backends)
        if missing_backends:
            config_issues.append(f"Missing backend types: {', '.join(missing_backends)}")
        
        config_score = max(0, 100 - (len(config_issues) * 25))
        
        print(f"   📦 Registered backends: {', '.join(backends)}")
        print(f"   🎯 Configuration score: {config_score}%")
        
        if config_issues:
            print("   ⚠️  Issues found:")
            for issue in config_issues:
                print(f"      - {issue}")
        
        return {
            'registered_backends': backends,
            'issues': config_issues,
            'performance_stats': performance_stats,
            'score': config_score
        }
    
    async def _validate_ranking_policies(self) -> Dict[str, Any]:
        """Validate ranking policy configurations."""
        print("📋 Validating ranking policies...")
        
        policies = self.dispatcher.get_available_ranking_policies()
        policy_details = {}
        policy_issues = []
        
        for policy_name in policies:
            try:
                policy_info = self.dispatcher.get_ranking_policy_info(policy_name)
                policy_details[policy_name] = policy_info
                
                # Basic validation
                if not policy_info.get('description'):
                    policy_issues.append(f"Policy '{policy_name}' missing description")
                    
            except Exception as e:
                policy_issues.append(f"Policy '{policy_name}' error: {str(e)}")
        
        policy_score = max(0, 100 - (len(policy_issues) * 20))
        
        print(f"   🎯 Available policies: {', '.join(policies)}")
        print(f"   📊 Policy validation score: {policy_score}%")
        
        if policy_issues:
            print("   ⚠️  Issues found:")
            for issue in policy_issues:
                print(f"      - {issue}")
        
        return {
            'available_policies': policies,
            'policy_details': policy_details,
            'issues': policy_issues,
            'score': policy_score
        }
    
    async def _validate_filter_capabilities(self) -> Dict[str, Any]:
        """Validate filtering capabilities."""
        print("🔍 Validating filter capabilities...")
        
        capabilities = self.dispatcher.get_filter_capabilities()
        expected_capabilities = {
            'time_window_filtering',
            'tag_filtering', 
            'content_type_filtering'
        }
        
        missing_capabilities = expected_capabilities - set(capabilities.keys())
        supported_count = sum(1 for supported in capabilities.values() if supported)
        
        capability_score = (supported_count / len(capabilities)) * 100 if capabilities else 0
        
        print(f"   🔧 Supported capabilities: {supported_count}/{len(capabilities)}")
        for cap, supported in capabilities.items():
            emoji = "✅" if supported else "❌"
            print(f"   {emoji} {cap.replace('_', ' ').title()}")
        
        if missing_capabilities:
            print(f"   ⚠️  Missing capabilities: {', '.join(missing_capabilities)}")
        
        return {
            'capabilities': capabilities,
            'missing_capabilities': list(missing_capabilities),
            'score': capability_score
        }
    
    async def _validate_performance_baseline(self) -> Dict[str, Any]:
        """Validate performance against baseline expectations."""
        print("⚡ Validating performance baseline...")
        
        # Run a few test queries to establish baseline
        test_queries = [
            "test query performance",
            "system validation check",
            "baseline measurement"
        ]
        
        response_times = []
        success_count = 0
        
        for query in test_queries:
            start_time = time.time()
            try:
                result = await self.dispatcher.dispatch_query(
                    query=query,
                    search_mode=SearchMode.HYBRID,
                    limit=5
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                response_times.append(response_time)
                
                if result.success:
                    success_count += 1
                    
            except Exception:
                pass
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = float('inf')
            max_response_time = float('inf')
        
        # Performance scoring (under 100ms average is excellent)
        if avg_response_time < 100:
            perf_score = 100
        elif avg_response_time < 500:
            perf_score = 80
        elif avg_response_time < 1000:
            perf_score = 60
        else:
            perf_score = 40
        
        success_rate = (success_count / len(test_queries)) * 100 if test_queries else 0
        final_score = (perf_score + success_rate) / 2
        
        print(f"   ⏱️  Average response: {avg_response_time:.1f}ms")
        print(f"   🎯 Success rate: {success_rate:.1f}%")
        print(f"   📊 Performance score: {final_score:.1f}%")
        
        return {
            'avg_response_time_ms': avg_response_time,
            'max_response_time_ms': max_response_time,
            'success_rate': success_rate,
            'test_count': len(test_queries),
            'score': final_score
        }


class TestSuiteRunner:
    """Runs automated test suites for system validation."""
    
    def __init__(self, dispatcher: QueryDispatcher):
        self.dispatcher = dispatcher
        self.test_results: List[TestResult] = []
    
    def get_default_test_suite(self) -> List[TestCase]:
        """Get a comprehensive default test suite."""
        return [
            # Basic functionality tests
            TestCase(
                name="basic_search",
                query="python function",
                expected_result_count=1,
                timeout_ms=1000
            ),
            TestCase(
                name="empty_query",
                query="",
                expected_result_count=0,
                timeout_ms=500
            ),
            TestCase(
                name="complex_query",
                query="authentication system with database integration",
                search_mode=SearchMode.HYBRID,
                timeout_ms=2000
            ),
            
            # Search mode tests
            TestCase(
                name="vector_only_search",
                query="javascript async function",
                search_mode=SearchMode.VECTOR,
                timeout_ms=1000
            ),
            TestCase(
                name="graph_only_search", 
                query="system architecture design",
                search_mode=SearchMode.GRAPH,
                timeout_ms=1000
            ),
            TestCase(
                name="kv_only_search",
                query="database configuration",
                search_mode=SearchMode.KV,
                timeout_ms=1000
            ),
            
            # Dispatch policy tests
            TestCase(
                name="sequential_dispatch",
                query="api documentation",
                dispatch_policy=DispatchPolicy.SEQUENTIAL,
                timeout_ms=3000
            ),
            TestCase(
                name="fallback_dispatch",
                query="error handling patterns",
                dispatch_policy=DispatchPolicy.FALLBACK,
                timeout_ms=2000
            ),
            
            # Ranking policy tests
            TestCase(
                name="code_boost_ranking",
                query="authentication function",
                ranking_policy="code_boost",
                timeout_ms=1500
            ),
            TestCase(
                name="recency_ranking",
                query="recent changes",
                ranking_policy="recency",
                timeout_ms=1500
            ),
            
            # Content type filtering tests
            TestCase(
                name="code_only_filter",
                query="function implementation",
                content_types=["code"],
                timeout_ms=1000
            ),
            TestCase(
                name="docs_only_filter",
                query="api guide",
                content_types=["documentation"],
                timeout_ms=1000
            ),
            
            # Performance tests
            TestCase(
                name="large_result_set",
                query="system",
                timeout_ms=5000
            ),
            TestCase(
                name="high_precision_search",
                query="specific implementation detail",
                min_score=0.8,
                timeout_ms=2000
            ),
            
            # Edge cases
            TestCase(
                name="special_characters",
                query="@#$%^&*()",
                expected_result_count=0,
                timeout_ms=1000
            ),
            TestCase(
                name="very_long_query",
                query=" ".join(["word"] * 100),
                timeout_ms=3000
            )
        ]
    
    async def run_test_suite(self, test_cases: List[TestCase]) -> Dict[str, Any]:
        """Run a complete test suite."""
        print(f"🧪 Running Test Suite ({len(test_cases)} tests)")
        print("-" * 50)
        
        self.test_results.clear()
        passed_tests = 0
        failed_tests = 0
        total_time = 0
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Test {i}/{len(test_cases)}: {test_case.name}")
            
            result = await self._run_single_test(test_case)
            self.test_results.append(result)
            total_time += result.response_time_ms
            
            if result.success:
                passed_tests += 1
                status_emoji = "✅"
                details = f"{result.response_time_ms:.1f}ms, {result.result_count} results"
            else:
                failed_tests += 1
                status_emoji = "❌"
                details = result.error_message or "Unknown error"
            
            print(f"  {status_emoji} {details}")
        
        # Summary
        success_rate = (passed_tests / len(test_cases)) * 100
        avg_response_time = total_time / len(test_cases)
        
        print(f"\n📊 Test Suite Summary:")
        print(f"   ✅ Passed: {passed_tests}")
        print(f"   ❌ Failed: {failed_tests}")
        print(f"   📈 Success Rate: {success_rate:.1f}%")
        print(f"   ⏱️  Average Time: {avg_response_time:.1f}ms")
        print(f"   🕐 Total Time: {total_time:.1f}ms")
        
        return {
            'total_tests': len(test_cases),
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'avg_response_time_ms': avg_response_time,
            'total_time_ms': total_time,
            'test_results': [self._test_result_to_dict(r) for r in self.test_results]
        }
    
    async def _run_single_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = time.time()
        
        try:
            # Build query parameters
            query_params = {
                'query': test_case.query,
                'search_mode': test_case.search_mode,
                'dispatch_policy': test_case.dispatch_policy,
                'ranking_policy': test_case.ranking_policy,
                'limit': 20
            }
            
            if test_case.content_types:
                query_params['content_types'] = test_case.content_types
            if test_case.min_score:
                query_params['min_score'] = test_case.min_score
            
            # Execute query with timeout
            result = await asyncio.wait_for(
                self.dispatcher.dispatch_query(**query_params),
                timeout=test_case.timeout_ms / 1000.0
            )
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Validate results
            success = result.success
            error_message = None
            
            # Check expected result count if specified
            if test_case.expected_result_count is not None:
                if len(result.results) != test_case.expected_result_count:
                    success = False
                    error_message = f"Expected {test_case.expected_result_count} results, got {len(result.results)}"
            
            return TestResult(
                test_case=test_case,
                success=success,
                response_time_ms=response_time_ms,
                result_count=len(result.results) if result.success else 0,
                error_message=error_message,
                backends_used=result.backends_used if result.success else None,
                search_mode_used=result.search_mode_used if result.success else None
            )
            
        except asyncio.TimeoutError:
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            return TestResult(
                test_case=test_case,
                success=False,
                response_time_ms=response_time_ms,
                result_count=0,
                error_message=f"Timeout after {test_case.timeout_ms}ms"
            )
        except Exception as e:
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            return TestResult(
                test_case=test_case,
                success=False,
                response_time_ms=response_time_ms,
                result_count=0,
                error_message=str(e)
            )
    
    def _test_result_to_dict(self, result: TestResult) -> Dict[str, Any]:
        """Convert test result to dictionary for serialization."""
        return {
            'test_name': result.test_case.name,
            'success': result.success,
            'response_time_ms': result.response_time_ms,
            'result_count': result.result_count,
            'error_message': result.error_message,
            'backends_used': result.backends_used,
            'search_mode_used': result.search_mode_used,
            'query': result.test_case.query,
            'expected_result_count': result.test_case.expected_result_count
        }
    
    def export_results(self, filename: str):
        """Export test results to JSON file."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(self.test_results),
            'results': [self._test_result_to_dict(r) for r in self.test_results]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Test results exported to: {filename}")


class LoadTester:
    """Performs load testing and stress testing."""
    
    def __init__(self, dispatcher: QueryDispatcher):
        self.dispatcher = dispatcher
    
    async def run_load_test(self, 
                          concurrent_users: int = 10,
                          queries_per_user: int = 5,
                          query_delay_ms: float = 100) -> Dict[str, Any]:
        """Run a load test with concurrent users."""
        print(f"🔥 Load Test: {concurrent_users} users, {queries_per_user} queries each")
        print("-" * 60)
        
        test_queries = [
            "python authentication function",
            "javascript async api call",
            "database configuration setup",
            "system architecture overview",
            "api documentation guide",
            "error handling patterns",
            "user interface components",
            "backend service integration"
        ]
        
        async def simulate_user(user_id: int) -> List[Dict[str, Any]]:
            """Simulate a single user's query session."""
            user_results = []
            
            for i in range(queries_per_user):
                query = random.choice(test_queries)
                
                start_time = time.time()
                try:
                    result = await self.dispatcher.dispatch_query(
                        query=query,
                        search_mode=SearchMode.HYBRID,
                        limit=10
                    )
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    user_results.append({
                        'user_id': user_id,
                        'query_id': i,
                        'query': query,
                        'success': result.success,
                        'response_time_ms': response_time,
                        'result_count': len(result.results) if result.success else 0
                    })
                    
                except Exception as e:
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    user_results.append({
                        'user_id': user_id,
                        'query_id': i,
                        'query': query,
                        'success': False,
                        'response_time_ms': response_time,
                        'result_count': 0,
                        'error': str(e)
                    })
                
                # Delay between queries
                if query_delay_ms > 0 and i < queries_per_user - 1:
                    await asyncio.sleep(query_delay_ms / 1000.0)
            
            return user_results
        
        # Run concurrent user simulations
        start_time = time.time()
        
        tasks = [simulate_user(user_id) for user_id in range(concurrent_users)]
        all_results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_test_time = (end_time - start_time) * 1000
        
        # Flatten results
        flat_results = [result for user_results in all_results for result in user_results]
        
        # Analyze results
        successful_queries = [r for r in flat_results if r['success']]
        failed_queries = [r for r in flat_results if not r['success']]
        
        if successful_queries:
            response_times = [r['response_time_ms'] for r in successful_queries]
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
        else:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0
            p95_response_time = 0
        
        success_rate = (len(successful_queries) / len(flat_results)) * 100 if flat_results else 0
        queries_per_second = len(flat_results) / (total_test_time / 1000) if total_test_time > 0 else 0
        
        # Print summary
        print(f"\n📊 Load Test Results:")
        print(f"   👥 Users: {concurrent_users}")
        print(f"   📈 Total Queries: {len(flat_results)}")
        print(f"   ✅ Successful: {len(successful_queries)}")
        print(f"   ❌ Failed: {len(failed_queries)}")
        print(f"   📊 Success Rate: {success_rate:.1f}%")
        print(f"   🔥 Queries/Second: {queries_per_second:.1f}")
        print(f"   ⏱️  Avg Response: {avg_response_time:.1f}ms")
        print(f"   📈 95th Percentile: {p95_response_time:.1f}ms")
        print(f"   ⚡ Min/Max: {min_response_time:.1f}ms / {max_response_time:.1f}ms")
        print(f"   🕐 Total Test Time: {total_test_time:.1f}ms")
        
        return {
            'concurrent_users': concurrent_users,
            'queries_per_user': queries_per_user,
            'total_queries': len(flat_results),
            'successful_queries': len(successful_queries),
            'failed_queries': len(failed_queries),
            'success_rate': success_rate,
            'queries_per_second': queries_per_second,
            'avg_response_time_ms': avg_response_time,
            'min_response_time_ms': min_response_time,
            'max_response_time_ms': max_response_time,
            'p95_response_time_ms': p95_response_time,
            'total_test_time_ms': total_test_time,
            'detailed_results': flat_results
        }


async def main():
    """Main entry point for testing tools."""
    parser = argparse.ArgumentParser(description="Veris Memory Testing Tools")
    parser.add_argument(
        "command",
        choices=["validate", "test", "load-test"],
        help="Testing command to run"
    )
    parser.add_argument(
        "--export",
        help="Export results to JSON file"
    )
    parser.add_argument(
        "--concurrent-users",
        type=int,
        default=10,
        help="Number of concurrent users for load testing"
    )
    parser.add_argument(
        "--queries-per-user", 
        type=int,
        default=5,
        help="Number of queries per user for load testing"
    )
    
    args = parser.parse_args()
    
    # Initialize system with mock backends
    print("🚀 Initializing Veris Memory Testing Environment...")
    
    from storage.mock_backends import MockVectorBackend, MockGraphBackend, MockKVBackend
    
    dispatcher = QueryDispatcher()
    dispatcher.register_backend("vector", MockVectorBackend())
    dispatcher.register_backend("graph", MockGraphBackend())
    dispatcher.register_backend("kv", MockKVBackend())
    
    print("✅ Testing environment ready!")
    print()
    
    if args.command == "validate":
        # System validation
        validator = SystemValidator(dispatcher)
        results = await validator.validate_all_components()
        
        print(f"\n🏆 Overall System Score: {results['overall_score']:.1f}%")
        
        if args.export:
            with open(args.export, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Validation results exported to: {args.export}")
    
    elif args.command == "test":
        # Test suite execution
        runner = TestSuiteRunner(dispatcher)
        test_suite = runner.get_default_test_suite()
        results = await runner.run_test_suite(test_suite)
        
        if args.export:
            runner.export_results(args.export)
    
    elif args.command == "load-test":
        # Load testing
        load_tester = LoadTester(dispatcher)
        results = await load_tester.run_load_test(
            concurrent_users=args.concurrent_users,
            queries_per_user=args.queries_per_user
        )
        
        if args.export:
            with open(args.export, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Load test results exported to: {args.export}")


if __name__ == "__main__":
    asyncio.run(main())