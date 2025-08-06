# MCP Performance Benchmarks

This directory contains performance benchmarking tools for the Context Store MCP server.

## Overview

The benchmarking suite measures:

- Individual MCP tool response times
- Comparison with direct database access
- Concurrent connection handling (up to 200+ connections)
- Memory usage and resource consumption
- Performance under various load conditions

## Quick Start

```bash
# Run default benchmark (100 iterations, test 1/10/50/100 concurrent connections)
./run_benchmark.sh

# Run with custom parameters
./run_benchmark.sh 500 "1 25 50 100 150 200"

# Run Python script directly with all options
python mcp_performance_benchmark.py \
    --mcp-url http://localhost:8000/mcp \
    --iterations 1000 \
    --concurrent-connections 1 10 50 100 200 \
    --output-dir benchmark_results
```

## Performance Targets

Based on Sprint 5.14 requirements:

- **Response Time**: < 50ms for all operations
- **Concurrent Connections**: 100+ simultaneous connections
- **Memory Stability**: Minimal growth under sustained load

## Files

- `mcp_performance_benchmark.py` - Main benchmarking tool
- `run_benchmark.sh` - Convenience script to run benchmarks
- `benchmark_results/` - Directory containing benchmark results
- `README.md` - This file

## Benchmark Operations Tested

1. **store_context** - Store context with metadata
2. **retrieve_context** - Search and retrieve contexts
3. **query_graph** - Execute Cypher queries
4. **get_agent_state** - Retrieve agent state
5. **update_scratchpad** - Update scratchpad content

## Output Files

Each benchmark run generates:

- `mcp_benchmark_YYYYMMDD_HHMMSS.json` - Raw JSON results
- `mcp_benchmark_report_YYYYMMDD_HHMMSS.txt` - Formatted report

## Interpreting Results

The benchmark report includes:

1. **Individual Operation Performance**

   - Min/Max/Average/Median/P95 response times
   - Whether operations meet the <50ms target

2. **MCP vs Direct Database Comparison**

   - Overhead introduced by MCP protocol
   - Performance impact analysis

3. **Concurrent Connection Performance**

   - Success/failure rates at different connection levels
   - Response time degradation under load
   - Memory usage patterns

4. **Summary and Recommendations**
   - Overall performance assessment
   - Specific optimization suggestions

## Example Output

```
1. INDIVIDUAL OPERATION PERFORMANCE
----------------------------------------
Operation      Count  Min(ms)  Avg(ms)  Median(ms)  P95(ms)  Max(ms)  Target Met
store_context  100    12.34    23.45    22.10       35.67    45.23    ✓
retrieve_context 100  15.67    28.90    27.34       42.11    48.90    ✓

3. CONCURRENT CONNECTIONS PERFORMANCE
----------------------------------------
Connections  Successful  Failed  Avg Time(ms)  P95 Time(ms)  Memory Δ(MB)
1            1           0       45.23         45.23         0.12
10           10          0       48.90         52.34         1.45
50           50          0       67.89         89.12         5.67
100          100         0       95.45         145.67        10.23
```

## Performance Tuning

See `../docs/performance-tuning-guide.md` for detailed optimization recommendations based on benchmark results.

## Troubleshooting

If benchmarks fail:

1. **Check MCP server is running**

   ```bash
   docker-compose ps
   curl http://localhost:8000/mcp/health
   ```

2. **Verify database connections**

   - Neo4j: http://localhost:7474
   - Qdrant: http://localhost:6333

3. **Check system resources**

   ```bash
   # File descriptor limits
   ulimit -n

   # Memory available
   free -h
   ```

4. **Review server logs**
   ```bash
   docker-compose logs mcp-server
   ```
