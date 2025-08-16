# Veris Sentinel - Autonomous Monitoring Agent

## Overview

Veris Sentinel is an autonomous monitor/test/report agent for Veris Memory that provides continuous validation of system health, functionality, and performance. It implements the specification from Issue #46 with comprehensive testing capabilities.

## Features

### 🔍 Comprehensive Monitoring Checks

| Check ID | Description | Purpose |
|----------|-------------|---------|
| **S1-probes** | Health endpoint validation | Verify /health/live and /health/ready respond correctly |
| **S2-golden-fact-recall** | Functional fact storage/retrieval | Test core functionality with known Q&A pairs |
| **S4-metrics-wiring** | Monitoring infrastructure | Validate dashboard and analytics endpoints |
| **S5-security-negatives** | RBAC and security validation | Test authentication and authorization controls |
| **S7-config-parity** | Configuration drift detection | Verify expected service configuration |
| **S8-capacity-smoke** | Performance burst testing | Test system under concurrent load |

### 🚀 Autonomous Operation

- **Scheduled Monitoring**: Configurable cadence (default: 60 seconds)
- **Concurrent Execution**: Parallel check execution with configurable limits
- **Smart Jitter**: Prevents thundering herd with randomized timing
- **Timeout Protection**: Per-check and cycle-level timeout enforcement
- **Graceful Degradation**: Continues operation despite individual check failures

### 📊 Comprehensive Reporting

- **Real-time API**: HTTP endpoints for status, metrics, and reports
- **Persistent Storage**: SQLite database for historical data retention
- **Ring Buffers**: In-memory storage for recent failures and reports
- **Prometheus Metrics**: Standard metrics format for monitoring integration
- **Structured Logging**: JSON-formatted logs for analysis

### 🔔 Alerting & Integration

- **Webhook Alerts**: Slack/Teams integration for critical failures
- **GitHub Integration**: Automated issue creation for persistent failures
- **Multi-level Alerts**: Critical, high, warning, and info levels
- **Deduplication**: Intelligent alert suppression to prevent noise

## Quick Start

### 1. Deploy Sentinel

```bash
# Deploy alongside existing Veris Memory
docker-compose -f docker-compose.sentinel.yml up -d
```

### 2. Check Status

```bash
# View real-time status
curl http://localhost:9090/status

# Trigger immediate monitoring cycle
curl -X POST http://localhost:9090/run

# View recent reports
curl http://localhost:9090/report?n=5
```

### 3. Monitor Logs

```bash
# Follow sentinel logs
docker logs veris-sentinel -f

# Check health
docker ps | grep sentinel
```

## Configuration

### Environment Variables

```bash
# Target configuration
TARGET_BASE_URL=http://veris-memory-dev-context-store-1:8000
REDIS_URL=redis://veris-memory-dev-redis-1:6379
QDRANT_URL=http://veris-memory-dev-qdrant-1:6333
NEO4J_BOLT=bolt://veris-memory-dev-neo4j-1:7687

# Scheduling
SCHEDULE_CADENCE_SEC=60          # Monitoring frequency
MAX_JITTER_PCT=20                # Timing randomization
PER_CHECK_TIMEOUT_SEC=10         # Individual check timeout
CYCLE_BUDGET_SEC=45              # Total cycle timeout
MAX_PARALLEL_CHECKS=4            # Concurrent check limit

# Alerting
ALERT_WEBHOOK=https://hooks.slack.com/services/xxx/yyy/zzz
GITHUB_REPO=credentum/veris-memory
GITHUB_TOKEN_FILE=/run/secrets/github_token

# API
SENTINEL_API_PORT=9090
LOG_LEVEL=INFO
```

### Security Configuration

```bash
# Authentication secrets (mounted as files)
NEO4J_PASS_FILE=/run/secrets/neo4j_ro_password
JWT_ADMIN_FILE=/run/secrets/jwt_admin
JWT_READER_FILE=/run/secrets/jwt_reader

# TLS certificates (optional)
CLIENT_TLS_CERT=/run/certs/client.crt
CLIENT_TLS_KEY=/run/certs/client.key
CLIENT_TLS_CA=/run/certs/ca.crt
```

