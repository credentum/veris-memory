# Performance Benchmarking Suite

Comprehensive performance testing framework for the Veris Memory system.

## Overview

The performance benchmarking suite provides tools for measuring, analyzing, and monitoring system performance across various scenarios and configurations. It helps identify bottlenecks, validate performance requirements, and track performance trends over time.

## Features

- **Comprehensive Benchmarking**: Tests multiple search modes, dispatch policies, and concurrency levels
- **Stress Testing**: Sustained load testing with configurable duration and query rates
- **Performance Analysis**: Detailed statistics including percentiles, throughput, and error rates
- **Comparative Testing**: Side-by-side comparison of different configurations
- **Export Capabilities**: JSON export for CI/CD integration and historical tracking
- **Mock Backend Support**: Safe testing without requiring production backends

## Quick Start

### Basic Benchmark Suite

```bash
# Run complete benchmark suite
python tools/benchmarks/performance_suite.py benchmark

# Quick benchmark (reduced test set)
python tools/benchmarks/performance_suite.py quick-benchmark

# Export results for analysis
python tools/benchmarks/performance_suite.py benchmark --export benchmark_results.json
```

### Stress Testing

```bash
# 5-minute stress test at 50 QPS
python tools/benchmarks/performance_suite.py stress-test --duration 300 --target-qps 50

# High-load stress test
python tools/benchmarks/performance_suite.py stress-test --duration 600 --target-qps 100

# Export stress test results
python tools/benchmarks/performance_suite.py stress-test --export stress_results.json
```

### Real Backend Testing

```bash
# Use real backends instead of mocks (requires proper configuration)
python tools/benchmarks/performance_suite.py benchmark --real-backends
```

## Benchmark Configurations

### Default Benchmark Suite

The default suite includes 14 different benchmark configurations:

#### 1. Baseline Tests
- **Sequential Dispatch**: Tests performance with sequential backend dispatch
- **Parallel Dispatch**: Tests performance with parallel backend dispatch

#### 2. Search Mode Comparisons
- **Vector Only**: Pure vector search performance
- **Graph Only**: Pure graph search performance  
- **KV Only**: Pure key-value search performance
- **Hybrid Search**: Combined search mode performance

#### 3. Concurrency Tests
- **Low Concurrency**: 5 concurrent users, 200 queries
- **Medium Concurrency**: 10 concurrent users, 300 queries
- **High Concurrency**: 20 concurrent users, 500 queries

#### 4. Result Size Tests
- **Small Results**: 5 results per query
- **Large Results**: 50 results per query

#### 5. Query Complexity Tests
- **Simple Queries**: Short, straightforward queries
- **Complex Queries**: Long, multi-concept queries

#### 6. Dispatch Policy Tests
- **Fallback Policy**: Sequential fallback dispatch
- **Smart Policy**: Adaptive dispatch policy

### Custom Benchmark Configurations

You can create custom benchmark configurations:

```python
from tools.benchmarks.performance_suite import BenchmarkConfig, PerformanceBenchmark
from core.query_dispatcher import SearchMode, DispatchPolicy

custom_config = BenchmarkConfig(
    name="custom_test",
    description="Custom performance test",
    query_count=100,
    concurrent_users=5,
    search_mode=SearchMode.HYBRID,
    dispatch_policy=DispatchPolicy.PARALLEL,
    result_limit=20,
    use_filters=True,
    use_ranking=True,
    warmup_queries=10
)

benchmark = PerformanceBenchmark()
await benchmark.initialize()
results = await benchmark.run_benchmark_suite([custom_config])
```

## Output and Analysis

### Benchmark Results

Each benchmark produces detailed metrics:

```
📊 Benchmark 1/14: baseline_parallel
📝 Baseline performance with parallel dispatch
--------------------------------------------------
🔥 Warming up with 10 queries...
✅ Completed: 50/50 queries
⏱️  Total Time: 2847.3ms
📊 Throughput: 17.6 queries/second
📈 Response Times:
   Average: 45.2ms
   50th percentile: 42.1ms
   95th percentile: 78.9ms
   99th percentile: 95.4ms
   Range: 15.3ms - 102.7ms
✅ Error Rate: 0.0%
```

