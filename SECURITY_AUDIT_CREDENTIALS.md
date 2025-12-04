# Security Audit Report: Docker Compose Credentials & Environment Variables

**Audit Date**: 2025-11-15
**Auditor**: Claude (Automated Security Review)
**Scope**: Docker Compose configurations and environment variable handling
**Repository**: veris-memory

---

## Executive Summary

This security audit identified **4 CRITICAL** and **5 WARNING** level issues related to credential management in Docker Compose configurations. The primary concerns are hardcoded default passwords, missing authentication in production configurations, and .env file tracking issues.

### Risk Summary
- **Critical Issues**: 4
- **Warning Issues**: 5
- **Informational**: 3
- **Good Practices**: 4

---

## Critical Issues

### 🔴 CRITICAL-1: Hardcoded Read-Only Password in Main Configuration

**File**: `docker-compose.yml` (lines 15, 58)
**Severity**: CRITICAL
**Risk**: Password exposed in version control

**Issue**:
```yaml
- NEO4J_RO_PASSWORD=${NEO4J_RO_PASSWORD:-readonly_secure_2024!}
```

**Impact**:
- Default password `readonly_secure_2024!` is hardcoded and publicly visible
- Anyone with repository access can use this password
- Password is used in 4 service definitions (context-store, api, monitoring-dashboard, sentinel)
- Compromises read-only Neo4j access if environment variable not set

**Recommendation**:
```yaml
# Remove default - require explicit environment variable
- NEO4J_RO_PASSWORD=${NEO4J_RO_PASSWORD}

# Add validation in deployment scripts
if [ -z "$NEO4J_RO_PASSWORD" ]; then
  echo "ERROR: NEO4J_RO_PASSWORD must be set"
  exit 1
fi
```

**References**:
- docker-compose.yml:15
- docker-compose.yml:58

---

### 🔴 CRITICAL-2: Missing Redis Authentication in Production

**Files**:
- `docker-compose.prod.yml` (line 116)
- `docker-compose.hetzner.yml` (line 150-161)
- `docker-compose.simple.yml` (line 19-27)

**Severity**: CRITICAL
**Risk**: Unauthenticated database access in production

**Issue**:
```yaml
# docker-compose.prod.yml - NO PASSWORD!
command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

# docker-compose.hetzner.yml - NO PASSWORD!
command: >
  redis-server
  --appendonly yes
  --maxmemory 8gb
  --maxmemory-policy allkeys-lru
```

**Impact**:
- Redis runs without authentication in production deployments
- Anyone with network access can read/write cache data
- Potential for cache poisoning attacks
- Data exfiltration risk

**Recommendation**:
```yaml
# docker-compose.prod.yml
redis:
  command: >
    redis-server
    --requirepass ${REDIS_PASSWORD}
    --appendonly yes
    --maxmemory 512mb
    --maxmemory-policy allkeys-lru
    --protected-mode yes
  environment:
    - REDIS_PASSWORD=${REDIS_PASSWORD}
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
```

**References**:
- docker-compose.prod.yml:116
- docker-compose.hetzner.yml:150-161
- docker-compose.simple.yml:19-27

---

### 🔴 CRITICAL-3: Weak Development Default Passwords

**File**: `docker-compose.yml` (lines 30, 45)
**Severity**: CRITICAL (if used in production)
**Risk**: Weak default credentials

**Issue**:
```yaml
- NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-devpassword123}
--requirepass ${REDIS_PASSWORD:-devpassword123}
```

**Impact**:
- Simple, guessable default password "devpassword123"
- Risk if developers accidentally use dev config in production
- Common attack vector: developers copy dev configs to production

**Recommendation**:
1. Add clear warnings in dev config file header
2. Use randomized passwords generated on first run
3. Add validation to prevent dev config usage in production

```yaml
# Add to docker-compose.yml header
# ⚠️ DEVELOPMENT ONLY - DO NOT USE IN PRODUCTION
# This configuration uses weak default passwords for development convenience
# For production, use docker-compose.prod.yml or docker-compose.secure.yml

# Better approach - generate random password on startup
environment:
  - NEO4J_PASSWORD=${NEO4J_PASSWORD:-$(openssl rand -base64 32)}
```

