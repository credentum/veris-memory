# API Response Formats

This document describes the current API response formats and addresses breaking changes reported in Issue #48.

## Overview

Veris Memory has evolved its API response formats to provide more structured and consistent data. This document helps developers understand the current formats and migrate from older versions.

## Store Context Response Format

### Current Format (v0.9.0+)

```json
{
  "success": true,
  "id": "uuid-string",
  "vector_id": "uuid-string",
  "graph_id": "node-id",
  "message": "Context stored successfully"
}
```

### Legacy Format (v0.4.x - DEPRECATED)

```json
{
  "success": true,
  "context_id": "uuid-string",
  "stored_in": ["vector", "graph"]
}
```

## Retrieve Context Response Format

### Current Format (v0.9.0+)

**Vector Search Results:**
```json
{
  "success": true,
  "results": [
    {
      "id": "uuid-string",
      "content": {
        "text": "My name is Matt",
        "type": "decision",
        "title": "User Name",
        "fact_type": "personal_info"
      },
      "score": 0.95,
      "source": "vector"
    }
  ],
  "total_count": 1,
  "search_mode_used": "hybrid",
  "message": "Found 1 matching contexts"
}
```

**Graph Search Results:**
```json
{
  "success": true,
  "results": [
    {
      "n": {
        "id": "node-123",
        "type": "decision",
        "text": "My name is Matt",
        "title": "User Name"
      }
    }
  ],
  "total_count": 1,
  "search_mode_used": "graph"
}
```

### Legacy Format (v0.4.x - DEPRECATED)

```json
{
  "success": true,
  "contexts": [
    {
      "user_message": "What is my name?",
      "assistant_response": "I don't have your name saved yet",
      "exchange_type": "qa",
      "metadata": {...}
    }
  ]
}
```

## Breaking Changes from v0.4.x to v0.9.0

### 1. Field Name Changes

| Legacy Field | Current Field | Notes |
|-------------|---------------|-------|
| `user_message` | `text` | Content now in structured format |
| `assistant_response` | `type` + `title` | Semantic categorization |
| `exchange_type` | `fact_type` | More specific typing |
| `contexts` | `results` | Consistent naming |
| `context_id` | `id` | Simplified |

### 2. Structure Changes

**Legacy nested conversation format:**
```json
{
  "user_message": "My name is Matt",
  "assistant_response": "Nice to meet you, Matt!",
  "exchange_type": "introduction"
}
```

**Current semantic format:**
```json
{
  "text": "My name is Matt",
  "type": "decision", 
  "title": "User Name",
  "fact_type": "personal_info"
}
```

### 3. Response Wrapper Changes

**Legacy:**
```json
{
  "success": true,
  "contexts": [...],
  "count": 5
}
```

**Current:**
```json
{
  "success": true,
  "results": [...],
  "total_count": 5,
  "search_mode_used": "hybrid",
  "message": "Found 5 matching contexts"
}
```

## Readiness Check Format

### Current Format (v0.9.0+)

```json
{
  "ready": true,
  "readiness_level": "FULL",
  "readiness_score": 100,
  "service_status": {
    "core_services": {
      "redis": "healthy",
      "status": "healthy"
    },
    "enhanced_services": {
      "qdrant": "healthy",
      "neo4j": "healthy", 
      "status": "healthy"
    }
  },
  "recommended_actions": [
    "✓ Core functionality operational"
  ]
}
```

### Legacy Format Issues (FIXED)

**Previous problematic format:**
```json
{
  "ready": false,
  "error": "'agent_ready'",
  "recommended_actions": [
    "Check system logs for detailed error information"
  ]
}
```

**Issue:** Referenced non-existent `agent_ready` field causing KeyError
**Status:** Fixed in this release

## Migration Guide

### For Integrations Using Legacy Format

1. **Update field mappings:**
   ```python
   # OLD
   name = data.get('user_message', '')
   response = data.get('assistant_response', '')
   
   # NEW
   text = data.get('text', '')
   fact_type = data.get('type', '')
   title = data.get('title', '')
   ```

2. **Handle nested structures:**
   ```python
   # Check for graph result format
   if 'n' in result:
       content = result['n']
   else:
       content = result.get('content', {})
   ```

3. **Update response parsing:**
   ```python
   # OLD
   contexts = response.get('contexts', [])
   
   # NEW  
   results = response.get('results', [])
   ```

## Readiness Levels

The new readiness system provides clearer diagnostic levels:

- **BASIC**: Core tools available, minimal functionality
- **STANDARD**: Redis healthy, all 5 MCP tools operational
- **FULL**: All services healthy, enhanced search available

## Error Handling

### Graceful Degradation

The system now operates in degraded mode rather than failing completely:

```json
{
  "ready": true,
  "readiness_level": "STANDARD",
  "usage_quotas": {
    "vector_operations": "unavailable",
    "graph_queries": "unavailable",
    "kv_operations": "unlimited"
  },
  "recommended_actions": [
    "INFO: Enhanced features unavailable - Qdrant (vector search) not ready"
  ]
}
```

## Backward Compatibility

Current version maintains backward compatibility for:
- Legacy field names (with deprecation warnings)
- Response structure parsing
- Error handling patterns

Future versions (v1.0+) will remove legacy support entirely.

## Support

For migration assistance or format questions:
- Create issue at: https://github.com/credentum/veris-memory/issues
- Reference this document in bug reports
- Include version information in support requests