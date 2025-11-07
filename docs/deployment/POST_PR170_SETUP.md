# Post-PR #170 Deployment Setup

**Required After**: Deploying PR #170 (Backend Restoration)
**Applies To**: All environments (development, staging, production)

---

## Overview

PR #170 introduced significant backend improvements including:
- Redis caching with configurable TTL
- Graceful degradation for embedding failures
- Relationship validation
- Performance optimizations

This guide covers the **required configuration** and **database migrations** needed after merging PR #170.

---

## 1. Environment Variables (REQUIRED)

### Add to `.env` file:

```bash
# PR #170: Cache and Embedding Configuration
VERIS_CACHE_TTL_SECONDS=300
STRICT_EMBEDDINGS=false
EMBEDDING_DIM=768  # or 384 for all-MiniLM-L6-v2
```

### What These Do:

| Variable | Default | Description |
|----------|---------|-------------|
| `VERIS_CACHE_TTL_SECONDS` | 300 | Cache TTL in seconds (5 minutes default) |
| `STRICT_EMBEDDINGS` | false | Embedding failure behavior (see below) |
| `EMBEDDING_DIM` | 768 | Vector dimensions (match your model) |

### STRICT_EMBEDDINGS Options:

- **`false` (recommended)**: Graceful degradation - contexts stored even if embeddings fail
- **`true`**: Fail fast - returns error if embeddings unavailable

### Cache TTL Recommendations:

| Data Type | Recommended TTL | Use Case |
|-----------|----------------|----------|
| Real-time data | 60-180s | User state, live metrics |
| Context retrieval | 300s (default) | General queries |
| Decision records | 900s | Moderately stable data |
| Static data | 3600s+ | Configuration, documentation |

---

## 2. Docker Compose Update (REQUIRED)

The `docker-compose.yml` in PR #170 includes these environment variables with defaults.

**If you have a custom docker-compose.yml**, add to the `context-store` service:

```yaml
services:
  context-store:
    environment:
      # ... existing variables ...
      # PR #170: Cache and embedding configuration
      - VERIS_CACHE_TTL_SECONDS=${VERIS_CACHE_TTL_SECONDS:-300}
      - STRICT_EMBEDDINGS=${STRICT_EMBEDDINGS:-false}
      - EMBEDDING_DIM=${EMBEDDING_DIM:-768}
```

---

## 3. Neo4j Index Creation (REQUIRED)

**Purpose**: Optimize relationship validation queries (2-5x faster)

### Run Once Per Environment:

```cypher
CREATE INDEX context_id_index IF NOT EXISTS
FOR (n:Context)
ON (n.id);
```

### Verification:

```cypher
SHOW INDEXES;
```

**Expected Output:**
```
name: "context_id_index"
type: "RANGE"
entityType: "NODE"
labelsOrTypes: ["Context"]
properties: ["id"]
state: "ONLINE"
populationPercent: 100.0
```

### How to Run:

**Option 1: Neo4j Browser**
1. Open Neo4j Browser: `http://localhost:7474`
2. Login with credentials from `.env`
3. Paste and execute the CREATE INDEX command

**Option 2: Cypher Shell**
```bash
docker exec -it veris-memory-dev-neo4j-1 cypher-shell \
  -u neo4j -p "${NEO4J_PASSWORD}" \
  -d neo4j \
  "CREATE INDEX context_id_index IF NOT EXISTS FOR (n:Context) ON (n.id);"
```

**Option 3: HTTP API**
```bash
curl -X POST http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -H "Authorization: Basic $(echo -n 'neo4j:your_password' | base64)" \
  -d '{
    "statements": [{
      "statement": "CREATE INDEX context_id_index IF NOT EXISTS FOR (n:Context) ON (n.id);"
    }]
  }'
```

---

## 4. Service Restart (REQUIRED)

After adding environment variables, restart services:

```bash
# Using docker-compose
docker-compose restart context-store

# Or full stack restart
docker-compose down && docker-compose up -d
```

---

## 5. Verification Steps

### 5.1 Check Environment Variables

```bash
# Verify variables are set
docker exec veris-memory-dev-context-store-1 env | grep -E "VERIS_CACHE_TTL|STRICT_EMBEDDINGS|EMBEDDING_DIM"
```

**Expected:**
```
VERIS_CACHE_TTL_SECONDS=300
STRICT_EMBEDDINGS=false
EMBEDDING_DIM=768
```

### 5.2 Check Neo4j Index

```bash
# Query index status
docker exec -it veris-memory-dev-neo4j-1 cypher-shell \
  -u neo4j -p "${NEO4J_PASSWORD}" \
  "SHOW INDEXES;"
```

**Look for:** `context_id_index` with `state: "ONLINE"`

### 5.3 Test Cache Performance

```bash
# Make same query twice and compare times
time curl -s -X POST http://localhost:8000/tools/retrieve_context \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"query": "test", "limit": 5}'

time curl -s -X POST http://localhost:8000/tools/retrieve_context \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"query": "test", "limit": 5}'
```

