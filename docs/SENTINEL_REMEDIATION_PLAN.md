# Sentinel Health Check Failures - Remediation Plan

**Date**: November 6, 2025
**System**: veris-memory on Hetzner (135.181.4.118)
**Status**: 10/11 checks failing, 1 unknown
**Severity**: CRITICAL

---

## Executive Summary

After merging PR #163 (Sentinel fixes), 10 out of 11 health checks are now failing. Root cause analysis indicates a **service integration breakdown** likely caused by:

1. **Incomplete deployment** of PR #163 changes
2. **Service endpoint path mismatches** (HTTP 404 errors)
3. **API authentication not properly configured** (Sprint 13)
4. **Network/DNS resolution issues** between containers

**Critical Constraint**: Sentinel runs in a Docker container and cannot execute `docker` commands. All diagnostics must be done via:
- API calls from within containers
- Host-level commands (run outside container)
- Service-to-service HTTP requests

---

## Root Cause Analysis

### Primary Issue: S1 Health Probe Failures (HTTP 404)

**Symptom**: All health endpoint requests return 404
**Impact**: Foundation check failing → All dependent checks cascade fail

**Likely Causes**:
1. **Endpoint path mismatch**: Sentinel expects `/health/live` and `/health/ready`, but services may expose `/health` only
2. **Service URL incorrect**: TARGET_BASE_URL may not match actual service names post-PR #163
3. **Network isolation**: Sentinel container cannot reach other services on expected network
4. **API key header not being sent**: Sprint 13 authentication blocking requests

### Secondary Issues

**S5 (Security)**: If API key validation isn't working, it could either be:
- Too permissive (security risk)
- Too restrictive (blocking legitimate requests)

**S2, S9 (Database)**: Dependent on S1 working first

**S8 (Capacity)**: May be symptom of failing checks consuming resources

---

## Investigation Steps (Run from HOST)

Before starting fixes, gather diagnostic data:

### Step 1: Verify Services Are Running

```bash
# On host (135.181.4.118)
ssh user@135.181.4.118

# Check all containers are up
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Expected output:
# veris-sentinel                    Up (healthy)
# veris-memory-dev-context-store-1  Up (healthy)
# veris-memory-dev-api-1            Up (healthy)
# veris-memory-dev-neo4j-1          Up (healthy)
# veris-memory-dev-qdrant-1         Up (healthy)
# veris-memory-dev-redis-1          Up (healthy)
```

### Step 2: Test Health Endpoints from Host

```bash
# Test context-store health endpoint
curl -v http://localhost:8000/health
curl -v http://localhost:8000/health/live
curl -v http://localhost:8000/health/ready

# Test with API key
curl -H "X-API-Key: $API_KEY_MCP" http://localhost:8000/health

# Test API server
curl -v http://localhost:8001/health
curl -v http://localhost:8001/api/v1/health/live
```

### Step 3: Test from Inside Sentinel Container

```bash
# Enter Sentinel container
docker exec -it veris-sentinel sh

# Test service discovery (DNS resolution)
nslookup context-store
nslookup api

# Test HTTP connectivity
wget -O- http://context-store:8000/health
wget -O- --header="X-API-Key: $API_KEY_MCP" http://context-store:8000/health

# Check environment variables
env | grep -E 'API_KEY|TARGET|SENTINEL'
```

### Step 4: Check Logs for Errors

```bash
# On host
docker logs veris-sentinel --tail=100 | grep -i "error\|404\|fail"
docker logs veris-memory-dev-context-store-1 --tail=50 | grep -i "error"
docker logs veris-memory-dev-api-1 --tail=50 | grep -i "error"
```

### Step 5: Verify Network Configuration

```bash
# On host
docker network inspect veris-memory-dev_default

# Check Sentinel is on correct network
docker inspect veris-sentinel | grep -A 10 Networks
```

---

## Phased Remediation Plan

### **PHASE 1: Foundation - Fix S1 Health Probes** (Priority: CRITICAL)

**Goal**: Restore basic service connectivity and health monitoring

**Time Estimate**: 30-60 minutes

#### Issue 1.1: Endpoint Path Mismatch

**Diagnosis**:
```bash
# From host, test all possible health endpoint paths:
curl -i http://localhost:8000/health
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
curl -i http://localhost:8000/api/v1/health
```

**Fix Options**:

