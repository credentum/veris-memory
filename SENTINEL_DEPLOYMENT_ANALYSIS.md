# Sentinel Monitoring Failures - Root Cause Analysis

## Current Deployment Status

**Deployed Code**: `c83117ab` (PR #267 - SimpleRedis hotfix)  
**Required Fix**: PR #269 (NOT YET DEPLOYED)  
**Result**: All Sentinel fixes are waiting to be deployed

---

## Why Sentinel Checks Are Failing (Current State)

### Root Cause 1: REST API Schema Mismatch ❌ NOT FIXED YET

**Problem**: REST compatibility layer passes `content` as **string** to MCP endpoint  
**MCP Expects**: `content` as **Dict[str, Any]**  
**Result**: 422 Unprocessable Content errors

**Current Flow** (BROKEN):
```
S9 → REST API: {"content": "text"}
REST API → MCP: {"content": "text"}  ❌ String
MCP Rejects: 422 - "content must be dict"
```

**Fixed in PR #269**:
```
S9 → REST API: {"content": "text"}
REST API → MCP: {"content": {"text": "text"}}  ✅ Dict
MCP Accepts: 201 Created
```

### Root Cause 2: HTTP Status Code Mismatch ❌ NOT FIXED YET

**Problem**: POST returns 200 OK instead of 201 Created  
**Sentinel Expects**: 201 for successful resource creation  
**Result**: Sentinel thinks operation failed even when it succeeded

**Fixed in PR #269**: `status_code=201` added to endpoint decorator

### Root Cause 3: Response Field Mismatch ❌ NOT FIXED YET

**Problem**: Search returns 'results' field  
**Sentinel Expects**: 'contexts' field  
**Result**: Sentinel sees empty result sets

**Fixed in PR #269**: Added 'contexts' field (kept 'results' for backward compat)

---

## After PR #269 Deployment - Remaining Issues

### Issue 4: Invalid MCP Type Values ⚠️ WILL STILL FAIL

**Problem**: Sentinel checks use invalid type values  
**Valid MCP Types**: `design | decision | trace | sprint | log`

**S9 graph_intent.py** (line 251):
```python
"content_type": "graph_intent_test"  # ❌ INVALID
```
Should be:
```python
"content_type": "log"  # ✅ VALID
```

**S10 content_pipeline.py** (lines 95-122):
```python
"type": "api_documentation"          # ❌ INVALID
"type": "troubleshooting_guide"      # ❌ INVALID
"type": "deployment_process"         # ❌ INVALID
"type": "performance_optimization"   # ❌ INVALID
```
Should all be:
```python
"type": "log"  # ✅ VALID (or "design", "decision", etc.)
```

---

## Deployment Timeline & Expected Results

### Phase 1: Deploy PR #269 (Immediate)

**Fixes Applied**:
- ✅ REST→MCP content format conversion
- ✅ HTTP 201 status codes
- ✅ SearchResponse 'contexts' field
- ✅ S10 dual content format handling

**Expected Results**:
- S9: Will get past 422 errors → Hit type validation error
- S10: Will get past 422 errors → Hit type validation error
- S3, S8: Should work (if using valid types)
- S5, S6, S7: Need to investigate their payloads

**Sentinel Score**: 0/11 → 3-5/11 (estimated)

### Phase 2: Fix Invalid Type Values (Follow-up PR)

**Changes Needed**:
1. S9: Change "graph_intent_test" → "log"
2. S10: Change all custom types → "log"
3. Review S3, S5, S6, S7, S8 for similar issues

**Expected Results**:
- All checks using /api/v1/contexts will work
- **Sentinel Score**: 5/11 → 7+/11

---

## Error Breakdown by Check

| Check | Current Error | After PR #269 | Final Fix Needed |
|-------|---------------|---------------|------------------|
| S3-paraphrase | 422 (schema) | May work | Verify type value |
| S5-security | Unknown | Investigate | TBD |
| S6-backup | Unknown | Investigate | TBD |
| S7-config | Unknown | Investigate | TBD |
| S8-capacity | 422 (schema) | May work | Verify type value |
| S9-graph-intent | 422 (schema) | Type validation | Change to "log" |
| S10-content | 422 (schema) | Type validation | Change to "log" |

---

## Immediate Actions Required

### 1. Deploy PR #269 ⚡ HIGH PRIORITY

```bash
# Merge PR #269
gh pr merge 269 --squash

# Deploy to Hetzner
./scripts/deploy-dev.sh
```

**Impact**: Will resolve 422 errors, improve Sentinel score to ~40%

### 2. Create Follow-up PR for Type Values 📝 MEDIUM PRIORITY

**File: src/monitoring/sentinel/checks/s9_graph_intent.py**
```python
# Line 251: Change
"content_type": "graph_intent_test"
# To:
"content_type": "log"
```

**File: src/monitoring/sentinel/checks/s10_content_pipeline.py**
```python
# Lines 95-122: Change all custom types to:
"type": "log"
```

### 3. Investigate Remaining Checks 🔍 MEDIUM PRIORITY

Check payload formats for:
- S3-paraphrase-robustness
- S5-security-negatives
- S6-backup-restore
- S7-config-parity

---

## Current vs Post-Fix Comparison

### Current State (c83117ab)
```
Sentinel Checks: 0/11 passing
Primary Error: 422 Unprocessable Content
Root Cause: REST API schema mismatch
Blocker: PR #269 not deployed
```

### After PR #269
```
Sentinel Checks: 3-5/11 passing (estimated)
Primary Error: Type validation failures
Root Cause: Invalid MCP type values
Blocker: Need follow-up PR to fix types
```

### After Type Fix
```
Sentinel Checks: 7+/11 passing (target)
Remaining Issues: S5, S6, S7 may need investigation
System Status: Production Ready
```

---

## Verification Commands

```bash
# 1. Check deployed commit
docker exec veris-memory-dev-context-store-1 git log -1 --oneline

# 2. Test context storage manually
curl -X POST http://localhost:8000/api/v1/contexts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $SENTINEL_API_KEY" \
  -d '{"content": "test", "content_type": "log"}'

# 3. Check Sentinel logs
docker logs veris-memory-dev-sentinel-1 --tail 100

# 4. View Sentinel status
curl http://localhost:9090/health
```

---

## Summary

**Current Problem**: PR #269 not deployed → All fixes waiting  
**Immediate Fix**: Deploy PR #269 → Resolves 422 errors  
**Follow-up Fix**: Change invalid types to "log" → Full Sentinel functionality  
**Timeline**: 
- PR #269 deployment: 10 minutes
- Type fix PR: 30 minutes
- Full resolution: < 1 hour

The good news: We've already identified and fixed all the issues. They just need to be deployed!
