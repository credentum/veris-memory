#!/bin/bash
# Remote burn-in test executed on Hetzner server

set -euo pipefail

# Copy test script to server
echo "📤 Deploying burn-in test to server..."

ssh hetzner-server << 'REMOTE_SCRIPT' > /tmp/burnin-output.log 2>&1
cd /opt/veris-memory

# Create burn-in test script
cat > /tmp/burnin_test.py << 'PYTHON'
#!/usr/bin/env python3
import requests
import json
import time
from datetime import datetime

print('🚀 VERIS MEMORY BURN-IN STABILITY SPRINT')
print('='*60)

cycles_passed = 0
total_cycles = 0
stability_threshold = 5
results = []

# Phase 1: Baseline
print('\n📊 PHASE 1: Baseline Metrics Capture')
print('-'*40)

try:
    # Test Qdrant locally
    r = requests.get('http://localhost:6333/collections/context_embeddings', timeout=5)
    config = r.json()['result']['config']['params']['vectors']
    points_count = r.json()['result']['points_count']
    collection_status = r.json()['result']['status']
    
    print(f'✅ Qdrant Configuration:')
    print(f'   Dimensions: {config["size"]}')
    print(f'   Distance: {config["distance"]}')
    print(f'   Status: {collection_status}')
    print(f'   Points: {points_count}')
    
    # Baseline performance test
    print('\nRunning baseline performance test...')
    latencies = []
    errors = 0
    
    for i in range(100):
        start = time.time()
        vector = [0.1] * 384
        try:
            r = requests.post(
                'http://localhost:6333/collections/context_embeddings/points/search',
                json={'vector': vector, 'limit': 5},
                timeout=5
            )
            latencies.append((time.time() - start) * 1000)
            if r.status_code != 200:
                errors += 1
        except:
            errors += 1
    
    latencies.sort()
    baseline_p50 = latencies[50] if latencies else 0
    baseline_p95 = latencies[95] if latencies else 0
    baseline_p99 = latencies[99] if latencies else 0
    
    print(f'✅ Baseline Performance:')
    print(f'   p50: {baseline_p50:.1f}ms')
    print(f'   p95: {baseline_p95:.1f}ms')
    print(f'   p99: {baseline_p99:.1f}ms')
    print(f'   Error rate: {errors}%')
    
except Exception as e:
    print(f'❌ Baseline failed: {e}')
    exit(1)

# Phase 2-4: Burn-in cycles
print('\n📊 PHASE 2-4: Burn-In Cycles')
print('-'*40)

while cycles_passed < stability_threshold and total_cycles < 10:
    total_cycles += 1
    print(f'\n🔄 Cycle {total_cycles}:')
    
    # Determine QPS
    if total_cycles % 3 == 0:
        qps = 50
        load_type = "BURST"
    elif total_cycles % 2 == 0:
        qps = 20
        load_type = "ELEVATED"
    else:
        qps = 10
        load_type = "NORMAL"
    
    print(f'  Load type: {load_type} ({qps} QPS)')
    
    # Fault injection every 4th cycle
    if total_cycles % 4 == 0:
        print('  💥 Fault injection: Service restart test')
        import subprocess
        subprocess.run(['docker-compose', 'restart', 'qdrant'], capture_output=True)
        time.sleep(10)
    
    # Load test
    errors = 0
    latencies = []
    
    for i in range(50):
        try:
            start = time.time()
            vector = [0.1 * (i % 10)] * 384
            r = requests.post(
                'http://localhost:6333/collections/context_embeddings/points/search',
                json={'vector': vector, 'limit': 5},
                timeout=5
            )
            latencies.append((time.time() - start) * 1000)
            if r.status_code != 200:
                errors += 1
        except:
            errors += 1
        time.sleep(1/qps)
    
    # Calculate metrics
    latencies.sort()
    p50 = latencies[int(len(latencies)*0.50)] if latencies else 0
    p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
    p99 = latencies[int(len(latencies)*0.99)] if latencies else 0
    error_rate = errors / 50 * 100
    
    # Integrity verification
    try:
        r = requests.get('http://localhost:6333/collections/context_embeddings', timeout=5)
        current_config = r.json()['result']['config']['params']['vectors']
        integrity_ok = (current_config['size'] == 384 and current_config['distance'] == 'Cosine')
    except:
        integrity_ok = False
    
    # Check stability
    drift_pct = abs(p95 - baseline_p95) / baseline_p95 * 100 if baseline_p95 > 0 else 0
    
    if drift_pct < 10 and error_rate < 0.5 and integrity_ok:
        cycles_passed += 1
        status = 'PASS'
    else:
        cycles_passed = 0
        if drift_pct < 20 and error_rate < 5:
            status = 'WARN'
        else:
            status = 'FAIL'
    
    # Store results
    cycle_result = {
        'cycle': total_cycles,
        'qps': qps,
        'p95_latency_ms': round(p95, 1),
        'error_rate_percent': round(error_rate, 2),
        'status': status
    }
    results.append(cycle_result)
    
    print(f'  Results:')
    print(f'    p95: {p95:.1f}ms (drift: {drift_pct:.1f}%)')
    print(f'    Errors: {error_rate:.1f}%')
    print(f'    Integrity: {"✅" if integrity_ok else "❌"}')
    print(f'    Status: {status}')
    print(f'  Stability: {cycles_passed}/{stability_threshold}')

# Phase 5: Final sign-off
print('\n📊 PHASE 5: Final Sign-Off')
print('-'*40)

if cycles_passed >= stability_threshold:
    print('✅ BURN-IN PASSED!')
    print(f'  Total cycles: {total_cycles}')
    print(f'  Stability achieved: {cycles_passed} consecutive passes')
    tag = f'burnin-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    print(f'  Tag: {tag}')
    
    # Save report
    report = {
        'status': 'PASSED',
        'cycles_run': total_cycles,
        'stable_cycles': cycles_passed,
        'baseline_p95_ms': round(baseline_p95, 1),
        'tag': tag,
        'cycles_history': results
    }
else:
    print('⚠️ Stability threshold not reached')
    print(f'  Cycles passed: {cycles_passed}/{stability_threshold}')
    report = {
        'status': 'PARTIAL',
        'cycles_run': total_cycles,
        'stable_cycles': cycles_passed,
        'baseline_p95_ms': round(baseline_p95, 1),
        'cycles_history': results
    }

with open('/opt/veris-memory/burnin-report.json', 'w') as f:
    json.dump(report, f, indent=2)

print('\n' + '='*60)
print('Burn-in sprint complete!')
print('Report saved to: /opt/veris-memory/burnin-report.json')
PYTHON

# Run the burn-in test
echo "🚀 Starting burn-in test on server..."
python3 /tmp/burnin_test.py

REMOTE_SCRIPT

echo ""
echo "📊 Burn-in test output:"
echo "======================"
cat /tmp/burnin-output.log

# Fetch the report
echo ""
echo "📥 Fetching burn-in report..."
scp -q hetzner-server:/opt/veris-memory/burnin-report.json /workspaces/agent-context-template/context-store/burnin-results/remote-report.json 2>/dev/null || true

if [ -f /workspaces/agent-context-template/context-store/burnin-results/remote-report.json ]; then
    echo "✅ Report saved to: burnin-results/remote-report.json"
    echo ""
    echo "📊 Report Summary:"
    cat /workspaces/agent-context-template/context-store/burnin-results/remote-report.json | python3 -m json.tool | head -20
else
    echo "⚠️ Could not fetch report file"
fi