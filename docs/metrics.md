# Context Store Metrics Documentation

## Overview

This document defines the metrics contract for the Context Store burn-in testing infrastructure, implementing Sprint 8 guardrails for timing source labeling and tail latency monitoring.

## Metrics Version

**Current Version:** 2.0.0

This version introduces enhanced metrics with timing source labels and tail latency visibility.

## Latency Metrics

### Timing Sources

All latency metrics include a `latency_source` field indicating where the measurement was taken:

- **`e2e`** (End-to-End): Client-measured latency from request initiation to response completion
  - Measured by: Test clients, burn-in scripts
  - Includes: Network overhead, queuing delays, processing time
  - Units: milliseconds (ms)

- **`internal`** (Internal): Server-side processing time only
  - Measured by: API middleware, service components
  - Includes: Processing time only (excludes network)
  - Units: milliseconds (ms)
  - Header: `X-Internal-Time` (when available)

### Percentile Metrics

For each timing source, the following percentiles are captured:

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `p50_ms` | 50th percentile (median) | Baseline tracking |
| `p95_ms` | 95th percentile | < 10ms for cycle pass |
| `p99_ms` | 99th percentile | Tail latency monitoring |
| `max_ms` | Maximum observed latency | Spike detection |

### Tail Latency Alerts

Automated alerts are generated when tail latency thresholds are exceeded:

#### Alert Thresholds

1. **P99 Spike Alert**
   - **Condition**: `p99 > 1.5 × p95`
   - **Severity**: WARN
   - **Message**: "p99 (Xms) > 1.5× p95 (Yms)"

2. **Max Spike Alert**
   - **Condition**: `max > 3.0 × p95`
   - **Severity**: WARN
   - **Message**: "max (Xms) > 3× p95 (Yms)"

#### Alert Structure

```json
{
  "type": "p99_spike" | "max_spike",
  "message": "Human-readable description",
  "severity": "WARN"
}
```

## Report Schema

### Enhanced Cycle Report Format

```json
{
  "cycle": 1,
  "timestamp": "2025-08-11T18:52:29.298136",
  "qps": 20,
  "latency": {
    "e2e": {
      "source": "e2e",
      "p50_ms": 1.2,
      "p95_ms": 2.4,
      "p99_ms": 3.1,
      "max_ms": 4.5,
      "count": 50
    },
    "internal": {
      "source": "internal", 
      "p50_ms": 0.8,
      "p95_ms": 1.9,
      "p99_ms": 2.4,
      "max_ms": 3.2,
      "count": 50
    }
  },
  "errors": 0,
  "status": "PASS",
  "tail_alerts": {
    "has_alerts": false,
    "alerts": []
  }
}
```

### Baseline Report Format

```json
{
  "baseline": {
    "e2e": {
      "source": "e2e",
      "p50_ms": 1.1,
      "p95_ms": 1.4,
      "p99_ms": 2.2,
      "max_ms": 3.8
    },
    "internal": {
      "source": "internal",
      "p50_ms": 0.7,
      "p95_ms": 1.1,
      "p99_ms": 1.8,
      "max_ms": 2.9
    },
    "tail_alerts": {
      "has_alerts": true,
      "alerts": [
        {
          "type": "p99_spike",
          "message": "p99 (2.2ms) > 1.5× p95 (1.4ms)",
          "severity": "WARN"
        }
      ]
    }
  }
}
```

## Measurement Points

### Client-Side (E2E)
- **Location**: Burn-in test scripts
- **Scope**: Full request-response cycle
- **Implementation**: `time.time()` before/after HTTP request

### Server-Side (Internal)
- **Location**: API middleware, component timers
- **Scope**: Processing time only
- **Implementation**: Server-side timing hooks
- **Transport**: `X-Internal-Time` HTTP header

## Tools and Scripts

### Enhanced Scripts

- `server_burnin_enhanced.py`: Basic burn-in with Sprint 8 metrics
- `comprehensive_burnin.py`: Full burn-in suite with enhanced metrics

### Usage Examples

```bash
# Run enhanced burn-in test
./scripts/burnin/server_burnin_enhanced.py

# Run comprehensive burn-in with full metrics
./scripts/burnin/comprehensive_burnin.py
```

### Report Locations

- **Enhanced Reports**: `burnin-results/server-burnin-enhanced.json`
- **Comprehensive Reports**: `burnin-results/comprehensive/cycle-N.json`
- **Baselines**: `burnin-results/comprehensive/baseline.json`

## Success Criteria

### Cycle Pass Conditions

1. **E2E p95 < 10ms**: Primary performance threshold
2. **Zero errors**: No request failures
3. **Tail alerts**: Warnings logged but don't fail cycle

### Stability Requirements

- **5 consecutive passing cycles** required for burn-in success
- **Tail alerts** tracked but don't reset stability counter
- **Error rate = 0%** maintained across all cycles

## Integration

### GitHub Actions

Enhanced metrics are automatically captured in CI/CD pipelines:

```yaml
- name: Run Enhanced Burn-in
  run: |
    ./scripts/burnin/server_burnin_enhanced.py
    # Reports include timing source labels and tail metrics
```

### Monitoring Integration

Metrics can be exported to monitoring systems:

```bash
# Export metrics to monitoring
curl -X POST /metrics/export \
  -H "Content-Type: application/json" \
  -d @burnin-results/server-burnin-enhanced.json
```

## Migration Notes

### From Version 1.0.0

- **Breaking**: Latency metrics now nested under `latency.e2e` and `latency.internal`
- **Added**: `max_ms` field to all percentile reports
- **Added**: `latency_source` field for timing source identification
- **Added**: `tail_alerts` structure for automated alert tracking

### Backward Compatibility

Legacy reports without `latency_source` are assumed to be `"e2e"` measurements.

## Troubleshooting

### Missing Internal Metrics

If `latency.internal` is null, server-side timing is not implemented:

```json
{
  "latency": {
    "e2e": { ... },
    "internal": null
  }
}
```

**Solution**: Implement server-side timing hooks and `X-Internal-Time` header.

### High Tail Alerts

Frequent p99 or max spike alerts indicate:

- Garbage collection pauses
- Resource contention
- Network instability
- Query complexity variance

**Investigation**: Check system metrics during alert periods.

## References

- [Sprint 8 Specification](../schemas/sprints/sprint-8-guardrails-p99-e2e.yaml)
- [Burn-in Testing Guide](testing/BURNIN-TESTING-GUIDE.md)
- [SLO Monitoring](SLO_MONITORING.md)