# GitHub Secrets Configuration Guide

**Repository**: veris-memory
**Last Updated**: 2025-11-15
**Purpose**: Complete reference for GitHub Actions secrets management

---

## Executive Summary

**YES, Redis password SHOULD be in GitHub Secrets** for production deployments to ensure:
- ✅ Consistent passwords across deployments
- ✅ Centralized secret management
- ✅ Audit trail of who deployed with what credentials
- ✅ No auto-regeneration on each deploy (which would break active connections)

Currently, Redis password is **auto-generated** during deployment, which is insecure for production.

---

## Critical Finding: Missing Redis Password

### Current Behavior (deploy-dev.sh:43-48)
```bash
if [ -z '$REDIS_PASSWORD' ]; then
  echo "🔐 Generating secure Redis password..."
  export REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
else
  export REDIS_PASSWORD='$REDIS_PASSWORD'
fi
```

### Problems
1. **Password regenerates on every deployment** (if not in GitHub Secrets)
2. **No centralized management** - password only exists on server
3. **Production configs have NO Redis auth** (docker-compose.prod.yml, docker-compose.hetzner.yml)
4. **Inconsistent across dev/prod** - dev might have password, prod doesn't

### Solution
Add `REDIS_PASSWORD` to GitHub Secrets for both development and production environments.

---

## Complete GitHub Secrets Checklist

### 📋 Required Secrets (Must Be Configured)

#### Infrastructure Access
| Secret Name | Purpose | Used In | Example Format | Priority |
|-------------|---------|---------|----------------|----------|
| `HETZNER_SSH_KEY` | SSH private key for server access | All deployments | `-----BEGIN OPENSSH PRIVATE KEY-----\n...` | 🔴 CRITICAL |
| `HETZNER_USER` | SSH username | All deployments | `root` or `deploy-user` | 🔴 CRITICAL |
| `HETZNER_HOST` | Server IP/hostname | All deployments | `123.45.67.89` or `server.example.com` | 🔴 CRITICAL |

#### Database Credentials
| Secret Name | Purpose | Used In | Example Format | Priority |
|-------------|---------|---------|----------------|----------|
| `NEO4J_PASSWORD` | Dev Neo4j password | deploy-dev.yml | `your_secure_neo4j_dev_password` | 🔴 CRITICAL |
| `NEO4J_PROD_PASSWORD` | Production Neo4j password | deploy-prod-manual.yml | `your_secure_neo4j_prod_password` | 🔴 CRITICAL |
| `REDIS_PASSWORD` | **MISSING - NEEDS TO BE ADDED** | deploy-dev.yml, deploy-prod-manual.yml | `your_secure_redis_password` | 🔴 CRITICAL |
| `NEO4J_RO_PASSWORD` | Read-only Neo4j access | Currently has default `readonly_secure_2024!` | `your_secure_readonly_password` | 🟠 HIGH |

#### API Authentication (Sprint 13)
| Secret Name | Purpose | Used In | Example Format | Priority |
|-------------|---------|---------|----------------|----------|
| `API_KEY_MCP` | MCP server authentication | deploy-dev.yml | `vmk_mcp_a1b2c3d4e5f6:mcp_server:writer:true` | 🔴 CRITICAL |
| `SENTINEL_API_KEY` | Sentinel monitoring auth | deploy-dev.yml | `vmk_sentinel_x9y8z7:sentinel:admin:true` | 🟡 MEDIUM |
| `API_KEY_VOICEBOT` | Voice bot authentication | deploy-dev.yml | `vmk_voicebot_m5n6o7:voice_bot:writer:true` | 🟡 MEDIUM |

#### Voice Platform (TeamAI)
| Secret Name | Purpose | Used In | Example Format | Priority |
|-------------|---------|---------|----------------|----------|
| `LIVEKIT_API_KEY` | LiveKit cloud API key | deploy-dev.yml | `APIxxxxxxxxxxxxx` | 🟡 MEDIUM |
| `LIVEKIT_API_SECRET` | LiveKit API secret | deploy-dev.yml | `secretxxxxxxxxxxxxx` | 🟡 MEDIUM |
| `LIVEKIT_API_WEBSOCKET` | LiveKit WebSocket URL | deploy-dev.yml | `wss://your-instance.livekit.cloud` | 🟡 MEDIUM |
| `OPENAI_API_KEY` | OpenAI for STT/TTS | deploy-dev.yml | `sk-proj-xxxxxxxxxxxxx` | 🟡 MEDIUM |

