# Veris Memory Critical Bug Fix Plan

**Date**: 2025-08-14  
**Status**: CRITICAL - System Non-Functional  
**Estimated Fix Time**: 2-3 hours  

## Executive Summary

The Veris Memory system has 7 critical bugs preventing ALL data storage operations. These are simple implementation errors that can be fixed quickly. The system is currently unable to store any context data, making the bot respond with the same answers repeatedly.

## Root Cause Analysis

### 🔴 Critical Issue #1: Vector ID Format Mismatch
**Location**: `src/mcp_server/main.py:859`  
**Current**: `context_id = f"ctx_{uuid.uuid4().hex[:12]}"`  
**Problem**: Generates IDs like "ctx_9ed976653a77" but Qdrant expects UUID or integer  
**Fix**: Use pure UUID without "ctx_" prefix  

### 🔴 Critical Issue #2: Wrong Qdrant Client Assignment  
**Location**: `src/mcp_server/main.py:317`  
**Current**: `qdrant_client = qdrant_initializer.client`  
**Problem**: Assigns raw QdrantClient instead of VectorDBInitializer wrapper  
**Fix**: Use the wrapper: `qdrant_client = qdrant_initializer`  

### 🔴 Critical Issue #3: Neo4j Parameter Name Error
**Location**: `src/mcp_server/main.py:892`  
**Current**: `neo4j_client.create_node(label="Context",...)`  
**Problem**: Method expects `labels` (plural) as List[str], not `label` (singular)  
**Fix**: Change to `labels=["Context"]`  

### 🟡 Issue #4: Vector Search Parameter Error
**Location**: `src/mcp_server/main.py:950-951`  
**Current**: `qdrant_client.search(collection_name=collection_name,...)`  
**Problem**: Method doesn't accept `collection_name` parameter  
**Fix**: Remove `collection_name` parameter  

### 🟡 Issue #5: Store Vector Parameter Mismatch
**Location**: `src/mcp_server/main.py:871-879`  
**Current**: Wrong parameter names (collection, id, vector, payload)  
**Problem**: Method expects (vector_id, embedding, metadata)  
**Fix**: Use correct parameter names  

### 🟡 Issue #6: Neo4j Timeout Parameter
**Location**: `src/mcp_server/main.py:902-906`  
**Current**: Passes `timeout` parameter to `neo4j_client.query()`  
**Problem**: Method doesn't accept timeout parameter  
**Fix**: Remove timeout parameter  

### 🟠 Issue #7: Missing REST Endpoints
**Location**: `src/mcp_server/main.py`  
**Problem**: Missing `/tools/update_scratchpad` and `/tools/get_agent_state` endpoints  
**Fix**: Add the missing endpoint implementations  

## Phased Implementation Plan

### Phase 1: Critical Storage Fixes (30 minutes)
Fix the most critical issues that prevent any data storage:

1. **Fix Vector ID Generation**
2. **Fix Qdrant Client Assignment**  
3. **Fix Store Vector Parameters**

### Phase 2: Database API Fixes (30 minutes)
Fix the database interaction issues:

4. **Fix Neo4j create_node Parameter**
5. **Fix Vector Search Parameters**
6. **Fix Neo4j Query Timeout**

### Phase 3: Complete MCP Implementation (1 hour)
Add missing functionality:

7. **Add Missing REST Endpoints**
8. **Implement update_scratchpad endpoint**
9. **Implement get_agent_state endpoint**

### Phase 4: Testing & Validation (30 minutes)
Verify all fixes work correctly:

10. **Test store_context endpoint**
11. **Test retrieve_context endpoint**
12. **Test query_graph endpoint**
13. **Test new endpoints**
14. **Run integration tests**

## Detailed Fix Implementation

### Fix #1: Vector ID Generation
```python
# src/mcp_server/main.py:859
# BEFORE:
context_id = f"ctx_{uuid.uuid4().hex[:12]}"

# AFTER:
context_id = str(uuid.uuid4())  # Pure UUID format
```

### Fix #2: Qdrant Client Assignment
```python
# src/mcp_server/main.py:317
# BEFORE:
qdrant_client = qdrant_initializer.client

# AFTER:
qdrant_client = qdrant_initializer
```

