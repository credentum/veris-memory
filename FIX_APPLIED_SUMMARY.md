# ✅ Sentinel Authentication Fix Applied

## What Was Wrong:
1. **Sentinel service** didn't have `API_KEY_MCP` in its environment variables
2. **API service** didn't have `API_KEY_MCP` in its environment variables
3. **Monitoring dashboard** didn't have `API_KEY_MCP` in its environment variables
4. **Sentinel code** wasn't including the API key in HTTP request headers

## What Was Fixed:

### 1. Updated `docker-compose.yml`:
Added `API_KEY_MCP=${API_KEY_MCP}` to:
- ✅ **sentinel** service (line 213)
- ✅ **api** service (line 57)
- ✅ **monitoring-dashboard** service (line 173)

### 2. Updated `src/monitoring/sentinel/base_check.py`:
- ✅ Added `import os` (line 9)
- ✅ Modified `test_api_call` method to include API key header (lines 215-219)

## Files Modified:
```
docker-compose.yml
src/monitoring/sentinel/base_check.py
```

## Deployment Steps (On Server):

```bash
# 1. Pull the updated code
git pull

# 2. Rebuild and restart services
docker-compose down
docker-compose build sentinel api monitoring-dashboard
docker-compose up -d

# 3. Wait for services to be healthy (about 60 seconds)
sleep 60
docker-compose ps

# 4. Test that Sentinel S2 checks now work
docker exec veris-memory_sentinel_1 python -c "
import asyncio
from src.monitoring.sentinel.checks.s2_golden_fact_recall import GoldenFactRecall
from src.monitoring.sentinel.models import SentinelConfig

async def test():
    config = SentinelConfig()
    check = GoldenFactRecall(config)
    result = await check.run_check()
    print(f'S2 Check Status: {result.status}')
    print(f'Message: {result.message}')
    return result.status != 'fail'

asyncio.run(test())
"

# 5. Check Sentinel logs for authentication errors
docker logs veris-memory_sentinel_1 --tail 50 | grep -E "401|auth|API"
```

## Verification:

After applying the fixes, the S2 check should:
- ✅ No longer get HTTP 401 errors
- ✅ Successfully store and retrieve test facts
- ✅ Report "pass" or "warn" status (not "fail")

## What This Fixes:

- **Sentinel S2 checks** will now authenticate properly
- **All monitoring checks** requiring API access will work
- **Service-to-service communication** will be authenticated
- **Consistent authentication** across all services

## Note:
The `.env` file on the server must contain:
```
API_KEY_MCP=<your-actual-api-key-value>
```

This fix ensures all services that need to make API calls to the context-store have the necessary authentication credentials.