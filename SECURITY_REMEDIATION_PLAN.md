# 🔴 CRITICAL SECURITY REMEDIATION PLAN
## Veris Memory MCP Server - Security Vulnerabilities

**Assessment Date**: 2025-11-14
**Server**: 135.181.4.118
**Security Grade**: D- → Target: A
**Classification**: CRITICAL - Immediate Action Required

---

## 📊 EXECUTIVE SUMMARY

### Current State: CRITICAL VULNERABILITIES
- **Redis (6379)**: Exposed to internet WITHOUT authentication (CVE 9.8/10)
- **Qdrant (6333-6334)**: Vector database exposed without proper auth (CVE 8.5/10)
- **Neo4j (7474, 7687)**: Graph database exposed despite password (CVE 7.5/10)
- **Multiple APIs (8000-9090)**: Global exposure with unknown auth status (CVE 7.0/10)
- **Docker Firewall Bypass**: UFW rules are ineffective for Docker ports

### Root Cause Analysis

1. **Insecure Docker Compose Configuration**
   - File: `docker-compose.yml` (currently deployed)
   - Issue: Port bindings use `"PORT:PORT"` format (binds to 0.0.0.0)
   - Should use: `"127.0.0.1:PORT:PORT"` format (localhost only)
   - Secure version exists: `docker-compose.hetzner.yml` ✅

2. **Docker Bypasses UFW Firewall**
   - Docker manipulates iptables directly via DOCKER-USER chain
   - UFW rules don't apply to Docker published ports
   - Services listen on 0.0.0.0 despite UFW deny rules

3. **Deploy Workflow Uses Wrong Compose File**
   - `.github/workflows/deploy-dev.yml` line 219: uses `docker-compose.yml`
   - Should use: `docker-compose.hetzner.yml` for production deployments

---

## 🚨 PHASED REMEDIATION PLAN

### PHASE 0: IMMEDIATE EMERGENCY RESPONSE (0-30 minutes)
**Priority**: P0-CRITICAL
**Downtime**: Required (5-10 minutes)
**Risk**: System will be briefly offline

#### Actions:
1. **Stop all exposed services immediately**
2. **Switch to secure docker-compose configuration**
3. **Restart with localhost-only bindings**
4. **Add Redis authentication**
5. **Verify all ports are localhost-bound**

#### Implementation:
```bash
# Emergency security lockdown script
# See: scripts/security/emergency-lockdown.sh
```

**Expected Outcome**:
- ✅ All database ports bound to 127.0.0.1 only
- ✅ Redis password-protected
- ✅ External port scanning shows ONLY 22, 80, 443 (if applicable)
- ✅ Services accessible only via localhost or VPN

---

### PHASE 1: INFRASTRUCTURE HARDENING (30-120 minutes)
**Priority**: P1-HIGH
**Downtime**: Minimal (rolling updates possible)

#### 1.1: Docker Firewall Integration
**Goal**: Make Docker respect firewall rules

**Implementation**:
```bash
# Add DOCKER-USER iptables rules
# See: scripts/security/docker-firewall-rules.sh
```

**Actions**:
- Create `/etc/docker/daemon.json` with security settings
- Add DOCKER-USER iptables rules to filter Docker ports
- Implement deny-all default policy for Docker chains
- Whitelist only internal Docker network communication

#### 1.2: Update GitHub Actions Workflow
**Goal**: Prevent deployment of insecure configurations

**Files to Modify**:
- `.github/workflows/deploy-dev.yml` line 219
- Change: `COMPOSE_FILE="docker-compose.yml"`
- To: `COMPOSE_FILE="docker-compose.hetzner.yml"`

**Additional Changes**:
- Add pre-deployment security verification
- Implement automated port scanning check
- Add security test to CI/CD pipeline

#### 1.3: Redis Security Enhancement
**Goal**: Add authentication and rate limiting

**Actions**:
- Add `requirepass` to Redis configuration
- Generate strong password (32+ characters)
- Store in environment variables/secrets
- Update application connection strings
- Enable Redis ACLs for fine-grained access control

#### 1.4: API Authentication Audit
**Goal**: Verify all APIs require authentication

**Services to Audit**:
- Port 8000: Veris Memory MCP Server
- Port 8001: Veris Memory REST API
- Port 8002: Voice-Bot API
- Port 8080: Monitoring Dashboard
- Port 9090: Sentinel Monitoring API

**Verification Steps**:
1. Test each endpoint without authentication
2. Implement/verify API key requirements
3. Add rate limiting to prevent abuse
4. Enable request logging for security monitoring

---

### PHASE 2: ENHANCED SECURITY MEASURES (2-4 hours)
**Priority**: P2-MEDIUM
**Downtime**: None (background hardening)

#### 2.1: VPN/Tailscale Implementation
**Goal**: Secure remote access to admin interfaces

**Recommendation**: Use Tailscale (already configured in hetzner compose)
- Install Tailscale on server
- Configure Tailscale access for Neo4j browser
- Configure Tailscale access for monitoring dashboards
- Remove public access to admin ports

#### 2.2: SSH Hardening
**Goal**: Reduce SSH attack surface

**Actions**:
- Change SSH port from 22 to non-standard port (e.g., 2222)
- Implement SSH key-only authentication (disable password auth)
- Install and configure fail2ban (already active, optimize rules)
- Whitelist specific IPs if possible
- Enable 2FA for SSH (Google Authenticator)

#### 2.3: Network Segmentation
**Goal**: Isolate services into security zones

**Implementation**:
- Create separate Docker networks for different service tiers
- Frontend network (public-facing services)
- Backend network (databases, cache)
- Admin network (monitoring, management)
- Implement network policies to restrict inter-service communication

#### 2.4: Security Monitoring & Alerting
**Goal**: Detect and respond to security incidents

**Components**:
- Deploy Wazuh or OSSEC for intrusion detection
- Configure fail2ban with custom rules for database ports
- Setup log aggregation (ELK stack or similar)
- Configure alerts for:
  - Failed authentication attempts
  - Port scanning activities
  - Unusual network traffic patterns
  - Container escape attempts

---

### PHASE 3: LONG-TERM SECURITY POSTURE (Ongoing)
**Priority**: P3-ONGOING

#### 3.1: Security Automation
- Automated security scanning (daily)
- Automated vulnerability patching
- Automated backup verification
- Automated compliance checks

#### 3.2: Compliance & Documentation
- Document security architecture
- Create incident response playbook
- Establish security review process
- Implement change management procedures

#### 3.3: Regular Security Audits
- Weekly: Automated security scans
- Monthly: Manual security review
- Quarterly: Penetration testing
- Annually: Full security audit

---

## 📋 IMPLEMENTATION CHECKLIST

### Pre-Deployment Verification
- [ ] Backup all data volumes
- [ ] Test rollback procedures
- [ ] Notify stakeholders of maintenance window
- [ ] Prepare rollback scripts

### Phase 0 - Emergency Response
- [ ] Stop all containers
- [ ] Switch to docker-compose.hetzner.yml
- [ ] Add Redis password
- [ ] Restart services with localhost bindings
- [ ] Verify no external port exposure
- [ ] Test service functionality

### Phase 1 - Infrastructure Hardening
- [ ] Configure Docker daemon security
- [ ] Implement DOCKER-USER iptables rules
- [ ] Update deploy-dev.yml workflow
- [ ] Add Redis authentication
- [ ] Audit API authentication
- [ ] Add rate limiting
- [ ] Implement request logging

### Phase 2 - Enhanced Security
- [ ] Deploy Tailscale/VPN
- [ ] Harden SSH configuration
- [ ] Implement network segmentation
- [ ] Deploy monitoring stack
- [ ] Configure security alerts

### Phase 3 - Ongoing Security
- [ ] Establish automated scanning
- [ ] Document security procedures
- [ ] Schedule regular audits
- [ ] Implement compliance checks

---

## 🔒 SECURITY VALIDATION TESTS

### Test 1: External Port Scan
```bash
# From external network
nmap -p 1-65535 135.181.4.118

# Expected Result:
# Only SSH (22 or custom), HTTP (80), HTTPS (443) open
# All database ports (6333, 6334, 6379, 7474, 7687) CLOSED
```

### Test 2: Redis Authentication
```bash
# Should FAIL without password
redis-cli -h localhost ping

# Should SUCCEED with password
redis-cli -h localhost -a <password> ping
```

### Test 3: Database Localhost Binding
```bash
# Check listening addresses
netstat -tlnp | grep -E "(6333|6334|6379|7474|7687)"

# Expected: All should show 127.0.0.1:PORT not 0.0.0.0:PORT
```

### Test 4: Docker Firewall Rules
```bash
# Verify DOCKER-USER chain has deny rules
iptables -L DOCKER-USER -v -n

# Expected: DROP rules for external access to database ports
```

### Test 5: API Authentication
```bash
# Test each API without credentials
curl -I http://135.181.4.118:8000/
curl -I http://135.181.4.118:8001/
curl -I http://135.181.4.118:8002/

# Expected: 401 Unauthorized or 403 Forbidden
```

---

## 🎯 SUCCESS CRITERIA

### Phase 0 Complete When:
- ✅ Zero database ports exposed to internet
- ✅ Redis requires authentication
- ✅ External nmap shows only essential ports
- ✅ All services functional from localhost

### Phase 1 Complete When:
- ✅ Docker firewall rules active and tested
- ✅ Deploy workflow uses secure configuration
- ✅ All APIs require authentication
- ✅ Rate limiting implemented
- ✅ Security logging enabled

### Phase 2 Complete When:
- ✅ VPN access configured for admin interfaces
- ✅ SSH hardened and attack surface reduced
- ✅ Network segmentation implemented
- ✅ Security monitoring active with alerts

### Target Security Grade: A
- Zero critical vulnerabilities
- All high vulnerabilities addressed
- Comprehensive monitoring in place
- Regular security audits scheduled
- Incident response procedures documented

---

## 🚀 QUICK START - EMERGENCY DEPLOYMENT

For immediate security lockdown:

```bash
cd /opt/veris-memory
git checkout -b security-emergency-fix
cp docker-compose.hetzner.yml docker-compose.secure.yml

# Edit to add Redis password
# Then execute emergency lockdown:
./scripts/security/emergency-lockdown.sh
```

---

## 📞 ESCALATION CONTACTS

If issues arise during deployment:
1. Rollback immediately using rollback script
2. Review deployment logs
3. Consult this document for troubleshooting
4. Document any deviations from plan

---

## 📚 REFERENCES

- OWASP Docker Security Cheat Sheet
- CIS Docker Benchmark
- Docker Security Best Practices
- UFW and Docker Integration Guide
- Redis Security Documentation
- Neo4j Security Guide

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Next Review**: After Phase 0 completion
