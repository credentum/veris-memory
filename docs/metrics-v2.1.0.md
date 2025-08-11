# Context Store Metrics Documentation v2.1.0

## Overview

This document defines the enhanced metrics contract for Context Store Sprint 9, adding internal timing breakdown and high-QPS capacity testing capabilities.

## Metrics Version

**Current Version:** 2.1.0

**Changes from v2.0.0:**
- ✅ Added internal timing breakdown (API, DB, processing)
- ✅ Enhanced high-QPS capacity testing support  
- ✅ Extended alert thresholds for production workloads
- ✅ Capacity planning metrics and recommendations

## Enhanced Latency Metrics

### Timing Sources

All latency metrics include detailed source attribution:

- **`e2e`** (End-to-End): Client-measured latency from request → response
  - Measured by: Test clients, load testing tools
  - Includes: Network + queuing + processing + serialization
  - Units: milliseconds (ms)

- **`internal`** (Internal): Server-side processing time breakdown
  - Measured by: Server instrumentation, middleware timers
  - Components: API layer + DB queries + processing time
  - Units: milliseconds (ms)
  - Export: `X-Internal-Time` header + breakdown data

### Internal Timing Breakdown

**New in v2.1.0:** Detailed internal latency components:

```json
{
  "internal_breakdown": {
    "api": {
      "p50": 0.2,
      "p95": 0.4, 
      "p99": 0.6,
      "max": 0.8
    },
    "db": {
      "p50": 1.2,
      "p95": 2.1,
      "p99": 3.4,
      "max": 4.2
    },
    "processing": {
      "p50": 0.3,
      "p95": 0.5,
      "p99": 0.7,
      "max": 0.9
    },
    "samples": 250
  }
}
```

**Component Definitions:**
- **`api`**: Request parsing, response serialization, HTTP overhead
- **`db`**: Qdrant vector search + Neo4j graph queries (if applicable)  
- **`processing`**: Business logic, data transformation, filtering

### Enhanced Percentile Metrics

Extended percentile coverage for high-load scenarios:

| Metric | Description | Production Threshold | Critical Threshold |
|--------|-------------|---------------------|-------------------|
| `p50_ms` | 50th percentile (median) | < 5ms | < 10ms |
| `p95_ms` | 95th percentile | < 10ms | < 20ms |
| `p99_ms` | 99th percentile | < 15ms | < 30ms |
| `max_ms` | Maximum observed latency | < 25ms | < 50ms |

### Enhanced Tail Latency Alerts

**v2.1.0 Alert Thresholds:**

1. **P99 Spike Alert**
   - **Condition**: `p99 > 1.5 × p95`
   - **Severity**: WARN
   - **Example**: "p99 (4.5ms) > 1.5× p95 (2.8ms)"

2. **Max Spike Alert**
   - **Condition**: `max > 3.0 × p95`
   - **Severity**: WARN
   - **Example**: "max (12.1ms) > 3× p95 (3.2ms)"

3. **High Latency Alert** *(New)*
   - **Condition**: `p95 > 20ms`
   - **Severity**: CRITICAL
   - **Example**: "p95 (23.4ms) exceeds 20ms production threshold"

## High-QPS Testing Schema

### Load Test Configuration

```json
{
  "load_test": {
    "target_qps": 100,
    "actual_qps": 98.7,
    "duration_seconds": 60.0,
    "completed_requests": 5922,
    "errors": 0,
    "error_rate_percent": 0.0
  }
}
```

### Capacity Analysis Schema

```json
{
  "capacity_analysis": {
    "tested_qps_range": "75-150",
    "saturation_point_qps": 120,
    "safe_operating_qps": 96,
    "max_tested_qps": 150,
    "recommendations": {
      "production_qps": 72,
      "alert_threshold_qps": 96,
      "scale_trigger_qps": 84
    }
  }
}
```

## v2.1.0 Report Schema

### Enhanced Baseline Report

```json
{
  "baseline": {
    "target_qps": 10,
    "actual_qps": 9.8,
    "duration_seconds": 10.0,
    "completed_requests": 98,
    "errors": 0,
    "error_rate_percent": 0.0,
    "latency": {
      "e2e": {
        "source": "e2e",
        "p50_ms": 1.2,
        "p95_ms": 1.8,
        "p99_ms": 2.4,
        "max_ms": 2.6,
        "count": 98
      },
      "internal": {
        "source": "internal",
        "p50_ms": 0.9,
        "p95_ms": 1.3,
        "p99_ms": 1.7,
        "max_ms": 1.9,
        "count": 98
      }
    },
    "internal_breakdown": {
      "api": {"p50": 0.2, "p95": 0.3, "p99": 0.4, "max": 0.5},
      "db": {"p50": 0.6, "p95": 0.9, "p99": 1.2, "max": 1.3},
      "processing": {"p50": 0.1, "p95": 0.1, "p99": 0.1, "max": 0.1},
      "samples": 98
    },
    "tail_alerts": {
      "has_alerts": false,
      "alerts": []
    }
  }
}
```

### High-QPS Test Cycle Schema

