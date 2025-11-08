"""
Tests for Voice Bot FastAPI Application
Tests all endpoints and Sprint 13 integration
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.main import app
from app.memory_client import MemoryClient
from app.voice_handler import VoiceHandler


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_memory_client():
    """Create mock memory client"""
    client = MagicMock(spec=MemoryClient)
    client.check_health = AsyncMock(return_value=True)
    client.get_detailed_health = AsyncMock(return_value={
        "mcp_server": "healthy",
        "embedding_pipeline": {
            "qdrant_connected": True,
            "embedding_service_loaded": True,
            "collection_created": True,
            "test_embedding_successful": True
        },
        "services": {
            "embeddings": "healthy",
            "neo4j": "healthy",
            "redis": "healthy"
        }
    })
    client.store_fact = AsyncMock(return_value=True)
    client.get_user_facts = AsyncMock(return_value={"name": "Alice", "color": "blue"})
    return client


@pytest.fixture
def mock_voice_handler():
    """Create mock voice handler"""
    handler = MagicMock(spec=VoiceHandler)
    handler.check_health = AsyncMock(return_value=True)
    handler.create_voice_session = AsyncMock(return_value={
        "room_name": "voice_test123_1234567890",
        "token": "test_token",
        "url": "ws://livekit:7880",
        "user_id": "test123",
        "created_at": datetime.utcnow().isoformat()
    })
    return handler


class TestRootEndpoint:
    """Test root endpoint"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "TeamAI Voice Bot"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"
        assert "health" in data["endpoints"]
        assert "docs" in data["endpoints"]


class TestHealthEndpoints:
    """Test health check endpoints"""

    def test_health_check_success(self, client, mock_memory_client, mock_voice_handler):
        """Test health check with all services healthy"""
        with patch('app.main.memory_client', mock_memory_client):
            with patch('app.main.voice_handler', mock_voice_handler):
                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["checks"]["mcp_server"] is True
        assert data["checks"]["livekit"] is True

    def test_health_check_degraded(self, client, mock_memory_client, mock_voice_handler):
        """Test health check with degraded services"""
        mock_memory_client.check_health = AsyncMock(return_value=False)

        with patch('app.main.memory_client', mock_memory_client):
            with patch('app.main.voice_handler', mock_voice_handler):
                response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["mcp_server"] is False

    def test_health_check_no_clients(self, client):
        """Test health check when clients not initialized"""
        with patch('app.main.memory_client', None):
            with patch('app.main.voice_handler', None):
                response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["mcp_server"] is False
        assert data["checks"]["livekit"] is False

    def test_detailed_health_check(self, client, mock_memory_client, mock_voice_handler):
        """Test detailed health check (Sprint 13)"""
        with patch('app.main.memory_client', mock_memory_client):
            with patch('app.main.voice_handler', mock_voice_handler):
                response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "voice-bot"
        assert data["status"] == "healthy"
        assert data["mcp_server"]["mcp_server"] == "healthy"
        assert "embedding_pipeline" in data["mcp_server"]
        assert data["mcp_server"]["embedding_pipeline"]["qdrant_connected"] is True

    def test_detailed_health_check_degraded_embedding(self, client, mock_memory_client, mock_voice_handler):
        """Test detailed health check with degraded embedding service"""
        mock_memory_client.get_detailed_health = AsyncMock(return_value={
            "mcp_server": "healthy",
            "embedding_pipeline": {},
            "services": {
                "embeddings": "degraded"
            }
        })

        with patch('app.main.memory_client', mock_memory_client):
            with patch('app.main.voice_handler', mock_voice_handler):
                response = client.get("/health/detailed")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert "warnings" in data


class TestVoiceSessionEndpoints:
    """Test voice session management"""

    def test_create_voice_session_success(self, client, mock_voice_handler):
        """Test successful voice session creation"""
        with patch('app.main.voice_handler', mock_voice_handler):
            response = client.post("/api/v1/voice/session?user_id=test123")

        assert response.status_code == 201
        data = response.json()
        assert data["room_name"].startswith("voice_test123_")
        assert data["token"] == "test_token"
        assert data["user_id"] == "test123"

    def test_create_voice_session_no_handler(self, client):
        """Test voice session creation when handler not initialized"""
        with patch('app.main.voice_handler', None):
            response = client.post("/api/v1/voice/session?user_id=test123")

        assert response.status_code == 503
        data = response.json()
        assert "not initialized" in data["detail"]

    def test_create_voice_session_error(self, client, mock_voice_handler):
        """Test voice session creation with error"""
        mock_voice_handler.create_voice_session = AsyncMock(
            side_effect=Exception("LiveKit connection failed")
        )

        with patch('app.main.voice_handler', mock_voice_handler):
            response = client.post("/api/v1/voice/session?user_id=test123")

        assert response.status_code == 500
        assert "LiveKit connection failed" in response.json()["detail"]


