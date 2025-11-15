# GitHub Secrets Quick Start Guide

**TL;DR: YES, add REDIS_PASSWORD to GitHub Secrets!**

---

## 🔴 CRITICAL: Missing Secrets (Add Immediately)

### 1. REDIS_PASSWORD
**Status**: ❌ NOT in GitHub Secrets (currently auto-generated on each deployment)
**Impact**: Password changes on every deployment, no central management
**Priority**: 🔴 CRITICAL

**How to add:**
```bash
# Generate password
openssl rand -base64 32 | tr -d "=+/" | cut -c1-32

# Add to GitHub:
# Repository → Settings → Secrets and variables → Actions → New repository secret
Name: REDIS_PASSWORD
Value: <paste generated password>
```

### 2. NEO4J_RO_PASSWORD
**Status**: ⚠️ Hardcoded default: `readonly_secure_2024!`
**Impact**: Exposed password in repository
**Priority**: 🟠 HIGH

**How to add:**
```bash
# Generate password
openssl rand -base64 32

# Add to GitHub:
Name: NEO4J_RO_PASSWORD
Value: <paste generated password>
```

---

## ✅ Currently Configured Secrets

These are already in GitHub Secrets (no action needed):

### Infrastructure (Already Set ✅)
- `HETZNER_SSH_KEY` - SSH private key
- `HETZNER_USER` - SSH username
- `HETZNER_HOST` - Server IP/hostname

### Database (Partial ⚠️)
- `NEO4J_PASSWORD` - Dev database ✅
- `NEO4J_PROD_PASSWORD` - Production database ✅
- `REDIS_PASSWORD` - ❌ **MISSING - ADD THIS!**
- `NEO4J_RO_PASSWORD` - ❌ **MISSING - ADD THIS!**

### API Authentication (Already Set ✅)
- `API_KEY_MCP` - MCP server
- `SENTINEL_API_KEY` - Sentinel monitoring
- `API_KEY_VOICEBOT` - Voice bot

### Voice Platform (Already Set ✅)
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_API_WEBSOCKET`
- `OPENAI_API_KEY`

### Monitoring (Already Set ✅)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `HOST_CHECK_SECRET`

### Production Only (Already Set ✅)
- `TAILSCALE_AUTHKEY`

---

## 📋 Complete Setup Checklist

### Step 1: Add Missing Critical Secrets

```bash
# Generate REDIS_PASSWORD
export REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "REDIS_PASSWORD=$REDIS_PASSWORD"
# Copy this password and add to GitHub Secrets

# Generate NEO4J_RO_PASSWORD
export NEO4J_RO_PASSWORD=$(openssl rand -base64 32)
echo "NEO4J_RO_PASSWORD=$NEO4J_RO_PASSWORD"
# Copy this password and add to GitHub Secrets
```

### Step 2: Add to GitHub
1. Go to: https://github.com/credentum/veris-memory/settings/secrets/actions
2. Click "New repository secret"
3. Add each secret:
   - Name: `REDIS_PASSWORD`
   - Value: <paste from Step 1>
4. Repeat for `NEO4J_RO_PASSWORD`

### Step 3: Verify Configuration
After adding secrets, verify they appear in the list:
- Repository → Settings → Secrets and variables → Actions
- You should see both new secrets listed

---

## 🚀 Why This Matters

### Current Situation (Without REDIS_PASSWORD in Secrets)
```bash
# deploy-dev.sh generates random password on EVERY deployment
if [ -z '$REDIS_PASSWORD' ]; then
  export REDIS_PASSWORD=$(openssl rand -base64 32)  # Different each time!
