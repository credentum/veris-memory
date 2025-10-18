# Veris Memory MCP Server - Analysis Report

## Executive Summary

Veris Memory is a sophisticated context storage and retrieval system for AI agents, implementing the Model Context Protocol (MCP) v1.0. The system is production-proven with real-world deployments in Telegram bots supporting concurrent users and real-time voice interaction. It provides multi-backend memory with semantic search (Qdrant), relationship tracking (Neo4j), and fast key-value operations (Redis).

---

## 1. Current MCP Server Capabilities & Endpoints

### Core Architecture
- **Framework**: FastAPI + MCP SDK (official Microsoft MCP Python SDK)
- **Protocol**: Model Context Protocol v1.0 compliant
- **Primary Implementation**: `/src/mcp_server/server.py` (MCP SDK-based)
- **Legacy Alternative**: `/src/mcp_server/main.py` (FastAPI HTTP-based)

### Available MCP Tools

#### 1. `store_context` (Dual Backend Storage)
- **Purpose**: Store structured context with embeddings and graph relationships
- **Parameters**:
  - `content` (object, required): Data to store
  - `type` (string, required): One of `design|decision|trace|sprint|log`
  - `metadata` (object, optional): Tags, source, priority
  - `relationships` (array, optional): Graph relationships to establish

- **Backends**:
  - Vector (Qdrant): Semantic embeddings stored
  - Graph (Neo4j): Nodes and relationships created
  - KV (Redis): Metadata cached

- **Response**: Returns `{success, id, vector_id, graph_id, message}`

#### 2. `retrieve_context` (Unified Hybrid Search)
- **Purpose**: Semantic + relationship-based context retrieval
- **Parameters**:
  - `query` (string, required): Search query
  - `type` (string, optional): Filter by context type (default: "all")
  - `search_mode` (string, enum): `vector|graph|kv|text|hybrid|auto` (default: "hybrid")
  - `limit` (integer): 1-100 results (default: 10)
  - `filters` (object, optional): Date range, status, tags
  - `include_relationships` (boolean): Include graph relationships
  - `sort_by` (string): `timestamp|relevance`

- **Implementation Details**:
  - Uses unified RetrievalCore for consistent search across API and MCP
  - Falls back to legacy direct Qdrant/Neo4j calls if RetrievalCore unavailable
  - Returns backend timings and backends_used for debugging
  - Supports BM25 text search via search_mode="text"

- **Response Schema**:
```json
{
  "success": boolean,
  "results": [{
    "id": string,
    "content": object,
    "score": 0-1,
    "source": "vector|graph|kv|text",
    "type": string,
    "metadata": object,
    "relationships": array,
    "title": string,
    "tags": array,
    "namespace": string,
    "user_id": string
  }],
  "total_count": integer,
  "search_mode_used": string,
  "backend_timings": {vector: ms, graph: ms, kv: ms},
  "backends_used": [string]
}
```

#### 3. `query_graph` (Cypher Queries)
- **Purpose**: Advanced Neo4j graph queries
- **Parameters**:
  - `query` (string): Cypher query (read-only validated)
  - `parameters` (object): Query variables
  - `limit` (integer): 1-1000 (default: 100)
  - `timeout` (integer): 1-30000 ms

- **Security**: CypherValidator checks for write operations and injection attacks
- **Response**: `{success, results, row_count, execution_time}`

#### 4. `update_scratchpad` (Transient Storage)
- **Purpose**: Agent working memory with TTL
- **Parameters**:
  - `agent_id` (string): Agent identifier (pattern: `^[a-zA-Z0-9_-]{1,64}$`)
  - `key` (string): Storage key (pattern: `^[a-zA-Z0-9_.-]{1,128}$`)
  - `content` (string): Data to store (max 100KB)
  - `mode` (string): `overwrite|append`
  - `ttl` (integer): 60-86400 seconds

- **Storage**: Redis with namespace isolation `scratchpad:{agent_id}:{key}`
- **Response**: `{success, agent_id, key, ttl, content_size, message}`

#### 5. `get_agent_state` (State Retrieval)
- **Purpose**: Retrieve agent-specific state data
- **Parameters**:
  - `agent_id` (string): Agent identifier
  - `key` (string, optional): Specific key to retrieve
  - `prefix` (string): Namespace prefix (default: "state")

- **Behavior**:
  - If `key` provided: Returns single value
  - If no `key`: Returns all keys matching prefix pattern
  - Uses SimpleRedisClient for direct, reliable access

- **Response**: `{success, data, keys, agent_id, message}`

### Health & Status Endpoints

#### `/health` (Lightweight)
- Returns basic server status without backend queries
- Response: `{status, uptime_seconds, timestamp, message}`