**Option A**: If services use `/health` (not `/health/live`):
```python
# File: src/monitoring/sentinel/checks/s1_health_probes.py
# Line: 62-72

# Change from:
endpoint = f"{self.config.target_base_url}/health/live"

# To:
endpoint = f"{self.config.target_base_url}/health"
```

**Option B**: If services use `/api/v1/health/*`:
```python
# Update endpoints to include API prefix
endpoint_live = f"{self.config.target_base_url}/api/v1/health/live"
endpoint_ready = f"{self.config.target_base_url}/api/v1/health/ready"
```

**Verification**:
```bash
# After fix, restart Sentinel
docker-compose -f docker-compose.sentinel.yml restart

# Check Sentinel logs
docker logs veris-sentinel --tail=20 -f

# Manually trigger a check cycle
curl -X POST http://localhost:9090/run
curl http://localhost:9090/status | jq '.last_cycle.results[] | select(.check_id=="S1-probes")'
```

#### Issue 1.2: API Key Not Being Sent

**Diagnosis**:
```bash
# Check if API_KEY_MCP is set in Sentinel
docker exec veris-sentinel env | grep API_KEY_MCP
```

**Fix**:
```bash
# If missing, add to .env file
echo "API_KEY_MCP=your_actual_api_key_here" >> .env

# Restart Sentinel with new env
docker-compose -f docker-compose.sentinel.yml down
docker-compose -f docker-compose.sentinel.yml up -d
```

**Verification**:
```bash
# Check headers are included
docker exec veris-sentinel wget -O- --header="X-API-Key: $API_KEY_MCP" http://context-store:8000/health
```

#### Issue 1.3: Service URL Wrong

**Diagnosis**:
```bash
# Check TARGET_BASE_URL in Sentinel
docker exec veris-sentinel env | grep TARGET_BASE_URL

# Should be: http://context-store:8000
# Not: http://veris-memory-dev-context-store-1:8000
```

**Fix**:
Already done in PR #163, but verify deployment:
```yaml
# File: docker-compose.sentinel.yml
# Should have:
environment:
  - TARGET_BASE_URL=http://context-store:8000
```

If incorrect:
```bash
# Update docker-compose.sentinel.yml
# Then rebuild and restart
docker-compose -f docker-compose.sentinel.yml up -d --build
```

#### Issue 1.4: Network Isolation

**Diagnosis**:
```bash
# Check Sentinel is on correct network
docker inspect veris-sentinel | jq '.[0].NetworkSettings.Networks'

# Should show: veris-memory-dev_default or context-store-network
```

**Fix**:
```bash
# If on wrong network, update docker-compose.sentinel.yml:
# networks:
#   context-store-network:
#     external: true
#     name: veris-memory-dev_default

docker-compose -f docker-compose.sentinel.yml down
docker-compose -f docker-compose.sentinel.yml up -d
```

**Success Criteria for Phase 1**:
- ✅ S1-probes status changes from FAIL to PASS
- ✅ No more HTTP 404 errors in logs
- ✅ Health endpoints return 200 OK
- ✅ API key authentication working

---

### **PHASE 2: Security & Database** (Priority: CRITICAL/HIGH)

**Goal**: Fix critical security issues and restore database connectivity

**Time Estimate**: 45-90 minutes

**Dependencies**: Phase 1 must be complete

#### Issue 2.1: S5 Security Vulnerability

**Investigation**:
```bash
# Check what security test is failing
docker logs veris-sentinel | grep "S5-security" -A 10

# Common issues:
# - API key validation not enforcing
# - Authentication bypass possible
# - CORS misconfigured
```

**Fix Options**:

**If API key not validated**:
```bash
# Verify AUTH_REQUIRED is true
docker exec veris-memory-dev-context-store-1 env | grep AUTH_REQUIRED

# Should be: AUTH_REQUIRED=true
```

If missing:
```bash
echo "AUTH_REQUIRED=true" >> .env
docker-compose restart context-store
```

**If negative test passing (should fail)**:
```python
# File: src/monitoring/sentinel/checks/s5_security_negatives.py
# Review test logic - ensure it's testing that:
# - Requests WITHOUT API key are rejected (401/403)
# - Requests with WRONG API key are rejected (403)
```

**Verification**:
```bash
# Test that requests without key are rejected
curl -i http://localhost:8000/tools/store_context
# Should return: 401 or 403

# Test that requests with key succeed
curl -i -H "X-API-Key: $API_KEY_MCP" http://localhost:8000/health
# Should return: 200
```

