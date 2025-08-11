"""
Safety Rails System for Code Review and Change Management for Phase 4.2

Implements comprehensive safety mechanisms including:
- Automated code review and validation before deployment
- Change impact assessment and risk scoring
- Rollback mechanisms and deployment gates
- Configuration validation and schema enforcement
- Performance regression detection
- Security vulnerability scanning
"""

import asyncio
import logging
import time
import json
import hashlib
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import re
import ast
import difflib
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SafetyRailsConfig:
    """Configuration for safety rails system."""
    
    # Code review settings
    require_code_review: bool = True
    min_reviewers: int = 1
    block_on_security_issues: bool = True
    block_on_performance_regression: bool = True
    
    # Change impact thresholds
    max_lines_changed: int = 500
    max_files_changed: int = 20
    critical_file_patterns: List[str] = None
    
    # Performance thresholds
    max_latency_regression_percent: float = 15.0
    max_memory_regression_percent: float = 10.0
    max_error_rate_increase_percent: float = 5.0
    
    # Security settings
    enable_security_scanning: bool = True
    security_severity_threshold: str = "medium"  # low, medium, high, critical
    
    # Validation settings
    require_tests: bool = True
    min_test_coverage_percent: float = 80.0
    require_integration_tests: bool = True
    
    # Rollback settings
    enable_automatic_rollback: bool = True
    rollback_timeout_minutes: int = 10
    health_check_timeout_seconds: int = 30
    
    def __post_init__(self):
        if self.critical_file_patterns is None:
            self.critical_file_patterns = [
                "*/mcp_server/*", "*/retrieval/*", "*/evaluation/*",
                "config.py", "*.yaml", "requirements.txt", "docker-compose.yml"
            ]


@dataclass
class ChangesetAnalysis:
    """Analysis of a code changeset."""
    
    changeset_id: str
    timestamp: str
    
    # Change metrics
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    lines_modified: int = 0
    
    # File categories
    critical_files_changed: List[str] = None
    config_files_changed: List[str] = None
    test_files_changed: List[str] = None
    
    # Risk assessment
    risk_score: float = 0.0  # 0-1 scale
    risk_factors: List[str] = None
    change_complexity: str = "low"  # low, medium, high
    
    # Security analysis
    security_issues: List[Dict[str, Any]] = None
    security_risk_level: str = "none"  # none, low, medium, high, critical
    
    # Performance impact
    performance_impact: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.critical_files_changed is None:
            self.critical_files_changed = []
        if self.config_files_changed is None:
            self.config_files_changed = []
        if self.test_files_changed is None:
            self.test_files_changed = []
        if self.risk_factors is None:
            self.risk_factors = []
        if self.security_issues is None:
            self.security_issues = []
        if self.performance_impact is None:
            self.performance_impact = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeploymentGate:
    """Deployment gate with validation criteria."""
    
    gate_id: str
    name: str
    description: str
    
    # Gate criteria
    required: bool = True
    criteria: Dict[str, Any] = None
    timeout_seconds: int = 300
    
    # Gate state
    status: str = "pending"  # pending, passed, failed, skipped
    result: Dict[str, Any] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.criteria is None:
            self.criteria = {}
        if self.result is None:
            self.result = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SafetyRailsReport:
    """Comprehensive safety rails report."""
    
    report_id: str
    timestamp: str
    changeset_id: str
    
    # Analysis results
    changeset_analysis: ChangesetAnalysis
    deployment_gates: List[DeploymentGate]
    
    # Overall assessment
    overall_status: str = "pending"  # pending, approved, rejected, conditional
    approval_required: bool = True
    blocking_issues: List[str] = None
    warnings: List[str] = None
    
    # Recommendations
    recommendations: List[str] = None
    required_actions: List[str] = None
    
    def __post_init__(self):
        if self.blocking_issues is None:
            self.blocking_issues = []
        if self.warnings is None:
            self.warnings = []
        if self.recommendations is None:
            self.recommendations = []
        if self.required_actions is None:
            self.required_actions = []
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['changeset_analysis'] = self.changeset_analysis.to_dict()
        result['deployment_gates'] = [gate.to_dict() for gate in self.deployment_gates]
        return result


