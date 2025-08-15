# Veris 60-Second Production Smoke Test Suite

Daily 60s production smoke: health, write→read, paraphrase, index freshness.

## Overview

The Veris Smoke Test Suite (`veris_smoke_60s.py`) implements a comprehensive 60-second production smoke test that validates core functionality and SLOs. It replaces ad-hoc smoke testing with a standardized, schema-validated approach.

## Features

### 🎯 **Core Tests (SM-1 to SM-6)**
- **SM-1**: Health probe - API availability & dependency checks
- **SM-2**: Store → index → count - End-to-end ingestion validation  
- **SM-3**: Needle retrieval (semantic) - Precision@1 measurement
- **SM-4**: Paraphrase robustness (MQE-lite) - Semantic consistency
- **SM-5**: Index freshness - Sub-1s visibility validation
- **SM-6**: SLO spot-check - P95 latency, error rate, recovery metrics

### 🔧 **Optional Tests (SM-7)**
- **SM-7**: Graph RO sanity - Neo4j read-only validation (skips if unavailable)

### 📊 **SLO Monitoring**
- **P95 Latency**: ≤300ms
- **Error Rate**: ≤0.5%
- **Recovery**: ≥95% precision@1
- **Index Freshness**: ≤1s visibility

## Configuration

### Environment Variables
```bash
export NEO4J_PASSWORD="your_admin_password"
export NEO4J_RO_PASSWORD="readonly_secure_2024!"
```

### Default Configuration
```yaml
RERANKER_ENABLED: true
RERANK_TOP_K: 10
HYBRID_ALPHA: 0.7
HYBRID_BETA: 0.3
QDRANT_WAIT_WRITES: true
TIMEOUT_MS: 60000
NAMESPACE: "smoke"           # isolated, throwaway
TTL_SECONDS: 120             # self-cleans after run
```

## Usage

### Direct Execution
```bash
# Run Veris smoke test suite
python veris_smoke_60s.py --url http://localhost:8000 --env production

# Save report to file
python veris_smoke_60s.py --output smoke_report.json

# Run gate logic on existing report
python veris_smoke_60s.py --gate --output smoke_report.json
```

### Via Deploy Guard (Modern)
```bash
# Use Veris suite (default)
python deploy_guard.py --url http://localhost:8000 --env production

# Explicit Veris mode with output
python deploy_guard.py --veris --output veris_report.json

# Gate existing report
python deploy_guard.py --gate --output veris_report.json

# Legacy mode (backward compatibility)
python deploy_guard.py --legacy
```

### Pipeline Integration
```bash
# In CI/CD pipeline
python deploy_guard.py --veris --output deployment_report.json
if [ $? -eq 0 ]; then
    echo "✅ DEPLOYMENT GREEN - Smoke tests passed"
    # Proceed with deployment
else
    echo "❌ DEPLOYMENT RED - Smoke tests failed"
    exit 1
fi
```

## Report Schema

The suite generates JSON reports conforming to `veris_smoke_report.schema.json`:

```json
{
  "suite_id": "veris-smoke-60s",
  "run_id": "smoke-2025-08-08T14:02:11Z",
  "timestamp": "2025-08-08T14:02:11Z",
  "env": "production",
  "namespace": "smoke",
  "summary": {
    "overall_status": "pass",
    "p95_latency_ms": 187,
    "error_rate_pct": 0.0,
    "recovery_top1_pct": 100,
    "index_freshness_s": 0.4,
    "failed_tests": []
  },
  "thresholds": {
    "p95_latency_ms": 300,
    "error_rate_pct": 0.5,
    "recovery_top1_pct": 95,
    "index_freshness_s": 1
  },
  "tests": [...]
}
```

## Gate Logic

The gate logic determines deployment readiness:

```python
def gate_logic(report: Dict[str, Any]) -> int:
    s = report["summary"]
    t = report.get("thresholds", {})
    
    checks = [
        s["overall_status"] == "pass",
        s["p95_latency_ms"] <= t.get("p95_latency_ms", 300),
        s["error_rate_pct"] <= t.get("error_rate_pct", 0.5),
        s["recovery_top1_pct"] >= t.get("recovery_top1_pct", 95),
        s["index_freshness_s"] <= t.get("index_freshness_s", 1),
        len(s["failed_tests"]) == 0
    ]
    
    ok = all(checks)
    print("DEPLOY:", "GREEN" if ok else "RED")
    return 0 if ok else 1
```

