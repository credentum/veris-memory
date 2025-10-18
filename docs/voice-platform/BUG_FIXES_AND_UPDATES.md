# Voice Bot Integration - Bug Fixes and Updates

**Date**: 2025-10-18
**Session**: session-20251018-213137-2793343
**Related PRs**: #159, #160

## Summary

Updated voice-bot integration to match recent bug fixes in veris-memory (PR #159 and #160). The main issue was that the initial voice-bot implementation used an incorrect MCP endpoint format that doesn't exist in the actual server.

## Bug Fixes from Veris-Memory

### PR #159: Comprehensive Search System Fixes

Three critical fixes were made to the search system:

1. **Vector Collection Mismatch** (CRITICAL)
   - **Issue**: Collection name was `context_embeddings` (empty) instead of `project_context` (contains data)
   - **Fix**: Changed `VECTOR_COLLECTION=project_context` in vector backend
   - **Impact**: Vector searches now return actual results

2. **Text Field Extraction Errors**
   - **Issue**: Validation failures when text fields were empty or nested
   - **Fix**: Added `_extract_text_content()` with 5 fallback strategies
   - **Impact**: Robust text processing for all content types

3. **Redis KV Backend Compatibility**
   - **Issue**: Missing `get()` method on RedisConnector class
   - **Fix**: Added `get()` method delegating to `get_cache()`
   - **Impact**: KV backend operations work without crashes

### PR #160: Documentation Updates

- Updated README to reflect v0.9.0 changes
- Fixed `VECTOR_COLLECTION` environment variable documentation
- Organized repository structure (moved 44 files to appropriate directories)

## Voice Bot Integration Updates

### Issue Discovered

The initial voice-bot implementation used a **non-existent MCP endpoint**:

```python
# ❌ INCORRECT (doesn't exist in MCP server)
POST /mcp/v1/call_tool
{
  "method": "call_tool",
  "params": {
    "name": "store_context",
    "arguments": {...}
  }
}
```

### Correct MCP Endpoint Format

The actual MCP server uses **direct tool endpoints**:

```python
# ✅ CORRECT (actual endpoint)
POST /tools/store_context
{
  "type": "log",
  "content": {...},
  "metadata": {...}
}
```

### Changes Made to Voice Bot

#### 1. Updated `memory_client.py`

**File**: `voice-bot/app/memory_client.py`

**Changed Methods**:
- `store_fact()` - Now uses `/tools/store_context`
- `_get_fact_by_key()` - Now uses `/tools/retrieve_context`
- `_semantic_fact_search()` - Now uses `/tools/retrieve_context`
- `store_conversation_trace()` - Now uses `/tools/store_context`

**Key Changes**:

1. **Endpoint URLs**: Changed from `/mcp/v1/call_tool` to `/tools/{tool_name}`
2. **Payload Format**: Removed wrapper structure, send payload directly
3. **Context Types**: Changed from `"fact"` (invalid) to `"log"` (valid)
4. **Allowed Types**: Only these types are valid:
   - `design` - Design decisions
   - `decision` - Project decisions
   - `trace` - Conversation traces
   - `sprint` - Sprint-related context
   - `log` - Log entries (used for facts)

#### 2. Updated Fact Storage Strategy

**Before**:
```python
payload = {
  "method": "call_tool",
  "params": {
    "name": "store_context",
    "arguments": {
      "type": "fact",  # ❌ Invalid type
      "content": {...}
    }
  }
}
```

**After**:
```python
payload = {
  "type": "log",  # ✅ Valid type for user facts
  "content": {
    "namespace": f"voicebot_{user_id}",
    "user_id": user_id,
    "key": key,
    "value": value,
    "timestamp": datetime.utcnow().isoformat()
  },
  "metadata": {
    "source": "voice_input",
    "fact_key": f"voicebot_{user_id}:{key}",
    "fact_type": "user_attribute"
  }
}
```

#### 3. Updated Retrieval Strategy

**Before**:
```python
POST /mcp/v1/call_tool  # ❌ Doesn't exist
{
  "method": "call_tool",
  "params": {
    "name": "retrieve_context",
    "arguments": {"query": "...", "filters": {...}}
  }
}
```

**After**:
```python
POST /tools/retrieve_context  # ✅ Correct endpoint
{
  "query": "user facts",
  "type": "log",
  "search_mode": "hybrid",
  "limit": 5,
  "filters": {
    "content.user_id": user_id,
    "metadata.fact_type": "user_attribute"
  }
}
```

## Impact on Voice Bot Functionality

### What Still Works

✅ **Health Checks**: No changes needed
✅ **FastAPI Endpoints**: All voice-bot endpoints unchanged
✅ **Docker Configuration**: No changes needed
✅ **LiveKit Integration**: Unaffected

### What Was Fixed

✅ **MCP Storage**: Now uses correct endpoint (`/tools/store_context`)
✅ **MCP Retrieval**: Now uses correct endpoint (`/tools/retrieve_context`)
✅ **Context Types**: Now uses valid type (`log` instead of `fact`)
✅ **Payload Format**: Now matches actual MCP server expectations

### What Needs Testing

🧪 **End-to-End Integration**:
1. Store fact via voice-bot API
2. Verify storage in MCP server
3. Retrieve fact via voice-bot API
4. Verify persistence across restarts

## Testing Plan

### 1. Manual Testing

```bash
# Start services
cd /claude-workspace/worktrees/sessions/session-20251018-213137-2793343/veris-memory
docker compose up -d

# Wait for MCP server to be ready
sleep 30

# Test fact storage
curl -X POST "http://localhost:8002/api/v1/facts/store?user_id=test123&key=name&value=Alice"

# Test fact retrieval
curl "http://localhost:8002/api/v1/facts/test123?keys=name"

# Expected response:
# {
#   "user_id": "test123",
#   "facts": {"name": "Alice"},
#   "count": 1,
#   "timestamp": "..."
# }
```

### 2. Persistence Testing

```bash
# Store fact
curl -X POST "http://localhost:8002/api/v1/facts/store?user_id=alice&key=color&value=blue"

# Restart voice-bot container
docker compose restart voice-bot

# Wait for restart
sleep 10

# Retrieve fact (should still be there)
curl "http://localhost:8002/api/v1/facts/alice?keys=color"

# Expected: {"color": "blue"}
```

### 3. Echo Test (Sprint 1 Validation)

```bash
# First message
curl -X POST "http://localhost:8002/api/v1/voice/echo-test?user_id=bob&message=My%20name%20is%20Bob"

# Restart container
docker compose restart voice-bot && sleep 10

# Second message (should remember name)
curl -X POST "http://localhost:8002/api/v1/voice/echo-test?user_id=bob&message=What%20is%20my%20name"

# Expected response should include "Bob"
```

## Files Changed

```
voice-bot/app/memory_client.py  # Updated MCP integration
docs/voice-platform/BUG_FIXES_AND_UPDATES.md  # This document
```

## Next Steps

1. ✅ Update memory_client.py with correct endpoints
2. 📝 Create this documentation
3. 🧪 Test integration with running MCP server
4. 🎯 Run Sprint 1 validation tests
5. 📦 Commit changes to repository

## References

- **PR #159**: Comprehensive Search System Fixes
- **PR #160**: Documentation Updates
- **MCP Server Code**: `src/mcp_server/main.py`
- **Vector Backend**: `src/backends/vector_backend.py` (collection name fix)
- **KV Store**: `src/storage/kv_store.py` (get() method added)

## Lessons Learned

1. **Always verify API endpoints** - The initial implementation assumed an endpoint format that didn't exist
2. **Check allowed values** - Context types are restricted to specific values
3. **Review recent changes** - Bug fixes in the main repo can affect integrations
4. **Test against actual server** - Would have caught the endpoint mismatch immediately

---

**Status**: ✅ Fixed and ready for testing
**Version**: Voice Bot v1.0.1 (post-bugfix)