### Summary Report

After all benchmarks complete:

```
🏆 BENCHMARK SUITE SUMMARY
============================================================

📊 Overall Results:
   Total Benchmarks: 14
   Total Queries: 1,650
   Success Rate: 99.2%
   Total Execution Time: 156.3s

⚡ Performance Metrics:
   Average Response Time: 38.7ms
   Median Response Time: 35.2ms
   Average 95th Percentile: 67.4ms
   Average Throughput: 15.8 queries/second
   Peak Throughput: 28.3 queries/second

🏆 Performance Rankings:
   🚀 Fastest: vector_only (21.3ms)
   🐌 Slowest: high_concurrency (89.5ms)
   🔥 Highest Throughput: kv_only (28.3 qps)
   ✅ Most Reliable: baseline_parallel (0.0% errors)
```

### Stress Test Results

Stress tests provide sustained load analysis:

```
🔥 Running Stress Test for 300s at 50 QPS
------------------------------------------------------------
⏱️  10s elapsed, 500 queries, 50.0 QPS
⏱️  20s elapsed, 1000 queries, 50.0 QPS
...

🏁 Stress Test Results:
   Target QPS: 50
   Actual QPS: 49.8
   Total Queries: 14,940
   Success Rate: 99.7%
   Avg Response Time: 42.1ms
   95th Percentile: 78.3ms
   Max Response Time: 156.8ms
```

## Performance Metrics Explained

### Response Time Metrics

- **Average**: Mean response time across all queries
- **50th Percentile (Median)**: Response time that 50% of queries complete under
- **95th Percentile**: Response time that 95% of queries complete under
- **99th Percentile**: Response time that 99% of queries complete under
- **Min/Max**: Fastest and slowest individual query times

### Throughput Metrics

- **Queries Per Second (QPS)**: Number of queries processed per second
- **Peak Throughput**: Highest sustained QPS achieved in any benchmark
- **Average Throughput**: Mean QPS across all benchmarks

### Reliability Metrics

- **Success Rate**: Percentage of queries that completed successfully
- **Error Rate**: Percentage of queries that failed
- **Availability**: System uptime during testing

## CI/CD Integration

### GitHub Actions Integration

```yaml
name: Performance Benchmarks

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      
      - name: Install Dependencies
        run: pip install -r requirements.txt
      
      - name: Run Performance Benchmarks
        run: |
          python tools/benchmarks/performance_suite.py quick-benchmark --export benchmark_results.json
      
      - name: Upload Results
        uses: actions/upload-artifact@v2
        with:
          name: benchmark-results
          path: benchmark_results.json
      
      - name: Performance Regression Check
        run: |
          python scripts/check_performance_regression.py benchmark_results.json
```

### Performance Monitoring

Set up automated performance monitoring:

```bash
#!/bin/bash
# scripts/performance_monitor.sh

# Run daily performance benchmark
python tools/benchmarks/performance_suite.py quick-benchmark --export "results/benchmark_$(date +%Y%m%d).json"

# Check for performance regressions
python scripts/analyze_performance_trends.py results/

# Alert if performance degrades by more than 20%
if [ $? -ne 0 ]; then
    echo "Performance regression detected!" | mail -s "Performance Alert" team@company.com
fi
```

## Performance Targets

### Baseline Performance Targets

| Metric | Target | Excellent | Good | Acceptable |
|--------|--------|-----------|------|------------|
| Average Response Time | < 50ms | < 30ms | < 50ms | < 100ms |
| 95th Percentile | < 100ms | < 60ms | < 100ms | < 200ms |
| Throughput | > 20 QPS | > 50 QPS | > 20 QPS | > 10 QPS |
| Error Rate | < 1% | < 0.1% | < 1% | < 5% |
| Concurrency | 20 users | 50+ users | 20+ users | 10+ users |

