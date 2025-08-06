# Context Store MCP Performance Tuning Guide

This guide provides comprehensive performance tuning recommendations for the Context Store MCP server based on benchmark results and best practices.

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [Quick Tuning Checklist](#quick-tuning-checklist)
3. [Database Optimization](#database-optimization)
4. [MCP Server Optimization](#mcp-server-optimization)
5. [Connection Pool Management](#connection-pool-management)
6. [Caching Strategies](#caching-strategies)
7. [Monitoring and Profiling](#monitoring-and-profiling)
8. [Troubleshooting Performance Issues](#troubleshooting-performance-issues)

## Performance Targets

Based on the acceptance criteria for issue #1017:

- **Response Time**: < 50ms for all MCP tool operations
- **Concurrent Connections**: Support 100+ simultaneous connections
- **Memory Usage**: Stable under load with minimal growth
- **Throughput**: Handle 1000+ operations per second

## Quick Tuning Checklist

- [ ] Enable connection pooling for all databases
- [ ] Configure appropriate pool sizes based on load
- [ ] Enable query result caching where appropriate
- [ ] Use batch operations for bulk data processing
- [ ] Enable compression for network communication
- [ ] Configure appropriate timeouts
- [ ] Monitor and tune garbage collection
- [ ] Use async/await patterns consistently

## Database Optimization

### Neo4j Performance Tuning

1. **Memory Configuration**

   ```bash
   # neo4j.conf
   dbms.memory.heap.initial_size=2G
   dbms.memory.heap.max_size=4G
   dbms.memory.pagecache.size=2G
   ```

2. **Connection Pool Settings**

   ```python
   # In Neo4jInitializer
   driver = GraphDatabase.driver(
       uri,
       auth=(username, password),
       max_connection_pool_size=100,
       connection_acquisition_timeout=30,
       max_transaction_retry_time=30
   )
   ```

3. **Index Creation**

   ```cypher
   CREATE INDEX context_type_idx FOR (c:Context) ON (c.type);
   CREATE INDEX context_timestamp_idx FOR (c:Context) ON (c.timestamp);
   CREATE INDEX agent_state_idx FOR (a:AgentState) ON (a.agent_id);
   ```

4. **Query Optimization**
   - Use parameters in queries to enable query plan caching
   - Limit result sets with `LIMIT` clauses
   - Use `PROFILE` to analyze slow queries

### Qdrant Performance Tuning

1. **Collection Configuration**

   ```python
   collection_config = {
       "size": 384,  # Embedding dimension
       "distance": "Cosine",
       "hnsw_config": {
           "m": 16,
           "ef_construct": 200,
           "full_scan_threshold": 10000
       },
       "optimizers_config": {
           "deleted_threshold": 0.2,
           "vacuum_min_vector_number": 1000,
           "default_segment_number": 5
       }
   }
   ```

2. **Batch Operations**

   ```python
   # Use batch upsert for multiple vectors
   client.upsert(
       collection_name="context_store",
       points=batch_points,
       batch_size=100
   )
   ```

3. **Search Optimization**
   - Pre-filter results using metadata before vector search
   - Use appropriate `limit` and `score_threshold` values
   - Enable caching for frequently accessed embeddings

## MCP Server Optimization

### 1. Async Request Handling

```python
# Use connection pooling with aiohttp
connector = aiohttp.TCPConnector(
    limit=100,
    limit_per_host=30,
    ttl_dns_cache=300
)

session = aiohttp.ClientSession(
    connector=connector,
    timeout=aiohttp.ClientTimeout(total=30)
)
```

### 2. Request Batching

```python
async def batch_process_requests(requests: List[Dict]):
    """Process multiple requests in parallel."""
    tasks = []
    for req in requests:
        task = process_single_request(req)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### 3. Response Compression

```python
# Enable gzip compression for responses
from aiohttp import web

app = web.Application()
app.middlewares.append(web.middleware(gzip_middleware))
```

## Connection Pool Management

### Optimal Pool Sizes

```python
# Configuration based on expected load
POOL_CONFIG = {
    "neo4j": {
        "min_size": 10,
        "max_size": 100,
        "max_idle_time": 300  # seconds
    },
    "qdrant": {
        "connections_per_host": 30,
        "total_connections": 100
    },
    "redis": {  # If using Redis for caching
        "min_size": 5,
        "max_size": 50
    }
}
```

### Connection Health Checks

```python
async def health_check_connections():
    """Periodic health check for all connections."""
    checks = {
        "neo4j": check_neo4j_health(),
        "qdrant": check_qdrant_health(),
        "mcp_server": check_server_health()
    }

    results = await asyncio.gather(*checks.values(), return_exceptions=True)
    return dict(zip(checks.keys(), results))
```

## Caching Strategies

### 1. Query Result Caching

```python
from functools import lru_cache
from aiocache import cached

@cached(ttl=300)  # Cache for 5 minutes
async def get_context_by_type(context_type: str):
    """Cached context retrieval by type."""
    return await neo4j_client.get_contexts_by_type(context_type)
```

### 2. Embedding Cache

```python
class EmbeddingCache:
    def __init__(self, max_size: int = 10000):
        self.cache = {}
        self.max_size = max_size

    async def get_or_compute(self, text: str):
        if text in self.cache:
            return self.cache[text]

        embedding = await compute_embedding(text)

        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest = min(self.cache.items(), key=lambda x: x[1]["timestamp"])
            del self.cache[oldest[0]]

        self.cache[text] = {
            "embedding": embedding,
            "timestamp": time.time()
        }
        return embedding
```

### 3. Connection State Caching

```python
# Cache agent states in memory with TTL
AGENT_STATE_CACHE = TTLCache(maxsize=1000, ttl=60)

async def get_agent_state_cached(agent_id: str):
    if agent_id in AGENT_STATE_CACHE:
        return AGENT_STATE_CACHE[agent_id]

    state = await get_agent_state_from_db(agent_id)
    AGENT_STATE_CACHE[agent_id] = state
    return state
```

## Monitoring and Profiling

### 1. Performance Metrics to Track

```python
# Key metrics for monitoring
PERFORMANCE_METRICS = {
    "response_time_ms": {
        "target": 50,
        "warning": 100,
        "critical": 200
    },
    "concurrent_connections": {
        "target": 100,
        "warning": 150,
        "critical": 200
    },
    "memory_usage_mb": {
        "target": 1024,
        "warning": 2048,
        "critical": 3072
    },
    "cpu_usage_percent": {
        "target": 50,
        "warning": 75,
        "critical": 90
    }
}
```

### 2. Profiling Tools

```python
# Use cProfile for detailed profiling
import cProfile
import pstats

def profile_function(func):
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions

        return result
    return wrapper
```

### 3. Real-time Monitoring

```python
import prometheus_client

# Define metrics
response_time = prometheus_client.Histogram(
    'mcp_response_time_seconds',
    'MCP tool response time',
    ['tool_name']
)

concurrent_connections = prometheus_client.Gauge(
    'mcp_concurrent_connections',
    'Number of concurrent MCP connections'
)

# Track metrics
@response_time.time()
async def handle_tool_call(tool_name: str, args: dict):
    # Tool implementation
    pass
```

## Troubleshooting Performance Issues

### Common Issues and Solutions

1. **High Response Times**

   - Check database query performance
   - Verify network latency
   - Review connection pool exhaustion
   - Check for blocking operations

2. **Memory Leaks**

   - Monitor object creation/destruction
   - Check for circular references
   - Review cache eviction policies
   - Use memory profilers

3. **Connection Timeouts**

   - Increase timeout values appropriately
   - Check database load
   - Review connection pool settings
   - Monitor network issues

4. **CPU Bottlenecks**
   - Profile hot code paths
   - Optimize algorithms
   - Use async operations
   - Consider horizontal scaling

### Performance Testing Commands

```bash
# Run performance benchmark
python context-store/benchmarks/mcp_performance_benchmark.py \
    --iterations 1000 \
    --concurrent-connections 1 10 50 100 200

# Monitor in real-time
htop  # CPU and memory
iotop  # I/O usage
nethogs  # Network usage

# Database-specific monitoring
# Neo4j
cypher-shell "CALL dbms.listQueries()"

# System resource limits
ulimit -n  # Check file descriptor limit
```

### Optimization Workflow

1. **Measure** - Run benchmarks to establish baseline
2. **Profile** - Identify bottlenecks using profiling tools
3. **Optimize** - Apply targeted optimizations
4. **Validate** - Re-run benchmarks to verify improvements
5. **Monitor** - Set up continuous monitoring

## Best Practices Summary

1. **Always measure before optimizing** - Use the benchmark tool to establish baselines
2. **Focus on the critical path** - Optimize the most frequently used operations first
3. **Use connection pooling** - Reuse connections to reduce overhead
4. **Implement caching strategically** - Cache expensive operations with appropriate TTLs
5. **Monitor continuously** - Set up alerts for performance degradation
6. **Plan for scale** - Design with horizontal scaling in mind
7. **Document changes** - Keep track of optimizations and their impact

## Running Performance Tests

To validate performance improvements:

```bash
# 1. Start the MCP server
cd context-store
docker-compose up -d

# 2. Run the benchmark
python benchmarks/mcp_performance_benchmark.py

# 3. Review results in benchmark_results/
ls -la benchmark_results/

# 4. Compare before/after optimization
diff benchmark_results/mcp_benchmark_report_*.txt
```

Remember: Performance optimization is an iterative process. Regular benchmarking and monitoring are essential for maintaining optimal performance as the system evolves.
