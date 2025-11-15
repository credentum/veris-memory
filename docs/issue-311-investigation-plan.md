# Issue #311: Hybrid Search Only Returns Vector Results

**Issue URL**: https://github.com/credentum/veris-memory/issues/311
**Investigation Date**: 2025-11-15
**Investigator**: Claude Agent
**Branch**: `investigate/issue-311-hybrid-search`

---

## Problem Statement

The `retrieve_context` endpoint reports using `"search_mode_used": "hybrid"` but all returned results show `"source": "vector"`. Graph-based and keyword-based results never appear in the results, even though the hybrid search infrastructure exists.

---

## Root Cause Analysis

### 1. Text Backend Not Registered

**Location**: `src/mcp_server/main.py:949-973`

**Finding**: The MCP server initialization registers:
- ✅ **Vector backend** (line 952)
- ✅ **Graph backend** (line 961)
- ✅ **KV backend** (line 970)
- ❌ **Text backend** - **NOT REGISTERED**

**Evidence**:
```python
# src/mcp_server/main.py
query_dispatcher.register_backend("vector", vector_backend)  # ✅ Registered
query_dispatcher.register_backend("graph", graph_backend)    # ✅ Registered
query_dispatcher.register_backend("kv", kv_backend)          # ✅ Registered
# Text backend registration missing!                          # ❌ NOT REGISTERED
```

**Impact**: The `TextBackend` class exists (`src/backends/text_backend.py`) but is never instantiated or registered, so keyword/BM25 search is unavailable.

---

### 2. Graph Backend May Have Empty Results

**Location**: `src/backends/graph_backend.py:42-92`

**Finding**: The graph backend IS registered and CAN return results with `source=ResultSource.GRAPH` (line 340), BUT it may be returning empty results for most queries.

**Why Graph Returns Empty**:
The graph backend's `_build_search_query()` method likely performs text matching on graph nodes. If:
- No nodes have matching text content
- The Cypher query is too restrictive
- Graph relationships haven't been created (Issue #310!)

Then graph backend returns `[]` empty results.

**Evidence from Testing**:
```bash
# My test: Stored 3 contexts with clear semantic relationships
# Relationship creation: 0 for all contexts (Issue #310)
# Graph query for relationships: Returns [] empty
```

**Relationship to Issue #310**: Issue #310 identified that `relationships_created: 0` for all stored contexts. If no relationships exist in the graph, graph traversal queries will naturally return no results.

---

### 3. KV Backend Scope

**Location**: `src/backends/kv_backend.py`

**Finding**: The KV backend is designed for direct key lookups, not semantic search.

**Typical KV Usage**:
- Direct ID lookups: `get_context_by_id(id)`
- Namespace queries: `list_contexts_in_namespace(namespace)`
- NOT semantic text search

**Result**: KV backend likely returns empty results `[]` for text queries in hybrid mode, which is expected behavior.

---

### 4. Hybrid Search Result Merging Works Correctly

**Location**: `src/core/query_dispatcher.py:189`

**Finding**: The result merging logic IS correct:
```python
# Line 189
merged_results = merge_results(*all_results.values()) if all_results else []
```

**How It Works**:
1. Dispatcher calls all registered backends in parallel (PARALLEL policy)
2. Collects results: `{` 'vector': [results], 'graph': [], 'kv': [] `}`
3. Merges with `merge_results()` which combines lists and deduplicates by ID
4. Result: Only vector results appear because graph/kv returned empty

**Verification**: The `merge_results()` function in `src/interfaces/memory_result.py:170-189` correctly preserves the `source` field from each result.

---

## Why Only Vector Results Appear

**The Chain of Events**:

1. **User Query**: `"How should I handle MCP integration?"`
2. **Dispatcher**: Selects backends `["vector", "graph", "kv"]` for HYBRID mode
3. **Parallel Execution**:
   - **Vector backend**: Returns 10 results with `source="vector"` ✅
   - **Graph backend**: Returns 0 results (no relationships exist)
   - **KV backend**: Returns 0 results (not designed for text search)
   - **Text backend**: NOT CALLED (not registered)
4. **Merge**: `merge_results([vector_results], [], [])` = only vector results
5. **Response**: `"search_mode_used": "hybrid"` but all `source="vector"`

**Conclusion**: The system REPORTS hybrid mode correctly, but only vector backend produces results. Graph/KV/Text backends either aren't registered or return empty results.

---

## Proposed Fix

### Fix #1: Register Text Backend (CRITICAL)

**Priority**: HIGH
**Impact**: Enables keyword/BM25 search for better recall

**Implementation**:

```python
# src/mcp_server/main.py (around line 973)

# Add after KV backend registration:
# Register text backend (BM25 keyword search)
if neo4j_client:  # Text backend can use Neo4j for full-text search
    try:
        from ..backends.text_backend import TextBackend
        text_backend = TextBackend(neo4j_client)
        query_dispatcher.register_backend("text", text_backend)
        logger.info("✅ Text backend registered with MCP dispatcher")
    except Exception as e:
        logger.warning(f"⚠️ Text backend initialization failed: {e}")
```

**Notes**:
- Verify `TextBackend` constructor signature
- Check if it requires Neo4j or a separate text index
- Test that it sets `source=ResultSource.TEXT`

---

### Fix #2: Improve Graph Backend Query Logic (MEDIUM)

**Priority**: MEDIUM
**Impact**: Graph backend can return results even without relationships

**Current Limitation**: Graph backend only returns results if:
- Text matches node properties
- Relationships exist for traversal