**References**:
- docker-compose.yml:30
- docker-compose.yml:45

---

### 🔴 CRITICAL-4: .env Files Tracked in Git History

**Files**:
- `config/production_recall_config.env` (currently tracked)
- Historical: `production_recall_config.env` (removed but in history)

**Severity**: CRITICAL
**Risk**: Potential secrets exposure in git history

**Issue**:
```bash
$ git log --all --name-only | grep '\.env$'
config/production_recall_config.env
production_recall_config.env
```

**Impact**:
- .env files may contain secrets in git history
- Even if removed, secrets remain in git history forever
- Current file `config/production_recall_config.env` is still tracked
- Misnaming: This file contains config, not environment secrets

**Recommendation**:
1. Rename config file to `.conf` or `.config` extension
2. Add to .gitignore: `config/**/*.env`
3. Audit git history for any actual secrets
4. If secrets found, rotate all credentials immediately
5. Consider using git-filter-repo to remove from history (DESTRUCTIVE)

```bash
# Immediate action
mv config/production_recall_config.env config/production_recall.conf
git add config/production_recall.conf
git rm config/production_recall_config.env

# Add to .gitignore
echo "config/**/*.env" >> .gitignore

# Audit history for secrets
git log -p config/production_recall_config.env production_recall_config.env | grep -iE '(password|secret|key|token)'
```

**References**:
- config/production_recall_config.env (currently tracked)
- Commits: fe1e028, 7eed4bd

---

## Warning Issues

### ⚠️ WARNING-1: Test Passwords in Docker Compose Test File

**File**: `docker-compose.test.yml` (lines 28, 57)
**Severity**: WARNING
**Risk**: Low (test environment only)

**Issue**:
```yaml
- NEO4J_AUTH=neo4j/test-password
- NEO4J_PASSWORD=test-password
```

**Impact**:
- Hardcoded test password "test-password"
- Low risk if only used in CI/CD
- Risk if test environment is accessible externally

**Recommendation**:
- Add comment clarifying this is for CI/CD only
- Ensure test environment is not publicly accessible
- Consider using randomly generated test passwords

**References**:
- docker-compose.test.yml:28
- docker-compose.test.yml:57

---

### ⚠️ WARNING-2: Port Binding on Docker Bridge Network

**File**: `docker-compose.yml` (line 9)
**Severity**: WARNING
**Risk**: Medium (depends on firewall configuration)

**Issue**:
```yaml
ports:
  - "8000:8000"  # SECURITY: Accessible via Docker bridge network
```

**Comment says**: "external access blocked by firewall"

**Impact**:
- Port 8000 bound to all interfaces (0.0.0.0:8000)
- Relies on external firewall for security
- If firewall misconfigured, service is publicly exposed
- Better: bind to localhost explicitly

**Recommendation**:
```yaml
ports:
  - "127.0.0.1:8000:8000"  # Bind to localhost only
```

**Note**: This is already correct in most other configs (prod, secure, hetzner)

**References**:
- docker-compose.yml:9

---

### ⚠️ WARNING-3: Multiple .env Template Files Tracked in Git

**Files**: All `.env.*` template files tracked in repository
**Severity**: WARNING
**Risk**: Low (templates with placeholders)

**Files Tracked**:
- `.env.example` ✅ (good - example file)
- `.env.hetzner` ⚠️ (template but misleading name)
- `.env.hetzner.template` ✅ (clear template)
- `.env.production.template` ✅ (clear template)
- `.env.sentinel.template` ✅ (clear template)
- `.env.voice.example` ✅ (clear example)

**Issue**:
The file `.env.hetzner` is tracked but should be named `.env.hetzner.template` to clarify it's a template, not an actual environment file.

**Recommendation**:
```bash
# Rename to clarify it's a template
git mv .env.hetzner .env.hetzner.example

# Or remove if .env.hetzner.template already exists
git rm .env.hetzner
```

