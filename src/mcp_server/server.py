#!/usr/bin/env python3
"""
Context Store MCP Server using the official MCP Python SDK.

This module implements the Model Context Protocol server for the context store
using the official MCP Python SDK for proper protocol compliance.
"""
# flake8: noqa: E501

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence

# MCP SDK imports
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import EmbeddedResource, ImageContent, Resource, TextContent, Tool

# Storage client imports
try:
    from core.config import Config

    from ..core.agent_namespace import AgentNamespace
    from ..core.embedding_config import create_embedding_generator

    # Unused import removed: from ..core.query_validator import validate_cypher_query
    from ..core.rate_limiter import rate_limit_check
    from ..core.ssl_config import SSLConfigManager
    from ..security.cypher_validator import CypherValidator
    from ..storage.kv_store import ContextKV
    from ..storage.neo4j_client import Neo4jInitializer
    from ..storage.qdrant_client import VectorDBInitializer
    from ..storage.reranker import get_reranker
    from ..validators.config_validator import validate_all_configs
except ImportError:
    # Fallback for different import contexts
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.agent_namespace import AgentNamespace
    from core.config import Config
    from core.embedding_config import create_embedding_generator
    from core.rate_limiter import rate_limit_check
    from core.ssl_config import SSLConfigManager
    from security.cypher_validator import CypherValidator
    from storage.kv_store import ContextKV
    from storage.neo4j_client import Neo4jInitializer
    from storage.qdrant_client import VectorDBInitializer
    from storage.reranker import get_reranker
    from validators.config_validator import validate_all_configs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("context-store")

# Global storage client instances
neo4j_client = None
qdrant_client = None
kv_store = None
embedding_generator = None

# Global security and namespace instances
cypher_validator = CypherValidator()
agent_namespace = AgentNamespace()

# Tool selector bridge import
try:
    from .tool_selector_bridge import get_tool_selector_bridge

    tool_selector_bridge = get_tool_selector_bridge()
except ImportError as e:
    logger.warning(f"Tool selector bridge not available: {e}")
    tool_selector_bridge = None


async def initialize_storage_clients() -> Dict[str, Any]:
    """Initialize storage clients with SSL/TLS support."""
    global neo4j_client, qdrant_client, kv_store, embedding_generator

    try:
        # Validate configuration
        config_result = validate_all_configs()
        base_config = config_result.get("config", {})

        if not config_result.get("valid", False):
            logger.warning(f"⚠️ Configuration validation failed: {config_result}")
            # Continue with initialization even if validation fails for missing optional configs

        # Initialize SSL configuration manager
        ssl_manager = SSLConfigManager(base_config)

        # Validate SSL certificates if configured
        ssl_validation = ssl_manager.validate_ssl_certificates()
        for backend, valid in ssl_validation.items():
            if not valid:
                logger.warning(f"⚠️ SSL certificate validation failed for {backend}")

        # Initialize Neo4j with SSL support
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if neo4j_password:
            neo4j_client = Neo4jInitializer()
            neo4j_username = os.getenv("NEO4J_USER", "neo4j")
            neo4j_ssl_config = ssl_manager.get_neo4j_ssl_config()

            # Merge SSL config into connection parameters
            connect_kwargs = {"username": neo4j_username, "password": neo4j_password}
            connect_kwargs.update(neo4j_ssl_config)

            if neo4j_client.connect(**connect_kwargs):
                ssl_status = "with SSL" if neo4j_ssl_config.get("encrypted") else "without SSL"
                logger.info(f"✅ Neo4j client initialized {ssl_status}")
            else:
                neo4j_client = None
                logger.warning("⚠️ Neo4j connection failed")
        else:
            neo4j_client = None
            logger.warning("⚠️ Neo4j disabled: NEO4J_PASSWORD not set")

        # Initialize Qdrant with SSL support
        qdrant_url = os.getenv("QDRANT_URL")
        if qdrant_url:
            qdrant_client = VectorDBInitializer()
            qdrant_ssl_config = ssl_manager.get_qdrant_ssl_config()

            if qdrant_client.connect(**qdrant_ssl_config):
                ssl_status = "with HTTPS" if qdrant_ssl_config.get("https") else "without SSL"
                logger.info(f"✅ Qdrant client initialized {ssl_status}")
            else:
                qdrant_client = None
                logger.warning("⚠️ Qdrant connection failed")
        else:
            qdrant_client = None
            logger.warning("⚠️ Qdrant disabled: QDRANT_URL not set")

        # Initialize KV Store with SSL support
        redis_url = os.getenv("REDIS_URL")
        redis_password = os.getenv("REDIS_PASSWORD")
        if redis_url:
            kv_store = ContextKV()
            redis_ssl_config = ssl_manager.get_redis_ssl_config()

            # Merge SSL config with password
            connect_kwargs = {"redis_password": redis_password}
            connect_kwargs.update(redis_ssl_config)

            if kv_store.connect(**connect_kwargs):
                ssl_status = "with SSL" if redis_ssl_config.get("ssl") else "without SSL"
                logger.info(f"✅ KV store initialized {ssl_status}")
            else:
                kv_store = None
                logger.warning("⚠️ KV store connection failed")
        else:
            kv_store = None
            logger.warning("⚠️ KV store disabled: REDIS_URL not set")

        # Initialize embedding generator
        try:
            embedding_generator = await create_embedding_generator(base_config)
            logger.info("✅ Embedding generator initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize embedding generator: {e}")
            embedding_generator = None

        logger.info("✅ Storage clients initialization completed")

        return {
            "success": True,
            "neo4j_initialized": neo4j_client is not None,
            "qdrant_initialized": qdrant_client is not None,
            "kv_store_initialized": kv_store is not None,
            "embedding_initialized": embedding_generator is not None,
            "message": "Storage clients initialized successfully",
        }

    except Exception as e:
        logger.error(f"❌ Failed to initialize storage clients: {e}")
        # Don't raise to allow server to start with partial functionality
        neo4j_client = None
        qdrant_client = None
        kv_store = None
        embedding_generator = None

        return {
            "success": False,
            "neo4j_initialized": False,
            "qdrant_initialized": False,
            "kv_store_initialized": False,
            "embedding_initialized": False,
            "message": f"Failed to initialize storage clients: {str(e)}",
        }


