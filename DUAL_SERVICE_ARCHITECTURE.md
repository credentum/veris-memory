# Dual Service Architecture

Veris Memory now deploys as two complementary services providing different interfaces to the same backend infrastructure.

## Service Overview

### MCP Server (Port 8000) - Primary AI Agent Interface
- **Purpose**: Model Context Protocol for AI agent communication
- **URL**: `http://context-store:8000` (internal) / `http://localhost:8000` (external)
- **Protocol**: MCP (Model Context Protocol)
- **Target Users**: AI agents, LLMs, intelligent systems
- **Health Check**: `http://localhost:8000/health`

### REST API Server (Port 8001) - Operational Interface
- **Purpose**: Traditional HTTP REST API for monitoring and operations
- **URL**: `http://api:8001` (internal) / `http://localhost:8001` (external)
- **Protocol**: HTTP/REST with OpenAPI documentation
- **Target Users**: Dashboards, monitoring systems, web applications
- **Health Check**: `http://localhost:8001/api/v1/health`

## Architecture Benefits

### Clear Separation of Concerns
- **MCP Server**: Optimized for AI agent context management
- **REST API**: Optimized for operational visibility and traditional integrations

### Shared Infrastructure
Both services use the same backend services:
- **Qdrant**: Vector database (port 6333)
- **Neo4j**: Graph database (port 7474/7687)
- **Redis**: Key-value cache (port 6379)

### No Breaking Changes
- Existing MCP clients continue to work unchanged
- New REST API clients get modern HTTP interface

## Deployment Services

```yaml
services:
  context-store:  # MCP Server
    command: ["python", "-m", "uvicorn", "src.mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "8000:8000"
    
  api:            # REST API Server  
    command: ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
    ports:
      - "8001:8001"
```

## Available Endpoints

### MCP Server (Port 8000)
- Protocol-specific endpoints for AI agent communication
- Health check: `GET /health`

### REST API Server (Port 8001)
- `GET /` - Service information
- `GET /api/v1/health` - Comprehensive health check
- `GET /api/v1/health/live` - Kubernetes liveness probe
- `GET /api/v1/health/ready` - Kubernetes readiness probe
- `GET /api/v1/search` - Context search endpoint
- `GET /docs` - Interactive OpenAPI documentation
- `GET /openapi.json` - OpenAPI schema

## Monitoring Integration

### Sentinel Monitoring
The Sentinel service monitors both interfaces:
- `SENTINEL_TARGET_URL=http://context-store:8000` (MCP)
- `SENTINEL_API_URL=http://api:8001` (REST API)

### Health Checks
Both services provide health endpoints but with different focuses:
- **MCP**: Basic service availability
- **REST API**: Comprehensive component status with detailed metrics

## Use Cases

### When to Use MCP Server (Port 8000)
- AI agent context storage and retrieval
- LLM conversation context management
- Intelligent system integration

### When to Use REST API Server (Port 8001)
- System monitoring and observability
- Dashboard integrations
- Traditional web application backends
- API documentation and exploration

## Development

### Local Testing
```bash
# Test MCP server
curl http://localhost:8000/health

# Test REST API server
curl http://localhost:8001/api/v1/health
curl http://localhost:8001/docs  # Interactive docs
```

### Docker Deployment
```bash
docker-compose up -d
# Both services will be available:
# - MCP Server: http://localhost:8000
# - REST API: http://localhost:8001
```

This architecture provides the best of both worlds - specialized AI agent communication through MCP and traditional operational interfaces through REST API.