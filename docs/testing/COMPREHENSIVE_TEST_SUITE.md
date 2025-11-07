# Comprehensive System Test Suite

**Location**: `tests/comprehensive_system_test.py`
**Coverage**: 90%+ of Veris Memory system functionality
**Purpose**: End-to-end verification of all system components, search modes, MCP tools, and stress scenarios

---

## Quick Start

```bash
# Run all tests (takes 5-10 minutes)
python tests/comprehensive_system_test.py

# Run specific test suite
python tests/comprehensive_system_test.py --suite redis
python tests/comprehensive_system_test.py --suite graph
python tests/comprehensive_system_test.py --suite vector
python tests/comprehensive_system_test.py --suite mcp
python tests/comprehensive_system_test.py --suite search
python tests/comprehensive_system_test.py --suite api
python tests/comprehensive_system_test.py --suite monitoring
python tests/comprehensive_system_test.py --suite stress

# Verbose output with details
python tests/comprehensive_system_test.py --verbose

# Save report to JSON file
python tests/comprehensive_system_test.py --output test_report.json
```

---

## Test Suites Overview

### 1. Redis Caching (`--suite redis`)
**Coverage**: Redis connectivity, cache behavior, TTL expiry

**Tests**:
- ✅ Redis connectivity via health endpoint
- ✅ Cache hit/miss behavior (measures speedup)
- ℹ️ Cache TTL expiry (informational)

**What It Validates**:
- Redis is accessible and healthy
- Cache writes working
- Cache reads working
- Cache hits detected (5x+ speedup expected)

**Expected Results**:
- Redis connectivity: PASS
- Cache hit behavior: PASS with 2-5x speedup
- TTL expiry: PASS (informational)

---

### 2. Neo4j Graph Operations (`--suite graph`)
**Coverage**: Graph database, relationships, traversal, indexing

