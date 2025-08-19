# MCP Tools Documentation

The Context Store provides 5 MCP tools for comprehensive context management. Each tool is designed for specific use cases and supports graceful degradation when storage backends are unavailable.

## Overview

| Tool                | Purpose                                         | Storage        | Rate Limited |
| ------------------- | ----------------------------------------------- | -------------- | ------------ |
| `store_context`     | Store context with embeddings and relationships | Vector + Graph | ✅           |
| `retrieve_context`  | Hybrid search across stored contexts            | Vector + Graph | ✅           |
| `query_graph`       | Execute read-only Cypher queries                | Graph          | ✅           |
| `update_scratchpad` | Transient storage with TTL                      | Key-Value      | ✅           |
| `get_agent_state`   | Retrieve agent state with isolation             | Key-Value      | ✅           |

## 1. store_context

Store context data with vector embeddings and graph relationships for semantic search and traversal.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "content": {
      "type": "object",
      "description": "Context content to store (required)"
    },
    "type": {
      "type": "string",
      "enum": ["design", "decision", "trace", "sprint", "log"],
      "description": "Type of context (required)"
    },
    "metadata": {
      "type": "object",
      "description": "Additional metadata (optional)"
    },
    "relationships": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "target": { "type": "string" },
          "type": { "type": "string" }
        }
      },
      "description": "Graph relationships to create (optional)"
    }
  },
  "required": ["content", "type"]
}
```

### Example Request

```json
{
  "method": "call_tool",
  "params": {
    "name": "store_context",
    "arguments": {
      "type": "design",
      "content": {
        "title": "User Authentication API",
        "description": "JWT-based authentication system",
        "components": ["auth-service", "user-db", "session-cache"]
      },
      "metadata": {
        "author": "developer@company.com",
        "priority": "high",
        "epic": "auth-system-v2"
      },
      "relationships": [
        { "type": "implements", "target": "req-auth-001" },
        { "type": "depends_on", "target": "ctx_user_db_design" }
      ]
    }
  }
}
```

### Success Response

```json
{
  "success": true,
  "id": "ctx_abc123def456",
  "vector_id": "ctx_abc123def456",
  "graph_id": "ctx_abc123def456",
  "message": "Context stored successfully in all backends",
  "backend_status": {
    "vector": "success",
    "graph": "success"
  }
}
```

### Error Response

```json
{
  "success": false,
  "id": null,
  "message": "Rate limit exceeded: 100 requests per minute",
  "error_type": "rate_limit"
}
```

### Error Types

- `rate_limit` - Rate limit exceeded
- `validation_error` - Invalid input data
- `storage_error` - Backend storage failure

---

## 2. retrieve_context

Retrieve context using hybrid vector similarity and graph search with multiple search modes.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query (required)"
    },
    "type": {
      "type": "string",
      "default": "all",
      "description": "Context type filter (optional)"
    },
    "search_mode": {
      "type": "string",
      "enum": ["vector", "graph", "hybrid"],
      "default": "hybrid",
      "description": "Search strategy (optional)"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100,
      "default": 10,
      "description": "Maximum results to return (optional)"
    },
    "sort_by": {
      "type": "string",
      "enum": ["timestamp", "relevance"],
      "default": "timestamp",
      "description": "Sort order for results. 'timestamp' returns newest first, 'relevance' returns highest score first"
    }
  },
  "required": ["query"]
}
```

### Example Request

```json
{
  "method": "call_tool",
  "params": {
    "name": "retrieve_context",
    "arguments": {
      "query": "authentication JWT security",
      "type": "design",
      "search_mode": "hybrid",
      "limit": 5
    }
  }
}
```

### Success Response

```json
{
  "success": true,
  "results": [
    {
      "id": "ctx_abc123def456",
      "score": 0.85,
      "source": "vector",
      "payload": {
        "content": {
          "title": "User Authentication API",
          "description": "JWT-based authentication system"
        },
        "type": "design",
        "metadata": {
          "author": "developer@company.com",
          "priority": "high"
        }
      }
    },
    {
      "id": "ctx_def789ghi012",
      "type": "design",
      "content": {
        "title": "OAuth Integration",
        "description": "Third-party OAuth providers"
      },
      "source": "graph",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total_count": 2,
  "search_mode_used": "hybrid",
  "message": "Found 2 matching contexts"
}
```

### Error Response

```json
{
  "success": false,
  "results": [],
  "message": "Rate limit exceeded: 50 searches per minute",
  "error_type": "rate_limit"
}
```

---

## 3. query_graph

Execute read-only Cypher queries on the graph database for advanced analysis and traversal.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Cypher query (read-only, required)"
    },
    "parameters": {
      "type": "object",
      "description": "Query parameters (optional)"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100,
      "description": "Maximum results to return (optional)"
    }
  },
  "required": ["query"]
}
```

### Example Request

```json
{
  "method": "call_tool",
  "params": {
    "name": "query_graph",
    "arguments": {
      "query": "MATCH (n:Context)-[r:IMPLEMENTS]->(req) WHERE n.type = $type RETURN n.id, n.content, r.type, req.id",
      "parameters": { "type": "design" },
      "limit": 20
    }
  }
}
```

### Success Response

```json
{
  "success": true,
  "results": [
    {
      "n.id": "ctx_abc123def456",
      "n.content": "{\"title\":\"User Authentication API\",\"description\":\"JWT-based system\"}",
      "r.type": "implements",
      "req.id": "req-auth-001"
    }
  ],
  "row_count": 1
}
```

### Error Response

```json
{
  "success": false,
  "error": "Query validation failed: Write operations not allowed",
  "error_type": "forbidden_operation"
}
```

### Security Restrictions

- Only read operations allowed (`MATCH`, `RETURN`, `WHERE`, `ORDER BY`, `LIMIT`)
- Write operations blocked (`CREATE`, `DELETE`, `SET`, `REMOVE`, `MERGE`, `DROP`)
- Query complexity analysis prevents resource exhaustion
- Parameter validation prevents injection attacks

---

## 4. update_scratchpad

Update agent scratchpad with transient storage, TTL support, and namespace isolation.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "description": "Agent identifier (required)"
    },
    "key": {
      "type": "string",
      "description": "Scratchpad data key (required)"
    },
    "content": {
      "type": "string",
      "description": "Content to store (required)"
    },
    "mode": {
      "type": "string",
      "enum": ["overwrite", "append"],
      "default": "overwrite",
      "description": "Update mode (optional)"
    },
    "ttl": {
      "type": "integer",
      "minimum": 60,
      "maximum": 86400,
      "default": 3600,
      "description": "Time to live in seconds (optional)"
    }
  },
  "required": ["agent_id", "key", "content"]
}
```

