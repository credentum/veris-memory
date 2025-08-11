#!/usr/bin/env python3
"""
Enhanced burn-in test with Sprint 8 guardrails:
- Timing source labels (e2e vs internal)
- P99 and max latency metrics
- Tail latency alert thresholds
"""
import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print('🚀 VERIS MEMORY BURN-IN STABILITY SPRINT (Enhanced)')
print('='*60)

class LatencyMetrics:
    """Track latency metrics with source labeling"""
    
    def __init__(self, source: str = "e2e"):
        self.source = source  # "e2e" or "internal"
        self.latencies: List[float] = []
    
    def add(self, latency_ms: float):
        self.latencies.append(latency_ms)
    
    def calculate_percentiles(self) -> Dict:
        if not self.latencies:
            return {
                'source': self.source,
                'p50_ms': 0,
                'p95_ms': 0,
                'p99_ms': 0,
                'max_ms': 0,
                'count': 0
            }
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            'source': self.source,
            'p50_ms': round(sorted_latencies[int(n * 0.50)], 1),
            'p95_ms': round(sorted_latencies[int(n * 0.95)], 1),
            'p99_ms': round(sorted_latencies[min(int(n * 0.99), n-1)], 1),
            'max_ms': round(sorted_latencies[-1], 1),
            'count': n
        }
    
    def check_tail_alerts(self) -> Dict:
        """Check for tail latency issues"""
        percentiles = self.calculate_percentiles()
        alerts = []
        
        if percentiles['count'] > 0:
            p95 = percentiles['p95_ms']
            p99 = percentiles['p99_ms']
            max_val = percentiles['max_ms']
            
            # Alert if p99 > 1.5× p95
            if p99 > p95 * 1.5:
                alerts.append({
                    'type': 'p99_spike',
                    'message': f'p99 ({p99}ms) > 1.5× p95 ({p95}ms)',
                    'severity': 'WARN'
                })
            
            # Alert if max > 3× p95
            if max_val > p95 * 3:
                alerts.append({
                    'type': 'max_spike',
                    'message': f'max ({max_val}ms) > 3× p95 ({p95}ms)',
                    'severity': 'WARN'
                })
        
        return {
            'has_alerts': len(alerts) > 0,
            'alerts': alerts
        }

def measure_e2e_latency(url: str, payload: Dict, timeout: int = 5) -> Tuple[float, bool, Optional[float]]:
    """
    Measure end-to-end latency from client perspective
    Returns: (e2e_latency_ms, success, internal_latency_ms)
    """
    start = time.time()
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        e2e_latency = (time.time() - start) * 1000
        
        # Try to extract internal timing from response headers if available
        internal_latency = None
        if 'X-Internal-Time' in response.headers:
            internal_latency = float(response.headers['X-Internal-Time'])
        
        success = response.status_code == 200
        return e2e_latency, success, internal_latency
    except Exception as e:
        e2e_latency = (time.time() - start) * 1000
        logger.warning(f"Request failed: {e}")
        return e2e_latency, False, None

# Test Qdrant configuration
try:
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
except Exception as e:
    print(f'❌ Failed to connect to Qdrant: {e}')
    exit(1)

# Baseline performance test with enhanced metrics
print('\n📊 Running baseline test (100 requests)...')
baseline_e2e = LatencyMetrics(source="e2e")
baseline_internal = LatencyMetrics(source="internal")

for i in range(100):
    vector = [0.1] * 384
    e2e_ms, success, internal_ms = measure_e2e_latency(
        'http://localhost:6333/collections/context_embeddings/points/search',
        {'vector': vector, 'limit': 5}
    )
    
    if success:
        baseline_e2e.add(e2e_ms)
        if internal_ms:
            baseline_internal.add(internal_ms)

# Calculate baseline metrics
baseline_e2e_stats = baseline_e2e.calculate_percentiles()
baseline_internal_stats = baseline_internal.calculate_percentiles()
baseline_e2e_alerts = baseline_e2e.check_tail_alerts()

print(f'\n✅ Baseline Performance (E2E):')
print(f'   p50: {baseline_e2e_stats["p50_ms"]}ms')
print(f'   p95: {baseline_e2e_stats["p95_ms"]}ms')
print(f'   p99: {baseline_e2e_stats["p99_ms"]}ms')
print(f'   max: {baseline_e2e_stats["max_ms"]}ms')

