# Phase 2: Data Initialization & Seeding

## Issue:
Databases have never been properly initialized with data.

## Solutions:

### 1. Fix Embedding Pipeline
**File**: `src/embeddings/embedding_service.py`

Check for:
- Model loading failures
- Memory issues with embedding model
- Fallback to lighter model if needed

### 2. Create Data Initialization Script
**File**: `scripts/initialize_data.py`

```python
#!/usr/bin/env python3
"""Initialize veris-memory with test data and verify all components."""

import asyncio
import aiohttp
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000"
API_KEY = "vmk_mcp_903e1bcb70d704da4fbf207722c471ba"

async def initialize_system():
    """Initialize system with test data."""

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }

    # Test data to seed
    test_contexts = [
        {
            "type": "design",
            "content": {
                "title": "MCP Protocol Design",
                "description": "Use Model Context Protocol for AI agent communication",
                "rationale": "Standardized interface for tool calling"
            },
            "metadata": {"component": "mcp_server", "sprint": "13"},
            "author": "system",
            "author_type": "agent"
        },
        {
            "type": "decision",
            "content": {
                "title": "API Key Authentication",
                "decision": "Implement Sprint 13 authentication",
                "status": "implemented"
            },
            "metadata": {"security": "high", "sprint": "13"},
            "author": "team",
            "author_type": "human"
        },
        {
            "type": "log",
            "content": {
                "title": "System Initialization",
                "event": "Initial data seeding completed",
                "timestamp": "2025-11-07T00:00:00Z"
            },
            "metadata": {"system": "true"},
            "author": "initializer",
            "author_type": "agent"
        }
    ]

    async with aiohttp.ClientSession() as session:
        # Store test contexts
        for context in test_contexts:
            try:
                async with session.post(
                    f"{API_URL}/tools/store_context",
                    json=context,
                    headers=headers
                ) as resp:
                    result = await resp.json()
                    logger.info(f"Stored: {context['content']['title']} - {result}")
            except Exception as e:
                logger.error(f"Failed to store context: {e}")

        # Verify retrieval
        try:
            async with session.post(
                f"{API_URL}/tools/retrieve_context",
                json={"query": "sprint 13", "limit": 10},
                headers=headers
            ) as resp:
                results = await resp.json()
                logger.info(f"Retrieved {results.get('total_count', 0)} contexts")
                return results
        except Exception as e:
            logger.error(f"Failed to retrieve: {e}")
            return None

if __name__ == "__main__":
    asyncio.run(initialize_system())
```

### 3. Fix Qdrant Collection Creation
**File**: `src/storage/qdrant_store.py`

Ensure collection is created with proper configuration:

```python
async def ensure_collection(self):
    """Ensure Qdrant collection exists with proper configuration."""
    try:
        # Check if collection exists
        collections = await self.client.get_collections()

        if self.collection_name not in [c.name for c in collections.collections]:
            # Create with proper vector size
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384,  # sentence-transformers/all-MiniLM-L6-v2
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Created collection: {self.collection_name}")
    except Exception as e:
        logger.error(f"Failed to ensure collection: {e}")
```

## Testing Phase 2:

```bash
# 1. Run initialization script
cd /claude-workspace/worktrees/sessions/session-20251107-000050-3532990/veris-memory
python scripts/initialize_data.py

# 2. Check Qdrant vectors
curl http://localhost:6333/collections/contexts/points/count

# 3. Check Neo4j data
docker exec -it veris-memory_neo4j_1 cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "MATCH (n) RETURN count(n) as node_count"

# 4. Check Redis
docker exec veris-memory_redis_1 redis-cli DBSIZE
```

## Expected Results:
- Qdrant should have vectors
- Neo4j should have nodes
- Redis should have keys (if used)