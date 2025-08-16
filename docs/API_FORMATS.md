# API Response Formats

This document describes the current API response formats for Veris Memory v1.0.

## Overview

Veris Memory provides a clean, consistent API with standardized response formats across all endpoints. 

**Breaking Changes Notice**: If you were using fields like `user_message`, `assistant_response`, or `exchange_type` from earlier versions, please update to the current format described below.

## Store Context Response Format

```json
{
  "success": true,
  "id": "uuid-string",
  "vector_id": "uuid-string",
  "graph_id": "node-id",
  "message": "Context stored successfully"
}
```

## Store Context Input Format

Use this standardized content format:

```json
{
  "content": {
    "text": "My name is Matt",
    "type": "decision",
    "title": "User Name",
    "fact_type": "personal_info"
  },
  "type": "log",
  "metadata": {"source": "telegram_bot", "timestamp": 1234567890}
}
```

## Retrieve Context Response Format

All search results (vector, graph, hybrid) use this consistent format:

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

**Key Points:**
- ✅ **Consistent structure**: All results use `{id, content, score, source}` format
- ✅ **No nested wrappers**: Eliminated problematic `{'n': {...}}` structures
- ✅ **Single parsing path**: Same code handles vector and graph results

## Readiness Check Format

Enhanced diagnostic information with clear readiness levels:

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

### Readiness Levels

- **BASIC**: Core tools available, minimal functionality
- **STANDARD**: Redis healthy, all 5 MCP tools operational  
- **FULL**: All services healthy, enhanced search available

## Content Field Structure

The standardized content format uses these fields:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `text` | string | Primary content text | "My name is Matt" |
| `type` | string | Content classification | "decision", "response", "fact" |
| `title` | string | Short descriptive title | "User Name" |
| `fact_type` | string | Semantic categorization | "personal_info", "preference" |

## Error Handling

### Graceful Degradation

System operates in degraded mode when some services are unavailable:

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
    "✓ Core functionality operational",
    "INFO: Enhanced features unavailable - Qdrant (vector search) not ready"
  ]
}
```

## Integration Code Examples

### Simple Result Processing

```python
# Clean, consistent parsing
for result in response['results']:
    content = result['content']
    text = content['text']
    content_type = content['type']
    
    print(f"Found: {text} (type: {content_type})")
```

### Search with Error Handling

```python
async def search_contexts(query: str):
    payload = {
        "query": query,
        "search_mode": "hybrid",
        "limit": 10
    }
    
    async with session.post(f"{BASE_URL}/tools/retrieve_context", json=payload) as resp:
        result = await resp.json()
        
        if result.get('success'):
            return result['results']
        else:
            logger.error(f"Search failed: {result.get('message', 'Unknown error')}")
            return []
```

## Migration from Previous Versions

If you were using earlier field names, update your code:

```python
# If you had:
user_msg = data.get('user_message', '')  
exchange_type = data.get('exchange_type', '')

# Update to:
text = data.get('text', '')
content_type = data.get('type', '')
```

## Support

For questions or issues:
- Create issue at: https://github.com/credentum/veris-memory/issues  
- Include version information and example requests
- Reference this documentation