### Search Mode Performance Expectations

| Search Mode | Expected Performance | Use Case |
|-------------|---------------------|----------|
| Vector | Fastest (< 30ms avg) | Semantic similarity |
| KV | Very Fast (< 25ms avg) | Exact matches |
| Graph | Fast (< 40ms avg) | Relationship queries |
| Hybrid | Moderate (< 60ms avg) | Comprehensive search |
| Auto | Variable | Adaptive optimization |

## Troubleshooting Performance Issues

### Common Performance Problems

1. **High Response Times**
   - Check backend health and connectivity
   - Monitor resource usage (CPU, memory, network)
   - Review query complexity and result sizes
   - Consider adding caching layers

2. **Low Throughput**
   - Verify concurrent user limits
   - Check for blocking operations
   - Review dispatch policy configuration
   - Monitor database connection pools

3. **High Error Rates**
   - Check backend availability
   - Review timeout configurations
   - Monitor system resource limits
   - Validate query input formats

### Performance Debugging

```bash
# Run system validation before benchmarking
python tools/cli/testing_tools.py validate

# Check backend health
python tools/cli/query_simulator.py
# In simulator: status, backends, stats

# Run isolated backend tests
python tools/benchmarks/performance_suite.py benchmark | grep "vector_only\|graph_only\|kv_only"

# Check resource usage during benchmarks
htop  # Monitor CPU and memory
iotop # Monitor disk I/O
nethogs # Monitor network usage
```

### Performance Optimization Tips

1. **Query Optimization**
   - Use specific search modes when possible
   - Limit result sizes appropriately
   - Apply pre-filters to reduce search scope
   - Avoid very complex or ambiguous queries

2. **System Configuration**
   - Use parallel dispatch for better throughput
   - Configure appropriate connection pools
   - Enable caching for frequently accessed data
   - Optimize backend storage configurations

3. **Infrastructure**
   - Ensure adequate CPU and memory resources
   - Use SSD storage for better I/O performance
   - Configure appropriate network bandwidth
   - Consider load balancing for high traffic

## Advanced Usage

### Custom Metrics Collection

```python
import psutil
import time

class CustomPerformanceBenchmark(PerformanceBenchmark):
    async def _execute_single_query(self, query: str, config: BenchmarkConfig):
        # Monitor CPU and memory during query execution
        cpu_before = psutil.cpu_percent()
        memory_before = psutil.virtual_memory().percent
        
        success, response_time = await super()._execute_single_query(query, config)
        
        cpu_after = psutil.cpu_percent()
        memory_after = psutil.virtual_memory().percent
        
        # Store additional metrics
        self.custom_metrics.append({
            'query': query,
            'cpu_delta': cpu_after - cpu_before,
            'memory_delta': memory_after - memory_before,
            'response_time': response_time
        })
        
        return success, response_time
```

### Performance Comparison Testing

```python
# Compare different configurations
configs_a = [config1, config2, config3]  # Configuration set A
configs_b = [config4, config5, config6]  # Configuration set B

results_a = await benchmark.run_benchmark_suite(configs_a)
results_b = await benchmark.run_benchmark_suite(configs_b)

# Analyze differences
comparison = compare_benchmark_results(results_a, results_b)
print(f"Configuration A is {comparison['speedup_factor']:.1f}x faster")
```

## Contributing

When adding new benchmarks or improving the performance suite:

1. Follow existing patterns for benchmark configuration
2. Include comprehensive documentation for new metrics
3. Add validation for custom configurations
4. Update this README with new features
5. Test with both mock and real backends

## Resources

- [Developer Guide](../docs/developer/README.md) - System architecture and development
- [CLI Tools](../cli/README.md) - Interactive testing and debugging tools
- [API Documentation](../docs/api/README.md) - REST API performance considerations
- [System Monitoring](../docs/monitoring/README.md) - Production monitoring setup

---

*Performance benchmarking is critical for maintaining system quality. Run benchmarks regularly and monitor trends to catch performance regressions early.*