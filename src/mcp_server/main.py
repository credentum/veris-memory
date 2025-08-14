#!/usr/bin/env python3
"""
◎ Veris Memory  | memory with covenant

Context Store MCP Server.

This module implements the Model Context Protocol (MCP) server for the context store.
It provides tools for storing, retrieving, and querying context data using both
vector embeddings and graph relationships.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import secure error handling and MCP validation
try:
    from ..core.error_handler import (
        create_error_response, 
        handle_storage_error, 
        handle_validation_error, 
        handle_generic_error
    )
    from ..core.mcp_validation import (
        validate_mcp_request,
        validate_mcp_response,
        get_mcp_validator
    )
except ImportError:
    from core.error_handler import (
        create_error_response, 
        handle_storage_error, 
        handle_validation_error, 
        handle_generic_error
    )
    from core.mcp_validation import (
        validate_mcp_request,
        validate_mcp_response,
        get_mcp_validator
    )

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure logging for import failures
logger = logging.getLogger(__name__)

# Import sentence-transformers with fallback
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("Sentence-transformers library available for semantic embeddings")
except ImportError as e:
    logger.warning(f"Sentence-transformers not available, will use fallback: {e}")
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    # Define dummy type for type hints when not available
    SentenceTransformer = type(None)

# Fail-fast on missing embeddings if strict mode enabled
if (
    not SENTENCE_TRANSFORMERS_AVAILABLE
    and os.getenv("STRICT_EMBEDDINGS", "false").lower() == "true"
):
    raise RuntimeError(
        "Embeddings unavailable: sentence-transformers not installed and STRICT_EMBEDDINGS=true"
    )

from ..core.config import Config

# Health check constants
HEALTH_CHECK_GRACE_PERIOD_DEFAULT = 60
HEALTH_CHECK_MAX_RETRIES_DEFAULT = 3
HEALTH_CHECK_RETRY_DELAY_DEFAULT = 5.0
from ..core.query_validator import validate_cypher_query

# Import storage components
# Import storage components - using simplified interface for MCP server
try:
    from ..storage.kv_store import ContextKV as KVStore
except ImportError as e:
    logger.warning(f"Failed to import KVStore: {e}")
    from ..storage.kv_store import ContextKV as KVStore

try:
    from ..storage.neo4j_client import Neo4jInitializer as Neo4jClient
except ImportError as e:
    logger.warning(f"Failed to import Neo4jClient: {e}")
    from ..storage.neo4j_client import Neo4jInitializer as Neo4jClient

try:
    from qdrant_client import QdrantClient as QdrantClientLib

    from ..storage.qdrant_client import VectorDBInitializer
except ImportError as e:
    logger.warning(f"Failed to import Qdrant components: {e}")
    from ..storage.qdrant_client import VectorDBInitializer

    QdrantClientLib = None
from ..validators.config_validator import validate_all_configs

# Global embedding model instance
_embedding_model: Optional[SentenceTransformer] = None


def _get_embedding_model() -> Optional[SentenceTransformer]:
    """
    Get or initialize the sentence-transformers model.

    Uses a lightweight, efficient model for semantic embeddings.
    Falls back to None if sentence-transformers is not available.

    Returns:
        SentenceTransformer model instance or None if unavailable
    """
    global _embedding_model

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None

    if _embedding_model is None:
        try:
            # Use a lightweight, efficient model for general-purpose embeddings
            model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            logger.info(f"Loading sentence-transformers model: {model_name}")
            _embedding_model = SentenceTransformer(model_name)
            dimensions = _embedding_model.get_sentence_embedding_dimension()
            logger.info(f"Successfully loaded model with {dimensions} dimensions")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {e}")
            _embedding_model = None

    return _embedding_model


async def _generate_embedding(content: Dict[str, Any]) -> List[float]:
    """
    Generate embedding vector from content using sentence-transformers for semantic embeddings.

    This function uses proper sentence-transformers models to create semantically meaningful
    embeddings instead of hash-based pseudo-embeddings. Falls back to hash-based approach
    only if sentence-transformers is unavailable.

    Args:
        content: The content to generate embedding for

    Returns:
        List of floats representing the embedding vector with semantic meaning
    """
    # Convert content to text for embedding
    if isinstance(content, dict):
        # Extract meaningful text from structured content
        text_parts = []

        # Handle common content structures
        if "title" in content:
            text_parts.append(content["title"])
        if "description" in content:
            text_parts.append(content["description"])
        if "body" in content:
            text_parts.append(content["body"])
        if "content" in content:
            text_parts.append(str(content["content"]))

        # Fallback to JSON string if no structured text found
        if not text_parts:
            text_parts = [json.dumps(content, sort_keys=True)]

        text_to_embed = " ".join(text_parts)
    else:
        text_to_embed = str(content)

    # Try to use sentence-transformers for semantic embeddings
    model = _get_embedding_model()
    if model is not None:
        try:
            # Generate semantic embedding using sentence-transformers
            embedding = model.encode(text_to_embed, convert_to_tensor=False)
            # Convert numpy array to list if needed
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            else:
                embedding = list(embedding)

            embedding_dim = len(embedding)
            logger.debug(
                f"Generated semantic embedding with {embedding_dim} dimensions "
                f"using sentence-transformers"
            )
            return embedding

        except Exception as e:
            logger.warning(
                f"Failed to generate semantic embedding, falling back to hash-based: {e}"
            )

    # Critical error: Hash-based embeddings lack semantic meaning
    # This breaks MCP protocol compatibility for semantic search
    logger.error(
        "EMBEDDING_FALLBACK_ERROR: Hash-based embeddings are semantically meaningless. "
        "Install sentence-transformers for MCP protocol compliance."
    )

    # For MCP protocol compliance, we should fail rather than provide meaningless embeddings
    if os.getenv("STRICT_EMBEDDINGS", "false").lower() == "true":
        raise ValueError(
            "Semantic embeddings unavailable and STRICT_EMBEDDINGS=true. "
            "Install sentence-transformers package for proper MCP protocol support."
        )

    # Legacy hash-based fallback (deprecated, breaks semantic search)
    import hashlib

    hash_obj = hashlib.sha256(text_to_embed.encode())
    hash_bytes = hash_obj.digest()

    # Use standardized embedding dimensions from Config
    embedding_dim = Config.EMBEDDING_DIMENSIONS
    embedding = []

    for i in range(embedding_dim):
        byte_idx = i % len(hash_bytes)
        embedding.append(float(hash_bytes[byte_idx]) / 255.0)

    logger.debug(f"Generated hash-based fallback embedding with {len(embedding)} dimensions")
    return embedding


app = FastAPI(
    title="Context Store MCP Server",
    description="Model Context Protocol server for context management",
    version="1.0.0",
    debug=False,  # Disable debug mode for production security
)


# Global exception handler for production security with request tracking
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Sanitize all unhandled exceptions for production security with structured logging."""
    import time
    import uuid

    # Generate request ID for tracking
    request_id = str(uuid.uuid4())[:8]
    timestamp = time.time()

    # Structured logging with context (but sanitized response)
    logger.error(
        "Unhandled exception in request",
        extra={
            "request_id": request_id,
            "timestamp": timestamp,
            "method": request.method,
            "url": str(request.url),
            "client_host": request.client.host if request.client else "unknown",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
        exc_info=True,
    )

    # Return sanitized error with request ID for debugging
    return JSONResponse(
        status_code=500,
        content={"error": "internal", "request_id": request_id, "timestamp": timestamp},
    )


# Global storage clients
neo4j_client = None
qdrant_client = None
kv_store = None


class StoreContextRequest(BaseModel):
    """Request model for store_context tool."""

    content: Dict[str, Any]
    type: str = Field(..., pattern="^(design|decision|trace|sprint|log)$")
    metadata: Optional[Dict[str, Any]] = None
    relationships: Optional[List[Dict[str, str]]] = None


class RetrieveContextRequest(BaseModel):
    """Request model for retrieve_context tool."""

    query: str
    type: Optional[str] = "all"
    search_mode: str = "hybrid"
    limit: int = Field(10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    include_relationships: bool = False


class QueryGraphRequest(BaseModel):
    """Request model for query_graph tool."""

    query: str
    parameters: Optional[Dict[str, Any]] = None
    limit: int = Field(100, ge=1, le=1000)
    timeout: int = Field(5000, ge=1, le=30000)


class UpdateScratchpadRequest(BaseModel):
    """Request model for update_scratchpad tool.
    
    Defines the input schema for updating agent scratchpad data.
    """
    agent_id: str = Field(..., description="Agent identifier", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    key: str = Field(..., description="Scratchpad key", pattern=r"^[a-zA-Z0-9_.-]{1,128}$")
    content: str = Field(..., description="Content to store in the scratchpad", min_length=1, max_length=100000)
    mode: str = Field("overwrite", description="Update mode for the content", pattern=r"^(overwrite|append)$")
    ttl: int = Field(3600, ge=60, le=86400, description="Time to live in seconds")


class GetAgentStateRequest(BaseModel):
    """Request model for get_agent_state tool.
    
    Defines the input schema for retrieving agent state data.
    """
    agent_id: str = Field(..., description="Agent identifier")
    key: Optional[str] = Field(None, description="Specific state key")
    prefix: str = Field("state", description="State type prefix")


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize storage clients and MCP validation on startup."""
    global neo4j_client, qdrant_client, kv_store
    
    # Initialize MCP contract validator
    try:
        validator = get_mcp_validator()
        summary = validator.get_validation_summary()
        print(f"✅ MCP Contract Validation initialized: {summary['contracts_loaded']} contracts loaded")
        print(f"📋 Available MCP tools: {', '.join(summary['available_tools'])}")
    except Exception as e:
        print(f"⚠️ MCP validation initialization warning: {e}")
        logger.warning(f"MCP validation setup warning: {e}")
    

    # Validate configuration
    config_result = validate_all_configs()
    if not config_result.get("valid", False):
        raise RuntimeError(f"Configuration validation failed: {config_result}")

    try:
        # Initialize Neo4j (allow graceful degradation if unavailable)
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if not neo4j_password:
            print("⚠️ NEO4J_PASSWORD not set - Neo4j will be unavailable")
            neo4j_client = None
        else:
            try:
                neo4j_client = Neo4jClient()
                neo4j_client.connect(
                    username=os.getenv("NEO4J_USER", "neo4j"), password=neo4j_password
                )
                print("✅ Neo4j connected successfully")
            except Exception as neo4j_error:
                print(f"⚠️ Neo4j unavailable: {neo4j_error}")
                neo4j_client = None

        # Initialize Qdrant (allow graceful degradation if unavailable)
        try:
            qdrant_initializer = VectorDBInitializer()
            if qdrant_initializer.connect():
                # Get the actual Qdrant client for operations
                qdrant_client = qdrant_initializer
                print("✅ Qdrant connected successfully")
            else:
                qdrant_client = None
        except Exception as qdrant_error:
            print(f"⚠️ Qdrant unavailable: {qdrant_error}")
            qdrant_client = None

        # Initialize KV Store (Redis - required for core functionality)
        kv_store = KVStore()
        redis_password = os.getenv("REDIS_PASSWORD")
        kv_store.connect(redis_password=redis_password)
        print("✅ Redis connected successfully")

        print("✅ Storage initialization completed (services may be degraded)")
    except Exception as e:
        print(f"❌ Critical failure in storage initialization: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up storage clients on shutdown."""
    if neo4j_client:
        neo4j_client.close()
    if kv_store:
        kv_store.close()

    print("Storage clients closed")


@app.get("/")
async def root() -> Dict[str, Any]:
    """
    Root endpoint providing agent discovery information.

    Returns comprehensive API information including available endpoints,
    MCP protocol details, and agent integration instructions.
    """
    return {
        "service": "◎ Veris Memory",
        "tagline": "memory with covenant",
        "version": "0.9.0",
        "protocol": {
            "name": "Model Context Protocol (MCP)",
            "version": "1.0",
            "spec": "https://spec.modelcontextprotocol.io/specification/",
        },
        "endpoints": {
            "health": {
                "path": "/health",
                "method": "GET",
                "description": "System health check with service status",
            },
            "status": {
                "path": "/status",
                "method": "GET",
                "description": "Comprehensive status with tools and dependencies",
            },
            "readiness": {
                "path": "/tools/verify_readiness",
                "method": "POST",
                "description": "Agent readiness verification and diagnostics",
            },
        },
        "capabilities": {
            "schema": "agent-first-schema-protocol",
            "tools": [
                "store_context",
                "retrieve_context",
                "query_graph",
                "update_scratchpad",
                "get_agent_state",
            ],
            "storage": {
                "vector": "Qdrant (high-dimensional semantic search)",
                "graph": "Neo4j (relationship and knowledge graphs)",
                "kv": "Redis (fast key-value caching)",
                "analytics": "DuckDB (structured data analysis)",
            },
        },
        "integration": {
            "mcp_client": {
                "url": "https://veris-memory.fly.dev",
                "connection": "HTTP/HTTPS",
                "authentication": "None (public)",
                "rate_limits": "60 requests/minute",
            },
            "agent_usage": {
                "step1": "GET /status to verify system health",
                "step2": "POST /tools/verify_readiness for diagnostics",
                "step3": "Use MCP tools via standard protocol calls",
            },
        },
        "documentation": {
            "repository": "https://github.com/credentum/veris-memory",
            "organization": "https://github.com/credentum",
            "contact": "Issues and PRs welcome",
        },
        "deployment": {
            "platform": "Fly.io",
            "region": "iad (US East)",
            "resources": "8GB memory, 4 performance CPUs",
            "uptime_target": "99.9%",
        },
    }


# Global startup time tracking
_server_startup_time = time.time()


async def _check_service_with_retries(
    service_name: str,
    check_func,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None,
) -> Tuple[str, str]:
    """Check a service with retry logic and detailed error reporting.

    Args:
        service_name: Name of the service being checked
        check_func: Function to call for health check
        max_retries: Maximum number of retry attempts (default from env HEALTH_CHECK_MAX_RETRIES)
        retry_delay: Delay between retries in seconds (default from env HEALTH_CHECK_RETRY_DELAY)

    Returns:
        tuple: (status, error_message)
        status: "healthy", "initializing", "unhealthy"
    """
    # Use environment variables for configuration with defaults
    if max_retries is None:
        max_retries = int(
            os.getenv("HEALTH_CHECK_MAX_RETRIES", str(HEALTH_CHECK_MAX_RETRIES_DEFAULT))
        )
    if retry_delay is None:
        retry_delay = float(
            os.getenv("HEALTH_CHECK_RETRY_DELAY", str(HEALTH_CHECK_RETRY_DELAY_DEFAULT))
        )

    last_error = None

    for attempt in range(max_retries):
        try:
            await asyncio.get_event_loop().run_in_executor(None, check_func)
            logger.info(f"{service_name} health check successful on attempt {attempt + 1}")
            return "healthy", ""
        except (ConnectionRefusedError, OSError) as e:
            # Network-level connection errors
            last_error = f"Connection error: {e}"
            logger.warning(
                f"{service_name} connection refused on attempt {attempt + 1}/{max_retries}: {e}"
            )
        except TimeoutError as e:
            # Timeout errors
            last_error = f"Timeout error: {e}"
            logger.warning(f"{service_name} timeout on attempt {attempt + 1}/{max_retries}: {e}")
        except ImportError as e:
            # Missing dependencies - don't retry these
            last_error = f"Missing dependency: {e}"
            logger.error(f"{service_name} missing dependency: {e}")
            return "unhealthy", last_error
        except Exception as e:
            # Generic errors
            last_error = f"Service error: {e}"
            logger.warning(
                f"{service_name} health check failed on attempt {attempt + 1}/{max_retries}: {e}"
            )

        if attempt < max_retries - 1:  # Don't sleep on the last attempt
            await asyncio.sleep(retry_delay)

    # All retries failed
    error_msg = f"Failed after {max_retries} attempts. Last error: {last_error}"
    logger.error(f"{service_name} health check failed: {error_msg}")
    return "unhealthy", error_msg


def _is_in_startup_grace_period(grace_period_seconds: int = None) -> bool:
    """Check if we're still in the startup grace period.

    Args:
        grace_period_seconds: Grace period duration (default from env HEALTH_CHECK_GRACE_PERIOD)
    """
    if grace_period_seconds is None:
        grace_period_seconds = int(
            os.getenv("HEALTH_CHECK_GRACE_PERIOD", str(HEALTH_CHECK_GRACE_PERIOD_DEFAULT))
        )

    return (time.time() - _server_startup_time) < grace_period_seconds


@app.get("/health")
async def health() -> Dict[str, Any]:
    """
    Enhanced health check endpoint with grace periods and retry logic.

    Returns the health status of the server and its dependencies.
    Implements 60-second grace period and 3-retry mechanism as per issue #1759.
    """
    startup_elapsed = time.time() - _server_startup_time
    in_grace_period = _is_in_startup_grace_period()

    health_status = {
        "status": "healthy",
        "services": {"neo4j": "unknown", "qdrant": "unknown", "redis": "unknown"},
        "startup_time": _server_startup_time,
        "uptime_seconds": int(startup_elapsed),
        "grace_period_active": in_grace_period,
    }

    # During grace period, services might still be initializing
    if in_grace_period:
        logger.info(f"Health check during grace period ({int(startup_elapsed)}s elapsed)")

    # Check Neo4j with retries
    if neo4j_client:
        try:

            def neo4j_check():
                # Simple connectivity test using a basic query
                return neo4j_client.query("RETURN 1 as test")

            status, error = await _check_service_with_retries("Neo4j", neo4j_check)

            if status == "healthy":
                health_status["services"]["neo4j"] = "healthy"
            elif in_grace_period and status == "unhealthy":
                health_status["services"]["neo4j"] = "initializing"
                health_status["status"] = "initializing"
            else:
                health_status["services"]["neo4j"] = "unhealthy"
                health_status["status"] = "degraded"
                health_status["neo4j_error"] = error
        except Exception as e:
            health_status["services"]["neo4j"] = "initializing" if in_grace_period else "unhealthy"
            health_status["status"] = "initializing" if in_grace_period else "degraded"
            logger.error(f"Neo4j health check exception: {e}")

    # Check Qdrant with retries
    if qdrant_client:
        try:

            def qdrant_check():
                return qdrant_client.get_collections()

            status, error = await _check_service_with_retries("Qdrant", qdrant_check)

            if status == "healthy":
                health_status["services"]["qdrant"] = "healthy"
            elif in_grace_period and status == "unhealthy":
                health_status["services"]["qdrant"] = "initializing"
                health_status["status"] = "initializing"
            else:
                health_status["services"]["qdrant"] = "unhealthy"
                health_status["status"] = "degraded"
                health_status["qdrant_error"] = error
        except Exception as e:
            health_status["services"]["qdrant"] = "initializing" if in_grace_period else "unhealthy"
            health_status["status"] = "initializing" if in_grace_period else "degraded"
            logger.error(f"Qdrant health check exception: {e}")

    # Check Redis with retries (Redis usually starts fast)
    if kv_store:
        try:

            def redis_check():
                if kv_store.redis.redis_client:
                    return kv_store.redis.redis_client.ping()
                return True

            status, error = await _check_service_with_retries(
                "Redis", redis_check, max_retries=2, retry_delay=2.0
            )

            if status == "healthy":
                health_status["services"]["redis"] = "healthy"
            else:
                health_status["services"]["redis"] = "unhealthy"
                health_status["status"] = "degraded"
                health_status["redis_error"] = error
        except Exception as e:
            health_status["services"]["redis"] = "unhealthy"
            health_status["status"] = "degraded"
            logger.error(f"Redis health check exception: {e}")

    # Final status determination
    all_services = list(health_status["services"].values())
    if all(s == "healthy" for s in all_services):
        health_status["status"] = "healthy"
    elif any(s == "initializing" for s in all_services) and in_grace_period:
        health_status["status"] = "initializing"
    else:
        health_status["status"] = "degraded"

    logger.info(
        f"Health check result: {health_status['status']} - Services: {health_status['services']}"
    )
    return health_status


@app.get("/status")
async def status() -> Dict[str, Any]:
    """
    Enhanced status endpoint for agent orchestration.

    Returns comprehensive system information including Veris Memory identity,
    available tools, version information, and dependency health.
    """
    # Get health status
    health_status = await health()

    return {
        "label": "◎ Veris Memory",
        "version": "0.9.0",
        "protocol": "MCP-1.0",
        "deps": {
            "qdrant": "ok" if health_status["services"]["qdrant"] == "healthy" else "error",
            "neo4j": "ok" if health_status["services"]["neo4j"] == "healthy" else "error",
            "redis": "ok" if health_status["services"]["redis"] == "healthy" else "error",
        },
        "tools": [
            "store_context",
            "retrieve_context",
            "query_graph",
            "update_scratchpad",
            "get_agent_state",
        ],
    }


@app.post("/tools/verify_readiness")
async def verify_readiness() -> Dict[str, Any]:
    """
    Agent readiness verification endpoint.

    Provides diagnostic information for agents to verify system readiness,
    including tool availability, schema versions, and resource quotas.
    """
    try:
        # Get current status
        status_info = await status()

        # Check tool availability
        tools_available = len(status_info["tools"])

        # Get index sizes if possible
        index_info = {}
        if qdrant_client:
            try:
                collections = qdrant_client.get_collections()
                if hasattr(collections, "collections"):
                    for collection in collections.collections:
                        if collection.name == "context_store":
                            index_info["vector_count"] = (
                                collection.vectors_count
                                if hasattr(collection, "vectors_count")
                                else "unknown"
                            )
            except Exception:
                index_info["vector_count"] = "unavailable"

        if neo4j_client:
            try:
                # Try to get node count
                result = neo4j_client.execute_query("MATCH (n) RETURN count(n) as node_count")
                if result and len(result) > 0:
                    index_info["graph_nodes"] = result[0].get("node_count", "unknown")
            except Exception:
                index_info["graph_nodes"] = "unavailable"

        # Schema version from agent schema
        schema_version = "0.9.0"  # From agent-schema.json

        readiness_score = 0
        if status_info["agent_ready"]:
            readiness_score += 40  # Base readiness
        if tools_available == 5:
            readiness_score += 30  # All tools available
        if index_info:
            readiness_score += 20  # Indexes accessible
        readiness_score += 10  # Schema compatibility

        return {
            "ready": status_info["agent_ready"],
            "readiness_score": min(readiness_score, 100),
            "tools_available": tools_available,
            "tools_expected": 5,
            "schema_version": schema_version,
            "protocol_version": "MCP-1.0",
            "indexes": index_info,
            "dependencies": status_info["dependencies"],
            "usage_quotas": {
                "vector_operations": "unlimited",
                "graph_queries": "unlimited",
                "kv_operations": "unlimited",
                "note": "Quotas depend on underlying database limits",
            },
            "recommended_actions": [
                (
                    "Verify all dependencies are healthy"
                    if not status_info["agent_ready"]
                    else "System ready for agent operations"
                ),
                (
                    f"Tools available: {tools_available}/5"
                    if tools_available < 5
                    else "All MCP tools operational"
                ),
            ],
        }

    except Exception as e:
        return {
            "ready": False,
            "readiness_score": 0,
            "error": str(e),
            "recommended_actions": [
                "Check system logs for detailed error information",
                "Verify all dependencies are running and accessible",
            ],
        }


@app.post("/tools/store_context")
async def store_context(request: StoreContextRequest) -> Dict[str, Any]:
    """
    Store context with embeddings and graph relationships.

    This tool stores context data in both vector and graph databases,
    enabling hybrid retrieval capabilities.
    """
    try:
        # Generate unique ID
        import uuid

        context_id = f"ctx_{uuid.uuid4().hex[:12]}"

        # Store in vector database
        vector_id = None
        if qdrant_client:
            # Create embedding from content using proper embedding service
            embedding = await _generate_embedding(request.content)
            logger.info(f"Generated embedding with {len(embedding)} dimensions")

            vector_id = qdrant_client.store_vector(
                vector_id=context_id,
                embedding=embedding,
                metadata={
                    "content": request.content,
                    "type": request.type,
                    "metadata": request.metadata,
                }
            )

        # Store in graph database
        graph_id = None
        if neo4j_client:
            graph_id = neo4j_client.create_node(
                label="Context",
                properties={"id": context_id, "type": request.type, **request.content},
            )

            # Create relationships if specified
            if request.relationships:
                for rel in request.relationships:
                    neo4j_client.create_relationship(
                        from_id=graph_id, to_id=rel["target"], rel_type=rel["type"]
                    )

        return {
            "success": True,
            "id": context_id,
            "vector_id": vector_id,
            "graph_id": graph_id,
            "message": "Context stored successfully",
        }

    except Exception as e:
        import traceback

        print(f"Error storing context: {traceback.format_exc()}")
        return handle_generic_error(e, "store context")


@app.post("/tools/retrieve_context")
async def retrieve_context(request: RetrieveContextRequest) -> Dict[str, Any]:
    """
    Retrieve context using hybrid search.

    Combines vector similarity search with graph traversal for
    comprehensive context retrieval.
    """
    try:
        results = []

        if request.search_mode in ["vector", "hybrid"] and qdrant_client:
            # Perform vector search using hash-based embedding
            import hashlib

            query_hash = hashlib.sha256(request.query.encode()).digest()
            query_vector = []
            embedding_dim = Config.EMBEDDING_DIMENSIONS
            for i in range(embedding_dim):
                byte_idx = i % len(query_hash)
                query_vector.append(float(query_hash[byte_idx]) / 255.0)

            try:
                # Get collection name from config (default: context_store)
                collection_name = os.getenv("QDRANT_COLLECTION", "context_store")

                vector_results = qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=request.limit,
                )

                # Convert results to proper format
                for result in vector_results:
                    results.append(
                        {
                            "id": result.id,
                            "content": result.payload,
                            "score": result.score,
                            "source": "vector",
                        }
                    )

            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                # Continue with other search modes

        if request.search_mode in ["graph", "hybrid"] and neo4j_client:
            # Perform graph search
            cypher_query = """
            MATCH (n:Context)
            WHERE n.type = $type OR $type = 'all'
            RETURN n
            LIMIT $limit
            """
            graph_results = neo4j_client.query(
                cypher_query, parameters={"type": request.type, "limit": request.limit}
            )
            results.extend(graph_results)

        return {
            "success": True,
            "results": results[: request.limit],
            "total_count": len(results),
            "search_mode_used": request.search_mode,
            "message": f"Found {len(results)} matching contexts",
        }

    except Exception as e:
        import traceback

        print(f"Error retrieving context: {traceback.format_exc()}")
        error_response = handle_generic_error(e, "retrieve context")
        error_response["results"] = []
        return error_response


@app.post("/tools/query_graph")
async def query_graph(request: QueryGraphRequest) -> Dict[str, Any]:
    """
    Execute Cypher queries on the graph database.

    Allows read-only graph queries for advanced context exploration.
    """
    # Security check - validate query for safety
    is_valid, error_msg = validate_cypher_query(request.query)
    if not is_valid:
        raise HTTPException(status_code=403, detail=f"Query validation failed: {error_msg}")

    try:
        if not neo4j_client:
            raise HTTPException(status_code=503, detail="Graph database not available")

        results = neo4j_client.query(
            request.query,
            parameters=request.parameters
        )

        return {
            "success": True,
            "results": results[: request.limit],
            "row_count": len(results),
            "execution_time": 0,  # Placeholder
        }

    except Exception as e:
        return handle_generic_error(e, "execute graph query")


@app.post("/tools/update_scratchpad")
async def update_scratchpad_endpoint(request: UpdateScratchpadRequest) -> Dict[str, Any]:
    """Update agent scratchpad with transient storage.
    
    Provides temporary storage for agent working memory with TTL support.
    Supports both overwrite and append modes with namespace isolation.
    
    Args:
        request: UpdateScratchpadRequest containing agent_id, key, content, mode, and ttl
        
    Returns:
        Dict containing success status, message, and operation details
    """
    # Validate request against MCP contract
    request_data = request.model_dump()
    validation_errors = validate_mcp_request("update_scratchpad", request_data)
    if validation_errors:
        logger.warning(f"MCP contract validation failed: {validation_errors}")
        # Continue processing - validation is for compliance monitoring
    
    try:
        if not kv_store:
            raise HTTPException(status_code=503, detail="KV store not available")
        
        # Create namespaced key
        redis_key = f"scratchpad:{request.agent_id}:{request.key}"
        
        # Store value with TTL based on mode
        if request.mode == "append" and kv_store.exists(redis_key):
            # Append mode: get existing content and append
            existing_content = kv_store.get(redis_key) or ""
            if isinstance(existing_content, bytes):
                existing_content = existing_content.decode('utf-8')
            content_str = f"{existing_content}\n{request.content}"
        else:
            # Overwrite mode or no existing content
            content_str = request.content
        try:
            success = kv_store.set(redis_key, content_str, ex=request.ttl)
        except (ConnectionError, TimeoutError, Exception) as e:
            return handle_storage_error(e, "update scratchpad")
        
        if success:
            return {
                "success": True,
                "agent_id": request.agent_id,
                "key": redis_key,
                "ttl": request.ttl,
                "content_size": len(content_str),
                "message": f"Scratchpad updated successfully (mode: {request.mode})"
            }
        else:
            return {
                "success": False,
                "error_type": "storage_error",
                "message": "Failed to update scratchpad"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        return handle_generic_error(e, "update scratchpad")


@app.post("/tools/get_agent_state")
async def get_agent_state_endpoint(request: GetAgentStateRequest) -> Dict[str, Any]:
    """Retrieve agent state from storage.
    
    Returns agent-specific state data with namespace isolation.
    Supports retrieving specific keys or all keys for an agent.
    
    Args:
        request: GetAgentStateRequest containing agent_id, optional key, and prefix
        
    Returns:
        Dict containing success status, retrieved data, and available keys
    """
    # Validate request against MCP contract
    request_data = request.model_dump()
    validation_errors = validate_mcp_request("get_agent_state", request_data)
    if validation_errors:
        logger.warning(f"MCP contract validation failed: {validation_errors}")
        # Continue processing - validation is for compliance monitoring
    
    try:
        if not kv_store:
            raise HTTPException(status_code=503, detail="KV store not available")
        
        # Build key pattern
        if request.key:
            redis_key = f"{request.prefix}:{request.agent_id}:{request.key}"
            try:
                value = kv_store.get(redis_key)
            except (ConnectionError, Exception) as e:
                error_response = handle_storage_error(e, "get agent state")
                error_response["data"] = {}
                return error_response
            
            if value is None:
                return {
                    "success": False,
                    "data": {},
                    "message": f"No state found for key: {request.key}"
                }
            
            # Parse JSON if possible
            try:
                data = json.loads(value) if isinstance(value, bytes) else value
            except json.JSONDecodeError:
                data = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return {
                "success": True,
                "data": {request.key: data},
                "agent_id": request.agent_id,
                "message": "State retrieved successfully"
            }
        else:
            # Get all keys for agent
            pattern = f"{request.prefix}:{request.agent_id}:*"
            try:
                keys = kv_store.keys(pattern)
            except (ConnectionError, Exception) as e:
                error_response = handle_storage_error(e, "get agent state")
                error_response["data"] = {}
                return error_response
            
            if not keys:
                return {
                    "success": True,
                    "data": {},
                    "keys": [],
                    "agent_id": request.agent_id,
                    "message": "No state found for agent"
                }
            
            # Retrieve all values
            data = {}
            for key in keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                key_name = key_str.split(':', 2)[-1]  # Extract key name
                value = kv_store.get(key)
                
                try:
                    data[key_name] = json.loads(value) if isinstance(value, bytes) else value
                except json.JSONDecodeError:
                    data[key_name] = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return {
                "success": True,
                "data": data,
                "keys": list(data.keys()),
                "agent_id": request.agent_id,
                "message": f"Retrieved {len(data)} state entries"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        error_response = handle_generic_error(e, "retrieve agent state")
        error_response["data"] = {}
        return error_response


@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List available MCP tools and their contracts."""
    contracts_dir = Path(__file__).parent.parent.parent / "contracts"
    tools = []

    if contracts_dir.exists():
        for contract_file in contracts_dir.glob("*.json"):
            try:
                with open(contract_file) as f:
                    contract = json.load(f)
                    tools.append(
                        {
                            "name": contract.get("name"),
                            "description": contract.get("description"),
                            "version": contract.get("version"),
                        }
                    )
            except FileNotFoundError as e:
                logger.warning(f"Contract file not found: {contract_file} - {e}")
                continue
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in contract file {contract_file}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading contract file {contract_file}: {e}")
                continue

    return {"tools": tools, "server_version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MCP_SERVER_PORT", 8000)))
