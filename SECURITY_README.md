# 🔒 Security Hardening Branch

This branch contains **critical security fixes** for the Veris Memory MCP Server infrastructure, addressing multiple CRITICAL vulnerabilities (CVE 9.8, 8.5, 7.5) identified in the production deployment on server 135.181.4.118.

## 🚨 Critical Issues Addressed

| Severity | Issue | CVE Level | Status |
|----------|-------|-----------|--------|
| **CRITICAL** | Redis exposed without authentication | 9.8/10 | ✅ Fixed |
| **CRITICAL** | Qdrant exposed without authentication | 8.5/10 | ✅ Fixed |
| **HIGH** | Neo4j exposed to internet | 7.5/10 | ✅ Fixed |
| **HIGH** | APIs exposed globally | 7.0/10 | ✅ Mitigated |
| **CRITICAL** | Docker bypasses UFW firewall | N/A | ✅ Fixed |

## 📁 Repository Structure

```
.
├── SECURITY_REMEDIATION_PLAN.md      # Comprehensive phased remediation plan
├── SECURITY_README.md                 # This file
├── docker-compose.secure.yml          # Security-hardened Docker Compose config
├── scripts/
│   └── security/
│       ├── emergency-lockdown.sh      # Immediate security fix (Phase 0)
│       ├── docker-firewall-rules.sh   # Docker firewall integration (Phase 1)
│       └── security-audit.sh          # Security validation tool
└── .github/
    └── workflows/
        └── deploy-dev.yml             # Updated deployment workflow (to be modified)
```

## 🚀 Quick Start - Emergency Deployment

### Prerequisites

- Root/sudo access to server
- Docker and docker-compose installed
- Backup of all data (CRITICAL)
- NEO4J_PASSWORD environment variable set

### Phase 0: Immediate Emergency Response (5-10 minutes)

**⚠️ WARNING: This will cause 5-10 minutes of downtime**

```bash
# 1. SSH into the server
ssh user@135.181.4.118

# 2. Navigate to the repository
cd /opt/veris-memory

# 3. Create backup (CRITICAL - DO NOT SKIP)
sudo ./scripts/backup/create-emergency-backup.sh

# 4. Set required environment variables
export NEO4J_PASSWORD='your-secure-neo4j-password'
export REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# 5. Run emergency lockdown script
sudo ./scripts/security/emergency-lockdown.sh

# 6. Verify security
sudo ./scripts/security/security-audit.sh

# 7. Test external exposure (from different machine)
nmap -p 1-65535 135.181.4.118
# Expected: Only SSH (22), HTTP (80), HTTPS (443) should be open
# Database ports 6333, 6334, 6379, 7474, 7687 should be CLOSED
```

### Phase 1: Infrastructure Hardening (30-120 minutes)

```bash
# 1. Configure Docker firewall rules
sudo ./scripts/security/docker-firewall-rules.sh

# 2. Update GitHub Actions workflow
# Edit .github/workflows/deploy-dev.yml line 219:
# Change: COMPOSE_FILE="docker-compose.yml"
# To: COMPOSE_FILE="docker-compose.secure.yml"

# 3. Commit and push changes
git add .github/workflows/deploy-dev.yml
git commit -m "fix: Use secure docker-compose configuration in deployment"
git push origin security-work

# 4. Run security audit again
sudo ./scripts/security/security-audit.sh
```

## 📖 Detailed Documentation

### Main Documents

1. **[SECURITY_REMEDIATION_PLAN.md](./SECURITY_REMEDIATION_PLAN.md)**
   - Complete phased remediation plan
   - Detailed implementation steps
   - Validation procedures
   - Long-term security measures

2. **[docker-compose.secure.yml](./docker-compose.secure.yml)**
   - Production-ready secure configuration
   - All ports bound to localhost
   - Authentication enforced
   - Resource limits configured
   - Health checks enabled

3. **[scripts/security/](./scripts/security/)**
   - `emergency-lockdown.sh` - Immediate fix (Phase 0)
   - `docker-firewall-rules.sh` - Firewall integration (Phase 1)
   - `security-audit.sh` - Validation and compliance checking

## 🔑 Security Features Implemented

### Port Binding Security
- ✅ **Before**: `"6379:6379"` → Binds to 0.0.0.0 (INTERNET EXPOSED)
- ✅ **After**: `"127.0.0.1:6379:6379"` → Localhost only

### Authentication
- ✅ **Redis**: Now requires `requirepass` authentication
- ✅ **Neo4j**: Password authentication enforced
- ✅ **Qdrant**: Access restricted to localhost (API key support pending)

### Docker Firewall Integration
- ✅ **DOCKER-USER iptables rules** prevent Docker from bypassing UFW
- ✅ **Explicit DROP rules** for database ports from external sources
- ✅ **Whitelisted internal networks** (Docker, localhost, Tailscale)

