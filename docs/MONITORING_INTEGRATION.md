# Monitoring Integration Guide

This guide explains how to connect Veris Memory's structured logs and metrics to your monitoring and alerting systems.

## Overview

Veris Memory emits structured logs and Prometheus-compatible metrics for key operations:

1. **Embedding Fallback Events** - Track when hash-based embeddings are used
2. **Cache Hit/Miss Rates** - Monitor cache effectiveness
3. **Backend Health** - Component availability and errors

## Structured Log Format

All key events include:
- Human-readable message
- Structured `extra` dict with machine-readable fields
- Prometheus-compatible metric string

**Example Log Entry**:
```json
{
  "timestamp": "2025-11-07T12:34:56Z",
  "level": "WARNING",
  "message": "MIGRATION MODE: Using hash-based embeddings (0% semantic value)...",
  "extra": {
    "event_type": "embedding_fallback",
    "fallback_type": "hash_based",
    "semantic_value": "0%",
    "migration_mode": true,
    "alert_level": "warning"
  }
}
```

**Metric String**:
```
METRIC: embedding_fallback_count{type='hash_based',semantic_value='0'} 1
```

---

## Integration Methods

### Method 1: Prometheus with Log-Based Metrics

**Tools**: Prometheus, promtail/mtail, Grafana

**Setup**:

1. **Configure Log Parser** (promtail example):
```yaml
# promtail-config.yaml
scrape_configs:
  - job_name: veris-memory
    static_configs:
      - targets:
          - localhost
        labels:
          job: veris-memory
          __path__: /var/log/veris-memory/*.log

    pipeline_stages:
      # Extract METRIC: lines
      - regex:
          expression: '^.*METRIC: (?P<metric_name>\w+){(?P<labels>[^}]+)} (?P<value>\d+)$'

      # Convert to Prometheus metrics
      - metrics:
          embedding_fallback_count:
            type: Counter
            description: "Count of embedding fallbacks"
            source: value
            config:
              action: inc
              match_all: true

          cache_requests_total:
            type: Counter
            description: "Total cache requests by result"
            source: value
            config:
              action: inc
              match_all: true
```

2. **Create Prometheus Rules**:
```yaml
# prometheus-rules.yaml
groups:
  - name: veris_memory_alerts
    interval: 30s
    rules:
      # Alert on high hash embedding fallback rate
      - alert: HighHashEmbeddingFallbackRate
        expr: rate(embedding_fallback_count{type="hash_based"}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
          service: veris-memory
        annotations:
          summary: "High rate of hash-based embedding fallbacks"
          description: "{{ $value | humanize }} fallbacks/sec. Embedding service may be degraded."

      # Alert on low cache hit rate
      - alert: LowCacheHitRate
        expr: |
          sum(rate(cache_requests_total{result="hit"}[5m])) /
          sum(rate(cache_requests_total[5m])) < 0.3
        for: 10m
        labels:
          severity: info
          service: veris-memory
        annotations:
          summary: "Cache hit rate below 30%"
          description: "Current hit rate: {{ $value | humanizePercentage }}. Consider increasing TTL."

      # Alert on embedding service down
      - alert: EmbeddingServiceDown
        expr: rate(embedding_fallback_count[5m]) > 0.5
        for: 2m
        labels:
          severity: critical
          service: veris-memory
        annotations:
          summary: "Embedding service appears to be down"
          description: "High fallback rate indicates embedding service failure."
```

3. **Grafana Dashboard**:
```json
{
  "dashboard": {
    "title": "Veris Memory - Performance",
    "panels": [
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "sum(rate(cache_requests_total{result='hit'}[5m])) / sum(rate(cache_requests_total[5m]))"
          }
        ],
        "type": "stat"
      },
      {
        "title": "Embedding Fallback Rate",
        "targets": [
          {
            "expr": "rate(embedding_fallback_count[5m])"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Cache Requests by Result",
        "targets": [
          {
            "expr": "sum by (result) (rate(cache_requests_total[5m]))"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

---

### Method 2: DataDog with Log Pipeline

**Tools**: DataDog Agent, Log Pipeline

**Setup**:

1. **Configure DataDog Agent** (`datadog.yaml`):
```yaml
logs_enabled: true

