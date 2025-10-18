# Sprint 13 Monitoring Setup

**Version**: 1.0
**Last Updated**: 2025-10-18
**Sprint**: 13 - Critical Fixes and Enhancements

---

## Overview

This document describes monitoring setup for Sprint 13 features, including:

1. **Embedding Pipeline Health** - Track embedding generation success rates
2. **Storage Backend Utilization** - Monitor Qdrant, Neo4j, Redis usage
3. **API Performance** - Request latency, throughput, error rates
4. **Relationship Detection** - Auto-detection statistics
5. **Namespace Management** - Lock contention, namespace usage

---

## Table of Contents

1. [Metrics Overview](#metrics-overview)
2. [Prometheus Configuration](#prometheus-configuration)
3. [Grafana Dashboards](#grafana-dashboards)
4. [Alerting Rules](#alerting-rules)
5. [Health Endpoints](#health-endpoints)
6. [Log Monitoring](#log-monitoring)

---

## Metrics Overview

### Embedding Pipeline Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `embedding_generation_total` | Counter | Total embeddings generated | - |
| `embedding_generation_failures` | Counter | Failed embedding generations | >10/hour |
| `embedding_generation_duration_seconds` | Histogram | Time to generate embedding | p95 >1s |
| `embedding_service_available` | Gauge | Embedding service status (0/1) | 0 |
| `qdrant_collection_vectors_count` | Gauge | Total vectors in Qdrant | - |

**Example**:
```prometheus
# Embedding success rate (last 5m)
rate(embedding_generation_total[5m]) - rate(embedding_generation_failures[5m])

# P95 embedding generation time
histogram_quantile(0.95, embedding_generation_duration_seconds_bucket)
```

---

### Storage Backend Metrics

#### Qdrant Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `qdrant_vectors_count` | Gauge | Total vectors stored | - |
| `qdrant_disk_usage_bytes` | Gauge | Disk space used | >80% |
| `qdrant_memory_usage_bytes` | Gauge | Memory used | >2GB |
| `qdrant_search_duration_seconds` | Histogram | Search latency | p95 >500ms |

#### Neo4j Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `neo4j_context_nodes_total` | Gauge | Total Context nodes | - |
| `neo4j_relationships_total` | Gauge | Total relationships | - |
| `neo4j_query_duration_seconds` | Histogram | Query latency | p95 >300ms |
| `neo4j_disk_usage_bytes` | Gauge | Disk space used | >80% |

#### Redis Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `redis_memory_usage_bytes` | Gauge | Memory used | >1GB |
| `redis_keys_total` | Gauge | Total keys | - |
| `redis_keys_without_ttl` | Gauge | Keys without expiration | >100 |
| `redis_evictions_total` | Counter | Evicted keys | >0 |

---

### API Performance Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `http_requests_total` | Counter | Total HTTP requests | - |
| `http_requests_duration_seconds` | Histogram | Request latency | p95 >2s |
| `http_requests_errors_total` | Counter | Failed requests | >5/min |
| `http_requests_in_flight` | Gauge | Active requests | >50 |

**By Endpoint**:
```prometheus
# Store context latency
http_requests_duration_seconds{endpoint="/tools/store_context"}

# Retrieve context error rate
rate(http_requests_errors_total{endpoint="/tools/retrieve_context"}[5m])
```

---

### Sprint 13 Specific Metrics

#### Relationship Detection

| Metric | Type | Description |
|--------|------|-------------|
| `relationship_detections_total` | Counter | Total relationships detected |
| `relationship_detections_by_type` | Counter | Detections by relationship type |
| `relationship_creation_failures` | Counter | Failed relationship creations |
| `relationship_detection_duration_seconds` | Histogram | Detection latency |

**Example**:
```prometheus
# Relationships detected per minute
rate(relationship_detections_total[1m])

# Detection by type
sum(relationship_detections_by_type) by (type)
```

#### Namespace Management

| Metric | Type | Description |
|--------|------|-------------|
| `namespace_locks_acquired_total` | Counter | Locks acquired |
| `namespace_locks_failed_total` | Counter | Failed lock acquisitions |
| `namespace_locks_active` | Gauge | Currently held locks |
| `namespace_contexts_total` | Gauge | Contexts per namespace |

#### Memory Management

| Metric | Type | Description |
|--------|------|-------------|
| `redis_ttl_set_total` | Counter | TTLs set on keys |
| `redis_cleanup_keys_checked` | Counter | Keys checked in cleanup |
| `redis_sync_events_synced` | Counter | Events synced to Neo4j |
| `redis_sync_failures_total` | Counter | Sync failures |

---

## Prometheus Configuration

### 1. Install Prometheus

```bash
# Docker Compose addition
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

volumes:
  prometheus_data:
```

### 2. Prometheus Configuration File

**File**: `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Scrape configs
scrape_configs:
  # Veris Memory MCP Server
  - job_name: 'veris-memory-mcp'
    static_configs:
      - targets: ['veris-memory-mcp:8000']
    metrics_path: '/metrics'

  # Qdrant
  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']
    metrics_path: '/metrics'

  # Neo4j
  - job_name: 'neo4j'
    static_configs:
      - targets: ['neo4j:2004']

  # Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

# Recording rules
rule_files:
  - '/etc/prometheus/rules/*.yml'
```

### 3. Prometheus Recording Rules

**File**: `monitoring/rules/sprint_13.yml`

```yaml
groups:
  - name: sprint_13_metrics
    interval: 30s
    rules:
      # Embedding success rate
      - record: embedding:success_rate:5m
        expr: |
          (
            rate(embedding_generation_total[5m]) -
            rate(embedding_generation_failures[5m])
          ) / rate(embedding_generation_total[5m])

      # Relationship detection rate
      - record: relationships:detection_rate:1m
        expr: rate(relationship_detections_total[1m])

      # API error rate
      - record: http:error_rate:5m
        expr: |
          rate(http_requests_errors_total[5m]) /
          rate(http_requests_total[5m])

      # Storage utilization
      - record: storage:disk_usage:percent
        expr: |
          (qdrant_disk_usage_bytes + neo4j_disk_usage_bytes) /
          (qdrant_disk_total_bytes + neo4j_disk_total_bytes) * 100
```

---

## Grafana Dashboards

### 1. Install Grafana

```bash
# Docker Compose addition
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false

volumes:
  grafana_data:
```

### 2. Datasource Configuration

**File**: `monitoring/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### 3. Sprint 13 Dashboard

**File**: `monitoring/dashboards/sprint_13.json`

```json
{
  "dashboard": {
    "title": "Sprint 13 - Veris Memory Overview",
    "panels": [
      {
        "title": "Embedding Pipeline Health",
        "type": "graph",
        "targets": [
          {
            "expr": "embedding:success_rate:5m",
            "legendFormat": "Success Rate"
          },
          {
            "expr": "embedding_service_available",
            "legendFormat": "Service Available"
          }
        ]
      },
      {
        "title": "Embedding Generation Time (P95)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, embedding_generation_duration_seconds_bucket)",
            "legendFormat": "P95 Latency"
          }
        ]
      },
      {
        "title": "Relationship Detection Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "relationships:detection_rate:1m",
            "legendFormat": "Detections/min"
          },
          {
            "expr": "sum(rate(relationship_detections_by_type[1m])) by (type)",
            "legendFormat": "{{type}}"
          }
        ]
      },
      {
        "title": "Storage Backend Health",
        "type": "stat",
        "targets": [
          {
            "expr": "qdrant_vectors_count",
            "legendFormat": "Qdrant Vectors"
          },
          {
            "expr": "neo4j_context_nodes_total",
            "legendFormat": "Neo4j Contexts"
          },
          {
            "expr": "redis_keys_total",
            "legendFormat": "Redis Keys"
          }
        ]
      },
      {
        "title": "API Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_requests_duration_seconds_bucket)",
            "legendFormat": "P95 Latency"
          },
          {
            "expr": "http:error_rate:5m",
            "legendFormat": "Error Rate"
          }
        ]
      },
      {
        "title": "Namespace Lock Contention",
        "type": "graph",
        "targets": [
          {
            "expr": "namespace_locks_active",
            "legendFormat": "Active Locks"
          },
          {
            "expr": "rate(namespace_locks_failed_total[1m])",
            "legendFormat": "Failed Acquisitions/min"
          }
        ]
      },
      {
        "title": "Redis Memory & TTL Management",
        "type": "graph",
        "targets": [
          {
            "expr": "redis_memory_usage_bytes / 1024 / 1024",
            "legendFormat": "Memory Usage (MB)"
          },
          {
            "expr": "redis_keys_without_ttl",
            "legendFormat": "Keys Without TTL"
          }
        ]
      },
      {
        "title": "Redis-Neo4j Sync Status",
        "type": "stat",
        "targets": [
          {
            "expr": "increase(redis_sync_events_synced[1h])",
            "legendFormat": "Events Synced (1h)"
          },
          {
            "expr": "redis_sync_failures_total",
            "legendFormat": "Total Failures"
          }
        ]
      }
    ]
  }
}
```

---

## Alerting Rules

### Alertmanager Configuration

**File**: `monitoring/alertmanager.yml`

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@example.com'
  smtp_auth_username: 'alerts@example.com'
  smtp_auth_password: 'password'

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'team'

receivers:
  - name: 'team'
    email_configs:
      - to: 'team@example.com'
```