#### `/health/detailed` (Comprehensive)
- Tests Neo4j, Qdrant, and Redis connectivity
- Implements 60-second grace period and 3-retry mechanism
- Response includes per-service health status

#### `/health/embeddings` (Embedding Service Health)
- Tests embedding generation and model loading
- Returns dimension compatibility and performance metrics
- Response: `{status, service, test, compatibility, alerts, recommendations}`

#### `/status` (Agent Discovery)
- Comprehensive system info for orchestration
- Response: `{label, version, protocol, agent_ready, deps, tools}`

#### `/tools/verify_readiness` (Diagnostics)
- Agent readiness verification with scoring (0-100)
- Readiness levels: BASIC, STANDARD, FULL
- Response includes recommendations and service status

---

## 2. Context Storage & Retrieval - Key/Value Fact Storage

### Fact Storage Architecture

**Location**: `/src/storage/fact_store.py`

The system implements a structured fact storage layer with lineage tracking:

```python
@dataclass
class Fact:
    value: Any
    confidence: float
    source_turn_id: str
    updated_at: str
    provenance: str
    attribute: str
    user_id: str
    namespace: str
```

### Key Pattern for Facts
```
facts:{namespace}:{user_id}:{attribute}
fact_history:{namespace}:{user_id}:{attribute}
```

### Key/Value API Methods

#### `store_fact(namespace, user_id, attribute, value, confidence, source_turn_id, provenance)`
- Creates deterministic fact with lineage
- Stores previous value in history before update
- Supports arbitrary attribute names (e.g., `name`, `email`, `preferences.food`)
- TTL: Configurable (default 30 days)

#### `get_fact(namespace, user_id, attribute)` → Optional[Fact]
- Retrieves single fact with metadata
- Returns None if not found
- Includes confidence and provenance

#### `get_user_facts(namespace, user_id)` → Dict[str, Fact]
- Returns all facts for a user
- Maps attribute → Fact object

#### `delete_fact(namespace, user_id, attribute)` → bool
- Removes fact and clears history
- Returns success status

#### `get_fact_history(namespace, user_id, attribute)` → List[Dict]
- Retrieves fact change history
- Each entry: `{fact, replaced_at, replaced_by}`

### Fact Retrieval with Keys

The retrieve_context API supports namespace-based filtering:

```python
# API Request
{
  "query": "user preferences",
  "namespaces": ["agent_123"],  # Filter by namespace
  "search_mode": "kv",  # Direct key-value search
  "limit": 10
}

# Returns facts where namespace == "agent_123"
# Matches across all attributes for that user
```

### Key/Value Store Backend
- **Implementation**: `/src/storage/kv_store.py`
- **Redis Connector** with:
  - Connection pooling
  - Performance metrics collection
  - DuckDB analytics integration
  - Configurable TTL and retention

---

## 3. Available APIs for `retrieve_context` with user_id & keys

### Current API Capabilities

#### Namespace Filtering (Indirect user_id support)
```python
# The retrieve_context supports namespace-based isolation
{
  "query": "specific user facts",
  "filters": {
    "namespaces": ["user_123", "user_456"]  # Filter by namespace
  },
  "search_mode": "kv"
}
```

**Note**: The current implementation doesn't have explicit `user_id` parameter in MCP contract, but the underlying fact_store supports:
- Fact key pattern: `facts:{namespace}:{user_id}:{attribute}`
- User facts retrieval: `get_user_facts(namespace, user_id)`

### REST API Route Capabilities

**Location**: `/src/api/routes/search.py`

```python
# API-level namespace support
@router.post("/search")
async def search_contexts(request: SearchRequest) -> SearchResponse:
    # request.namespaces: Optional[List[str]]
    # Filters results to specific namespaces
    
# Convenience filters converted to core FilterCriteria
pre_filters.extend(_create_convenience_filters(request))
```

### Recommended API Extension Points

For voice-bot integration with proper user_id support:

1. **Extend MCP retrieve_context contract** with:
   - `user_id` (optional): Direct user identifier
   - `namespace` (optional): Namespace override
   - `include_facts` (optional): Include fact_store data

2. **Add fact retrieval endpoint**:
   ```python
   # New MCP tool: retrieve_user_facts
   {
     "agent_id": "voice-bot-v1",
     "user_id": "telegram_user_123",
     "attributes": ["name", "preferences", "history"],  # or null for all
     "include_lineage": true
   }
   ```

---

## 4. Docker Setup & Network Configuration

### Docker Compose Architecture
**File**: `/docker-compose.yml`

#### Service Network
All services on `context-store-network` (Docker bridge):

