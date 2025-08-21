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
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import SortBy

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
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Import SimpleRedisClient for direct Redis operations
try:
    from ..storage.simple_redis import SimpleRedisClient
except ImportError as e:
    logger.warning(f"Failed to import SimpleRedisClient: {e}")
    from storage.simple_redis import SimpleRedisClient

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

# Import monitoring dashboard components
try:
    from ..monitoring.dashboard import UnifiedDashboard
    from ..monitoring.streaming import MetricsStreamer
    from ..monitoring.request_metrics import get_metrics_collector, RequestMetricsMiddleware
    DASHBOARD_AVAILABLE = True
    REQUEST_METRICS_AVAILABLE = True
    logger.info("Dashboard monitoring components available")
except ImportError as e:
    logger.warning(f"Dashboard monitoring not available: {e}")
    DASHBOARD_AVAILABLE = False
    REQUEST_METRICS_AVAILABLE = False
    UnifiedDashboard = None
    MetricsStreamer = None

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
            
            # Pad or truncate to match Qdrant collection dimensions
            target_dim = Config.EMBEDDING_DIMENSIONS
            if embedding_dim < target_dim:
                # Pad with zeros
                padding = [0.0] * (target_dim - embedding_dim)
                embedding = embedding + padding
                logger.debug(f"Padded embedding from {embedding_dim} to {target_dim} dimensions")
            elif embedding_dim > target_dim:
                # Truncate
                embedding = embedding[:target_dim]
                logger.debug(f"Truncated embedding from {embedding_dim} to {target_dim} dimensions")
            
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request metrics middleware if available
if REQUEST_METRICS_AVAILABLE:
    app.add_middleware(RequestMetricsMiddleware, metrics_collector=get_metrics_collector())


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
simple_redis = None  # Direct Redis client for scratchpad operations

# Global dashboard components
dashboard = None
websocket_connections = set()  # Track WebSocket connections


class StoreContextRequest(BaseModel):
    """Request model for store_context tool.
    
    Attributes:
        content: Dictionary containing the context data to store
        type: Type of context (design, decision, trace, sprint, log)
        metadata: Optional metadata associated with the context
        relationships: Optional list of relationships to other contexts
    """

    content: Dict[str, Any]
    type: str = Field(..., pattern="^(design|decision|trace|sprint|log)$")
    metadata: Optional[Dict[str, Any]] = None
    relationships: Optional[List[Dict[str, str]]] = None