## API Endpoints

### GET /status

Returns current sentinel status and last cycle summary.

```json
{
  "running": true,
  "last_cycle": {
    "cycle_id": "a1b2c3d4",
    "timestamp": "2023-01-01T12:00:00Z",
    "total_checks": 6,
    "passed_checks": 5,
    "failed_checks": 1,
    "cycle_duration_ms": 2450
  },
  "total_cycles": 42,
  "failure_count": 3
}
```

### POST /run

Triggers immediate monitoring cycle.

```json
{
  "success": true,
  "cycle_report": {
    "cycle_id": "x1y2z3",
    "results": [...]
  }
}
```

### GET /checks

Lists available monitoring checks.

```json
{
  "checks": {
    "S1-probes": {
      "description": "Health endpoint validation",
      "enabled": true
    },
    "S2-golden-fact-recall": {
      "description": "Functional fact storage/retrieval",
      "enabled": true
    }
  }
}
```

### GET /metrics

Prometheus-style metrics endpoint.

```
# Veris Sentinel Metrics
sentinel_checks_total 6
sentinel_checks_passed 5
sentinel_checks_failed 1
sentinel_cycle_duration_ms 2450
sentinel_failure_buffer_size 3
sentinel_running 1
```

### GET /report?n=10

Returns last N cycle reports with detailed results.

## Check Details

### S1: Health Probes

Tests basic system liveness and readiness:

- **Liveness**: `/health/live` endpoint responds with status "alive"
- **Readiness**: `/health/ready` endpoint shows all components healthy
- **Component Validation**: Qdrant, Neo4j, Redis status verification

**Success Criteria**: All endpoints respond correctly, components healthy

### S2: Golden Fact Recall

Tests core functionality with known question/answer pairs:

- **Fact Storage**: Store test facts via `/api/store_context`
- **Natural Questions**: Retrieve with human-like queries
- **Precision Validation**: Verify correct facts appear in top results

**Test Dataset**:
- Name: "Matt" → "What's my name?"
- Food: "spicy" → "What kind of food do I like?"
- Location: "San Francisco" → "Where do I live?"

**Success Criteria**: P@1 ≥ 1.0 (all queries return correct fact first)

### S4: Metrics Wiring

Validates monitoring infrastructure:

- **Dashboard Access**: `/api/dashboard` endpoint responds
- **Analytics Available**: `/api/dashboard/analytics` functional
- **Required Fields**: System, services, timestamp present

**Success Criteria**: All monitoring endpoints accessible, data structured correctly

### S5: Security Negatives

Tests authentication and authorization:

- **Reader Permissions**: Can retrieve but not store contexts
- **Invalid Tokens**: Properly rejected with 401/403
- **Admin Endpoints**: Protected from unauthorized access

**Success Criteria**: Proper security responses, no unauthorized access

### S7: Configuration Parity

Detects configuration drift:

- **Expected Services**: Qdrant, Neo4j, Redis present in dashboard
- **Feature Availability**: Analytics endpoints indicate Phase 2 deployment
- **Service Health**: All required components operational

**Success Criteria**: Configuration matches expected deployment state

### S8: Capacity Smoke

Performance under load:

- **Concurrent Requests**: 20 simultaneous health checks
- **Response Times**: P95 < 300ms, P99 < 500ms
- **Error Rates**: < 0.5% failures under load

**Success Criteria**: System performs well under brief concurrent load

## Alerting Rules

### Critical Alerts (Immediate notification)

- **S1-probes fail**: Core system health issues
- **S6-backup-restore-parity fail**: Data protection concerns
- **Overall error rate > 20%**: System-wide problems

### High Priority Alerts (5-minute delay)

