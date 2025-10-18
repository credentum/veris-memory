# Sprint 13 API Documentation

**Version**: 1.0
**Last Updated**: 2025-10-18
**Sprint**: 13 - Critical Fixes and Enhancements

---

## Overview

Sprint 13 introduces critical enhancements to the Veris Memory MCP server, including:

1. **Embedding Pipeline Visibility** - Clear feedback on embedding status
2. **API Key Authentication** - Secure, role-based access control
3. **Memory Management** - Redis TTL management and data persistence
4. **Namespace Management** - Multi-tenant organization
5. **Relationship Auto-Detection** - Automatic graph relationship creation
6. **Enhanced Tool Discovery** - Comprehensive /tools endpoint

---

## Table of Contents

1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [New Endpoints (Sprint 13)](#new-endpoints)
4. [Request/Response Models](#request-response-models)
5. [Error Handling](#error-handling)
6. [Examples](#examples)

---

## Authentication

### API Key Authentication (Phase 2)

All endpoints support optional API key authentication via:

**Header Option 1: X-API-Key**
```http
X-API-Key: vmk_your_api_key_here
```

**Header Option 2: Authorization Bearer**
```http
Authorization: Bearer vmk_your_api_key_here
```

### API Key Format

```
API_KEY_{NAME}=key:user_id:role:is_agent
```

**Example**:
```bash
API_KEY_ADMIN=vmk_admin_secret:admin_user:admin:false
API_KEY_AGENT=vmk_agent_key:ai_assistant:writer:true
```

### Roles and Capabilities

| Role | Capabilities | Description |
|------|-------------|-------------|
| `admin` | all | Full access including deletions |
| `writer` | read, write, query, cache | Can create and read contexts |
| `reader` | read, query | Read-only access |
| `guest` | read | Limited read access |

### Human-Only Operations

The following operations require `is_agent=false` (human authentication):

- `DELETE /tools/delete_context` - Hard delete
- `POST /tools/forget_context` - Soft delete (retention period)

**Reason**: Prevents AI agents from accidentally or maliciously deleting data.

---

## Core Endpoints

### 1. Store Context

**Endpoint**: `POST /tools/store_context`

**Description**: Store a new context with embeddings and graph relationships.

**Sprint 13 Enhancements**:
- Returns `embedding_status` in response
- Auto-populates `author` and `author_type` from API key
- Auto-detects and creates graph relationships
- Auto-assigns namespace based on content

**Request Body**:
```json
{
  "type": "design|code|decision|reference|sprint",
  "content": {
    "title": "String (optional)",
    "description": "String (optional)",
    "text": "String (optional)",
    "... additional fields"
  },
  "metadata": {
    "sprint": "String (optional)",
    "project_id": "String (optional)",
    "team_id": "String (optional)",
    "... additional metadata"
  },
  "author": "String (optional, auto-populated)",
  "author_type": "human|agent (optional, auto-populated)"
}
```

**Response** (Success):
```json
{
  "success": true,
  "context_id": "uuid-string",
  "vector_id": "uuid-string",
  "graph_id": "internal-id",
  "embedding_status": "completed|failed|unavailable",
  "embedding_message": "String (if failed)",
  "relationships_created": 3,
  "namespace": "/project/veris-memory/context"
}
```

**Embedding Status Values**:
- `completed` - Embedding generated successfully
- `failed` - Embedding generation failed (check `embedding_message`)
- `unavailable` - Embedding service not initialized

**Example**:
```bash
curl -X POST http://localhost:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vmk_admin_key" \
  -d '{
    "type": "sprint",
    "content": {
      "sprint_number": 13,
      "title": "Critical Fixes Sprint",
      "description": "Fixes embedding pipeline, adds auth. Closes issue #123.",
      "project_id": "veris-memory"
    },
    "metadata": {
      "sprint": "13",
      "status": "active"
    }
  }'
```

**Relationship Auto-Detection** (Phase 4):
The system automatically detects and creates these relationships:
- `FIXES` → issue_123 (detected "Closes issue #123")
- `PART_OF` → sprint_13 (from metadata.sprint)
- `PART_OF` → project_veris-memory (from content.project_id)
- `PRECEDED_BY` → Sprint 12 (if exists, temporal detection)

---

### 2. Retrieve Context

**Endpoint**: `POST /tools/retrieve_context`

**Description**: Hybrid semantic + graph search for contexts.

**Sprint 13 Enhancements**:
- Default limit reduced from 10 to 5
- Enhanced validation (min: 1, max: 100)

**Request Body**:
```json
{
  "query": "String (required)",
  "limit": 5,
  "filters": {
    "type": "String (optional)",
    "metadata": {}
  }
}
```

**Response**:
```json
{
  "results": [
    {
      "context_id": "uuid",
      "type": "sprint",
      "content": {...},
      "metadata": {...},
      "score": 0.92,
      "author": "admin_user",
      "author_type": "human"
    }
  ],
  "total_results": 5,
  "search_mode": "hybrid"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -d '{
    "query": "embedding pipeline fixes",
    "limit": 3,
    "filters": {
      "type": "sprint"
    }
  }'
```

---

### 3. Query Graph

**Endpoint**: `POST /tools/query_graph`

**Description**: Execute Cypher queries on the knowledge graph.

**Sprint 13 Enhancements**:
- Auto-created relationships available for querying
- New relationship types: PRECEDED_BY, FOLLOWED_BY, PART_OF, IMPLEMENTS, FIXES, REFERENCES

**Request Body**:
```json
{
  "query": "MATCH (c:Context)-[r]->(t) WHERE c.type = 'sprint' RETURN c, r, t LIMIT 10"
}
```

**Response**:
```json
{
  "results": [
    {
      "c": {"id": "uuid", "type": "sprint", "sprint_number": 13},
      "r": {"type": "PRECEDED_BY", "reason": "Previous sprint"},
      "t": {"id": "uuid2", "type": "sprint", "sprint_number": 12}
    }
  ],
  "total_results": 1
}
```

**Example - Find All Sprint Relationships**:
```bash
curl -X POST http://localhost:8000/tools/query_graph \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MATCH (s:Context {type: \"sprint\"})-[r]->() RETURN s.sprint_number, type(r), r.reason LIMIT 20"
  }'
```

---

### 4. Update Scratchpad

**Endpoint**: `POST /tools/update_scratchpad`

**Description**: Update Redis cache with TTL management.

**Sprint 13 Enhancements**:
- Automatic TTL assignment based on key type
- Event logging for all operations
- Hourly sync to Neo4j for persistence

**Request Body**:
```json
{
  "agent_id": "String (required)",
  "key": "String (required)",
  "value": "String (required)",
  "ttl": 3600
}
```

**Response**:
```json
{
  "success": true,
  "key": "scratchpad:agent_id:key",
  "ttl": 3600,
  "expiration": "2025-10-18T14:30:00"
}
```

**TTL Defaults** (Phase 3):
- `scratchpad:*` - 1 hour (3600s)
- `session:*` - 7 days (604800s)
- `cache:*` - 5 minutes (300s)
- `temporary:*` - 1 minute (60s)
- `persistent:*` - 30 days (2592000s)

**Example**:
```bash
curl -X POST http://localhost:8000/tools/update_scratchpad \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "ai_assistant",
    "key": "current_task",
    "value": "Implementing Sprint 13 features",
    "ttl": 7200
  }'
```

---

### 5. Get Agent State

**Endpoint**: `POST /tools/get_agent_state`

**Description**: Retrieve agent state from scratchpad.

**Request Body**:
```json
{
  "agent_id": "String (required)",
  "keys": ["String (optional)"]
}
```

**Response**:
```json
{
  "agent_id": "ai_assistant",
  "state": {
    "current_task": "Implementing Sprint 13 features",
    "last_updated": "2025-10-18T12:00:00"
  },
  "ttl": {
    "current_task": 5400
  }
}
```

---

## New Endpoints (Sprint 13)

### 6. Delete Context (Phase 2)

**Endpoint**: `POST /tools/delete_context`

**Description**: Hard delete a context (human-only operation).

**Authentication**: Requires human API key (`is_agent=false`)

**Request Body**:
```json
{
  "context_id": "uuid-string",
  "reason": "String (required, min 5 chars)",
  "hard_delete": false
}
```

**Response**:
```json
{
  "success": true,
  "context_id": "uuid-string",
  "deleted_from": ["qdrant", "neo4j", "redis"],
  "audit_log_id": "audit-uuid"
}
```

**Error (AI Agent Attempt)**:
```json
{
  "success": false,
  "error": "Delete operations require human authentication",
  "context_id": "uuid-string"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/tools/delete_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vmk_admin_key" \
  -d '{
    "context_id": "abc-123-def-456",
    "reason": "Duplicate context, marked for removal"
  }'
```

---

### 7. Forget Context (Phase 2/3)

**Endpoint**: `POST /tools/forget_context`

**Description**: Soft-delete a context with retention period.

**Request Body**:
```json
{
  "context_id": "uuid-string",
  "reason": "String (required, min 5 chars)",
  "retention_days": 30
}
```

**Response**:
```json
{
  "success": true,
  "context_id": "uuid-string",
  "status": "forgotten",
  "retention_until": "2025-11-17T12:00:00",
  "audit_log_id": "audit-uuid"
}
```

**Retention Period**:
- Minimum: 1 day
- Maximum: 90 days
- Default: 30 days

Context is marked as deleted but retained for the specified period, then permanently removed.

**Example**:
```bash
curl -X POST http://localhost:8000/tools/forget_context \
  -H "Content-Type: application/json" \
  -d '{
    "context_id": "old-test-123",
    "reason": "Test data no longer needed",
    "retention_days": 7
  }'
```

---

### 8. Tool Discovery (Phase 4)

**Endpoint**: `GET /tools`

**Description**: Comprehensive tool discovery with schemas and examples.

**Response Structure**:
```json
{
  "tools": [
    {
      "name": "store_context",
      "description": "Store context with embeddings and graph relationships",
      "endpoint": "/tools/store_context",
      "method": "POST",
      "available": true,
      "requires_auth": true,
      "capabilities": ["write", "store"],
      "human_only": false,
      "input_schema": {
        "type": "object",
        "required": ["content", "type"],
        "properties": {...}
      },
      "output_schema": {
        "type": "object",
        "properties": {...}
      },
      "example": {...}
    }
  ],
  "total_tools": 7,
  "available_tools": 7,
  "capabilities": ["write", "store", "read", "search", "query", "graph", "cache", "state", "delete", "admin", "forget"],
  "sprint_13_enhancements": [
    "embedding_status_tracking",
    "api_key_authentication",
    "namespace_management",
    "relationship_auto_detection",
    "delete_forget_operations"
  ]
}
```

**Example**:
```bash
curl -X GET http://localhost:8000/tools
```

**Use Cases**:
- MCP client auto-discovery
- API documentation generation
- Client SDK generation
- Capability-based routing

---

### 9. Health Check (Enhanced - Phase 1)

**Endpoint**: `GET /health/detailed`

**Description**: Detailed health status including embedding pipeline.

**Sprint 13 Enhancements**:
- Embedding service status
- Embedding pipeline diagnostics
- Test embedding verification

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-18T12:00:00",
  "qdrant": {
    "healthy": true,
    "collections": 3,
    "embedding_service_loaded": true,
    "test_embedding_successful": true,
    "embedding_dimensions": 384
  },
  "neo4j": {
    "healthy": true,
    "connected": true
  },
  "redis": {
    "healthy": true,
    "connected": true,
    "memory_usage": "15.2 MB"
  },
  "embedding_pipeline": {
    "status": "operational",
    "model": "all-MiniLM-L6-v2",
    "dimensions": 384
  }
}
```

**Error State Example**:
```json
{
  "status": "degraded",
  "qdrant": {
    "healthy": false,
    "embedding_service_loaded": false,
    "error": "sentence-transformers not installed",
    "warning": "New contexts will NOT be searchable via semantic similarity"
  }
}
```

**Example**:
```bash
curl -X GET http://localhost:8000/health/detailed
```

---

## Request/Response Models

### Context Types

- `code` - Code snippets, implementations
- `design` - Design documents, architecture
- `decision` - Decision records, ADRs
- `reference` - Reference materials, links
- `sprint` - Sprint plans, summaries

### Metadata Fields

**Standard Fields**:
```json
{
  "author": "String - user_id from API key",
  "author_type": "human|agent",
  "created_at": "ISO 8601 timestamp",
  "sprint": "String - sprint identifier",
  "project_id": "String - project identifier",
  "team_id": "String - team identifier",
  "namespace": "String - namespace path"
}
```

**Namespace Auto-Assignment** (Phase 4):
```
Content has project_id → /project/{project_id}/context
Content has team_id → /team/{team_id}/context
API key has user_id → /user/{user_id}/context
Default → /global/default
```

### Relationship Types (Phase 4)

| Type | Description | Example |
|------|-------------|---------|
| `RELATES_TO` | General semantic relationship | Context A relates to Context B |
| `DEPENDS_ON` | Dependency relationship | Feature depends on infrastructure |
| `PRECEDED_BY` | Temporal sequence | Sprint 13 preceded by Sprint 12 |
| `FOLLOWED_BY` | Temporal sequence | Sprint 12 followed by Sprint 13 |
| `PART_OF` | Hierarchical containment | Context is part of Sprint 13 |
| `IMPLEMENTS` | Implementation relationship | Code implements design |
| `FIXES` | Bug fix relationship | Commit fixes issue #123 |
| `REFERENCES` | Reference relationship | Document references PR #456 |

**Auto-Detection Examples**:
- `"Fixes issue #123"` → Creates `FIXES` relationship to `issue_123`
- `"See PR #456"` → Creates `REFERENCES` relationship to `pr_456`
- `metadata.sprint = "13"` → Creates `PART_OF` relationship to `sprint_13`
- Sequential contexts → Creates `PRECEDED_BY`/`FOLLOWED_BY` relationships

---

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "Error message here",
  "error_code": "ERROR_CODE",
  "details": {...}
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTH_REQUIRED` | 401 | API key required but not provided |
| `AUTH_INVALID` | 401 | API key invalid or expired |
| `AUTH_INSUFFICIENT` | 403 | API key lacks required capabilities |
| `HUMAN_REQUIRED` | 403 | Operation requires human authentication |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `EMBEDDING_FAILED` | 500 | Embedding generation failed |
| `STORAGE_ERROR` | 500 | Backend storage error |

### Example Error Responses

**Invalid API Key**:
```json
{
  "success": false,
  "error": "Invalid API key",
  "error_code": "AUTH_INVALID"
}
```

**Agent Delete Attempt**:
```json
{
  "success": false,
  "error": "Delete operations require human authentication. AI agents cannot delete contexts.",
  "error_code": "HUMAN_REQUIRED",
  "context_id": "abc-123"
}
```

**Embedding Failed**:
```json
{
  "success": true,
  "context_id": "abc-123",
  "embedding_status": "failed",
  "embedding_message": "sentence-transformers not installed. Context stored in graph only.",
  "warning": "Semantic search will not work for this context"
}
```

---

## Examples

### Complete Workflow Example

```bash
# 1. Check system health
curl -X GET http://localhost:8000/health/detailed

# 2. Discover available tools
curl -X GET http://localhost:8000/tools

# 3. Store a sprint context (with auth)
curl -X POST http://localhost:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vmk_admin_key" \
  -d '{
    "type": "sprint",
    "content": {
      "sprint_number": 13,
      "title": "Critical Fixes and Enhancements",
      "goals": ["Fix embedding pipeline", "Add authentication"],
      "status": "completed",
      "project_id": "veris-memory"
    },
    "metadata": {
      "sprint": "13",
      "start_date": "2025-10-01",
      "end_date": "2025-10-15"
    }
  }'

# Response includes:
# - embedding_status: "completed"
# - relationships_created: 3 (PART_OF project, PART_OF sprint, PRECEDED_BY sprint 12)
# - namespace: "/project/veris-memory/context"

# 4. Search for the context
curl -X POST http://localhost:8000/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -d '{
    "query": "sprint 13 embedding fixes",
    "limit": 5
  }'

# 5. Query graph relationships
curl -X POST http://localhost:8000/tools/query_graph \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MATCH (s:Context {type: \"sprint\", sprint_number: 13})-[r]->() RETURN r.type, r.reason"
  }'

# 6. Update agent scratchpad
curl -X POST http://localhost:8000/tools/update_scratchpad \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "claude",
    "key": "last_sprint",
    "value": "Sprint 13 completed successfully",
    "ttl": 604800
  }'

# 7. Soft-delete old test context
curl -X POST http://localhost:8000/tools/forget_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vmk_admin_key" \
  -d '{
    "context_id": "old-test-123",
    "reason": "Test data cleanup",
    "retention_days": 7
  }'
```

---

## Migration Notes

### From Pre-Sprint-13

**Breaking Changes**: None - all changes are backward compatible

**New Optional Fields**:
- `author` - auto-populated from API key if not provided
- `author_type` - auto-populated as "human" or "agent"
- `namespace` - auto-assigned based on content

**Behavioral Changes**:
1. **Default Search Limit**: Changed from 10 to 5 results
2. **Embedding Status**: All responses include `embedding_status`
3. **Relationship Creation**: Automatic graph relationship detection
4. **TTL Management**: Redis keys now have automatic TTLs

**Recommended Actions**:
1. Set up API keys for production use
2. Review embedding status in health checks
3. Enable authentication (`AUTH_REQUIRED=true`)
4. Monitor relationship auto-detection stats

---

## Performance Considerations

### Response Times (Typical)

| Endpoint | Typical | Max |
|----------|---------|-----|
| `GET /tools` | <10ms | 50ms |
| `GET /health/detailed` | <50ms | 200ms |
| `POST /tools/store_context` | 200-500ms | 2s |
| `POST /tools/retrieve_context` | 100-300ms | 1s |
| `POST /tools/query_graph` | 50-200ms | 500ms |

**Factors Affecting Performance**:
- Embedding generation: +100-300ms
- Relationship detection: +50-200ms
- Neo4j relationship creation: +10-50ms per relationship
- Redis TTL operations: +1-5ms

### Rate Limiting

**Current Status**: Not enforced in Sprint 13 (planned for future sprint)

**Recommended Limits** (to be implemented):

| User Type | Limit | Burst | Time Window |
|-----------|-------|-------|-------------|
| Anonymous (AUTH_REQUIRED=false) | 10 req/min | 20 req | 60 seconds |
| Guest (reader role) | 30 req/min | 50 req | 60 seconds |
| Reader | 60 req/min | 100 req | 60 seconds |
| Writer | 100 req/min | 200 req | 60 seconds |
| Admin | Unlimited | - | - |

**Endpoint-Specific Limits** (recommended):

| Endpoint | Limit | Reason |
|----------|-------|--------|
| POST /tools/store_context | 10 req/min | Expensive (embedding + graph) |
| POST /tools/retrieve_context | 60 req/min | Moderate (vector search) |
| POST /tools/query_graph | 30 req/min | Moderate (graph query) |
| POST /tools/delete_context | 5 req/min | Destructive operation |
| POST /tools/forget_context | 10 req/min | Destructive operation |
| GET /tools | 120 req/min | Lightweight (metadata) |
| GET /health/* | 300 req/min | Monitoring endpoint |

**Rate Limit Headers** (to be implemented):
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1697654400
Retry-After: 60
```

**Rate Limit Response** (HTTP 429):
```json
{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "limit": 100,
  "remaining": 0,
  "reset_at": "2025-10-18T13:00:00Z",
  "retry_after": 60
}
```

**Implementation Notes**:
- Use Redis-based rate limiter for distributed systems
- Per-API-key tracking (not IP-based to avoid proxy issues)
- Separate limits for different endpoints
- Burst allowance for bursty workloads
- Admin keys exempt from rate limiting

**Workaround Until Implementation**:
- Use application-level rate limiting
- Monitor via Prometheus metrics
- Set up alerts for unusual request patterns

---

## Support and Troubleshooting

### Common Issues

**1. Embedding Status: "unavailable"**
- **Cause**: `sentence-transformers` not installed
- **Fix**: `pip install sentence-transformers`
- **Impact**: Semantic search will not work

**2. API Key Authentication Failing**
- **Cause**: Incorrect header format or key
- **Fix**: Use `X-API-Key: vmk_key` or `Authorization: Bearer vmk_key`

**3. Delete Operation Blocked**
- **Cause**: Attempting delete with agent API key
- **Fix**: Use human API key (`is_agent=false`)

**4. Relationships Not Created**
- **Cause**: Neo4j not available or content doesn't match patterns
- **Fix**: Check Neo4j connection, verify content has references

### Debug Endpoints

```bash
# Check embedding pipeline
curl http://localhost:8000/health/detailed | jq '.qdrant'

# Check relationship detection stats
curl http://localhost:8000/stats/relationships

# Check namespace stats
curl http://localhost:8000/stats/namespaces
```

---

## Appendix: API Key Setup

### Environment Configuration

```bash
# .env file
AUTH_REQUIRED=true

# Admin key (human)
API_KEY_ADMIN=vmk_admin_secret:admin_user:admin:false

# Writer key (human)
API_KEY_WRITER=vmk_writer_key:writer_user:writer:false

# Agent key
API_KEY_AGENT=vmk_agent_key:ai_assistant:writer:true

# Reader key
API_KEY_READER=vmk_reader_key:read_user:reader:false
```

### Key Generation

```python
import secrets

def generate_api_key(prefix="vmk"):
    return f"{prefix}_{secrets.token_urlsafe(32)}"

print(generate_api_key())
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-18 | Initial Sprint 13 documentation |

---

## Contact

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/credentum/veris-memory/issues
- Documentation: https://github.com/credentum/veris-memory/docs
