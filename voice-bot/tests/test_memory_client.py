"""
Tests for MCP Memory Client
Tests Sprint 13 integration: auth, retry logic, author attribution, embedding status
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.memory_client import (
    MemoryClient,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPEmbeddingError
)


@pytest.fixture
def memory_client():
    """Create memory client for testing"""
    return MemoryClient(
        mcp_url="http://test-mcp:8000",
        api_key="test_api_key",
        author_prefix="test_bot",
        enable_retry=True,
        retry_attempts=3
    )


@pytest.fixture
def memory_client_no_auth():
    """Create memory client without authentication"""
    return MemoryClient(
        mcp_url="http://test-mcp:8000",
        api_key=None,
        author_prefix="test_bot",
        enable_retry=False,
        retry_attempts=1
    )


class TestMemoryClientInit:
    """Test memory client initialization"""

    def test_client_initialization(self, memory_client):
        """Test basic initialization"""
        assert memory_client.mcp_url == "http://test-mcp:8000"
        assert memory_client.api_key == "test_api_key"
        assert memory_client.author_prefix == "test_bot"
        assert memory_client.enable_retry is True
        assert memory_client.retry_attempts == 3

    def test_client_initialization_no_auth(self, memory_client_no_auth):
        """Test initialization without API key"""
        assert memory_client_no_auth.api_key is None
        assert memory_client_no_auth.enable_retry is False

    def test_url_strip_trailing_slash(self):
        """Test URL normalization"""
        client = MemoryClient(mcp_url="http://test:8000/")
        assert client.mcp_url == "http://test:8000"


class TestHeaderGeneration:
    """Test Sprint 13 API key header generation"""

    def test_get_headers_with_api_key(self, memory_client):
        """Test headers include API key"""
        headers = memory_client._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["X-API-Key"] == "test_api_key"

    def test_get_headers_without_api_key(self, memory_client_no_auth):
        """Test headers without API key"""
        headers = memory_client_no_auth._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert "X-API-Key" not in headers


class TestRetryLogic:
    """Test Sprint 13 retry logic with exponential backoff"""

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, memory_client):
        """Test retry on 5xx errors"""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch.object(memory_client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(MCPConnectionError) as exc_info:
                await memory_client._retry_request("GET", "http://test/health")

            # Should retry 3 times
            assert mock_request.call_count == 3
            assert "Failed after 3 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self, memory_client):
        """Test no retry on 401 authentication errors"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(memory_client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(MCPAuthenticationError) as exc_info:
                await memory_client._retry_request("GET", "http://test/health")

            # Should NOT retry on auth error
            assert mock_request.call_count == 1
            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, memory_client):
        """Test no retry on 4xx client errors (except 401)"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch.object(memory_client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            response = await memory_client._retry_request("GET", "http://test/invalid")

            # Should NOT retry on client error
            assert mock_request.call_count == 1
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self, memory_client):
        """Test successful request doesn't retry"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(memory_client.client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            response = await memory_client._retry_request("GET", "http://test/health")

            # Should succeed on first attempt
            assert mock_request.call_count == 1
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, memory_client):
        """Test exponential backoff timing"""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch.object(memory_client.client, 'request', new_callable=AsyncMock) as mock_request:
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                mock_request.return_value = mock_response

                with pytest.raises(MCPConnectionError):
                    await memory_client._retry_request("GET", "http://test/health")

                # Check exponential backoff: 1s, 2s
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls == [1, 2]  # 2^0=1, 2^1=2 (no sleep after last attempt)


