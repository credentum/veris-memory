# Context Store - Quick Start Guide

Get your MCP context store running in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- 4GB available RAM
- Ports 8000, 6333, 7687, 6379 available

## One-Line Deployment

```bash
git clone https://github.com/credentum/context-store.git && cd context-store && cp .env.example .env && sed -i 's/your_neo4j_password_here/contextstore123/' .env && docker-compose up -d
```

Wait 30 seconds for services to initialize, then test:

```bash
curl http://localhost:8000/health
```

### Alternative: Step-by-Step

```bash
# 1. Clone repository
git clone https://github.com/credentum/context-store.git
cd context-store

# 2. Configure environment
cp .env.example .env
# Edit .env and set NEO4J_PASSWORD=your_secure_password

# 3. Deploy with docker-compose
docker-compose up -d

# 4. Verify deployment
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "services": {
    "neo4j": "healthy",
    "qdrant": "healthy",
    "redis": "healthy"
  }
}
```

## Your First MCP Call

### 1. Store Context

```bash
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "store_context",
      "arguments": {
        "type": "design",
        "content": {
          "title": "Hello World API",
          "description": "My first context store entry"
        },
        "metadata": {
          "author": "quickstart-user"
        }
      }
    }
  }'
```

### 2. Retrieve Context

```bash
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "retrieve_context",
      "arguments": {
        "query": "Hello World",
        "limit": 5
      }
    }
  }'
```

### 3. Update Agent Scratchpad

```bash
curl -X POST http://localhost:8000/mcp/call_tool \
  -H "Content-Type: application/json" \
  -d '{
    "method": "call_tool",
    "params": {
      "name": "update_scratchpad",
      "arguments": {
        "agent_id": "quickstart-agent",
        "key": "notes",
        "content": "Successfully deployed context store!"
      }
    }
  }'
```

## Configuration

The default configuration works out of the box. For production deployment, set these environment variables:

```bash
# Security
NEO4J_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
QDRANT_API_KEY=your_qdrant_key

# Performance
QDRANT_DIMENSIONS=1536
EMBEDDING_MODEL=text-embedding-ada-002
```

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker-compose logs

# Restart with fresh data
docker-compose down -v
docker-compose up -d
```

### Port Conflicts

```bash
# Use different ports
MCP_SERVER_PORT=8001 QDRANT_PORT=6334 docker-compose up -d
```

### Health Check Failing

```bash
# Wait longer for initialization
sleep 60 && curl http://localhost:8000/health

# Check individual services
curl http://localhost:6333/health  # Qdrant
curl http://localhost:7474         # Neo4j Browser
```

## Next Steps

- Read the [MCP Tools Documentation](docs/MCP_TOOLS.md)
- See [Architecture Overview](docs/ARCHITECTURE.md)
- Check [Production Deployment](docs/DEPLOYMENT.md)
- Browse [Examples](examples/)

## Support

- **Issues**: [GitHub Issues](https://github.com/credentum/context-store/issues)
- **Discussions**: [GitHub Discussions](https://github.com/credentum/context-store/discussions)
- **Health Check**: `curl http://localhost:8000/health`

**Success!** You now have a fully functional MCP context store.