logs_config:
  - type: file
    path: /var/log/veris-memory/*.log
    service: veris-memory
    source: python

    # Custom parsing for METRIC: lines
    log_processing_rules:
      - type: exclude_at_match
        name: exclude_debug
        pattern: "DEBUG"
```

2. **Create Log Pipeline** (DataDog UI):
- Grok Parser:
  ```
  METRIC:\s+%{NOTSPACE:metric_name}\{%{DATA:metric_labels}\}\s+%{NUMBER:metric_value}
  ```

- Remapper:
  - `event_type` → `evt.name`
  - `fallback_type` → tag
  - `search_mode` → tag

3. **Create Monitors**:

```python
# DataDog API - Create Monitor
import requests

monitor = {
    "name": "High Hash Embedding Fallback Rate",
    "type": "metric alert",
    "query": "avg(last_5m):rate(embedding_fallback_count{type:hash_based}) > 0.05",
    "message": """
    High rate of hash-based embedding fallbacks detected.
    Current rate: {{value}} per second

    This may indicate:
    - Embedding service degraded or down
    - sentence-transformers not installed
    - Model loading failures

    Action: Check embedding service logs and health
    @slack-alerts @oncall
    """,
    "tags": ["service:veris-memory", "component:embeddings"],
    "priority": 2
}

requests.post(
    "https://api.datadoghq.com/api/v1/monitor",
    headers={"DD-API-KEY": "YOUR_API_KEY"},
    json=monitor
)
```

---

### Method 3: CloudWatch Logs with Metric Filters

**Tools**: AWS CloudWatch, CloudWatch Logs

**Setup**:

1. **Create Metric Filters**:
```bash
# Embedding fallback metric
aws logs put-metric-filter \
  --log-group-name /veris-memory/application \
  --filter-name EmbeddingFallbackCount \
  --filter-pattern '[time, level=WARNING*, msg="*METRIC: embedding_fallback_count*"]' \
  --metric-transformations \
    metricName=EmbeddingFallbackCount,\
    metricNamespace=VerisMemory,\
    metricValue=1,\
    defaultValue=0

# Cache hit metric
aws logs put-metric-filter \
  --log-group-name /veris-memory/application \
  --filter-name CacheHits \
  --filter-pattern '[time, level=INFO*, msg="*METRIC: cache_requests_total{result=''hit''*"]' \
  --metric-transformations \
    metricName=CacheHits,\
    metricNamespace=VerisMemory,\
    metricValue=1

# Cache miss metric
aws logs put-metric-filter \
  --log-group-name /veris-memory/application \
  --filter-name CacheMisses \
  --filter-pattern '[time, level=INFO*, msg="*METRIC: cache_requests_total{result=''miss''*"]' \
  --metric-transformations \
    metricName=CacheMisses,\
    metricNamespace=VerisMemory,\
    metricValue=1
```

2. **Create CloudWatch Alarms**:
```bash
# Alert on high embedding fallback rate
aws cloudwatch put-metric-alarm \
  --alarm-name veris-memory-high-embedding-fallback \
  --alarm-description "High rate of hash-based embedding fallbacks" \
  --metric-name EmbeddingFallbackCount \
  --namespace VerisMemory \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789:veris-alerts

# Alert on low cache hit rate
aws cloudwatch put-metric-alarm \
  --alarm-name veris-memory-low-cache-hit-rate \
  --alarm-description "Cache hit rate below 30%" \
  --metrics file://cache-hit-rate-metric.json \
  --evaluation-periods 2 \
  --threshold 0.3 \
  --comparison-operator LessThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789:veris-alerts
```

**cache-hit-rate-metric.json**:
```json
[
  {
    "Id": "hit_rate",
    "Expression": "hits / (hits + misses)",
    "Label": "Cache Hit Rate"
  },
  {
    "Id": "hits",
    "MetricStat": {
      "Metric": {
        "Namespace": "VerisMemory",
        "MetricName": "CacheHits"
      },
      "Period": 300,
      "Stat": "Sum"
    },
    "ReturnData": false
  },
  {
    "Id": "misses",
    "MetricStat": {
      "Metric": {
        "Namespace": "VerisMemory",
        "MetricName": "CacheMisses"
      },
      "Period": 300,
      "Stat": "Sum"
    },
    "ReturnData": false
  }
]
```

---

### Method 4: ELK Stack (Elasticsearch, Logstash, Kibana)

**Tools**: Filebeat, Logstash, Elasticsearch, Kibana

**Setup**:

1. **Filebeat Configuration** (`filebeat.yml`):
```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/veris-memory/*.log
    json.keys_under_root: true
    json.add_error_key: true
    fields:
      service: veris-memory

output.logstash:
  hosts: ["logstash:5044"]
```

2. **Logstash Pipeline** (`logstash.conf`):
```ruby
filter {
  # Parse METRIC: lines
  if [message] =~ /^METRIC:/ {
    grok {
      match => {
        "message" => "METRIC: %{NOTSPACE:metric_name}\{%{DATA:metric_labels}\} %{NUMBER:metric_value:int}"
      }
    }

    # Extract labels
    kv {
      source => "metric_labels"
      field_split => ","
      value_split => "="
      remove_char_key => "'"
      remove_char_value => "'"
    }

    mutate {
      add_tag => ["metric"]
    }
  }

  # Parse structured extra fields
  if [extra] {
    ruby {
      code => "
        event.get('extra').each { |k, v|
          event.set(k, v)
        }
      "
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "veris-memory-%{+YYYY.MM.dd}"
  }
}
```

3. **Kibana Visualizations**:

Create these in Kibana:

- **Cache Hit Rate** (Metric Visualization):
  ```
  Filter: metric_name: "cache_requests_total" AND result: "hit"
  Count / (Count of cache_requests_total)
  ```

- **Embedding Fallback Timeline** (Line Chart):
  ```
  Filter: metric_name: "embedding_fallback_count"
  Y-axis: Count
  X-axis: @timestamp
  ```

4. **Kibana Alerts** (Watcher):
```json
{
  "trigger": {
    "schedule": {
      "interval": "5m"
    }
  },
  "input": {
    "search": {
      "request": {
        "indices": ["veris-memory-*"],
        "body": {
          "query": {
            "bool": {
              "must": [
                {
                  "match": {
                    "metric_name": "embedding_fallback_count"
                  }
                },
                {
                  "range": {
                    "@timestamp": {
                      "gte": "now-5m"
                    }
                  }
                }
              ]
            }
          }
        }
      }
    }
  },
  "condition": {
    "compare": {
      "ctx.payload.hits.total": {
        "gte": 10
      }
    }
  },
  "actions": {
    "send_email": {
      "email": {
        "to": "oncall@example.com",
        "subject": "Veris Memory: High embedding fallback rate",
        "body": "Detected {{ctx.payload.hits.total}} embedding fallbacks in the last 5 minutes."
      }
    }
  }
}
```

---

## Metrics Reference

### embedding_fallback_count

**Type**: Counter
**Labels**: `type`, `semantic_value`
**Description**: Increments each time hash-based embeddings are used

**Example**:
```
METRIC: embedding_fallback_count{type='hash_based',semantic_value='0'} 1
```

**Alert Thresholds**:
- **Info**: > 0.01/sec (1 per 100 seconds) - Monitor
- **Warning**: > 0.05/sec (1 per 20 seconds) - Investigate
- **Critical**: > 0.5/sec (1 per 2 seconds) - Embedding service likely down

---

### cache_requests_total

**Type**: Counter
**Labels**: `result` (hit/miss/error), `search_mode`
**Description**: Tracks all cache operations

**Examples**:
```
METRIC: cache_requests_total{result='hit',search_mode='hybrid'} 1
METRIC: cache_requests_total{result='miss',search_mode='vector'} 1
METRIC: cache_requests_total{result='error'} 1
```

**Derived Metrics**:
- **Cache Hit Rate**: `sum(hit) / sum(hit + miss)`
- **Cache Error Rate**: `sum(error) / sum(hit + miss + error)`

**Alert Thresholds**:
- **Cache Hit Rate < 30%**: Consider increasing TTL
- **Cache Hit Rate < 10%**: Check if cache is working
- **Cache Error Rate > 5%**: Redis connection issues

---

## Testing Your Monitoring

### 1. Test Embedding Fallback Alerts

```bash
# Enable hash embeddings temporarily
export ALLOW_HASH_EMBEDDINGS=true

# Generate some requests
for i in {1..10}; do
  curl -X POST http://localhost:8000/tools/store_context \
    -H "X-API-Key: vmk_..." \
    -d "{\"type\":\"log\",\"content\":{\"title\":\"Test $i\"},\"author\":\"test\",\"author_type\":\"agent\"}"
done

# Check logs for METRIC: embedding_fallback_count
docker-compose logs context-store | grep "METRIC: embedding_fallback_count"

# Verify your monitoring system received the events
# (check Grafana, DataDog, CloudWatch, etc.)
```

### 2. Test Cache Metrics

```bash
# First request (cache miss)
curl -X POST http://localhost:8000/tools/retrieve_context \
  -H "X-API-Key: vmk_..." \
  -d '{"query":"test","limit":5}'

# Second request (cache hit)
curl -X POST http://localhost:8000/tools/retrieve_context \
  -H "X-API-Key: vmk_..." \
  -d '{"query":"test","limit":5}'

# Check logs for metrics
docker-compose logs context-store | grep "METRIC: cache_requests_total"

# Verify metrics in monitoring system
```

---

## Troubleshooting

### Metrics Not Appearing in Prometheus

1. Check log format:
   ```bash
   docker-compose logs context-store | grep "METRIC:"
   ```

2. Verify promtail is parsing correctly:
   ```bash
   curl http://localhost:9080/metrics | grep embedding_fallback_count
   ```

3. Check Prometheus targets:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

### DataDog Not Receiving Events

1. Check DataDog Agent status:
   ```bash
   datadog-agent status
   ```

2. Verify log collection:
   ```bash
   datadog-agent check logs
   ```

3. Check pipeline processing:
   - DataDog UI → Logs → Pipelines → veris-memory
   - Verify grok parser is matching

### CloudWatch Metric Filters Not Triggering

1. Test filter pattern:
   ```bash
   aws logs filter-log-events \
     --log-group-name /veris-memory/application \
     --filter-pattern '[time, level=WARNING*, msg="*METRIC: embedding_fallback_count*"]' \
     --limit 10
   ```

2. Check metric data:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace VerisMemory \
     --metric-name EmbeddingFallbackCount \
     --start-time 2025-11-07T00:00:00Z \
     --end-time 2025-11-07T23:59:59Z \
     --period 3600 \
     --statistics Sum
   ```

---

## Best Practices

1. **Set Up Alerts Before Deploying**
   - Configure at least embedding fallback and cache hit rate alerts
   - Test alerts in staging environment

2. **Monitor Baselines**
   - Track normal cache hit rates (typically 30-60%)
   - Establish baseline for embedding fallback frequency

3. **Use Dashboards**
   - Create a central dashboard for key metrics
   - Include cache hit rate, fallback rate, error rates

4. **Regular Review**
   - Review alerts monthly
   - Adjust thresholds based on observed behavior
   - Remove alerts that fire too frequently (tune thresholds)

5. **Document Runbooks**
   - What to do when embedding fallback alert fires
   - How to investigate low cache hit rates
   - Escalation procedures for critical alerts

---

## Additional Resources

- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [DataDog Log Management](https://docs.datadoghq.com/logs/)
- [CloudWatch Logs Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AnalyzingLogData.html)
- [ELK Stack Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)

---

**Last Updated**: 2025-11-07
**Veris Memory Version**: 1.0.0+
