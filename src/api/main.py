#!/usr/bin/env python3
"""
Veris Memory REST API Server

Production-grade FastAPI server with comprehensive error handling,
OpenAPI documentation, validation, and observability features.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

# API routes
from .routes import search, health, metrics
from .middleware import ErrorHandlerMiddleware, ValidationMiddleware, LoggingMiddleware
from .models import ErrorResponse
from .dependencies import set_query_dispatcher, get_query_dispatcher

# Core components  
from ..core.query_dispatcher import QueryDispatcher
from ..utils.logging_middleware import api_logger

# Configuration
API_TITLE = "Veris Memory API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
# Veris Memory Context Storage & Retrieval API

A production-grade context storage and retrieval system with:

- **Hybrid Search**: Vector, graph, and key-value search across multiple backends
- **Intelligent Ranking**: Pluggable ranking policies (default, code-boost, recency)  
- **Advanced Filtering**: Time windows, tags, content types, and custom filters
- **Query Orchestration**: Multi-backend dispatch with parallel, sequential, and fallback policies
- **Comprehensive Observability**: Structured logging, metrics, and health monitoring

## Authentication

API endpoints require valid authentication tokens. Include the token in the Authorization header:

```
Authorization: Bearer <your-token>
```

## Rate Limiting

API requests are rate-limited per client. Default limits:
- 1000 requests per hour for authenticated users
- 100 requests per hour for unauthenticated requests

## Error Handling

All errors return structured responses with detailed error information:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameters", 
    "details": {...},
    "trace_id": "req-123-abc"
  }
}
```
"""