```json
{
  "high_qps_tests": [
    {
      "target_qps": 100,
      "actual_qps": 98.7,
      "duration_seconds": 60.0,
      "completed_requests": 5922,
      "errors": 0,
      "error_rate_percent": 0.0,
      "latency": {
        "e2e": {
          "source": "e2e",
          "p50_ms": 2.1,
          "p95_ms": 3.4,
          "p99_ms": 4.8,
          "max_ms": 6.2,
          "count": 5922
        },
        "internal": {
          "source": "internal", 
          "p50_ms": 1.6,
          "p95_ms": 2.6,
          "p99_ms": 3.7,
          "max_ms": 4.8,
          "count": 5922
        }
      },
      "internal_breakdown": {
        "api": {"p50": 0.3, "p95": 0.5, "p99": 0.7, "max": 0.9},
        "db": {"p50": 1.1, "p95": 1.8, "p99": 2.6, "max": 3.4},
        "processing": {"p50": 0.2, "p95": 0.3, "p99": 0.4, "max": 0.5},
        "samples": 5922
      },
      "tail_alerts": {
        "has_alerts": true,
        "alerts": [
          {
            "type": "p99_spike",
            "message": "p99 (4.8ms) > 1.5× p95 (3.4ms)",
            "severity": "WARN"
          }
        ]
      }
    }
  ]
}
```

## Capacity Planning Metrics

### Saturation Detection

**Saturation Indicators:**
- **Error Rate**: `error_rate_percent > 0.5%`
- **Latency Drift**: `p95_current > baseline_p95 * 1.2` (20% increase)
- **Alert Threshold**: `p95 > 20ms` (production concern)

### Operational Recommendations

**Safe Operating Zones:**
- **Production QPS**: 60% of saturation point
- **Alert Threshold**: 80% of saturation point  
- **Scale Trigger**: 70% of saturation point

```json
{
  "recommendations": {
    "production_qps": 72,
    "alert_threshold_qps": 96, 
    "scale_trigger_qps": 84,
    "max_burst_qps": 120,
    "scale_cooldown_seconds": 300
  }
}
```

## Migration from v2.0.0

### Breaking Changes

**None** - Full backward compatibility maintained.

### New Fields

**Added to all reports:**
- `internal_breakdown` - Internal timing component analysis
- `capacity_analysis` - High-QPS testing results and recommendations  
- Enhanced alert types (`high_latency` severity)

### Legacy Support

Reports without internal timing data are handled gracefully:
- `internal_breakdown` returns `null` if no internal data available
- `latency.internal` remains optional
- All v2.0.0 report formats continue to validate

## Tools and Usage

### High-QPS Testing Script

```bash
# Run Sprint 9 high-QPS capacity test
./scripts/burnin/server_burnin_high_qps.py

# Test specific QPS range
python3 server_burnin_high_qps.py --qps-range 50,75,100
```

### Report Analysis

```bash
# Extract capacity recommendations
jq '.capacity_analysis.recommendations' sprint9-high-qps-report.json

# Compare internal vs e2e timing
jq '.baseline.internal_breakdown' sprint9-high-qps-report.json
```

## Integration Examples

### Monitoring Integration

```python
# Export high-QPS metrics to monitoring
def export_capacity_metrics(report):
    metrics = {
        'saturation_qps': report['capacity_analysis']['saturation_point_qps'],
        'safe_qps': report['capacity_analysis']['safe_operating_qps'],
        'internal_api_p95': report['baseline']['internal_breakdown']['api']['p95'],
        'internal_db_p95': report['baseline']['internal_breakdown']['db']['p95']
    }
    return metrics
```

### Alert Configuration

```yaml
# Prometheus alerting rules for v2.1.0 metrics
groups:
  - name: context_store_capacity
    rules:
      - alert: HighLatency
        expr: context_store_p95_latency > 20
        labels:
          severity: critical
        annotations:
          summary: "Context Store p95 latency exceeds production threshold"
      
      - alert: ApproachingSaturation  
        expr: context_store_qps > context_store_safe_qps
        labels:
          severity: warning
        annotations:
          summary: "Context Store QPS approaching safe operating limit"
```

## Performance Benchmarks

### Reference Performance (Hetzner Server)

| QPS | P95 Latency | P99 Latency | Error Rate | Status |
|-----|-------------|-------------|------------|---------|
| 10  | 1.8ms       | 2.4ms       | 0.0%       | ✅ Optimal |
| 50  | 2.2ms       | 2.8ms       | 0.0%       | ✅ Good |
| 75  | 3.1ms       | 4.2ms       | 0.0%       | ✅ Acceptable |
| 100 | 4.5ms       | 6.8ms       | 0.1%       | ⚠️ Monitor |
| 150 | 8.2ms       | 15.3ms      | 0.8%       | ❌ Saturated |

### Internal Timing Breakdown (100 QPS)

- **API Layer**: 0.5ms p95 (15% of total)
- **Database**: 1.8ms p95 (60% of total) 
- **Processing**: 0.3ms p95 (10% of total)
- **Network/Other**: 15% of total latency

## References

- [Sprint 9 Specification](../schemas/sprints/sprint-9-internal-timing-high-qps.yaml)
- [High-QPS Testing Guide](testing/HIGH-QPS-TESTING-GUIDE.md)
- [Capacity Planning Guidelines](CAPACITY-PLANNING.md)
- [v2.0.0 Migration Guide](METRICS-V2-MIGRATION.md)