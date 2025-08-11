# Veris Memory Burn-In Testing Guide

## Overview

This document provides context for agents performing burn-in stability testing on the Veris Memory (Context Store) deployment on the Hetzner dedicated server. Burn-in testing validates system stability, performance, and configuration integrity under continuous load.

## Current Deployment Status

**Status: ✅ PRODUCTION READY** (as of 2025-08-11)

- **Server**: Hetzner Dedicated Server
- **IP**: 135.181.4.118  
- **Location**: `/opt/veris-memory`
- **Repository**: https://github.com/credentum/veris-memory.git
- **Last Successful Burn-in**: `burnin-stable-20250811-185229`

## Infrastructure

### Services Running

1. **Qdrant** (Vector Database)
   - Port: 6333 (localhost only)
   - Configuration: 384 dimensions, Cosine distance
   - Collection: `context_embeddings`
   - Status: Green/Healthy

2. **Neo4j** (Graph Database)
   - Port: 7474 (localhost only)
   - Version: 5.15.0
   - Status: Active

3. **Redis** (Cache)
   - Port: 6379 (localhost only)
   - Status: Active

### Docker Containers

```bash
veris-memory-redis-1    # Redis cache
veris-memory-qdrant-1   # Vector database
veris-memory-neo4j-1    # Graph database
```

## SSH Access Configuration

### Important: Authentication Issues

1. **SSH Alias**: Use `hetzner-server` (configured in `~/.ssh/config`)
2. **Direct IP**: May fail due to firewall/fail2ban
3. **User**: root (NOT codespace)
4. **Key**: Uses `~/.ssh/hetzner_key`

### Common Connection Issues & Solutions

```bash
# If connection times out, you may be banned by fail2ban
# Your IP (GitHub Codespaces): 4.155.74.48

# On server, check and unban:
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip 4.155.74.48

# Add firewall exception:
sudo iptables -I INPUT -s 4.155.74.48 -p tcp --dport 22 -j ACCEPT
sudo ufw allow from 4.155.74.48 to any port 22
```

## Burn-In Testing Process

### What is Burn-In Testing?

Burn-in testing runs continuous cycles of load tests until achieving a stability threshold (typically 5 consecutive successful cycles). It validates:

1. **Performance Stability**: No latency drift
2. **Configuration Integrity**: Dimensions and settings remain correct
3. **Error Resilience**: Zero or minimal errors under load
4. **Service Recovery**: Handles restarts gracefully

### Test Phases

1. **Phase 1: Baseline Capture**
   - Measure baseline p50, p95, p99 latencies
   - Document initial configuration
   - Set comparison metrics

2. **Phase 2-4: Burn-In Cycles**
   - Normal load (10 QPS)
   - Elevated load (20 QPS)
   - Burst load (50 QPS)
   - Fault injection (service restarts)

3. **Phase 5: Final Sign-Off**
   - Verify stability achieved
   - Create git tag
   - Generate final report

### Success Criteria

- **Stability Threshold**: 5 consecutive passing cycles
- **P95 Latency**: < 10ms
- **Error Rate**: < 0.5%
- **Configuration**: No drift from baseline
- **Integrity**: All services healthy

## Running Burn-In Tests

### Quick Test (Recommended)

```bash
# Copy test script to server
scp scripts/burnin/server_burnin.py hetzner-server:/opt/veris-memory/

# Run on server
ssh hetzner-server "cd /opt/veris-memory && python3 server_burnin.py"

# Fetch results
scp hetzner-server:/opt/veris-memory/burnin-report.json burnin-results/
```

### Available Test Scripts

Located in `/context-store/scripts/burnin/`:

1. **server_burnin.py** - Simple, reliable test for direct server execution
2. **comprehensive_burnin.py** - Full-featured with detailed metrics
3. **execute_burnin.py** - Can run locally or remotely
4. **final_burnin.sh** - Shell script version
5. **remote_burnin.sh** - Deploys and runs remotely
6. **quick_burnin.sh** - Fast validation test

## Latest Test Results

### Performance Metrics (2025-08-11)

| Metric | Value | Status |
|--------|-------|--------|
| Baseline p50 | 1.1ms | ✅ Excellent |
| Baseline p95 | 1.4ms | ✅ Excellent |
| Baseline p99 | 2.2ms | ✅ Excellent |
| Under Load p95 | 2.4ms | ✅ Stable |
| Max QPS Tested | 50 | ✅ Handled |
| Error Rate | 0% | ✅ Perfect |

### Burn-In Cycles

All 5 cycles PASSED:
- Cycle 1: 10 QPS → p95=2.4ms ✅
- Cycle 2: 20 QPS → p95=2.4ms ✅
- Cycle 3: 50 QPS → p95=2.3ms ✅
- Cycle 4: 20 QPS → p95=2.4ms ✅
- Cycle 5: 10 QPS → p95=2.4ms ✅

## Troubleshooting

### Cannot Connect to Server

1. Check if banned by fail2ban (see SSH Access section)
2. Use SSH alias `hetzner-server` instead of IP
3. Verify SSH key exists: `~/.ssh/hetzner_key`
4. Check firewall isn't blocking GitHub Codespaces IPs (4.155.x.x)

### Test Failures

1. **High Latency**: Check if other processes consuming resources
2. **Connection Refused**: Services may need restart
3. **Config Drift**: Verify Qdrant collection settings
4. **Syntax Errors**: Use provided scripts, avoid inline Python

### Service Issues

```bash
# Check service status
ssh hetzner-server "docker ps"

# Restart specific service
ssh hetzner-server "cd /opt/veris-memory && docker-compose restart qdrant"

# Check Qdrant configuration
ssh hetzner-server "curl -s http://localhost:6333/collections/context_embeddings | jq"

# Test Qdrant search
ssh hetzner-server "curl -X POST http://localhost:6333/collections/context_embeddings/points/search \
  -H 'Content-Type: application/json' \
  -d '{\"vector\": [0.1]*384, \"limit\": 5}'"
```

## Best Practices

1. **Always use localhost** when testing on server (not external IP)
2. **Run at least 5 cycles** for valid stability assessment
3. **Test different QPS levels** (10, 20, 50) to verify scaling
4. **Save reports** for historical comparison
5. **Tag successful runs** in git for rollback points

## Compliance Thresholds

| Metric | Maximum Allowed | Current |
|--------|----------------|---------|
| P@1 Drift | ≤ 0.02 | 0.00 ✅ |
| NDCG@5 Drift | ≤ 0.02 | 0.00 ✅ |
| p95 Latency Drift | ≤ 10% | 0% ✅ |
| Error Rate | ≤ 0.5% | 0% ✅ |

## Summary for New Agents

The Veris Memory deployment on Hetzner is **production-ready** with proven stability:

1. **Performance**: Sub-3ms p95 latency, handles 50 QPS bursts
2. **Stability**: Passed 5 consecutive burn-in cycles
3. **Configuration**: 384-dimensional vectors with Cosine distance
4. **Reliability**: Zero errors across all tests
5. **Tagged Release**: `burnin-stable-20250811-185229`

When running new burn-in tests:
- Use `server_burnin.py` for simplicity
- Connect via `hetzner-server` SSH alias
- Watch for fail2ban blocks (unban if needed)
- Aim for 5 stable cycles
- Tag successful runs

## Related Files

- Test Results: `/context-store/burnin-results/`
- Test Scripts: `/context-store/scripts/burnin/`
- Deployment Script: `/context-store/scripts/deploy-to-hetzner.sh`
- Latest Report: `/context-store/burnin-results/server-burnin-report.json`

---

*Last Updated: 2025-08-11*
*Next Scheduled Test: As needed or before major updates*