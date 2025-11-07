# Phase 1: Authentication & Connectivity Fix

## Files to Modify:

### 1. Fix Sentinel API Authentication
**File**: `src/monitoring/sentinel/base_check.py`

Add authentication headers to the `test_api_call` method:

```python
# Line 214: Add API key header support
request_kwargs = {
    "timeout": aiohttp.ClientTimeout(total=timeout),
    "headers": {
        "Content-Type": "application/json",
        "X-API-Key": os.getenv("API_KEY_MCP", "vmk_test_a1b2c3d4e5f6789012345678901234567890")
    }
}
```

### 2. Update Docker Compose Environment
**File**: `docker-compose.yml`

Add API_KEY_MCP to sentinel service (line 198):

```yaml
sentinel:
  environment:
    # Add this line
    - API_KEY_MCP=${API_KEY_MCP:-vmk_mcp_903e1bcb70d704da4fbf207722c471ba:sentinel:writer:true}
```

Also add to api service (line 46):

```yaml
api:
  environment:
    # Add this line
    - API_KEY_MCP=${API_KEY_MCP:-vmk_mcp_903e1bcb70d704da4fbf207722c471ba:api:writer:false}
```

### 3. Create Environment File Template
**File**: `.env.local`

```bash
# Sprint 13 Authentication
API_KEY_MCP=vmk_mcp_903e1bcb70d704da4fbf207722c471ba:mcp_server:writer:true

# Database Passwords
NEO4J_PASSWORD=secure_password_here
NEO4J_RO_PASSWORD=readonly_secure_2024!

# Environment
ENVIRONMENT=development
AUTH_REQUIRED=true
```

## Testing Phase 1:

```bash
# 1. Apply the fixes
cd /claude-workspace/worktrees/sessions/session-20251107-000050-3532990/veris-memory

# 2. Restart services
docker-compose down
docker-compose up -d

# 3. Wait for services to be healthy
docker-compose ps

# 4. Test Sentinel S2 check
docker exec veris-memory_sentinel_1 python -m src.monitoring.sentinel.checks.s2_golden_fact_recall
```

## Expected Result:
- S2 checks should pass without 401 errors
- API authentication should work across all services