#### Issue 2.2: S2 Golden Fact Recall (Database)

**Investigation**:
```bash
# Check Qdrant is healthy
curl http://localhost:6333/
curl http://localhost:6333/collections

# Check if collection exists
curl http://localhost:6333/collections/veris_memory_contexts
```

**Fix if collection missing**:
```bash
# From host, initialize collection
docker exec veris-memory-dev-context-store-1 python -c "
from src.storage.qdrant_store import QdrantStore
store = QdrantStore()
store.initialize()
"
```

**Test golden facts**:
```bash
# Store a test context
curl -X POST http://localhost:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_MCP" \
  -d '{
    "type": "decision",
    "content": {"title": "Test Golden Fact", "description": "This is a test"},
    "author": "test",
    "author_type": "human"
  }'

# Retrieve it
curl -X POST http://localhost:8000/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY_MCP" \
  -d '{"query": "Test Golden Fact", "limit": 1}'
```

#### Issue 2.3: S9 Graph Intent (Neo4j)

**Investigation**:
```bash
# Check Neo4j is accessible
docker exec veris-memory-dev-neo4j-1 cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "MATCH (n) RETURN count(n)"
```

**Fix if connection fails**:
```bash
# Verify credentials
docker exec veris-memory-dev-context-store-1 env | grep NEO4J

# Test connection from context-store
docker exec veris-memory-dev-context-store-1 python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', '$NEO4J_PASSWORD'))
with driver.session() as session:
    result = session.run('MATCH (n) RETURN count(n) as count')
    print(result.single()['count'])
"
```

**Success Criteria for Phase 2**:
- ✅ S5-security status changes to PASS
- ✅ S2-golden-fact-recall passes (6/6 tests)
- ✅ S9-graph-intent passes
- ✅ No authentication bypasses possible
- ✅ Databases accessible and responding

---

### **PHASE 3: Resources & Configuration** (Priority: HIGH/MEDIUM)

**Goal**: Address capacity issues and configuration drift

**Time Estimate**: 60-120 minutes

**Dependencies**: Phases 1-2 complete

#### Issue 3.1: S8 Capacity Issues

**Investigation (from host)**:
```bash
# Check container resource usage
docker stats --no-stream

# Check disk space
df -h
docker system df

# Check specific service memory
docker inspect veris-memory-dev-neo4j-1 | jq '.[0].HostConfig.Memory'
docker inspect veris-memory-dev-qdrant-1 | jq '.[0].HostConfig.Memory'
```

**Fix if memory limits too low**:
```yaml
# File: docker-compose.yml
# Increase limits for resource-intensive services

neo4j:
  deploy:
    resources:
      limits:
        memory: 2G  # Increase from 1G
        cpus: '2.0'

qdrant:
  deploy:
    resources:
      limits:
        memory: 1G  # Increase from 512M
```

**Fix if disk space low**:
```bash
# Clean up Docker
docker system prune -a --volumes

# If still low, resize volumes or add storage
```

#### Issue 3.2: S7 Configuration Parity

**Investigation**:
```bash
# Compare environment variables
docker exec veris-memory-dev-context-store-1 env | sort > /tmp/context-store-env.txt
docker exec veris-memory-dev-api-1 env | sort > /tmp/api-env.txt
diff /tmp/context-store-env.txt /tmp/api-env.txt

# Check for expected variables
docker exec veris-memory-dev-context-store-1 env | grep -E 'API_KEY|NEO4J|QDRANT|REDIS'
```

**Fix mismatches**:
```bash
# Update .env file with consistent values
# Then restart affected services
docker-compose restart context-store api
```

#### Issue 3.3: S6 Backup/Restore

**Investigation**:
```bash
# Check if backup scripts exist
ls -la /opt/veris-memory/scripts/backup*

# Check backup storage
ls -la /opt/veris-memory/backups/
```

**Fix if backups failing**:
```bash
# Test backup manually
bash /opt/veris-memory/scripts/backup-all.sh

# Test restore
bash /opt/veris-memory/scripts/test-restore.sh
```

**Success Criteria for Phase 3**:
- ✅ S8-capacity passes (no resource constraints)
- ✅ S7-config-parity passes (all configs consistent)
- ✅ S6-backup-restore passes (backups valid)
- ✅ Container memory usage < 80%
- ✅ Disk space > 20% free

---

