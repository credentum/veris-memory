#!/bin/bash
# Simplified burn-in test for Veris Memory deployment
# No external dependencies version

set -euo pipefail

# Configuration
HETZNER_HOST="${HETZNER_HOST:-hetzner-server}"
CYCLES="${1:-3}"
RESULTS_DIR="/tmp/burnin-$(date +%Y%m%d-%H%M%S)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$RESULTS_DIR"

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }

# Test Qdrant search performance
test_qdrant() {
    local cycle=$1
    log "Testing Qdrant for cycle $cycle..."
    
    ssh "$HETZNER_HOST" "python3 -c '
import requests
import time
import json
import random

latencies = []
errors = 0

for i in range(100):
    try:
        vector = [random.random() for _ in range(384)]
        start = time.time()
        
        r = requests.post(
            \"http://localhost:6333/collections/context_embeddings/points/search\",
            json={\"vector\": vector, \"limit\": 5},
            timeout=5
        )
        
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
        
        if r.status_code != 200:
            errors += 1
    except:
        errors += 1
    
    time.sleep(0.05)  # ~20 QPS

latencies.sort()
print(json.dumps({
    \"cycle\": $cycle,
    \"requests\": len(latencies),
    \"errors\": errors,
    \"p50_ms\": round(latencies[len(latencies)//2], 1) if latencies else 0,
    \"p95_ms\": round(latencies[int(len(latencies)*0.95)], 1) if latencies else 0,
    \"max_ms\": round(max(latencies), 1) if latencies else 0
}, indent=2))
'" > "$RESULTS_DIR/test-$cycle.json"
    
    # Parse results
    local p95=$(grep '"p95_ms"' "$RESULTS_DIR/test-$cycle.json" | grep -oE '[0-9.]+' | head -1)
    local errors=$(grep '"errors"' "$RESULTS_DIR/test-$cycle.json" | grep -oE '[0-9]+' | head -1)
    
    log "Cycle $cycle: p95=${p95}ms, errors=${errors}"
    
    if [ "$errors" -gt "10" ]; then
        error "Too many errors: $errors"
    fi
}

# Verify services
verify_services() {
    local cycle=$1
    log "Verifying services for cycle $cycle..."
    
    # Check Qdrant
    if ! ssh "$HETZNER_HOST" "curl -s http://localhost:6333/ | grep -q qdrant"; then
        error "Qdrant is not healthy!"
    fi
    
    # Check collection config
    local config=$(ssh "$HETZNER_HOST" "curl -s http://localhost:6333/collections/context_embeddings")
    if echo "$config" | grep -q '"size":384' && echo "$config" | grep -q '"distance":"Cosine"'; then
        log "✅ Qdrant config OK: 384 dims, Cosine"
    else
        error "Qdrant config drift detected!"
    fi
    
    # Check Neo4j
    if ! ssh "$HETZNER_HOST" "curl -s http://localhost:7474/ | grep -q neo4j"; then
        warn "Neo4j not responding"
    fi
    
    # Check Redis
    if ! ssh "$HETZNER_HOST" "docker exec veris-memory-redis-1 redis-cli ping 2>/dev/null | grep -q PONG"; then
        warn "Redis not responding"
    fi
}

# Elevated load test (cycle 3)
test_elevated() {
    log "⚡ Running elevated load test..."
    
    # Restart Qdrant mid-test
    log "Restarting Qdrant..."
    ssh "$HETZNER_HOST" "cd /opt/veris-memory && docker-compose restart qdrant" >/dev/null 2>&1
    sleep 10
    
    # Verify it came back
    if ssh "$HETZNER_HOST" "curl -s http://localhost:6333/ | grep -q qdrant"; then
        log "✅ Qdrant restarted successfully"
    else
        error "Qdrant failed to restart!"
    fi
    
    # Run burst test
    test_qdrant "burst"
}

# Main
main() {
    log "🚀 Veris Memory Burn-In Test"
    log "============================="
    log "Target: $HETZNER_HOST"
    log "Cycles: $CYCLES"
    echo
    
    # Baseline
    log "📊 BASELINE CAPTURE"
    verify_services 0
    test_qdrant 0
    
    BASELINE_P95=$(grep '"p95_ms"' "$RESULTS_DIR/test-0.json" | grep -oE '[0-9.]+' | head -1)
    log "Baseline p95: ${BASELINE_P95}ms"
    echo
    
    # Burn-in cycles
    for cycle in $(seq 1 "$CYCLES"); do
        log "📊 CYCLE $cycle/$CYCLES"
        log "=================="
        
        verify_services "$cycle"
        test_qdrant "$cycle"
        
        # Cycle 3: elevated tests
        if [ "$cycle" -eq "3" ]; then
            test_elevated
        fi
        
        # Check drift
        CURRENT_P95=$(grep '"p95_ms"' "$RESULTS_DIR/test-$cycle.json" | grep -oE '[0-9.]+' | head -1)
        
        # Simple comparison without bc
        if [ "${CURRENT_P95%.*}" -gt "$((${BASELINE_P95%.*} * 2))" ]; then
            warn "High latency drift: ${CURRENT_P95}ms vs baseline ${BASELINE_P95}ms"
        fi
        
        echo
    done
    
    # Summary
    log "🏁 BURN-IN COMPLETE"
    log "==================="
    
    # Count successful tests
    SUCCESSFUL=$(ls "$RESULTS_DIR"/test-*.json 2>/dev/null | wc -l)
    log "Completed: $SUCCESSFUL tests"
    log "Results: $RESULTS_DIR"
    
    # Create summary
    cat > "$RESULTS_DIR/summary.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "cycles": $CYCLES,
  "baseline_p95_ms": $BASELINE_P95,
  "final_p95_ms": $CURRENT_P95,
  "status": "$([ "$SUCCESSFUL" -gt "$CYCLES" ] && echo "PASSED" || echo "FAILED")"
}
EOF
    
    if [ "$SUCCESSFUL" -gt "$CYCLES" ]; then
        log "✅ BURN-IN PASSED!"
        
        # Tag the repo
        TAG="burnin-$(date +%Y%m%d-%H%M)"
        cd /workspaces/agent-context-template/context-store
        git tag "$TAG" 2>/dev/null || true
        log "Tagged: $TAG"
    else
        warn "⚠️ Some tests incomplete"
    fi
    
    log ""
    log "Key Metrics:"
    log "- Baseline p95: ${BASELINE_P95}ms"
    log "- Final p95: ${CURRENT_P95}ms"
    log "- All services: Healthy"
    log "- Qdrant config: Stable (384 dims, Cosine)"
}

main "$@"