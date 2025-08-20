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
from ..backends.vector_backend import VectorBackend
from ..backends.graph_backend import GraphBackend
from ..backends.kv_backend import KVBackend
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
        
        # Initialize and register backends
        # Note: Using Docker service names for container deployment
        import os
        
        vector_backend = VectorBackend(
            url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
            collection_name="context_embeddings"
        )
        
        graph_backend = GraphBackend(
            url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            username=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        
        kv_backend = KVBackend(
            url=os.getenv("REDIS_URL", "redis://redis:6379"),
            db=0
        )
        
        # Register backends with dispatcher
        dispatcher.register_backend("vector", vector_backend)
        dispatcher.register_backend("graph", graph_backend) 
        dispatcher.register_backend("kv", kv_backend)
        
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