#### Monitoring & Notifications
| Secret Name | Purpose | Used In | Example Format | Priority |
|-------------|---------|---------|----------------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram notification bot | deploy-dev.yml | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` | 🟢 LOW |
| `TELEGRAM_CHAT_ID` | Telegram chat ID | deploy-dev.yml | `123456789` or `-1001234567890` | 🟢 LOW |
| `HOST_CHECK_SECRET` | Host validation secret | deploy-dev.yml | `your_host_check_secret` | 🟢 LOW |

#### Production Only
| Secret Name | Purpose | Used In | Example Format | Priority |
|-------------|---------|---------|----------------|----------|
| `TAILSCALE_AUTHKEY` | Tailscale VPN auth | deploy-prod-manual.yml | `tskey-auth-xxxxxxxxxxxxxx` | 🟠 HIGH |

---

## Secrets by Environment

### Development Environment (`deploy-dev.yml`)
**Required (11 secrets):**
1. ✅ HETZNER_SSH_KEY
2. ✅ HETZNER_USER
3. ✅ HETZNER_HOST
4. ✅ NEO4J_PASSWORD
5. ❌ **REDIS_PASSWORD** (MISSING - currently auto-generated)
6. ✅ API_KEY_MCP
7. ✅ SENTINEL_API_KEY
8. ✅ TELEGRAM_BOT_TOKEN
9. ✅ TELEGRAM_CHAT_ID
10. ✅ HOST_CHECK_SECRET
11. ⚠️ NEO4J_RO_PASSWORD (has default, should be explicit)

**Optional (5 secrets - for voice platform):**
12. LIVEKIT_API_KEY
13. LIVEKIT_API_SECRET
14. LIVEKIT_API_WEBSOCKET
15. API_KEY_VOICEBOT
16. OPENAI_API_KEY

### Production Environment (`deploy-prod-manual.yml`)
**Required (6 secrets):**
1. ✅ HETZNER_SSH_KEY
2. ✅ HETZNER_USER
3. ✅ HETZNER_HOST
4. ✅ NEO4J_PROD_PASSWORD
5. ❌ **REDIS_PASSWORD** (MISSING - production has NO Redis auth!)
6. ✅ TAILSCALE_AUTHKEY

---

## How to Add Secrets to GitHub

### Step 1: Navigate to Secrets
1. Go to repository: `https://github.com/credentum/veris-memory`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

### Step 2: Add Required Secrets

#### Database Passwords

**Redis Password (CRITICAL - MISSING)**
```bash
# Generate secure password
openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
# Example output: Xy9mK4nP2vQ8rT6wU3zA7cB5dE1fG0hJ

# Add to GitHub Secrets:
Name: REDIS_PASSWORD
Value: Xy9mK4nP2vQ8rT6wU3zA7cB5dE1fG0hJ
```

**Neo4j Password**
```bash
# Generate secure password
openssl rand -base64 32
# Example output: K8m9N0p1Q2r3S4t5U6v7W8x9Y0z1A2b3C4d5E6f7G8h=

# Add to GitHub Secrets:
Name: NEO4J_PASSWORD
Value: K8m9N0p1Q2r3S4t5U6v7W8x9Y0z1A2b3C4d5E6f7G8h=
```

**Neo4j Read-Only Password**
```bash
# Generate different password for read-only access
openssl rand -base64 32
# Example output: M4n5O6p7Q8r9S0t1U2v3W4x5Y6z7A8b9C0d1E2f3G4h=

# Add to GitHub Secrets:
Name: NEO4J_RO_PASSWORD
Value: M4n5O6p7Q8r9S0t1U2v3W4x5Y6z7A8b9C0d1E2f3G4h=
```

#### API Keys (Sprint 13 Format)

**MCP API Key**
```bash
# Generate random hex (16 bytes = 32 characters)
openssl rand -hex 16
# Example output: d9ef8d8699ca748e5a484c5026ecdc2a

# Format as MCP key:
Name: API_KEY_MCP
Value: vmk_mcp_d9ef8d8699ca748e5a484c5026ecdc2a:mcp_server:writer:true
```

**Sentinel API Key**
```bash
# Generate random hex
openssl rand -hex 16
# Example output: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6

# Format as Sentinel key:
Name: SENTINEL_API_KEY
Value: vmk_sentinel_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6:sentinel:admin:true
```

**Voice Bot API Key**
```bash
# Generate random hex
openssl rand -hex 16
# Example output: b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7

# Format as Voice Bot key:
Name: API_KEY_VOICEBOT
Value: vmk_voicebot_b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7:voice_bot:writer:true
```

#### SSH Key