class RetrieveContextRequest(BaseModel):
    """Request model for retrieve_context tool.
    
    Attributes:
        query: Search query string
        type: Context type filter, defaults to "all"
        search_mode: Search strategy (vector, graph, hybrid)
        limit: Maximum number of results to return
        filters: Optional additional filters
        include_relationships: Whether to include relationship data
        sort_by: Sort order for results (timestamp or relevance)
    """

    query: str
    type: Optional[str] = "all"
    search_mode: str = "hybrid"
    limit: int = Field(10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    include_relationships: bool = False
    sort_by: SortBy = Field(SortBy.TIMESTAMP)


class QueryGraphRequest(BaseModel):
    """Request model for query_graph tool.
    
    Attributes:
        query: Cypher query string to execute
        parameters: Optional query parameters
        limit: Maximum number of results to return
        timeout: Query timeout in milliseconds
    """

    query: str
    parameters: Optional[Dict[str, Any]] = None
    limit: int = Field(100, ge=1, le=1000)
    timeout: int = Field(5000, ge=1, le=30000)


class UpdateScratchpadRequest(BaseModel):
    """Request model for update_scratchpad tool.
    
    Attributes:
        agent_id: Unique identifier for the agent (alphanumeric, underscore, hyphen)
        key: Key for the scratchpad entry (alphanumeric, underscore, dot, hyphen)
        content: Content to store in the scratchpad
        mode: Update mode - "overwrite" or "append"
        ttl: Time to live in seconds (60-86400)
    """
    agent_id: str = Field(..., description="Agent identifier", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    key: str = Field(..., description="Scratchpad key", pattern=r"^[a-zA-Z0-9_.-]{1,128}$")
    content: str = Field(..., description="Content to store in the scratchpad", min_length=1, max_length=100000)
    mode: str = Field("overwrite", description="Update mode for the content", pattern=r"^(overwrite|append)$")
    ttl: int = Field(3600, ge=60, le=86400, description="Time to live in seconds")


class GetAgentStateRequest(BaseModel):
    """Request model for get_agent_state tool.
    
    Attributes:
        agent_id: Unique identifier for the agent
        key: Optional specific state key to retrieve
        prefix: State type prefix for namespacing
    """
    agent_id: str = Field(..., description="Agent identifier")
    key: Optional[str] = Field(None, description="Specific state key")
    prefix: str = Field("state", description="State type prefix")


def validate_and_get_credential(env_var_name: str, required: bool = True, min_length: int = 8) -> Optional[str]:
    """
    Securely retrieve and validate credentials from environment variables.
    
    Args:
        env_var_name: Name of the environment variable
        required: Whether the credential is required for operation
        min_length: Minimum length for password validation
        
    Returns:
        The credential value if valid, None if optional and missing
        
    Raises:
        RuntimeError: If required credential is missing or invalid
    """
    credential = os.getenv(env_var_name)
    
    if not credential:
        if required:
            raise RuntimeError(f"Required credential {env_var_name} is not set")
        return None
    
    # Basic validation
    if len(credential) < min_length:
        raise RuntimeError(f"Credential {env_var_name} is too short (minimum {min_length} characters)")
    
    # Check for common insecure defaults
    insecure_defaults = ["password", "123456", "admin", "default", "changeme", "secret"]
    if credential.lower() in insecure_defaults:
        raise RuntimeError(f"Credential {env_var_name} uses an insecure default value")
    
    return credential


def validate_startup_credentials() -> Dict[str, Optional[str]]:
    """
    Validate all required credentials at startup with fail-fast behavior.
    
    Returns:
        Dictionary of validated credentials
        
    Raises:
        RuntimeError: If any required credential validation fails
    """
    try:
        credentials = {
            'neo4j_password': validate_and_get_credential("NEO4J_PASSWORD", required=False),
            'qdrant_api_key': validate_and_get_credential("QDRANT_API_KEY", required=False, min_length=1),
            'redis_password': validate_and_get_credential("REDIS_PASSWORD", required=False, min_length=1)
        }
        
        # Log secure startup status
        available_services = []
        if credentials['neo4j_password']:
            available_services.append("Neo4j")
        if credentials['qdrant_api_key']:
            available_services.append("Qdrant")
        if credentials['redis_password']:
            available_services.append("Redis")
            
        logger.info(f"Credential validation complete. Available services: {', '.join(available_services) if available_services else 'Core only'}")
        
        return credentials
        
    except Exception as e:
        logger.error(f"Credential validation failed: {e}")
        raise RuntimeError(f"Startup credential validation failed: {e}")


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize storage clients and MCP validation on startup."""
    global neo4j_client, qdrant_client, kv_store, dashboard
    
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

    # Validate and retrieve all credentials securely
    credentials = validate_startup_credentials()

    try:
        # Initialize Neo4j (allow graceful degradation if unavailable)
        if credentials['neo4j_password']:
            try:
                neo4j_client = Neo4jClient()
                neo4j_client.connect(
                    username=os.getenv("NEO4J_USER", "neo4j"), 
                    password=credentials['neo4j_password']
                )
                print("✅ Neo4j connected successfully")
            except Exception as neo4j_error:
                print(f"⚠️ Neo4j unavailable: {neo4j_error}")
                neo4j_client = None
        else:
            print("⚠️ NEO4J_PASSWORD not set - Neo4j will be unavailable")
            neo4j_client = None

        # Initialize Qdrant (allow graceful degradation if unavailable)
        try:
            qdrant_initializer = VectorDBInitializer()
            if qdrant_initializer.connect():
                # Auto-create collection if it doesn't exist
                try:
                    qdrant_initializer.create_collection(force=False)
                    print("✅ Qdrant collection verified/created")
                except Exception as collection_error:
                    print(f"⚠️ Qdrant collection setup failed: {collection_error}")
                
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
        
        # Initialize SimpleRedisClient as a direct bypass for scratchpad operations
        global simple_redis
        simple_redis = SimpleRedisClient()
        if simple_redis.connect(redis_password=redis_password):
            print("✅ SimpleRedisClient connected successfully (scratchpad bypass)")
        else:
            print("⚠️ SimpleRedisClient connection failed, scratchpad operations may fail")

        print("✅ Storage initialization completed (services may be degraded)")
        
        # Initialize dashboard monitoring if available
        if DASHBOARD_AVAILABLE:
            try:
                dashboard = UnifiedDashboard()
                
                # Set service clients for real health checks
                dashboard.set_service_clients(
                    neo4j_client=neo4j_client,
                    qdrant_client=qdrant_client,
                    redis_client=simple_redis
                )
                
                # Start background collection loop
                await dashboard.start_collection_loop()
                print("✅ Dashboard monitoring initialized with background collection")
            except Exception as e:
                print(f"⚠️ Dashboard initialization failed: {e}")
                dashboard = None
        else:
            print("⚠️ Dashboard monitoring not available")
        
        # Start metrics queue processor for request metrics
        if REQUEST_METRICS_AVAILABLE:
            try:
                metrics_collector = get_metrics_collector()
                await metrics_collector.start_queue_processor()
                print("✅ Metrics queue processor started - analytics will now track operations")
            except Exception as e:
                print(f"⚠️ Failed to start metrics queue processor: {e}")
                logger.warning(f"Metrics queue processor startup failed: {e}")
            
    except Exception as e:
        print(f"❌ Critical failure in storage initialization: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up storage clients and metrics on shutdown."""
    if neo4j_client:
        neo4j_client.close()
    if kv_store:
        kv_store.close()
    if dashboard:
        await dashboard.stop_collection_loop()
        await dashboard.shutdown()
    
    # Stop metrics queue processor
    if REQUEST_METRICS_AVAILABLE:
        try:
            metrics_collector = get_metrics_collector()
            await metrics_collector.stop_queue_processor()
            print("Metrics queue processor stopped")
        except Exception as e:
            logger.warning(f"Error stopping metrics queue processor: {e}")

    print("Storage clients, dashboard, and metrics closed")


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
    check_func: callable,
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


@app.get("/health/embeddings")
async def check_embeddings():
    """Detailed health check for embedding service."""
    try:
        from ..embedding import get_embedding_service
        
        service = await get_embedding_service()
        health_status = service.get_health_status()
        
        # Test embedding generation
        test_start = time.time()
        try:
            test_embedding = await service.generate_embedding("health check test")
            test_time = time.time() - test_start
            embedding_test = {
                "success": True,
                "dimensions": len(test_embedding),
                "generation_time_ms": round(test_time * 1000, 2)
            }
        except Exception as e:
            embedding_test = {
                "success": False,
                "error": str(e),
                "generation_time_ms": round((time.time() - test_start) * 1000, 2)
            }
        
        # Check dimension compatibility
        model_dims = health_status["model_dimensions"]
        target_dims = health_status["target_dimensions"]
        dimensions_compatible = model_dims > 0 and target_dims > 0
        
        # Determine overall status using enhanced health status
        service_status = health_status.get("status", "unhealthy")
        overall_healthy = (
            health_status["model_loaded"] and 
            embedding_test["success"] and
            dimensions_compatible and
            service_status in ["healthy", "warning"]  # Warning is still operational
        )
        
        # Use service status if it's more specific than binary healthy/unhealthy
        final_status = service_status if service_status in ["critical", "warning"] else ("healthy" if overall_healthy else "unhealthy")
        
        return {
            "status": final_status,
            "timestamp": time.time(),
            "service": health_status,
            "test": embedding_test,
            "compatibility": {
                "dimensions_compatible": dimensions_compatible,
                "padding_required": model_dims < target_dims if model_dims > 0 else False,
                "truncation_required": model_dims > target_dims if model_dims > 0 else False
            },
            "alerts": health_status.get("alerts", []),
            "recommendations": [
                "Monitor error rate and latency trends",
                "Ensure sentence-transformers dependency is installed",
                "Check model loading performance during startup"
            ]
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e),
            "service": {"model_loaded": False}
        }

@app.get("/health")
async def health() -> Dict[str, Any]:
    """
    Lightweight health check endpoint for Docker health checks.
    
    Returns basic server status without expensive backend queries.
    For detailed backend status, use /health/detailed endpoint.
    """
    startup_elapsed = time.time() - _server_startup_time
    
    return {
        "status": "healthy",
        "uptime_seconds": int(startup_elapsed),
        "timestamp": time.time(),
        "message": "Server is running - use /health/detailed for backend status"
    }


@app.get("/health/detailed")
async def health_detailed() -> Dict[str, Any]:
    """
    Detailed health check endpoint with backend connectivity tests.

    Returns comprehensive health status of the server and its dependencies.
    Implements 60-second grace period and 3-retry mechanism as per issue #1759.
    WARNING: This endpoint performs expensive backend queries - use sparingly.
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

    # Determine agent readiness based on core functionality
    agent_ready = (
        health_status["services"]["redis"] == "healthy" and  # Core KV storage required
        len([
            "store_context",
            "retrieve_context", 
            "query_graph",
            "update_scratchpad",
            "get_agent_state",
        ]) == 5  # All tools available
    )

    return {
        "label": "◎ Veris Memory",
        "version": "0.9.0",
        "protocol": "MCP-1.0",
        "agent_ready": agent_ready,
        "deps": {
            "qdrant": "ok" if health_status["services"]["qdrant"] == "healthy" else "error",
            "neo4j": "ok" if health_status["services"]["neo4j"] == "healthy" else "error",
            "redis": "ok" if health_status["services"]["redis"] == "healthy" else "error",
        },
        "dependencies": {
            "qdrant": health_status["services"]["qdrant"],
            "neo4j": health_status["services"]["neo4j"], 
            "redis": health_status["services"]["redis"],
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

        # Determine readiness level and score
        readiness_score = 0
        readiness_level = "BASIC"
        
        # Core functionality check (Redis + Tools)
        core_ready = status_info["agent_ready"]
        if core_ready:
            readiness_score += 40  # Base readiness
            readiness_level = "STANDARD"
        
        # All tools available
        if tools_available == 5:
            readiness_score += 30  # All tools available
            
        # Enhanced features (vector/graph search)
        enhanced_ready = (
            status_info["dependencies"]["qdrant"] == "healthy" and 
            status_info["dependencies"]["neo4j"] == "healthy"
        )
        if enhanced_ready:
            readiness_score += 20  # Enhanced search available
            readiness_level = "FULL"
            
        # Indexes accessible
        if index_info:
            readiness_score += 10  # Indexes accessible
            
        # Generate clear, actionable recommendations
        recommendations = []
        if not core_ready:
            recommendations.extend([
                "CRITICAL: Redis connection required for core operations",
                "Check Redis configuration and network connectivity"
            ])
        elif tools_available < 5:
            recommendations.append(f"WARNING: Only {tools_available}/5 tools available")
        else:
            recommendations.append("✓ Core functionality operational")
            
        if not enhanced_ready:
            missing_services = []
            if status_info["dependencies"]["qdrant"] != "healthy":
                missing_services.append("Qdrant (vector search)")
            if status_info["dependencies"]["neo4j"] != "healthy":
                missing_services.append("Neo4j (graph queries)")
            
            if missing_services:
                recommendations.append(f"INFO: Enhanced features unavailable - {', '.join(missing_services)} not ready")
                recommendations.append("System can operate with basic functionality")

        return {
            "ready": core_ready,
            "readiness_level": readiness_level,  # NEW: Clear level indicator
            "readiness_score": min(readiness_score, 100),
            "tools_available": tools_available,
            "tools_expected": 5,
            "schema_version": schema_version,
            "protocol_version": "MCP-1.0",
            "indexes": index_info,
            "dependencies": status_info["dependencies"],
            "service_status": {  # NEW: Clear service breakdown
                "core_services": {
                    "redis": status_info["dependencies"]["redis"],
                    "status": "healthy" if core_ready else "degraded"
                },
                "enhanced_services": {
                    "qdrant": status_info["dependencies"]["qdrant"],
                    "neo4j": status_info["dependencies"]["neo4j"],
                    "status": "healthy" if enhanced_ready else "degraded"
                }
            },
            "usage_quotas": {
                "vector_operations": "unlimited" if enhanced_ready else "unavailable",
                "graph_queries": "unlimited" if enhanced_ready else "unavailable", 
                "kv_operations": "unlimited",
                "note": "Quotas depend on underlying database limits",
            },
            "recommended_actions": recommendations,
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

        context_id = str(uuid.uuid4())

        # Store in vector database
        vector_id = None
        if qdrant_client:
            try:
                logger.info("Generating embedding for vector storage using robust embedding service...")
                # Use new robust embedding service with comprehensive error handling
                from ..embedding import generate_embedding
                try:
                    embedding = await generate_embedding(request.content, adjust_dimensions=True)
                    logger.info(f"Generated embedding with {len(embedding)} dimensions using robust service")
                except Exception as embedding_error:
                    logger.error(f"Robust embedding service failed: {embedding_error}")
                    # Fall back to legacy method if robust service fails
                    embedding = await _generate_embedding(request.content)
                    logger.warning("Used legacy embedding generation as fallback")

                logger.info("Storing vector in Qdrant...")
                vector_id = qdrant_client.store_vector(
                    vector_id=context_id,
                    embedding=embedding,
                    metadata={
                        "content": request.content,
                        "type": request.type,
                        "metadata": request.metadata,
                    }
                )
                logger.info(f"Successfully stored vector with ID: {vector_id}")
            except Exception as vector_error:
                logger.error(f"Vector storage failed: {vector_error}")
                # Continue with graph storage even if vector storage fails
                vector_id = None

        # Store in graph database
        graph_id = None
        if neo4j_client:
            try:
                logger.info("Storing context in Neo4j graph database...")
                # Flatten nested objects for Neo4j compatibility
                flattened_properties = {"id": context_id, "type": request.type}
                
                # Handle request.content safely - convert nested objects to JSON strings
                for key, value in request.content.items():
                    if isinstance(value, (dict, list)):
                        flattened_properties[f"{key}_json"] = json.dumps(value)
                    else:
                        flattened_properties[key] = value
                
                graph_id = neo4j_client.create_node(
                    labels=["Context"],
                    properties=flattened_properties,
                )
                logger.info(f"Successfully created graph node with ID: {graph_id}")

                # Create relationships if specified
                if request.relationships:
                    for rel in request.relationships:
                        neo4j_client.create_relationship(
                            from_id=graph_id, to_id=rel["target"], rel_type=rel["type"]
                        )
                    logger.info(f"Created {len(request.relationships)} relationships")
            except Exception as graph_error:
                logger.error(f"Graph storage failed: {graph_error}")
                # Continue even if graph storage fails
                graph_id = None

        return {
            "success": True,
            "id": context_id,
            "vector_id": vector_id,
            "graph_id": graph_id,
            "message": "Context stored successfully",
        }

    except Exception as e:
        import traceback
        
        # Log detailed error information securely (internal only)
        logger.error(f"Error storing context: {traceback.format_exc()}")
        
        # Return sanitized error response (external)
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
            # Perform vector search using semantic embeddings
            try:
                # Generate semantic embedding for query using robust service
                from ..embedding import generate_embedding
                query_vector = await generate_embedding(request.query, adjust_dimensions=True)
                logger.info(f"Generated query embedding with {len(query_vector)} dimensions using robust service")

                vector_results = qdrant_client.search(
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
                logger.info(f"Vector search found {len(vector_results)} results")

            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                # Continue with other search modes

        if request.search_mode in ["graph", "hybrid"] and neo4j_client:
            # Perform graph search
            try:
                cypher_query = """
                MATCH (n:Context)
                WHERE n.type = $type OR $type = 'all'
                RETURN n
                LIMIT $limit
                """
                raw_graph_results = neo4j_client.query(
                    cypher_query, parameters={"type": request.type, "limit": request.limit}
                )
                
                # Normalize graph results to consistent format (eliminate nested 'n' structure)
                for raw_result in raw_graph_results:
                    if isinstance(raw_result, dict) and 'n' in raw_result:
                        # Extract the actual node data from {'n': {...}} wrapper
                        node_data = raw_result['n']
                    else:
                        # Handle direct node data
                        node_data = raw_result
                    
                    # Convert to consistent format matching vector results
                    normalized_result = {
                        "id": node_data.get("id", "unknown"),
                        "content": {
                            key: value for key, value in node_data.items() 
                            if key != "id"  # Don't duplicate id in content
                        },
                        "score": 1.0,  # Graph results don't have similarity scores
                        "source": "graph",
                    }
                    results.append(normalized_result)
                    
                logger.info(f"Graph search found {len(raw_graph_results)} results")
                
            except Exception as e:
                logger.warning(f"Graph search failed: {e}")
                # Continue with vector results only

        # Apply sorting based on sort_by parameter
        if request.sort_by == SortBy.TIMESTAMP:
            # Sort by timestamp (newest first)
            results.sort(key=lambda x: x.get("created_at", "") or "", reverse=True)
            logger.info("Sorted results by timestamp (newest first)")
        elif request.sort_by == SortBy.RELEVANCE:
            # Sort by relevance score (highest first)
            results.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
            logger.info("Sorted results by relevance score (highest first)")

        return {
            "success": True,
            "results": results[: request.limit],
            "total_count": len(results),
            "search_mode_used": request.search_mode,
            "message": f"Found {len(results)} matching contexts",
        }

    except Exception as e:
        import traceback
        
        # Log detailed error information securely (internal only)
        logger.error(f"Error retrieving context: {traceback.format_exc()}")
        
        # Return sanitized error response (external)
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
    # Additional runtime TTL validation for resource exhaustion prevention
    if request.ttl < 60:
        raise HTTPException(
            status_code=400,
            detail="TTL too short: minimum 60 seconds required to prevent resource exhaustion"
        )
    if request.ttl > 86400:  # 24 hours
        raise HTTPException(
            status_code=400,
            detail="TTL too long: maximum 86400 seconds (24 hours) allowed to prevent resource exhaustion"
        )
    
    # Additional content size validation for large payloads
    if len(request.content) > 100000:  # 100KB
        raise HTTPException(
            status_code=400,
            detail="Content too large: maximum 100KB allowed to prevent resource exhaustion"
        )
    
    # Validate request against MCP contract
    request_data = request.model_dump()
    validation_errors = validate_mcp_request("update_scratchpad", request_data)
    if validation_errors:
        logger.warning(f"MCP contract validation failed: {validation_errors}")
        # Continue processing - validation is for compliance monitoring
    
    try:
        # Use SimpleRedisClient for direct, reliable Redis access
        if not simple_redis:
            raise HTTPException(status_code=503, detail="Redis client not available")
        
        # Create namespaced key
        redis_key = f"scratchpad:{request.agent_id}:{request.key}"
        
        # Store value with TTL based on mode
        if request.mode == "append" and simple_redis.exists(redis_key):
            # Append mode: get existing content and append
            existing_content = simple_redis.get(redis_key) or ""
            content_str = f"{existing_content}\n{request.content}"
        else:
            # Overwrite mode or no existing content
            content_str = request.content
        
        try:
            # Use simple_redis for direct Redis access
            logger.info(f"Using SimpleRedisClient to store key: {redis_key}")
            success = simple_redis.set(redis_key, content_str, ex=request.ttl)
            logger.info(f"SimpleRedisClient.set() returned: {success}")
            
        except Exception as e:
            logger.error(f"SimpleRedisClient error: {type(e).__name__}: {e}")
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
        # Use SimpleRedisClient for direct, reliable Redis access
        if not simple_redis:
            raise HTTPException(status_code=503, detail="Redis client not available")
        
        # Build key pattern
        if request.key:
            redis_key = f"{request.prefix}:{request.agent_id}:{request.key}"
            try:
                logger.info(f"Using SimpleRedisClient to get key: {redis_key}")
                value = simple_redis.get(redis_key)
                logger.info(f"SimpleRedisClient.get() returned value: {value is not None}")
            except Exception as e:
                logger.error(f"SimpleRedisClient error: {type(e).__name__}: {e}")
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
                logger.info(f"Using SimpleRedisClient to get keys matching: {pattern}")
                keys = simple_redis.keys(pattern)
                logger.info(f"SimpleRedisClient.keys() found {len(keys)} keys")
            except Exception as e:
                logger.error(f"SimpleRedisClient error: {type(e).__name__}: {e}")
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
                value = simple_redis.get(key)
                
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


class RateLimiter:
    """Rate limiter for API endpoints to prevent DoS attacks."""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(lambda: deque())
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for the given client."""
        now = datetime.utcnow()
        cutoff_time = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        client_requests = self.requests[client_id]
        while client_requests and client_requests[0] < cutoff_time:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) >= self.max_requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True
    
    def get_reset_time(self, client_id: str) -> Optional[datetime]:
        """Get when the rate limit will reset for the client."""
        client_requests = self.requests[client_id]
        if not client_requests:
            return None
        return client_requests[0] + timedelta(seconds=self.window_seconds)


