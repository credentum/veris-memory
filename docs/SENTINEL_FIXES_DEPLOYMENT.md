# Sentinel Fixes Deployment Guide

This guide provides step-by-step instructions for deploying the Sentinel fixes that address:
1. Telegram HTML escaping bug (40% alert failures)
2. Service name mismatches (S1 health check failures)
3. Firewall check design flaw (false security alerts)
4. Sprint 13 API authentication issues

## Overview of Fixes

### Phase 1: Critical Fixes
- ✅ Fixed Telegram HTML escaping with recursive escape function
- ✅ Implemented host-based firewall monitoring
- ✅ Updated Sentinel API to receive host check results

### Phase 2: Service Connectivity
- ✅ Fixed service naming in docker-compose.sentinel.yml
- ✅ Added Sprint 13 API authentication to health checks
- ✅ Updated network configuration

### Phase 3: Documentation
- ✅ Created comprehensive security setup guide
- ✅ Documented host-based monitoring setup

---

## Pre-Deployment Checklist

Before deploying these fixes, ensure:

- [ ] You have SSH access to the Hetzner server (135.181.4.118)
- [ ] You have sudo privileges on the server
- [ ] Current services are running and can be safely restarted
- [ ] You have a backup of the current configuration
- [ ] The API_KEY_MCP environment variable is set

---

## Deployment Steps

### Step 1: Update Code on Server

```bash
# SSH into the server
ssh user@135.181.4.118

# Navigate to repository
cd /opt/veris-memory

# Stash any local changes
git stash

# Pull latest changes
git pull origin main

# Or if using a feature branch:
git fetch origin
git checkout feature/sentinel-fixes
git pull origin feature/sentinel-fixes
```

###Step 2: Verify Configuration Files

```bash
# Check that .env file has required variables
grep -E 'API_KEY_MCP|NEO4J_PASSWORD' .env

# If API_KEY_MCP is missing, add it (replace with your actual key):
echo "API_KEY_MCP=your_actual_api_key_here" >> .env

# Verify docker-compose.yml has correct service names
docker-compose config | grep -A 5 "services:"
```

### Step 3: Setup Host-Based Firewall Monitoring

```bash
# 1. Copy monitoring script to system location
sudo mkdir -p /opt/veris-memory/scripts
sudo cp scripts/sentinel-host-checks.sh /opt/veris-memory/scripts/
sudo chmod +x /opt/veris-memory/scripts/sentinel-host-checks.sh

# 2. Create log directory
sudo mkdir -p /var/log
sudo touch /var/log/sentinel-host-checks.log
sudo chmod 644 /var/log/sentinel-host-checks.log

# 3. Test the script manually
sudo /opt/veris-memory/scripts/sentinel-host-checks.sh

# 4. Verify it works
tail -20 /var/log/sentinel-host-checks.log

# 5. Add to crontab (runs every 5 minutes)
(sudo crontab -l 2>/dev/null; echo "*/5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh >> /var/log/sentinel-host-checks.log 2>&1") | sudo crontab -

# 6. Verify crontab entry
sudo crontab -l | grep sentinel
```

### Step 4: Configure Firewall (If Not Already Done)

**⚠️ IMPORTANT: Make sure you won't lock yourself out!**

```bash
# First, ensure SSH is allowed
sudo ufw allow 22/tcp

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow required ports (localhost only for security)
sudo ufw allow from 127.0.0.1 to any port 8000 comment 'MCP Server'
sudo ufw allow from 127.0.0.1 to any port 8001 comment 'REST API'
sudo ufw allow from 127.0.0.1 to any port 8080 comment 'Dashboard'
sudo ufw allow from 127.0.0.1 to any port 9090 comment 'Sentinel API'

# Allow Mosh if using it
sudo ufw allow 60000:61000/udp comment 'Mosh'

# Enable firewall
sudo ufw --force enable

# Verify status
sudo ufw status verbose
```

### Step 5: Rebuild and Restart Sentinel

