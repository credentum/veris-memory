"""Pytest configuration for context-store tests.

This file configures the test environment and handles import paths centrally.
All test files should use this configuration - DO NOT add sys.path manipulations
in individual test files.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

# Centralized sys.path configuration for all tests
# This allows tests to import from src/ directly without individual setup
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CONFIG_PATH", str(project_root / "config" / "test.yaml"))

# Import test configuration utilities
from src.core.test_config import get_minimal_config, get_test_config  # noqa: E402


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide full test configuration for storage components."""
    return get_test_config()


@pytest.fixture
def minimal_config() -> Dict[str, Any]:
    """Provide minimal test configuration."""
    return get_minimal_config()


@pytest.fixture
def mock_neo4j_config() -> Dict[str, Any]:
    """Provide Neo4j-specific test configuration."""
    return {
        "neo4j": {
            "host": "localhost",
            "port": 7687,
            "database": "test_context",
            "username": "neo4j",
            "password": "test_password",
            "ssl": False,
        }
    }


@pytest.fixture
def mock_qdrant_config() -> Dict[str, Any]:
    """Provide Qdrant-specific test configuration."""
    return {
        "qdrant": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "test_contexts",
            "dimensions": 384,
            "https": False,
        }
    }


@pytest.fixture
def mock_redis_config() -> Dict[str, Any]:
    """Provide Redis-specific test configuration."""
    return {
        "redis": {"host": "localhost", "port": 6379, "database": 0, "password": None, "ssl": False}
    }


@pytest.fixture
def mock_config_loader(test_config):
    """Mock the config loader to return test configuration."""
    with patch("storage.neo4j_client.open", side_effect=FileNotFoundError):
        with patch("storage.qdrant_client.open", side_effect=FileNotFoundError):
            with patch("storage.kv_store.open", side_effect=FileNotFoundError):
                yield test_config


@pytest.fixture
def neo4j_client_mock(test_config):
    """Create a mock Neo4j client for testing."""
    from storage.neo4j_client import Neo4jInitializer

    client = Neo4jInitializer(config=test_config, test_mode=True)
    return client


@pytest.fixture
def qdrant_client_mock(test_config):
    """Create a mock Qdrant client for testing."""
    from storage.qdrant_client import VectorDBInitializer

    client = VectorDBInitializer(config=test_config, test_mode=True)
    return client


@pytest.fixture
def kv_store_mock(test_config):
    """Create a mock KV store for testing."""
    from storage.kv_store import ContextKV

    store = ContextKV(config=test_config, test_mode=True)
    return store


# Enhanced Database Mocking Fixtures for Phase 2 & 3


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for comprehensive testing."""
    from unittest.mock import Mock

    # Create mock driver
    mock_driver = Mock()
    mock_session = Mock()
    mock_tx = Mock()

    # Configure mock behavior
    mock_driver.session.return_value = mock_session
    mock_session.begin_transaction.return_value = mock_tx
    mock_session.run.return_value = Mock(data=lambda: [])
    mock_tx.run.return_value = Mock(data=lambda: [])

    # Mock async methods
    mock_session.close = Mock()
    mock_tx.commit = Mock()
    mock_tx.rollback = Mock()

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        yield mock_driver


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for comprehensive testing."""
    from unittest.mock import Mock

    from qdrant_client.models import Distance, VectorParams

    # Create mock client
    mock_client = Mock()

    # Configure collection operations
    mock_client.get_collections.return_value.collections = []
    mock_client.create_collection = Mock()
    mock_client.delete_collection = Mock()
    mock_client.collection_exists.return_value = False

    # Configure vector operations
    mock_client.upsert = Mock()
    mock_client.search = Mock(return_value=[])
    mock_client.scroll = Mock(return_value=([], None))
    mock_client.delete = Mock()

    # Configure info operations
    mock_client.get_collection.return_value = Mock(
        config=Mock(params=VectorParams(size=384, distance=Distance.COSINE))
    )

    with patch("qdrant_client.QdrantClient", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for comprehensive testing."""
    from unittest.mock import Mock

    # Create mock client
    mock_client = Mock()

    # Configure Redis operations
    mock_client.get = Mock(return_value=None)
    mock_client.set = Mock(return_value=True)
    mock_client.delete = Mock(return_value=1)
    mock_client.exists = Mock(return_value=False)
    mock_client.expire = Mock(return_value=True)
    mock_client.ttl = Mock(return_value=-1)

    # Configure Redis collections
    mock_client.hget = Mock(return_value=None)
    mock_client.hset = Mock(return_value=1)
    mock_client.hgetall = Mock(return_value={})
    mock_client.hdel = Mock(return_value=1)

    # Configure async operations
    mock_client.ping = Mock(return_value=True)

    with patch("redis.Redis", return_value=mock_client):
        yield mock_client


@pytest.fixture
def docker_compose_project_name():
    """Provide project name for Docker Compose tests."""
    return "context-store-test"


@pytest.fixture(scope="session")
def docker_compose_file():
    """Provide Docker Compose file path for integration tests."""
    return "docker-compose.test.yml"


@pytest.fixture
def test_database_config():
    """Provide test database configuration for integration tests."""
    return {
        "neo4j": {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "testpassword",
            "database": "neo4j",
        },
        "qdrant": {
            "url": "http://localhost:6333",
            "collection_name": "test_collection",
            "vector_size": 384,
        },
        "redis": {
            "url": "redis://localhost:6379/0",
            "prefix": "test:",
        },
    }


@pytest.fixture
def async_test_timeout():
    """Provide timeout for async tests to prevent hanging."""
    return 30.0  # 30 seconds


@pytest.fixture
def embedding_mock():
    """Mock embedding service for testing."""
    from unittest.mock import Mock

    mock_service = Mock()
    mock_service.embed_text.return_value = [0.1] * 384  # Mock 384-dim vector
    mock_service.embed_batch.return_value = [[0.1] * 384] * 5  # Mock batch

    return mock_service


@pytest.fixture
def rate_limiter_mock():
    """Mock rate limiter for testing."""
    from unittest.mock import Mock

    mock_limiter = Mock()
    mock_limiter.check_rate_limit.return_value = (True, None)  # Allow all requests
    mock_limiter.get_rate_limit_info.return_value = {"status": "ok"}

    return mock_limiter


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test to avoid collisions."""
    try:
        from prometheus_client import REGISTRY
        # Clear the registry before each test
        collectors = list(REGISTRY._collector_to_names.keys())
        for collector in collectors:
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                pass  # Already unregistered
    except ImportError:
        pass  # Prometheus not available
    
    yield
    
    # Clean up after test
    try:
        from prometheus_client import REGISTRY
        collectors = list(REGISTRY._collector_to_names.keys())
        for collector in collectors:
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                pass
    except ImportError:
        pass