# Global rate limiters for different endpoint types
analytics_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)  # 5 req/min for analytics
dashboard_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)  # 20 req/min for dashboard


def get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting."""
    # Use X-Forwarded-For if behind proxy, fallback to direct IP
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    
    # Include user agent in client ID for better granularity
    user_agent = request.headers.get("user-agent", "")[:50]  # Limit length
    return f"{client_ip}:{hash(user_agent) % 10000}"


def check_rate_limit(rate_limiter: RateLimiter, request: Request) -> None:
    """Check rate limit and raise HTTPException if exceeded."""
    client_id = get_client_id(request)
    
    if not rate_limiter.is_allowed(client_id):
        reset_time = rate_limiter.get_reset_time(client_id)
        reset_seconds = int((reset_time - datetime.utcnow()).total_seconds()) if reset_time else 60
        
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after_seconds": reset_seconds,
                "max_requests": rate_limiter.max_requests,
                "window_seconds": rate_limiter.window_seconds
            },
            headers={"Retry-After": str(reset_seconds)}
        )


# Dashboard API Endpoints
@app.get("/api/dashboard")
async def get_dashboard_json(request: Request, include_trends: bool = False):
    """Get complete dashboard data in JSON format with optional trending data.
    
    Args:
        include_trends: Include 5-minute trending data for latency and error rates
    """
    # Apply rate limiting for dashboard endpoint
    check_rate_limit(dashboard_rate_limiter, request)
    
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    
    try:
        metrics = await dashboard.collect_all_metrics()
        response = {
            "success": True,
            "format": "json",
            "timestamp": time.time(),
            "data": metrics
        }
        
        # Add trending data if requested and available
        if include_trends and REQUEST_METRICS_AVAILABLE:
            try:
                request_collector = get_metrics_collector()
                trending_data = await request_collector.get_trending_data(minutes=5)
                endpoint_stats = await request_collector.get_endpoint_stats()
                
                response["analytics"] = {
                    "trending": {
                        "period_minutes": 5,
                        "data_points": trending_data,
                        "description": "Per-minute metrics for the last 5 minutes"
                    },
                    "endpoints": {
                        "top_endpoints": dict(list(endpoint_stats.items())[:10]),
                        "description": "Top 10 endpoints by request count"
                    }
                }
            except Exception as e:
                logger.debug(f"Could not get analytics data: {e}")
                
        return response
    except Exception as e:
        logger.error(f"Failed to get dashboard JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/analytics")
async def get_dashboard_analytics(request: Request, minutes: int = 5, include_insights: bool = True):
    """Get enhanced dashboard data with analytics and performance insights for AI agents.
    
    Args:
        minutes: Minutes of trending data to include (default: 5)
        include_insights: Include automated performance insights
    """
    # Apply rate limiting for analytics endpoint
    check_rate_limit(analytics_rate_limiter, request)
    
    # Input validation for minutes parameter
    if minutes <= 0 or minutes > 1440:  # Max 24 hours
        raise HTTPException(
            status_code=400, 
            detail="minutes parameter must be between 1 and 1440 (24 hours)"
        )
    
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    
    try:
        # Use the enhanced analytics dashboard method
        analytics_json = await dashboard.generate_json_dashboard_with_analytics(
            metrics=None, 
            include_trends=True, 
            minutes=minutes
        )
        
        # Parse the JSON to add metadata
        import json as json_module
        analytics_data = json_module.loads(analytics_json)
        
        response = {
            "success": True,
            "format": "json_analytics",
            "timestamp": time.time(),
            "analytics_window_minutes": minutes,
            "data": analytics_data
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get dashboard analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/ascii", response_class=PlainTextResponse)
async def get_dashboard_ascii() -> str:
    """Get dashboard in ASCII format for human reading.
    
    Returns:
        ASCII art string representation of dashboard metrics
    """
    if not dashboard:
        return "Dashboard Error: Dashboard not available"
    
    try:
        metrics = await dashboard.collect_all_metrics()
        ascii_output = dashboard.generate_ascii_dashboard(metrics)
        return ascii_output
    except Exception as e:
        logger.error(f"Failed to get dashboard ASCII: {e}")
        return f"Dashboard Error: {str(e)}"


@app.get("/api/dashboard/system")
async def get_system_metrics():
    """Get system metrics only."""
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    
    try:
        metrics = await dashboard.collect_all_metrics()
        return {
            "success": True,
            "type": "system_metrics",
            "timestamp": time.time(),
            "data": metrics.get("system", {})
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/services")
async def get_service_metrics():
    """Get service health metrics only."""
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    
    try:
        metrics = await dashboard.collect_all_metrics()
        return {
            "success": True,
            "type": "service_metrics",
            "timestamp": time.time(),
            "data": metrics.get("services", [])
        }
    except Exception as e:
        logger.error(f"Failed to get service metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/security")
async def get_security_metrics():
    """Get security metrics only."""
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    
    try:
        metrics = await dashboard.collect_all_metrics()
        return {
            "success": True,
            "type": "security_metrics",
            "timestamp": time.time(),
            "data": metrics.get("security", {})
        }
    except Exception as e:
        logger.error(f"Failed to get security metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboard/refresh")
async def refresh_dashboard():
    """Force refresh of dashboard metrics."""
    if not dashboard:
        raise HTTPException(status_code=503, detail="Dashboard not available")
    
    try:
        metrics = await dashboard.collect_all_metrics(force_refresh=True)
        
        # Broadcast update to all WebSocket connections
        await _broadcast_to_websockets({
            "type": "force_refresh",
            "timestamp": time.time(),
            "data": metrics
        })
        
        return {
            "success": True,
            "message": "Dashboard metrics refreshed",
            "timestamp": time.time(),
            "websocket_notifications_sent": len(websocket_connections)
        }
    except Exception as e:
        logger.error(f"Failed to refresh dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/health")
async def dashboard_health():
    """Dashboard API health check.
    
    Returns comprehensive health status of the dashboard system including:
    - Dashboard component health (requires active collection loop)
    - WebSocket connection health (under connection limits)
    
    The collection_running check is required because the dashboard is only
    considered healthy when actively collecting metrics from services.
    Without an active collection loop, metrics become stale and the
    dashboard cannot provide accurate real-time monitoring.
    """
    try:
        # Dashboard is healthy when: exists, has recent updates, and collection is active
        dashboard_exists = dashboard is not None
        has_recent_update = dashboard.last_update is not None if dashboard_exists else False
        
        # Check collection status with timeout protection
        collection_running = False
        if dashboard_exists:
            try:
                # Add timeout protection for collection status check
                collection_running = getattr(dashboard, '_collection_running', False)
                
                # Additional health check: verify last update is recent (within 2 minutes)
                if has_recent_update and dashboard.last_update:
                    time_since_update = (datetime.utcnow() - dashboard.last_update).total_seconds()
                    if time_since_update > 120:  # 2 minutes
                        logger.warning(f"Dashboard last update was {time_since_update:.1f}s ago")
                        has_recent_update = False
                        
            except Exception as e:
                logger.error(f"Error checking dashboard collection status: {e}")
                collection_running = False
        
        dashboard_healthy = dashboard_exists and has_recent_update and collection_running
        websocket_healthy = len(websocket_connections) <= 100  # Max connections
        overall_healthy = dashboard_healthy and websocket_healthy
        
        return {
            "success": True,
            "healthy": overall_healthy,
            "timestamp": time.time(),
            "components": {
                "dashboard": {
                    "healthy": dashboard_healthy,
                    "collection_running": getattr(dashboard, '_collection_running', False) if dashboard else False,
                    "last_update": dashboard.last_update.isoformat() if dashboard and dashboard.last_update else None
                },
                "websockets": {
                    "healthy": websocket_healthy,
                    "active_connections": len(websocket_connections),
                    "max_connections": 100
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get API health: {e}")
        return {
            "success": False,
            "healthy": False,
            "error": str(e),
            "timestamp": time.time()
        }


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard streaming."""
    await websocket.accept()
    websocket_connections.add(websocket)
    
    try:
        logger.info(f"WebSocket connected ({len(websocket_connections)} total)")
        
        if len(websocket_connections) > 100:  # Max connections
            await websocket.close(code=1008, reason="Max connections exceeded")
            return

        # Send initial dashboard data
        if dashboard:
            metrics = await dashboard.collect_all_metrics(force_refresh=True)
            await websocket.send_json({
                "type": "initial_data",
                "timestamp": time.time(),
                "data": metrics
            })

        # Start streaming updates
        await _stream_dashboard_updates(websocket)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")
    finally:
        websocket_connections.discard(websocket)


