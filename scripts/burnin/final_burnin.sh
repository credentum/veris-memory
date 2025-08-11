#!/bin/bash
# Final burn-in test for Veris Memory deployment
set -euo pipefail

HETZNER_HOST="${HETZNER_HOST:-hetzner-server}"
CYCLES="${1:-3}"
RESULTS_DIR="/workspaces/agent-context-template/context-store/burnin-results/run-$(date +%Y%m%d-%H%M%S)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$RESULTS_DIR"

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}" | tee -a "$RESULTS_DIR/log.txt"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}" | tee -a "$RESULTS_DIR/log.txt"; }

# Quick Qdrant test
test_qdrant() {
    local cycle=$1
    log "Testing Qdrant performance (cycle $cycle)..."
    
    # Create Python test script
    cat > "$RESULTS_DIR/test.py" << 'PYTHON'
import requests, time, json, random, sys
cycle = int(sys.argv[1])
latencies = []
errors = 0

for i in range(50):  # Reduced for faster testing
    try:
        vector = [random.random() for _ in range(384)]
        start = time.time()
        r = requests.post(
            "http://localhost:6333/collections/context_embeddings/points/search",
            json={"vector": vector, "limit": 5},
            timeout=5
        )
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
        if r.status_code != 200:
            errors += 1
    except:
        errors += 1
    time.sleep(0.02)  # ~50 QPS burst

latencies.sort()
print(json.dumps({
    "cycle": cycle,
    "requests": len(latencies),
    "errors": errors,
    "p50_ms": round(latencies[len(latencies)//2], 1) if latencies else 0,
    "p95_ms": round(latencies[int(len(latencies)*95//100)], 1) if latencies else 0,
    "max_ms": round(max(latencies), 1) if latencies else 0
}))
PYTHON
    
    # Run test on server
    scp -q "$RESULTS_DIR/test.py" "$HETZNER_HOST:/tmp/burnin_test.py" 2>/dev/null
    ssh "$HETZNER_HOST" "python3 /tmp/burnin_test.py $cycle" > "$RESULTS_DIR/cycle-$cycle.json"
    
    # Parse results
    local p95=$(grep '"p95_ms"' "$RESULTS_DIR/cycle-$cycle.json" | grep -oE '[0-9.]+' | head -1)
    local errors=$(grep '"errors"' "$RESULTS_DIR/cycle-$cycle.json" | grep -oE '[0-9]+' | head -1)
    
    log "Results: p95=${p95}ms, errors=${errors}/50"
    echo "$p95"  # Return p95 for comparison
}

# Verify services and config
verify_all() {
    local cycle=$1
    log "Verifying services (cycle $cycle)..."
    
    # Quick health checks
    ssh "$HETZNER_HOST" << EOF > "$RESULTS_DIR/health-$cycle.json" 2>/dev/null
{
  "qdrant": $(curl -s http://localhost:6333/ | grep -q qdrant && echo '"healthy"' || echo '"unhealthy"'),
  "neo4j": $(curl -s http://localhost:7474/ | grep -q neo4j && echo '"healthy"' || echo '"unhealthy"'),
  "redis": $(docker exec veris-memory-redis-1 redis-cli ping 2>/dev/null | grep -q PONG && echo '"healthy"' || echo '"unhealthy"')
}
EOF
    
    # Verify Qdrant config
    local config=$(ssh "$HETZNER_HOST" "curl -s http://localhost:6333/collections/context_embeddings")
    if echo "$config" | grep -q '"size":384' && echo "$config" | grep -q '"distance":"Cosine"'; then
        log "✅ Config stable: 384 dims, Cosine distance"
        return 0
    else
        warn "Config drift detected!"
        return 1
    fi
}

# Service restart test
test_restart() {
    log "Testing service restart resilience..."
    ssh "$HETZNER_HOST" "cd /opt/veris-memory && docker-compose restart qdrant" >/dev/null 2>&1
    sleep 10
    if ssh "$HETZNER_HOST" "curl -s http://localhost:6333/ | grep -q qdrant"; then
        log "✅ Qdrant restarted successfully"
    else
        warn "Qdrant restart failed!"
    fi
}

# Main burn-in
main() {
    log "🚀 Veris Memory Burn-In Sprint"
    log "=============================="
    log "Target: $HETZNER_HOST"
    log "Cycles: $CYCLES"
    log "Results: $RESULTS_DIR"
    echo
    
    # Phase 1: Baseline
    log "📊 PHASE 1: BASELINE METRICS"
    verify_all 0
    BASELINE_P95=$(test_qdrant 0)
    log "Baseline established: p95=${BASELINE_P95}ms"
    echo
    
    # Phase 2-4: Burn-in cycles
    PASS_COUNT=0
    for cycle in $(seq 1 "$CYCLES"); do
        log "📊 BURN-IN CYCLE $cycle/$CYCLES"
        log "========================"
        
        # Phase 4: Integrity check
        verify_all "$cycle"
        
        # Phase 2: Normal load
        CURRENT_P95=$(test_qdrant "$cycle")
        
        # Phase 3: Elevated load (every 3rd cycle)
        if [ $((cycle % 3)) -eq 0 ]; then
            log "⚡ Elevated load test..."
            test_restart
            test_qdrant "elevated-$cycle" >/dev/null
        fi
        
        # Check drift
        DRIFT=$(( (${CURRENT_P95%.*} - ${BASELINE_P95%.*}) * 100 / ${BASELINE_P95%.*} ))
        if [ "$DRIFT" -lt 20 ]; then
            log "✅ Cycle $cycle PASSED (drift: ${DRIFT}%)"
            ((PASS_COUNT++))
        else
            warn "Cycle $cycle: High drift (${DRIFT}%)"
        fi
        echo
    done
    
    # Phase 5: Final sign-off
    log "🏁 PHASE 5: FINAL SIGN-OFF"
    log "=========================="
    
    # Generate summary
    cat > "$RESULTS_DIR/summary.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "cycles_total": $CYCLES,
  "cycles_passed": $PASS_COUNT,
  "baseline_p95_ms": $BASELINE_P95,
  "final_p95_ms": $CURRENT_P95,
  "drift_percent": $DRIFT,
  "status": "$([ "$PASS_COUNT" -eq "$CYCLES" ] && echo "PASSED" || echo "PARTIAL")"
}
EOF
    
    log "Summary:"
    log "- Cycles passed: $PASS_COUNT/$CYCLES"
    log "- Baseline p95: ${BASELINE_P95}ms"
    log "- Final p95: ${CURRENT_P95}ms"
    log "- Drift: ${DRIFT}%"
    
    if [ "$PASS_COUNT" -eq "$CYCLES" ]; then
        log "✅ BURN-IN PASSED!"
        
        # Tag the deployment
        TAG="burnin-stable-$(date +%Y%m%d-%H%M%S)"
        cd /workspaces/agent-context-template/context-store
        git tag "$TAG" 2>/dev/null || true
        log "Tagged: $TAG"
    else
        warn "⚠️ Burn-in completed with warnings"
    fi
    
    log ""
    log "Full results: $RESULTS_DIR"
}

main "$@"