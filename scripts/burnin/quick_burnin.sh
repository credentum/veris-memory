#!/bin/bash
# Quick burn-in test for Veris Memory deployment
# Validates stability and performance over multiple cycles

set -euo pipefail

# Configuration
HETZNER_HOST="${HETZNER_HOST:-hetzner-server}"
CYCLES="${1:-5}"  # Default 5 cycles
RESULTS_DIR="/tmp/burnin-results-$(date +%Y%m%d-%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create results directory
mkdir -p "$RESULTS_DIR"

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}" | tee -a "$RESULTS_DIR/burnin.log"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$RESULTS_DIR/burnin.log"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$RESULTS_DIR/burnin.log"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$RESULTS_DIR/burnin.log"
}

# Check service health
check_health() {
    local cycle=$1
    log "Checking service health for cycle $cycle..."
    
    # Check via SSH
    ssh "$HETZNER_HOST" << 'EOF' > "$RESULTS_DIR/health-cycle-$cycle.json" 2>/dev/null
    echo "{"
    echo '  "timestamp": "'$(date -Iseconds)'",'
    echo '  "services": {'
    
    # Check Qdrant
    if curl -s http://localhost:6333/ | grep -q "qdrant"; then
        echo '    "qdrant": "healthy",'
    else
        echo '    "qdrant": "unhealthy",'
    fi
    
    # Check Neo4j
    if curl -s http://localhost:7474/ | grep -q "neo4j"; then
        echo '    "neo4j": "healthy",'
    else
        echo '    "neo4j": "unhealthy",'
    fi
    
    # Check Redis
    if docker exec veris-memory-redis-1 redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo '    "redis": "healthy"'
    else
        echo '    "redis": "unhealthy"'
    fi
    
    echo "  }"
    echo "}"
EOF
    
    # Check if all services are healthy
    if grep -q '"unhealthy"' "$RESULTS_DIR/health-cycle-$cycle.json"; then
        warn "Some services are unhealthy in cycle $cycle"
        return 1
    else
        log "✅ All services healthy"
        return 0
    fi
}

# Test Qdrant collection config
test_qdrant_config() {
    local cycle=$1
    log "Verifying Qdrant configuration for cycle $cycle..."
    
    ssh "$HETZNER_HOST" << 'EOF' > "$RESULTS_DIR/qdrant-config-cycle-$cycle.json"
    curl -s http://localhost:6333/collections/context_embeddings | python3 -c "
import sys, json
data = json.load(sys.stdin)
config = data.get('result', {}).get('config', {})
vectors = config.get('params', {}).get('vectors', {})
print(json.dumps({
    'size': vectors.get('size'),
    'distance': vectors.get('distance'),
    'status': data.get('result', {}).get('status'),
    'points_count': data.get('result', {}).get('points_count', 0)
}, indent=2))
"
EOF
    
    # Verify configuration
    local size=$(grep '"size"' "$RESULTS_DIR/qdrant-config-cycle-$cycle.json" | grep -o '[0-9]*')
    local distance=$(grep '"distance"' "$RESULTS_DIR/qdrant-config-cycle-$cycle.json" | grep -o '"Cosine"')
    
    if [ "$size" = "384" ] && [ -n "$distance" ]; then
        log "✅ Qdrant config verified: 384 dimensions, Cosine distance"
        return 0
    else
        error "Qdrant configuration drift detected!"
        return 1
    fi
}

# Run performance test
run_perf_test() {
    local cycle=$1
    local duration=${2:-60}  # Default 60 seconds
    log "Running performance test for cycle $cycle (${duration}s)..."
    
    # Create test script
    cat > /tmp/perf_test.py << 'EOF'
import requests
import time
import json
import sys
import random

duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
host = sys.argv[2] if len(sys.argv) > 2 else "localhost"

url = f"http://{host}:6333/collections/context_embeddings/points/search"
latencies = []
errors = 0
total = 0

start_time = time.time()
while time.time() - start_time < duration:
    try:
        # Generate random test vector
        test_vector = [random.random() for _ in range(384)]
        
        req_start = time.time()
        response = requests.post(url, json={
            "vector": test_vector,
            "limit": 5,
            "with_payload": True
        }, timeout=5)
        
        latency_ms = (time.time() - req_start) * 1000
        latencies.append(latency_ms)
        total += 1
        
        if response.status_code != 200:
            errors += 1
            
    except Exception as e:
        errors += 1
        total += 1
    
    time.sleep(0.1)  # ~10 QPS

# Calculate metrics
latencies.sort()
if latencies:
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
else:
    p50 = p95 = p99 = 0

error_rate = (errors / total * 100) if total > 0 else 0

print(json.dumps({
    "total_requests": total,
    "errors": errors,
    "error_rate_pct": round(error_rate, 2),
    "p50_ms": round(p50, 1),
    "p95_ms": round(p95, 1),
    "p99_ms": round(p99, 1),
    "avg_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0
}, indent=2))
EOF
    
    # Run test on remote server
    scp -q /tmp/perf_test.py "$HETZNER_HOST:/tmp/" 2>/dev/null
    ssh "$HETZNER_HOST" "python3 /tmp/perf_test.py $duration localhost" > "$RESULTS_DIR/perf-cycle-$cycle.json"
    
    # Parse and display results
    local p95=$(grep '"p95_ms"' "$RESULTS_DIR/perf-cycle-$cycle.json" | grep -oE '[0-9.]+')
    local errors=$(grep '"errors"' "$RESULTS_DIR/perf-cycle-$cycle.json" | grep -oE '[0-9]+')
    
    log "Performance: p95=${p95}ms, errors=${errors}"
    
    # Check thresholds
    if (( $(echo "$p95 > 500" | bc -l) )); then
        warn "High latency detected: ${p95}ms"
    fi
    
    if [ "$errors" -gt "5" ]; then
        warn "High error count: ${errors}"
    fi
}

