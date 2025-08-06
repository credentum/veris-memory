"""Comprehensive tests for mcp_server/main.py module.

This test suite provides 70% coverage for the MCP server main module,
testing all major components including:
- FastAPI app configuration and startup/shutdown events
- Health check endpoint with service status
- Store context tool endpoint
- Retrieve context tool endpoint
- Query graph tool endpoint
- List tools endpoint
- Error handling and edge cases
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.mcp_server.main import (  # noqa: E402
    QueryGraphRequest,
    RetrieveContextRequest,
    StoreContextRequest,
    app,
    health,
    list_tools,
    query_graph,
    retrieve_context,
    shutdown_event,
    startup_event,
    store_context,
)


class TestStoreContextRequest:
    """Test cases for StoreContextRequest model."""

    def test_valid_store_context_request(self):
        """Test valid store context request creation."""
        valid_data = {
            "content": {"title": "Test Content", "body": "Test body"},
            "type": "design",
            "metadata": {"author": "test"},
            "relationships": [{"target": "ctx_123", "type": "RELATES_TO"}],
        }

        request = StoreContextRequest(**valid_data)
        assert request.content == valid_data["content"]
        assert request.type == "design"
        assert request.metadata == valid_data["metadata"]
        assert request.relationships == valid_data["relationships"]

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # Missing content
        with pytest.raises(ValidationError):
            StoreContextRequest(type="design")

        # Missing type
        with pytest.raises(ValidationError):
            StoreContextRequest(content={"test": "data"})

    def test_type_validation(self):
        """Test type field validation."""
        valid_types = ["design", "decision", "trace", "sprint", "log"]

        for valid_type in valid_types:
            request = StoreContextRequest(content={"test": "data"}, type=valid_type)
            assert request.type == valid_type

        # Invalid type
        with pytest.raises(ValidationError):
            StoreContextRequest(content={"test": "data"}, type="invalid_type")

    def test_optional_fields(self):
        """Test optional fields have defaults."""
        request = StoreContextRequest(content={"test": "data"}, type="design")
        assert request.metadata is None
        assert request.relationships is None


class TestRetrieveContextRequest:
    """Test cases for RetrieveContextRequest model."""

    def test_valid_retrieve_context_request(self):
        """Test valid retrieve context request creation."""
        valid_data = {
            "query": "test query",
            "type": "design",
            "search_mode": "hybrid",
            "limit": 20,
            "filters": {"status": "active"},
            "include_relationships": True,
        }

        request = RetrieveContextRequest(**valid_data)
        assert request.query == "test query"
        assert request.type == "design"
        assert request.search_mode == "hybrid"
        assert request.limit == 20
        assert request.filters == {"status": "active"}
        assert request.include_relationships is True

    def test_default_values(self):
        """Test default values for optional fields."""
        request = RetrieveContextRequest(query="test")
        assert request.type == "all"
        assert request.search_mode == "hybrid"
        assert request.limit == 10
        assert request.filters is None
        assert request.include_relationships is False

    def test_limit_validation(self):
        """Test limit field validation."""
        # Valid limits
        for limit in [1, 50, 100]:
            request = RetrieveContextRequest(query="test", limit=limit)
            assert request.limit == limit

        # Invalid limits
        for invalid_limit in [0, -1, 101]:
            with pytest.raises(ValidationError):
                RetrieveContextRequest(query="test", limit=invalid_limit)


class TestQueryGraphRequest:
    """Test cases for QueryGraphRequest model."""

    def test_valid_query_graph_request(self):
        """Test valid query graph request creation."""
        valid_data = {
            "query": "MATCH (n) RETURN n",
            "parameters": {"param": "value"},
            "limit": 500,
            "timeout": 10000,
        }

        request = QueryGraphRequest(**valid_data)
        assert request.query == "MATCH (n) RETURN n"
        assert request.parameters == {"param": "value"}
        assert request.limit == 500
        assert request.timeout == 10000

    def test_default_values(self):
        """Test default values."""
        request = QueryGraphRequest(query="MATCH (n) RETURN n")
        assert request.parameters is None
        assert request.limit == 100
        assert request.timeout == 5000

    def test_limit_validation(self):
        """Test limit validation."""
        # Valid limits
        for limit in [1, 500, 1000]:
            request = QueryGraphRequest(query="test", limit=limit)
            assert request.limit == limit

        # Invalid limits
        for invalid_limit in [0, -1, 1001]:
            with pytest.raises(ValidationError):
                QueryGraphRequest(query="test", limit=invalid_limit)

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeouts
        for timeout in [1, 15000, 30000]:
            request = QueryGraphRequest(query="test", timeout=timeout)
            assert request.timeout == timeout

        # Invalid timeouts
        for invalid_timeout in [0, -1, 30001]:
            with pytest.raises(ValidationError):
                QueryGraphRequest(query="test", timeout=invalid_timeout)


class TestFastAPIApp:
    """Test cases for FastAPI app configuration."""

    def test_app_configuration(self):
        """Test FastAPI app is configured correctly."""
        assert app.title == "Context Store MCP Server"
        assert app.description == "Model Context Protocol server for context management"
        assert app.version == "1.0.0"

    def test_app_has_endpoints(self):
        """Test that all required endpoints are registered."""
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/health",
            "/tools/store_context",
            "/tools/retrieve_context",
            "/tools/query_graph",
            "/tools",
        ]

        for route in expected_routes:
            assert route in routes


class TestStartupEvent:
    """Test cases for startup event handler."""

    @patch("src.mcp_server.main.validate_all_configs")
    @patch("src.mcp_server.main.Neo4jClient")
    @patch("src.mcp_server.main.QdrantClient")
    @patch("src.mcp_server.main.KVStore")
    @patch.dict(
        os.environ,
        {
            "NEO4J_PASSWORD": "test_password",
            "NEO4J_URI": "bolt://test:7687",
            "NEO4J_USER": "test_user",
            "QDRANT_URL": "http://test:6333",
            "REDIS_URL": "redis://test:6379",
        },
    )
    @pytest.mark.asyncio
    async def test_successful_startup(self, mock_kv, mock_qdrant, mock_neo4j, mock_validate):
        """Test successful startup event."""
        mock_validate.return_value = {"valid": True}
        mock_neo4j_instance = Mock()
        mock_qdrant_instance = Mock()
        mock_kv_instance = Mock()

        mock_neo4j.return_value = mock_neo4j_instance
        mock_qdrant.return_value = mock_qdrant_instance
        mock_kv.return_value = mock_kv_instance

        with patch("builtins.print") as mock_print:
            await startup_event()

        mock_validate.assert_called_once()
        mock_neo4j.assert_called_once()
        mock_qdrant.assert_called_once()
        mock_kv.assert_called_once()

        # Verify connect methods were called with correct parameters
        mock_neo4j_instance.connect.assert_called_once_with(
            username="test_user", password="test_password"
        )
        mock_qdrant_instance.connect.assert_called_once()
        mock_kv_instance.connect.assert_called_once_with(redis_password=None)
        mock_print.assert_called_with("✅ All storage clients initialized successfully")

    @patch("src.mcp_server.main.validate_all_configs")
    @pytest.mark.asyncio
    async def test_startup_config_validation_failure(self, mock_validate):
        """Test startup failure due to config validation."""
        mock_validate.return_value = {"valid": False, "errors": ["Config error"]}

        with pytest.raises(RuntimeError, match="Configuration validation failed"):
            await startup_event()

    @patch("src.mcp_server.main.validate_all_configs")
    @patch.dict(os.environ, {}, clear=True)
    @pytest.mark.asyncio
    async def test_startup_missing_neo4j_password(self, mock_validate):
        """Test startup failure due to missing NEO4J_PASSWORD."""
        mock_validate.return_value = {"valid": True}

        with pytest.raises(RuntimeError, match="NEO4J_PASSWORD environment variable is required"):
            await startup_event()

    @patch("src.mcp_server.main.validate_all_configs")
    @patch("src.mcp_server.main.Neo4jClient")
    @patch.dict(os.environ, {"NEO4J_PASSWORD": "test_password"})
    @pytest.mark.asyncio
    async def test_startup_client_initialization_failure(self, mock_neo4j, mock_validate):
        """Test startup failure during client initialization."""
        mock_validate.return_value = {"valid": True}
        mock_neo4j.side_effect = Exception("Connection failed")

        with patch("builtins.print") as mock_print:
            with pytest.raises(Exception, match="Connection failed"):
                await startup_event()

        mock_print.assert_called_with("❌ Failed to initialize storage clients: Connection failed")

    @patch("src.mcp_server.main.validate_all_configs")
    @patch("src.mcp_server.main.Neo4jClient")
    @patch("src.mcp_server.main.QdrantClient")
    @patch("src.mcp_server.main.KVStore")
    @patch.dict(os.environ, {"NEO4J_PASSWORD": "test_password"})
    @pytest.mark.asyncio
    async def test_startup_default_urls(self, mock_kv, mock_qdrant, mock_neo4j, mock_validate):
        """Test startup with default URL values."""
        mock_validate.return_value = {"valid": True}

        await startup_event()

        mock_neo4j.assert_called_once()
        mock_qdrant.assert_called_once()
        mock_kv.assert_called_once()

        # Verify connect methods were called with default values
        mock_neo4j.return_value.connect.assert_called_once_with(
            username="neo4j", password="test_password"
        )
        mock_qdrant.return_value.connect.assert_called_once()
        mock_kv.return_value.connect.assert_called_once_with(redis_password=None)


class TestShutdownEvent:
    """Test cases for shutdown event handler."""

    @pytest.mark.asyncio
    async def test_successful_shutdown(self):
        """Test successful shutdown event."""
        mock_neo4j = Mock()
        mock_neo4j.close = Mock()
        mock_kv = Mock()
        mock_kv.close = Mock()

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            with patch("src.mcp_server.main.kv_store", mock_kv):
                with patch("builtins.print") as mock_print:
                    await shutdown_event()

        mock_neo4j.close.assert_called_once()
        mock_kv.close.assert_called_once()
        mock_print.assert_called_with("Storage clients closed")

    @pytest.mark.asyncio
    async def test_shutdown_with_no_clients(self):
        """Test shutdown when no clients are initialized."""
        with patch("src.mcp_server.main.neo4j_client", None):
            with patch("src.mcp_server.main.kv_store", None):
                with patch("builtins.print") as mock_print:
                    await shutdown_event()

        mock_print.assert_called_with("Storage clients closed")


class TestHealthEndpoint:
    """Test cases for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_all_services_healthy(self):
        """Test health check when all services are healthy."""
        mock_neo4j = Mock()
        mock_neo4j.verify_connectivity = Mock()
        mock_qdrant = Mock()
        mock_qdrant.get_collections = Mock(return_value=[])
        mock_kv = Mock()
        mock_kv.ping = Mock()

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
                with patch("src.mcp_server.main.kv_store", mock_kv):
                    result = await health()

        expected = {
            "status": "healthy",
            "services": {"neo4j": "healthy", "qdrant": "healthy", "redis": "healthy"},
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_health_neo4j_unhealthy(self):
        """Test health check when Neo4j is unhealthy."""
        mock_neo4j = Mock()
        mock_neo4j.verify_connectivity.side_effect = ConnectionError("Neo4j down")

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            with patch("src.mcp_server.main.qdrant_client", None):
                with patch("src.mcp_server.main.kv_store", None):
                    with patch("builtins.print") as mock_print:
                        result = await health()

        assert result["status"] == "degraded"
        assert result["services"]["neo4j"] == "unhealthy"
        mock_print.assert_called_with("Neo4j health check failed: Neo4j down")

    @pytest.mark.asyncio
    async def test_health_qdrant_unhealthy(self):
        """Test health check when Qdrant is unhealthy."""
        mock_qdrant = Mock()
        mock_qdrant.get_collections.side_effect = TimeoutError("Qdrant timeout")

        with patch("src.mcp_server.main.neo4j_client", None):
            with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
                with patch("src.mcp_server.main.kv_store", None):
                    with patch("builtins.print") as mock_print:
                        result = await health()

        assert result["status"] == "degraded"
        assert result["services"]["qdrant"] == "unhealthy"
        mock_print.assert_called_with("Qdrant health check failed: Qdrant timeout")

    @pytest.mark.asyncio
    async def test_health_redis_unhealthy(self):
        """Test health check when Redis is unhealthy."""
        mock_kv = Mock()
        mock_kv.redis = Mock()
        mock_kv.redis.redis_client = Mock()
        mock_kv.redis.redis_client.ping.side_effect = Exception("Redis error")

        with patch("src.mcp_server.main.neo4j_client", None):
            with patch("src.mcp_server.main.qdrant_client", None):
                with patch("src.mcp_server.main.kv_store", mock_kv):
                    with patch("builtins.print") as mock_print:
                        result = await health()

        assert result["status"] == "degraded"
        assert result["services"]["redis"] == "unhealthy"
        mock_print.assert_called_with("Redis health check failed: Redis error")

    @pytest.mark.asyncio
    async def test_health_no_clients_initialized(self):
        """Test health check when no clients are initialized."""
        with patch("src.mcp_server.main.neo4j_client", None):
            with patch("src.mcp_server.main.qdrant_client", None):
                with patch("src.mcp_server.main.kv_store", None):
                    result = await health()

        expected = {
            "status": "healthy",
            "services": {"neo4j": "unknown", "qdrant": "unknown", "redis": "unknown"},
        }
        assert result == expected


class TestStoreContextEndpoint:
    """Test cases for store_context endpoint."""

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.Config")
    async def test_store_context_success(self, mock_config):
        """Test successful context storage."""
        mock_config.EMBEDDING_DIMENSIONS = 768

        mock_qdrant = Mock()
        mock_qdrant.store_vector = Mock(return_value="vector_123")
        mock_neo4j = Mock()
        mock_neo4j.create_node = Mock(return_value="node_123")
        mock_neo4j.create_relationship = Mock()

        request = StoreContextRequest(
            content={"title": "Test", "body": "Content"},
            type="design",
            metadata={"author": "test"},
            relationships=[{"target": "ctx_456", "type": "RELATES_TO"}],
        )

        with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
            with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
                with patch("uuid.uuid4") as mock_uuid:
                    mock_uuid.return_value.hex = "abcdef123456"
                    result = await store_context(request)

        assert result["success"] is True
        assert result["id"] == "ctx_abcdef123456"
        assert result["vector_id"] == "vector_123"
        assert result["graph_id"] == "node_123"
        assert "stored successfully" in result["message"]

        mock_qdrant.store_vector.assert_called_once()
        mock_neo4j.create_node.assert_called_once()
        mock_neo4j.create_relationship.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_context_no_clients(self):
        """Test store context when no clients are available."""
        request = StoreContextRequest(content={"title": "Test"}, type="design")

        with patch("src.mcp_server.main.qdrant_client", None):
            with patch("src.mcp_server.main.neo4j_client", None):
                with patch("uuid.uuid4") as mock_uuid:
                    mock_uuid.return_value.hex = "abcdef123456"
                    result = await store_context(request)

        assert result["success"] is True
        assert result["vector_id"] is None
        assert result["graph_id"] is None

    @pytest.mark.asyncio
    async def test_store_context_exception(self):
        """Test store context with exception."""
        mock_qdrant = Mock()
        mock_qdrant.store_vector.side_effect = Exception("Storage failed")

        request = StoreContextRequest(content={"title": "Test"}, type="design")

        with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
            with patch("builtins.print") as mock_print:
                result = await store_context(request)

        assert result["success"] is False
        assert result["id"] is None
        assert "Failed to store context" in result["message"]
        mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_store_context_no_relationships(self):
        """Test store context without relationships."""
        mock_neo4j = Mock()
        mock_neo4j.create_node = Mock(return_value="node_123")

        request = StoreContextRequest(content={"title": "Test"}, type="design")

        with patch("src.mcp_server.main.qdrant_client", None):
            with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
                result = await store_context(request)

        mock_neo4j.create_relationship.assert_not_called()


class TestRetrieveContextEndpoint:
    """Test cases for retrieve_context endpoint."""

    @pytest.mark.asyncio
    async def test_retrieve_context_vector_search(self):
        """Test retrieve context with vector search."""
        mock_qdrant = Mock()
        mock_qdrant.search = Mock(
            return_value=[
                {"id": "ctx_1", "score": 0.9, "payload": {"content": "test1"}},
                {"id": "ctx_2", "score": 0.8, "payload": {"content": "test2"}},
            ]
        )

        request = RetrieveContextRequest(query="test query", search_mode="vector", limit=10)

        with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
            with patch("src.mcp_server.main.neo4j_client", None):
                result = await retrieve_context(request)

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["total_count"] == 2
        assert result["search_mode_used"] == "vector"
        mock_qdrant.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_context_graph_search(self):
        """Test retrieve context with graph search."""
        mock_neo4j = Mock()
        mock_neo4j.query = Mock(
            return_value=[
                {"n": {"id": "ctx_1", "content": "test1"}},
                {"n": {"id": "ctx_2", "content": "test2"}},
            ]
        )

        request = RetrieveContextRequest(
            query="test query", search_mode="graph", type="design", limit=5
        )

        with patch("src.mcp_server.main.qdrant_client", None):
            with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
                result = await retrieve_context(request)

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["search_mode_used"] == "graph"
        mock_neo4j.query.assert_called_once_with(
            """
            MATCH (n:Context)
            WHERE n.type = $type OR $type = 'all'
            RETURN n
            LIMIT $limit
            """,
            parameters={"type": "design", "limit": 5},
        )

    @pytest.mark.asyncio
    async def test_retrieve_context_hybrid_search(self):
        """Test retrieve context with hybrid search."""
        mock_qdrant = Mock()
        mock_qdrant.search = Mock(return_value=[{"id": "ctx_1", "score": 0.9}])
        mock_neo4j = Mock()
        mock_neo4j.query = Mock(return_value=[{"n": {"id": "ctx_2"}}])

        request = RetrieveContextRequest(query="test query", search_mode="hybrid", limit=10)

        with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
            with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
                result = await retrieve_context(request)

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["search_mode_used"] == "hybrid"
        mock_qdrant.search.assert_called_once()
        mock_neo4j.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_context_no_clients(self):
        """Test retrieve context when no clients are available."""
        request = RetrieveContextRequest(query="test")

        with patch("src.mcp_server.main.qdrant_client", None):
            with patch("src.mcp_server.main.neo4j_client", None):
                result = await retrieve_context(request)

        assert result["success"] is True
        assert result["results"] == []
        assert result["total_count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_context_exception(self):
        """Test retrieve context with exception."""
        mock_qdrant = Mock()
        mock_qdrant.search.side_effect = Exception("Search failed")

        request = RetrieveContextRequest(query="test", search_mode="vector")

        with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
            with patch("builtins.print") as mock_print:
                result = await retrieve_context(request)

        assert result["success"] is False
        assert result["results"] == []
        assert "Failed to retrieve context" in result["message"]
        mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_retrieve_context_limit_applied(self):
        """Test that limit is properly applied to results."""
        mock_qdrant = Mock()
        mock_qdrant.search = Mock(return_value=[{"id": f"ctx_{i}"} for i in range(20)])

        request = RetrieveContextRequest(query="test", search_mode="vector", limit=5)

        with patch("src.mcp_server.main.qdrant_client", mock_qdrant):
            result = await retrieve_context(request)

        assert len(result["results"]) == 5
        assert result["total_count"] == 20


class TestQueryGraphEndpoint:
    """Test cases for query_graph endpoint."""

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.validate_cypher_query")
    async def test_query_graph_success(self, mock_validate):
        """Test successful graph query."""
        mock_validate.return_value = (True, None)
        mock_neo4j = Mock()
        mock_neo4j.query = Mock(
            return_value=[
                {"n": {"id": "ctx_1", "name": "Test"}},
                {"n": {"id": "ctx_2", "name": "Test2"}},
            ]
        )

        request = QueryGraphRequest(
            query="MATCH (n) RETURN n", parameters={"param": "value"}, limit=100, timeout=5000
        )

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            result = await query_graph(request)

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["row_count"] == 2
        assert result["execution_time"] == 0

        mock_validate.assert_called_once_with("MATCH (n) RETURN n")
        mock_neo4j.query.assert_called_once_with(
            "MATCH (n) RETURN n",
            parameters={"param": "value"},
            timeout=5.0,  # Converted from milliseconds
        )

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.validate_cypher_query")
    async def test_query_graph_validation_failure(self, mock_validate):
        """Test graph query with validation failure."""
        mock_validate.return_value = (False, "Forbidden operation detected")

        request = QueryGraphRequest(query="CREATE (n)")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await query_graph(request)

        assert exc_info.value.status_code == 403
        assert "Query validation failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.validate_cypher_query")
    async def test_query_graph_no_neo4j_client(self, mock_validate):
        """Test graph query when Neo4j client is not available."""
        mock_validate.return_value = (True, None)

        request = QueryGraphRequest(query="MATCH (n) RETURN n")

        with patch("src.mcp_server.main.neo4j_client", None):
            result = await query_graph(request)

        assert result["success"] is False
        assert "Graph database not available" in result["error"]

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.validate_cypher_query")
    async def test_query_graph_query_exception(self, mock_validate):
        """Test graph query with query execution exception."""
        mock_validate.return_value = (True, None)
        mock_neo4j = Mock()
        mock_neo4j.query.side_effect = Exception("Query execution failed")

        request = QueryGraphRequest(query="MATCH (n) RETURN n")

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            result = await query_graph(request)

        assert result["success"] is False
        assert result["error"] == "Query execution failed"

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.validate_cypher_query")
    async def test_query_graph_limit_applied(self, mock_validate):
        """Test that limit is applied to query results."""
        mock_validate.return_value = (True, None)
        mock_neo4j = Mock()
        mock_neo4j.query = Mock(return_value=[{"n": {"id": f"ctx_{i}"}} for i in range(200)])

        request = QueryGraphRequest(query="MATCH (n) RETURN n", limit=50)

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            result = await query_graph(request)

        assert len(result["results"]) == 50
        assert result["row_count"] == 200

    @pytest.mark.asyncio
    @patch("src.mcp_server.main.validate_cypher_query")
    async def test_query_graph_no_parameters(self, mock_validate):
        """Test graph query without parameters."""
        mock_validate.return_value = (True, None)
        mock_neo4j = Mock()
        mock_neo4j.query = Mock(return_value=[])

        request = QueryGraphRequest(query="MATCH (n) RETURN n")

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            result = await query_graph(request)

        mock_neo4j.query.assert_called_once_with(
            "MATCH (n) RETURN n", parameters=None, timeout=5.0  # Should be None when not provided
        )


class TestListToolsEndpoint:
    """Test cases for list_tools endpoint."""

    @pytest.mark.asyncio
    async def test_list_tools_with_contracts(self):
        """Test list tools when contract files exist."""
        contract_data = [
            {"name": "store_context", "description": "Store context data", "version": "1.0.0"},
            {
                "name": "retrieve_context",
                "description": "Retrieve context data",
                "version": "1.0.0",
            },
        ]

        mock_contracts_dir = Mock()
        mock_contracts_dir.exists.return_value = True
        mock_contracts_dir.glob.return_value = [
            Path("store_context.json"),
            Path("retrieve_context.json"),
        ]

        mock_files = [
            mock_open(read_data=json.dumps(contract_data[0])).return_value,
            mock_open(read_data=json.dumps(contract_data[1])).return_value,
        ]

        with patch("src.mcp_server.main.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.parent.parent.parent.__truediv__ = Mock(return_value=mock_contracts_dir)
            mock_path.return_value = mock_path_instance
            with patch("builtins.open", side_effect=mock_files):
                result = await list_tools()

        assert len(result["tools"]) == 2
        assert result["server_version"] == "1.0.0"
        assert result["tools"][0]["name"] == "store_context"
        assert result["tools"][1]["name"] == "retrieve_context"

    @pytest.mark.asyncio
    async def test_list_tools_no_contracts_dir(self):
        """Test list tools when contracts directory doesn't exist."""
        mock_contracts_dir = Mock()
        mock_contracts_dir.exists.return_value = False

        with patch("src.mcp_server.main.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.parent.parent.parent.__truediv__ = Mock(return_value=mock_contracts_dir)
            mock_path.return_value = mock_path_instance
            result = await list_tools()

        assert result["tools"] == []
        assert result["server_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_list_tools_empty_contracts_dir(self):
        """Test list tools when contracts directory is empty."""
        mock_contracts_dir = Mock()
        mock_contracts_dir.exists.return_value = True
        mock_contracts_dir.glob.return_value = []

        with patch("src.mcp_server.main.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.parent.parent.parent.__truediv__ = Mock(return_value=mock_contracts_dir)
            mock_path.return_value = mock_path_instance
            result = await list_tools()

        assert result["tools"] == []
        assert result["server_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_list_tools_file_read_error(self):
        """Test list tools when contract file can't be read."""
        mock_contracts_dir = Mock()
        mock_contracts_dir.exists.return_value = True
        mock_contracts_dir.glob.return_value = [Path("invalid.json")]

        with patch("src.mcp_server.main.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.parent.parent.parent.__truediv__ = Mock(return_value=mock_contracts_dir)
            mock_path.return_value = mock_path_instance
            with patch("builtins.open", side_effect=FileNotFoundError()):
                # Should handle the error gracefully
                result = await list_tools()

        # Should still return basic response even if file reading fails
        assert "tools" in result
        assert result["server_version"] == "1.0.0"


class TestIntegrationWithTestClient:
    """Integration tests using FastAPI TestClient."""

    def test_health_endpoint_integration(self):
        """Test health endpoint via HTTP client."""
        client = TestClient(app)

        with patch("src.mcp_server.main.neo4j_client", None):
            with patch("src.mcp_server.main.qdrant_client", None):
                with patch("src.mcp_server.main.kv_store", None):
                    response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data

    def test_list_tools_endpoint_integration(self):
        """Test list tools endpoint via HTTP client."""
        client = TestClient(app)

        mock_contracts_dir = Mock()
        mock_contracts_dir.exists.return_value = False

        with patch("src.mcp_server.main.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.parent.parent.parent.__truediv__ = Mock(return_value=mock_contracts_dir)
            mock_path.return_value = mock_path_instance
            response = client.get("/tools")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert data["server_version"] == "1.0.0"

    def test_store_context_endpoint_integration(self):
        """Test store context endpoint via HTTP client."""
        client = TestClient(app)

        request_data = {"content": {"title": "Test Context"}, "type": "design"}

        with patch("src.mcp_server.main.qdrant_client", None):
            with patch("src.mcp_server.main.neo4j_client", None):
                response = client.post("/tools/store_context", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "id" in data

    def test_retrieve_context_endpoint_integration(self):
        """Test retrieve context endpoint via HTTP client."""
        client = TestClient(app)

        request_data = {"query": "test query"}

        with patch("src.mcp_server.main.qdrant_client", None):
            with patch("src.mcp_server.main.neo4j_client", None):
                response = client.post("/tools/retrieve_context", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "results" in data

    @patch("src.mcp_server.main.validate_cypher_query")
    def test_query_graph_endpoint_integration(self, mock_validate):
        """Test query graph endpoint via HTTP client."""
        client = TestClient(app)
        mock_validate.return_value = (True, None)

        request_data = {"query": "MATCH (n) RETURN n"}

        mock_neo4j = Mock()
        mock_neo4j.query = Mock(return_value=[])

        with patch("src.mcp_server.main.neo4j_client", mock_neo4j):
            response = client.post("/tools/query_graph", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "results" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