```
Context Store (8000)
    ↓
  ├→ Qdrant (6333/6334) [Vector DB]
  ├→ Neo4j (7474/7687) [Graph DB]
  ├→ Redis (6379) [Cache/KV]
    ↓
REST API (8001)
    ↓
Monitoring Dashboard (8080)
    ↓
Sentinel (9090)
```

#### Service Connection URLs (Internal - Docker Network)
```
QDRANT_URL=http://qdrant:6333
NEO4J_URI=bolt://neo4j:7687
REDIS_URL=redis://redis:6379
```

#### Port Mappings (External - Host)
| Service | Container Port | Host Port | Protocol |
|---------|---|---|---|
| Context Store | 8000 | 8000 | HTTP |
| REST API | 8001 | 8001 | HTTP |
| Qdrant Vector DB | 6333 | 6333 | HTTP |
| Qdrant gRPC | 6334 | 6334 | gRPC |
| Neo4j HTTP | 7474 | 7474 | HTTP |
| Neo4j Bolt | 7687 | 7687 | Binary |
| Redis | 6379 | 6379 | Redis |
| Monitoring | 8080 | 8080 | HTTP |
| Sentinel | 9090 | 9090 | HTTP |

#### Health Checks
Each service has comprehensive health checks:
- Context Store: `curl -f http://localhost:8000/health`
- Redis: `redis-cli ping`
- Qdrant: `curl -f http://localhost:6333/`
- Neo4j: `wget --spider http://localhost:7474`

#### Volume Management
- `qdrant_data`: Vector database persistence
- `neo4j_data`, `neo4j_logs`: Graph database storage
- `redis_data`: KV store persistence
- `sentinel_data`: Monitoring history

### Docker Network Details

**Network Driver**: `bridge` (default)
**Isolation**: Each container can reach others by service name (DNS)

**For Voice-Bot Integration**:
1. If running in same Docker network: Use internal URLs (e.g., `http://context-store:8000`)
2. If external: Use host ports with public IP (e.g., `http://localhost:8000` or `http://veris-memory.fly.dev`)
3. SSL/TLS: Configured via `SSLConfigManager` with certificate validation

---

## 5. Existing Examples & Integration Patterns

### Example 1: Hello World MCP Client
**Location**: `/examples/hello_world.py`

```python
from src.mcp_server.main import app  # FastAPI app

# Direct requests to HTTP endpoints:
client = ContextStoreMCP(base_url="http://localhost:8000")

# Store context
result = client.call_tool("store_context", {
    "type": "design",
    "content": {"title": "API", "description": "..."},
    "metadata": {"author": "hello-world"}
})

# Retrieve context
results = client.call_tool("retrieve_context", {
    "query": "API design",
    "search_mode": "hybrid",
    "limit": 5
})

# Update scratchpad
client.call_tool("update_scratchpad", {
    "agent_id": "hello-world-agent",
    "key": "progress",
    "content": "Step 1 completed",
    "ttl": 3600
})

# Get agent state
state = client.call_tool("get_agent_state", {
    "agent_id": "hello-world-agent"
})
```

### Example 2: Direct Python MCP SDK Integration
**Location**: `/src/mcp_server/server.py`

Using official MCP SDK with stdio_server:

```python
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("context-store")

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    if name == "store_context":
        # Handle context storage
        pass
    elif name == "retrieve_context":
        # Handle context retrieval
        pass
```

### Example 3: Fact-Aware Search
**Location**: `/src/mcp_server/server.py` (Phase 2 integration)

```python
from src.storage.fact_store import FactStore
from src.core.intent_classifier import IntentClassifier

# Store user facts
fact_store.store_fact(
    namespace="voice_bot",
    user_id="telegram_123",
    attribute="name",
    value="Alice",
    confidence=1.0,
    source_turn_id="turn_42",
    provenance="user_input"
)

# Retrieve facts
user_facts = fact_store.get_user_facts("voice_bot", "telegram_123")
# Returns: {"name": Fact(...), "preferences": Fact(...), ...}

# Search with fact awareness
results = await retrieve_context(
    query="user preferences",
    search_mode="hybrid"
)
# RetrievalCore integrates facts into ranking
```

### Example 4: Docker Deployment Pattern

```bash
# Start all services
docker-compose up -d

# Wait for services to be healthy
sleep 60

# Test MCP server
curl http://localhost:8000/health

# Connect voice-bot via Docker network
# Inside voice-bot container:
# VERIS_URL=http://context-store:8000
# Connect to fact_store via Redis: redis://redis:6379
```

### Example 5: API vs MCP Protocol

**FastAPI HTTP Routes** (REST API):
```python
# POST /tools/store_context
# POST /tools/retrieve_context
# POST /tools/query_graph
# POST /tools/update_scratchpad
# POST /tools/get_agent_state
```

