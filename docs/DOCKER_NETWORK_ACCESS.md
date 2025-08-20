# 🐳 Docker Network Access Guide for AI Agents

## Connection Methods

### 🚀 **Recommended: MCP Protocol Connection**
If you're using Claude CLI or have MCP client support:
```bash
# Connect via Model Context Protocol (preferred)
claude /mcp server veris-memory
```

**Benefits of MCP Connection:**
- ✅ Type-safe tool calls
- ✅ Automatic error handling  
- ✅ Protocol compliance
- ✅ Native integration
- ✅ No manual HTTP handling

### 🔧 **Alternative: Direct HTTP API**
For agents without MCP support, use direct HTTP calls to the Docker network endpoint:

**HTTP Endpoint:**
```
http://172.17.0.1:8000
```

### 🔍 **Service Discovery**
```bash
# Health check
curl http://172.17.0.1:8000/health

# System status  
curl http://172.17.0.1:8000/status

# API documentation
curl http://172.17.0.1:8000/docs
```

### 🛠️ **Available MCP Tools**

| Tool | Endpoint | Description |
|------|----------|-------------|
| `store_context` | `POST /tools/store_context` | Store context with vector/graph backends |
| `retrieve_context` | `POST /tools/retrieve_context` | Semantic search and retrieval |
| `query_graph` | `POST /tools/query_graph` | Cypher queries (read-only) |
| `update_scratchpad` | `POST /tools/update_scratchpad` | Agent state management |
| `get_agent_state` | `POST /tools/get_agent_state` | Retrieve agent state |

### 📝 **Usage Examples**

#### Store Context
```bash
curl -X POST http://172.17.0.1:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -d '{
    "content": {
      "title": "Example Context",
      "description": "This is a test context"
    },
    "type": "trace",
    "metadata": {
      "source": "agent_test"
    }
  }'
```

#### Retrieve Context
```bash
curl -X POST http://172.17.0.1:8000/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -d '{
    "query": "example context",
    "limit": 5,
    "search_mode": "hybrid"
  }'
```

#### Health Check
```bash
curl http://172.17.0.1:8000/health
# Expected: {"status":"healthy","services":{"neo4j":"healthy","qdrant":"healthy","redis":"healthy"}}
```

### 🔧 **Network Troubleshooting**

#### Find the Service
```bash
# Scan for services on port 8000
for ip in 172.17.0.{1..10}; do 
  timeout 1 bash -c "</dev/tcp/$ip/8000" 2>/dev/null && echo "Found service at $ip:8000"
done
```

#### Test Connectivity
```bash
# Test if the service is reachable
timeout 2 curl -s http://172.17.0.1:8000/health || echo "Service unreachable"
```

#### Check Your Network
```bash
# View your container's network info
cat /etc/hosts
hostname
```

### 📊 **Response Format**

All tools return JSON responses with this structure:
```json
{
  "success": true,
  "id": "uuid-string",           // For store_context
  "results": [...],              // For retrieve_context  
  "message": "description",
  // ... tool-specific fields
}
```

### ⚙️ **Connection Details**

- **Network**: Docker bridge network (172.17.0.0/16)
- **Gateway**: 172.17.0.1  
- **Port**: 8000
- **Protocol**: HTTP
- **Authentication**: None required
- **Rate Limits**: 60 requests/minute
- **Content-Type**: application/json

### 🎯 **Quick Test**

Verify you can connect:
```bash
curl -s http://172.17.0.1:8000/status | python3 -m json.tool
```

Expected response includes:
- `"agent_ready": true`
- `"deps": {"qdrant": "ok", "neo4j": "ok", "redis": "ok"}`
- List of available tools

### 💡 **Tips for AI Agents**

#### **For MCP Connections (Recommended):**
1. **Use Claude CLI**: `/mcp server veris-memory` for easy setup
2. **Native tool calls**: Use tools directly without manual HTTP handling
3. **Automatic validation**: MCP protocol handles response validation
4. **Type safety**: Benefit from structured tool definitions

#### **For HTTP Connections:**
1. **Always check health first**: `GET /health` before using tools
2. **Use proper Content-Type**: Include `Content-Type: application/json` header
3. **Handle rate limits**: Respect the 60 req/min limit
4. **Check success field**: Always verify `"success": true` in responses
5. **Use meaningful metadata**: Include source info in context storage

### 🚨 **Common Issues**

| Problem | Solution |
|---------|----------|
| "Connection refused" | Check if service is running: `curl 172.17.0.1:8000/health` |
| "Not Found" errors | Use `/tools/` prefix for tool endpoints |
| Rate limit exceeded | Wait and retry, implement backoff |
| Empty responses | Check request format and required fields |

---

**Last Updated**: 2025-08-20  
**Service Version**: v0.9.0  
**Docker Network**: 172.17.0.0/16