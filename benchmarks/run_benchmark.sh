#!/bin/bash
# Script to run MCP performance benchmarks

set -e

echo "==================================="
echo "MCP Performance Benchmark Runner"
echo "==================================="

# Check if MCP server is running
check_mcp_server() {
    echo "Checking MCP server status..."
    if curl -s -f http://localhost:8000/mcp/health > /dev/null 2>&1; then
        echo "✅ MCP server is running"
        return 0
    else
        echo "❌ MCP server is not running"
        echo "Please start the server with: docker-compose up -d"
        return 1
    fi
}

# Create results directory
mkdir -p benchmark_results

# Parse command line arguments
ITERATIONS=${1:-100}
CONCURRENT=${2:-"1 10 50 100"}

echo ""
echo "Configuration:"
echo "- Iterations: $ITERATIONS"
echo "- Concurrent connections: $CONCURRENT"
echo ""

# Check server before running
if ! check_mcp_server; then
    echo "Exiting due to server not running"
    exit 1
fi

echo ""
echo "Starting benchmark..."
echo ""

# Run the benchmark
python3 mcp_performance_benchmark.py \
    --iterations "$ITERATIONS" \
    --concurrent-connections $CONCURRENT \
    --output-dir benchmark_results

echo ""
echo "Benchmark complete! Results saved to benchmark_results/"
echo ""

# Show summary of latest results
LATEST_REPORT=$(ls -t benchmark_results/mcp_benchmark_report_*.txt | head -1)
if [ -f "$LATEST_REPORT" ]; then
    echo "Summary from $LATEST_REPORT:"
    echo ""
    grep -A 10 "SUMMARY AND RECOMMENDATIONS" "$LATEST_REPORT"
fi
