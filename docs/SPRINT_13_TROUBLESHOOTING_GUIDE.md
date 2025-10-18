# Sprint 13 Troubleshooting Guide

**Version**: 1.0
**Last Updated**: 2025-10-18
**Sprint**: 13 - Critical Fixes and Enhancements

---

## Table of Contents

1. [Embedding Pipeline Issues](#embedding-pipeline-issues)
2. [Authentication Problems](#authentication-problems)
3. [Memory Management Issues](#memory-management-issues)
4. [Namespace Conflicts](#namespace-conflicts)
5. [Relationship Detection Issues](#relationship-detection-issues)
6. [Performance Problems](#performance-problems)
7. [Diagnostic Commands](#diagnostic-commands)

---

## Embedding Pipeline Issues

### Issue 1: `embedding_status: "unavailable"`

**Symptoms**:
```json
{
  "embedding_status": "unavailable",
  "embedding_message": "Embedding service not initialized"
}
```

**Cause**: Embedding service failed to initialize during startup.

**Diagnosis**:
```bash
# Check health endpoint
curl http://localhost:8000/health/detailed | jq '.qdrant'

# Check server logs for startup errors
docker logs veris-memory-mcp | grep -i "embedding"
```

**Solutions**:

1. **Install sentence-transformers**:
```bash
pip install sentence-transformers
```

2. **Verify Qdrant connection**:
```bash
# Test Qdrant connectivity
curl http://localhost:6333/collections

# Check if veris-memory collection exists
curl http://localhost:6333/collections/veris-memory
```

3. **Restart the MCP server**:
```bash
docker-compose restart veris-memory-mcp
```

4. **Check initialization logs**:
```bash
# Look for embedding test during startup
docker logs veris-memory-mcp | grep "FULLY OPERATIONAL"

# Should see:
# ✅ Qdrant + Embeddings: FULLY OPERATIONAL (384D vectors)
```

**Prevention**: Add `sentence-transformers` to requirements.txt

---

### Issue 2: `embedding_status: "failed"`

**Symptoms**:
```json
{
  "embedding_status": "failed",
  "embedding_message": "Failed to generate embedding: ..."
}
```

**Cause**: Embedding generation failed for specific content.

**Diagnosis**:
```bash
# Check if content is too long
cat context.json | jq '.content | length'

# Check for special characters or encoding issues
cat context.json | jq '.content' | file -
```

**Solutions**:

1. **Simplify content**:
```python
# Truncate long text
content_text = content_text[:1000]  # Max 1000 chars
```

2. **Check encoding**:
```python
# Ensure UTF-8 encoding
content_text = content_text.encode('utf-8', errors='ignore').decode('utf-8')
```

3. **Retry with simpler content**:
```bash
curl -X POST http://localhost:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test",
    "content": {"text": "Simple test"},
    "metadata": {}
  }'
```

**Prevention**: Validate content length before submission (<5000 characters recommended)

---

### Issue 3: Qdrant Collection Not Created

**Symptoms**:
- Health endpoint shows `qdrant.healthy: false`
- Error: "Collection not found"

**Diagnosis**:
```bash
# List all collections
curl http://localhost:6333/collections | jq '.result.collections'

# Check for veris-memory collection
curl http://localhost:6333/collections/veris-memory
```

**Solutions**:

1. **Create collection manually**:
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="veris-memory",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
```

2. **Delete and recreate**:
```bash
# Delete existing collection
curl -X DELETE http://localhost:6333/collections/veris-memory

# Restart server to auto-create
docker-compose restart veris-memory-mcp
```

---

## Authentication Problems

### Issue 4: "Invalid API key" Error

**Symptoms**:
```json
{
  "error": "Invalid API key",
  "error_code": "AUTH_INVALID"
}
```

**Cause**: API key not recognized or malformed.

**Diagnosis**:
```bash
# Check environment variables
docker exec veris-memory-mcp env | grep API_KEY

# Verify key format
echo $API_KEY_ADMIN | grep -oE 'vmk_[a-zA-Z0-9_-]+'
```

**Solutions**:

1. **Verify key format**:
```bash
# Correct format: vmk_{secret}:{user_id}:{role}:{is_agent}
API_KEY_ADMIN=vmk_admin_secret:admin_user:admin:false
```

2. **Check header format**:
```bash
# Option 1: X-API-Key header
curl -H "X-API-Key: vmk_admin_secret" ...

# Option 2: Authorization Bearer
curl -H "Authorization: Bearer vmk_admin_secret" ...
```

3. **Reload environment**:
```bash
# Update .env file
echo 'API_KEY_TEST=vmk_test_key:test_user:writer:false' >> .env

# Restart container
docker-compose restart veris-memory-mcp
```

**Prevention**: Use environment variable validation in startup scripts

---

### Issue 5: "Delete operations require human authentication"

**Symptoms**:
```json
{
  "error": "Delete operations require human authentication. AI agents cannot delete contexts.",
  "error_code": "HUMAN_REQUIRED"
}
```

**Cause**: Attempting to delete with an agent API key (`is_agent=true`).

**Diagnosis**:
```bash
# Check if key is marked as agent
echo $API_KEY_CURRENT | awk -F: '{print $4}'
# Output: "true" means agent key, "false" means human key
```

**Solutions**:

1. **Use human API key**:
```bash
# Ensure is_agent=false
API_KEY_HUMAN=vmk_human_key:human_user:admin:false

curl -X POST http://localhost:8000/tools/delete_context \
  -H "X-API-Key: vmk_human_key" \
  -d '{"context_id": "...", "reason": "..."}'
```

2. **Verify key configuration**:
```bash
# List all API keys
docker exec veris-memory-mcp env | grep API_KEY | awk -F= '{print $1, $2}' | column -t
```

**Prevention**: Document which keys are for humans vs agents

---

### Issue 6: "AUTH_REQUIRED but no key provided"

**Symptoms**:
- Requests fail with 401 Unauthorized
- Error: "API key required"

**Cause**: `AUTH_REQUIRED=true` but no API key sent in request.

**Diagnosis**:
```bash
# Check if auth is required
docker exec veris-memory-mcp env | grep AUTH_REQUIRED

# Test without key
curl -X POST http://localhost:8000/tools/store_context -d '{}' -v
```

**Solutions**:

1. **Disable auth for development**:
```bash
# Update .env
AUTH_REQUIRED=false

# Restart
docker-compose restart veris-memory-mcp
```

2. **Always include API key**:
```bash
# Add to all requests
curl -H "X-API-Key: vmk_test_key" ...
```

3. **Use default test key**:
```bash
# System provides default test key
API_KEY_TEST=vmk_test_key:test_user:writer:false
```

---

## Memory Management Issues

### Issue 7: Redis Memory Bloat

**Symptoms**:
- Redis memory usage growing unbounded
- No TTL set on keys

**Diagnosis**:
```bash
# Check Redis memory usage
redis-cli INFO memory | grep used_memory_human

# Find keys without TTL
redis-cli --scan --pattern "*" | while read key; do
  ttl=$(redis-cli TTL "$key")
  if [ "$ttl" -eq "-1" ]; then
    echo "No TTL: $key"
  fi
done
```

**Solutions**:

1. **Set TTL on existing keys**:
```bash
# Set 1-hour TTL on scratchpad keys
redis-cli --scan --pattern "scratchpad:*" | while read key; do
  redis-cli EXPIRE "$key" 3600
done
```

2. **Enable automatic cleanup**:
```python
from src.storage.redis_manager import redis_cleanup_job
import asyncio

# Run cleanup job
asyncio.run(redis_cleanup_job(redis_client, interval_seconds=3600))
```

3. **Monitor cleanup stats**:
```python
from src.storage.redis_manager import RedisTTLManager

manager = RedisTTLManager(redis_client)
stats = manager.get_cleanup_stats()
print(stats)
```

**Prevention**: Ensure background cleanup job is running

---

### Issue 8: Data Loss After Redis Flush

**Symptoms**:
- Redis data lost after restart
- Scratchpad values disappear

**Cause**: Redis not persisting to disk or no sync to Neo4j.

**Diagnosis**:
```bash
# Check Redis persistence config
redis-cli CONFIG GET save

# Check sync job status
docker logs veris-memory-mcp | grep "sync job"
```

**Solutions**:

1. **Enable Redis persistence**:
```bash
# Update redis.conf
appendonly yes
appendfsync everysec

# Restart Redis
docker-compose restart redis
```

2. **Verify Neo4j sync is running**:
```python
from src.tools.redis_neo4j_sync import redis_neo4j_sync_job
import asyncio

# Check sync stats
sync = RedisNeo4jSync(redis_client, neo4j_client)
stats = sync.get_sync_stats()
print(f"Last sync: {stats['last_sync']}")
```

3. **Manual sync if needed**:
```bash
curl -X POST http://localhost:8000/admin/sync-redis-neo4j
```

**Prevention**: Monitor sync job logs, set up alerting

---

## Namespace Conflicts

### Issue 9: Namespace Lock Contention

**Symptoms**:
- Multiple operations on same namespace failing
- `acquire_lock()` returns False

**Diagnosis**:
```bash
# Check for active locks
redis-cli --scan --pattern "namespace_lock:*"

# Check lock details
redis-cli GET "namespace_lock:/global/test"
redis-cli TTL "namespace_lock:/global/test"
```

**Solutions**:

1. **Wait for lock to expire**:
```python
from src.core.namespace_manager import NamespaceManager

manager = NamespaceManager(redis_client)

# Check if locked
if manager.is_locked("/global/test"):
    print("Locked, waiting...")
    time.sleep(30)  # Wait for TTL expiration
```

2. **Force release lock** (if stale):
```bash
# Delete stale lock
redis-cli DEL "namespace_lock:/global/test"
```

3. **Increase lock TTL**:
```python
# Use longer TTL for long operations
manager.acquire_lock("/global/test", "my_lock", ttl=300)  # 5 minutes
```

**Prevention**: Always release locks in finally blocks

---

### Issue 10: Namespace Not Auto-Assigned

**Symptoms**:
- Context created with `/global/default` instead of expected namespace
- No `namespace` field in metadata

**Diagnosis**:
```bash
# Check content for namespace indicators
curl http://localhost:8000/tools/retrieve_context -d '{"query": "...", "limit": 1}' | \
  jq '.results[0] | {content, metadata, namespace}'
```

**Solutions**:

1. **Add project_id to content**:
```json
{
  "content": {
    "project_id": "veris-memory",  // This triggers /project/ namespace
    "title": "..."
  }
}
```

2. **Explicitly set namespace**:
```json
{
  "content": {...},
  "metadata": {
    "namespace": "/team/engineering/backend"
  }
}
```

3. **Check auto-assignment logic**:
```python
from src.core.namespace_manager import add_namespace_to_context

namespace = add_namespace_to_context(
    content={"project_id": "veris"},
    namespace_path=None,
    user_id=None
)
print(f"Assigned: {namespace}")  # Should be /project/veris/context
```

**Prevention**: Document namespace assignment rules

---

## Relationship Detection Issues

### Issue 11: Relationships Not Created

**Symptoms**:
- `relationships_created: 0` in store response
- Graph query shows isolated nodes

**Diagnosis**:
```bash
# Check relationship detection
curl -X POST http://localhost:8000/tools/query_graph -d '{
  "query": "MATCH (c:Context)-[r]->() RETURN count(r)"
}'

# Check detection stats
curl http://localhost:8000/stats/relationships | jq '.detection_stats'
```

**Solutions**:

1. **Verify content has detectable patterns**:
```json
{
  "content": {
    "description": "This fixes issue #123 and implements PR #456"
  },
  "metadata": {
    "sprint": "13",
    "project_id": "veris"
  }
}
```

2. **Check Neo4j connectivity**:
```bash
# Test Neo4j connection
curl http://localhost:7474/db/neo4j/tx/commit \
  -u neo4j:password \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "MATCH (n) RETURN count(n)"}]}'
```

3. **Manual relationship creation**:
```python
from src.core.relationship_detector import RelationshipDetector

detector = RelationshipDetector(neo4j_client)

relationships = detector.detect_relationships(
    context_id="test-123",
    context_type="sprint",
    content={"description": "Fixes issue #100"},
    metadata={"sprint": "13"}
)

print(f"Detected: {relationships}")

# Create relationships
created = detector.create_relationships("test-123", relationships)
print(f"Created: {created}")
```

**Prevention**: Add relationship detection to test suite

---

### Issue 12: Duplicate Relationships

**Symptoms**:
- Same relationship created multiple times
- Graph queries return duplicates

**Diagnosis**:
```bash
# Find duplicate relationships
curl -X POST http://localhost:8000/tools/query_graph -d '{
  "query": "MATCH (a)-[r]->(b) WITH a, b, type(r) as rel_type, count(r) as cnt WHERE cnt > 1 RETURN a.id, rel_type, b.id, cnt"
}'
```

**Solutions**:

1. **Use MERGE instead of CREATE**:
```cypher
# Relationship creation uses MERGE by default
MERGE (source)-[r:FIXES]->(target)
SET r.reason = $reason
```

2. **Clean up duplicates**:
```cypher
// Delete duplicate relationships, keep one
MATCH (a)-[r]->(b)
WITH a, b, type(r) as rel_type, collect(r) as rels
WHERE size(rels) > 1
UNWIND rels[1..] as duplicate
DELETE duplicate
```

**Prevention**: Relationship detector uses MERGE by default

---

## Performance Problems

### Issue 13: Slow Store Operations

**Symptoms**:
- `store_context` taking >2 seconds
- Timeouts on context creation

**Diagnosis**:
```bash
# Profile store operation
time curl -X POST http://localhost:8000/tools/store_context -d '{...}'

# Check component times in logs
docker logs veris-memory-mcp | grep "store_context" | grep "ms"
```

**Solutions**:

1. **Reduce content size**:
```python
# Limit content length
max_content_length = 5000
content_text = content_text[:max_content_length]
```

2. **Disable relationship detection temporarily**:
```python
# In emergency, skip relationship detection
skip_relationships = True
```

3. **Check backend health**:
```bash
# Qdrant response time
time curl http://localhost:6333/collections/veris-memory

# Neo4j response time
time curl http://localhost:7474/db/neo4j/tx/commit -u neo4j:password \
  -d '{"statements": [{"statement": "RETURN 1"}]}'
```

4. **Optimize embeddings**:
```python
# Use smaller embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384D, fast
# Instead of: "all-mpnet-base-v2"  # 768D, slower
```

**Prevention**: Set up performance monitoring

---

### Issue 14: High Memory Usage

**Symptoms**:
- MCP server using >2GB RAM
- OOM kills

**Diagnosis**:
```bash
# Check memory usage
docker stats veris-memory-mcp

# Check heap size
docker exec veris-memory-mcp ps aux | grep python
```

**Solutions**:

1. **Limit embedding model cache**:
```python
# Reduce model cache
os.environ['TRANSFORMERS_CACHE'] = '/tmp/transformers_cache'
```

2. **Clear Redis memory**:
```bash
# Flush old data
redis-cli --scan --pattern "scratchpad:*" | while read key; do
  ttl=$(redis-cli TTL "$key")
  if [ "$ttl" -lt "60" ]; then
    redis-cli DEL "$key"
  fi
done
```

3. **Restart periodically**:
```bash
# Add to cron
0 3 * * * docker-compose restart veris-memory-mcp
```

**Prevention**: Set memory limits in docker-compose.yml

---

## Diagnostic Commands

### Health Checks

```bash
# Overall health
curl http://localhost:8000/health

# Detailed health with all components
curl http://localhost:8000/health/detailed | jq '.'

# Specific component health
curl http://localhost:8000/health/detailed | jq '.qdrant'
curl http://localhost:8000/health/detailed | jq '.neo4j'
curl http://localhost:8000/health/detailed | jq '.redis'
```

### Statistics

```bash
# Relationship detection stats
curl http://localhost:8000/stats/relationships | jq '.detection_stats'

# Namespace stats
curl http://localhost:8000/stats/namespaces | jq '.namespaces'

# Redis cleanup stats
curl http://localhost:8000/stats/redis-cleanup | jq '.cleanup_stats'

# Sync stats
curl http://localhost:8000/stats/redis-sync | jq '.sync_stats'
```

### Backend Status

```bash
# Qdrant
curl http://localhost:6333/collections/veris-memory | jq '.result.vectors_count'

# Neo4j
curl http://localhost:7474/db/neo4j/tx/commit \
  -u neo4j:password \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "MATCH (n:Context) RETURN count(n)"}]}' | jq '.'