if baseline_internal_stats['count'] > 0:
    print(f'\n✅ Baseline Performance (Internal):')
    print(f'   p50: {baseline_internal_stats["p50_ms"]}ms')
    print(f'   p95: {baseline_internal_stats["p95_ms"]}ms')
    print(f'   p99: {baseline_internal_stats["p99_ms"]}ms')
    print(f'   max: {baseline_internal_stats["max_ms"]}ms')

if baseline_e2e_alerts['has_alerts']:
    print(f'\n⚠️ Baseline Tail Latency Alerts:')
    for alert in baseline_e2e_alerts['alerts']:
        print(f'   {alert["severity"]}: {alert["message"]}')

# Run enhanced burn-in cycles
print('\n📊 Running burn-in cycles with enhanced metrics...')
stable_cycles = 0
results = []
all_tail_alerts = []

for cycle in range(1, 6):
    print(f'\nCycle {cycle}:', end=' ')
    
    # Initialize metrics for this cycle
    cycle_e2e = LatencyMetrics(source="e2e")
    cycle_internal = LatencyMetrics(source="internal")
    errors = 0
    
    # Different QPS per cycle
    qps = 50 if cycle % 3 == 0 else 20 if cycle % 2 == 0 else 10
    
    for i in range(50):
        vector = [0.1 * (i % 10)] * 384
        e2e_ms, success, internal_ms = measure_e2e_latency(
            'http://localhost:6333/collections/context_embeddings/points/search',
            {'vector': vector, 'limit': 5}
        )
        
        if success:
            cycle_e2e.add(e2e_ms)
            if internal_ms:
                cycle_internal.add(internal_ms)
        else:
            errors += 1
        
        time.sleep(1/qps)
    
    # Calculate cycle metrics
    e2e_stats = cycle_e2e.calculate_percentiles()
    internal_stats = cycle_internal.calculate_percentiles()
    tail_alerts = cycle_e2e.check_tail_alerts()
    
    # Success criteria: p95 < 10ms, no errors, no critical tail alerts
    cycle_pass = e2e_stats['p95_ms'] < 10 and errors == 0
    
    if cycle_pass:
        stable_cycles += 1
        status = 'PASS'
        print(f'✅ PASS ({qps} QPS, p95={e2e_stats["p95_ms"]}ms, p99={e2e_stats["p99_ms"]}ms, max={e2e_stats["max_ms"]}ms)')
    else:
        stable_cycles = 0
        status = 'FAIL'
        print(f'❌ FAIL ({qps} QPS, p95={e2e_stats["p95_ms"]}ms, p99={e2e_stats["p99_ms"]}ms, max={e2e_stats["max_ms"]}ms, errors={errors})')
    
    if tail_alerts['has_alerts']:
        print(f'   ⚠️ Tail alerts: {len(tail_alerts["alerts"])} warnings')
        for alert in tail_alerts['alerts']:
            logger.warning(f'   Cycle {cycle}: {alert["message"]}')
        all_tail_alerts.extend(tail_alerts['alerts'])
    
    # Build cycle result with enhanced metrics
    cycle_result = {
        'cycle': cycle,
        'qps': qps,
        'latency': {
            'e2e': e2e_stats,
            'internal': internal_stats if internal_stats['count'] > 0 else None
        },
        'errors': errors,
        'status': status,
        'tail_alerts': tail_alerts
    }
    results.append(cycle_result)

print(f'\n{"="*60}')

# Final report with enhanced metrics
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

if all_tail_alerts:
    print(f'\n⚠️ Total tail latency warnings: {len(all_tail_alerts)}')

# Save enhanced report
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
        'e2e': baseline_e2e_stats,
        'internal': baseline_internal_stats if baseline_internal_stats['count'] > 0 else None,
        'tail_alerts': baseline_e2e_alerts
    },
    'cycles': results,
    'stable_cycles': stable_cycles,
    'total_tail_alerts': len(all_tail_alerts),
    'timestamp': datetime.now().isoformat(),
    'tag': tag,
    'metrics_version': '2.0.0'  # Indicates enhanced metrics format
}

# Save to burnin-results directory
report_path = '/workspaces/agent-context-template/context-store/burnin-results/server-burnin-enhanced.json'
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)

print(f'\n📊 Enhanced report saved: {report_path}')
print('='*60)