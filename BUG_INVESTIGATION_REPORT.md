# Veris Memory Bug Investigation Report

**Date**: 2025-01-14  
**Investigator**: Claude  
**System Version**: 0.9.0  
**Status**: Critical Issues Found

## Executive Summary

A comprehensive investigation of the Veris Memory system revealed **4 critical bugs** that completely prevent the system from functioning. These are implementation errors, not infrastructure issues. The system cannot store or retrieve any data in its current state.

## Investigation Methodology

1. **Live System Testing**: Connected to running instance at `http://172.17.0.1:8000`
2. **Code Analysis**: Examined source files in `/claude-workspace/worktrees/persistent/veris-memory`
3. **API Testing**: Attempted to use all 5 MCP tools via REST endpoints
4. **Root Cause Analysis**: Traced errors back to specific lines of code

## Findings

### Issue #1: QdrantClient Method Not Found ⚠️ CRITICAL

**Error Message**: `'QdrantClient' object has no attribute 'store_vector'`

**Investigation Path**:
```
Error occurred → src/mcp_server/main.py:762 → Called store_vector on wrong object
→ Traced to line 317 → qdrant_client = qdrant_initializer.client (raw client)
→ Should be: qdrant_client = qdrant_initializer (wrapper with methods)
```

**Root Cause Analysis**:
- The code assigns the raw Qdrant client library object instead of the wrapper
- The wrapper (`VectorDBInitializer`) has the `store_vector` method
- The raw client does not have this method, causing AttributeError

**Evidence**:
```python
# Line 317 (WRONG):
qdrant_client = qdrant_initializer.client  # This is QdrantClient from library

# Should be:
qdrant_client = qdrant_initializer  # This has store_vector method
```

### Issue #2: Method Signature Mismatch 🔴 HIGH

**Error Location**: `src/mcp_server/main.py:762-771`

**Investigation**:
```python
# Current call (WRONG parameters):
vector_id = qdrant_client.store_vector(
    collection="context_store",  # ❌ No such parameter
    id=context_id,               # ❌ Should be vector_id
    vector=embedding,             # ❌ Should be embedding
    payload={...}                 # ❌ Should be metadata
)

# Expected signature (from qdrant_client.py:272-274):
def store_vector(
    self, 
    vector_id: str, 
    embedding: list, 
    metadata: Optional[Dict[str, Any]] = None
)
```

### Issue #3: Neo4j Timeout Parameter 🟡 MEDIUM

**Error Message**: `Neo4jInitializer.query() got an unexpected keyword argument 'timeout'`

**Investigation Path**:
```
main.py:905 passes timeout → neo4j_client.query() doesn't accept it
→ Checked neo4j_client.py:447 → Only accepts cypher and parameters
```

**Code Evidence**:
```python
# main.py:902-906 (WRONG):
results = neo4j_client.query(
    request.query,
    parameters=request.parameters,
    timeout=request.timeout / 1000,  # ❌ This parameter doesn't exist
)

# neo4j_client.py:447 (ACTUAL):
def query(self, cypher: str, parameters: Optional[JSON] = None) -> QueryResult:
    # No timeout parameter!
```

### Issue #4: Missing REST Endpoints 🔴 HIGH

**Investigation Method**: Searched for all POST endpoints in main.py

**Found Endpoints**:
```bash
648: @app.post("/tools/verify_readiness")
741: @app.post("/tools/store_context")
807: @app.post("/tools/retrieve_context")
886: @app.post("/tools/query_graph")
```

**Missing Endpoints**:
- ❌ `/tools/update_scratchpad` - No POST endpoint exists
- ❌ `/tools/get_agent_state` - No POST endpoint exists

**Impact**: 40% of advertised MCP tools are not accessible via REST API

## System Impact Assessment

| Component | Status | Impact |
|-----------|--------|--------|
| Store Context | 🔴 BROKEN | Cannot store any data |
| Retrieve Context | 🟡 WORKS | But no data to retrieve |
| Query Graph | 🔴 BROKEN | Timeout error prevents queries |
| Update Scratchpad | 🔴 MISSING | Endpoint doesn't exist |
| Get Agent State | 🔴 MISSING | Endpoint doesn't exist |

**Overall System Status**: **NON-FUNCTIONAL**

## Test Results

### Test 1: Store Context
```json
Request: POST /tools/store_context
{
  "type": "design",
  "content": {...},
  "metadata": {...}
}

Response: {
  "success": false,
  "message": "Failed to store context: 'QdrantClient' object has no attribute 'store_vector'"
}
```

### Test 2: Query Graph
```json
Request: POST /tools/query_graph
{
  "query": "MATCH (n) RETURN count(n)",
  "parameters": {}
}

Response: {
  "success": false,
  "error": "Neo4jInitializer.query() got an unexpected keyword argument 'timeout'"
}
```

### Test 3: Get Agent State
```
Request: POST /tools/get_agent_state
Response: 404 Not Found
```

## Code Quality Observations

1. **No Integration Tests**: These bugs would be caught by basic integration tests
2. **Inconsistent Error Handling**: Some endpoints return success:false, others throw 404
3. **Incomplete Implementation**: MCP server.py has the tools but main.py missing endpoints
4. **Parameter Mismatches**: Multiple cases of wrong parameter names/types

## Recommendations

### Immediate Actions (Sprint 12)
1. **Fix QdrantClient assignment** (1 line change)
2. **Fix store_vector parameters** (4 line changes)
3. **Remove timeout parameter** (1 line change)
4. **Add missing endpoints** (~50 lines of code)

### Follow-up Actions
1. **Add integration tests** for all endpoints
2. **Implement CI/CD pipeline** with automated testing
3. **Add monitoring** for API errors
4. **Code review process** to catch such issues

## Investigation Files Examined

- `/src/mcp_server/main.py` - Main API server
- `/src/storage/qdrant_client.py` - Vector storage implementation
- `/src/storage/neo4j_client.py` - Graph storage implementation
- `/src/mcp_server/server.py` - MCP protocol server
- `/contracts/` - Tool specifications
- `/tests/` - Test suite (not comprehensive enough)

## Conclusion

The Veris Memory system has fundamental implementation bugs that prevent any basic operations. These are not complex issues - they are simple coding errors that suggest the system was not tested end-to-end before deployment. 

**The good news**: All issues can be fixed in 1-2 days with focused effort.

**The concerning news**: The presence of these bugs suggests deeper quality control issues in the development process.

## Next Steps

1. ✅ Investigation complete
2. ✅ Bug fix sprint plan created (`SPRINT_BUGFIX_PLAN.md`)
3. ✅ Implementation guide created (`BUGFIX_IMPLEMENTATION.py`)
4. ⏳ Awaiting implementation team assignment
5. ⏳ Fix deployment targeted for Sprint 12

---

**Investigation Duration**: 45 minutes  
**Bugs Found**: 4 critical, 0 minor  
**Estimated Fix Time**: 1-2 days  
**Risk Level**: CRITICAL - System non-functional