async def cleanup_storage_clients() -> None:
    """Clean up storage clients."""
    global neo4j_client, qdrant_client, kv_store

    if neo4j_client:
        neo4j_client.close()
        logger.info("Neo4j client closed")

    if kv_store:
        kv_store.close()
        logger.info("KV store closed")

    # Qdrant VectorDBInitializer doesn't have a close method in the current implementation
    # but we set it to None for cleanup
    if qdrant_client:
        qdrant_client = None
        logger.info("Qdrant client cleaned up")

    logger.info("Storage clients cleaned up")


@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="context://health",
            name="Health Status",
            description="Server and service health status",
            mimeType="application/json",
        ),
        Resource(
            uri="context://tools",
            name="Available Tools",
            description="List of available MCP tools",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read resource content."""
    if uri == "context://health":
        health_status = await get_health_status()
        return json.dumps(health_status, indent=2)

    elif uri == "context://tools":
        tools_info = await get_tools_info()
        return json.dumps(tools_info, indent=2)

    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="store_context",
            description="Store context data with vector embeddings and graph relationships",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "object",
                        "description": "Context content to store",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["design", "decision", "trace", "sprint", "log"],
                        "description": "Type of context",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata",
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string"},
                                "type": {"type": "string"},
                            },
                        },
                        "description": "Graph relationships to create",
                    },
                },
                "required": ["content", "type"],
            },
        ),
        Tool(
            name="retrieve_context",
            description="Retrieve context using hybrid vector and graph search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "type": {
                        "type": "string",
                        "default": "all",
                        "description": "Context type filter",
                    },
                    "search_mode": {
                        "type": "string",
                        "enum": ["vector", "graph", "hybrid"],
                        "default": "hybrid",
                        "description": "Search strategy",
                    },
                    "retrieval_mode": {
                        "type": "string",
                        "enum": ["vector", "graph", "hybrid"],
                        "default": "hybrid",
                        "description": "Retrieval mode for hybrid vector and graph search",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum results to return",
                    },
                    "max_hops": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 2,
                        "description": "Maximum hops for graph traversal",
                    },
                    "relationship_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter relationships by type (e.g., ['LINK', 'REFERENCES'])",
                    },
                    "include_reasoning_path": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include reasoning path in results",
                    },
                    "enable_community_detection": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include community detection results",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_graph",
            description="Execute read-only Cypher queries on the graph database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cypher query (read-only)",
                    },
                    "parameters": {"type": "object", "description": "Query parameters"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "default": 100,
                        "description": "Maximum results to return",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="update_scratchpad",
            description="Update agent scratchpad with transient storage and TTL support",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "key": {"type": "string", "description": "Scratchpad data key (not secret)"},
                    "content": {"type": "string", "description": "Content to store"},
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "default": "overwrite",
                        "description": "Update mode",
                    },
                    "ttl": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 86400,
                        "default": 3600,
                        "description": "Time to live in seconds (1 hour default)",
                    },
                },
                "required": ["agent_id", "key", "content"],
            },
        ),
        Tool(
            name="get_agent_state",
            description="Retrieve agent state with namespace isolation",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "key": {
                        "type": "string",
                        "description": "State data key (optional for all, not secret)",
                    },
                    "prefix": {
                        "type": "string",
                        "enum": ["state", "scratchpad", "memory", "config"],
                        "default": "state",
                        "description": "State type to retrieve",
                    },
                },
                "required": ["agent_id"],
            },
        ),
        Tool(
            name="detect_communities",
            description="Detect communities in the knowledge graph using GraphRAG",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm": {
                        "type": "string",
                        "enum": ["louvain", "leiden", "modularity"],
                        "default": "louvain",
                        "description": "Community detection algorithm",
                    },
                    "min_community_size": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 50,
                        "default": 3,
                        "description": "Minimum size for communities",
                    },
                    "resolution": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 2.0,
                        "default": 1.0,
                        "description": "Resolution parameter for community detection",
                    },
                    "include_members": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include community member details",
                    },
                },
            },
        ),
        Tool(
            name="select_tools",
            description="Select relevant tools based on query using multiple selection algorithms",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or context description for tool selection",
                    },
                    "max_tools": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5,
                        "description": "Maximum number of tools to return (≤ N)",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["dot_product", "rule_based", "hybrid"],
                        "default": "hybrid",
                        "description": "Selection method to use",
                    },
                    "category_filter": {
                        "type": "string",
                        "description": "Filter tools by category (optional)",
                    },
                    "include_scores": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include relevance scores in response",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_available_tools",
            description="List all available tools in the tool selector system",
            inputSchema={
                "type": "object",
                "properties": {
                    "category_filter": {
                        "type": "string",
                        "description": "Filter tools by category (optional)",
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include tool metadata in response",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["name", "category", "keywords"],
                        "default": "name",
                        "description": "Sort tools by specified field",
                    },
                },
            },
        ),
        Tool(
            name="get_tool_info",
            description="Get detailed information about a specific tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to get information about",
                    },
                    "include_usage_examples": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include usage examples if available",
                    },
                },
                "required": ["tool_name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: Dict[str, Any]
) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    if name == "store_context":
        result = await store_context_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "retrieve_context":
        result = await retrieve_context_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "query_graph":
        result = await query_graph_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_scratchpad":
        result = await update_scratchpad_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_agent_state":
        result = await get_agent_state_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "detect_communities":
        result = await detect_communities_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "select_tools":
        result = await select_tools_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "list_available_tools":
        result = await list_available_tools_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_tool_info":
        result = await get_tool_info_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def store_context_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Store context data with vector embeddings and graph relationships.

    This function stores context data in both vector and graph databases,
    creating embeddings for semantic search and establishing relationships
    for graph traversal. It supports graceful degradation when storage
    backends are unavailable.

    Args:
        arguments: Dictionary containing:
            - content (dict): The context content to store (required)
            - type (str): Context type - one of 'design', 'decision', 'trace', 'sprint', 'log'
            - metadata (dict, optional): Additional metadata for the context
            - relationships (list, optional): List of graph relationships to create
                Each relationship should have 'type' and 'target' keys

    Returns:
        Dict containing:
            - success (bool): Whether the operation succeeded
            - id (str): Unique identifier for the stored context
            - vector_id (str, optional): Vector database ID if stored
            - graph_id (str, optional): Graph database node ID if stored
            - message (str): Success or error message
            - validation_errors (list, optional): Any validation errors

    Example:
        >>> arguments = {
        ...     "content": {"title": "API Design", "description": "REST API specification"},
        ...     "type": "design",
        ...     "metadata": {"author": "developer", "priority": "high"},
        ...     "relationships": [{"type": "implements", "target": "req-001"}]
        ... }
        >>> result = await store_context_tool(arguments)
        >>> print(result["success"])  # True
        >>> print(result["id"])       # ctx_abc123...
    """
    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("store_context")
    if not allowed:
        return {
            "success": False,
            "id": None,
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        # Generate unique ID
        import uuid

        context_id = f"ctx_{uuid.uuid4().hex[:12]}"

        content = arguments["content"]
        context_type = arguments["type"]
        metadata = arguments.get("metadata", {})
        relationships = arguments.get("relationships", [])

        # Store in vector database
        vector_id = None
        if qdrant_client and qdrant_client.client:
            try:
                from qdrant_client.models import PointStruct

                # Generate proper semantic embedding from content
                content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
                if embedding_generator:
                    embedding = await embedding_generator.generate_embedding(content_str)
                    logger.info("Generated semantic embedding using configured model")
                else:
                    # Fallback to improved hash-based embedding for development
                    logger.warning("No embedding generator available, using fallback method")
                    import hashlib

                    hash_obj = hashlib.sha256(content_str.encode())
                    hash_bytes = hash_obj.digest()

                    # Get dimensions from Qdrant config or default
                    dimensions = qdrant_client.config.get("qdrant", {}).get(
                        "dimensions", Config.EMBEDDING_DIMENSIONS
                    )
                    embedding = []
                    for i in range(dimensions):
                        byte_idx = i % len(hash_bytes)
                        # Normalize to [-1, 1] for better vector space properties
                        normalized_value = (float(hash_bytes[byte_idx]) / 255.0) * 2.0 - 1.0
                        embedding.append(normalized_value)

                # Use the collection name from config or default
                collection_name = qdrant_client.config.get("qdrant", {}).get(
                    "collection_name", "project_context"
                )

                # Store the vector using VectorDBInitializer.store_vector method
                vector_metadata = {
                    "content": content,
                    "type": context_type,
                    "metadata": metadata,
                }
                qdrant_client.store_vector(
                    vector_id=context_id,
                    embedding=embedding,
                    metadata=vector_metadata,
                )
                vector_id = context_id
                logger.info(f"Stored vector with ID: {vector_id}")
            except Exception as e:
                logger.error(f"Failed to store vector: {e}")
                vector_id = None

        # Store in graph database
        graph_id = None
        if neo4j_client and neo4j_client.driver:
            try:
                with neo4j_client.driver.session(database=neo4j_client.database) as session:
                    # Create context node
                    create_query = """
                    CREATE (c:Context {
                        id: $id,
                        type: $type,
                        content: $content,
                        metadata: $metadata,
                        created_at: datetime()
                    })
                    RETURN c.id as node_id
                    """
                    result = session.run(
                        create_query,
                        id=context_id,
                        type=context_type,
                        content=json.dumps(content),
                        metadata=json.dumps(metadata),
                    )
                    record = result.single()
                    if record:
                        graph_id = record["node_id"]
                        logger.info(f"Created graph node with ID: {graph_id}")

                        # Create relationships if specified
                        for rel in relationships:
                            try:
                                rel_query = """
                                MATCH (a:Context {id: $from_id})
                                MATCH (b:Context {id: $to_id})
                                CREATE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
                                RETURN r
                                """
                                session.run(
                                    rel_query,
                                    from_id=context_id,
                                    to_id=rel["target"],
                                    rel_type=rel["type"],
                                )
                                logger.info(
                                    f"Created relationship: {context_id} -> "
                                    f"{rel['target']} ({rel['type']})"
                                )
                            except Exception as rel_e:
                                logger.warning(f"Failed to create relationship: {rel_e}")
            except Exception as e:
                logger.error(f"Failed to store in graph database: {e}")
                graph_id = None

        # Build success message with backend status
        backend_status = []
        if vector_id:
            backend_status.append("vector")
        if graph_id:
            backend_status.append("graph")

        if not backend_status:
            message = "Context stored with fallback (no backends available)"
        elif len(backend_status) == 2:
            message = "Context stored successfully in all backends"
        else:
            available = ", ".join(backend_status)
            failed = "graph" if vector_id and not graph_id else "vector"
            message = (
                f"Context stored successfully in {available} (warning: {failed} backend failed)"
            )

        return {
            "success": True,
            "id": context_id,
            "vector_id": vector_id,
            "graph_id": graph_id,
            "message": message,
            "backend_status": {
                "vector": "success" if vector_id else "failed",
                "graph": "success" if graph_id else "failed",
            },
        }

    except Exception as e:
        logger.error(f"Error storing context: {e}")
        return {
            "success": False,
            "id": None,
            "message": f"Failed to store context: {str(e)}",
        }


async def retrieve_context_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve context using hybrid vector and graph search.

    This function performs semantic search across stored contexts using
    vector similarity and graph traversal. It supports multiple search modes
    and filters to find relevant context information.

    Args:
        arguments: Dictionary containing:
            - query (str): Search query text (required)
            - type (str, optional): Filter by context type ('design', 'decision', etc.)
                Default: 'all' (no filtering)
            - search_mode (str, optional): Search strategy - 'vector', 'graph', or 'hybrid'
                Default: 'hybrid'
            - retrieval_mode (str, optional): Retrieval mode for hybrid search - 'vector', 'graph', or 'hybrid'
                Default: 'hybrid'
            - limit (int, optional): Maximum number of results to return (1-100)
                Default: 10

    Returns:
        Dict containing:
            - success (bool): Whether the search succeeded
            - results (list): List of matching context objects
            - total_count (int): Total number of results found
            - search_mode_used (str): The search mode that was actually used
            - retrieval_mode_used (str): The retrieval mode that was actually used
            - message (str): Success or error message

    Example:
        >>> arguments = {
        ...     "query": "API authentication design",
        ...     "type": "design",
        ...     "search_mode": "hybrid",
        ...     "retrieval_mode": "hybrid",
        ...     "limit": 5
        ... }
        >>> result = await retrieve_context_tool(arguments)
        >>> print(len(result["results"]))  # Number of matching contexts
        >>> for ctx in result["results"]:
        ...     print(ctx["content"]["title"])  # Context titles
    """
    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("retrieve_context")
    if not allowed:
        return {
            "success": False,
            "results": [],
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        query = arguments["query"]
        context_type = arguments.get("type", "all")
        search_mode = arguments.get("search_mode", "hybrid")
        retrieval_mode = arguments.get("retrieval_mode", "hybrid")
        limit = arguments.get("limit", 10)

        # New GraphRAG parameters
        max_hops = arguments.get("max_hops", 2)
        relationship_types = arguments.get("relationship_types", None)
        include_reasoning_path = arguments.get("include_reasoning_path", False)
        enable_community_detection = arguments.get("enable_community_detection", False)

        # Use retrieval_mode if specified, otherwise fall back to search_mode
        effective_mode = retrieval_mode

        results = []

        if effective_mode in ["vector", "hybrid"] and qdrant_client and qdrant_client.client:
            try:
                # Generate proper semantic embedding for query
                if embedding_generator:
                    query_vector = await embedding_generator.generate_embedding(query)
                    logger.info("Generated semantic query embedding using configured model")
                else:
                    # Fallback to hash-based query embedding for development
                    logger.warning(
                        "No embedding generator available, using fallback method for query"
                    )
                    import hashlib

                    query_hash = hashlib.sha256(query.encode()).digest()

                    # Get dimensions from Qdrant config or default
                    dimensions = qdrant_client.config.get("qdrant", {}).get(
                        "dimensions", Config.EMBEDDING_DIMENSIONS
                    )
                    query_vector = []
                    for i in range(dimensions):
                        byte_idx = i % len(query_hash)
                        # Normalize to [-1, 1] for better vector space properties
                        normalized_value = (float(query_hash[byte_idx]) / 255.0) * 2.0 - 1.0
                        query_vector.append(normalized_value)

                # Use the collection name from config or default
                collection_name = qdrant_client.config.get("qdrant", {}).get(
                    "collection_name", "project_context"
                )

                # Use VectorDBInitializer.search method instead of direct client access
                vector_results = qdrant_client.search(
                    query_vector=query_vector,
                    limit=limit,
                    filter_dict=None,  # Can be enhanced later with type filtering
                )

                # Convert VectorDBInitializer results to our format
                # vector_results is already in the correct format from VectorDBInitializer.search
                for result in vector_results:
                    results.append(
                        {
                            "id": result["id"],
                            "score": result["score"],
                            "source": "vector",
                            "payload": result["payload"],
                        }
                    )

                logger.info(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.error(f"Vector search failed: {e}")

        if effective_mode in ["graph", "hybrid"] and neo4j_client and neo4j_client.driver:
            try:
                # Perform graph search
                with neo4j_client.driver.session(database=neo4j_client.database) as session:
                    # Enhanced graph search with configurable hop distance and relationship filtering
                    if effective_mode == "hybrid" or max_hops > 1:
                        # Build relationship type filter
                        rel_filter = ""
                        if relationship_types:
                            rel_types = "|".join(relationship_types)
                            rel_filter = f":{rel_types}"
                        else:
                            rel_filter = ""  # Allow all relationship types

                        # Multi-hop traversal query with configurable parameters
                        cypher_query = f"""
                        MATCH (n:Context)-[r{rel_filter}*1..{max_hops}]->(m)
                        WHERE (n.type = $type OR $type = 'all')
                        AND (n.content CONTAINS $query OR n.metadata CONTAINS $query OR
                             m.content CONTAINS $query OR m.metadata CONTAINS $query)
                        RETURN DISTINCT m.id as id, m.type as type, m.content as content,
                               m.metadata as metadata, m.created_at as created_at
                        LIMIT $limit
                        """
                    else:
                        # Standard graph search for single-hop modes
                        cypher_query = """
                        MATCH (n:Context)
                        WHERE (n.type = $type OR $type = 'all')
                        AND (n.content CONTAINS $query OR n.metadata CONTAINS $query)
                        RETURN n.id as id, n.type as type, n.content as content,
                               n.metadata as metadata, n.created_at as created_at
                        LIMIT $limit
                        """
                    query_result = neo4j_client.query(
                        cypher_query,
                        parameters={"type": context_type, "query": query, "limit": limit},
                    )

                    for record in query_result:
                        try:
                            content = json.loads(record["content"]) if record["content"] else {}
                            metadata = json.loads(record["metadata"]) if record["metadata"] else {}
                        except json.JSONDecodeError:
                            content = record["content"]
                            metadata = record["metadata"]

                        results.append(
                            {
                                "id": record["id"],
                                "type": record["type"],
                                "content": content,
                                "metadata": metadata,
                                "created_at": (
                                    str(record["created_at"]) if record["created_at"] else None
                                ),
                                "source": "graph",
                            }
                        )

                graph_results_count = len([r for r in results if r.get("source") == "graph"])
                logger.info(f"Graph search returned {graph_results_count} results")
            except Exception as e:
                logger.error(f"Graph search failed: {e}")

        # Enhance results with GraphRAG features if requested
        enhanced_results = results[:limit]
        graphrag_metadata = {
            "max_hops_used": max_hops,
            "relationship_types_used": relationship_types,
            "reasoning_path_included": include_reasoning_path,
            "community_detection_enabled": enable_community_detection,
        }

        # Add reasoning path if requested
        if include_reasoning_path and enhanced_results:
            # Simple reasoning path implementation - can be enhanced with full GraphRAG integration
            for result in enhanced_results:
                result[
                    "reasoning_path"
                ] = f"Found via {result.get('source', 'unknown')} search with {max_hops}-hop traversal"

        # Add community detection placeholder - will be implemented in community detection tool
        if enable_community_detection:
            graphrag_metadata[
                "community_info"
            ] = "Community detection available via detect_communities tool"

        # Apply reranking to improve precision
        reranker_config = qdrant_client.config.get("reranker", {}) if qdrant_client else {}
        reranker = get_reranker(reranker_config)
        if reranker.enabled and enhanced_results:
            logger.info(f"Applying reranker to {len(enhanced_results)} results")
            reranked_results = reranker.rerank(query, enhanced_results)
            
            # Add reranker metadata
            graphrag_metadata["reranker"] = {
                "enabled": True,
                "model": reranker.model_name,
                "original_count": len(enhanced_results),
                "reranked_count": len(reranked_results),
                "top_k": reranker.top_k,
                "return_k": reranker.return_k
            }
            enhanced_results = reranked_results
        else:
            graphrag_metadata["reranker"] = {"enabled": False}

        return {
            "success": True,
            "results": enhanced_results,
            "total_count": len(results),
            "search_mode_used": search_mode,
            "retrieval_mode_used": effective_mode,
            "graphrag_metadata": graphrag_metadata,
            "message": f"Found {len(enhanced_results)} matching contexts using GraphRAG-enhanced {'reranked ' if reranker.enabled else ''}search",
        }

    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        return {
            "success": False,
            "results": [],
            "message": f"Failed to retrieve context: {str(e)}",
        }


async def query_graph_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute read-only Cypher queries on the graph database.

    This function allows executing custom Cypher queries for advanced
    graph analysis and traversal. For security, only read operations
    are permitted - write operations like CREATE, DELETE, SET are blocked.

    Args:
        arguments: Dictionary containing:
            - query (str): Cypher query to execute (required)
                Must be read-only (no CREATE/DELETE/SET/REMOVE/MERGE/DROP)
            - parameters (dict, optional): Query parameters for parameterized queries
                Default: {}
            - limit (int, optional): Maximum number of results to return (1-1000)
                Default: 100

    Returns:
        Dict containing:
            - success (bool): Whether the query succeeded
            - results (list): Query results as list of dictionaries
            - row_count (int): Number of rows returned
            - error (str, optional): Error message if query failed

    Security:
        - Only read operations are allowed (MATCH, RETURN, WHERE, etc.)
        - Write operations (CREATE, DELETE, SET, REMOVE, MERGE, DROP) are blocked
        - Query validation prevents SQL injection-style attacks

    Example:
        >>> arguments = {
        ...     "query": "MATCH (n:Context)-[:IMPLEMENTS]->(r:Requirement) "
        ...              "WHERE n.type = $type RETURN n.title, r.id",
        ...     "parameters": {"type": "design"},
        ...     "limit": 20
        ... }
        >>> result = await query_graph_tool(arguments)
        >>> for row in result["results"]:
        ...     print(f"Design: {row['n.title']} implements {row['r.id']}")
    """
    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("query_graph")
    if not allowed:
        return {
            "success": False,
            "results": [],
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        query = arguments["query"]
        parameters = arguments.get("parameters", {})
        limit = arguments.get("limit", 100)

        # Enhanced security check with comprehensive validation
        validation_result = cypher_validator.validate_query(query, parameters)
        if not validation_result.is_valid:
            logger.warning(f"Query validation failed: {validation_result.error_message}")
            return {
                "success": False,
                "error": f"Query validation failed: {validation_result.error_message}",
                "error_type": validation_result.error_type,
            }

        # Log warnings if any
        if validation_result.warnings:
            logger.info(f"Query validation warnings: {validation_result.warnings}")

        logger.info(
            f"Query validation passed with complexity score: {validation_result.complexity_score}"
        )

        # Use read-only client for enhanced security
        try:
            from ..storage.neo4j_readonly import get_readonly_client
            readonly_client = get_readonly_client(config.get_all_config() if config else None)
            
            if not readonly_client.connect():
                # Fallback to main client if read-only client unavailable
                if not neo4j_client or not neo4j_client.driver:
                    return {"success": False, "error": "Graph database not available"}
                logger.warning("Read-only client unavailable, using main client")
                results = neo4j_client.query(query, parameters)
            else:
                # Use secure read-only client
                logger.info("Using read-only client for graph query")
                results = readonly_client.query(query, parameters)
                
        except ImportError as e:
            logger.warning(f"Read-only client not available: {e}, using main client")
            if not neo4j_client or not neo4j_client.driver:
                return {"success": False, "error": "Graph database not available"}
            results = neo4j_client.query(query, parameters)
        except Exception as e:
            logger.error(f"Graph query execution failed: {e}")
            return {"success": False, "error": str(e)}

        return {"success": True, "results": results[:limit], "row_count": len(results)}

    except Exception as e:
        logger.error(f"Error executing graph query: {e}")
        return {"success": False, "error": str(e)}


async def update_scratchpad_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update agent scratchpad with transient storage and TTL support.

    This function provides a scratchpad for agents to store temporary data
    with automatic expiration. Each agent has an isolated namespace to prevent
    data leakage between agents.

    Args:
        arguments: Dictionary containing:
            - agent_id (str): Agent identifier (required)
            - key (str): Scratchpad key (required)
            - content (str): Content to store (required)
            - mode (str, optional): Update mode 'overwrite' or 'append' (default: 'overwrite')
            - ttl (int, optional): Time to live in seconds (default: 3600, max: 86400)

    Returns:
        Dict containing:
            - success (bool): Whether the operation succeeded
            - message (str): Success or error message
            - key (str): The namespaced key used for storage
            - ttl (int): TTL applied in seconds

    Example:
        >>> arguments = {
        ...     "agent_id": "agent-123",
        ...     "key": "working_memory",
        ...     "content": "Current task: analyze data",
        ...     "mode": "append",
        ...     "ttl": 7200
        ... }
        >>> result = await update_scratchpad_tool(arguments)
        >>> print(result["success"])  # True
    """
    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("update_scratchpad")
    if not allowed:
        return {
            "success": False,
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        agent_id = arguments["agent_id"]
        key = arguments["key"]
        content = arguments["content"]
        mode = arguments.get("mode", "overwrite")
        ttl = arguments.get("ttl", 3600)  # 1 hour default

        # Validate agent ID and key using namespace manager
        if not agent_namespace.validate_agent_id(agent_id):
            return {
                "success": False,
                "message": f"Invalid agent ID format: {agent_id}",
                "error_type": "invalid_agent_id",
            }

        if not agent_namespace.validate_key(key):
            return {
                "success": False,
                "message": f"Invalid key format: {key}",
                "error_type": "invalid_key",
            }

        # Validate content
        if not isinstance(content, str):
            return {
                "success": False,
                "message": "Content must be a string",
                "error_type": "invalid_content_type",
            }

        if len(content) > 100000:  # 100KB limit
            return {
                "success": False,
                "message": "Content exceeds maximum size (100KB)",
                "error_type": "content_too_large",
            }

        # Validate TTL
        if ttl < 60 or ttl > 86400:  # 1 minute to 24 hours
            return {
                "success": False,
                "message": "TTL must be between 60 and 86400 seconds",
                "error_type": "invalid_ttl",
            }

        # Create namespaced key
        try:
            namespaced_key = agent_namespace.create_namespaced_key(agent_id, "scratchpad", key)
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create namespaced key: {str(e)}",
                "error_type": "namespace_error",
            }

        # Check Redis availability
        if not kv_store or not kv_store.redis:
            return {
                "success": False,
                "message": "Redis storage not available",
                "error_type": "storage_unavailable",
            }

        try:
            # Handle append mode
            if mode == "append":
                existing_content = kv_store.redis.get(namespaced_key)
                if existing_content:
                    content = existing_content + "\n" + content

            # Store content with TTL
            success = kv_store.redis.setex(namespaced_key, ttl, content)

            if success:
                logger.info(f"Updated scratchpad for agent {agent_id}, key: {key}, TTL: {ttl}s")
                return {
                    "success": True,
                    "message": f"Scratchpad updated successfully (mode: {mode})",
                    "key": namespaced_key,
                    "ttl": ttl,
                    "content_size": len(content),
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to store content in Redis",
                    "error_type": "storage_error",
                }

        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            return {
                "success": False,
                "message": f"Storage operation failed: {str(e)}",
                "error_type": "storage_exception",
            }

    except KeyError as e:
        return {
            "success": False,
            "message": f"Missing required parameter: {str(e)}",
            "error_type": "missing_parameter",
        }
    except Exception as e:
        logger.error(f"Error updating scratchpad: {e}")
        return {
            "success": False,
            "message": f"Failed to update scratchpad: {str(e)}",
            "error_type": "unexpected_error",
        }


async def get_agent_state_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve agent state with namespace isolation.

    This function retrieves agent state data from the appropriate storage
    backend while ensuring namespace isolation. Agents can only access
    their own state data.

    Args:
        arguments: Dictionary containing:
            - agent_id (str): Agent identifier (required)
            - key (str, optional): Specific state key to retrieve
            - prefix (str, optional): State type - 'state', 'scratchpad', 'memory', 'config' (default: 'state')

    Returns:
        Dict containing:
            - success (bool): Whether the operation succeeded
            - data (dict): Retrieved state data
            - keys (list, optional): Available keys if no specific key requested
            - message (str): Success or error message

    Example:
        >>> arguments = {
        ...     "agent_id": "agent-123",
        ...     "key": "working_memory",
        ...     "prefix": "scratchpad"
        ... }
        >>> result = await get_agent_state_tool(arguments)
        >>> print(result["data"])  # Retrieved content
    """
    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("get_agent_state")
    if not allowed:
        return {
            "success": False,
            "data": {},
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        agent_id = arguments["agent_id"]
        key = arguments.get("key")
        prefix = arguments.get("prefix", "state")

        # Validate agent ID
        if not agent_namespace.validate_agent_id(agent_id):
            return {
                "success": False,
                "data": {},
                "message": f"Invalid agent ID format: {agent_id}",
                "error_type": "invalid_agent_id",
            }

        # Validate prefix
        if not agent_namespace.validate_prefix(prefix):
            return {
                "success": False,
                "data": {},
                "message": f"Invalid prefix: {prefix}",
                "error_type": "invalid_prefix",
            }

        # Validate key if provided
        if key and not agent_namespace.validate_key(key):
            return {
                "success": False,
                "data": {},
                "message": f"Invalid key format: {key}",
                "error_type": "invalid_key",
            }

        # Check Redis availability
        if not kv_store or not kv_store.redis:
            return {
                "success": False,
                "data": {},
                "message": "Redis storage not available",
                "error_type": "storage_unavailable",
            }

        try:
            if key:
                # Retrieve specific key
                namespaced_key = agent_namespace.create_namespaced_key(agent_id, prefix, key)

                # Verify agent has access to this key
                if not agent_namespace.verify_agent_access(agent_id, namespaced_key):
                    return {
                        "success": False,
                        "data": {},
                        "message": "Access denied to requested resource",
                        "error_type": "access_denied",
                    }

                content = kv_store.redis.get(namespaced_key)
                if content is None:
                    return {
                        "success": False,
                        "data": {},
                        "message": f"Key '{key}' not found",
                        "error_type": "key_not_found",
                    }

                logger.info(f"Retrieved state for agent {agent_id}, key: {key}")
                return {
                    "success": True,
                    "data": {
                        "key": key,
                        "content": content,
                        "namespaced_key": namespaced_key,
                    },
                    "message": "State retrieved successfully",
                }

            else:
                # List all keys for the agent with the given prefix
                pattern = f"agent:{agent_id}:{prefix}:*"
                keys = kv_store.redis.keys(pattern)

                if not keys:
                    return {
                        "success": True,
                        "data": {},
                        "keys": [],
                        "message": f"No {prefix} data found for agent",
                    }

                # Retrieve all matching keys (limit to reasonable amount)
                max_keys = 100
                data = {}
                retrieved_keys = []

                for namespaced_key in keys[:max_keys]:
                    try:
                        # Parse the key to get the actual key name
                        _, _, _, actual_key = namespaced_key.split(":", 3)
                        content = kv_store.redis.get(namespaced_key)
                        if content is not None:
                            data[actual_key] = content
                            retrieved_keys.append(actual_key)
                    except Exception as e:
                        logger.warning(f"Failed to retrieve key {namespaced_key}: {e}")
                        continue

                logger.info(f"Retrieved {len(retrieved_keys)} {prefix} keys for agent {agent_id}")
                return {
                    "success": True,
                    "data": data,
                    "keys": retrieved_keys,
                    "message": f"Retrieved {len(retrieved_keys)} {prefix} entries",
                    "total_available": len(keys),
                }

        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            return {
                "success": False,
                "data": {},
                "message": f"Storage operation failed: {str(e)}",
                "error_type": "storage_exception",
            }

    except KeyError as e:
        return {
            "success": False,
            "data": {},
            "message": f"Missing required parameter: {str(e)}",
            "error_type": "missing_parameter",
        }
    except Exception as e:
        logger.error(f"Error retrieving agent state: {e}")
        return {
            "success": False,
            "data": {},
            "message": f"Failed to retrieve state: {str(e)}",
            "error_type": "unexpected_error",
        }


async def get_health_status() -> Dict[str, Any]:
    """Get server health status."""
    health_status = {
        "status": "healthy",
        "services": {"neo4j": "unknown", "qdrant": "unknown", "redis": "unknown"},
    }

    # Check Neo4j using Neo4jInitializer.query method
    if neo4j_client and neo4j_client.driver:
        try:
            neo4j_client.query("RETURN 1")
            health_status["services"]["neo4j"] = "healthy"
        except Exception as e:
            health_status["services"]["neo4j"] = "unhealthy"
            health_status["status"] = "degraded"
            logger.warning(f"Neo4j health check failed: {e}")

    # Check Qdrant using VectorDBInitializer.get_collections method
    if qdrant_client and qdrant_client.client:
        try:
            qdrant_client.get_collections()
            health_status["services"]["qdrant"] = "healthy"
        except Exception as e:
            health_status["services"]["qdrant"] = "unhealthy"
            health_status["status"] = "degraded"
            logger.warning(f"Qdrant health check failed: {e}")

    # Check Redis/KV Store
    if kv_store:
        try:
            # Test Redis connection through ContextKV
            if kv_store.redis.redis_client:
                kv_store.redis.redis_client.ping()
                health_status["services"]["redis"] = "healthy"
            else:
                health_status["services"]["redis"] = "disconnected"
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["services"]["redis"] = "unhealthy"
            health_status["status"] = "degraded"
            logger.warning(f"Redis health check failed: {e}")

    return health_status


async def detect_communities_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Detect communities in the knowledge graph using GraphRAG.

    This tool performs community detection on the knowledge graph to identify
    clusters of related documents, entities, or concepts. It uses various
    community detection algorithms to analyze the graph structure and find
    meaningful groupings.

    Args:
        arguments: Dictionary containing:
            - algorithm (str, optional): Community detection algorithm ('louvain', 'leiden', 'modularity')
                Default: 'louvain'
            - min_community_size (int, optional): Minimum size for communities (2-50)
                Default: 3
            - resolution (float, optional): Resolution parameter for algorithm (0.1-2.0)
                Default: 1.0
            - include_members (bool, optional): Include community member details
                Default: True

    Returns:
        Dict containing:
            - success (bool): Whether community detection succeeded
            - communities (list): List of detected communities
            - algorithm_used (str): Algorithm that was used
            - total_communities (int): Total number of communities found
            - message (str): Success or error message

    Example:
        >>> arguments = {
        ...     "algorithm": "louvain",
        ...     "min_community_size": 3,
        ...     "resolution": 1.0,
        ...     "include_members": True
        ... }
        >>> result = await detect_communities_tool(arguments)
        >>> print(f"Found {result['total_communities']} communities")
    """
    # Import GraphRAG bridge
    try:
        from .graphrag_bridge import get_graphrag_bridge
    except ImportError:
        return {
            "success": False,
            "communities": [],
            "message": "GraphRAG bridge not available",
            "error_type": "import_error",
        }

    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("detect_communities")
    if not allowed:
        return {
            "success": False,
            "communities": [],
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        # Extract parameters
        algorithm = arguments.get("algorithm", "louvain")
        min_community_size = arguments.get("min_community_size", 3)
        resolution = arguments.get("resolution", 1.0)
        include_members = arguments.get("include_members", True)

        # Validate parameters
        if algorithm not in ["louvain", "leiden", "modularity"]:
            return {
                "success": False,
                "communities": [],
                "message": f"Invalid algorithm: {algorithm}. Must be one of: louvain, leiden, modularity",
                "error_type": "invalid_algorithm",
            }

        if not (2 <= min_community_size <= 50):
            return {
                "success": False,
                "communities": [],
                "message": f"Invalid min_community_size: {min_community_size}. Must be between 2 and 50",
                "error_type": "invalid_parameter",
            }

        if not (0.1 <= resolution <= 2.0):
            return {
                "success": False,
                "communities": [],
                "message": f"Invalid resolution: {resolution}. Must be between 0.1 and 2.0",
                "error_type": "invalid_parameter",
            }

        # Get GraphRAG bridge and perform community detection
        bridge = get_graphrag_bridge()

        if not bridge.is_available():
            return {
                "success": False,
                "communities": [],
                "message": "GraphRAG integration not available",
                "error_type": "graphrag_unavailable",
            }

        # Perform community detection
        result = await bridge.detect_communities(
            algorithm=algorithm, min_community_size=min_community_size, resolution=resolution
        )

        # Filter communities by size if requested
        if result["success"] and min_community_size > 1:
            filtered_communities = [
                community
                for community in result["communities"]
                if community.get("size", 0) >= min_community_size
            ]
            result["communities"] = filtered_communities
            result["total_communities"] = len(filtered_communities)

        # Remove member details if not requested
        if not include_members and result["success"]:
            for community in result["communities"]:
                if "members" in community:
                    community["member_count"] = len(community["members"])
                    del community["members"]

        # Add GraphRAG metadata
        result["graphrag_metadata"] = {
            "algorithm_used": algorithm,
            "min_community_size": min_community_size,
            "resolution": resolution,
            "include_members": include_members,
            "bridge_status": bridge.get_status(),
        }

        return result

    except Exception as e:
        logger.error(f"Error in community detection: {e}")
        return {
            "success": False,
            "communities": [],
            "message": f"Community detection failed: {str(e)}",
            "error_type": "execution_error",
        }


async def get_tools_info() -> Dict[str, Any]:
    """Get information about available tools."""
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
            except Exception as e:
                logger.warning(f"Failed to load contract {contract_file}: {e}")

    return {"tools": tools, "server_version": "1.0.0", "mcp_version": "1.0"}


async def select_tools_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Select relevant tools based on query using multiple selection algorithms.

    This tool provides intelligent tool selection using numpy dot-product relevance,
    rule-based heuristics, or hybrid approaches. It returns ≤ N relevant tools
    and logs selection results in YAML format.

    Args:
        arguments: Dictionary containing:
            - query (str): Search query or context description (required)
            - max_tools (int, optional): Maximum number of tools to return (default: 5)
            - method (str, optional): Selection method (default: "hybrid")
            - category_filter (str, optional): Filter by category
            - include_scores (bool, optional): Include relevance scores (default: True)

    Returns:
        Dict containing selected tools, metadata, and YAML selection log
    """
    if not tool_selector_bridge:
        return {
            "success": False,
            "tools": [],
            "total_available": 0,
            "message": "Tool selector bridge not available",
            "error_type": "bridge_unavailable",
        }

    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("select_tools")
    if not allowed:
        return {
            "success": False,
            "tools": [],
            "total_available": 0,
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        result = await tool_selector_bridge.select_tools(arguments)
        logger.info(f"Tool selection completed: {result.get('message', 'No message')}")
        return result

    except Exception as e:
        logger.error(f"Error in select_tools_tool: {e}")
        return {
            "success": False,
            "tools": [],
            "total_available": 0,
            "message": f"Tool selection failed: {str(e)}",
            "error_type": "execution_error",
        }


async def list_available_tools_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all available tools in the tool selector system.

    This tool provides a comprehensive list of all tools available in the
    tool selector system, with optional filtering and sorting capabilities.

    Args:
        arguments: Dictionary containing:
            - category_filter (str, optional): Filter by category
            - include_metadata (bool, optional): Include metadata (default: True)
            - sort_by (str, optional): Sort by field (default: "name")

    Returns:
        Dict containing list of tools, categories, and metadata
    """
    if not tool_selector_bridge:
        return {
            "success": False,
            "tools": [],
            "total_count": 0,
            "categories": [],
            "message": "Tool selector bridge not available",
            "error_type": "bridge_unavailable",
        }

    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("list_available_tools")
    if not allowed:
        return {
            "success": False,
            "tools": [],
            "total_count": 0,
            "categories": [],
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        result = await tool_selector_bridge.list_available_tools(arguments)
        logger.info(f"Tool listing completed: {result.get('message', 'No message')}")
        return result

    except Exception as e:
        logger.error(f"Error in list_available_tools_tool: {e}")
        return {
            "success": False,
            "tools": [],
            "total_count": 0,
            "categories": [],
            "message": f"Tool listing failed: {str(e)}",
            "error_type": "execution_error",
        }


async def get_tool_info_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed information about a specific tool.

    This tool provides comprehensive information about a specific tool,
    including its documentation, usage examples, and metadata.

    Args:
        arguments: Dictionary containing:
            - tool_name (str): Name of the tool to get info about (required)
            - include_usage_examples (bool, optional): Include usage examples (default: True)

    Returns:
        Dict containing detailed tool information
    """
    if not tool_selector_bridge:
        return {
            "success": False,
            "message": "Tool selector bridge not available",
            "error_type": "bridge_unavailable",
        }

    # Rate limiting check
    allowed, rate_limit_msg = await rate_limit_check("get_tool_info")
    if not allowed:
        return {
            "success": False,
            "message": f"Rate limit exceeded: {rate_limit_msg}",
            "error_type": "rate_limit",
        }

    try:
        result = await tool_selector_bridge.get_tool_info(arguments)
        logger.info(f"Tool info retrieval completed: {result.get('message', 'No message')}")
        return result

    except Exception as e:
        logger.error(f"Error in get_tool_info_tool: {e}")
        return {
            "success": False,
            "message": f"Tool info retrieval failed: {str(e)}",
            "error_type": "execution_error",
        }


async def main():
    """Main server entry point."""
    # Initialize storage clients
    await initialize_storage_clients()

    try:
        # Run the server using stdio transport
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="context-store",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(),
                ),
            )
    finally:
        # Clean up
        await cleanup_storage_clients()


if __name__ == "__main__":
    asyncio.run(main())