**References**:
- .env.hetzner (duplicate of .env.hetzner.template)

---

### ⚠️ WARNING-4: Placeholder Example Keys Too Realistic

**File**: `.env.example` (line 25)
**Severity**: WARNING
**Risk**: Low (example key could be mistaken for real key)

**Issue**:
```bash
# Example: API_KEY_MCP=vmk_mcp_d9ef8d8699ca748e5a484c5026ecdc2a:mcp_server:writer:true
```

**Impact**:
- Realistic-looking example key might be copied directly
- Developers might not realize they need to generate their own
- Low risk but could lead to configuration errors

**Recommendation**:
```bash
# Make it more obviously a placeholder
# Example: API_KEY_MCP=vmk_mcp_YOUR_RANDOM_HEX_HERE:mcp_server:writer:true
# Generate with: openssl rand -hex 16
```

**References**:
- .env.example:25

---

### ⚠️ WARNING-5: Inconsistent Redis Password Handling

**Files**: Various docker-compose files
**Severity**: WARNING
**Risk**: Medium (configuration inconsistency)

**Issue**:
Different Redis configurations across environments:

```yaml
# docker-compose.yml - CORRECT (with password)
- REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
command: redis-server --requirepass ${REDIS_PASSWORD}

# docker-compose.prod.yml - MISSING PASSWORD ❌
environment:
  - REDIS_URL=redis://redis:6379
command: redis-server --appendonly yes

# docker-compose.secure.yml - CORRECT (with password)
- REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
command: redis-server --requirepass ${REDIS_PASSWORD}
```

**Impact**:
- Inconsistent security posture across environments
- Easy to misconfigure production
- Connection errors if client expects password but server doesn't require it

**Recommendation**:
Standardize Redis authentication across ALL environments:
1. Always require password in server command
2. Always include password in REDIS_URL
3. Use strong default for dev, require env var for prod

**References**:
- docker-compose.yml (correct)
- docker-compose.prod.yml (missing)
- docker-compose.secure.yml (correct)
- docker-compose.hetzner.yml (missing)

---

## Informational Issues

### ℹ️ INFO-1: Docker Compose Port Comments Could Be Clearer

Many files have comments like:
```yaml
- "127.0.0.1:8000:8000"  # SECURITY: Bind to localhost only
```

**Suggestion**: Add firewall/network access method info
```yaml
- "127.0.0.1:8000:8000"  # Localhost only - access via SSH tunnel or Tailscale
```

---

### ℹ️ INFO-2: Missing Environment Variable Validation

No startup validation for required environment variables.

**Suggestion**: Add entrypoint script to validate:
```bash
#!/bin/bash
# validate-env.sh
required_vars=("NEO4J_PASSWORD" "REDIS_PASSWORD" "API_KEY_MCP")
for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "ERROR: $var is required but not set"
    exit 1
  fi
done
exec "$@"
```

---

### ℹ️ INFO-3: Consider Using Docker Secrets

For production deployments, consider using Docker Swarm secrets instead of environment variables:

```yaml
secrets:
  neo4j_password:
    external: true
  redis_password:
    external: true

services:
  neo4j:
    secrets:
      - neo4j_password
    environment:
      - NEO4J_AUTH_FILE=/run/secrets/neo4j_password
```

---

## Good Security Practices Found ✅

### 1. Localhost Binding in Most Configs
Most production configs correctly bind to 127.0.0.1:
```yaml
- "127.0.0.1:8000:8000"  # ✅ Good
- "127.0.0.1:7474:7474"  # ✅ Good
- "127.0.0.1:6379:6379"  # ✅ Good
```

### 2. .gitignore Properly Configured
```
.env
.env.local
.env.test.local
.env.production.local
```
✅ Main .env files are properly ignored

### 3. Security Comments Throughout
Good security awareness shown in comments:
```yaml
# SECURITY: Bind to localhost only
# SECURITY: Redis with password auth
# SECURITY: Password required
```

### 4. Secure Configuration Template
`docker-compose.secure.yml` demonstrates good security practices:
- All ports on localhost
- Resource limits
- Health checks
- No new privileges
- Logging configuration