async def _stream_dashboard_updates(websocket: WebSocket):
    """Stream dashboard updates to WebSocket client."""
    update_interval = 5  # seconds
    heartbeat_interval = 30  # seconds
    
    last_heartbeat = time.time()
    
    try:
        while True:
            if dashboard:
                # Collect current metrics
                metrics = await dashboard.collect_all_metrics()
                
                # Send update
                update_message = {
                    "type": "dashboard_update",
                    "timestamp": time.time(),
                    "data": metrics
                }
                
                await websocket.send_json(update_message)
                
                # Send heartbeat if needed
                now = time.time()
                if (now - last_heartbeat) >= heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": now
                    })
                    last_heartbeat = now
            
            # Wait for next update
            await asyncio.sleep(update_interval)
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected during streaming")
    except Exception as e:
        logger.error(f"Streaming error: {e}")


async def _broadcast_to_websockets(message: Dict[str, Any]) -> None:
    """Broadcast message to all connected WebSocket clients.
    
    Args:
        message: Dictionary containing the message data to broadcast
    """
    if not websocket_connections:
        return
    
    # Create list of connections to avoid modification during iteration
    connections = list(websocket_connections)
    
    for websocket in connections:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            # Remove failed connection
            websocket_connections.discard(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MCP_SERVER_PORT", 8000)))
