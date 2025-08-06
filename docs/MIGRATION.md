# Migration Guide

This guide helps users migrate from direct storage access to the MCP-based Context Store server.

## Overview

The Context Store has evolved from direct database access to a standardized MCP (Model Context Protocol) server. This provides:

- **Standardized API**: Consistent tool interface across all clients
- **Better Security**: Controlled access with validation and rate limiting
- **Improved Performance**: Optimized queries and connection pooling
- **Enhanced Features**: Hybrid search, namespace isolation, graceful degradation

## Migration Timeline

| Version | Status        | Description                            |
| ------- | ------------- | -------------------------------------- |
| v0.4.x  | Legacy        | Direct database access (deprecated)    |
| v0.5.x  | Current Alpha | MCP server with backward compatibility |
| v1.0.x  | Future        | MCP-only (direct access removed)       |

## Breaking Changes

### 1. API Interface Change

**Before (Direct Access)**:

```python
from context_store import ContextStore

store = ContextStore(
    qdrant_url="http://localhost:6333",
    neo4j_uri="bolt://localhost:7687",
    redis_url="redis://localhost:6379"
)

# Direct method calls
result = store.store_context({
    "title": "API Design",
    "description": "REST API specification"
}, context_type="design")

contexts = store.retrieve_context("API design", limit=5)
```

**After (MCP Protocol)**:

```python
from mcp.client import MCPClient
import asyncio

async def use_context_store():
    client = MCPClient("http://localhost:8000/mcp")
    await client.connect()

    # MCP tool calls
    result = await client.call_tool("store_context", {
        "content": {"title": "API Design", "description": "REST API specification"},
        "type": "design"
    })

    contexts = await client.call_tool("retrieve_context", {
        "query": "API design",
        "limit": 5
    })

    await client.close()

asyncio.run(use_context_store())
```

### 2. Configuration Changes

**Before**:

```python
config = {
    "qdrant": {"url": "http://localhost:6333", "api_key": "..."},
    "neo4j": {"uri": "bolt://localhost:7687", "user": "neo4j", "password": "..."},
    "redis": {"url": "redis://localhost:6379", "password": "..."}
}
```

**After**:

```env
# .env file
NEO4J_PASSWORD=your_password
REDIS_PASSWORD=your_password
QDRANT_API_KEY=your_key

# Single MCP endpoint
MCP_SERVER_URL=http://localhost:8000/mcp
```

### 3. Deployment Changes

**Before**:

```bash
# Manual service management
docker run -d qdrant/qdrant
docker run -d neo4j
docker run -d redis
python -m context_store.server
```

**After**:

```bash
# Single docker-compose command
git clone https://github.com/credentum/context-store.git
cd context-store
cp .env.example .env
# Edit .env with your passwords
docker-compose up -d
```

## Step-by-Step Migration

### Step 1: Deploy MCP Server

1. **Clone the repository**:

   ```bash
   git clone https://github.com/credentum/context-store.git
   cd context-store
   ```

2. **Configure environment**:

   ```bash
   cp .env.example .env
   # Edit .env and set NEO4J_PASSWORD and other credentials
   ```

3. **Deploy services**:

   ```bash
   docker-compose up -d
   ```

4. **Verify deployment**:
   ```bash
   curl http://localhost:8000/health
   ```

### Step 2: Update Client Code

#### Python Applications

**Install MCP client**:

```bash
pip install mcp-client
```

**Update imports and initialization**:

```python
# Old
from context_store import ContextStore
store = ContextStore(config)

# New
from mcp.client import MCPClient
client = MCPClient("http://localhost:8000/mcp")
await client.connect()
```

**Update method calls**:

```python
# Old: store_context
result = store.store_context(content, context_type="design", metadata=meta)

# New: store_context tool
result = await client.call_tool("store_context", {
    "content": content,
    "type": "design",
    "metadata": meta
})

# Old: retrieve_context
contexts = store.retrieve_context(query, limit=5, context_type="design")

# New: retrieve_context tool
result = await client.call_tool("retrieve_context", {
    "query": query,
    "limit": 5,
    "type": "design"
})
contexts = result["results"]

# Old: graph queries
results = store.query_graph("MATCH (n:Context) RETURN n")

# New: query_graph tool
result = await client.call_tool("query_graph", {
    "query": "MATCH (n:Context) RETURN n"
})
results = result["results"]
```

#### JavaScript/TypeScript Applications

**Install MCP client**:

```bash
npm install @modelcontextprotocol/client
```

**Update code**:

```typescript
// Old - direct database clients
import { QdrantClient } from "qdrant-client";
import { Neo4jClient } from "neo4j-driver";

// New - MCP client
import { MCPClient } from "@modelcontextprotocol/client";

const client = new MCPClient({
  serverUrl: "http://localhost:8000/mcp",
});

await client.connect();

// Store context
const result = await client.callTool("store_context", {
  content: { title: "API Design", description: "REST API spec" },
  type: "design",
});
```

#### CLI Applications

**Old shell scripts**:

```bash
# Direct database calls
psql -h localhost -d context -c "INSERT INTO contexts..."
curl -X POST http://localhost:6333/collections/contexts/points
```