**Hetzner SSH Key**
```bash
# Use existing private key OR generate new one:
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/veris-deploy

# Copy the ENTIRE private key (including headers)
cat ~/.ssh/veris-deploy

# Add to GitHub Secrets:
Name: HETZNER_SSH_KEY
Value: (paste entire key including -----BEGIN OPENSSH PRIVATE KEY----- and -----END OPENSSH PRIVATE KEY-----)

# Then add public key to server:
ssh-copy-id -i ~/.ssh/veris-deploy.pub user@server
```

#### Infrastructure

**Hetzner Server Details**
```bash
# Add server username:
Name: HETZNER_USER
Value: root  # or your deployment user

# Add server hostname/IP:
Name: HETZNER_HOST
Value: 123.45.67.89  # or your server IP/hostname
```

#### Tailscale (Production Only)

**Tailscale Auth Key**
```bash
# Get from: https://login.tailscale.com/admin/settings/keys
# Generate a reusable auth key with appropriate tags

Name: TAILSCALE_AUTHKEY
Value: tskey-auth-kxxxxxxxxxxxxxxxxxxxxx-yyyyyyyyyyyyyyyyyyyy
```

#### Optional: Voice Platform

**LiveKit Configuration**
```bash
# Get from: https://cloud.livekit.io
Name: LIVEKIT_API_KEY
Value: APIxxxxxxxxxxxxx

Name: LIVEKIT_API_SECRET
Value: secretxxxxxxxxxxxxx

Name: LIVEKIT_API_WEBSOCKET
Value: wss://your-instance.livekit.cloud
```

**OpenAI API Key**
```bash
# Get from: https://platform.openai.com/api-keys
Name: OPENAI_API_KEY
Value: sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### Optional: Telegram Notifications

**Telegram Bot Token**
```bash
# Get from: @BotFather on Telegram
Name: TELEGRAM_BOT_TOKEN
Value: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# Get chat ID from: @userinfobot on Telegram
Name: TELEGRAM_CHAT_ID
Value: 123456789  # or -1001234567890 for group
```

---

## Secrets Validation Checklist

### Before Deployment
Use this checklist to verify all secrets are configured:

```bash
# Run this in GitHub Actions to validate (add to workflow)
required_secrets=(
  "HETZNER_SSH_KEY"
  "HETZNER_USER"
  "HETZNER_HOST"
  "NEO4J_PASSWORD"
  "REDIS_PASSWORD"
  "API_KEY_MCP"
)

for secret in "${required_secrets[@]}"; do
  if [ -z "${!secret}" ]; then
    echo "❌ ERROR: $secret is not set!"
    exit 1
  else
    echo "✅ $secret is configured"
  fi
done
```

### GitHub Secrets Current Status

| Secret | Dev Required | Prod Required | Currently Set? | Status |
|--------|--------------|---------------|----------------|--------|
| HETZNER_SSH_KEY | ✅ Yes | ✅ Yes | ✅ Yes | ✅ OK |
| HETZNER_USER | ✅ Yes | ✅ Yes | ✅ Yes | ✅ OK |
| HETZNER_HOST | ✅ Yes | ✅ Yes | ✅ Yes | ✅ OK |
| NEO4J_PASSWORD | ✅ Yes | ❌ No | ✅ Yes | ✅ OK |
| NEO4J_PROD_PASSWORD | ❌ No | ✅ Yes | ✅ Yes | ✅ OK |
| **REDIS_PASSWORD** | ✅ Yes | ✅ Yes | ❌ **NO** | 🔴 **MISSING** |
| **NEO4J_RO_PASSWORD** | ⚠️ Recommended | ⚠️ Recommended | ❌ **NO** | 🟠 **HAS DEFAULT** |
| API_KEY_MCP | ✅ Yes | ⚠️ Maybe | ✅ Yes | ✅ OK |
| SENTINEL_API_KEY | ✅ Yes | ⚠️ Maybe | ✅ Yes | ✅ OK |
| TELEGRAM_BOT_TOKEN | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| TELEGRAM_CHAT_ID | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| TAILSCALE_AUTHKEY | ❌ No | ✅ Yes | ✅ Yes | ✅ OK |
| LIVEKIT_API_KEY | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| LIVEKIT_API_SECRET | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| LIVEKIT_API_WEBSOCKET | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| API_KEY_VOICEBOT | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| OPENAI_API_KEY | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |
| HOST_CHECK_SECRET | ⚠️ Optional | ⚠️ Optional | ✅ Yes | ✅ OK |

---

## Immediate Actions Required

### 🔴 CRITICAL: Add REDIS_PASSWORD

**Step 1: Generate Password**
```bash
openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
```

**Step 2: Add to GitHub Secrets**
- Go to Settings → Secrets → Actions
- Add secret: `REDIS_PASSWORD`
- Value: (generated password from Step 1)

**Step 3: Update Deployment Scripts**
The scripts already check for REDIS_PASSWORD, so they'll automatically use it once added.

**Step 4: Update Docker Compose Files**
Fix production configs to require Redis password:
- docker-compose.prod.yml (line 116)
- docker-compose.hetzner.yml (line 150-161)
- docker-compose.simple.yml (line 19-27)

### 🟠 HIGH PRIORITY: Add NEO4J_RO_PASSWORD

Remove the hardcoded default `readonly_secure_2024!` from:
- docker-compose.yml (lines 15, 58)

```bash
# Generate password
openssl rand -base64 32