fi
```

**Problems:**
- ❌ Password changes break active connections
- ❌ No audit trail of what password was used
- ❌ Can't troubleshoot connection issues
- ❌ Production configs have NO Redis auth at all!

### After Adding REDIS_PASSWORD to Secrets
```bash
# deploy-dev.sh uses consistent password from GitHub
export REDIS_PASSWORD='$REDIS_PASSWORD'  # Same password every time!
```

**Benefits:**
- ✅ Consistent password across deployments
- ✅ Centrally managed in GitHub
- ✅ Audit trail of deployments
- ✅ Secure and encrypted storage
- ✅ Can rotate on schedule

---

## 🔧 What Gets Fixed

### Files That Will Use REDIS_PASSWORD from Secrets

1. **deploy-dev.sh** (line 47)
   - Currently: Generates random password if not set
   - After: Uses password from GitHub Secrets

2. **docker-compose.yml** (lines 16, 59, 185, 227)
   - Already configured to use `${REDIS_PASSWORD}`
   - Will use value from GitHub Secrets

3. **docker-compose.prod.yml** (line 116)
   - ❌ Currently: NO PASSWORD (needs fix)
   - After: Add password requirement

4. **docker-compose.hetzner.yml** (line 150-161)
   - ❌ Currently: NO PASSWORD (needs fix)
   - After: Add password requirement

5. **docker-compose.simple.yml** (line 19-27)
   - ❌ Currently: NO PASSWORD (needs fix)
   - After: Add password requirement

---

## 📊 Security Impact Assessment

### Before (Current State)
| Component | Auth Status | Risk Level | Issue |
|-----------|-------------|------------|-------|
| Dev Redis | Password (random) | 🟡 MEDIUM | Changes each deploy |
| Prod Redis | ❌ NO AUTH | 🔴 CRITICAL | Anyone can access |
| Hetzner Redis | ❌ NO AUTH | 🔴 CRITICAL | Anyone can access |
| Dev Neo4j | Password ✅ | 🟢 LOW | Properly secured |
| Prod Neo4j | Password ✅ | 🟢 LOW | Properly secured |
| Neo4j RO | Hardcoded default | 🔴 CRITICAL | Public password |

### After (Adding Secrets)
| Component | Auth Status | Risk Level | Issue |
|-----------|-------------|------------|-------|
| Dev Redis | Password ✅ | 🟢 LOW | Fixed from Secrets |
| Prod Redis | Password ✅ | 🟢 LOW | Fixed from Secrets |
| Hetzner Redis | Password ✅ | 🟢 LOW | Fixed from Secrets |
| Dev Neo4j | Password ✅ | 🟢 LOW | No change |
| Prod Neo4j | Password ✅ | 🟢 LOW | No change |
| Neo4j RO | Password ✅ | 🟢 LOW | Fixed from Secrets |

---

## 🎯 Action Items Summary

### Immediate (Critical)
1. ✅ Generate `REDIS_PASSWORD`
2. ✅ Add `REDIS_PASSWORD` to GitHub Secrets
3. ✅ Generate `NEO4J_RO_PASSWORD`
4. ✅ Add `NEO4J_RO_PASSWORD` to GitHub Secrets

### Short Term (This Week)
5. Fix `docker-compose.prod.yml` to require Redis password
6. Fix `docker-compose.hetzner.yml` to require Redis password
7. Fix `docker-compose.simple.yml` to require Redis password
8. Remove hardcoded `readonly_secure_2024!` from `docker-compose.yml`

### Medium Term (This Month)
9. Set up secret rotation schedule
10. Document rotation procedures
11. Add secret validation to CI/CD
12. Test disaster recovery with rotated secrets

---

## 💡 Pro Tips

### Testing Secrets Locally
```bash
# SSH to server
ssh user@server

# Check if Redis password is set
docker exec veris-memory-dev-redis-1 redis-cli ping
# Should fail without password after fix

docker exec veris-memory-dev-redis-1 redis-cli -a "$REDIS_PASSWORD" ping
# Should return: PONG
```

### Rotating Secrets Safely
```bash
# 1. Generate new password
NEW_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# 2. Update GitHub Secret first
# Repository → Settings → Secrets → REDIS_PASSWORD → Update

# 3. Trigger deployment
# Deployment will update .env and restart services with new password

# 4. Verify
# Test connection with new password
```

### Emergency Rollback
If deployment fails after adding secrets:
```bash
# SSH to server
ssh user@server
cd /opt/veris-memory

# Check logs
docker compose -p veris-memory-dev logs redis

# If password issue, temporarily fix .env
vi .env  # Update REDIS_PASSWORD manually

# Restart services
docker compose -p veris-memory-dev restart redis
```

---

## 📞 Support

### Questions?
- Full documentation: See `GITHUB_SECRETS_GUIDE.md`
- Security audit: See `SECURITY_AUDIT_CREDENTIALS.md`

### Common Issues

**Q: Will adding REDIS_PASSWORD break current deployments?**
A: No, the deployment script checks for it and generates one if missing. Once you add it, it will use your value instead.

**Q: Do I need to restart services after adding to GitHub Secrets?**
A: Yes, trigger a new deployment to update the .env file on the server with the new password.

**Q: What if I lose the password?**
A: You can regenerate it, update the GitHub Secret, and redeploy. The old password is only needed during transition.

**Q: Can I use the same password for dev and prod?**
A: Technically yes, but it's not recommended. Use different passwords for each environment.

---

## ✅ Verification Checklist

After completing setup:

- [ ] REDIS_PASSWORD added to GitHub Secrets
- [ ] NEO4J_RO_PASSWORD added to GitHub Secrets
- [ ] Triggered new deployment
- [ ] Verified dev deployment succeeded
- [ ] Verified Redis requires password
- [ ] Verified Neo4j RO uses new password
- [ ] Updated docker-compose.prod.yml
- [ ] Updated docker-compose.hetzner.yml
- [ ] Updated docker-compose.simple.yml
- [ ] Tested production deployment
- [ ] Documented passwords in secure location (password manager)

---

**Created**: 2025-11-15
**Last Updated**: 2025-11-15
**Next Review**: After implementing critical actions