**Proposed Enhancement**:
```python
# src/backends/graph_backend.py

def _build_search_query(self, query: str, options: SearchOptions):
    """
    Build Cypher query that ALWAYS returns relevant nodes,
    even if no relationships exist.
    """
    # Current: Requires relationship traversal (too restrictive)
    # Enhanced: Text search on node properties as fallback

    cypher = """
    MATCH (n:Context)
    WHERE n.text CONTAINS $query_text
       OR n.title CONTAINS $query_text
       OR n.content CONTAINS $query_text
    RETURN n
    ORDER BY n.created_at DESC
    LIMIT $limit
    """
    return cypher, {"query_text": query, "limit": options.limit}
```

**Benefit**: Graph backend returns results based on content matching, not just relationships.

---

### Fix #3: Fix Relationship Auto-Creation (Addresses Issue #310)

**Priority**: HIGH (but separate issue)
**Impact**: Once relationships exist, graph traversal becomes valuable

**See Issue #310** for full plan on auto-creating relationships.

**Quick Win**: Manually create test relationships to verify graph backend works:
```cypher
# Test in Neo4j
MATCH (a:Context), (b:Context)
WHERE a.id = "c461d52c..." AND b.id = "41d65223..."
CREATE (a)-[:REFERENCES]->(b)
```

---

### Fix #4: Add Result Source Breakdown to Response (OPTIONAL)

**Priority**: LOW
**Impact**: Better visibility into which backends contributed results

**Enhancement**:
```python
# src/core/query_dispatcher.py

return SearchResultResponse(
    success=True,
    results=final_results,
    search_mode_used=search_mode.value,
    backends_used=list(backends_used),
    backend_timings=backend_timings,
    # NEW: Add source breakdown
    source_breakdown={
        "vector": sum(1 for r in final_results if r.source == "vector"),
        "graph": sum(1 for r in final_results if r.source == "graph"),
        "text": sum(1 for r in final_results if r.source == "text"),
        "kv": sum(1 for r in final_results if r.source == "kv"),
    }
)
```

**Benefit**: Response shows `"source_breakdown": {"vector": 10, "graph": 0, "text": 0}` so users understand the hybrid composition.

---

## Implementation Plan

### Phase 1: Quick Wins (30 minutes)

1. **Register Text Backend**
   - File: `src/mcp_server/main.py`
   - Add text backend registration after KV backend
   - Verify `TextBackend` initialization requirements
   - Test that hybrid search now includes text results

2. **Verify Backends Are Called**
   - Add debug logging in `query_dispatcher._execute_search()`
   - Log: `f"Backend {backend_name} returned {len(results)} results"`
   - Run test query and check logs

### Phase 2: Testing (30 minutes)

3. **Test Each Backend Independently**
   ```python
   # Test vector only
   search_mode = "vector"  # Should return results with source="vector"

   # Test graph only
   search_mode = "graph"   # May return [] if no relationships

   # Test text only
   search_mode = "text"    # NEW - should work after registration

   # Test hybrid
   search_mode = "hybrid"  # Should show mixed sources
   ```

4. **Create Test Relationships**
   - Manually create some relationships in Neo4j
   - Re-test graph backend
   - Verify graph results appear with `source="graph"`

### Phase 3: Documentation (30 minutes)

5. **Update Issue #311**
   - Report findings
   - Share fix implementation
   - Request testing/review

6. **Update Documentation**
   - Document that text backend needs manual registration
   - Add troubleshooting for "only vector results"
   - Explain source field meanings

---

## Testing Checklist

- [ ] Text backend registered successfully
- [ ] Hybrid search calls all 4 backends (vector, graph, text, kv)
- [ ] Results include mixed sources when available
- [ ] `search_mode_used` accurately reflects mode
- [ ] Backend timings reported for all backends
- [ ] Empty backend results don't crash merger
- [ ] Score threshold works across all backends
- [ ] Limit applies to merged results, not per-backend

---

## Expected Outcome After Fix

### Before Fix:
```json
{
  "search_mode_used": "hybrid",
  "backends_used": ["vector", "graph", "kv"],
  "backend_timings": {"vector": 25.1, "graph": 0.5, "kv": 0.3},
  "results": [
    {"source": "vector", "score": 0.89},
    {"source": "vector", "score": 0.76},
    {"source": "vector", "score": 0.65}
  ]
}
```

### After Fix:
```json
{
  "search_mode_used": "hybrid",
  "backends_used": ["vector", "graph", "text", "kv"],
  "backend_timings": {"vector": 25.1, "graph": 12.3, "text": 8.5, "kv": 0.3},
  "results": [
    {"source": "vector", "score": 0.89},
    {"source": "text", "score": 0.82},
    {"source": "graph", "score": 0.76},
    {"source": "vector", "score": 0.65}
  ],
  "source_breakdown": {"vector": 2, "graph": 1, "text": 1, "kv": 0}
}
```

---

## Open Questions

1. **Text Backend Requirements**: Does `TextBackend` need Neo4j full-text index or separate infrastructure?
2. **Graph Backend Fallback**: Should graph backend do simple text matching when no relationships exist?
3. **Performance**: Is calling 4 backends in parallel causing latency issues?
4. **Score Normalization**: Should scores from different backends be normalized before merging?

---

## Related Issues

- **Issue #310**: Graph relationships not auto-created
- **Issue #312**: Neo4j schema documentation gap
- **Issue #313**: Missing relationship query examples

---

## Next Steps

1. Implement Fix #1 (register text backend)
2. Add debug logging to verify all backends are called
3. Test with sample queries
4. Update issue #311 with findings
5. Consider implementing optional Fix #4 (source breakdown)