# Redis
redis-cli INFO | grep "used_memory_human"
redis-cli DBSIZE
```

### Logs

```bash
# Tail all logs
docker-compose logs -f veris-memory-mcp

# Filter for errors
docker logs veris-memory-mcp 2>&1 | grep -i error

# Filter for specific component
docker logs veris-memory-mcp | grep "embedding"
docker logs veris-memory-mcp | grep "relationship"
docker logs veris-memory-mcp | grep "namespace"
```

### Performance Profiling

```bash
# Profile store operation
time curl -X POST http://localhost:8000/tools/store_context -d '{...}'

# Profile search operation
time curl -X POST http://localhost:8000/tools/retrieve_context -d '{...}'

# Check request metrics
curl http://localhost:8000/metrics | grep request_duration
```

---

## Emergency Procedures

### Procedure 1: Complete System Reset

```bash
# 1. Stop all services
docker-compose down

# 2. Clear all data (WARNING: DATA LOSS)
docker volume rm veris-memory_qdrant_data
docker volume rm veris-memory_neo4j_data
docker volume rm veris-memory_redis_data

# 3. Restart services
docker-compose up -d

# 4. Verify initialization
curl http://localhost:8000/health/detailed
```

### Procedure 2: Rollback to Pre-Sprint-13

```bash
# 1. Checkout previous commit
git checkout HEAD~5  # Before Sprint 13

# 2. Rebuild containers
docker-compose build

# 3. Restart
docker-compose up -d

# 4. Verify
curl http://localhost:8000/health
```

### Procedure 3: Repair Corrupted Data

```bash
# 1. Backup current data
docker exec veris-memory-neo4j neo4j-admin dump --to=/backups/backup.dump
redis-cli --rdb /backups/redis.rdb

# 2. Stop services
docker-compose stop

# 3. Restore from backup
docker exec veris-memory-neo4j neo4j-admin load --from=/backups/backup.dump

# 4. Restart
docker-compose start

# 5. Verify
curl http://localhost:8000/health/detailed
```

---

## Getting Help

If issues persist after trying these solutions:

1. **Check GitHub Issues**: https://github.com/credentum/veris-memory/issues
2. **Enable Debug Logging**:
```bash
LOG_LEVEL=DEBUG docker-compose up -d
docker logs veris-memory-mcp -f
```
3. **Collect Diagnostic Info**:
```bash
# Run diagnostics
./scripts/diagnostics.sh > diagnostics.txt

# Include in issue report
- System info (OS, Docker version)
- Error logs
- Health endpoint output
- Steps to reproduce
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-18 | Initial Sprint 13 troubleshooting guide |