### Fix #3: Neo4j Labels Parameter
```python
# src/mcp_server/main.py:892
# BEFORE:
graph_id = neo4j_client.create_node(
    label="Context",
    properties={"id": context_id, "type": request.type, **request.content},
)

# AFTER:
graph_id = neo4j_client.create_node(
    labels=["Context"],  # Changed to plural, as a list
    properties={"id": context_id, "type": request.type, **request.content},
)
```

### Fix #4: Vector Search Parameters
```python
# src/mcp_server/main.py:950-954
# BEFORE:
vector_results = qdrant_client.search(
    collection_name=collection_name,
    query_vector=query_vector,
    limit=request.limit,
)

# AFTER:
vector_results = qdrant_client.search(
    query_vector=query_vector,
    limit=request.limit,
)
```

### Fix #5: Store Vector Parameters
```python
# src/mcp_server/main.py:871-879
# BEFORE:
vector_id = qdrant_client.store_vector(
    vector_id=context_id,
    embedding=embedding,
    metadata={
        "content": request.content,
        "type": request.type,
        "metadata": request.metadata,
    }
)

# AFTER (Already correct based on investigation)
# Just ensure context_id is a valid UUID from Fix #1
```

### Fix #6: Neo4j Query Timeout
```python
# src/mcp_server/main.py:902-906
# BEFORE:
results = neo4j_client.query(
    request.query,
    parameters=request.parameters,
    timeout=request.timeout / 1000,
)

# AFTER:
results = neo4j_client.query(
    request.query,
    parameters=request.parameters
)
```

## Testing Plan

### Quick Smoke Test
```bash
# Test 1: Store Context
curl -X POST "http://135.181.4.118:8000/tools/store_context" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test",
    "content": {"message": "Testing fix"},
    "metadata": {"timestamp": "2025-08-14"}
  }'

# Test 2: Retrieve Context  
curl -X POST "http://135.181.4.118:8000/tools/retrieve_context" \
  -H "Content-Type: application/json" \
  -d '{"query": "Testing fix", "limit": 5}'

# Test 3: Query Graph
curl -X POST "http://135.181.4.118:8000/tools/query_graph" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (n) RETURN count(n)", "parameters": {}}'
```

### Validation Checklist
- [ ] No more "ctx_xxx is not a valid point ID" errors
- [ ] No more "unexpected keyword argument 'label'" errors  
- [ ] No more "unexpected keyword argument 'collection_name'" errors
- [ ] No more "object has no attribute 'store_vector'" errors
- [ ] No more "unexpected keyword argument 'timeout'" errors
- [ ] All 5 MCP tools accessible via REST API
- [ ] Data successfully stores and retrieves

## Deployment Steps

1. **Create Feature Branch**
   ```bash
   git checkout -b fix/critical-storage-bugs
   ```

2. **Apply All Fixes**
   - Implement fixes in order of phases
   - Test each phase before moving to next

3. **Run Tests**
   ```bash
   python -m pytest tests/
   ```

4. **Deploy to Staging**
   ```bash
   docker-compose -f docker-compose.yml up --build
   ```

5. **Verify with Smoke Tests**

6. **Deploy to Production**
   ```bash
   ./scripts/deploy-to-hetzner.sh
   ```

## Success Criteria

✅ System can store context without errors  
✅ System can retrieve stored context  
✅ Graph queries execute successfully  
✅ All 5 MCP tools are functional  
✅ Bot provides varied responses based on stored context  

## Risk Assessment

**Risk Level**: LOW  
- All fixes are straightforward parameter/naming corrections
- No architectural changes required
- No data migration needed
- Rollback is simple if issues arise

## Timeline

**Total Estimated Time**: 2-3 hours
- Phase 1: 30 minutes
- Phase 2: 30 minutes  
- Phase 3: 1 hour
- Phase 4: 30 minutes
- Buffer: 30 minutes

## Post-Fix Actions

1. **Add Integration Tests** to prevent regression
2. **Update Documentation** with correct API signatures
3. **Add Monitoring** for storage failures
4. **Implement CI/CD** pipeline with automated testing
5. **Code Review Process** to catch such issues early

---

**Ready to implement?** Start with Phase 1 for immediate impact.