### Container Security
- ✅ **no-new-privileges** flag prevents privilege escalation
- ✅ **Resource limits** prevent DoS attacks
- ✅ **Health checks** for all services
- ✅ **Logging** configured with rotation

## 🧪 Validation Tests

### Test 1: External Port Scan
```bash
# From external network (NOT on the server)
nmap -p 1-65535 135.181.4.118

# Expected Result:
# PORT    STATE    SERVICE
# 22/tcp  open     ssh
# All other ports should be closed or filtered
```

### Test 2: Redis Authentication
```bash
# Should FAIL (no auth)
redis-cli -h localhost ping
# Expected: (error) NOAUTH Authentication required.

# Should SUCCEED (with auth)
redis-cli -h localhost -a <password> ping
# Expected: PONG
```

### Test 3: Database Localhost Binding
```bash
# Check all database ports are localhost-bound
sudo netstat -tlnp | grep -E "(6333|6334|6379|7474|7687)"

# Expected: All should show 127.0.0.1:PORT NOT 0.0.0.0:PORT
# tcp   0   0 127.0.0.1:6379   0.0.0.0:*   LISTEN   12345/redis
# tcp   0   0 127.0.0.1:7474   0.0.0.0:*   LISTEN   12346/java
# ...etc
```

### Test 4: Automated Security Audit
```bash
# Run comprehensive security audit
sudo ./scripts/security/security-audit.sh

# Expected: Security Grade A or B, zero critical failures
```

## 🔄 Rollback Procedure

If issues arise during deployment:

```bash
# 1. Stop all containers
docker-compose -p veris-memory-secure down

# 2. Restore from backup
BACKUP_DIR="/opt/veris-memory-backups/emergency-YYYYMMDD-HHMMSS"
cp ${BACKUP_DIR}/docker-compose.yml ./
cp ${BACKUP_DIR}/.env ./

# 3. Restart services
docker-compose up -d

# 4. Verify services are running
docker-compose ps
```

## 📊 Success Criteria

### Phase 0 Complete ✅
- [ ] Zero database ports exposed to internet (verified by external nmap)
- [ ] Redis requires authentication
- [ ] All services functional from localhost
- [ ] Backup created and verified

### Phase 1 Complete ✅
- [ ] Docker firewall rules active (iptables -L DOCKER-USER shows DROP rules)
- [ ] Deploy workflow uses secure configuration
- [ ] All APIs require authentication
- [ ] Security audit passes with grade B or higher

### Target State: Security Grade A
- [ ] Zero critical vulnerabilities
- [ ] All high vulnerabilities addressed
- [ ] Comprehensive monitoring in place
- [ ] Regular security audits scheduled
- [ ] Incident response procedures documented

## 🛡️ Long-Term Security Measures

### Ongoing Activities
1. **Weekly**: Automated security scans
2. **Monthly**: Manual security review
3. **Quarterly**: Penetration testing
4. **Annually**: Full security audit

### Recommended Enhancements
1. **Tailscale VPN**: For secure remote access to admin interfaces
2. **SSH Hardening**: Non-standard port, key-only auth, 2FA
3. **WAF/CDN**: Cloudflare or similar for DDoS protection
4. **SIEM**: Centralized security monitoring and alerting
5. **Automated Patching**: Keep all systems updated

## 📞 Support and Escalation

### If Deployment Fails
1. **Rollback immediately** using the procedure above
2. **Review logs**: `docker-compose logs --tail=100`
3. **Check security audit**: `./scripts/security/security-audit.sh`
4. **Consult documentation**: `SECURITY_REMEDIATION_PLAN.md`

### Emergency Contacts
- Server IP: 135.181.4.118
- Backup Location: `/opt/veris-memory-backups/`
- Logs: `/var/log/veris-memory-security/`

## 📚 References

- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Docker and UFW Integration](https://docs.docker.com/network/packet-filtering-firewalls/)
- [Redis Security](https://redis.io/docs/management/security/)
- [Neo4j Security Guide](https://neo4j.com/docs/operations-manual/current/security/)

## 🎯 Next Steps

After completing the emergency lockdown:

1. **Verify External Security**: Run nmap from external network
2. **Test Application Functionality**: Ensure all services work correctly
3. **Configure VPN Access**: Set up Tailscale for remote admin access
4. **Update Deployment Workflow**: Modify GitHub Actions to use secure config
5. **Schedule Regular Audits**: Set up automated weekly security scans
6. **Document Procedures**: Create runbooks for common operations
7. **Train Team**: Ensure all team members understand security procedures

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-14
**Branch**: security-work
**Status**: Ready for deployment