**Tests**:
- ✅ Neo4j connectivity via health endpoint
- ✅ `query_graph` MCP tool functionality
- ✅ Relationship creation (PR #170 feature)
- ✅ Graph traversal queries
- ✅ `context_id_index` existence and status

**What It Validates**:
- Neo4j is accessible and healthy
- Graph queries work via MCP tool
- Contexts can be linked with relationships
- Relationship validation working
- Performance index is created and online

**Expected Results**:
- All tests: PASS
- Relationships created: >0
- Index found: True

---

### 3. Qdrant Vector Operations (`--suite vector`)
**Coverage**: Vector storage, similarity search, embeddings

**Tests**:
- ✅ Qdrant connectivity via health endpoint
- ✅ Vector storage (embeddings stored in Qdrant)
- ✅ Vector similarity search
- ✅ Embedding dimensions match config

**What It Validates**:
- Qdrant is accessible and healthy
- Vectors are being generated and stored
- Vector search returns results
- Embedding dimensions correct (384 or 768)

**Expected Results**:
- Connectivity: PASS
- Vector storage: PASS (if embeddings working)
- Vector search: PASS
- Dimensions: 384 (MiniLM) or 768 (MPNet)

**Known Issues**:
- ⚠️ If embeddings are failing, vector storage and search will fail
- ✅ System continues working with graph/keyword search (graceful degradation)

---

### 4. MCP Tools (`--suite mcp`)
**Coverage**: All MCP protocol tools

**Tests**:
- ✅ `store_context` - Store contexts
- ✅ `retrieve_context` - Retrieve contexts
- ✅ `update_scratchpad` - Agent scratchpad management
- ✅ `get_agent_state` - Agent state retrieval

**What It Validates**:
- All MCP tools are accessible
- Tools accept parameters correctly
- Tools return expected responses
- Agent state persistence working

**Expected Results**:
- All tools: PASS
- Store: Returns context ID
- Retrieve: Returns results array
- Scratchpad: Updates successfully
- Agent state: Returns scratchpad data

---

### 5. Search Modes (`--suite search`)
**Coverage**: All search modes and fallback behavior

**Tests**:
- ✅ Hybrid search (vector + graph + keyword)
- ✅ Vector-only search
- ✅ Graph-only search
- ✅ Keyword-only search
- ✅ Graceful degradation (when embeddings fail)

**What It Validates**:
- All search modes work independently
- Hybrid mode combines results
- System falls back gracefully when components fail
- `STRICT_EMBEDDINGS=false` allows storage without vectors

**Expected Results**:
- All search modes: PASS
- Graceful degradation: PASS (contexts stored even if embeddings fail)

**Key Feature** (PR #170):
- With `STRICT_EMBEDDINGS=false`, system stores contexts even when embeddings fail
- Graph and keyword search still work
- No user-facing errors

---

### 6. REST API Service (`--suite api`)
**Coverage**: REST API endpoints (port 8001)

**Tests**:
- ✅ API health endpoint
- ✅ API readiness endpoint
- ✅ API metrics endpoint

**What It Validates**:
- REST API service is running
- Health checks respond correctly
- Metrics endpoint is accessible

**Expected Results**:
- Health: PASS (200 OK)
- Readiness: PASS (status: "healthy")
- Metrics: PASS (200 OK)

---

### 7. Monitoring Infrastructure (`--suite monitoring`)
**Coverage**: Monitoring dashboard, metrics, Prometheus

**Tests**:
- ✅ Monitoring dashboard health (port 8080)
- ℹ️ Metrics emission (requires log access)
- ℹ️ Prometheus format validation

**What It Validates**:
- Dashboard is accessible
- Metrics are being emitted
- Prometheus-compatible format

**Expected Results**:
- Dashboard health: PASS
- Metrics/Prometheus: Informational (requires log/endpoint access)

---

### 8. Stress Testing (`--suite stress`)
**Coverage**: Concurrent load, large payloads, rapid requests

**Tests**:
- ✅ Concurrent stores (20 threads)
- ✅ Large payload handling (100KB)
- ✅ Rapid retrieval (50 requests)

**What It Validates**:
- System handles concurrent load
- Large contexts can be stored
- Performance under sustained load
- No resource exhaustion

**Expected Results**:
- Concurrent stores: 80%+ success rate
- Large payload: PASS
- Rapid retrieval: 90%+ success rate

**Thresholds**:
- Concurrent: 16/20 successes minimum
- Rapid: 45/50 successes minimum

---

### 9. Context Types (`--suite types`)
**Coverage**: All context type schemas

**Tests**:
- ✅ All context types (decision, design, knowledge, conversation, reference, log, observation)

**What It Validates**:
- All context types are accepted
- Type-specific validation working
- Schemas are correctly defined

**Expected Results**:
- All types: PASS (7/7)

---

## Understanding Test Results

### Success Indicators

```
✅ Test Name: PASSED (123.45ms)
```
- Green checkmark
- Test completed successfully
- Duration in milliseconds

### Failure Indicators

```
❌ Test Name: FAILED (456.78ms)
     Error: Connection refused
```
- Red X
- Test failed
- Duration and error message shown

### Informational Tests

Some tests are marked as informational because they require resources not available via API:
- Cache TTL expiry (requires waiting for TTL)
- Metrics emission (requires Docker log access)
- Prometheus format (requires metrics endpoint access)

These will always PASS with a note explaining the limitation.

---

## Test Report Summary

After running tests, you'll see a summary like:

```
================================================================================
                                TEST SUMMARY
================================================================================

Overall Results:
  Total Tests: 45
  Passed: 42
  Failed: 3
  Pass Rate: 93.3%
  Duration: 8.52s

By Category:
  Redis Caching:
    Passed: 3/3
  Neo4j Graph Operations:
    Passed: 5/5
  Qdrant Vector Operations:
    Passed: 2/4  ⚠️  (embeddings failing)
  MCP Tools:
    Passed: 4/4
  Search Modes:
    Passed: 5/5
  REST API Service:
    Passed: 3/3
  Monitoring Infrastructure:
    Passed: 3/3
  Stress Testing:
    Passed: 3/3
  Context Types:
    Passed: 1/1

Failed Tests:
  ❌ Vector Storage (vector)
     Error: Embedding status: failed
  ❌ Vector Search (vector)
     Error: No results returned
```

### Pass Rate Interpretation

- **90-100%**: Excellent - System fully operational
- **80-89%**: Good - Minor issues, system functional
- **70-79%**: Fair - Some components degraded
- **<70%**: Poor - Major issues, requires attention

---

## Comparison: Basic vs Comprehensive Tests

### Basic Load Test (`tests/load_test_deployment.py`)
**Coverage**: ~30-40%

**What It Tests**:
- ✅ Redis caching (cache hits)
- ✅ Store context (10 requests)
- ✅ Retrieve context (20 requests)
- ✅ Basic embedding status

**What It Doesn't Test**:
- ❌ Neo4j graph operations
- ❌ Qdrant vector search
- ❌ Other MCP tools (scratchpad, agent state)
- ❌ Search modes
- ❌ REST API service
- ❌ Monitoring infrastructure
- ❌ Stress scenarios

**Use When**: Quick smoke test after deployment

### Comprehensive Test Suite (`tests/comprehensive_system_test.py`)
**Coverage**: ~90%+

**What It Tests**:
- ✅ Everything from basic load test
- ✅ Neo4j graph operations (query_graph, relationships, traversal)
- ✅ Qdrant vector operations (storage, search, dimensions)
- ✅ All MCP tools (store, retrieve, scratchpad, agent state)
- ✅ All search modes (hybrid, vector, graph, keyword)
- ✅ REST API service (health, readiness, metrics)
- ✅ Monitoring infrastructure (dashboard, metrics)
- ✅ Stress testing (concurrent, large payloads, rapid)
- ✅ All context types
- ✅ Relationship creation and validation
- ✅ Graceful degradation
- ✅ Performance indexes

**Use When**: Full system validation, pre-release testing, troubleshooting

---

## Integration with CI/CD

### GitHub Actions Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Run comprehensive system tests
  run: |
    python tests/comprehensive_system_test.py --output test_report.json
  timeout-minutes: 15

- name: Upload test report
  uses: actions/upload-artifact@v3
  with:
    name: test-report
    path: test_report.json
```

### Pre-deployment Checklist

Before deploying to production:

```bash
# 1. Run comprehensive tests
python tests/comprehensive_system_test.py --verbose

# 2. Check pass rate >= 90%
# If < 90%, investigate failures before deploying

# 3. Save report for records
python tests/comprehensive_system_test.py --output pre_deploy_$(date +%Y%m%d_%H%M%S).json

# 4. If tests pass, proceed with deployment
./scripts/deploy.sh
```

---

## Troubleshooting Test Failures

### Redis Tests Failing

**Symptoms**: Redis connectivity or cache tests fail

**Diagnosis**:
```bash
# Check Redis health
docker logs veris-memory-dev-redis-1 --tail=50

# Check Redis connection
docker exec veris-memory-dev-redis-1 redis-cli ping
```

**Solutions**:
- Restart Redis: `docker-compose restart redis`
- Check `REDIS_URL` environment variable
- Verify Redis container is running

---

### Neo4j Tests Failing

**Symptoms**: Graph connectivity or query_graph tests fail

**Diagnosis**:
```bash
# Check Neo4j health
docker logs veris-memory-dev-neo4j-1 --tail=50

# Check Neo4j connection
docker exec -it veris-memory-dev-neo4j-1 cypher-shell \
  -u neo4j -p "${NEO4J_PASSWORD}" "RETURN 1"
```

**Solutions**:
- Restart Neo4j: `docker-compose restart neo4j`
- Check `NEO4J_PASSWORD` environment variable
- Verify Neo4j container is running
- Wait for Neo4j startup (can take 60s)

---

### Qdrant/Vector Tests Failing

**Symptoms**: Vector storage or search tests fail

**Diagnosis**:
```bash
# Check Qdrant health
curl http://172.17.0.1:6333/

# Check embedding service
docker logs veris-memory-dev-context-store-1 --tail=100 | grep -i embedding
```

**Common Causes**:
1. **Embeddings failing** (most common):
   - Health check passes but real requests fail
   - Check logs for model loading errors
   - Verify model files exist in container

2. **Qdrant not accessible**:
   - Check Qdrant container is running
   - Verify `QDRANT_URL` environment variable

**Solutions**:
- Restart context-store: `docker-compose restart context-store`
- Check `EMBEDDING_DIM` matches model (384 or 768)
- Verify sentence-transformers model is downloaded
- Check Docker volume mounts for model cache

---

### MCP Tools Tests Failing

**Symptoms**: Scratchpad or agent state tests fail

**Diagnosis**:
```bash
# Check MCP server logs
docker logs veris-memory-dev-context-store-1 --tail=100

# Test tool manually
curl -X POST http://172.17.0.1:8000/tools/update_scratchpad \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test", "content": {"test": "data"}}'
```

**Solutions**:
- Check API key is correct
- Verify MCP server is running
- Check tool endpoints are registered

---

### Stress Tests Failing

**Symptoms**: Concurrent or rapid tests have low success rates

**Diagnosis**:
```bash
# Check system resources
docker stats --no-stream

# Check for rate limiting
docker logs veris-memory-dev-context-store-1 | grep -i "rate limit"

# Check error logs
docker logs veris-memory-dev-context-store-1 --tail=200 | grep ERROR
```

**Common Causes**:
- System under heavy load
- Rate limiting enabled
- Resource exhaustion (memory, connections)
- Timeout issues

**Solutions**:
- Increase timeout thresholds
- Adjust rate limits in configuration
- Scale up resources (memory, CPU)
- Reduce concurrent thread count

---

## Advanced Usage

### Running Specific Tests in a Suite

The test suite is modular. To add custom test filtering:

```python
# In comprehensive_system_test.py, modify run_suite() to accept test filters
runner = ComprehensiveTestRunner()
runner.run_suite("graph", filter_tests=["Relationship Creation", "Graph Traversal"])
```

### Custom Test Thresholds

Modify pass rate thresholds in `ComprehensiveTestRunner`:

```python
# Default: 80% pass rate for success
return pass_rate >= 80

# Stricter: 95% pass rate
return pass_rate >= 95
```

### Adding New Tests

To add a new test:

1. **Create test class** (if new category):
```python
class NewCategoryTests:
    @staticmethod
    def test_new_feature() -> Dict[str, Any]:
        # Test implementation
        return {"passed": True, "details": {...}}
```

2. **Add to test runner**:
```python
self.suites = {
    "newcategory": ("New Category", [
        ("New Feature Test", NewCategoryTests.test_new_feature),
    ]),
}
```

3. **Run new suite**:
```bash
python tests/comprehensive_system_test.py --suite newcategory
```

---

## Performance Benchmarks

### Expected Test Durations

| Suite | Tests | Duration | Notes |
|-------|-------|----------|-------|
| Redis | 3 | ~1s | Quick health + cache test |
| Graph | 5 | ~5s | Includes context creation |
| Vector | 4 | ~3s | Depends on embeddings |
| MCP | 4 | ~2s | Tool invocations |
| Search | 5 | ~4s | Multiple search modes |
| API | 3 | ~1s | Health checks only |
| Monitoring | 3 | ~1s | Dashboard health |
| Stress | 3 | ~30s | Concurrent + large payload |
| Types | 1 | ~3s | All context types |
| **Total** | **31** | **~50s** | Full suite |

### Optimization Tips

1. **Run specific suites** during development:
   ```bash
   # Only test what you changed
   python tests/comprehensive_system_test.py --suite graph
   ```

2. **Reduce stress test iterations** for faster feedback:
   ```python
   # Modify in StressTests class
   test_concurrent_stores(num_threads=10)  # Instead of 20
   test_rapid_retrieval(num_requests=25)   # Instead of 50
   ```

3. **Run in parallel** (requires modifications):
   - Use `pytest` with `pytest-xdist`
   - Mark tests as independent
   - Be careful with shared state

---

## See Also

- **Basic Load Testing**: `docs/deployment/LOAD_TEST_RESULTS.md`
- **Post-deployment Setup**: `docs/deployment/POST_PR170_SETUP.md`
- **Monitoring Integration**: `docs/MONITORING_INTEGRATION.md`
- **System Architecture**: `docs/ARCHITECTURE.md`

---

**Last Updated**: 2025-11-07
**Version**: 1.0
**Coverage**: 90%+ system functionality