**MCP Protocol** (Stdio-based):
```python
# Same tool names but via MCP SDK
# Tools: store_context, retrieve_context, query_graph, update_scratchpad, get_agent_state
```

Both implement the same business logic; protocol difference is transport.

---

## 6. Voice-Bot Integration Recommendations

### Architecture Pattern

```
Voice Bot (Telegram/Discord)
    ↓
[Local MCP Client]
    ↓
Context Store MCP Server (HTTP or stdio)
    ↓
├→ Qdrant (semantic search)
├→ Neo4j (relationships)
├→ Redis (facts + scratchpad)
    ↓
[Real-time responses + persistent memory]
```

### Key Integration Points

#### 1. User Identity Management
```python
# Map voice platform user ID to Veris namespace
namespace = f"voicebot_{platform}_{user_id}"
# Example: "voicebot_telegram_123456789"

# Store user facts on conversation updates
fact_store.store_fact(
    namespace=namespace,
    user_id=user_id,  # Internal ID
    attribute="telegram_username",
    value="@alice",
    confidence=1.0
)
```

#### 2. Real-time Context Retrieval
```python
# On each message, retrieve relevant facts + context
user_facts = fact_store.get_user_facts(namespace, user_id)
context_results = await retrieve_context(
    query=user_message,
    namespaces=[namespace],  # Filtered to user
    search_mode="hybrid",
    limit=5
)
```

#### 3. Session Management via Scratchpad
```python
# Track conversation state
await update_scratchpad(
    agent_id="voicebot_v1",
    key=f"session:{user_id}",
    content=json.dumps({
        "turn_count": 42,
        "last_topic": "preferences",
        "context_ids": [...]
    }),
    mode="overwrite",
    ttl=3600  # 1 hour session
)
```

#### 4. Conversation Logging
```python
# Store complete conversation as context
await store_context(
    type="trace",  # Conversation trace
    content={
        "user_id": user_id,
        "messages": [{
            "role": "user",
            "content": "...",
            "timestamp": "2025-10-18T..."
        }],
        "summary": "Discussed preferences"
    },
    metadata={
        "source": "telegram_voice_bot",
        "tags": ["conversation", user_id]
    }
)
```

### Network Configuration for Voice-Bot

#### Option A: Docker-to-Docker (Same Machine)
```python
# In voice-bot container
context_store_url = "http://context-store:8000"
redis_url = "redis://redis:6379"

# Requires: same docker-compose network
```

#### Option B: External Voice-Bot
```python
# External host connects to Veris on localhost
context_store_url = "http://localhost:8000"  # or public IP
redis_url = "redis://localhost:6379"

# Requires: ports exposed from docker-compose
```

#### Option C: Cloud Deployment (Fly.io)
```python
# Production deployment
context_store_url = "https://veris-memory.fly.dev"
redis_url = "redis://redis.internal:6379"  # Fly.io private networks

# Already configured and deployed
```

---

## 7. Critical Implementation Details

### Embedding Service
- **Model**: `all-MiniLM-L6-v2` (configurable via EMBEDDING_MODEL env var)
- **Dimensions**: 384 (must match Qdrant collection)
- **Fallback**: Hash-based embeddings if sentence-transformers unavailable (NOT recommended)
- **Semantic**: Full sentence-transformers semantic embeddings (NOT hash-based)

### Query Validation
- **Cypher**: CypherValidator prevents write operations and injection
- **MCP Requests**: validate_mcp_request checks against contract specs
- **Content**: ContentTypeValidator ensures type safety

### Rate Limiting
- Analytics: 5 req/min
- Dashboard: 20 req/min
- Per-IP tracking with user-agent hashing

### Error Handling
- Secure error responses (sanitized for external clients)
- Request ID tracking for debugging
- Structured logging with context

### Metrics Collection
- Request latency per endpoint
- Backend response times (vector, graph, kv)
- Error rates and types
- Dashboard streaming via WebSocket

---

## Summary: What Voice-Bot Needs

| Requirement | Veris Implementation | Status |
|---|---|---|
| User-scoped memory | FactStore with namespace/user_id | ✅ Complete |
| Key-value facts | `store_fact()`, `get_user_facts()`, `get_fact()` | ✅ Complete |
| Real-time retrieval | `retrieve_context` with hybrid search | ✅ Complete |
| Conversation history | `store_context` with type="trace" | ✅ Complete |
| Session state | `update_scratchpad` with TTL | ✅ Complete |
| Relationship tracking | Neo4j graph with `query_graph` | ✅ Complete |
| Semantic search | Qdrant + sentence-transformers | ✅ Complete |
| Docker deployment | docker-compose.yml fully configured | ✅ Complete |
| MCP protocol | Official SDK implementation | ✅ Complete |
| Health monitoring | /health, /health/detailed, /status | ✅ Complete |

