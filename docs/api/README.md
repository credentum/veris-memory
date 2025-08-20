# Veris Memory API Documentation

Comprehensive REST API documentation for the Veris Memory system.

## Overview

The Veris Memory API provides a RESTful interface for storing, searching, and retrieving contextual information. It supports multiple search modes, advanced filtering, and configurable ranking policies.

**Base URL:** `http://localhost:8000` (development)  
**API Version:** v1  
**Documentation:** `/docs` (Swagger UI) or `/redoc` (ReDoc)

## Authentication

Currently, the API supports Bearer token authentication (configurable):

```http
Authorization: Bearer <your-token-here>
```

For development and testing, authentication may be disabled.

## Core Endpoints

### Search Contexts

**POST** `/api/v1/search`

Search for contexts across all backends with configurable parameters.

#### Request Body

```json
{
  "query": "python authentication function",
  "search_mode": "hybrid",
  "dispatch_policy": "parallel",
  "ranking_policy": "code_boost",
  "limit": 20,
  "content_types": ["code", "documentation"],
  "tags": ["python", "security"],
  "min_score": 0.7,
  "max_score": 1.0,
  "time_window": {
    "hours_ago": 24
  },
  "pre_filters": [
    {
      "field": "type",
      "operator": "equals",
      "value": "code"
    }
  ]
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query (min 1 character) |
| `search_mode` | enum | No | Search mode: `vector`, `graph`, `kv`, `hybrid`, `auto` |
| `dispatch_policy` | enum | No | Dispatch policy: `parallel`, `sequential`, `fallback`, `smart` |
| `ranking_policy` | string | No | Ranking policy name (e.g., `default`, `code_boost`, `recency`) |
| `limit` | integer | No | Maximum results (1-100, default: 10) |
| `content_types` | array | No | Filter by content types |
| `tags` | array | No | Filter by tags |
| `min_score` | float | No | Minimum relevance score (0.0-1.0) |
| `max_score` | float | No | Maximum relevance score (0.0-1.0) |
| `time_window` | object | No | Time-based filtering |
| `pre_filters` | array | No | Pre-filtering criteria |

#### Response

```json
{
  "success": true,
  "results": [
    {
      "id": "result_123",
      "text": "def authenticate_user(username: str, password: str) -> bool:",
      "type": "code",
      "score": 0.95,
      "source": "vector",
      "timestamp": "2024-01-15T10:30:00Z",
      "tags": ["python", "authentication", "security"],
      "metadata": {
        "language": "python",
        "complexity": "medium"
      }
    }
  ],
  "total_count": 1,
  "search_mode_used": "hybrid",
  "query": "python authentication function",
  "response_time_ms": 45.2,
  "backend_timings": {
    "vector": 25.1,
    "graph": 20.1
  },
  "backends_used": ["vector", "graph"],
  "ranking_policy_used": "code_boost",
  "filters_applied": {
    "content_types": ["code", "documentation"],
    "tags": ["python", "security"],
    "min_score": 0.7
  },
  "trace_id": "abc123def456",
  "timestamp": "2024-01-15T10:30:45Z"
}
```

### Store Context

**POST** `/api/v1/contexts`

Store a new context in the system.

#### Request Body

```json
{
  "id": "unique_context_id",
  "text": "Content of the context to store",
  "type": "code",
  "tags": ["python", "function", "api"],
  "metadata": {
    "language": "python",
    "author": "developer@example.com",
    "complexity": "medium"
  }
}
```

#### Response

```json
{
  "success": true,
  "context_id": "unique_context_id",
  "stored_at": "2024-01-15T10:30:00Z",
  "backends_stored": ["vector", "graph", "kv"]
}
```

## Configuration Endpoints

### Get Search Modes

**GET** `/api/v1/search/modes`

Get available search modes.

#### Response

```json
["vector", "graph", "kv", "hybrid", "auto"]
```

### Get Dispatch Policies

**GET** `/api/v1/search/policies`

Get available dispatch policies.

#### Response

```json
["parallel", "sequential", "fallback", "smart"]
```

### Get Ranking Policies

**GET** `/api/v1/search/ranking`

Get available ranking policies with details.

#### Response

```json
[
  {
    "name": "default",
    "description": "Default relevance-based ranking",
    "configuration": {
      "base_weight": 1.0
    }
  },
  {
    "name": "code_boost",
    "description": "Boosts code content in results",
    "configuration": {
      "code_boost_factor": 1.5,
      "type_weights": {
        "code": 1.5,
        "documentation": 1.0,
        "configuration": 0.8
      }
    }
  }
]
```

### Get System Information

**GET** `/api/v1/search/system-info`

Get comprehensive system information.

#### Response

```json
{
  "version": "1.0.0",
  "backends": ["vector", "graph", "kv"],
  "ranking_policies": ["default", "code_boost", "recency"],
  "filter_capabilities": {
    "time_window_filtering": true,
    "tag_filtering": true,
    "content_type_filtering": true
  },
  "rate_limits": {
    "requests_per_minute": 60,
    "burst_limit": 10
  },
  "features": [
    "semantic_search",
    "graph_traversal",
    "hybrid_ranking",
    "real_time_filtering"
  ]
}
```

## Health and Monitoring

### Health Check

**GET** `/api/v1/health`

Basic health check endpoint.

#### Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Detailed Health Check

**GET** `/api/v1/health/detailed`

Comprehensive health check including backend status.

#### Response

```json
{
  "status": "healthy",
  "backends": {
    "vector": {
      "status": "healthy",
      "response_time_ms": 25.1,
      "last_check": "2024-01-15T10:30:00Z"
    },
    "graph": {
      "status": "healthy", 
      "response_time_ms": 30.2,
      "last_check": "2024-01-15T10:30:00Z"
    },
    "kv": {
      "status": "healthy",
      "response_time_ms": 15.8,
      "last_check": "2024-01-15T10:30:00Z"
    }
  },
  "system_metrics": {
    "uptime_seconds": 3600,
    "total_requests": 1250,
    "avg_response_time_ms": 42.3
  }
}
```

### Metrics

**GET** `/api/v1/metrics`

Get system metrics and performance data.

#### Response

```json
{
  "request_count": 1250,
  "avg_response_time_ms": 42.3,
  "p95_response_time_ms": 85.7,
  "p99_response_time_ms": 120.4,
  "status_counts": {
    "200": 1200,
    "400": 25,
    "404": 15,
    "500": 10
  },
  "endpoint_metrics": {
    "POST /api/v1/search": {
      "count": 800,
      "avg_time_ms": 45.2,
      "errors": 5
    },
    "GET /api/v1/health": {
      "count": 400,
      "avg_time_ms": 2.1,
      "errors": 0
    }
  },
  "backend_performance": {
    "vector": {
      "avg_response_time_ms": 35.2,
      "total_requests": 800,
      "error_rate": 0.01
    },
    "graph": {
      "avg_response_time_ms": 28.7,
      "total_requests": 600,
      "error_rate": 0.005
    }
  }
}
```

## Data Models

### MemoryResult

Represents a search result from the system.

```json
{
  "id": "string",
  "text": "string",
  "type": "code|documentation|configuration|design|note|conversation",
  "score": 0.95,
  "source": "vector|graph|kv",
  "timestamp": "2024-01-15T10:30:00Z",
  "tags": ["tag1", "tag2"],
  "metadata": {
    "key": "value"
  }
}
```

### FilterCriteria

Defines filtering criteria for search requests.

```json
{
  "field": "string",
  "operator": "equals|contains|greater_than|less_than|in|not_in",
  "value": "any",
  "case_sensitive": false
}
```

### TimeWindow

Defines time-based filtering options.

```json
{
  "hours_ago": 24,
  "start_time": "2024-01-15T00:00:00Z",
  "end_time": "2024-01-15T23:59:59Z"
}
```

## Error Handling

### Error Response Format

All errors return a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Query parameter is required",
    "details": {
      "field": "query",
      "constraint": "min_length"
    },
    "trace_id": "abc123def456"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `AUTHENTICATION_ERROR` | 401 | Authentication failed |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `RATE_LIMIT_ERROR` | 429 | Rate limit exceeded |
| `BACKEND_ERROR` | 502 | Backend service error |
| `TIMEOUT_ERROR` | 504 | Request timeout |
| `INTERNAL_ERROR` | 500 | Internal server error |

### Common Error Scenarios

**Empty Query (422)**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Query cannot be empty",
    "details": {
      "field": "query",
      "constraint": "min_length"
    }
  }
}
```