# Add to GitHub Secrets:
Name: NEO4J_RO_PASSWORD
Value: (generated password)
```

---

## Secret Rotation Procedures

### How Often to Rotate

| Secret Type | Rotation Frequency | Reason |
|-------------|-------------------|---------|
| Database passwords | Every 90 days | Best practice for data protection |
| API keys (MCP, Sentinel) | Every 180 days | Medium risk, limited scope |
| SSH keys | Every 365 days | Infrastructure access |
| Voice platform keys | As needed | External service managed |
| Telegram tokens | As needed | Low risk, notification only |

### Rotation Process

#### 1. Database Passwords (Neo4j, Redis)

**Neo4j Password Rotation:**
```bash
# Step 1: Generate new password
NEW_PASSWORD=$(openssl rand -base64 32)

# Step 2: Update Neo4j password on server
docker exec veris-memory-dev-neo4j-1 \
  cypher-shell -u neo4j -p "$OLD_PASSWORD" \
  "ALTER USER neo4j SET PASSWORD '$NEW_PASSWORD'"

# Step 3: Update GitHub Secret
# Go to Settings → Secrets → Actions → NEO4J_PASSWORD → Update

# Step 4: Redeploy to update .env file
# Trigger deployment workflow
```

**Redis Password Rotation:**
```bash
# Step 1: Generate new password
NEW_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# Step 2: Update GitHub Secret first
# Go to Settings → Secrets → Actions → REDIS_PASSWORD → Update

# Step 3: Redeploy (will restart Redis with new password)
# Trigger deployment workflow

# Note: This will cause brief downtime as Redis restarts
```

#### 2. API Keys Rotation

**MCP API Key Rotation:**
```bash
# Step 1: Generate new key
NEW_RANDOM=$(openssl rand -hex 16)
NEW_KEY="vmk_mcp_${NEW_RANDOM}:mcp_server:writer:true"

# Step 2: Add new key to API key validator (keep old key temporarily)
# Update src/auth/api_key_validator.py to accept both keys

# Step 3: Update GitHub Secret
# Settings → Secrets → Actions → API_KEY_MCP → Update

# Step 4: Redeploy

# Step 5: Remove old key from validator after confirming new key works
```

#### 3. SSH Key Rotation

```bash
# Step 1: Generate new SSH key
ssh-keygen -t ed25519 -C "github-actions-deploy-$(date +%Y%m)" -f ~/.ssh/veris-deploy-new

# Step 2: Add new public key to server
ssh-copy-id -i ~/.ssh/veris-deploy-new.pub user@server

# Step 3: Update GitHub Secret
cat ~/.ssh/veris-deploy-new  # Copy entire private key
# Settings → Secrets → Actions → HETZNER_SSH_KEY → Update

# Step 4: Test deployment with new key
# Trigger deployment workflow

# Step 5: Remove old public key from server (after confirming new key works)
ssh user@server
vi ~/.ssh/authorized_keys  # Remove old key
```

### Emergency Rotation (Compromise Detected)

If a secret is compromised:

1. **IMMEDIATELY** rotate the secret following procedures above
2. **AUDIT** all deployments that used the compromised secret
3. **REVIEW** access logs for unauthorized access
4. **NOTIFY** security team if data breach suspected
5. **DOCUMENT** incident and response actions

---

## Environment-Specific Configuration

### Development Environment
- Uses auto-generated Redis password (if not in secrets) ❌ **Should be fixed**
- Single Neo4j password for read-write
- Optional voice platform integration
- Telegram notifications optional

### Production Environment
- **MUST** have explicit Redis password ❌ **Currently missing**
- Separate Neo4j password (`NEO4J_PROD_PASSWORD`)
- Requires Tailscale for secure access
- Should have all monitoring enabled

---

## Security Best Practices

### ✅ DO:
1. **Use GitHub Secrets** for ALL passwords and keys
2. **Generate strong passwords** with at least 32 characters
3. **Use different passwords** for dev and production
4. **Rotate secrets regularly** according to schedule
5. **Audit secret usage** in workflow logs (secrets are masked)
6. **Document** when and why secrets were rotated
7. **Use environment protection rules** for production deployments

### ❌ DON'T:
1. **Don't hardcode** passwords in docker-compose files
2. **Don't use default passwords** in production
3. **Don't share secrets** between environments
4. **Don't commit secrets** to git (even in history)
5. **Don't echo secrets** in deployment logs
6. **Don't use weak passwords** like "password123"
7. **Don't skip rotation** schedule

### 🔒 GitHub Actions Security Features

**Already Implemented:**
```yaml
# deploy-dev.yml masks all secrets
- name: Setup SSH key
  run: |
    echo "::add-mask::${{ secrets.HETZNER_SSH_KEY }}"
    echo "::add-mask::${{ secrets.NEO4J_PASSWORD }}"
    # ... all secrets are masked
