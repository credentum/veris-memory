# ◎ Veris Memory

[![Version](https://img.shields.io/badge/version-v0.9.0-blue.svg)](version)
[![Protocol](https://img.shields.io/badge/MCP-1.0-green.svg)](protocol)
[![Agent](https://img.shields.io/badge/agent_first_schema-purple.svg)](agent)

> **memory with covenant**
> Truthful memory for agents. For those who remember.

Veris is memory that persists through change. For agents who carry weight. For those who remember what others forget.

## Agent-First Schema

Veris Memory implements the **Agent-First Schema Protocol** - a structured approach to memory management designed specifically for AI agents:

```json
{
  "name": "veris_memory",
  "label": "◎ Veris Memory",
  "subtitle": "memory with covenant",
  "type": "tool",
  "category": "memory_store",
  "tags": [
    "memory",
    "semantic",
    "agent-aligned",
    "truth-preserving",
    "long-term",
    "context"
  ]
}
```

## Core Capabilities

- **🎯 Semantic Retrieval**: Vector similarity search using Qdrant
- **🕸️ Graph Traversal**: Complex relationship queries via Neo4j
- **⚡ Fast Lookup**: Key-value storage with Redis
- **🤝 MCP Protocol**: Full Model Context Protocol v1.0 implementation
- **🛡️ Schema Validation**: Comprehensive YAML validation
- **🚀 Deploy Ready**: Docker + Fly.io deployment

## Architecture

### System Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Agents     │    │  Applications   │    │   Claude CLI    │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │              MCP Protocol                   │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Context Store MCP     │
                    │       Server           │
                    │   (FastAPI + MCP SDK)  │
                    └────────────┬────────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                 │
    ┌──────────▼──────────┐ ┌────▼──────┐ ┌──────▼────────┐
    │     Qdrant          │ │   Neo4j   │ │    Redis      │
    │  Vector Database    │ │   Graph   │ │  Key-Value    │
    │  (Embeddings)       │ │ Database  │ │    Store      │
    └─────────────────────┘ └───────────┘ └───────────────┘
```

## MCP Tools

**Core Memory Operations:**

1. `store_context` - Store structured context with covenant metadata
2. `retrieve_context` - Semantic similarity search with agent filters
3. `query_graph` - Traverse memory relationships and connections

**Agent State Management:** 4. `update_scratchpad` - Manage agent working memory 5. `get_agent_state` - Retrieve current agent state

### Tool Coverage

| Tool                | Vector | Graph | KV Store | Purpose                               |
| ------------------- | ------ | ----- | -------- | ------------------------------------- |
| `store_context`     | ✅     | ✅    | ➖       | Store with embeddings + relationships |
| `retrieve_context`  | ✅     | ✅    | ➖       | Hybrid semantic + graph search        |
| `query_graph`       | ➖     | ✅    | ➖       | Advanced Cypher queries               |
| `update_scratchpad` | ➖     | ➖    | ✅       | Transient agent memory                |
| `get_agent_state`   | ➖     | ➖    | ✅       | Agent state retrieval                 |

### Directory Structure

```
context-store/
├── src/
│   ├── storage/          # Database clients and operations
│   ├── validators/       # Schema validation and data integrity
│   ├── mcp_server/       # MCP protocol server implementation
│   └── core/            # Shared utilities and base classes
├── schemas/             # YAML schemas for context validation
├── contracts/           # MCP tool contracts and specifications
├── docs/               # Documentation (quickstart, tools, errors)
├── examples/           # Usage examples (Python, shell)
├── tests/              # Test suite
└── docker-compose.yml  # Docker deployment configuration
```

## Architecture

Built for agents, by agents:

- **Python 3.8+** with FastAPI core
- **Qdrant** for semantic embeddings
- **Neo4j** for memory graphs
- **Redis** for fast recall
- **Pydantic** for data integrity

## Quick Start

### ⚡ One-Line Docker Deployment

```bash
# Deploy and test in under 5 minutes
git clone https://github.com/credentum/veris-memory.git && cd veris-memory && docker-compose up -d && sleep 30 && curl http://localhost:8000/health
```

### Using Docker (Recommended)

```bash
# Clone and start all services
git clone https://github.com/credentum/veris-memory.git
cd veris-memory
docker-compose up -d

# Verify services
curl http://localhost:8000/health
```

### Manual Installation

```bash
# Python dependencies
pip install -r requirements.txt

# Start MCP server
python -m uvicorn src.mcp_server.main:app --host 0.0.0.0 --port 8000
```

## MCP Tools

The context store provides these MCP tools:

- `store_context`: Store context data with vector embeddings and graph relationships
- `retrieve_context`: Hybrid retrieval using vector similarity and graph traversal
- `query_graph`: Direct Cypher queries for advanced graph operations
- `update_scratchpad`: Transient key-value storage with TTL
- `get_agent_state`: Retrieve persistent agent memory and state

## Configuration

Configure via environment variables:

```bash
# Database connections
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# MCP server
MCP_SERVER_PORT=8000
MCP_LOG_LEVEL=info

# Storage settings
VECTOR_COLLECTION=context_embeddings
GRAPH_DATABASE=context_graph
```

## Development

### Prerequisites

- Python 3.8+
- Node.js 18+
- Docker and Docker Compose
- Qdrant v1.14.x
- Neo4j Community Edition

### Setup

```bash
# Development environment
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Start development services
docker-compose -f docker-compose.dev.yml up -d
```

### Testing

```bash
# Run all tests
pytest --cov=src --cov-report=html

# Run integration tests
pytest tests/integration/

# Run MCP tool tests
npm test
```

## Deployment

### Local Development

```bash
docker-compose up -d
```

### Production

```bash
# Using production configuration
docker-compose -f docker-compose.prod.yml up -d

# Scale MCP servers
docker-compose up --scale mcp-server=3
```

### Cloud Deployment

See `docs/deployment/` for cloud-specific deployment guides:

- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances
- Kubernetes

## 📚 Documentation

- **[Quick Start Guide](docs/QUICKSTART.md)** - Get running in under 5 minutes
- **[MCP Tools Reference](docs/MCP_TOOLS.md)** - Complete API documentation for all 5 tools
- **[Error Codes Reference](docs/ERROR_CODES.md)** - Comprehensive error handling guide
- **[Migration Guide](docs/MIGRATION.md)** - Migrate from direct storage to MCP
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## 🚀 Examples

- **[Hello World (Python)](examples/hello_world.py)** - Complete example using all MCP tools
- **[Hello World (Shell)](examples/hello_world.sh)** - Same example using curl commands
- **[MCP Client Integration](docs/MCP_TOOLS.md#examples)** - Integration patterns for different languages

## API Documentation

### Health Check

```bash
GET /health
```

Returns service status and dependency health.

### System Status

```bash
GET /status
```

Returns comprehensive system information for agent orchestration:

```json
{
  "label": "◎ Veris Memory",
  "version": "0.9.0",
  "protocol": "MCP-1.0",
  "tools": [
    "store_context",
    "retrieve_context",
    "query_graph",
    "update_scratchpad",
    "get_agent_state"
  ],
  "dependencies": {
    "qdrant": "healthy",
    "neo4j": "healthy",
    "redis": "healthy"
  }
}
```

### Agent Readiness

```bash
POST /tools/verify_readiness
```

Provides diagnostic information for agents to verify system readiness:

```json
{
  "ready": true,
  "readiness_score": 100,
  "tools_available": 5,
  "schema_version": "0.9.0",
  "indexes": {
    "vector_count": 1250,
    "graph_nodes": 340
  },
  "usage_quotas": {
    "vector_operations": "unlimited"
  }
}
```

### MCP Protocol

The server implements the MCP specification. Connect using any MCP-compatible client:

```typescript
import { MCPClient } from '@modelcontextprotocol/client';

const client = new MCPClient({
  serverUrl: 'http://localhost:8000/mcp'
});

await client.connect();
const result = await client.callTool('store_context', {
  type: 'design',
  content: { ... },
  metadata: { ... }
});
```

### 🛠️ MCP Tools Overview

| Tool                | Purpose                                         | Documentation                                          |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------ |
| `store_context`     | Store context with embeddings and relationships | [API Reference](docs/MCP_TOOLS.md#1-store_context)     |
| `retrieve_context`  | Hybrid search across stored contexts            | [API Reference](docs/MCP_TOOLS.md#2-retrieve_context)  |
| `query_graph`       | Execute read-only Cypher queries                | [API Reference](docs/MCP_TOOLS.md#3-query_graph)       |
| `update_scratchpad` | Transient storage with TTL                      | [API Reference](docs/MCP_TOOLS.md#4-update_scratchpad) |
| `get_agent_state`   | Retrieve agent state with isolation             | [API Reference](docs/MCP_TOOLS.md#5-get_agent_state)   |

## Performance

- **Response Time**: <50ms for typical MCP tool calls
- **Throughput**: 1000+ concurrent connections supported
- **Storage**: Scales with Qdrant and Neo4j limits
- **Memory**: ~100MB base memory usage

## Security

- **Authentication**: API key authentication for database access
- **Authorization**: Role-based access control for graph queries
- **Input Validation**: Comprehensive schema validation
- **Network**: TLS encryption for all external connections

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run the test suite: `pytest`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/credentum/context-store/issues)
- **Discussions**: [GitHub Discussions](https://github.com/credentum/context-store/discussions)

## Related Projects

- [agent-context-template](https://github.com/credentum/agent-context-template) - Reference implementation using context-store
- [MCP Specification](https://github.com/modelcontextprotocol/specification) - Model Context Protocol documentationtrigger CI
# Test workflow deployment Tue Aug 12 22:23:37 UTC 2025