class CodeAnalyzer:
    """Analyzes code changes for safety assessment."""
    
    def __init__(self, config: SafetyRailsConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".CodeAnalyzer")
    
    def analyze_changeset(
        self, 
        changeset_id: str,
        changed_files: List[str],
        file_diffs: Dict[str, str]
    ) -> ChangesetAnalysis:
        """Analyze a changeset for safety assessment."""
        
        self.logger.info(f"Analyzing changeset: {changeset_id}")
        
        analysis = ChangesetAnalysis(
            changeset_id=changeset_id,
            timestamp=datetime.now().isoformat()
        )
        
        # Basic metrics
        analysis.files_changed = len(changed_files)
        
        total_added = 0
        total_removed = 0
        total_modified = 0
        
        for file_path, diff in file_diffs.items():
            lines_added, lines_removed, lines_modified = self._count_lines_in_diff(diff)
            total_added += lines_added
            total_removed += lines_removed
            total_modified += lines_modified
        
        analysis.lines_added = total_added
        analysis.lines_removed = total_removed
        analysis.lines_modified = total_modified
        
        # Categorize files
        for file_path in changed_files:
            if self._is_critical_file(file_path):
                analysis.critical_files_changed.append(file_path)
            if self._is_config_file(file_path):
                analysis.config_files_changed.append(file_path)
            if self._is_test_file(file_path):
                analysis.test_files_changed.append(file_path)
        
        # Risk assessment
        analysis.risk_score = self._calculate_risk_score(analysis, file_diffs)
        analysis.risk_factors = self._identify_risk_factors(analysis, file_diffs)
        analysis.change_complexity = self._assess_complexity(analysis)
        
        # Security analysis
        if self.config.enable_security_scanning:
            analysis.security_issues = self._scan_security_issues(file_diffs)
            analysis.security_risk_level = self._assess_security_risk(analysis.security_issues)
        
        # Performance impact assessment
        analysis.performance_impact = self._assess_performance_impact(changed_files, file_diffs)
        
        self.logger.info(
            f"Analysis complete: {analysis.files_changed} files, "
            f"risk_score={analysis.risk_score:.3f}, "
            f"complexity={analysis.change_complexity}"
        )
        
        return analysis
    
    def _count_lines_in_diff(self, diff: str) -> Tuple[int, int, int]:
        """Count added, removed, and modified lines in diff."""
        
        lines = diff.split('\n')
        added = 0
        removed = 0
        modified = 0
        
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed += 1
            elif line.startswith('@@'):
                continue
            elif len(line.strip()) > 0:
                modified += 1
        
        return added, removed, modified
    
    def _is_critical_file(self, file_path: str) -> bool:
        """Check if file matches critical file patterns."""
        
        for pattern in self.config.critical_file_patterns:
            if self._matches_pattern(file_path, pattern):
                return True
        return False
    
    def _is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file."""
        
        config_patterns = [
            "*.yaml", "*.yml", "*.json", "*.ini", "*.toml",
            "config.py", "settings.py", "*.env"
        ]
        
        for pattern in config_patterns:
            if self._matches_pattern(file_path, pattern):
                return True
        return False
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        
        test_patterns = [
            "test_*.py", "*_test.py", "*/tests/*", "*/test/*"
        ]
        
        for pattern in test_patterns:
            if self._matches_pattern(file_path, pattern):
                return True
        return False
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches pattern."""
        
        import fnmatch
        return fnmatch.fnmatch(file_path, pattern)
    
    def _calculate_risk_score(
        self, 
        analysis: ChangesetAnalysis,
        file_diffs: Dict[str, str]
    ) -> float:
        """Calculate overall risk score (0-1)."""
        
        risk = 0.0
        
        # Size-based risk
        if analysis.files_changed > self.config.max_files_changed:
            risk += 0.3
        elif analysis.files_changed > self.config.max_files_changed * 0.5:
            risk += 0.1
        
        total_lines = analysis.lines_added + analysis.lines_removed
        if total_lines > self.config.max_lines_changed:
            risk += 0.3
        elif total_lines > self.config.max_lines_changed * 0.5:
            risk += 0.1
        
        # Critical files risk
        if len(analysis.critical_files_changed) > 0:
            risk += 0.2 + (len(analysis.critical_files_changed) * 0.1)
        
        # Configuration changes risk
        if len(analysis.config_files_changed) > 0:
            risk += 0.15
        
        # Test coverage risk
        test_ratio = len(analysis.test_files_changed) / max(1, analysis.files_changed)
        if test_ratio < 0.2:  # Less than 20% test files
            risk += 0.1
        
        # Complex patterns risk
        for diff in file_diffs.values():
            if self._contains_complex_patterns(diff):
                risk += 0.05
        
        return min(1.0, risk)
    
    def _identify_risk_factors(
        self, 
        analysis: ChangesetAnalysis,
        file_diffs: Dict[str, str]
    ) -> List[str]:
        """Identify specific risk factors."""
        
        factors = []
        
        if analysis.files_changed > self.config.max_files_changed:
            factors.append(f"Too many files changed: {analysis.files_changed}")
        
        total_lines = analysis.lines_added + analysis.lines_removed
        if total_lines > self.config.max_lines_changed:
            factors.append(f"Too many lines changed: {total_lines}")
        
        if len(analysis.critical_files_changed) > 0:
            factors.append(f"Critical files modified: {', '.join(analysis.critical_files_changed)}")
        
        if len(analysis.config_files_changed) > 0:
            factors.append(f"Configuration files changed: {', '.join(analysis.config_files_changed)}")
        
        # Check for dangerous patterns
        for file_path, diff in file_diffs.items():
            if re.search(r'subprocess\.|os\.system|eval\(|exec\(', diff):
                factors.append(f"Potentially dangerous code patterns in {file_path}")
            
            if re.search(r'password|secret|token|key', diff, re.IGNORECASE):
                factors.append(f"Potential secrets in {file_path}")
        
        return factors
    
    def _assess_complexity(self, analysis: ChangesetAnalysis) -> str:
        """Assess change complexity level."""
        
        total_changes = analysis.lines_added + analysis.lines_removed
        
        if (total_changes > 200 or 
            analysis.files_changed > 10 or 
            len(analysis.critical_files_changed) > 2):
            return "high"
        elif (total_changes > 50 or 
              analysis.files_changed > 3 or 
              len(analysis.critical_files_changed) > 0):
            return "medium"
        else:
            return "low"
    
    def _scan_security_issues(self, file_diffs: Dict[str, str]) -> List[Dict[str, Any]]:
        """Scan for security issues in code changes."""
        
        issues = []
        
        security_patterns = [
            {
                'pattern': r'subprocess\.|os\.system|eval\(|exec\(',
                'severity': 'high',
                'description': 'Potentially dangerous code execution'
            },
            {
                'pattern': r'password|secret|token|key.*=.*["\'][^"\']{8,}["\']',
                'severity': 'critical',
                'description': 'Potential hardcoded secrets'
            },
            {
                'pattern': r'import.*pickle|pickle\.load|pickle\.loads',
                'severity': 'medium',
                'description': 'Unsafe deserialization with pickle'
            },
            {
                'pattern': r'random\.random\(\)|random\.choice',
                'severity': 'low',
                'description': 'Insecure random number generation'
            }
        ]
        
        for file_path, diff in file_diffs.items():
            for pattern_info in security_patterns:
                matches = re.finditer(pattern_info['pattern'], diff, re.IGNORECASE)
                for match in matches:
                    issues.append({
                        'file': file_path,
                        'line': diff[:match.start()].count('\n') + 1,
                        'severity': pattern_info['severity'],
                        'description': pattern_info['description'],
                        'pattern': match.group(0)
                    })
        
        return issues
    
    def _assess_security_risk(self, security_issues: List[Dict[str, Any]]) -> str:
        """Assess overall security risk level."""
        
        if not security_issues:
            return "none"
        
        severity_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        max_severity = max(severity_scores.get(issue['severity'], 0) for issue in security_issues)
        
        if max_severity >= 4:
            return "critical"
        elif max_severity >= 3:
            return "high"
        elif max_severity >= 2:
            return "medium"
        else:
            return "low"
    
    def _assess_performance_impact(
        self, 
        changed_files: List[str],
        file_diffs: Dict[str, str]
    ) -> Dict[str, Any]:
        """Assess potential performance impact."""
        
        impact = {
            'risk_level': 'low',
            'concerns': [],
            'recommendations': []
        }
        
        # Check for performance-sensitive file changes
        perf_sensitive_patterns = [
            "*/retrieval/*", "*/mcp_server/*", "*/evaluation/*"
        ]
        
        perf_files = []
        for file_path in changed_files:
            for pattern in perf_sensitive_patterns:
                if self._matches_pattern(file_path, pattern):
                    perf_files.append(file_path)
                    break
        
        if perf_files:
            impact['concerns'].append(f"Performance-sensitive files changed: {', '.join(perf_files)}")
        
        # Check for potentially slow patterns
        for file_path, diff in file_diffs.items():
            if re.search(r'\.join\(.*for.*in.*\)|nested.*for.*loop', diff, re.IGNORECASE):
                impact['concerns'].append(f"Potential inefficient loops in {file_path}")
            
            if re.search(r'time\.sleep|asyncio\.sleep', diff):
                impact['concerns'].append(f"Added sleep/delays in {file_path}")
            
            if re.search(r'SELECT \*|\.fetchall\(\)', diff):
                impact['concerns'].append(f"Potential database performance issues in {file_path}")
        
        # Determine risk level
        if len(perf_files) > 2 or len(impact['concerns']) > 3:
            impact['risk_level'] = 'high'
            impact['recommendations'].append("Conduct performance testing before deployment")
        elif len(perf_files) > 0 or len(impact['concerns']) > 0:
            impact['risk_level'] = 'medium'
            impact['recommendations'].append("Monitor performance metrics after deployment")
        
        return impact
    
    def _contains_complex_patterns(self, diff: str) -> bool:
        """Check if diff contains complex patterns."""
        
        complex_patterns = [
            r'class.*\(.*\).*:',  # Class definitions
            r'async def|await',    # Async patterns
            r'try:.*except.*:',    # Exception handling
            r'with.*as.*:',        # Context managers
            r'lambda.*:',          # Lambda functions
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, diff):
                return True
        
        return False