### Example Request

```json
{
  "method": "call_tool",
  "params": {
    "name": "update_scratchpad",
    "arguments": {
      "agent_id": "agent-auth-dev-001",
      "key": "current_task",
      "content": "Implementing JWT token validation middleware",
      "mode": "overwrite",
      "ttl": 7200
    }
  }
}
```

### Success Response

```json
{
  "success": true,
  "message": "Scratchpad updated successfully (mode: overwrite)",
  "key": "agent:agent-auth-dev-001:scratchpad:current_task",
  "ttl": 7200,
  "content_size": 42
}
```

### Error Response

```json
{
  "success": false,
  "message": "Invalid agent ID format: agent-invalid@id",
  "error_type": "invalid_agent_id"
}
```

### Error Types

- `rate_limit` - Rate limit exceeded
- `invalid_agent_id` - Agent ID format validation failed
- `invalid_key` - Key format validation failed
- `invalid_content_type` - Content must be string
- `content_too_large` - Content exceeds 100KB limit
- `invalid_ttl` - TTL outside allowed range (60-86400 seconds)
- `storage_unavailable` - Redis not available
- `storage_error` - Redis operation failed

---

## 5. get_agent_state

Retrieve agent state with namespace isolation and prefix filtering.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "description": "Agent identifier (required)"
    },
    "key": {
      "type": "string",
      "description": "Specific state key to retrieve (optional)"
    },
    "prefix": {
      "type": "string",
      "enum": ["state", "scratchpad", "memory", "config"],
      "default": "state",
      "description": "State type to retrieve (optional)"
    }
  },
  "required": ["agent_id"]
}
```

### Example Request (Specific Key)

```json
{
  "method": "call_tool",
  "params": {
    "name": "get_agent_state",
    "arguments": {
      "agent_id": "agent-auth-dev-001",
      "key": "current_task",
      "prefix": "scratchpad"
    }
  }
}
```

### Success Response (Specific Key)

```json
{
  "success": true,
  "data": {
    "key": "current_task",
    "content": "Implementing JWT token validation middleware",
    "namespaced_key": "agent:agent-auth-dev-001:scratchpad:current_task"
  },
  "message": "State retrieved successfully"
}
```

### Example Request (All Keys)

```json
{
  "method": "call_tool",
  "params": {
    "name": "get_agent_state",
    "arguments": {
      "agent_id": "agent-auth-dev-001",
      "prefix": "scratchpad"
    }
  }
}
```

### Success Response (All Keys)

```json
{
  "success": true,
  "data": {
    "current_task": "Implementing JWT token validation middleware",
    "progress": "Completed authentication service setup",
    "notes": "Need to add error handling for expired tokens"
  },
  "keys": ["current_task", "progress", "notes"],
  "message": "Retrieved 3 scratchpad entries",
  "total_available": 3
}
```

### Error Response

```json
{
  "success": false,
  "data": {},
  "message": "Key 'nonexistent' not found",
  "error_type": "key_not_found"
}
```

### Error Types

- `rate_limit` - Rate limit exceeded
- `invalid_agent_id` - Agent ID format validation failed
- `invalid_prefix` - Invalid prefix value
- `invalid_key` - Key format validation failed
- `key_not_found` - Requested key doesn't exist
- `access_denied` - Agent doesn't have access to resource
- `storage_unavailable` - Redis not available
- `storage_exception` - Redis operation failed

---

## Rate Limiting

All tools implement rate limiting with the following defaults:

- **store_context**: 100 requests per minute
- **retrieve_context**: 50 requests per minute
- **query_graph**: 30 requests per minute
- **update_scratchpad**: 200 requests per minute
- **get_agent_state**: 100 requests per minute

Rate limit exceeded responses include:

```json
{
  "success": false,
  "message": "Rate limit exceeded: 50 requests per minute",
  "error_type": "rate_limit"
}
```

## Graceful Degradation

Tools gracefully handle backend failures:

- **Vector DB unavailable**: Falls back to graph search only
- **Graph DB unavailable**: Falls back to vector search only
- **Redis unavailable**: Returns storage unavailable error
- **All backends unavailable**: Returns partial success with warnings

## Security Features

- **Input validation**: Comprehensive schema validation
- **Query validation**: Read-only Cypher query enforcement
- **Namespace isolation**: Agent data segregation
- **Rate limiting**: Prevents resource exhaustion
- **Content size limits**: Prevents memory exhaustion
- **TTL enforcement**: Automatic data expiration

## Next Steps

- See [Quick Start Guide](QUICKSTART.md) for deployment
- Try the [Hello World Example](../examples/hello_world.py)
- Read [Architecture Overview](ARCHITECTURE.md) for system design
- Check [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues
