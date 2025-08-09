# Service Level Objectives (SLOs) - Context Store Production Monitoring

## Overview

This document defines Service Level Objectives (SLOs) for the Context Store production deployment. These SLOs establish measurable reliability targets that align with user expectations and business requirements.

## Core SLOs

### 1. Availability SLO
- **Objective**: 99.5% uptime over 30-day rolling window
- **Measurement**: HTTP 200 responses to `/health` endpoint
- **Error Budget**: 3.6 hours downtime per month
- **Alerting Threshold**: 99.0% (0.5% buffer)

**Prometheus Query:**
```promql
(sum(rate(mcp_requests_total{endpoint="health",status="success"}[5m])) / 
 sum(rate(mcp_requests_total{endpoint="health"}[5m]))) * 100
```

### 2. Request Latency SLO
- **Objective**: 95% of requests complete within 500ms
- **Measurement**: MCP request duration histogram
- **Error Budget**: 5% of requests may exceed 500ms
- **Alerting Threshold**: 90% (5% buffer)

**Prometheus Query:**
```promql
histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket[5m])) < 0.5
```

### 3. Context Storage Success Rate SLO
- **Objective**: 99.9% of context storage operations succeed
- **Measurement**: `store_context` endpoint success rate
- **Error Budget**: 0.1% failed storage operations
- **Alerting Threshold**: 99.5% (0.4% buffer)

**Prometheus Query:**
```promql
(sum(rate(mcp_requests_total{endpoint="store_context",status="success"}[5m])) / 
 sum(rate(mcp_requests_total{endpoint="store_context"}[5m]))) * 100
```

### 4. Context Retrieval Success Rate SLO
- **Objective**: 99.5% of context retrieval operations succeed
- **Measurement**: `retrieve_context` endpoint success rate
- **Error Budget**: 0.5% failed retrieval operations
- **Alerting Threshold**: 99.0% (0.5% buffer)

**Prometheus Query:**
```promql
(sum(rate(mcp_requests_total{endpoint="retrieve_context",status="success"}[5m])) / 
 sum(rate(mcp_requests_total{endpoint="retrieve_context"}[5m]))) * 100
```

### 5. Search Quality SLO
- **Objective**: 90% of needle tests pass in smoke tests
- **Measurement**: Deploy guard test results
- **Error Budget**: 10% needle test failures
- **Alerting Threshold**: 85% (5% buffer)

**Implementation**: Tracked via deploy guard automated testing

### 6. Storage Backend Health SLO
- **Objective**: 99.9% uptime for Qdrant and Neo4j
- **Measurement**: Backend health check success rate
- **Error Budget**: 0.1% backend downtime
- **Alerting Threshold**: 99.5% (0.4% buffer)

**Prometheus Query:**
```promql
mcp_health_status{component=~"qdrant|neo4j"} == 1
```

## Infrastructure SLOs

### 7. Database Response Time SLO
- **Objective**: 99% of database operations complete within 100ms
- **Measurement**: Storage operation duration histogram
- **Error Budget**: 1% of operations may exceed 100ms
- **Alerting Threshold**: 95% (4% buffer)

**Prometheus Query:**
```promql
histogram_quantile(0.99, rate(mcp_storage_duration_seconds_bucket[5m])) < 0.1
```

### 8. Embedding Generation SLO
- **Objective**: 95% of embeddings generated within 2 seconds
- **Measurement**: Embedding operation duration histogram
- **Error Budget**: 5% of operations may exceed 2 seconds
- **Alerting Threshold**: 90% (5% buffer)

**Prometheus Query:**
```promql
histogram_quantile(0.95, rate(mcp_embedding_duration_seconds_bucket[5m])) < 2.0
```

### 9. Rate Limiting Fairness SLO
- **Objective**: Rate limiting affects <5% of legitimate requests
- **Measurement**: Rate limit hit counter vs total requests
- **Error Budget**: 5% legitimate requests rate limited
- **Alerting Threshold**: 3% (2% buffer)

**Prometheus Query:**
```promql
(sum(rate(mcp_rate_limit_hits_total[5m])) / 
 sum(rate(mcp_requests_total[5m]))) * 100 < 5
```

### 10. Backup Success SLO
- **Objective**: 100% of daily backups complete successfully
- **Measurement**: Backup system completion status
- **Error Budget**: 0 failed backups per month
- **Alerting Threshold**: Any backup failure

**Implementation**: Monitored via backup system logs and cron job status

## SLO Monitoring Dashboard

### Key Metrics Displayed
1. **SLO Burn Rate**: Current error budget consumption rate
2. **Error Budget Remaining**: Percentage of error budget left
3. **Historical SLO Performance**: 30-day trend charts
4. **Component Health Status**: Real-time health of all services
5. **Alert Status**: Current firing alerts and their impact on SLOs

### Dashboard Queries

#### Error Budget Burn Rate (1-hour window)
```promql
(1 - (
  sum(rate(mcp_requests_total{status="success"}[1h])) / 
  sum(rate(mcp_requests_total[1h]))
)) * 100
```

#### Days of Error Budget Remaining
```promql
(slo_error_budget_remaining / slo_burn_rate) / (24 * 3600)
```

## Alerting Strategy

### Alert Severity Levels

#### 1. Critical (Page immediately)
- SLO breach imminent (Error budget will be exhausted in <2 hours)
- Multiple backend services down
- Deploy guard smoke tests failing

#### 2. Warning (Notify during business hours)
- SLO at risk (Error budget will be exhausted in <24 hours)
- Single backend service degraded
- High request latency (>1s for 95th percentile)

#### 3. Info (Log for review)
- SLO performing well but trending toward threshold
- Successful deployment completion
- Backup completion status

### Alert Runbooks

#### SLO Breach Alert Response
1. **Immediate Actions** (0-5 minutes)
   - Check deployment status via `/health` endpoint
   - Verify backend service health (Qdrant, Neo4j, Redis)
   - Review recent deployments or configuration changes

2. **Investigation** (5-15 minutes)
   - Analyze request latency patterns
   - Check storage backend performance metrics
   - Review application logs for errors

3. **Mitigation** (15-30 minutes)
   - Roll back recent changes if identified as cause
   - Scale resources if performance issue
   - Restart services if health checks failing

4. **Recovery Validation** (30-45 minutes)
   - Run deploy guard smoke tests
   - Monitor SLO recovery trend
   - Document incident and root cause

## SLO Review Process

### Weekly SLO Review
- Analyze SLO performance trends
- Review error budget consumption
- Identify opportunities for reliability improvements
- Update alert thresholds based on operational experience

### Monthly SLO Assessment
- Evaluate SLO targets against business needs
- Adjust objectives based on service evolution
- Plan reliability engineering initiatives
- Update documentation and procedures

### Quarterly SLO Planning
- Set SLO targets for next quarter
- Review historical performance data
- Plan infrastructure improvements
- Budget allocation for reliability projects

## Implementation Status

✅ **Completed Components:**
- Prometheus metrics collection (`src/core/monitoring.py`)
- Deploy guard smoke tests (`deploy_guard.py`)
- Backup system with success tracking (`backup_system.py`)
- Namespace isolation enforcement (`src/core/agent_namespace.py`)
- Configuration management hardening (`src/core/config.py`)

🔧 **Ready for Production:**
- SLO monitoring queries defined
- Alert thresholds established
- Runbook procedures documented
- Dashboard specifications complete

## Contact Information

- **SLO Owner**: DevOps Team
- **Escalation**: On-call Engineer
- **Dashboard**: http://grafana.context-store.com/slo-dashboard
- **Runbooks**: https://docs.context-store.com/runbooks/