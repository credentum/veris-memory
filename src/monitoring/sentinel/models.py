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
    """
    Configuration for Sentinel monitoring.

    Uses TARGET_BASE_URL environment variable for Docker deployments.
    Falls back to localhost for local development.
    """
    target_base_url: Optional[str] = None
    check_interval_seconds: int = 60
    alert_threshold_failures: int = 3
    webhook_url: Optional[str] = None
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    enabled_checks: List[str] = None

    def __post_init__(self):
        """Set defaults from environment variables if not specified."""
        import os

        # Set target_base_url from environment (Docker) or use localhost (local dev)
        # Note: Default port is 8000 to match context-store default port
        if self.target_base_url is None:
            self.target_base_url = os.getenv('TARGET_BASE_URL', 'http://localhost:8000')

        # Set default enabled checks if not specified
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
                "S10-content-pipeline",
                "S11-firewall-status"
            ]
    
    def is_check_enabled(self, check_id: str) -> bool:
        """Check if a specific check is enabled."""
        return check_id in self.enabled_checks
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value like a dictionary.
        
        This method allows the config to be used like a dictionary
        for backward compatibility with checks.
        """
        # Map common keys to actual attributes
        if key == 'veris_memory_url':
            return self.target_base_url
        elif key == 'api_url':
            # Return the configured target_base_url (already set from environment)
            return self.target_base_url
        elif key == 'qdrant_url':
            import os
            return os.getenv('QDRANT_URL', 'http://localhost:6333')
        elif key == 'neo4j_url':
            import os
            return os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        elif key == 'redis_url':
            import os
            return os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        # Try to get from object attributes
        return getattr(self, key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SentinelConfig':
        """Create from dictionary format."""
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> 'SentinelConfig':
        """Create configuration from environment variables.

        Uses TARGET_BASE_URL (consistent with __post_init__ and docker-compose)
        instead of SENTINEL_TARGET_URL for better compatibility.
        """
        import os

        return cls(
            target_base_url=os.getenv('TARGET_BASE_URL', 'http://localhost:8000'),
            check_interval_seconds=int(os.getenv('SENTINEL_CHECK_INTERVAL', '60')),
            alert_threshold_failures=int(os.getenv('SENTINEL_ALERT_THRESHOLD', '3')),
            webhook_url=os.getenv('SENTINEL_WEBHOOK_URL'),
            github_token=os.getenv('GITHUB_TOKEN'),
            github_repo=os.getenv('SENTINEL_GITHUB_REPO'),
            enabled_checks=os.getenv('SENTINEL_ENABLED_CHECKS', '').split(',') if os.getenv('SENTINEL_ENABLED_CHECKS') else None
        )