```bash
# Stop current sentinel container
docker-compose -f docker-compose.sentinel.yml down

# Rebuild with updated code
docker-compose -f docker-compose.sentinel.yml build --no-cache

# Start sentinel with new configuration
docker-compose -f docker-compose.sentinel.yml up -d

# Verify it started successfully
docker ps | grep sentinel

# Check logs for any errors
docker logs veris-sentinel --tail=50 -f
```

### Step 6: Restart Main Services (If Needed)

If you need to ensure all services have the latest configuration:

```bash
# Restart all services
docker-compose restart

# Or for a complete rebuild:
docker-compose down
docker-compose up -d --build

# Wait for services to be healthy
sleep 30

# Verify all services are running
docker ps
```

### Step 7: Verification and Testing

#### Test 1: Verify Sentinel is Running

```bash
# Check Sentinel status
curl -s http://localhost:9090/status | jq '.'

# Should return JSON with running: true
```

#### Test 2: Verify Health Checks

```bash
# Trigger a manual check cycle
curl -X POST http://localhost:9090/run | jq '.success'

# Wait a moment, then check status
sleep 5
curl -s http://localhost:9090/status | jq '.last_cycle'

# S1 should show "pass" if services are healthy
```

#### Test 3: Verify Host Firewall Check

```bash
# Check if host monitoring data is being received
curl -s http://localhost:9090/status | jq '.host_check_results."S11-firewall-status"'

# Should show firewall status from host script
```

#### Test 4: Verify Telegram Alerting (If Configured)

```bash
# Check Sentinel logs for Telegram errors
docker logs veris-sentinel 2>&1 | grep -i telegram

# Should not see "HTTP 400" errors anymore
# Should see "Telegram message sent successfully"
```

#### Test 5: Verify API Authentication

```bash
# Test health endpoint with API key
curl -s -H "X-API-Key: your_actual_api_key_here" \
  http://localhost:8000/health | jq '.'

# Should return healthy status
```

#### Test 6: End-to-End Check

```bash
# Run a complete monitoring cycle
curl -X POST http://localhost:9090/run | jq '.'

# Check the report
curl -s http://localhost:9090/report?n=1 | jq '.reports[0]'

# Verify:
# - S1-probes: pass (health checks working)
# - S11-firewall-status: pass or warn (host monitoring working)
# - No HTTP 404 errors
# - Proper authentication
```

---

## Post-Deployment Validation

### Success Criteria

After deployment, verify these conditions:

- [ ] Sentinel container is running and healthy
- [ ] S1 health probes are passing (not 404)
- [ ] S11 firewall check shows host data (not "not configured")
- [ ] No Telegram HTTP 400 errors in logs
- [ ] All services accessible with API authentication
- [ ] Host monitoring script running in cron
- [ ] Firewall is active and properly configured

### Check Dashboard

```bash
# View Prometheus metrics
curl -s http://localhost:9090/metrics

# Should show:
# sentinel_running 1
# sentinel_checks_passed > 0
# sentinel_checks_failed should be low or 0
```

### Monitor for 24 Hours

After deployment, monitor for at least 24 hours:

```bash
# Check Sentinel logs periodically
docker logs veris-sentinel --tail=100

# Check host monitoring logs
tail -f /var/log/sentinel-host-checks.log

# Verify cron is running
sudo systemctl status cron
```

---

## Rollback Procedure

If issues occur, rollback with these steps:

### Quick Rollback

```bash
# Stop new sentinel
docker-compose -f docker-compose.sentinel.yml down

# Revert to previous code
git reset --hard HEAD~1  # Or specific commit
git checkout main

# Rebuild and restart
docker-compose -f docker-compose.sentinel.yml build
docker-compose -f docker-compose.sentinel.yml up -d
```

### Remove Host Monitoring (If Needed)

```bash
# Remove cron job
sudo crontab -l | grep -v sentinel-host-checks | sudo crontab -

# Stop script
sudo rm /opt/veris-memory/scripts/sentinel-host-checks.sh
```

