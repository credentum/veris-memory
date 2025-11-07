"""
Shared test fixtures for voice-bot tests
"""
import pytest
import os
from unittest.mock import MagicMock, AsyncMock


# Set minimal required environment variables for tests
# Individual tests can override as needed
if "LIVEKIT_API_KEY" not in os.environ:
    os.environ["LIVEKIT_API_KEY"] = "test_key"
if "LIVEKIT_API_SECRET" not in os.environ:
    os.environ["LIVEKIT_API_SECRET"] = "test_secret"


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response"""
    def _create_response(status_code=200, json_data=None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = str(json_data)
        return response
    return _create_response


@pytest.fixture
def mock_successful_mcp_response(mock_httpx_response):
    """Create a successful MCP response"""
    return mock_httpx_response(200, {
        "success": True,
        "context_id": "ctx_test_123",
        "embedding_status": "completed",
        "relationships_created": 0
    })


@pytest.fixture
def mock_failed_mcp_response(mock_httpx_response):
    """Create a failed MCP response"""
    return mock_httpx_response(500, {
        "error": "Internal server error"
    })


@pytest.fixture
def mock_auth_error_response(mock_httpx_response):
    """Create an authentication error response"""
    return mock_httpx_response(401, {
        "error": "Unauthorized",
        "detail": "Invalid API key"
    })


@pytest.fixture
def sample_user_facts():
    """Sample user facts for testing"""
    return {
        "name": "Alice",
        "color": "blue",
        "age": "30",
        "city": "San Francisco"
    }


@pytest.fixture
def sample_conversation_messages():
    """Sample conversation messages for testing"""
    return [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you! How can I help you today?"},
        {"role": "user", "content": "Tell me about the weather"},
        {"role": "assistant", "content": "I'd be happy to help with the weather!"}
    ]


@pytest.fixture
def sample_voice_session():
    """Sample voice session data"""
    return {
        "room_name": "voice_test123_1234567890",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
        "url": "ws://livekit:7880",
        "user_id": "test123",
        "created_at": "2025-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_detailed_health():
    """Sample detailed health response"""
    return {
        "status": "healthy",
        "embedding_pipeline": {
            "qdrant_connected": True,
            "embedding_service_loaded": True,
            "collection_created": True,
            "test_embedding_successful": True
        },
        "services": {
            "embeddings": "healthy",
            "neo4j": "healthy",
            "redis": "healthy",
            "qdrant": "healthy"
        }
    }


@pytest.fixture
def sample_degraded_health():
    """Sample degraded health response"""
    return {
        "status": "degraded",
        "embedding_pipeline": {
            "qdrant_connected": True,
            "embedding_service_loaded": False,
            "collection_created": False,
            "test_embedding_successful": False
        },
        "services": {
            "embeddings": "unhealthy",
            "neo4j": "healthy",
            "redis": "healthy",
            "qdrant": "healthy"
        }
    }


# Async test support
@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Clean up after tests
@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment after each test"""
    yield
    # Cleanup code here if needed