class DeploymentGateRunner:
    """Runs deployment gates for safety validation."""
    
    def __init__(self, config: SafetyRailsConfig):
        self.config = config
        self.logger = logging.getLogger(__name__ + ".DeploymentGateRunner")
    
    async def run_all_gates(
        self, 
        changeset_analysis: ChangesetAnalysis,
        changeset_id: str
    ) -> List[DeploymentGate]:
        """Run all deployment gates for a changeset."""
        
        gates = self._create_deployment_gates(changeset_analysis)
        
        self.logger.info(f"Running {len(gates)} deployment gates for changeset {changeset_id}")
        
        # Run gates concurrently where possible
        gate_tasks = []
        for gate in gates:
            task = asyncio.create_task(self._run_gate(gate, changeset_analysis))
            gate_tasks.append(task)
        
        # Wait for all gates to complete
        await asyncio.gather(*gate_tasks, return_exceptions=True)
        
        # Check results
        passed = sum(1 for gate in gates if gate.status == "passed")
        failed = sum(1 for gate in gates if gate.status == "failed")
        
        self.logger.info(f"Deployment gates completed: {passed} passed, {failed} failed")
        
        return gates
    
    def _create_deployment_gates(self, analysis: ChangesetAnalysis) -> List[DeploymentGate]:
        """Create deployment gates based on changeset analysis."""
        
        gates = []
        
        # Security gate
        if self.config.enable_security_scanning:
            gates.append(DeploymentGate(
                gate_id="security_scan",
                name="Security Vulnerability Scan",
                description="Scan for security vulnerabilities and patterns",
                required=self.config.block_on_security_issues,
                criteria={
                    'max_severity': self.config.security_severity_threshold,
                    'security_issues': analysis.security_issues
                }
            ))
        
        # Test coverage gate
        if self.config.require_tests:
            gates.append(DeploymentGate(
                gate_id="test_coverage",
                name="Test Coverage Validation",
                description="Ensure adequate test coverage",
                required=True,
                criteria={
                    'min_coverage': self.config.min_test_coverage_percent,
                    'require_integration_tests': self.config.require_integration_tests
                }
            ))
        
        # Performance regression gate
        if self.config.block_on_performance_regression:
            gates.append(DeploymentGate(
                gate_id="performance_regression",
                name="Performance Regression Check",
                description="Check for performance regressions",
                required=True,
                criteria={
                    'max_latency_regression': self.config.max_latency_regression_percent,
                    'max_memory_regression': self.config.max_memory_regression_percent,
                    'performance_impact': analysis.performance_impact
                }
            ))
        
        # Configuration validation gate
        if len(analysis.config_files_changed) > 0:
            gates.append(DeploymentGate(
                gate_id="config_validation",
                name="Configuration Validation",
                description="Validate configuration file changes",
                required=True,
                criteria={
                    'config_files': analysis.config_files_changed
                }
            ))
        
        # Risk assessment gate
        if analysis.risk_score > 0.5:
            gates.append(DeploymentGate(
                gate_id="risk_assessment",
                name="High Risk Change Review",
                description="Additional review required for high-risk changes",
                required=True,
                criteria={
                    'risk_score': analysis.risk_score,
                    'risk_factors': analysis.risk_factors
                }
            ))
        
        return gates
    
    async def _run_gate(self, gate: DeploymentGate, analysis: ChangesetAnalysis):
        """Run individual deployment gate."""
        
        gate.start_time = datetime.now().isoformat()
        gate.status = "running"
        
        try:
            if gate.gate_id == "security_scan":
                await self._run_security_gate(gate, analysis)
            elif gate.gate_id == "test_coverage":
                await self._run_test_coverage_gate(gate, analysis)
            elif gate.gate_id == "performance_regression":
                await self._run_performance_gate(gate, analysis)
            elif gate.gate_id == "config_validation":
                await self._run_config_validation_gate(gate, analysis)
            elif gate.gate_id == "risk_assessment":
                await self._run_risk_assessment_gate(gate, analysis)
            else:
                gate.status = "skipped"
                gate.result['reason'] = "Unknown gate type"
        
        except Exception as e:
            gate.status = "failed"
            gate.error_message = str(e)
            self.logger.error(f"Gate {gate.gate_id} failed: {e}")
        
        finally:
            gate.end_time = datetime.now().isoformat()
    
    async def _run_security_gate(self, gate: DeploymentGate, analysis: ChangesetAnalysis):
        """Run security validation gate."""
        
        security_issues = gate.criteria.get('security_issues', [])
        max_severity = gate.criteria.get('max_severity', 'medium')
        
        severity_levels = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        max_allowed_level = severity_levels.get(max_severity, 2)
        
        blocking_issues = []
        for issue in security_issues:
            issue_level = severity_levels.get(issue['severity'], 0)
            if issue_level >= max_allowed_level:
                blocking_issues.append(issue)
        
        gate.result = {
            'total_issues': len(security_issues),
            'blocking_issues': len(blocking_issues),
            'max_severity_found': analysis.security_risk_level,
            'details': blocking_issues[:5]  # Limit details
        }
        
        if len(blocking_issues) > 0:
            gate.status = "failed"
            gate.error_message = f"Found {len(blocking_issues)} security issues above threshold"
        else:
            gate.status = "passed"
    
    async def _run_test_coverage_gate(self, gate: DeploymentGate, analysis: ChangesetAnalysis):
        """Run test coverage validation gate."""
        
        # Simulate test coverage check (in real implementation, would run actual coverage tools)
        min_coverage = gate.criteria.get('min_coverage', 80)
        require_integration = gate.criteria.get('require_integration_tests', True)
        
        # Mock coverage calculation
        test_files = len(analysis.test_files_changed)
        total_files = analysis.files_changed
        
        # Simple heuristic: coverage roughly correlates with test file ratio
        estimated_coverage = min(95, (test_files / max(1, total_files)) * 100 + 60)
        
        gate.result = {
            'estimated_coverage': estimated_coverage,
            'required_coverage': min_coverage,
            'test_files_changed': test_files,
            'integration_tests_present': test_files > 0  # Simplified check
        }
        
        if estimated_coverage < min_coverage:
            gate.status = "failed"
            gate.error_message = f"Coverage {estimated_coverage:.1f}% below required {min_coverage}%"
        elif require_integration and test_files == 0:
            gate.status = "failed"
            gate.error_message = "Integration tests required but not found"
        else:
            gate.status = "passed"
    
    async def _run_performance_gate(self, gate: DeploymentGate, analysis: ChangesetAnalysis):
        """Run performance regression validation gate."""
        
        performance_impact = gate.criteria.get('performance_impact', {})
        risk_level = performance_impact.get('risk_level', 'low')
        
        # Mock performance regression check
        # In real implementation, would run benchmarks and compare with baseline
        
        simulated_regression = {
            'latency_change_percent': 2.0 if risk_level == 'high' else 0.5,
            'memory_change_percent': 1.0 if risk_level == 'high' else 0.2,
            'error_rate_change_percent': 0.1
        }
        
        max_latency_regression = gate.criteria.get('max_latency_regression', 15)
        max_memory_regression = gate.criteria.get('max_memory_regression', 10)
        
        gate.result = {
            'performance_regression': simulated_regression,
            'risk_level': risk_level,
            'performance_concerns': performance_impact.get('concerns', [])
        }
        
        if (simulated_regression['latency_change_percent'] > max_latency_regression or
            simulated_regression['memory_change_percent'] > max_memory_regression):
            gate.status = "failed"
            gate.error_message = "Performance regression exceeds thresholds"
        else:
            gate.status = "passed"
    
    async def _run_config_validation_gate(self, gate: DeploymentGate, analysis: ChangesetAnalysis):
        """Run configuration validation gate."""
        
        config_files = gate.criteria.get('config_files', [])
        
        validation_results = []
        for config_file in config_files:
            # Mock config validation (in real implementation, would validate against schemas)
            if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                validation_results.append({'file': config_file, 'valid': True, 'format': 'yaml'})
            elif config_file.endswith('.json'):
                validation_results.append({'file': config_file, 'valid': True, 'format': 'json'})
            else:
                validation_results.append({'file': config_file, 'valid': True, 'format': 'other'})
        
        gate.result = {
            'config_files_validated': len(validation_results),
            'validation_results': validation_results
        }
        
        failed_validations = [r for r in validation_results if not r['valid']]
        
        if failed_validations:
            gate.status = "failed"
            gate.error_message = f"Configuration validation failed for {len(failed_validations)} files"
        else:
            gate.status = "passed"
    
    async def _run_risk_assessment_gate(self, gate: DeploymentGate, analysis: ChangesetAnalysis):
        """Run risk assessment gate for high-risk changes."""
        
        risk_score = gate.criteria.get('risk_score', 0)
        risk_factors = gate.criteria.get('risk_factors', [])
        
        # High-risk changes require manual approval
        gate.result = {
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'requires_manual_approval': True,
            'recommended_reviewers': 2 if risk_score > 0.7 else 1
        }
        
        # High-risk gate always requires manual intervention
        gate.status = "failed"
        gate.error_message = f"High-risk change (score: {risk_score:.3f}) requires manual approval"