---

## Troubleshooting

### Issue: Sentinel Won't Start

```bash
# Check logs for errors
docker logs veris-sentinel

# Common causes:
# 1. Port 9090 already in use
sudo lsof -i :9090

# 2. Network issues
docker network ls | grep veris

# 3. Missing environment variables
docker exec veris-sentinel env | grep API_KEY_MCP
```

### Issue: S1 Health Checks Still Failing

```bash
# Test endpoints manually
curl -v http://localhost:8000/health
curl -v http://context-store:8000/health  # From inside Docker network

# Check service names
docker ps --format "table {{.Names}}\t{{.Networks}}"

# Verify API key
curl -H "X-API-Key: your_actual_api_key_here" \
  http://localhost:8000/health
```

### Issue: Host Monitoring Not Working

```bash
# Verify script permissions
ls -la /opt/veris-memory/scripts/sentinel-host-checks.sh

# Test manually
sudo /opt/veris-memory/scripts/sentinel-host-checks.sh

# Check if sentinel API is accessible
curl -v http://localhost:9090/host-checks/firewall

# Verify cron is running
sudo systemctl status cron
sudo journalctl -u cron -f
```

### Issue: Telegram Alerts Still Failing

```bash
# Check exact error
docker logs veris-sentinel 2>&1 | grep -A 5 "Telegram"

# Test with simple message
curl -X POST https://api.telegram.org/bot<BOT_TOKEN>/sendMessage \
  -d "chat_id=<CHAT_ID>" \
  -d "text=Test message" \
  -d "parse_mode=HTML"

# Verify escaping is working
docker exec veris-sentinel python3 -c "
from src.monitoring.sentinel.telegram_alerter import TelegramAlerter
alerter = TelegramAlerter('test:token', '12345')
result = alerter._escape_nested_html({'test': '<value>'})
print(result)
"
```

---

## Performance Monitoring

### Key Metrics to Watch

```bash
# Sentinel cycle performance
curl -s http://localhost:9090/metrics | grep sentinel_cycle_duration_ms

# Check failure rate
curl -s http://localhost:9090/metrics | grep sentinel_checks_failed

# Memory usage
docker stats veris-sentinel --no-stream
```

### Alert Thresholds

Monitor and alert on:
- `sentinel_checks_failed > 2` - Multiple checks failing
- `sentinel_cycle_duration_ms > 10000` - Cycles taking too long
- `sentinel_running == 0` - Sentinel stopped

---

## Next Steps

After successful deployment:

1. **Monitor for 7 Days**: Watch for any issues or regressions
2. **Review Alerts**: Ensure all alerts are actionable and not noisy
3. **Optimize Intervals**: Adjust check intervals based on load
4. **Document Issues**: Record any new issues in GitHub
5. **Plan Phase 3**: Implement remaining check fixes (S2-S10)

---

## Support

If you encounter issues:

1. Check logs: `docker logs veris-sentinel`
2. Review documentation: `docs/SECURITY_SETUP.md`
3. Create GitHub issue with full error details
4. Contact: @workspace-002 (Sentinel maintainer)

---

**Deployment Checklist**

```
Pre-Deployment:
[ ] Backed up current configuration
[ ] Verified SSH access
[ ] Confirmed API keys are set

Deployment:
[ ] Updated code from repository
[ ] Installed host monitoring script
[ ] Configured cron job
[ ] Set up firewall (if needed)
[ ] Rebuilt Sentinel container
[ ] Restarted services

Verification:
[ ] Sentinel is running
[ ] S1 checks passing
[ ] S11 shows host data
[ ] No Telegram errors
[ ] API auth working
[ ] Host script in cron

Post-Deployment:
[ ] Monitored for 24 hours
[ ] Verified all metrics
[ ] Documented any issues
[ ] Updated runbooks
```

---

**Deployed By**: __________________
**Date**: __________________
**Version**: Sentinel Fixes v1.0
**Status**: [ ] Success [ ] Partial [ ] Rollback Required
