#!/usr/bin/env python3
"""
test_config.py: Test configuration utilities for context storage system

This module provides test-friendly configuration loading and defaults
to enable proper test isolation without requiring actual config files.
"""

from typing import Any, Dict, Optional


def get_test_config() -> Dict[str, Any]:
    """
    Get default test configuration.

    Returns:
        Dictionary with test configuration for all storage backends
    """
    return {
        "neo4j": {
            "host": "localhost",
            "port": 7687,
            "database": "test_context",
            "username": "neo4j",
            "password": "test_password",
            "ssl": False,
        },
        "qdrant": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "test_contexts",
            "dimensions": 384,
            "https": False,
        },
        "redis": {"host": "localhost", "port": 6379, "database": 0, "password": None, "ssl": False},
        "storage": {"base_path": "/tmp/test_storage", "cache_ttl": 3600, "max_cache_size": 100},
        "embedding": {"model": "all-MiniLM-L6-v2", "cache_embeddings": True, "batch_size": 32},
        "security": {"auth_enabled": False, "ssl_enabled": False},
    }


def get_minimal_config() -> Dict[str, Any]:
    """
    Get minimal configuration for basic testing.

    Returns:
        Minimal configuration dictionary
    """
    return {
        "neo4j": {"host": "localhost", "port": 7687},
        "qdrant": {"host": "localhost", "port": 6333},
        "redis": {"host": "localhost", "port": 6379},
    }


def merge_configs(
    base_config: Dict[str, Any], override_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Merge configuration dictionaries, with overrides taking precedence.

    Args:
        base_config: Base configuration dictionary
        override_config: Configuration overrides

    Returns:
        Merged configuration dictionary
    """
    if not override_config:
        return base_config.copy()

    result = base_config.copy()

    for key, value in override_config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result