**Expected:** Second request should be 2-5x faster (cache hit)

### 5.4 Verify Metrics Emission

```bash
# Check logs for METRIC: lines
docker logs veris-memory-dev-context-store-1 --tail=100 | grep "METRIC:"
```

**Expected output:**
```
METRIC: cache_requests_total{result='miss',search_mode='hybrid'} 1
METRIC: cache_requests_total{result='hit',search_mode='hybrid'} 1
METRIC: embedding_generation_errors_total{strict_mode='false'} 1
```

---

## 6. Monitoring Setup (RECOMMENDED)

PR #170 includes structured logging and Prometheus-compatible metrics.

**See**: `docs/MONITORING_INTEGRATION.md` for full setup guide

### Quick Monitoring Commands:

```bash
# Cache hit rate
docker logs veris-memory-dev-context-store-1 | \
  grep "cache_requests_total" | \
  awk '{if($0 ~ /hit/) hit++; total++} END {print "Hit Rate:", hit/total*100"%"}'

# Embedding failures
docker logs veris-memory-dev-context-store-1 | \
  grep "embedding_generation_errors" | wc -l

# Critical errors
docker logs veris-memory-dev-context-store-1 --tail=100 | \
  grep -E "ERROR|CRITICAL"
```

---

## 7. Performance Tuning (OPTIONAL)

### Adjust Cache TTL Based on Usage:

**If cache hit rate < 30%:**
```bash
# Increase TTL to 15 minutes
VERIS_CACHE_TTL_SECONDS=900
```

**If data changes frequently:**
```bash
# Decrease TTL to 2 minutes
VERIS_CACHE_TTL_SECONDS=120
```

### Enable Strict Mode for Production:

```bash
# Fail fast instead of graceful degradation
STRICT_EMBEDDINGS=true
```

**Use when**: You want to know immediately if embeddings fail, rather than silently degrading.

---

## 8. Rollback Procedure

If issues occur after PR #170:

### Option 1: Keep PR #170, Fix Configuration

```bash
# 1. Check environment variables are correct
cat .env | grep -E "VERIS_CACHE_TTL|STRICT_EMBEDDINGS"

# 2. Verify Neo4j index exists
docker exec -it veris-memory-dev-neo4j-1 cypher-shell \
  -u neo4j -p "${NEO4J_PASSWORD}" "SHOW INDEXES;"

# 3. Check logs for specific errors
docker logs veris-memory-dev-context-store-1 --tail=200
```

### Option 2: Temporary Workaround

```bash
# Disable caching temporarily (not recommended)
VERIS_CACHE_TTL_SECONDS=0

# Or enable graceful degradation
STRICT_EMBEDDINGS=false
```

### Option 3: Full Rollback

```bash
# Revert to previous version
git checkout <previous-commit>
docker-compose down && docker-compose up -d --build
```

---

## 9. Migration Checklist

Use this checklist when deploying PR #170:

- [ ] Added `VERIS_CACHE_TTL_SECONDS` to `.env`
- [ ] Added `STRICT_EMBEDDINGS` to `.env`
- [ ] Added `EMBEDDING_DIM` to `.env` (or verified existing value)
- [ ] Updated `docker-compose.yml` with new environment variables
- [ ] Created Neo4j `context_id_index`
- [ ] Verified index is ONLINE with `SHOW INDEXES`
- [ ] Restarted `context-store` service
- [ ] Confirmed environment variables loaded correctly
- [ ] Tested cache performance (2-5x speedup on hits)
- [ ] Checked logs for METRIC: emissions
- [ ] No critical errors in logs
- [ ] Documented any custom TTL values chosen

---

## 10. FAQ

### Q: What if I don't set these environment variables?

**A**: The application will use defaults:
- `VERIS_CACHE_TTL_SECONDS=300` (5 minutes)
- `STRICT_EMBEDDINGS=false` (graceful degradation)
- `EMBEDDING_DIM=768` (for all-mpnet-base-v2)

### Q: What if I skip the Neo4j index?

**A**: System works but relationship validation is 2-5x slower. Not critical but recommended.

### Q: Can I change these values without restarting?

**A**: No, you must restart the `context-store` service for environment variable changes to take effect.

### Q: How do I know if caching is working?

**A**: Run the same query twice. Second request should be noticeably faster (2-5x). Check logs for `cache_requests_total{result='hit'}`.

### Q: What if embeddings keep failing?

**A**: With `STRICT_EMBEDDINGS=false` (default), contexts are still stored without vectors. Graph/keyword search still works. Check embedding service logs for root cause.

---

## Support

**Issues**: https://github.com/credentum/veris-memory/issues
**Documentation**: `/docs/MONITORING_INTEGRATION.md`
**Load Testing**: `/tests/load_test_deployment.py`

---

**Last Updated**: 2025-11-07
**PR**: #170 - Backend Restoration
**Version**: 1.0
