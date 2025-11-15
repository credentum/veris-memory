# Sentinel S5/S8 Investigation Guide

**Created**: 2025-11-15  
**Status**: Active Investigation  
**Priority**: P1 (High)

## Overview

This document provides investigation guidance for S5 (Security Negatives) and S8 (Capacity Smoke) Sentinel check failures.

---

## S5: Security Negatives (2/9 Tests Failing)

### Current Status
- **Overall**: 2 failures detected
- **Severity**: High
- **Message**: "Security vulnerabilities detected: 2 issues found"

### Test Breakdown (9 Total Tests)

1. ✅ **invalid_authentication** - Testing invalid auth rejection
2. ✅ **unauthorized_access** - Testing unauthorized endpoint access
3. ✅ **rate_limiting** - Testing rate limit enforcement
4. ✅ **sql_injection_protection** - Testing SQL injection defenses
5. ❓ **admin_endpoint_protection** - LIKELY FAILING
6. ✅ **cors_policy** - Testing CORS configuration
7. ✅ **input_validation** - Testing input sanitization
8. ✅ **application_attack_patterns** - Testing attack pattern detection
9. ❓ **authentication_anomalies** - LIKELY FAILING

### Most Likely Failures

#### 1. Admin Endpoint Protection

**Location**: `s5_security_negatives.py:368-419`

**Test Logic**:
```python
# Tests admin endpoints like /admin, /internal, /debug
# Expected: 401 Unauthorized or 403 Forbidden
# EXCEPTION: Development mode allows access (lines 382-393)
```

**Potential Issues**:
- ENVIRONMENT variable set to "production" but admin endpoints still accessible
- Development mode check failing (not detecting ENVIRONMENT correctly)
- Admin endpoints returning 200 OK instead of 401/403

**Investigation Steps**:
```bash
# 1. Check ENVIRONMENT variable in Sentinel container
docker exec veris-memory-dev-sentinel-1 env | grep ENVIRONMENT

# 2. Test admin endpoint directly
curl -i http://localhost:8000/admin

# 3. Check logs for admin endpoint access
docker logs veris-memory-dev-context-store-1 | grep -i "admin\|internal\|debug"

# 4. Verify FastAPI route definitions
grep -r "@app\\.get.*admin" src/
```

**Expected Fix**:
- If production: Add authentication middleware to admin endpoints
- If development: Verify ENVIRONMENT variable is correctly set

#### 2. Authentication Anomalies

**Location**: `s5_security_negatives.py:624-719`

**Test Logic**:
```python
# Sends 50 rapid failed authentication attempts
# Measures: attempts_per_minute, time_to_detection, rate_limit_triggered
# FAILS if: >100 failed attempts/minute without rate limiting (line 684-690)
```

**Potential Issues**:
- No rate limiting configured on authentication endpoints
- Rate limiting exists but threshold >100 attempts/minute
- Authentication endpoint doesn't track failed attempts

**Investigation Steps**:
```bash
# 1. Check if rate limiting is configured
grep -r "RateLimiter\|SlowAPI" src/

# 2. Test authentication rate limiting
for i in {1..60}; do
  curl -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"fake","password":"fake"}' &
done
wait

# 3. Check authentication logs
docker logs veris-memory-dev-context-store-1 | grep -i "auth\|login" | tail -100
```

**Expected Fix**:
- Implement rate limiting using slowapi or similar:
  ```python
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter

  @app.post("/auth/login")
  @limiter.limit("20/minute")  # 20 attempts per minute
  async def login(credentials: LoginRequest):
      ...
  ```

---

## S8: Capacity Smoke (1/7 Tests Failing)

### Current Status
- **Overall**: 1 failure detected
- **Severity**: Medium
- **Message**: "Capacity issues detected: 1 problems found"

### Test Breakdown (7 Total Tests)

1. ✅ **concurrent_requests** - 50 concurrent requests
2. ✅ **sustained_load** - 30 second sustained load
3. ✅ **system_resources** - CPU/memory monitoring
4. ✅ **database_connections** - Connection pool testing
5. ✅ **memory_usage** - Memory leak detection
6. ❓ **response_times** - LIKELY FAILING
7. ❓ **resource_exhaustion_attacks** - POSSIBLE FAILURE

### Most Likely Failures

#### 1. Response Times

**Location**: `s8_capacity_smoke.py:564-642`

**Test Logic**:
```python
# Thresholds (lines 595-600):
# - avg_response_time > 2500ms → FAIL
# - p95_response_time > 5000ms → FAIL
# - max_response_time > 12500ms → FAIL
# - coefficient_of_variation > 1.0 → FAIL (high variability)
```

