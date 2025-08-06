# ◎ Veris Memory

**memory with covenant**

Truthful memory for agents. For those who remember.

---

## For Agents

Veris Memory provides persistent, semantic memory storage through the **MCP 1.0 protocol**. Connect once, remember forever.

### Quick Connect

```python
# MCP Client Connection
from mcp.client import MCPClient

client = MCPClient("http://localhost:8000/mcp")
await client.connect()
```

```bash
# Claude CLI Integration
claude --mcp-server http://localhost:8000/mcp
```

### Memory Operations

#### Store Context
```python
await client.call_tool("store_context", {
    "type": "decision",
    "content": {"title": "API Design Choice", "decision": "REST over GraphQL", "reasoning": "Team familiarity"},
    "metadata": {"priority": "high", "project": "auth-service"}
})
```

#### Retrieve Context  
```python
results = await client.call_tool("retrieve_context", {
    "query": "API design decisions",
    "limit": 5,
    "filters": {"project": "auth-service"}
})
```

#### Query Relationships
```python
graph = await client.call_tool("query_graph", {
    "node_id": "decision-123",
    "depth": 2,
    "relationship_types": ["depends_on", "conflicts_with"]
})
```

---

## Protocol Specification

**Protocol:** MCP-1.0  
**Version:** 0.9.0-alpha  
**Category:** memory_store  

### Endpoints

| Tool | Method | Path | Description |
|------|--------|------|-------------|
| `store_context` | POST | `/tools/store_context` | Store contextual memory with structured metadata and optional TTL |
| `retrieve_context` | POST | `/tools/retrieve_context` | Retrieve relevant context using semantic similarity and filters |
| `query_graph` | POST | `/tools/query_graph` | Traverse graph relationships between stored memory nodes |

### Tool Contracts

- **store_context_tool.json** - Context storage contract
- **retrieve_context_tool.json** - Context retrieval contract  
- **query_graph_tool.json** - Graph traversal contract

---

## Installation & Deployment

### Docker Deployment
```bash
# Clone repository
git clone https://github.com/credentum/veris-memory.git
cd veris-memory

# Start services
docker-compose up -d

# Verify MCP endpoint
curl http://localhost:8000/mcp/health
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start MCP server
python -m src.mcp_server.main

# Test connection
python scripts/test_mcp_connection.py
```

---

## Memory Types

Veris Memory supports structured context storage across domains:

- **`decision`** - Architectural decisions, trade-offs, rationale
- **`design`** - System designs, specifications, patterns
- **`learning`** - Insights, failures, lessons learned  
- **`task`** - Work items, progress, dependencies
- **`knowledge`** - Documentation, references, expertise

Each type maintains semantic relationships and supports graph traversal.

---

## Truth Preservation

> *"Veris is memory that persists through change. For agents who carry weight. For those who remember what others forget."*

### Covenant Principles

1. **Fidelity** - Context is stored exactly as provided, without modification
2. **Persistence** - Memory survives system restarts and deployments
3. **Accessibility** - Semantic retrieval surfaces relevant context when needed
4. **Relationships** - Graph connections preserve context relationships
5. **Accountability** - Metadata tracks provenance and authority

### Agent-Aligned Design

- **Semantic Search** - Natural language queries find relevant memories
- **Contextual Filtering** - Scope retrieval by project, type, or metadata
- **Relationship Mapping** - Understand how decisions connect and conflict
- **TTL Support** - Automatic cleanup for ephemeral context
- **MCP Standard** - Universal protocol for agent memory integration

---

## Symbol

```
◎ Veris Memory
```

**Memory core. Covenant of truth. Symbol of agent-aligned recall.**

The symbol represents:
- **◎** - Complete memory, unbroken covenant
- **Veris** - Latin for truth, accuracy, reality
- **Memory** - Persistent context storage
- **Covenant** - Binding commitment to preservation

---

## License

**MIT License** - Credentum Project

For agents who remember. For systems that endure. For truth that persists.

---

*Version 0.9.0-alpha - Veris Memory*