# Agent Memory Reference

**For AI Agents Working on Veris Memory**

## Quick Start

The complete system documentation is stored **inside Veris Memory itself**! 

### How to Access

Use the MCP `query_graph` tool or REST API to retrieve stored documentation:

```python
import requests

BASE_URL = 'http://172.17.0.1:8000'
HEADERS = {'X-API-Key': 'vmk_mcp_903e1bcb70d704da4fbf207722c471ba'}

# Get full documentation
query = {
    "query": """
    MATCH (c:Context {id: '58c677bc-44a6-4597-890e-c36f672d9325'})
    RETURN c
    """
}

response = requests.post(f'{BASE_URL}/tools/query_graph', headers=HEADERS, json=query)
documentation = response.json()
```

## Stored Context IDs

### 1. **Full System Documentation** (520 lines)
**Context ID**: `58c677bc-44a6-4597-890e-c36f672d9325`  
**Type**: design  
**Contains**:
- Complete PR history (PRs #170-#178)
- System architecture
- All 31 tests documented
- Deployment workflows
- Environment variables
- Quick reference commands
- Performance metrics
- Known issues & solutions

### 2. **Quick Status Summary**
**Context ID**: `37e24801-a892-4acf-90d8-31ab53e7b5ce`  
**Type**: design  
**Contains**:
- Current system status (100% test pass rate)
- Recent PR summaries
- Key metrics (7 MCP tools, Neo4j index, etc.)
- System architecture overview
- Critical fixes summary

### 3. **Known Issues & Solutions**
**Context ID**: `31974ed4-0840-4e94-b36a-ce3447b48080`  
**Type**: decision  
**Contains**:
- Resolved issues with solutions
- DateTime serialization fix
- Duplicate env vars prevention
- Neo4j index creation fix
- Important patterns to follow

## Why Documentation is in Veris Memory

✅ **Self-documenting system** - The memory system stores its own history  
✅ **Always accessible** - Any agent can query for context  
✅ **Version controlled** - Stored with metadata and timestamps  
✅ **Searchable** - Graph queries can find specific information  
✅ **Demonstrates the system** - Shows Veris Memory in action  

## Quick Queries

### Get Recent Work Summary
```cypher
MATCH (c:Context {id: '37e24801-a892-4acf-90d8-31ab53e7b5ce'})
RETURN c.content
```

### Get Troubleshooting Guide
```cypher
MATCH (c:Context {id: '31974ed4-0840-4e94-b36a-ce3447b48080'})
RETURN c.content
```

### Get All System Documentation
```cypher
MATCH (c:Context)
WHERE c.id IN [
  '58c677bc-44a6-4597-890e-c36f672d9325',
  '37e24801-a892-4acf-90d8-31ab53e7b5ce', 
  '31974ed4-0840-4e94-b36a-ce3447b48080'
]
RETURN c
ORDER BY c.created_at
```

## Alternative: File-Based Documentation

The full documentation is also available in:
- `CURRENT_STATUS.md` (in repo, PR #179)

But for the true Veris Memory experience, **query it from the MCP server**! 🚀

---

**Last Updated**: 2025-11-07  
**System Status**: ✅ Production Ready (31/31 tests passing)