**Rate Limit Exceeded (429)**
```json
{
  "error": {
    "code": "RATE_LIMIT_ERROR",
    "message": "Rate limit exceeded. Try again later.",
    "details": {
      "retry_after_seconds": 60,
      "limit": 60,
      "window": "minute"
    }
  }
}
```

**Backend Unavailable (502)**
```json
{
  "error": {
    "code": "BACKEND_ERROR",
    "message": "One or more backends are unavailable",
    "details": {
      "failed_backends": ["graph"],
      "available_backends": ["vector", "kv"]
    }
  }
}
```

## Rate Limiting

- **Default Limit:** 60 requests per minute per IP
- **Burst Limit:** 10 requests per second
- **Headers:** Rate limit information is included in response headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642234800
Retry-After: 15
```

## Request/Response Headers

### Standard Headers

**Request Headers:**
- `Content-Type: application/json`
- `Authorization: Bearer <token>` (if authentication enabled)
- `X-Trace-ID: <custom-trace-id>` (optional, for request tracking)

**Response Headers:**
- `Content-Type: application/json`
- `X-Trace-ID: <trace-id>` (for request tracking)
- `X-Response-Time-Ms: <time>` (processing time)
- Rate limiting headers (see above)

## SDKs and Client Libraries

### Python Client Example

```python
import requests

