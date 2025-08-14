# Sprint 12 – Critical Bug Fixes for Veris Memory

## Sprint Overview
**Sprint Number**: 12
**Title**: Critical Bug Fixes and Implementation Corrections
**Duration**: 3-5 days
**Priority**: CRITICAL
**Status**: Planning

## Executive Summary
Investigation revealed multiple critical implementation bugs preventing basic operations in Veris Memory. These issues must be resolved before any beta readiness verification (Sprint 11) can proceed.

## Critical Issues Identified

### 1. **QdrantClient store_vector Method Issue**
**Severity**: CRITICAL
**Location**: `/src/mcp_server/main.py:762`
**Problem**: Code attempts to call `store_vector()` on raw QdrantClient object instead of VectorDBInitializer
**Root Cause**: Line 317 assigns `qdrant_client = qdrant_initializer.client` (raw client) instead of keeping the initializer

### 2. **Neo4j Query Timeout Parameter Issue**
**Severity**: HIGH
**Location**: `/src/mcp_server/main.py:905`
**Problem**: Passing unsupported `timeout` parameter to `neo4j_client.query()`
**Root Cause**: Neo4jInitializer.query() only accepts `cypher` and `parameters`, not `timeout`

### 3. **Missing REST Endpoints**
**Severity**: HIGH
**Location**: `/src/mcp_server/main.py`
**Problem**: Two MCP tools have no REST endpoints exposed
**Missing Endpoints**:
- `/tools/update_scratchpad`
- `/tools/get_agent_state`

### 4. **Store Vector Method Signature Mismatch**
**Severity**: MEDIUM
**Location**: `/src/mcp_server/main.py:762-771`
**Problem**: Calling store_vector with incorrect parameters
**Expected**: `store_vector(vector_id, embedding, metadata)`
**Actual**: Passing `collection`, `id`, `vector`, `payload`

## Sprint Phases

### Phase 1: Critical Storage Fixes (Day 1)

#### Task 1.1: Fix Qdrant Client Usage
```python
# Current (BROKEN):
qdrant_client = qdrant_initializer.client  # Line 317

# Fixed:
qdrant_client = qdrant_initializer  # Keep the wrapper with store_vector method
```

**Changes Required**:
1. Update line 317 in main.py to keep VectorDBInitializer instance
2. Update all references to ensure they use the wrapper methods
3. Test store_context endpoint thoroughly

#### Task 1.2: Fix Store Vector Method Call
```python
# Current (BROKEN):
vector_id = qdrant_client.store_vector(
    collection="context_store",  # Wrong parameter
    id=context_id,
    vector=embedding,
    payload={...}
)

# Fixed:
vector_id = qdrant_client.store_vector(
    vector_id=context_id,
    embedding=embedding,
    metadata={
        "content": request.content,
        "type": request.type,
        "metadata": request.metadata,
    }
)
```

### Phase 2: Neo4j Query Fix (Day 1-2)

#### Task 2.1: Remove Timeout Parameter
```python
# Current (BROKEN):
results = neo4j_client.query(
    request.query,
    parameters=request.parameters,
    timeout=request.timeout / 1000,  # Remove this line
)

# Fixed:
results = neo4j_client.query(
    request.query,
    parameters=request.parameters
)
```

#### Task 2.2: Implement Timeout at Driver Level (Optional Enhancement)
- Add timeout support to Neo4jInitializer.query() method
- Use Neo4j driver's session config for timeout
- Update method signature appropriately

### Phase 3: Add Missing Endpoints (Day 2-3)

