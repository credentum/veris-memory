#!/usr/bin/env python3
"""Simple burn-in test to run on server"""
import requests
import json
import time
from datetime import datetime

print('🚀 VERIS MEMORY BURN-IN STABILITY SPRINT')
print('='*60)

# Test Qdrant
r = requests.get('http://localhost:6333/collections/context_embeddings')
data = r.json()['result']
config = data['config']['params']['vectors']
status = data['status']
points = data['points_count']

print(f'\n✅ Qdrant Configuration:')
print(f'   Dimensions: {config["size"]}')
print(f'   Distance: {config["distance"]}')
print(f'   Status: {status}')
print(f'   Points: {points}')

# Baseline performance test
print('\n📊 Running baseline test (100 requests)...')
latencies = []
for i in range(100):
    start = time.time()
    vector = [0.1] * 384
    r = requests.post('http://localhost:6333/collections/context_embeddings/points/search',
                     json={'vector': vector, 'limit': 5}, timeout=5)
    latencies.append((time.time() - start) * 1000)

latencies.sort()
p50 = latencies[50]
p95 = latencies[95]
p99 = latencies[99]

print(f'✅ Baseline Performance:')
print(f'   p50: {p50:.1f}ms')
print(f'   p95: {p95:.1f}ms')
print(f'   p99: {p99:.1f}ms')

# Run 5 burn-in cycles
print('\n📊 Running burn-in cycles...')
stable_cycles = 0
results = []

for cycle in range(1, 6):
    print(f'\nCycle {cycle}:', end=' ')
    cycle_latencies = []
    errors = 0
    
    # Different QPS per cycle
    qps = 50 if cycle % 3 == 0 else 20 if cycle % 2 == 0 else 10
    
    for i in range(50):
        try:
            start = time.time()
            vector = [0.1 * (i % 10)] * 384
            r = requests.post('http://localhost:6333/collections/context_embeddings/points/search',
                            json={'vector': vector, 'limit': 5}, timeout=5)
            cycle_latencies.append((time.time() - start) * 1000)
            if r.status_code != 200:
                errors += 1
        except:
            errors += 1
        time.sleep(1/qps)
    
    cycle_latencies.sort()
    cycle_p95 = cycle_latencies[int(len(cycle_latencies)*0.95)] if cycle_latencies else 0
    
    # Success if p95 < 10ms and no errors
    if cycle_p95 < 10 and errors == 0:
        stable_cycles += 1
        status = 'PASS'
        print(f'✅ PASS ({qps} QPS, p95={cycle_p95:.1f}ms)')
    else:
        stable_cycles = 0
        status = 'FAIL'
        print(f'❌ FAIL ({qps} QPS, p95={cycle_p95:.1f}ms, errors={errors})')
    
    results.append({
        'cycle': cycle,
        'qps': qps,
        'p95_ms': round(cycle_p95, 1),
        'errors': errors,
        'status': status
    })

print(f'\n{"="*60}')

# Final report
if stable_cycles >= 5:
    final_status = 'PASSED'
    tag = f'burnin-stable-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    print('✅✅✅ BURN-IN PASSED! ✅✅✅')
    print(f'   5 consecutive stable cycles achieved')
    print(f'   Tag: {tag}')
else:
    final_status = 'PARTIAL'
    tag = None
    print(f'⚠️ Burn-in incomplete: {stable_cycles}/5 stable cycles')

# Save report
report = {
    'status': final_status,
    'deployment': {
        'server': 'Hetzner (135.181.4.118)',
        'location': '/opt/veris-memory'
    },
    'configuration': {
        'dimensions': config['size'],
        'distance': config['distance'],
        'status': status
    },
    'baseline': {
        'p50_ms': round(p50, 1),
        'p95_ms': round(p95, 1),
        'p99_ms': round(p99, 1)
    },
    'cycles': results,
    'stable_cycles': stable_cycles,
    'timestamp': datetime.now().isoformat(),
    'tag': tag
}

with open('burnin-report.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f'\n📊 Report saved: burnin-report.json')
print('='*60)