# Hetzner Production Monitoring Deployment Guide

## Overview

This guide covers deploying the Veris Memory monitoring system to the Hetzner dedicated server (135.181.4.118) with Phase 2 real-time analytics and security controls.

## Prerequisites

- Hetzner server with 64GB RAM (AMD Ryzen 5 3600)
- SSH access configured
- Docker and Docker Compose installed
- UFW firewall available

## Quick Deployment

### 1. Run Automated Deployment

```bash
# Deploy monitoring system with all security controls
./scripts/deploy-monitoring-production.sh
```

This script will:
- ✅ Configure UFW firewall rules
- ✅ Generate secure tokens and passwords
- ✅ Deploy production Docker Compose configuration
- ✅ Start all services with monitoring enabled
- ✅ Validate deployment health

### 2. Validate Deployment

```bash
# Run comprehensive validation
./scripts/validate-monitoring-deployment.sh
```

This validates:
- ✅ Health endpoints responding
- ✅ Monitoring dashboard functional
- ✅ Rate limiting working
- ✅ Database connectivity
- ✅ Security configuration
- ✅ Performance metrics
- ✅ Resource usage optimal

## Production Configuration

### Ports and Access

| Service | Port | Access | Purpose |
|---------|------|--------|---------|
| Veris API | 8001 | localhost only | MCP server |
| Monitoring Dashboard | 8080 | localhost only | Real-time analytics |
| SSH | 22 | external | Server access |
| Claude CLI Dev | 2222 | external | Development (optional) |

### Security Features

- **Firewall**: UFW with localhost-only access to services
- **Rate Limiting**: 5 req/min for analytics, 20 req/min for dashboard
- **Authentication**: Required tokens for dashboard access
- **CORS**: Disabled for production
- **Resource Limits**: Memory/CPU limits configured

### Monitoring Endpoints

```bash
# Health checks
curl http://127.0.0.1:8001/health/live
curl http://127.0.0.1:8001/health/ready

# Monitoring dashboard (JSON for agents)
curl http://127.0.0.1:8080/api/dashboard

# Real-time analytics
curl "http://127.0.0.1:8080/api/dashboard/analytics?minutes=5"

# ASCII dashboard (human-readable)
curl http://127.0.0.1:8080/api/dashboard/ascii
```

## Performance Specifications

### Target Performance (64GB System)

- **API Response Time**: < 100ms P95
- **Dashboard Load Time**: < 500ms P95
- **Memory Usage**: < 8GB total
- **CPU Usage**: < 50% average
- **Concurrent Users**: 20+ simultaneous

### Resource Allocation

```yaml
# Container limits (docker-compose.prod.yml)
resources:
  limits:
    memory: 2G      # Main API service
    cpus: '1.0'
  reservations:
    memory: 1G
    cpus: '0.5'
```

## Troubleshooting

### Common Issues

1. **Services not starting**
   ```bash
   # Check logs
   docker-compose -f docker-compose.prod.yml logs
   
   # Restart services
   docker-compose -f docker-compose.prod.yml restart
   ```

2. **Monitoring endpoints not responding**
   ```bash
   # Check firewall
   sudo ufw status
   
   # Test local connectivity
   curl -v http://127.0.0.1:8080/api/dashboard/health
   ```

3. **High resource usage**
   ```bash
   # Check container stats
   docker stats --no-stream
   
   # Check system resources
   free -h && df -h
   ```

### Log Locations

```bash
# Application logs
docker-compose -f docker-compose.prod.yml logs context-store

# System logs
journalctl -u docker.service

# Deployment logs
/tmp/monitoring-deploy-*.log
```

## Security Hardening

### Environment Variables

Create `.env.production` with secure values:

```bash
# Generate secure passwords
NEO4J_PASSWORD=$(openssl rand -base64 32)
ANALYTICS_AUTH_TOKEN=$(openssl rand -base64 48)

# Configure monitoring
MONITORING_ENABLED=true
DASHBOARD_AUTH_REQUIRED=true
ENABLE_CORS=false
```

### Firewall Rules

```bash
# Required UFW rules
sudo ufw allow 22/tcp                    # SSH
sudo ufw allow from 127.0.0.1 to any port 8001  # API
sudo ufw allow from 127.0.0.1 to any port 8080  # Dashboard
sudo ufw enable
```

## Monitoring Features

### Real-Time Analytics

- **Request Metrics**: P95/P99 latency, error rates
- **System Metrics**: CPU, memory, disk usage
- **Database Health**: Qdrant, Neo4j, Redis status
- **Performance Insights**: Automated alerting and recommendations

### Dashboard Formats

1. **JSON Dashboard** (`/api/dashboard`)
   - Machine-readable format for AI agents
   - Complete system metrics
   - Time-series analytics

2. **Analytics Dashboard** (`/api/dashboard/analytics`)
   - Real-time trending data
   - Performance insights engine
   - Configurable time windows

3. **ASCII Dashboard** (`/api/dashboard/ascii`)
   - Human-readable terminal output
   - Visual status indicators
   - Quick system overview

## Next Steps

After successful deployment:

1. **Set up external monitoring** (optional)
   - Configure Prometheus integration
   - Set up alerting webhooks
   - Implement log aggregation

2. **Deploy autonomous monitoring agent** (Issue #46)
   - Implement Veris Sentinel container
   - Configure automated testing
   - Set up GitHub issue creation

3. **Performance optimization**
   - Tune for 64GB system capabilities
   - Optimize database configurations
   - Implement caching strategies

## Support

For issues with the monitoring deployment:

1. Check the validation script output
2. Review deployment logs
3. Verify firewall and network configuration
4. Test individual service health endpoints

The monitoring system is designed to be self-healing and will automatically recover from transient failures.