# Global components are now managed in dependencies.py


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    
    api_logger.info("Starting Veris Memory API server")
    
    try:
        # Initialize query dispatcher and backends
        dispatcher = QueryDispatcher()
        
        # Initialize backends using real backend initialization (same pattern as MCP server)
        import os
        api_logger.info("Initializing real backends for API service")
        
        # Import backend clients and configuration (same as MCP server)
        from ..storage.qdrant_client import VectorDBInitializer
        from ..storage.neo4j_client import Neo4jInitializer as Neo4jClient
        from ..storage.kv_store import ContextKV as KVStore
        from ..core.ssl_config import SSLConfigManager
        from ..validators.config_validator import validate_all_configs
        import urllib.parse
        
        vector_backend = None
        graph_backend = None
        kv_backend = None
        
        # Initialize configuration validation (same as MCP server)
        try:
            config_result = validate_all_configs()
            base_config = config_result.get("config", {})
            if not config_result.get("valid", False):
            api_logger.warning(f"⚠️ Configuration validation failed: {config_result}")
        
            # Initialize SSL configuration manager
            ssl_manager = SSLConfigManager(base_config)
            
            # Validate SSL certificates if configured
            ssl_validation = ssl_manager.validate_ssl_certificates()
            for backend, valid in ssl_validation.items():
            if not valid:
                api_logger.warning(f"⚠️ SSL certificate validation failed for {backend}")
                
        except Exception as config_error:
            api_logger.warning(f"⚠️ Configuration setup failed: {config_error}")
            ssl_manager = None
        
        # Initialize Neo4j with proper configuration (EXACT MCP pattern)
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if neo4j_password:
            try:
                # Get Neo4j URI from environment
                neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
                neo4j_username = os.getenv("NEO4J_USER", "neo4j")
                
                # Parse URI to extract host and port
                parsed = urllib.parse.urlparse(neo4j_uri)
                neo4j_host = parsed.hostname or "localhost"
                neo4j_port = parsed.port or 7687
                
                # Create config for Neo4jInitializer (EXACT MCP pattern)
                neo4j_config = {
                    "neo4j": {
                        "host": neo4j_host,
                        "port": neo4j_port,
                        "database": "neo4j",
                        "ssl": neo4j_uri.startswith("bolt+s") or neo4j_uri.startswith("neo4j+s")
                    }
                }
                
                neo4j_client = Neo4jClient(config=neo4j_config)
                if ssl_manager:
                    neo4j_ssl_config = ssl_manager.get_neo4j_ssl_config()
                
                # Neo4j.connect only accepts username and password
                # SSL config is handled internally by Neo4j client
                if neo4j_client.connect(username=neo4j_username, password=neo4j_password):
                    ssl_status = "with SSL" if ssl_manager and ssl_manager.get_neo4j_ssl_config().get("encrypted") else "without SSL"
                    api_logger.info(f"✅ API: Neo4j connected at {neo4j_uri} {ssl_status}")
                    graph_backend = neo4j_client
                else:
                    api_logger.warning(f"⚠️ API: Neo4j connection failed at {neo4j_uri}")
            except Exception as e:
                api_logger.warning(f"⚠️ API: Neo4j initialization error: {e}")
        else:
            api_logger.warning("⚠️ API: Neo4j disabled - NEO4J_PASSWORD not set")
        
        # Initialize Qdrant with proper configuration (EXACT MCP pattern)
        qdrant_url = os.getenv("QDRANT_URL")
        if qdrant_url:
            try:
                # Parse Qdrant URL to extract host and port
                parsed_qdrant = urllib.parse.urlparse(qdrant_url)
                qdrant_host = parsed_qdrant.hostname or "localhost"
                qdrant_port = parsed_qdrant.port or 6333
                
                # Create config for VectorDBInitializer (EXACT MCP pattern)
                qdrant_config = {
                    "qdrant": {
                        "host": qdrant_host,
                        "port": qdrant_port,
                        "ssl": qdrant_url.startswith("https"),
                        "timeout": 5
                    }
                }
                
                qdrant_client = VectorDBInitializer(config=qdrant_config)
                if ssl_manager:
                    qdrant_ssl_config = ssl_manager.get_qdrant_ssl_config()
                
                if qdrant_client.connect():
                    ssl_status = "with HTTPS" if ssl_manager and ssl_manager.get_qdrant_ssl_config().get("https") else "without SSL"
                    api_logger.info(f"✅ API: Qdrant connected at {qdrant_url} {ssl_status}")
                    vector_backend = qdrant_client
                else:
                    api_logger.warning(f"⚠️ API: Qdrant connection failed at {qdrant_url}")
            except Exception as e:
                api_logger.warning(f"⚠️ API: Qdrant initialization error: {e}")
        else:
            api_logger.warning("⚠️ API: Qdrant disabled - QDRANT_URL not set")
        
        # Initialize KV Store with proper configuration (EXACT MCP pattern)
        redis_url = os.getenv("REDIS_URL")
        redis_password = os.getenv("REDIS_PASSWORD")
        if redis_url:
            try:
                # Parse Redis URL to extract host and port
                parsed_redis = urllib.parse.urlparse(redis_url)
                redis_host = parsed_redis.hostname or "localhost"
                redis_port = parsed_redis.port or 6379
                
                # Create config for ContextKV (EXACT MCP pattern)
                redis_config = {
                    "redis": {
                        "host": redis_host,
                        "port": redis_port,
                        "database": 0,
                        "ssl": redis_url.startswith("rediss")
                    }
                }
                
                kv_store_client = KVStore(config=redis_config)
                if ssl_manager:
                    redis_ssl_config = ssl_manager.get_redis_ssl_config()
                
                # Pass password if available
                if kv_store_client.connect(redis_password=redis_password):
                    ssl_status = "with SSL" if ssl_manager and ssl_manager.get_redis_ssl_config().get("ssl") else "without SSL"
                    api_logger.info(f"✅ API: Redis connected at {redis_url} {ssl_status}")
                    kv_backend = kv_store_client
                else:
                    api_logger.warning(f"⚠️ API: Redis connection failed at {redis_url}")
            except Exception as e:
                api_logger.warning(f"⚠️ API: Redis initialization error: {e}")
        else:
            api_logger.warning("⚠️ API: Redis disabled - REDIS_URL not set")
        
        # Log backend connection status without failing startup
        missing_backends = []
        if not vector_backend:
            missing_backends.append("Qdrant")
        if not graph_backend:
            missing_backends.append("Neo4j")
        if not kv_backend:
            missing_backends.append("Redis")
        
        if missing_backends:
            api_logger.warning(f"⚠️ API: Real backends failed: {missing_backends}. API will start in degraded mode.")
            api_logger.warning("⚠️ API: Some search functionality may be limited until backends are available.")
            # Don't fall back to mock backends - they caused 98.8% failure rate
            # Instead, allow API to start and handle missing backends gracefully via health checks
        else:
            api_logger.info("✅ API: All real backends connected successfully")
        
        # Register backends with dispatcher (only register available backends)
        backends_registered = []
        if vector_backend:
            dispatcher.register_backend("vector", vector_backend)
            backends_registered.append("vector")
        if graph_backend:
            dispatcher.register_backend("graph", graph_backend)
            backends_registered.append("graph")
        if kv_backend:
            dispatcher.register_backend("kv", kv_backend)
            backends_registered.append("kv")
        
        if not backends_registered:
            api_logger.warning("⚠️ API: No backends available during startup - API will start in degraded mode")
        else:
            api_logger.info(f"✅ API: Registered backends: {backends_registered}")
        
        # Set global dispatcher
        set_query_dispatcher(dispatcher)
        
        api_logger.info(
            "Query dispatcher initialized",
            backends=dispatcher.list_backends(),
            ranking_policies=dispatcher.get_available_ranking_policies()
        )
        
        yield
        
    except Exception as e:
        api_logger.error("Failed to initialize API components", error=str(e))
        raise
    finally:
        # Cleanup
        api_logger.info("Shutting down Veris Memory API server")
        # Perform any cleanup if needed


def create_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Create enhanced OpenAPI schema with additional metadata."""
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=[
            {
                "name": "search",
                "description": "Context search and retrieval operations"
            },
            {
                "name": "health", 
                "description": "Health check and system status endpoints"
            },
            {
                "name": "metrics",
                "description": "Performance metrics and observability"
            }
        ]
    )
    
    # Add additional schema information
    openapi_schema["info"]["contact"] = {
        "name": "Veris Memory API Support",
        "email": "support@veris-memory.com"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add server information
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.veris-memory.com",
            "description": "Production server"
        }
    ]
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Apply security to all endpoints by default
    for path_item in openapi_schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "security" not in operation:
                operation["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc", 
        openapi_url="/openapi.json"
    )
    
    # Security middleware
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Configure appropriately for production
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Custom middleware (applied in reverse order)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(ValidationMiddleware) 
    app.add_middleware(LoggingMiddleware)
    
    # Include routers
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
    
    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """API root endpoint with basic information."""
        return {
            "name": API_TITLE,
            "version": API_VERSION,
            "status": "operational",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    
    # Custom OpenAPI schema
    app.openapi = lambda: create_openapi_schema(app)
    
    return app


# Application instance
app = create_app()


# get_query_dispatcher is now in dependencies.py


if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )