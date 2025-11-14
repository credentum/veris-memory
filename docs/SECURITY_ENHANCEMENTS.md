# Security Enhancements - Grade B+ → A

**Status:** ✅ Production Ready
**PR:** TBD
**Security Audit:** 2025-11-14 (Post-PR #248)

## Executive Summary

This document describes the security enhancements implemented to improve Veris Memory's security posture from **Grade B+** to **Grade A**. These enhancements build upon the critical security fixes in PR #248 and address recommendations from the security audit.

## What Was Implemented

### 1. Nginx Reverse Proxy with Rate Limiting

**Purpose:** Protect externally exposed services (voice-bot and LiveKit) from DDoS attacks and abuse.

**Implementation:**
- **Nginx service:** `nginx-voice-proxy` container
- **Protected services:**
  - Voice-Bot (8443/HTTPS, 8080/HTTP)
  - LiveKit (7880/WebSocket)

**Rate Limits:**
```
Voice-Bot:  10 requests/second per IP (burst: 20)
LiveKit:    20 requests/second per IP (burst: 50)
```

**Additional Protection:**
- Connection limits per IP (10 for voice-bot, 50 for LiveKit)
- Request body size limits (10MB max)
- Timeout protection against slowloris attacks
- Automatic HTTP → HTTPS redirect

**Files:**
- `dockerfiles/Dockerfile.nginx` - Nginx container
- `docker/nginx/nginx.conf` - Main nginx configuration
- `docker/nginx/conf.d/voice-bot.conf` - Voice-bot proxy config
- `docker/nginx/conf.d/livekit.conf` - LiveKit proxy config
- `docker-compose.voice.yml` - Updated to include nginx service

### 2. Docker Daemon Security Settings

**Purpose:** Harden Docker daemon configuration following industry best practices.

**Settings Applied:**
```json
{
  "icc": false,                    // Disable inter-container communication by default
  "userland-proxy": false,         // Use iptables instead of userland proxy
  "iptables": true,                // Let Docker manage iptables rules
  "no-new-privileges": true,       // Prevent privilege escalation
  "live-restore": true,            // Keep containers running during daemon downtime
  "log-driver": "json-file",       // Structured logging
  "log-opts": {
    "max-size": "10m",             // Prevent unbounded log growth
    "max-file": "3"
  }
}
```

**Applied by:** `scripts/security/docker-firewall-rules.sh` (from PR #248)

### 3. DOCKER-USER Iptables Rules (Defense-in-Depth)

**Purpose:** Ensure Docker respects firewall rules and prevent firewall bypass.

**Rules:**
1. Allow established/related connections
2. Allow localhost (127.0.0.0/8)
3. Allow Docker internal networks (172.16.0.0/12, 10.0.0.0/8)
4. Allow Tailscale VPN (100.64.0.0/10) if detected
5. **Block external access to database ports:**
   - Redis (6379)
   - Qdrant (6333, 6334)
   - Neo4j (7474, 7687)
6. Log dropped packets (for monitoring)

**Persistence:** Systemd service `docker-firewall.service` restores rules on boot.

**Applied by:** `scripts/security/docker-firewall-rules.sh` (from PR #248)

### 4. Pre-commit Security Hooks

**Purpose:** Prevent security regressions during development.

**Enabled Checks:**
- Secret scanning (detect accidentally committed credentials)
- Dependency vulnerability scanning
- Code quality checks
- File permission validation

**Installation:**
```bash
# Hooks are automatically installed via:
sudo bash scripts/apply-security-enhancements.sh
```

**Manual Usage:**
```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run <hook-name>
```

### 5. Automated Security Audits

**Purpose:** Continuous security monitoring and early detection of issues.

**Schedule:** Weekly (Sundays at 2 AM UTC)
**Script:** `scripts/security/security-audit.sh` (from PR #248)
**Logs:** `/var/log/veris-memory-security-audit.log`

**What It Checks:**
- Port exposure analysis
- Authentication configuration
- Docker daemon security settings
- Firewall rule verification
- Service health status
- Known vulnerability patterns

**Manual Execution:**
```bash
sudo bash scripts/security/security-audit.sh
```

## Security Improvements

| Aspect | Before (B+) | After (A) |
|--------|-------------|-----------|
| **Voice-Bot Exposure** | Direct exposure, unlimited requests | Nginx proxy, 10 req/s rate limit |
| **LiveKit Exposure** | Direct exposure, unlimited requests | Nginx proxy, 20 req/s rate limit |
| **DDoS Protection** | None | Multi-layer: rate limiting, connection limits, timeouts |
| **Firewall Bypass** | Docker could bypass UFW | DOCKER-USER rules enforce firewall policy |
| **Development Security** | Manual security checks | Automated pre-commit hooks |
| **Security Monitoring** | Manual, ad-hoc audits | Weekly automated security audits |
| **Attack Surface** | 2 exposed services (unlimited) | 2 exposed services (rate-limited + proxied) |

## Deployment

### Prerequisites

- Root/sudo access to the server
- Docker and Docker Compose installed
- Veris Memory repository cloned to `/opt/veris-memory`

### Option 1: Automated Deployment (Recommended)

```bash
# Clone or pull latest changes
cd /opt/veris-memory
git pull origin main

# Apply all security enhancements
sudo bash scripts/apply-security-enhancements.sh

# Deploy updated services
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d

# Verify deployment
bash scripts/deployment-report.sh dev
```

### Option 2: Manual Step-by-Step

```bash
# 1. Apply Docker daemon security and iptables rules
sudo bash scripts/security/docker-firewall-rules.sh

# 2. Restart Docker daemon (if not done by script)
sudo systemctl restart docker

# 3. Deploy nginx proxy and updated services
cd /opt/veris-memory
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d

# 4. Enable pre-commit hooks (development only)
pip3 install pre-commit
pre-commit install

# 5. Set up cron job for security audits
(crontab -l 2>/dev/null; echo "0 2 * * 0 /opt/veris-memory/scripts/security/security-audit.sh > /var/log/veris-memory-security-audit.log 2>&1") | crontab -
```

## Verification

### 1. Check Nginx Rate Limiting is Active

```bash
# View nginx logs
docker logs nginx-voice-proxy

# Test rate limiting (should see 429 errors after hitting limit)
for i in {1..30}; do curl -s -o /dev/null -w "%{http_code}\n" https://135.181.4.118:8443/health; done
```

Expected: First 10-20 requests succeed (200), subsequent requests fail (429 Too Many Requests)

### 2. Verify Docker Daemon Configuration

```bash
# View daemon.json
sudo cat /etc/docker/daemon.json

# Check Docker is using the configuration
docker info | grep -A10 "Security Options"
```

Expected: `no-new-privileges: true`, logging configured

### 3. Check DOCKER-USER Iptables Rules

```bash
# List DOCKER-USER chain rules
sudo iptables -L DOCKER-USER -n -v --line-numbers

# Verify DROP rules exist for database ports
sudo iptables -L DOCKER-USER -n | grep -E "6379|6333|7474|7687"
```

Expected: DROP rules for ports 6333, 6334, 6379, 7474, 7687

### 4. Test External Database Access is Blocked

```bash
# From external machine (should fail/timeout):
curl http://135.181.4.118:6333     # Qdrant - should timeout
curl http://135.181.4.118:6379     # Redis - should timeout
curl http://135.181.4.118:7474     # Neo4j - should timeout

# From localhost (should work):
ssh user@135.181.4.118
curl http://localhost:6333         # Qdrant - should respond
```

### 5. Verify Pre-commit Hooks

```bash
# Check installed hooks
pre-commit --version
pre-commit run --all-files
```

Expected: Hooks run successfully

### 6. Check Automated Security Audits

```bash
# View cron jobs
crontab -l

# Check if security audit is scheduled
crontab -l | grep security-audit.sh

# Run manual audit
sudo bash scripts/security/security-audit.sh

# View audit logs
tail -100 /var/log/veris-memory-security-audit.log
```

## Architecture Changes

### Before: Direct Exposure
```
Internet → Voice-Bot (8002) [No rate limiting]
Internet → LiveKit (7880) [No rate limiting]
```

### After: Nginx Proxy with Rate Limiting
```
Internet → Nginx (8443/HTTPS) → Voice-Bot (8002) [Rate: 10 req/s]
Internet → Nginx (8080/HTTP)  → Redirect to 8443
Internet → Nginx (7880/WS)    → LiveKit (7880) [Rate: 20 req/s]
```

## Port Mapping Changes

| Service | Old Binding | New Binding | Access |
|---------|-------------|-------------|--------|
| Voice-Bot | `0.0.0.0:8002` | Internal only | Via nginx:8443 |
| LiveKit HTTP | `0.0.0.0:7880` | Internal only | Via nginx:7880 |
| Nginx HTTPS | N/A | `0.0.0.0:8443` | Direct (rate-limited) |
| Nginx HTTP | N/A | `0.0.0.0:8080` | Direct (redirects to HTTPS) |
| Nginx LiveKit | N/A | `0.0.0.0:7880` | Direct (rate-limited proxy) |

**Note:** LiveKit UDP ports (50000-50100) remain directly exposed as required for WebRTC media streams (cannot be proxied by nginx).

## Monitoring and Maintenance

### Daily Monitoring

```bash
# Check for rate limiting events
docker logs --since 24h nginx-voice-proxy | grep limiting

# Check for dropped packets (DOCKER-USER)
sudo dmesg | grep DOCKER-USER-DROP | tail -20

# Check service health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Weekly Tasks

1. Review security audit logs:
   ```bash
   cat /var/log/veris-memory-security-audit.log
   ```

2. Check for failed login attempts or suspicious activity:
   ```bash
   sudo journalctl -u docker --since "1 week ago" | grep -i fail
   ```

3. Review nginx access logs for unusual patterns:
   ```bash
   docker exec nginx-voice-proxy tail -1000 /var/log/nginx/access.log | grep -vE "200|304"
   ```

### Monthly Tasks

1. Review and update rate limiting thresholds if needed
2. Check for Docker and nginx security updates
3. Run comprehensive security audit:
   ```bash
   sudo bash scripts/security/security-audit.sh
   ```

## Troubleshooting

### Issue: Rate limiting too aggressive

**Symptoms:** Legitimate users getting 429 errors

**Solution:** Adjust rate limits in nginx configuration

```bash
# Edit voice-bot rate limit
vim docker/nginx/conf.d/voice-bot.conf
# Change: limit_req zone=voicebot_limit burst=20 nodelay;
# To:     limit_req zone=voicebot_limit burst=50 nodelay;

# Rebuild and restart nginx
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d nginx-voice-proxy
```

### Issue: Docker firewall rules blocking internal communication

**Symptoms:** Services can't communicate with each other

**Solution:** Verify Docker network ranges in DOCKER-USER rules

```bash
# Check Docker networks
docker network inspect veris-memory-dev_context-store-network | grep Subnet

# Update firewall rules if needed
sudo iptables -I DOCKER-USER -s <NETWORK_CIDR> -d <NETWORK_CIDR> -j RETURN
```

### Issue: Pre-commit hooks failing

**Symptoms:** Git commits are blocked by pre-commit hooks

**Solution:** Fix the security issues or skip hooks (not recommended)

```bash
# Fix the issues (recommended)
pre-commit run --all-files

# Temporary skip (emergency only)
git commit --no-verify -m "message"
```

## Rollback Procedure

If you need to rollback these security enhancements:

```bash
# 1. Remove nginx proxy
docker compose -f docker-compose.voice.yml down nginx-voice-proxy

# 2. Restore direct port bindings in docker-compose.voice.yml
#    (revert changes to livekit and voice-bot port mappings)

# 3. Flush DOCKER-USER rules (optional, defense-in-depth)
sudo iptables -F DOCKER-USER

# 4. Restore original Docker daemon.json (if backup exists)
sudo cp /etc/docker/daemon.json.backup-<timestamp> /etc/docker/daemon.json
sudo systemctl restart docker

# 5. Remove cron job
crontab -l | grep -v security-audit.sh | crontab -

# 6. Disable pre-commit hooks
pre-commit uninstall
```

## Security Grade Compliance

### Grade A Requirements Met

- ✅ **Perimeter Security:** Rate limiting and DDoS protection
- ✅ **Defense-in-Depth:** Multi-layer security (nginx + iptables + Docker daemon)
- ✅ **Automated Monitoring:** Weekly security audits
- ✅ **Development Security:** Pre-commit hooks prevent regressions
- ✅ **Logging and Alerting:** Comprehensive logging for all security events
- ✅ **Incident Response:** Emergency lockdown scripts available
- ✅ **Documentation:** Complete security documentation

### Remaining Recommendations for Grade A+

1. **External DDoS Protection:** Consider Cloudflare or AWS Shield
2. **Web Application Firewall (WAF):** Consider ModSecurity or cloud WAF
3. **Intrusion Detection System (IDS):** Consider OSSEC or Wazuh
4. **Security Information and Event Management (SIEM):** Consider ELK stack with security plugins

## References

- [PR #248: CRITICAL Security Fixes](https://github.com/credentum/veris-memory/pull/248)
- [Security Audit Report (2025-11-14)](../security-audit-pr248-verification.json)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Nginx Rate Limiting](https://www.nginx.com/blog/rate-limiting-nginx/)

## Support

For questions or issues related to these security enhancements:

1. Check the troubleshooting section above
2. Review security audit logs: `/var/log/veris-memory-security-audit.log`
3. Run manual security audit: `sudo bash scripts/security/security-audit.sh`
4. Contact the security team

---

**Last Updated:** 2025-11-14
**Maintainer:** Veris Memory Security Team
**Status:** ✅ Production Ready