class VerisMemoryClient:
    def __init__(self, base_url: str, token: str = None):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
    
    def search(self, query: str, **kwargs) -> dict:
        """Search for contexts."""
        payload = {"query": query, **kwargs}
        response = requests.post(
            f"{self.base_url}/api/v1/search",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> dict:
        """Check system health."""
        response = requests.get(
            f"{self.base_url}/api/v1/health",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = VerisMemoryClient("http://localhost:8000")
results = client.search("python authentication function", limit=5)
print(f"Found {len(results['results'])} results")
```

### cURL Examples

**Basic Search:**
```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "python authentication function",
    "limit": 10
  }'
```

**Advanced Search:**
```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication system",
    "search_mode": "hybrid",
    "ranking_policy": "code_boost",
    "content_types": ["code", "documentation"],
    "min_score": 0.7,
    "limit": 20
  }'
```

**Health Check:**
```bash
curl -X GET "http://localhost:8000/api/v1/health/detailed"
```

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:
- **JSON Format:** `/openapi.json`
- **Interactive Documentation:** `/docs` (Swagger UI)
- **Alternative Documentation:** `/redoc` (ReDoc)

## Testing the API

### Using CLI Tools

```bash
# Interactive testing
python tools/cli/query_simulator.py

# Automated testing
python tools/cli/testing_tools.py test

# Load testing
python tools/cli/testing_tools.py load-test --concurrent-users 10
```

### Unit Testing

```python
import pytest
from fastapi.testclient import TestClient
from src.api.main import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_search_endpoint(client):
    response = client.post("/api/v1/search", json={
        "query": "test query"
    })
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total_count" in data
```

## Performance Considerations

### Optimization Tips

1. **Use Appropriate Limits:** Don't request more results than needed
2. **Leverage Caching:** Use time-based filters to enable caching
3. **Choose Search Modes Wisely:** Vector search is fastest, hybrid is most comprehensive
4. **Filter Early:** Use pre-filters to reduce result set size
5. **Monitor Performance:** Use metrics endpoints to track performance

### Expected Performance

- **Simple Queries:** < 50ms average response time
- **Complex Queries:** < 200ms average response time  
- **Throughput:** 100+ requests/second (depending on hardware)
- **Concurrent Users:** Supports 50+ concurrent users

## Changelog

### Version 1.0.0
- Initial API release
- Full search functionality
- Health monitoring endpoints
- Rate limiting implementation
- Comprehensive error handling

---

*For more information, see the [Developer Guide](../developer/README.md) or contact the development team.*