---

## Summary of Files Analyzed

| File | Status | Issues |
|------|--------|--------|
| docker-compose.yml | ⚠️ Issues | Hardcoded RO password, port binding |
| docker-compose.yml | ⚠️ Issues | Weak dev passwords |
| docker-compose.prod.yml | 🔴 Critical | Missing Redis password |
| docker-compose.secure.yml | ✅ Good | Best practices followed |
| docker-compose.hetzner.yml | 🔴 Critical | Missing Redis password |
| docker-compose.simple.yml | 🔴 Critical | Missing Redis password |
| docker-compose.test.yml | ⚠️ Minor | Test passwords hardcoded |
| docker-compose.voice.yml | ✅ Good | Proper env var usage |
| docker-compose.debug.yml | Not analyzed | |
| .env.example | ✅ Good | Proper template |
| .env.hetzner | ⚠️ Minor | Naming confusion |
| .gitignore | ✅ Good | Proper .env exclusions |

---

## Recommendations Priority

### Immediate Action Required (Critical)
1. ✅ **Remove hardcoded default password** from docker-compose.yml (NEO4J_RO_PASSWORD)
2. ✅ **Add Redis authentication** to prod/hetzner/simple configs
3. ✅ **Rename production_recall_config.env** to .conf extension
4. ✅ **Audit git history** for any actual secrets in .env files

### Short Term (Within 1 Week)
5. Standardize Redis password handling across all configs
6. Add environment variable validation scripts
7. Update docker-compose.yml with stronger warnings
8. Fix port binding in docker-compose.yml to use 127.0.0.1

### Medium Term (Within 1 Month)
9. Implement Docker secrets for production
10. Add automated security scanning to CI/CD
11. Create deployment validation script
12. Document credential rotation procedures

---

## Testing Recommendations

### Test Redis Authentication
```bash
# Should FAIL without password (currently succeeds in prod!)
docker exec veris-memory-prod-redis redis-cli ping

# Should succeed with password
docker exec veris-memory-prod-redis redis-cli -a "${REDIS_PASSWORD}" ping
```

### Test Environment Variable Requirements
```bash
# Should fail without NEO4J_PASSWORD
unset NEO4J_PASSWORD
docker-compose -f docker-compose.prod.yml up -d  # Should error

# Should succeed with password
export NEO4J_PASSWORD=$(openssl rand -base64 32)
docker-compose -f docker-compose.prod.yml up -d  # Should start
```

---

## Compliance & Best Practices

### OWASP Top 10 Alignment
- ✅ A02:2021 – Cryptographic Failures (passwords should be in secrets, not env vars)
- ✅ A05:2021 – Security Misconfiguration (Redis without auth, default passwords)
- ✅ A07:2021 – Identification and Authentication Failures (weak dev passwords)

### CIS Docker Benchmark
- ✅ 5.3 Ensure that containers do not share the host's network namespace (using bridge)
- ✅ 5.9 Ensure that the host's process namespace is not shared (not using host PID)
- ⚠️ 5.25 Ensure that container health is checked at runtime (some configs missing health checks)

### NIST Cybersecurity Framework
- Identify: ✅ Credential inventory complete
- Protect: ⚠️ Some credentials not properly protected
- Detect: ⚠️ No monitoring for credential misuse
- Respond: ⚠️ No credential rotation procedures documented
- Recover: ⚠️ No credential recovery plan

---

## Conclusion

The veris-memory repository demonstrates good security awareness with proper localhost binding and .gitignore configuration. However, **critical issues exist with hardcoded passwords and missing authentication in production configurations** that must be addressed immediately.

The most urgent fixes are:
1. Remove hardcoded `readonly_secure_2024!` password
2. Add Redis authentication to production configs
3. Audit and clean up .env file tracking in git

Implementing these fixes will significantly improve the security posture of the deployment infrastructure.

---

**Report Generated**: 2025-11-15
**Next Review**: Recommended after fixes implemented
**Contact**: Security team for questions on this audit
