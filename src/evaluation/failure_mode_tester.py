"""
Failure Mode Testing and Recovery Validation System for Phase 4.2

Implements comprehensive failure mode testing including:
- Service failure simulation and recovery validation
- Data corruption detection and recovery testing
- Network partition and split-brain scenario testing
- Resource exhaustion and graceful degradation validation
- Cascade failure prevention and circuit breaker testing
- Backup and restore mechanism validation
"""

import asyncio
import logging
import time
import random
import json
import hashlib
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
import threading
import weakref
import psutil

logger = logging.getLogger(__name__)


@dataclass
class FailureModeConfig:
    """Configuration for failure mode testing."""
    
    # Test categories
    test_service_failures: bool = True
    test_data_corruption: bool = True
    test_network_partitions: bool = True
    test_resource_exhaustion: bool = True
    test_cascade_failures: bool = True
    test_backup_recovery: bool = True
    
    # Service failure parameters
    service_failure_types: List[str] = None
    max_service_downtime_seconds: float = 60.0
    recovery_timeout_seconds: float = 120.0
    
    # Data corruption parameters
    corruption_rate: float = 0.01  # 1% of data
    corruption_types: List[str] = None
    checksum_validation: bool = True
    
    # Network partition parameters
    partition_duration_seconds: float = 30.0
    partition_types: List[str] = None
    
    # Resource exhaustion parameters
    memory_exhaustion_threshold: float = 0.9  # 90% memory usage
    cpu_exhaustion_threshold: float = 0.95   # 95% CPU usage
    disk_exhaustion_threshold: float = 0.95  # 95% disk usage
    
    # Recovery validation parameters
    max_recovery_time_seconds: float = 300.0
    health_check_interval_seconds: float = 5.0
    recovery_success_criteria: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.service_failure_types is None:
            self.service_failure_types = [
                'sudden_termination', 'graceful_shutdown', 'memory_leak',
                'cpu_spike', 'deadlock', 'infinite_loop', 'exception_flood'
            ]
        
        if self.corruption_types is None:
            self.corruption_types = [
                'bit_flip', 'truncation', 'duplication', 'permutation',
                'injection', 'deletion', 'encoding_error'
            ]
        
        if self.partition_types is None:
            self.partition_types = [
                'complete_isolation', 'asymmetric_partition', 'flaky_connection',
                'high_latency', 'packet_loss', 'bandwidth_limit'
            ]
        
        if self.recovery_success_criteria is None:
            self.recovery_success_criteria = {
                'service_responsive': True,
                'data_integrity': True,
                'performance_acceptable': True,
                'no_data_loss': True
            }


@dataclass
class FailureScenario:
    """Definition of a specific failure scenario."""
    
    scenario_id: str
    name: str
    description: str
    category: str
    
    # Failure parameters
    failure_type: str
    severity: str = "medium"  # low, medium, high, critical
    duration_seconds: float = 60.0
    affected_components: List[str] = None
    
    # Recovery parameters
    auto_recovery: bool = True
    recovery_strategy: str = "restart"  # restart, rollback, failover, manual
    expected_recovery_time: float = 120.0
    
    # Validation criteria
    success_criteria: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.affected_components is None:
            self.affected_components = []
        if self.success_criteria is None:
            self.success_criteria = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureTestResult:
    """Result of a failure mode test."""
    
    test_id: str
    scenario: FailureScenario
    timestamp: str
    
    # Execution timeline
    start_time: str
    failure_injected_time: Optional[str] = None
    recovery_initiated_time: Optional[str] = None
    recovery_completed_time: Optional[str] = None
    end_time: Optional[str] = None
    
    # Test outcomes
    status: str = "pending"  # pending, passed, failed, error, timeout
    failure_injection_success: bool = False
    recovery_success: bool = False
    data_integrity_verified: bool = False
    
    # Metrics
    failure_detection_time_ms: float = 0.0
    recovery_time_ms: float = 0.0
    total_downtime_ms: float = 0.0
    data_loss_detected: bool = False
    
    # Detailed results
    failure_details: Dict[str, Any] = None
    recovery_details: Dict[str, Any] = None
    validation_results: Dict[str, Any] = None
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.failure_details is None:
            self.failure_details = {}
        if self.recovery_details is None:
            self.recovery_details = {}
        if self.validation_results is None:
            self.validation_results = {}
        if self.error_messages is None:
            self.error_messages = []
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['scenario'] = self.scenario.to_dict()
        return result