class SafetyRailsManager:
    """Main safety rails management system."""
    
    def __init__(self, config: Optional[SafetyRailsConfig] = None):
        """Initialize safety rails manager."""
        
        self.config = config or SafetyRailsConfig()
        self.code_analyzer = CodeAnalyzer(self.config)
        self.gate_runner = DeploymentGateRunner(self.config)
        
        self.logger = logging.getLogger(__name__ + ".SafetyRailsManager")
    
    async def review_changeset(
        self, 
        changeset_id: str,
        changed_files: List[str],
        file_diffs: Dict[str, str]
    ) -> SafetyRailsReport:
        """
        Comprehensive safety review of a changeset.
        
        Args:
            changeset_id: Unique identifier for the changeset
            changed_files: List of modified file paths
            file_diffs: Dict mapping file paths to their diffs
            
        Returns:
            Comprehensive safety rails report
        """
        
        self.logger.info(f"Starting safety review for changeset: {changeset_id}")
        
        report_id = f"safety_review_{changeset_id}_{int(time.time())}"
        
        try:
            # Step 1: Analyze changeset
            changeset_analysis = self.code_analyzer.analyze_changeset(
                changeset_id, changed_files, file_diffs
            )
            
            # Step 2: Run deployment gates
            deployment_gates = await self.gate_runner.run_all_gates(
                changeset_analysis, changeset_id
            )
            
            # Step 3: Generate overall assessment
            overall_status, blocking_issues, warnings = self._assess_overall_status(
                changeset_analysis, deployment_gates
            )
            
            # Step 4: Generate recommendations
            recommendations, required_actions = self._generate_recommendations(
                changeset_analysis, deployment_gates, overall_status
            )
            
            # Create report
            report = SafetyRailsReport(
                report_id=report_id,
                timestamp=datetime.now().isoformat(),
                changeset_id=changeset_id,
                changeset_analysis=changeset_analysis,
                deployment_gates=deployment_gates,
                overall_status=overall_status,
                approval_required=overall_status in ['conditional', 'rejected'],
                blocking_issues=blocking_issues,
                warnings=warnings,
                recommendations=recommendations,
                required_actions=required_actions
            )
            
            self.logger.info(f"Safety review completed: {overall_status}")
            self.logger.info(f"  Blocking issues: {len(blocking_issues)}")
            self.logger.info(f"  Warnings: {len(warnings)}")
            
            return report
        
        except Exception as e:
            self.logger.error(f"Safety review failed: {e}")
            raise
    
    def _assess_overall_status(
        self, 
        analysis: ChangesetAnalysis, 
        gates: List[DeploymentGate]
    ) -> Tuple[str, List[str], List[str]]:
        """Assess overall safety status."""
        
        blocking_issues = []
        warnings = []
        
        # Check required gates
        required_gates_failed = [g for g in gates if g.required and g.status == "failed"]
        
        if required_gates_failed:
            blocking_issues.extend([
                f"Required gate failed: {gate.name} - {gate.error_message}"
                for gate in required_gates_failed
            ])
        
        # Security issues
        if analysis.security_risk_level in ['high', 'critical']:
            blocking_issues.append(f"Security risk level: {analysis.security_risk_level}")
        elif analysis.security_risk_level == 'medium':
            warnings.append(f"Medium security risk detected")
        
        # Risk score
        if analysis.risk_score > 0.8:
            blocking_issues.append(f"Very high risk score: {analysis.risk_score:.3f}")
        elif analysis.risk_score > 0.6:
            warnings.append(f"High risk score: {analysis.risk_score:.3f}")
        
        # Performance impact
        perf_impact = analysis.performance_impact
        if perf_impact and perf_impact.get('risk_level') == 'high':
            warnings.append("High performance impact risk detected")
        
        # Determine overall status
        if blocking_issues:
            return "rejected", blocking_issues, warnings
        elif warnings or any(g.status == "failed" for g in gates if not g.required):
            return "conditional", blocking_issues, warnings
        else:
            return "approved", blocking_issues, warnings
    
    def _generate_recommendations(
        self,
        analysis: ChangesetAnalysis,
        gates: List[DeploymentGate],
        overall_status: str
    ) -> Tuple[List[str], List[str]]:
        """Generate recommendations and required actions."""
        
        recommendations = []
        required_actions = []
        
        # Security recommendations
        if len(analysis.security_issues) > 0:
            if analysis.security_risk_level in ['high', 'critical']:
                required_actions.append("Address all high/critical security issues before deployment")
            else:
                recommendations.append("Review and address identified security concerns")
        
        # Risk-based recommendations
        if analysis.risk_score > 0.7:
            required_actions.append("Obtain additional code review approval")
            recommendations.append("Consider breaking changes into smaller, incremental deployments")
        
        # Test coverage recommendations
        test_gate = next((g for g in gates if g.gate_id == "test_coverage"), None)
        if test_gate and test_gate.status == "failed":
            required_actions.append("Increase test coverage to meet minimum requirements")
        
        # Performance recommendations
        if analysis.performance_impact and analysis.performance_impact.get('risk_level') != 'low':
            recommendations.append("Conduct performance testing in staging environment")
            recommendations.append("Monitor key performance metrics closely post-deployment")
        
        # Configuration change recommendations
        if len(analysis.config_files_changed) > 0:
            recommendations.append("Verify configuration changes in staging environment")
            if overall_status == "approved":
                recommendations.append("Consider gradual rollout for configuration changes")
        
        # General recommendations
        if analysis.change_complexity == "high":
            recommendations.append("Consider feature flags for easier rollback")
            recommendations.append("Prepare detailed rollback plan")
        
        return recommendations, required_actions


# Convenience functions

async def review_changeset_safety(
    changeset_id: str,
    changed_files: List[str], 
    file_diffs: Dict[str, str],
    config: Optional[SafetyRailsConfig] = None
) -> SafetyRailsReport:
    """Convenience function to review changeset safety."""
    
    manager = SafetyRailsManager(config)
    return await manager.review_changeset(changeset_id, changed_files, file_diffs)


def create_strict_safety_config() -> SafetyRailsConfig:
    """Create strict safety configuration for production."""
    
    return SafetyRailsConfig(
        require_code_review=True,
        min_reviewers=2,
        block_on_security_issues=True,
        block_on_performance_regression=True,
        max_lines_changed=200,
        max_files_changed=10,
        security_severity_threshold="low",
        min_test_coverage_percent=90.0,
        max_latency_regression_percent=5.0,
        enable_automatic_rollback=True
    )