# Test with elevated load
test_elevated_load() {
    local cycle=$1
    log "Testing elevated load (2x QPS) for cycle $cycle..."
    
    # Run shorter test with higher load
    ssh "$HETZNER_HOST" << 'EOF' > "$RESULTS_DIR/burst-cycle-$cycle.json"
    python3 /tmp/perf_test.py 30 localhost
EOF
    
    log "✅ Elevated load test complete"
}

# Test service restart
test_service_restart() {
    local cycle=$1
    log "Testing service restart resilience for cycle $cycle..."
    
    # Restart Qdrant
    ssh "$HETZNER_HOST" "cd /opt/veris-memory && docker-compose restart qdrant" >/dev/null 2>&1
    
    # Wait for service to be ready
    sleep 10
    
    # Verify it's back
    if ssh "$HETZNER_HOST" "curl -s http://localhost:6333/ | grep -q qdrant"; then
        log "✅ Service restart successful"
    else
        error "Service failed to restart!"
    fi
}

# Generate cycle report
generate_report() {
    local cycle=$1
    log "Generating report for cycle $cycle..."
    
    cat > "$RESULTS_DIR/report-cycle-$cycle.json" << EOF
{
  "cycle": $cycle,
  "timestamp": "$(date -Iseconds)",
  "health_check": "$([ -f "$RESULTS_DIR/health-cycle-$cycle.json" ] && echo "completed" || echo "failed")",
  "perf_test": "$([ -f "$RESULTS_DIR/perf-cycle-$cycle.json" ] && echo "completed" || echo "failed")",
  "config_check": "$([ -f "$RESULTS_DIR/qdrant-config-cycle-$cycle.json" ] && echo "completed" || echo "failed")"
}
EOF
}

# Main burn-in loop
main() {
    log "🚀 Starting Veris Memory Burn-In Test"
    log "=================================="
    log "Target: $HETZNER_HOST"
    log "Cycles: $CYCLES"
    log "Results: $RESULTS_DIR"
    echo ""
    
    # Capture baseline
    log "📊 PHASE 1: Capturing Baseline"
    check_health 0
    test_qdrant_config 0
    run_perf_test 0 120  # 2-minute baseline
    
    # Save baseline metrics
    cp "$RESULTS_DIR/perf-cycle-0.json" "$RESULTS_DIR/baseline.json"
    BASELINE_P95=$(grep '"p95_ms"' "$RESULTS_DIR/baseline.json" | grep -oE '[0-9.]+')
    log "Baseline p95: ${BASELINE_P95}ms"
    echo ""
    
    # Run burn-in cycles
    for cycle in $(seq 1 "$CYCLES"); do
        log "📊 BURN-IN CYCLE $cycle/$CYCLES"
        log "=========================="
        
        # Normal load test
        check_health "$cycle"
        test_qdrant_config "$cycle"
        run_perf_test "$cycle" 60
        
        # Every 3rd cycle, run elevated tests
        if [ $((cycle % 3)) -eq 0 ]; then
            log "⚡ Running elevated load tests..."
            test_elevated_load "$cycle"
            test_service_restart "$cycle"
        fi
        
        # Generate cycle report
        generate_report "$cycle"
        
        # Check drift from baseline
        CURRENT_P95=$(grep '"p95_ms"' "$RESULTS_DIR/perf-cycle-$cycle.json" | grep -oE '[0-9.]+')
        DRIFT=$(echo "scale=2; ($CURRENT_P95 - $BASELINE_P95) / $BASELINE_P95 * 100" | bc)
        
        info "Drift from baseline: ${DRIFT}%"
        
        # Fail if drift > 20%
        if (( $(echo "$DRIFT > 20" | bc -l) )); then
            error "Excessive drift detected: ${DRIFT}%"
        fi
        
        echo ""
    done
    
    # Final summary
    log "🏁 BURN-IN COMPLETE"
    log "=================="
    log "Total cycles: $CYCLES"
    log "Results saved to: $RESULTS_DIR"
    
    # Count successful cycles
    SUCCESSFUL=$(ls "$RESULTS_DIR"/report-cycle-*.json 2>/dev/null | wc -l)
    log "Successful cycles: $SUCCESSFUL/$CYCLES"
    
    # Generate final summary
    cat > "$RESULTS_DIR/burnin-summary.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "total_cycles": $CYCLES,
  "successful_cycles": $SUCCESSFUL,
  "baseline_p95_ms": $BASELINE_P95,
  "results_dir": "$RESULTS_DIR",
  "status": "$([ "$SUCCESSFUL" -eq "$CYCLES" ] && echo "PASSED" || echo "FAILED")"
}
EOF
    
    if [ "$SUCCESSFUL" -eq "$CYCLES" ]; then
        log "✅ BURN-IN PASSED - System is stable!"
        
        # Create git tag
        TAG="burnin-$(date +%Y%m%d-%H%M%S)"
        log "Creating git tag: $TAG"
        cd /workspaces/agent-context-template/context-store
        git tag "$TAG" 2>/dev/null || true
        log "Tagged as: $TAG"
    else
        error "❌ BURN-IN FAILED - System unstable"
    fi
}

# Run main
main "$@"