#!/usr/bin/env python3
"""
Data models and configuration for Veris Sentinel.

Contains the core data structures used throughout the sentinel system.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class CheckResult:
    """Result of a single check execution."""
    check_id: str
    timestamp: datetime
    status: str  # "pass", "warn", "fail"
    latency_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckResult':
        """Create from dictionary format."""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class SentinelConfig:
    """Configuration for Sentinel monitoring."""
    target_base_url: str = "http://localhost:8000"
    check_interval_seconds: int = 60
    alert_threshold_failures: int = 3
    webhook_url: Optional[str] = None
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    enabled_checks: List[str] = None
    
    def __post_init__(self):
        """Set default enabled checks if not specified."""
        if self.enabled_checks is None:
            self.enabled_checks = [
                "S1-probes",
                "S2-golden-fact-recall", 
                "S3-paraphrase-robustness",
                "S4-metrics-wiring",
                "S5-security-negatives",
                "S6-backup-restore",
                "S7-config-parity",
                "S8-capacity-smoke",
                "S9-graph-intent",
                "S10-content-pipeline"
            ]
    
    def is_check_enabled(self, check_id: str) -> bool:
        """Check if a specific check is enabled."""
        return check_id in self.enabled_checks
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SentinelConfig':
        """Create from dictionary format."""
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> 'SentinelConfig':
        """Create configuration from environment variables."""
        import os
        
        return cls(
            target_base_url=os.getenv('SENTINEL_TARGET_URL', 'http://localhost:8000'),
            check_interval_seconds=int(os.getenv('SENTINEL_CHECK_INTERVAL', '60')),
            alert_threshold_failures=int(os.getenv('SENTINEL_ALERT_THRESHOLD', '3')),
            webhook_url=os.getenv('SENTINEL_WEBHOOK_URL'),
            github_token=os.getenv('GITHUB_TOKEN'),
            github_repo=os.getenv('SENTINEL_GITHUB_REPO'),
            enabled_checks=os.getenv('SENTINEL_ENABLED_CHECKS', '').split(',') if os.getenv('SENTINEL_ENABLED_CHECKS') else None
        )