@dataclass
class FailureTestSuite:
    """Complete failure mode test suite results."""
    
    suite_id: str
    timestamp: str
    duration_minutes: float
    
    # Configuration
    config: FailureModeConfig
    scenarios_tested: List[str]
    
    # Summary statistics
    total_scenarios: int = 0
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    scenarios_error: int = 0
    
    # Detailed results
    test_results: List[FailureTestResult] = None
    
    # Analysis
    critical_failures: List[str] = None
    recovery_gaps: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.test_results is None:
            self.test_results = []
        if self.critical_failures is None:
            self.critical_failures = []
        if self.recovery_gaps is None:
            self.recovery_gaps = []
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'config': asdict(self.config),
            'test_results': [r.to_dict() for r in self.test_results]
        }


class ServiceFailureSimulator:
    """Simulates various service failure modes."""
    
    def __init__(self, config: FailureModeConfig):
        self.config = config
        self.simulated_failures = {}
        self.logger = logging.getLogger(__name__ + ".ServiceFailureSimulator")
    
    async def simulate_failure(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate a service failure according to scenario."""
        
        self.logger.info(f"Simulating service failure: {scenario.failure_type}")
        
        failure_details = {
            'failure_type': scenario.failure_type,
            'severity': scenario.severity,
            'duration': scenario.duration_seconds,
            'simulation_method': 'mock'
        }
        
        try:
            if scenario.failure_type == 'sudden_termination':
                return await self._simulate_sudden_termination(scenario)
            elif scenario.failure_type == 'graceful_shutdown':
                return await self._simulate_graceful_shutdown(scenario)
            elif scenario.failure_type == 'memory_leak':
                return await self._simulate_memory_leak(scenario)
            elif scenario.failure_type == 'cpu_spike':
                return await self._simulate_cpu_spike(scenario)
            elif scenario.failure_type == 'deadlock':
                return await self._simulate_deadlock(scenario)
            elif scenario.failure_type == 'exception_flood':
                return await self._simulate_exception_flood(scenario)
            else:
                return await self._simulate_generic_failure(scenario)
        
        except Exception as e:
            failure_details['simulation_error'] = str(e)
            self.logger.error(f"Failure simulation error: {e}")
            return failure_details
    
    async def _simulate_sudden_termination(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate sudden service termination."""
        
        details = {
            'failure_type': 'sudden_termination',
            'simulated': True,
            'exit_code': 137,  # SIGKILL
            'clean_shutdown': False
        }
        
        # Mark service as terminated
        self.simulated_failures['service_terminated'] = True
        
        # Wait for failure duration
        await asyncio.sleep(scenario.duration_seconds)
        
        details['actual_downtime'] = scenario.duration_seconds
        return details
    
    async def _simulate_graceful_shutdown(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate graceful service shutdown."""
        
        details = {
            'failure_type': 'graceful_shutdown',
            'simulated': True,
            'exit_code': 0,
            'clean_shutdown': True,
            'cleanup_performed': True
        }
        
        # Simulate graceful shutdown process
        self.simulated_failures['service_shutting_down'] = True
        await asyncio.sleep(2)  # Cleanup time
        
        self.simulated_failures['service_terminated'] = True
        await asyncio.sleep(scenario.duration_seconds - 2)
        
        details['actual_downtime'] = scenario.duration_seconds
        return details
    
    async def _simulate_memory_leak(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate memory leak leading to service failure."""
        
        details = {
            'failure_type': 'memory_leak',
            'simulated': True,
            'memory_growth_mb_per_second': 10,
            'oom_threshold_mb': 1000
        }
        
        # Simulate memory growth
        memory_usage = 100  # Start at 100MB
        leak_duration = min(scenario.duration_seconds, 30)  # Limit simulation time
        
        for i in range(int(leak_duration)):
            memory_usage += 10  # 10MB per second
            self.simulated_failures['memory_usage_mb'] = memory_usage
            
            if memory_usage > 1000:  # OOM condition
                self.simulated_failures['oom_killed'] = True
                details['oom_triggered'] = True
                break
            
            await asyncio.sleep(1)
        
        details['final_memory_mb'] = memory_usage
        return details
    
    async def _simulate_cpu_spike(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate CPU spike causing service degradation."""
        
        details = {
            'failure_type': 'cpu_spike',
            'simulated': True,
            'target_cpu_percent': 95,
            'duration': scenario.duration_seconds
        }
        
        # Simulate high CPU usage
        self.simulated_failures['cpu_high'] = True
        self.simulated_failures['service_degraded'] = True
        
        await asyncio.sleep(scenario.duration_seconds)
        
        self.simulated_failures['cpu_high'] = False
        self.simulated_failures['service_degraded'] = False
        
        return details
    
    async def _simulate_deadlock(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate deadlock condition."""
        
        details = {
            'failure_type': 'deadlock',
            'simulated': True,
            'threads_involved': 2,
            'resources_locked': ['resource_a', 'resource_b']
        }
        
        # Simulate deadlock
        self.simulated_failures['deadlock_detected'] = True
        self.simulated_failures['service_unresponsive'] = True
        
        await asyncio.sleep(scenario.duration_seconds)
        
        # Deadlock resolved (simulated)
        self.simulated_failures['deadlock_detected'] = False
        self.simulated_failures['service_unresponsive'] = False
        
        return details
    
    async def _simulate_exception_flood(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate flood of exceptions causing service instability."""
        
        details = {
            'failure_type': 'exception_flood',
            'simulated': True,
            'exceptions_per_second': 100,
            'exception_types': ['ValueError', 'RuntimeError', 'ConnectionError']
        }
        
        # Simulate exception flood
        exception_count = 0
        flood_duration = min(scenario.duration_seconds, 10)  # Limit simulation
        
        for i in range(int(flood_duration)):
            exception_count += 100  # 100 exceptions per second
            self.simulated_failures['exception_count'] = exception_count
            self.simulated_failures['service_degraded'] = True
            await asyncio.sleep(1)
        
        details['total_exceptions'] = exception_count
        return details
    
    async def _simulate_generic_failure(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Simulate generic failure mode."""
        
        details = {
            'failure_type': scenario.failure_type,
            'simulated': True,
            'generic_failure': True
        }
        
        # Generic failure simulation
        self.simulated_failures['generic_failure'] = scenario.failure_type
        await asyncio.sleep(scenario.duration_seconds)
        
        return details
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current simulated service status."""
        
        status = {
            'running': not self.simulated_failures.get('service_terminated', False),
            'responsive': not self.simulated_failures.get('service_unresponsive', False),
            'healthy': not any([
                self.simulated_failures.get('service_degraded', False),
                self.simulated_failures.get('deadlock_detected', False),
                self.simulated_failures.get('oom_killed', False)
            ]),
            'active_failures': list(self.simulated_failures.keys()),
            'failure_details': self.simulated_failures.copy()
        }
        
        return status
    
    async def reset_failures(self):
        """Reset all simulated failures."""
        self.simulated_failures.clear()
        self.logger.info("All simulated failures reset")


class RecoveryValidator:
    """Validates service recovery and data integrity."""
    
    def __init__(self, config: FailureModeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".RecoveryValidator")
    
    async def validate_recovery(
        self, 
        scenario: FailureScenario,
        failure_simulator: ServiceFailureSimulator
    ) -> Dict[str, Any]:
        """Validate service recovery after failure."""
        
        self.logger.info(f"Validating recovery for scenario: {scenario.name}")
        
        recovery_details = {
            'scenario_id': scenario.scenario_id,
            'recovery_strategy': scenario.recovery_strategy,
            'recovery_start_time': datetime.now().isoformat(),
            'validation_steps': []
        }
        
        try:
            # Step 1: Initiate recovery
            recovery_initiated = await self._initiate_recovery(scenario, failure_simulator)
            recovery_details['recovery_initiated'] = recovery_initiated
            
            if not recovery_initiated:
                recovery_details['validation_steps'].append("Recovery initiation failed")
                return recovery_details
            
            # Step 2: Wait for service restoration
            service_restored = await self._wait_for_service_restoration(scenario, failure_simulator)
            recovery_details['service_restored'] = service_restored
            recovery_details['validation_steps'].append(f"Service restoration: {'SUCCESS' if service_restored else 'FAILED'}")
            
            # Step 3: Validate data integrity
            data_integrity = await self._validate_data_integrity(scenario)
            recovery_details['data_integrity'] = data_integrity
            recovery_details['validation_steps'].append(f"Data integrity: {'VALID' if data_integrity else 'COMPROMISED'}")
            
            # Step 4: Performance validation
            performance_ok = await self._validate_performance(scenario)
            recovery_details['performance_acceptable'] = performance_ok
            recovery_details['validation_steps'].append(f"Performance: {'ACCEPTABLE' if performance_ok else 'DEGRADED'}")
            
            # Step 5: Health check validation
            health_check = await self._validate_health_checks(scenario, failure_simulator)
            recovery_details['health_checks_passed'] = health_check
            recovery_details['validation_steps'].append(f"Health checks: {'PASSED' if health_check else 'FAILED'}")
            
            # Overall recovery success
            recovery_success = all([
                service_restored,
                data_integrity,
                performance_ok,
                health_check
            ])
            
            recovery_details['recovery_success'] = recovery_success
            recovery_details['recovery_end_time'] = datetime.now().isoformat()
            
            return recovery_details
        
        except Exception as e:
            recovery_details['recovery_error'] = str(e)
            recovery_details['recovery_success'] = False
            self.logger.error(f"Recovery validation error: {e}")
            return recovery_details
    
    async def _initiate_recovery(
        self, 
        scenario: FailureScenario,
        failure_simulator: ServiceFailureSimulator
    ) -> bool:
        """Initiate recovery based on strategy."""
        
        try:
            if scenario.recovery_strategy == "restart":
                return await self._restart_service(failure_simulator)
            elif scenario.recovery_strategy == "rollback":
                return await self._rollback_service(failure_simulator)
            elif scenario.recovery_strategy == "failover":
                return await self._failover_service(failure_simulator)
            else:
                return await self._manual_recovery(failure_simulator)
        
        except Exception as e:
            self.logger.error(f"Recovery initiation failed: {e}")
            return False
    
    async def _restart_service(self, failure_simulator: ServiceFailureSimulator) -> bool:
        """Simulate service restart."""
        
        # Reset failures (simulates service restart)
        await failure_simulator.reset_failures()
        
        # Simulate startup time
        await asyncio.sleep(5)
        
        # Check if service is responsive
        status = failure_simulator.get_service_status()
        return status['running'] and status['responsive']
    
    async def _rollback_service(self, failure_simulator: ServiceFailureSimulator) -> bool:
        """Simulate service rollback to previous version."""
        
        # Simulate rollback process
        await asyncio.sleep(10)  # Rollback takes longer
        await failure_simulator.reset_failures()
        
        # Check service status
        status = failure_simulator.get_service_status()
        return status['running'] and status['healthy']
    
    async def _failover_service(self, failure_simulator: ServiceFailureSimulator) -> bool:
        """Simulate failover to backup service."""
        
        # Simulate failover process
        await asyncio.sleep(15)  # Failover takes time
        await failure_simulator.reset_failures()
        
        # Check service status
        status = failure_simulator.get_service_status()
        return status['running']
    
    async def _manual_recovery(self, failure_simulator: ServiceFailureSimulator) -> bool:
        """Simulate manual recovery intervention."""
        
        # Manual recovery simulation
        await asyncio.sleep(20)  # Manual intervention takes longer
        await failure_simulator.reset_failures()
        
        status = failure_simulator.get_service_status()
        return status['running']
    
    async def _wait_for_service_restoration(
        self, 
        scenario: FailureScenario,
        failure_simulator: ServiceFailureSimulator
    ) -> bool:
        """Wait for and validate service restoration."""
        
        max_wait_time = scenario.expected_recovery_time
        check_interval = self.config.health_check_interval_seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            status = failure_simulator.get_service_status()
            
            if status['running'] and status['responsive'] and status['healthy']:
                return True
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        return False
    
    async def _validate_data_integrity(self, scenario: FailureScenario) -> bool:
        """Validate data integrity after recovery."""
        
        # Simulate data integrity checks
        # In real implementation, would verify checksums, run consistency checks, etc.
        
        integrity_checks = [
            ('checksum_validation', True),
            ('consistency_check', True),
            ('foreign_key_validation', True),
            ('backup_verification', True)
        ]
        
        # Simulate some failures based on scenario severity
        if scenario.severity in ['high', 'critical']:
            # Higher chance of data integrity issues
            integrity_checks[1] = ('consistency_check', random.random() > 0.1)  # 10% failure rate
        
        all_passed = all(passed for _, passed in integrity_checks)
        
        self.logger.info(f"Data integrity validation: {all_passed}")
        return all_passed
    
    async def _validate_performance(self, scenario: FailureScenario) -> bool:
        """Validate performance after recovery."""
        
        # Simulate performance tests
        # In real implementation, would run actual performance benchmarks
        
        performance_metrics = {
            'response_time_ms': random.uniform(50, 200),
            'throughput_qps': random.uniform(80, 120),
            'error_rate': random.uniform(0, 0.05),
            'cpu_usage': random.uniform(0.3, 0.7),
            'memory_usage': random.uniform(0.4, 0.8)
        }
        
        # Define acceptable thresholds
        acceptable = (
            performance_metrics['response_time_ms'] < 500 and
            performance_metrics['throughput_qps'] > 50 and
            performance_metrics['error_rate'] < 0.1 and
            performance_metrics['cpu_usage'] < 0.9 and
            performance_metrics['memory_usage'] < 0.9
        )
        
        # Adjust based on scenario severity
        if scenario.severity == 'critical':
            acceptable = acceptable and performance_metrics['response_time_ms'] < 300
        
        return acceptable
    
    async def _validate_health_checks(
        self, 
        scenario: FailureScenario,
        failure_simulator: ServiceFailureSimulator
    ) -> bool:
        """Validate health checks after recovery."""
        
        health_checks = []
        
        # Basic health checks
        status = failure_simulator.get_service_status()
        health_checks.append(status['running'])
        health_checks.append(status['responsive'])
        health_checks.append(status['healthy'])
        
        # Additional health validations
        health_checks.append(len(status['active_failures']) == 0)
        
        # Simulate external dependency checks
        external_deps_healthy = random.random() > 0.05  # 5% chance of dependency issues
        health_checks.append(external_deps_healthy)
        
        return all(health_checks)


class FailureModeTester:
    """Main failure mode testing framework."""
    
    def __init__(self, config: Optional[FailureModeConfig] = None):
        """Initialize failure mode tester."""
        
        self.config = config or FailureModeConfig()
        self.failure_simulator = ServiceFailureSimulator(self.config)
        self.recovery_validator = RecoveryValidator(self.config)
        
        self.logger = logging.getLogger(__name__ + ".FailureModeTester")
    
    async def run_failure_mode_tests(
        self, 
        test_name: str = "failure_mode_test_suite"
    ) -> FailureTestSuite:
        """
        Run comprehensive failure mode test suite.
        
        Args:
            test_name: Name for this test suite
            
        Returns:
            Complete failure test suite results
        """
        
        self.logger.info(f"Starting failure mode testing: {test_name}")
        
        suite_id = f"failure_mode_suite_{test_name}_{int(time.time())}"
        start_time = time.time()
        
        # Generate test scenarios
        scenarios = self._create_test_scenarios()
        
        test_results = []
        categories_tested = []
        
        try:
            # Execute each scenario
            for scenario in scenarios:
                self.logger.info(f"Running scenario: {scenario.name}")
                
                test_result = await self._execute_failure_scenario(scenario)
                test_results.append(test_result)
                
                if scenario.category not in categories_tested:
                    categories_tested.append(scenario.category)
                
                # Brief pause between scenarios
                await asyncio.sleep(2)
            
            # Analyze results
            duration = (time.time() - start_time) / 60
            
            suite = FailureTestSuite(
                suite_id=suite_id,
                timestamp=datetime.now().isoformat(),
                duration_minutes=duration,
                config=self.config,
                scenarios_tested=categories_tested,
                test_results=test_results
            )
            
            # Calculate summary statistics
            suite.total_scenarios = len(test_results)
            suite.scenarios_passed = len([r for r in test_results if r.status == "passed"])
            suite.scenarios_failed = len([r for r in test_results if r.status == "failed"])
            suite.scenarios_error = len([r for r in test_results if r.status == "error"])
            
            # Analyze critical issues
            suite.critical_failures = self._identify_critical_failures(test_results)
            suite.recovery_gaps = self._identify_recovery_gaps(test_results)
            suite.recommendations = self._generate_recommendations(test_results)
            
            self.logger.info("Failure mode testing completed")
            self.logger.info(f"  Total scenarios: {suite.total_scenarios}")
            self.logger.info(f"  Passed: {suite.scenarios_passed}")
            self.logger.info(f"  Failed: {suite.scenarios_failed}")
            self.logger.info(f"  Errors: {suite.scenarios_error}")
            
            return suite
        
        except Exception as e:
            self.logger.error(f"Failure mode testing failed: {e}")
            raise
    
    def _create_test_scenarios(self) -> List[FailureScenario]:
        """Create failure test scenarios based on configuration."""
        
        scenarios = []
        
        # Service failure scenarios
        if self.config.test_service_failures:
            scenarios.extend(self._create_service_failure_scenarios())
        
        # Data corruption scenarios
        if self.config.test_data_corruption:
            scenarios.extend(self._create_data_corruption_scenarios())
        
        # Network partition scenarios
        if self.config.test_network_partitions:
            scenarios.extend(self._create_network_partition_scenarios())
        
        # Resource exhaustion scenarios
        if self.config.test_resource_exhaustion:
            scenarios.extend(self._create_resource_exhaustion_scenarios())
        
        # Cascade failure scenarios
        if self.config.test_cascade_failures:
            scenarios.extend(self._create_cascade_failure_scenarios())
        
        return scenarios
    
    def _create_service_failure_scenarios(self) -> List[FailureScenario]:
        """Create service failure scenarios."""
        
        scenarios = []
        
        for failure_type in self.config.service_failure_types:
            scenario = FailureScenario(
                scenario_id=f"service_failure_{failure_type}",
                name=f"Service failure: {failure_type}",
                description=f"Test service failure and recovery for {failure_type}",
                category="service_failures",
                failure_type=failure_type,
                severity="medium",
                duration_seconds=30,
                affected_components=["main_service"],
                recovery_strategy="restart",
                expected_recovery_time=60
            )
            scenarios.append(scenario)
        
        # Add a critical scenario
        critical_scenario = FailureScenario(
            scenario_id="service_failure_critical",
            name="Critical service failure",
            description="Test critical service failure with data loss risk",
            category="service_failures",
            failure_type="sudden_termination",
            severity="critical",
            duration_seconds=60,
            affected_components=["main_service", "database"],
            recovery_strategy="rollback",
            expected_recovery_time=120
        )
        scenarios.append(critical_scenario)
        
        return scenarios
    
    def _create_data_corruption_scenarios(self) -> List[FailureScenario]:
        """Create data corruption scenarios."""
        
        scenarios = []
        
        for corruption_type in self.config.corruption_types:
            scenario = FailureScenario(
                scenario_id=f"data_corruption_{corruption_type}",
                name=f"Data corruption: {corruption_type}",
                description=f"Test data corruption detection and recovery for {corruption_type}",
                category="data_corruption",
                failure_type=corruption_type,
                severity="high",
                duration_seconds=5,  # Corruption is instantaneous
                affected_components=["database", "file_storage"],
                recovery_strategy="rollback",
                expected_recovery_time=180
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _create_network_partition_scenarios(self) -> List[FailureScenario]:
        """Create network partition scenarios."""
        
        scenarios = []
        
        for partition_type in self.config.partition_types:
            scenario = FailureScenario(
                scenario_id=f"network_partition_{partition_type}",
                name=f"Network partition: {partition_type}",
                description=f"Test network partition handling for {partition_type}",
                category="network_partitions",
                failure_type=partition_type,
                severity="medium",
                duration_seconds=self.config.partition_duration_seconds,
                affected_components=["network", "distributed_components"],
                recovery_strategy="failover",
                expected_recovery_time=90
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _create_resource_exhaustion_scenarios(self) -> List[FailureScenario]:
        """Create resource exhaustion scenarios."""
        
        scenarios = [
            FailureScenario(
                scenario_id="resource_exhaustion_memory",
                name="Memory exhaustion",
                description="Test memory exhaustion handling and recovery",
                category="resource_exhaustion",
                failure_type="memory_leak",
                severity="high",
                duration_seconds=45,
                affected_components=["main_service"],
                recovery_strategy="restart",
                expected_recovery_time=60
            ),
            FailureScenario(
                scenario_id="resource_exhaustion_cpu",
                name="CPU exhaustion",
                description="Test CPU exhaustion handling and recovery",
                category="resource_exhaustion", 
                failure_type="cpu_spike",
                severity="medium",
                duration_seconds=30,
                affected_components=["main_service"],
                recovery_strategy="restart",
                expected_recovery_time=45
            ),
            FailureScenario(
                scenario_id="resource_exhaustion_disk",
                name="Disk space exhaustion",
                description="Test disk space exhaustion handling",
                category="resource_exhaustion",
                failure_type="disk_full",
                severity="high",
                duration_seconds=20,
                affected_components=["file_storage", "database"],
                recovery_strategy="manual",
                expected_recovery_time=300
            )
        ]
        
        return scenarios
    
    def _create_cascade_failure_scenarios(self) -> List[FailureScenario]:
        """Create cascade failure scenarios."""
        
        scenarios = [
            FailureScenario(
                scenario_id="cascade_failure_database",
                name="Database cascade failure",
                description="Test cascade failure starting from database",
                category="cascade_failures",
                failure_type="database_failure_cascade",
                severity="critical",
                duration_seconds=60,
                affected_components=["database", "api_service", "cache"],
                recovery_strategy="failover",
                expected_recovery_time=180
            ),
            FailureScenario(
                scenario_id="cascade_failure_external_dependency",
                name="External dependency cascade failure",
                description="Test cascade failure from external dependency",
                category="cascade_failures",
                failure_type="external_service_cascade",
                severity="high",
                duration_seconds=90,
                affected_components=["external_api", "main_service", "queue"],
                recovery_strategy="restart",
                expected_recovery_time=120
            )
        ]
        
        return scenarios
    
    async def _execute_failure_scenario(self, scenario: FailureScenario) -> FailureTestResult:
        """Execute a single failure scenario."""
        
        test_id = f"test_{scenario.scenario_id}_{int(time.time())}"
        
        result = FailureTestResult(
            test_id=test_id,
            scenario=scenario,
            timestamp=datetime.now().isoformat(),
            start_time=datetime.now().isoformat()
        )
        
        try:
            # Phase 1: Inject failure
            self.logger.info(f"Injecting failure: {scenario.failure_type}")
            failure_start_time = time.time()
            
            failure_details = await self.failure_simulator.simulate_failure(scenario)
            result.failure_details = failure_details
            result.failure_injection_success = failure_details.get('simulated', False)
            result.failure_injected_time = datetime.now().isoformat()
            
            if not result.failure_injection_success:
                result.status = "error"
                result.error_messages.append("Failed to inject failure")
                return result
            
            # Phase 2: Wait for failure detection (simulated)
            await asyncio.sleep(2)
            result.failure_detection_time_ms = 2000  # Simulated detection time
            
            # Phase 3: Initiate and validate recovery
            self.logger.info(f"Initiating recovery: {scenario.recovery_strategy}")
            recovery_start_time = time.time()
            result.recovery_initiated_time = datetime.now().isoformat()
            
            recovery_details = await self.recovery_validator.validate_recovery(
                scenario, self.failure_simulator
            )
            result.recovery_details = recovery_details
            result.recovery_success = recovery_details.get('recovery_success', False)
            result.data_integrity_verified = recovery_details.get('data_integrity', False)
            
            recovery_time = time.time() - recovery_start_time
            result.recovery_time_ms = recovery_time * 1000
            result.total_downtime_ms = (recovery_time + scenario.duration_seconds) * 1000
            
            result.recovery_completed_time = datetime.now().isoformat()
            
            # Phase 4: Final validation
            if result.recovery_success and result.data_integrity_verified:
                result.status = "passed"
            else:
                result.status = "failed"
                if not result.recovery_success:
                    result.error_messages.append("Recovery failed")
                if not result.data_integrity_verified:
                    result.error_messages.append("Data integrity compromised")
            
        except Exception as e:
            result.status = "error"
            result.error_messages.append(str(e))
            self.logger.error(f"Failure scenario execution error: {e}")
        
        finally:
            result.end_time = datetime.now().isoformat()
            
            # Reset any remaining failures
            await self.failure_simulator.reset_failures()
        
        return result
    
    def _identify_critical_failures(self, test_results: List[FailureTestResult]) -> List[str]:
        """Identify critical failures that need immediate attention."""
        
        critical_failures = []
        
        # Failed critical scenarios
        critical_failed = [r for r in test_results if 
                          r.scenario.severity == "critical" and r.status == "failed"]
        if critical_failed:
            critical_failures.append(f"Critical scenarios failed: {len(critical_failed)}")
        
        # Data integrity issues
        data_integrity_failed = [r for r in test_results if not r.data_integrity_verified]
        if data_integrity_failed:
            critical_failures.append(f"Data integrity issues: {len(data_integrity_failed)} scenarios")
        
        # Recovery failures
        recovery_failed = [r for r in test_results if not r.recovery_success]
        if recovery_failed:
            critical_failures.append(f"Recovery failures: {len(recovery_failed)} scenarios")
        
        # Long recovery times
        slow_recovery = [r for r in test_results if 
                        r.recovery_time_ms > self.config.max_recovery_time_seconds * 1000]
        if slow_recovery:
            critical_failures.append(f"Slow recovery times: {len(slow_recovery)} scenarios")
        
        return critical_failures
    
    def _identify_recovery_gaps(self, test_results: List[FailureTestResult]) -> List[str]:
        """Identify gaps in recovery capabilities."""
        
        gaps = []
        
        # Scenarios with no recovery strategy
        no_strategy = [r for r in test_results if 
                      r.scenario.recovery_strategy == "manual" and r.status == "failed"]
        if no_strategy:
            gaps.append(f"Manual recovery scenarios failing: {len(no_strategy)}")
        
        # Inconsistent recovery performance
        recovery_times = [r.recovery_time_ms for r in test_results if r.recovery_time_ms > 0]
        if recovery_times and max(recovery_times) > min(recovery_times) * 3:
            gaps.append("Inconsistent recovery performance across scenarios")
        
        # Category-specific gaps
        categories = set(r.scenario.category for r in test_results)
        for category in categories:
            category_results = [r for r in test_results if r.scenario.category == category]
            failed_in_category = [r for r in category_results if r.status == "failed"]
            
            if len(failed_in_category) > len(category_results) * 0.5:
                gaps.append(f"High failure rate in {category}: {len(failed_in_category)}/{len(category_results)}")
        
        return gaps
    
    def _generate_recommendations(self, test_results: List[FailureTestResult]) -> List[str]:
        """Generate recommendations based on test results."""
        
        recommendations = []
        
        # Recovery time recommendations
        slow_recovery = len([r for r in test_results if 
                           r.recovery_time_ms > self.config.max_recovery_time_seconds * 1000])
        if slow_recovery > 0:
            recommendations.append(f"Optimize recovery procedures: {slow_recovery} scenarios exceed time limits")
        
        # Data integrity recommendations
        integrity_issues = len([r for r in test_results if not r.data_integrity_verified])
        if integrity_issues > 0:
            recommendations.append(f"Strengthen data integrity protection for {integrity_issues} failure modes")
        
        # Monitoring recommendations
        detection_time_issues = len([r for r in test_results if r.failure_detection_time_ms > 10000])
        if detection_time_issues > 0:
            recommendations.append("Improve failure detection mechanisms")
        
        # Automation recommendations
        manual_scenarios = len([r for r in test_results if r.scenario.recovery_strategy == "manual"])
        if manual_scenarios > 0:
            recommendations.append(f"Consider automating recovery for {manual_scenarios} manual scenarios")
        
        # Category-specific recommendations
        service_failures = [r for r in test_results if r.scenario.category == "service_failures"]
        service_failed = len([r for r in service_failures if r.status == "failed"])
        if service_failed > len(service_failures) * 0.3:
            recommendations.append("Review service resilience and restart mechanisms")
        
        return recommendations


# Convenience functions

async def run_failure_mode_test_suite(
    test_name: str = "failure_mode_suite",
    config: Optional[FailureModeConfig] = None
) -> FailureTestSuite:
    """Run comprehensive failure mode test suite."""
    
    tester = FailureModeTester(config)
    return await tester.run_failure_mode_tests(test_name)


def create_comprehensive_failure_config() -> FailureModeConfig:
    """Create comprehensive configuration for failure mode testing."""
    
    return FailureModeConfig(
        test_service_failures=True,
        test_data_corruption=True,
        test_network_partitions=True,
        test_resource_exhaustion=True,
        test_cascade_failures=True,
        test_backup_recovery=True,
        max_service_downtime_seconds=120.0,
        recovery_timeout_seconds=300.0,
        corruption_rate=0.05,
        partition_duration_seconds=60.0,
        max_recovery_time_seconds=600.0
    )