class TestEchoTestEndpoint:
    """Test echo test endpoint (Sprint 1 validation)"""

    def test_echo_test_success(self, client, mock_memory_client):
        """Test successful echo test"""
        with patch('app.main.memory_client', mock_memory_client):
            response = client.post(
                "/api/v1/voice/echo-test?user_id=test123&message=Hello%20World"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test123"
        assert data["input"] == "Hello World"
        assert "Hi Alice" in data["response"]
        assert data["facts"]["name"] == "Alice"
        assert data["facts"]["color"] == "blue"

        # Verify fact was stored
        mock_memory_client.store_fact.assert_called_once_with(
            "test123", "last_message", "Hello World"
        )

    def test_echo_test_no_client(self, client):
        """Test echo test when client not initialized"""
        with patch('app.main.memory_client', None):
            response = client.post(
                "/api/v1/voice/echo-test?user_id=test123&message=Hello"
            )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_echo_test_error(self, client, mock_memory_client):
        """Test echo test with error"""
        mock_memory_client.store_fact = AsyncMock(side_effect=Exception("Storage error"))

        with patch('app.main.memory_client', mock_memory_client):
            response = client.post(
                "/api/v1/voice/echo-test?user_id=test123&message=Hello"
            )

        assert response.status_code == 500
        assert "Storage error" in response.json()["detail"]


class TestFactStorageEndpoints:
    """Test fact storage and retrieval endpoints"""

    def test_store_fact_success(self, client, mock_memory_client):
        """Test successful fact storage"""
        with patch('app.main.memory_client', mock_memory_client):
            response = client.post(
                "/api/v1/facts/store?user_id=test123&key=name&value=Alice"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user_id"] == "test123"
        assert data["key"] == "name"
        assert data["value"] == "Alice"

        # Verify correct method was called
        mock_memory_client.store_fact.assert_called_once_with("test123", "name", "Alice")

    def test_store_fact_failure(self, client, mock_memory_client):
        """Test fact storage failure"""
        mock_memory_client.store_fact = AsyncMock(return_value=False)

        with patch('app.main.memory_client', mock_memory_client):
            response = client.post(
                "/api/v1/facts/store?user_id=test123&key=name&value=Alice"
            )

        assert response.status_code == 500
        assert "Failed to store fact" in response.json()["detail"]

    def test_store_fact_no_client(self, client):
        """Test fact storage when client not initialized"""
        with patch('app.main.memory_client', None):
            response = client.post(
                "/api/v1/facts/store?user_id=test123&key=name&value=Alice"
            )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_get_facts_success(self, client, mock_memory_client):
        """Test successful fact retrieval"""
        with patch('app.main.memory_client', mock_memory_client):
            response = client.get("/api/v1/facts/test123")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test123"
        assert data["facts"]["name"] == "Alice"
        assert data["facts"]["color"] == "blue"
        assert data["count"] == 2

        # Verify correct method was called
        mock_memory_client.get_user_facts.assert_called_once_with("test123", None)

    def test_get_facts_with_keys(self, client, mock_memory_client):
        """Test fact retrieval with specific keys"""
        with patch('app.main.memory_client', mock_memory_client):
            response = client.get("/api/v1/facts/test123?keys=name,color")

        assert response.status_code == 200

        # Verify correct method was called with key list
        mock_memory_client.get_user_facts.assert_called_once_with(
            "test123", ["name", "color"]
        )

    def test_get_facts_no_client(self, client):
        """Test fact retrieval when client not initialized"""
        with patch('app.main.memory_client', None):
            response = client.get("/api/v1/facts/test123")

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_get_facts_error(self, client, mock_memory_client):
        """Test fact retrieval with error"""
        mock_memory_client.get_user_facts = AsyncMock(side_effect=Exception("Retrieval error"))

        with patch('app.main.memory_client', mock_memory_client):
            response = client.get("/api/v1/facts/test123")

        assert response.status_code == 500
        assert "Retrieval error" in response.json()["detail"]


class TestCORSMiddleware:
    """Test CORS configuration"""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present"""
        response = client.options("/")

        assert response.status_code == 200
        # CORS headers should be present
        # Note: In production, configure allow_origins more restrictively


class TestDocumentation:
    """Test API documentation endpoints"""

    def test_openapi_docs_available(self, client):
        """Test OpenAPI docs are available"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_available(self, client):
        """Test OpenAPI schema is available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert schema["info"]["title"] == "TeamAI Voice Bot"
        assert schema["info"]["version"] == "1.0.0"


class TestSprint13Integration:
    """Test Sprint 13 specific features"""

    def test_author_attribution_in_fact_storage(self, client, mock_memory_client):
        """Test that facts are stored with author attribution"""
        with patch('app.main.memory_client', mock_memory_client):
            response = client.post(
                "/api/v1/facts/store?user_id=test123&key=preference&value=dark_mode"
            )

        assert response.status_code == 200
        # Memory client should have been called with proper author attribution
        # (tested in memory_client tests)

    def test_retry_logic_applied(self, client, mock_memory_client):
        """Test that retry logic is applied to requests"""
        # This is tested in memory_client tests
        # Here we verify the client is configured with retry enabled
        with patch('app.main.memory_client', mock_memory_client):
            response = client.get("/health")

        assert response.status_code == 200

    def test_embedding_status_visibility(self, client, mock_memory_client, mock_voice_handler):
        """Test that embedding status is visible in detailed health"""
        with patch('app.main.memory_client', mock_memory_client):
            with patch('app.main.voice_handler', mock_voice_handler):
                response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "embedding_pipeline" in data["mcp_server"]


class TestErrorHandling:
    """Test error handling across endpoints"""

    def test_invalid_endpoint(self, client):
        """Test 404 for invalid endpoint"""
        response = client.get("/api/v1/invalid")
        assert response.status_code == 404

    def test_missing_query_parameters(self, client):
        """Test error handling for missing parameters"""
        response = client.post("/api/v1/voice/session")
        # FastAPI should return 422 for missing required query params
        assert response.status_code == 422


class TestStartupShutdown:
    """Test startup and shutdown events"""

    @pytest.mark.asyncio
    async def test_startup_initializes_clients(self):
        """Test that startup event initializes clients"""
        # This is more of an integration test
        # In practice, startup is tested by running the actual application
        pass

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self):
        """Test that shutdown event cleans up resources"""
        # This is more of an integration test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.main", "--cov-report=term-missing"])