#### Task 3.1: Implement update_scratchpad Endpoint
```python
@app.post("/tools/update_scratchpad")
async def update_scratchpad_endpoint(request: UpdateScratchpadRequest) -> Dict[str, Any]:
    """Update agent scratchpad with transient storage."""
    try:
        if not kv_store:
            raise HTTPException(status_code=503, detail="KV store not available")
        
        # Implementation using Redis
        key = f"scratchpad:{request.agent_id}:{request.key}"
        kv_store.set(key, request.value, ex=request.ttl)
        
        return {
            "success": True,
            "message": "Scratchpad updated successfully"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

#### Task 3.2: Implement get_agent_state Endpoint
```python
@app.post("/tools/get_agent_state")
async def get_agent_state_endpoint(request: GetAgentStateRequest) -> Dict[str, Any]:
    """Retrieve agent state from storage."""
    try:
        if not kv_store:
            raise HTTPException(status_code=503, detail="KV store not available")
        
        # Implementation using Redis
        key = f"{request.prefix}:{request.agent_id}:{request.key}"
        value = kv_store.get(key)
        
        if value is None:
            raise HTTPException(status_code=404, detail="Agent state not found")
        
        return {
            "success": True,
            "data": json.loads(value) if value else {},
            "message": "State retrieved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Phase 4: Integration Testing (Day 3-4)

#### Task 4.1: Create Integration Test Suite
```python
# tests/integration/test_all_endpoints.py
def test_store_context():
    """Test storing context with all storage backends."""
    pass

def test_retrieve_context():
    """Test retrieving contexts."""
    pass

def test_query_graph():
    """Test graph queries."""
    pass

def test_update_scratchpad():
    """Test scratchpad updates."""
    pass

def test_get_agent_state():
    """Test agent state retrieval."""
    pass
```

#### Task 4.2: End-to-End Testing
- Test all 5 MCP tools via REST API
- Verify storage in Qdrant, Neo4j, and Redis
- Test error handling and edge cases
- Performance benchmarking

### Phase 5: Documentation & Deployment (Day 4-5)

#### Task 5.1: Update API Documentation
- Document fixed endpoints
- Update OpenAPI spec
- Add examples for new endpoints

#### Task 5.2: Deployment Validation
- Deploy fixes to development environment
- Run smoke tests
- Monitor error logs
- Verify all services healthy

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|------------|
| All MCP tools functional | 100% | API tests pass |
| Store operations successful | 100% | No store_vector errors |
| Graph queries working | 100% | No timeout errors |
| Missing endpoints added | 2/2 | REST endpoints accessible |
| Integration tests passing | 100% | CI/CD green |
| Error rate | <1% | Monitoring dashboard |

## Implementation Files to Modify

1. **src/mcp_server/main.py**
   - Lines 317: Fix qdrant_client assignment
   - Lines 762-771: Fix store_vector call
   - Lines 902-906: Remove timeout parameter
   - Add update_scratchpad endpoint (~20 lines)
   - Add get_agent_state endpoint (~25 lines)

2. **src/storage/neo4j_client.py** (Optional)
   - Add timeout support to query method

3. **tests/integration/** (New)
   - Create comprehensive test suite

## Risk Mitigation

1. **Backup Current State**: Create git branch before changes
2. **Incremental Testing**: Test each fix individually
3. **Rollback Plan**: Keep previous Docker image tagged
4. **Monitoring**: Watch error rates during deployment

## Dependencies

- No external dependencies
- All fixes are internal code corrections
- Requires access to development environment for testing

## Definition of Done

- [ ] All 5 MCP tools accessible via REST API
- [ ] No store_vector errors in logs
- [ ] Graph queries execute without timeout errors
- [ ] Integration tests cover all endpoints
- [ ] API documentation updated
- [ ] Deployed to development environment
- [ ] Error rate <1% for 24 hours
- [ ] Code reviewed and merged to main

## Notes

These are fundamental implementation bugs that completely prevent the system from functioning. They must be fixed before any other work proceeds. The issues suggest the code may not have been tested end-to-end before deployment.

## Recommended Team

- **Lead**: Senior Backend Engineer (Python/FastAPI experience)
- **Support**: DevOps Engineer (for deployment validation)
- **QA**: Test Engineer (for integration test suite)

## Post-Sprint Actions

1. Add CI/CD pipeline tests to prevent similar issues
2. Implement automated integration testing
3. Add monitoring alerts for API errors
4. Consider code review process improvements
5. Document lessons learned

---

**Created**: 2025-01-14
**Author**: Claude (Bug Investigation)
**Status**: Ready for Implementation