- **S2-golden-fact-recall P@1 < 1.0**: Core functionality degraded
- **Performance spike > 1.5x baseline**: Unusual load patterns

### Warning Alerts (15-minute delay)

- **Any P99 latency spike**: Performance concerns
- **Individual check failures**: Component-specific issues

## Data Retention

### Ring Buffers (In-Memory)

- **Failures**: 200 most recent failures
- **Reports**: 50 most recent cycle reports  
- **Traces**: 500 most recent execution traces

### SQLite Database (Persistent)

- **Check Results**: Individual check outcomes
- **Cycle Reports**: Complete monitoring cycles
- **Retention**: 7 days of detailed history
- **Location**: `/var/lib/sentinel/sentinel.db`

## Security Model

### Principle of Least Privilege

- **User**: Non-root user (UID 10001)
- **Capabilities**: All capabilities dropped
- **Filesystem**: Read-only root filesystem
- **Network**: Internal Docker network only

### Authentication

- **Scoped JWT Tokens**: Admin and reader permissions
- **mTLS**: Optional client certificate authentication
- **Secrets**: File-based secret mounting

### Network Security

- **Internal Network**: No external connectivity except webhooks/GitHub
- **Localhost Binding**: API server bound to localhost only
- **Firewall**: Integrated with host firewall rules

## Troubleshooting

### Common Issues

1. **Sentinel not starting**
   ```bash
   # Check logs
   docker logs veris-sentinel
   
   # Verify network connectivity
   docker network ls | grep veris
   ```

2. **Checks failing**
   ```bash
   # Test individual check
   curl http://localhost:9090/run
   
   # Check target service health
   curl http://localhost:8000/health/live
   ```

3. **High memory usage**
   ```bash
   # Check container stats
   docker stats veris-sentinel
   
   # Review ring buffer sizes in config
   ```

### Debug Mode

```bash
# Enable debug logging
docker-compose -f docker-compose.sentinel.yml down
docker-compose -f docker-compose.sentinel.yml up -d \
  -e LOG_LEVEL=DEBUG
```

### Manual Testing

```bash
# Run test suite
python scripts/test-sentinel.py

# Test specific functionality
python -c "
import asyncio
from src.monitoring.veris_sentinel import *
config = SentinelConfig(target_base_url='http://localhost:8000')
asyncio.run(VerisHealthProbe(config).run_check())
"
```

## Performance Characteristics

### Resource Usage

- **Memory**: 256MB reserved, 512MB limit
- **CPU**: 0.25 cores reserved, 0.5 cores limit
- **Disk**: < 100MB for database and logs
- **Network**: Minimal outbound traffic

### Timing

- **Cycle Duration**: 2-5 seconds typical
- **Check Latency**: 10-500ms per check
- **Startup Time**: < 30 seconds
- **Recovery Time**: < 60 seconds after failures

### Scalability

- **Concurrent Checks**: 4 parallel (configurable)
- **Check Frequency**: 60-second default (configurable)
- **History Retention**: 7 days persistent, 500 traces in memory
- **Alert Rate**: Deduplicated, configurable cooldowns

## Integration Examples

### Slack Alerts

```bash
export ALERT_WEBHOOK="https://hooks.slack.com/services/T00/B00/XXX"
```

### Prometheus Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'veris-sentinel'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### GitHub Issues

```bash
export GITHUB_REPO="credentum/veris-memory"
export GITHUB_TOKEN_FILE="/run/secrets/github_token"
```

## Development

### Adding New Checks

1. Create check class inheriting base pattern
2. Implement `run_check()` method returning `CheckResult`
3. Add to `SentinelRunner.checks` dictionary
4. Update documentation and tests

### Testing Framework

```bash
# Run test suite
python scripts/test-sentinel.py

# Unit tests
pytest tests/monitoring/test_sentinel.py

# Integration tests
pytest tests/integration/test_sentinel_integration.py
```

The Veris Sentinel provides comprehensive, autonomous monitoring that ensures Veris Memory operates reliably in production environments.