class TestStoreFact:
    """Test fact storage with Sprint 13 features"""

    @pytest.mark.asyncio
    async def test_store_fact_success(self, memory_client):
        """Test successful fact storage"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "context_id": "ctx_123",
            "embedding_status": "completed",
            "relationships_created": 2
        }

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await memory_client.store_fact("user123", "name", "Alice")

            assert result is True
            mock_request.assert_called_once()

            # Check payload structure
            call_args = mock_request.call_args
            payload = call_args[1]['json']

            assert payload['type'] == 'log'
            assert payload['content']['namespace'] == 'voicebot_user123'
            assert payload['content']['user_id'] == 'user123'
            assert payload['content']['key'] == 'name'
            assert payload['content']['value'] == 'Alice'
            assert payload['author'] == 'test_bot_user123'
            assert payload['author_type'] == 'agent'
            assert payload['metadata']['source'] == 'voice_input'

    @pytest.mark.asyncio
    async def test_store_fact_embedding_failed(self, memory_client):
        """Test fact storage with embedding failure (Sprint 13)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "context_id": "ctx_123",
            "embedding_status": "failed",
            "embedding_message": "Embedding service unavailable"
        }

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await memory_client.store_fact("user123", "name", "Alice")

            # Should still succeed (embedding failure is non-fatal)
            assert result is True

    @pytest.mark.asyncio
    async def test_store_fact_auth_error(self, memory_client):
        """Test fact storage with authentication error"""
        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = MCPAuthenticationError("Invalid API key")

            result = await memory_client.store_fact("user123", "name", "Alice")

            assert result is False

    @pytest.mark.asyncio
    async def test_store_fact_connection_error(self, memory_client):
        """Test fact storage with connection error"""
        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Connection refused")

            result = await memory_client.store_fact("user123", "name", "Alice")

            assert result is False


class TestGetUserFacts:
    """Test fact retrieval"""

    @pytest.mark.asyncio
    async def test_get_facts_by_key(self, memory_client):
        """Test direct key lookup"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"content": {"key": "name", "value": "Alice"}}
            ]
        }

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            facts = await memory_client.get_user_facts("user123", ["name"])

            assert facts["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_facts_semantic_search(self, memory_client):
        """Test semantic search fallback"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"content": {"key": "name", "value": "Alice"}},
                {"content": {"key": "color", "value": "blue"}}
            ]
        }

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            facts = await memory_client.get_user_facts("user123")

            assert facts["name"] == "Alice"
            assert facts["color"] == "blue"

    @pytest.mark.asyncio
    async def test_get_facts_auth_error(self, memory_client):
        """Test fact retrieval with auth error"""
        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = MCPAuthenticationError("Invalid API key")

            facts = await memory_client.get_user_facts("user123", ["name"])

            assert facts == {}


class TestConversationTrace:
    """Test conversation trace storage"""

    @pytest.mark.asyncio
    async def test_store_conversation_trace_success(self, memory_client):
        """Test successful conversation trace storage"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "context_id": "ctx_456",
            "embedding_status": "completed"
        }

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await memory_client.store_conversation_trace("user123", messages)

            assert result is True

            # Check payload structure
            call_args = mock_request.call_args
            payload = call_args[1]['json']

            assert payload['type'] == 'trace'
            assert payload['content']['messages'] == messages
            assert payload['author'] == 'test_bot_user123'


class TestHealthChecks:
    """Test health check methods"""

    @pytest.mark.asyncio
    async def test_initialize_success(self, memory_client):
        """Test successful initialization"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await memory_client.initialize()

            assert result is True
            mock_request.assert_called_once_with(
                "GET",
                "http://test-mcp:8000/health",
                headers=memory_client._get_headers()
            )

    @pytest.mark.asyncio
    async def test_initialize_auth_error(self, memory_client):
        """Test initialization with auth error"""
        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = MCPAuthenticationError("Invalid API key")

            result = await memory_client.initialize()

            assert result is False

    @pytest.mark.asyncio
    async def test_check_health_success(self, memory_client):
        """Test health check success"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await memory_client.check_health()

            assert result is True

    @pytest.mark.asyncio
    async def test_get_detailed_health(self, memory_client):
        """Test detailed health check (Sprint 13)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
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
                "redis": "healthy"
            }
        }

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            health_data = await memory_client.get_detailed_health()

            assert health_data["mcp_server"] == "healthy"
            assert health_data["embedding_pipeline"]["qdrant_connected"] is True
            assert health_data["services"]["embeddings"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_detailed_health_degraded(self, memory_client):
        """Test detailed health check with degraded embedding service"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "embedding_pipeline": {},
            "services": {
                "embeddings": "unhealthy"
            }
        }

        with patch.object(memory_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            health_data = await memory_client.get_detailed_health()

            assert health_data["services"]["embeddings"] == "unhealthy"


class TestCleanup:
    """Test cleanup operations"""

    @pytest.mark.asyncio
    async def test_close_client(self, memory_client):
        """Test client cleanup"""
        with patch.object(memory_client.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await memory_client.close()

            mock_close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.memory_client", "--cov-report=term-missing"])