### Alert Rules

**File**: `monitoring/rules/alerts.yml`

```yaml
groups:
  - name: sprint_13_alerts
    rules:
      # Embedding Pipeline Alerts
      - alert: EmbeddingServiceDown
        expr: embedding_service_available == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Embedding service unavailable"
          description: "Embedding service has been unavailable for 5+ minutes. New contexts will not have semantic search."

      - alert: HighEmbeddingFailureRate
        expr: embedding:success_rate:5m < 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High embedding failure rate"
          description: "Embedding success rate is {{ $value }}% (threshold: 90%)"

      # Storage Alerts
      - alert: QdrantDiskFull
        expr: qdrant_disk_usage_bytes / qdrant_disk_total_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Qdrant disk usage high"
          description: "Qdrant disk usage is {{ $value }}% (threshold: 80%)"

      - alert: RedisMemoryHigh
        expr: redis_memory_usage_bytes > 1073741824  # 1GB
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory usage high"
          description: "Redis memory is {{ $value | humanize }} (threshold: 1GB)"

      - alert: RedisKeysWithoutTTL
        expr: redis_keys_without_ttl > 100
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Many Redis keys without TTL"
          description: "{{ $value }} keys have no expiration set"

      # API Performance Alerts
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, http_requests_duration_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency"
          description: "P95 API latency is {{ $value }}s (threshold: 2s)"

      - alert: HighAPIErrorRate
        expr: http:error_rate:5m > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "API error rate is {{ $value }}% (threshold: 5%)"

      # Sprint 13 Specific Alerts
      - alert: RelationshipDetectionFailures
        expr: rate(relationship_creation_failures[5m]) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Relationship detection failures"
          description: "{{ $value }} relationship creation failures per second"

      - alert: NamespaceLockContention
        expr: rate(namespace_locks_failed_total[5m]) > 5
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "High namespace lock contention"
          description: "{{ $value }} failed lock acquisitions per second"

      - alert: RedisSyncFailing
        expr: increase(redis_sync_failures_total[1h]) > 0
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Redis-to-Neo4j sync failing"
          description: "{{ $value }} sync failures in the last hour"
```