### **PHASE 4: Advanced Checks** (Priority: MEDIUM/LOW)

**Goal**: Fix remaining warning-level checks

**Time Estimate**: 90-180 minutes

**Dependencies**: Phases 1-3 complete

#### Issue 4.1: S4 Metrics Wiring

**Investigation**:
```bash
# Check if metrics endpoints are exposed
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
curl http://localhost:9090/metrics
```

**Fix if missing**:
- Verify monitoring dashboard is deployed
- Check Prometheus configuration
- Ensure metrics endpoints are enabled

#### Issue 4.2: S3 Paraphrase Robustness

**Investigation**:
```bash
# Test semantic search with paraphrases
# This requires S2 to be working first
```

**Fix**:
- Adjust similarity thresholds
- Test embedding model quality
- Review vector normalization

#### Issue 4.3: S10 Content Pipeline

**Investigation**:
```bash
# Test each pipeline stage
# Store → Embed → Index → Retrieve
```

**Fix**:
- Test ingestion
- Verify embedding generation
- Check storage persistence
- Test retrieval accuracy

**Success Criteria for Phase 4**:
- ✅ S4-metrics-wiring passes
- ✅ S3-paraphrase-robustness passes
- ✅ S10-content-pipeline passes
- ✅ All services integrated correctly

---

### **PHASE 5: Host Monitoring Setup** (Priority: LOW)

**Goal**: Complete S11 firewall monitoring setup

**Time Estimate**: 20-30 minutes

**Dependencies**: All other phases complete

```bash
# On host (not in container!)
sudo cp scripts/sentinel-host-checks.sh /opt/veris-memory/scripts/
sudo chmod +x /opt/veris-memory/scripts/sentinel-host-checks.sh

# Generate secure secret
SECRET=$(openssl rand -hex 32)
echo "export HOST_CHECK_SECRET=\"$SECRET\"" | sudo tee -a /etc/environment
echo "HOST_CHECK_SECRET=$SECRET" >> .env

# Add to crontab
(sudo crontab -l; echo "*/5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh >> /var/log/sentinel-host-checks.log 2>&1") | sudo crontab -

# Test manually
sudo /opt/veris-memory/scripts/sentinel-host-checks.sh
```

**Success Criteria**:
- ✅ S11-firewall-status changes from UNKNOWN to PASS
- ✅ Host script running via cron
- ✅ Firewall status reported to Sentinel

---

## Summary Timeline

| Phase | Priority | Time | Success Metric |
|-------|----------|------|----------------|
| 1. Foundation | CRITICAL | 30-60 min | S1 passes, no 404 errors |
| 2. Security & DB | CRITICAL | 45-90 min | S5, S2, S9 pass |
| 3. Resources | HIGH | 60-120 min | S8, S7, S6 pass |
| 4. Advanced | MEDIUM | 90-180 min | S4, S3, S10 pass |
| 5. Host Setup | LOW | 20-30 min | S11 passes |
| **TOTAL** | - | **4-8 hours** | **11/11 checks passing** |

---

## Quick Start: First 3 Commands

If you want to start immediately:

```bash
# 1. SSH to server
ssh user@135.181.4.118

# 2. Test health endpoints to find correct paths
curl -v http://localhost:8000/health
curl -v http://localhost:8000/health/live

# 3. Check Sentinel configuration
docker exec veris-sentinel env | grep -E 'TARGET|API_KEY'
```

Based on results, proceed to Phase 1 fixes.

---

## Rollback Plan

If any phase causes more problems:

```bash
# Rollback to pre-PR #163 state
cd /opt/veris-memory
git log --oneline -5  # Find commit before PR #163
git checkout <commit-hash>

# Rebuild and restart
docker-compose down
docker-compose -f docker-compose.sentinel.yml down
docker-compose up -d
docker-compose -f docker-compose.sentinel.yml up -d
```

---

## Monitoring Progress

After each phase:

```bash
# Check Sentinel status
curl -s http://localhost:9090/status | jq '{
  passed: .last_cycle.passed_checks,
  failed: .last_cycle.failed_checks,
  results: [.last_cycle.results[] | {id: .check_id, status: .status}]
}'

# Trigger manual check
curl -X POST http://localhost:9090/run
```

---

**END OF REMEDIATION PLAN**

This plan should be executed sequentially. Each phase builds on the previous one. The most critical issue is S1 (health probes) - fix this first and many other issues may resolve automatically.