```

This ensures secrets never appear in logs even if accidentally echoed.

---

## Deployment Script Integration

### How Secrets Are Used

**deploy-dev.sh (lines 50-61):**
```bash
# Secrets are exported as environment variables
export NEO4J_PASSWORD='$NEO4J_PASSWORD'
export REDIS_PASSWORD='$REDIS_PASSWORD'  # Will use if set, else generate
export TELEGRAM_BOT_TOKEN='$TELEGRAM_BOT_TOKEN'
export API_KEY_MCP='$API_KEY_MCP'
# ... etc
```

**deploy-dev.sh (lines 280-368):**
```bash
# Secrets are written to .env file on server
{
  printf "NEO4J_PASSWORD=%s\n" "$NEO4J_PASSWORD"
  printf "REDIS_PASSWORD=%s\n" "$REDIS_PASSWORD"
  printf "API_KEY_MCP=%s\n" "$API_KEY_MCP"
  # ... etc
} >> .env 2>/dev/null
```

The scripts are already designed to use GitHub Secrets! Just need to add the missing ones.

---

## Troubleshooting

### Secret Not Working

**Problem**: Deployment fails with "password incorrect"

**Solution**:
1. Verify secret is set in GitHub: Settings → Secrets → Actions
2. Check secret name matches exactly (case-sensitive)
3. Check for trailing spaces in secret value
4. Verify environment protection rules (prod requires approval)

### Secret Not Updating

**Problem**: Updated secret but deployment still uses old value

**Solution**:
1. Secrets are cached during workflow run
2. Re-trigger workflow to use new value
3. Check if .env file on server has old value (manually update if needed)

### Connection Refused After Password Rotation

**Problem**: Services can't connect to database after rotation

**Solution**:
1. Check if password was updated in GitHub Secrets
2. Check if .env file was regenerated on server
3. Verify containers restarted with new password
4. Check if old password is cached somewhere

---

## Quick Reference Commands

### Generate Passwords
```bash
# Strong password (32 chars)
openssl rand -base64 32

# Alphanumeric only (32 chars)
openssl rand -base64 32 | tr -d "=+/" | cut -c1-32

# Hex format (32 chars)
openssl rand -hex 16

# API key format
echo "vmk_mcp_$(openssl rand -hex 16):mcp_server:writer:true"
```

### Check Current Secrets
```bash
# SSH to server
ssh user@server

# Check .env file (secrets are here)
cat /opt/veris-memory/.env | grep -E "PASSWORD|API_KEY|TOKEN" | sed 's/=.*/=***/'

# Verify Redis password
docker exec veris-memory-dev-redis-1 redis-cli -a "$REDIS_PASSWORD" ping

# Verify Neo4j password
docker exec veris-memory-dev-neo4j-1 cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1"
```

### Test Secrets in GitHub Actions
```bash
# Add to workflow for debugging (will be masked)
echo "Testing secret: ${{ secrets.API_KEY_MCP }}"
# Output: Testing secret: ***
```

---

## Conclusion

**Critical Actions:**
1. ✅ **Add REDIS_PASSWORD to GitHub Secrets** (top priority)
2. ✅ **Add NEO4J_RO_PASSWORD to GitHub Secrets** (remove hardcoded default)
3. ✅ **Update production docker-compose files** to require Redis authentication
4. ✅ **Set up rotation schedule** for all secrets

Once these are completed, all credentials will be:
- Centrally managed in GitHub Secrets
- Automatically deployed without manual intervention
- Properly secured and rotated
- Auditable through GitHub's access logs

---

**Last Review**: 2025-11-15
**Next Review**: Recommended after implementing critical actions
**Contact**: DevOps/Security team for secret rotation approvals