**Potential Issues**:
- Average response time exceeding 2500ms under load
- High response time variability (inconsistent performance)
- Slow database queries or external API calls
- Resource contention (CPU/memory/disk)

**Investigation Steps**:
```bash
# 1. Check current response times
curl -w "\nTime: %{time_total}s\n" http://localhost:8000/api/v1/contexts/search \
  -X POST -H "Content-Type: application/json" \
  -d '{"query":"test","limit":10}'

# 2. Run load test with timing
ab -n 100 -c 10 -p search.json -T application/json \
  http://localhost:8000/api/v1/contexts/search

# 3. Check slow query logs (Neo4j, Qdrant)
docker logs veris-memory-dev-neo4j-1 | grep -i "slow"
docker logs veris-memory-dev-qdrant-1 | grep -i "slow\|timeout"

# 4. Profile endpoint performance
python -m cProfile -o profile.stats scripts/api-load-test.py
python -m pstats profile.stats
```

**Optimization Options**:
1. **If thresholds too strict**: Increase S8_MAX_RESPONSE_TIME_MS in .env.sentinel
   ```bash
   # Current: 2500ms
   # Proposed: 3500ms (if REST forwarding adds overhead)
   S8_MAX_RESPONSE_TIME_MS=3500
   ```

2. **If actual performance issue**:
   - Add database query caching
   - Optimize Neo4j/Qdrant queries
   - Add connection pooling
   - Enable async query execution

#### 2. Resource Exhaustion Attacks

**Location**: `s8_capacity_smoke.py:729-924`

**Test Logic**:
```python
# Sends burst of 100 rapid requests
# FAILS if (lines 834-843, 892):
# - Error rate > 5% under load
# - Response time degrades >10x
# - CPU usage > 80%
```

**Investigation Steps**:
```bash
# 1. Monitor resource usage during load
docker stats --no-stream veris-memory-dev-context-store-1

# 2. Check for connection exhaustion
netstat -an | grep :8000 | grep TIME_WAIT | wc -l

# 3. Review error logs under load
# (Run load test then check logs)
docker logs veris-memory-dev-context-store-1 --tail 500 | grep -i "error\|timeout\|refused"
```

---

## Recommended Action Plan

### Immediate (P0)
1. ✅ **Run investigation scripts** (provided above) to identify exact failures
2. ✅ **Check Sentinel logs** for detailed failure messages:
   ```bash
   docker logs veris-memory-dev-sentinel-1 | grep "S5\|S8" | tail -100
   ```

### Short-term (P1)
1. **S5 Admin Protection**: 
   - Add auth middleware if production
   - OR verify ENVIRONMENT=development is set correctly

2. **S5 Rate Limiting**:
   - Implement slowapi rate limiting on auth endpoints
   - Configure: 20 attempts/minute per IP

3. **S8 Response Times**:
   - Profile slow endpoints
   - Optimize or increase threshold to 3500ms

### Long-term (P2)
1. Add comprehensive rate limiting across all endpoints
2. Implement request queuing for burst protection
3. Add query result caching (Redis)
4. Set up APM (Application Performance Monitoring)
5. Configure auto-scaling based on load

---

## Verification After Fixes

### S5 Verification
```bash
# Run security tests manually
python -m pytest tests/monitoring/sentinel/test_s5_security.py -v

# Check Sentinel S5 status
curl http://localhost:9090/api/v1/checks/S5-security-negatives | jq '.status'
```

### S8 Verification
```bash
# Run capacity tests manually
python -m pytest tests/monitoring/sentinel/test_s8_capacity.py -v

# Check Sentinel S8 status
curl http://localhost:9090/api/v1/checks/S8-capacity-smoke | jq '.status'
```

---

## Related Documentation

- S5 Check Source: `src/monitoring/sentinel/checks/s5_security_negatives.py`
- S8 Check Source: `src/monitoring/sentinel/checks/s8_capacity_smoke.py`
- Sentinel API: `src/monitoring/sentinel/api.py`
- Rate Limiting Guide: `docs/SECURITY_SETUP.md` (to be created)
- Performance Tuning: `docs/PERFORMANCE_OPTIMIZATION.md` (to be created)

---

## Investigation Log

| Date | Investigator | Finding | Action Taken |
|------|-------------|---------|--------------|
| 2025-11-15 | Claude Code | Created investigation guide | Document created |
| | | S5: 2/9 tests failing | Identified likely failures |
| | | S8: 1/7 tests failing | Provided investigation steps |

---

**Next Steps**: Run investigation scripts and update this document with findings.