---

## Health Endpoints

### Standard Health Check

**Endpoint**: `GET /health`

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-18T12:00:00Z"
}
```

**Monitoring**:
```prometheus
# Health check probe
probe_success{job="veris-memory-mcp"}
```

---

### Detailed Health Check

**Endpoint**: `GET /health/detailed`

```bash
curl http://localhost:8000/health/detailed
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-18T12:00:00Z",
  "qdrant": {
    "healthy": true,
    "embedding_service_loaded": true,
    "test_embedding_successful": true,
    "collections": 3,
    "vectors_count": 1523,
    "disk_usage_mb": 245.2
  },
  "neo4j": {
    "healthy": true,
    "context_nodes": 1523,
    "relationships": 456,
    "disk_usage_mb": 512.1
  },
  "redis": {
    "healthy": true,
    "memory_usage_mb": 15.2,
    "keys_total": 342,
    "keys_without_ttl": 5
  },
  "embedding_pipeline": {
    "status": "operational",
    "model": "all-MiniLM-L6-v2",
    "dimensions": 384,
    "recent_failures": 0
  }
}
```

**Monitoring**:
```prometheus
# Component health
qdrant_healthy{instance="veris-memory-mcp"}
neo4j_healthy{instance="veris-memory-mcp"}
redis_healthy{instance="veris-memory-mcp"}
```

---

### Statistics Endpoints

**Relationship Stats**: `GET /stats/relationships`

```json
{
  "total_detected": 456,
  "by_type": {
    "PRECEDED_BY": 23,
    "PART_OF": 156,
    "REFERENCES": 89,
    "FIXES": 34
  },
  "last_detection": "2025-10-18T11:59:30Z"
}
```

**Namespace Stats**: `GET /stats/namespaces`

```json
{
  "total_namespaces": 12,
  "namespaces": {
    "/global/default": {"context_count": 45, "type": "global"},
    "/project/veris-memory/context": {"context_count": 234, "type": "project"}
  }
}
```

**Redis Cleanup Stats**: `GET /stats/redis-cleanup`

```json
{
  "total_cleaned": 1234,
  "last_cleanup": "2025-10-18T11:00:00Z",
  "errors": 0
}
```

**Redis Sync Stats**: `GET /stats/redis-sync`

```json
{
  "total_synced": 5678,
  "last_sync": "2025-10-18T11:30:00Z",
  "errors": 0,
  "last_error": null
}
```

---

## Log Monitoring

### Structured Logging

All Sprint 13 components use structured JSON logging:

```json
{
  "timestamp": "2025-10-18T12:00:00Z",
  "level": "INFO",
  "component": "relationship_detector",
  "message": "Detected 3 relationships for context abc-123",
  "context_id": "abc-123",
  "relationships": ["FIXES issue_456", "PART_OF sprint_13", "PART_OF project_veris"]
}
```

### Log Aggregation with Loki

**Docker Compose Addition**:

```yaml
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/loki-config.yml
    command: -config.file=/etc/loki/loki-config.yml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log
      - ./monitoring/promtail-config.yml:/etc/promtail/promtail-config.yml
    command: -config.file=/etc/promtail/promtail-config.yml