## Test Details

### SM-1: Health Probe (5s timeout)
- **Purpose**: Validate API availability and core dependencies
- **Checks**: HTTP 200 from `/health`, Qdrant + Redis connectivity
- **Success Criteria**: `http_200 == true`, `deps_ok == ["qdrant","redis"]`

### SM-2: Store → Index → Count (8s timeout)
- **Purpose**: End-to-end ingestion pipeline validation
- **Process**: Store needle document with `wait=true`, verify count increase
- **Success Criteria**: `count_increases_by == 1`

### SM-3: Needle Retrieval (8s timeout)
- **Purpose**: Semantic search precision validation
- **Process**: Query "What are the benefits of microservices?" against stored needle
- **Success Criteria**: `precision_at_1 >= 1.0` (top result is smoke needle)

### SM-4: Paraphrase Robustness (8s timeout)
- **Purpose**: Semantic consistency across query variations
- **Process**: Test paraphrases of original query
- **Success Criteria**: `top_doc_is_smoke_needle == true`

### SM-5: Index Freshness (6s timeout)
- **Purpose**: Index visibility latency validation
- **Process**: Immediate re-query of stored needle
- **Success Criteria**: `visible_under_seconds <= 1`

### SM-6: SLO Spot-Check (4s timeout)
- **Purpose**: Aggregate SLO compliance validation
- **Process**: Analyze metrics from SM-1 through SM-5
- **Success Criteria**: All SLO thresholds met

### SM-7: Graph RO Sanity (5s timeout, optional)
- **Purpose**: Neo4j read-only access validation
- **Process**: Execute `RETURN 1 AS ok` via query_graph
- **Success Criteria**: `ro_read_ok == true` (skips if unavailable)

## Fail-Fast Behavior

The suite implements fail-fast logic:
1. **Hard Timeout**: 60-second suite-wide timeout
2. **Critical Test Failure**: Abort on any SM-1 through SM-6 failure
3. **Optional Test Failure**: SM-7 failures are logged but don't abort suite
4. **Early Termination**: Suite stops on first critical failure

## Self-Cleaning

The suite uses throwaway data to avoid residue:
- **Namespace**: `smoke` (isolated from production data)
- **TTL**: 120 seconds (auto-cleanup)  
- **Content**: Standardized test documents that self-identify

## Integration Examples

### GitHub Actions
```yaml
- name: Deploy Guard Smoke Test
  run: |
    python context-store/deploy_guard.py \
      --url ${{ env.CONTEXT_STORE_URL }} \
      --env ${{ env.ENVIRONMENT }} \
      --output smoke_report.json
    
    if [ $? -ne 0 ]; then
      echo "❌ Smoke tests failed - blocking deployment"
      cat smoke_report.json
      exit 1
    fi
```

### Docker Compose Healthcheck
```yaml
services:
  context-store:
    healthcheck:
      test: ["CMD", "python", "/app/deploy_guard.py", "--url", "http://localhost:8000"]
      interval: 300s
      timeout: 65s
      retries: 2
      start_period: 30s
```

### Kubernetes Readiness Probe
```yaml
readinessProbe:
  exec:
    command:
    - python
    - /app/deploy_guard.py
    - --url
    - http://localhost:8000
  initialDelaySeconds: 30
  periodSeconds: 300
  timeoutSeconds: 65
```

## Files

- **`veris_smoke_60s.py`**: Core smoke test suite implementation
- **`veris_smoke_report.schema.json`**: JSON schema for report validation
- **`veris_smoke_report_example.json`**: Example report showing all tests passing
- **`deploy_guard.py`**: Updated deploy guard with Veris integration
- **`VERIS_SMOKE_SUITE.md`**: This documentation

## Benefits

### 🎯 **Standardization**
- Consistent test structure across environments
- Schema-validated reports
- Predictable behavior and timing

### 🚀 **Production Ready**
- Comprehensive SLO validation
- Fail-fast for quick feedback
- Self-cleaning to avoid data pollution

### 🔧 **Integration Friendly**
- JSON output for automation
- Clear exit codes for CI/CD
- Flexible configuration options

### 📊 **Observability**
- Detailed metrics per test
- Performance regression detection
- Historical trend analysis capability

The Veris Smoke Test Suite provides production-grade validation in exactly 60 seconds, ensuring your Context Store deployment is healthy and meeting SLOs before serving traffic.