**New MCP calls**:

```bash
# MCP tool calls
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "store_context",
      "arguments": {
        "content": {"title": "API Design"},
        "type": "design"
      }
    }
  }'
```

### Step 3: Data Migration

Your existing data will be automatically accessible through the MCP server. No data migration is required as the MCP server connects to the same databases.

**Verify data access**:

```bash
# Check that existing contexts are accessible
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "retrieve_context",
      "arguments": {"query": "your-existing-data", "limit": 10}
    }
  }'
```

### Step 4: Update CI/CD

**Before**:

```yaml
# .github/workflows/test.yml
- name: Start services
  run: |
    docker-compose -f docker-compose.test.yml up -d
    python -m context_store.server &

- name: Run tests
  run: python -m pytest tests/
```

**After**:

```yaml
# .github/workflows/test.yml
- name: Start Context Store
  run: |
    cd context-store
    docker-compose up -d

- name: Wait for services
  run: |
    timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'

- name: Run tests
  run: python -m pytest tests/
```

## Compatibility Matrix

| Feature          | Legacy API | MCP API | Notes                     |
| ---------------- | ---------- | ------- | ------------------------- |
| Store Context    | ✅         | ✅      | Parameter names changed   |
| Retrieve Context | ✅         | ✅      | Response format changed   |
| Graph Queries    | ✅         | ✅      | Security validation added |
| Scratchpad       | ❌         | ✅      | New feature               |
| Agent State      | ❌         | ✅      | New feature               |
| Rate Limiting    | ❌         | ✅      | New feature               |
| Input Validation | Basic      | ✅      | Enhanced validation       |
| Error Handling   | Basic      | ✅      | Structured error codes    |

## Common Migration Issues

### 1. Async/Await Required

**Problem**: MCP client requires async/await

```python
# This won't work
result = client.call_tool("store_context", args)
```

**Solution**: Use async/await

```python
# This works
result = await client.call_tool("store_context", args)
```

### 2. Response Format Changes

**Problem**: Response structure is different

```python
# Old response
contexts = [{"id": "123", "title": "..."}]

# New response
response = {"success": True, "results": [{"id": "123", "payload": {"content": {"title": "..."}}}]}
```

**Solution**: Extract results from response

```python
if response["success"]:
    contexts = [r["payload"]["content"] for r in response["results"]]
```

### 3. Connection Management

**Problem**: Need to manage client connections

```python
# Don't forget to close connections
client = MCPClient("http://localhost:8000/mcp")
await client.connect()
# ... use client ...
await client.close()  # Important!
```

**Solution**: Use context manager

```python
async with MCPClient("http://localhost:8000/mcp") as client:
    result = await client.call_tool("store_context", args)
    # Client automatically closed
```

### 4. Environment Variables

**Problem**: Configuration not found

```
ConnectionError: Could not connect to MCP server
```

**Solution**: Check environment and service health

```bash
# Verify services are running
docker-compose ps

# Check health endpoint
curl http://localhost:8000/health

# Check logs
docker-compose logs context-store
```

## Testing Migration

### Unit Tests

```python
import pytest
from mcp.client import MCPClient

@pytest.fixture
async def mcp_client():
    client = MCPClient("http://localhost:8000/mcp")
    await client.connect()
    yield client
    await client.close()

@pytest.mark.asyncio
async def test_store_context(mcp_client):
    result = await mcp_client.call_tool("store_context", {
        "content": {"title": "Test Context"},
        "type": "design"
    })
    assert result["success"] is True
    assert "id" in result
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_migration_compatibility(mcp_client):
    # Store context with new API
    store_result = await mcp_client.call_tool("store_context", {
        "content": {"title": "Migration Test", "description": "Testing compatibility"},
        "type": "design",
        "metadata": {"migration": "test"}
    })

    # Retrieve with new API
    retrieve_result = await mcp_client.call_tool("retrieve_context", {
        "query": "Migration Test",
        "limit": 1
    })

    assert retrieve_result["success"] is True
    assert len(retrieve_result["results"]) > 0

    context = retrieve_result["results"][0]
    assert context["payload"]["content"]["title"] == "Migration Test"
```

## Rollback Plan

If you need to rollback to the legacy API:

1. **Stop MCP server**:

   ```bash
   docker-compose down
   ```

2. **Revert client code** to use direct database access

3. **Start individual services**:

   ```bash
   docker run -d --name qdrant qdrant/qdrant
   docker run -d --name neo4j neo4j
   docker run -d --name redis redis
   ```

4. **Update connection strings** in your application config

## Support

- **Migration Issues**: [GitHub Issues](https://github.com/credentum/context-store/issues)
- **API Questions**: [GitHub Discussions](https://github.com/credentum/context-store/discussions)
- **Documentation**: [MCP Tools Reference](MCP_TOOLS.md)
- **Examples**: [Hello World Example](../examples/hello_world.py)

## Timeline for Legacy Support

- **v0.5.x**: Legacy API deprecated but functional
- **v0.6.x**: Legacy API generates warnings
- **v1.0.x**: Legacy API removed (MCP-only)

**Recommendation**: Migrate before v1.0 release to avoid disruption.