```

**Loki Configuration**: `monitoring/loki-config.yml`

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb:
    directory: /loki/index
  filesystem:
    directory: /loki/chunks
```

### Key Log Queries

**Embedding Failures**:
```logql
{job="veris-memory-mcp"} |= "embedding" |= "failed"
```

**Relationship Detection**:
```logql
{job="veris-memory-mcp", component="relationship_detector"}
| json
| relationships_count > 0
```

**API Errors**:
```logql
{job="veris-memory-mcp"} |= "error" | json | level="ERROR"
```

**Namespace Lock Failures**:
```logql
{job="veris-memory-mcp", component="namespace_manager"}
|= "lock" |= "failed"
```

---

## Quick Start

### 1. Deploy Monitoring Stack

```bash
# 1. Create monitoring directory
mkdir -p monitoring/{dashboards,rules,datasources}

# 2. Copy configuration files
cp docs/monitoring/*.yml monitoring/

# 3. Update docker-compose.yml
cat >> docker-compose.yml <<EOF
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/rules:/etc/prometheus/rules
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/datasources:/etc/grafana/provisioning/datasources

volumes:
  prometheus_data:
  grafana_data:
EOF

# 4. Start monitoring
docker-compose up -d prometheus grafana
```

### 2. Access Dashboards

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

### 3. Verify Metrics

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Check metrics endpoint
curl http://localhost:8000/metrics

# Test alert rules
curl http://localhost:9090/api/v1/rules
```

---

## Best Practices

1. **Set Up Alerts Early**: Configure critical alerts before deploying to production
2. **Monitor Trends**: Track metrics over time to identify degradation
3. **Regular Reviews**: Review dashboards weekly during sprint
4. **Automate Responses**: Use alertmanager webhooks for automated remediation
5. **Capacity Planning**: Monitor growth trends to plan for scaling

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-18 | Initial Sprint 13 monitoring setup |
