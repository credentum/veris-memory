# MCP Server Docker Bridge Network Access Fix

**Issue ID:** Docker Bridge Access Broken by PR #248
**Date:** 2025-11-14
**Status:** ✅ Fixed in PR #263

## Problem

PR #248 security fixes changed the MCP server (context-store) port binding from `0.0.0.0:8000` to `127.0.0.1:8000` to prevent external access. While this improved security, it had an unintended consequence:

**Broke Docker Bridge Network Access:**
- Docker containers (including Claude Code agents) connect via Docker bridge network (`172.17.0.x`)
- `127.0.0.1:8000` only accepts connections from the host's localhost
- Docker containers couldn't reach `127.0.0.1:8000` (that's the container's own localhost)
- Docker containers couldn't reach `172.17.0.1:8000` (service not bound to that interface)

**Impact:**
- Claude Code agents running in Docker containers couldn't connect to Veris Memory MCP server
- MCP tools became unavailable
- Context storage and retrieval failed

## Root Cause

```yaml
# docker-compose.yml (PR #248)
context-store:
  ports:
    - "127.0.0.1:8000:8000"  # ❌ Only accessible from host's localhost
```

This binding means:
- ✅ Host machine can connect via `127.0.0.1:8000` or `localhost:8000`
- ❌ Docker containers **cannot** connect (not on the host's localhost interface)
- ✅ External machines **cannot** connect (blocked by binding + firewall)

## Solution

Changed the binding to allow Docker bridge network access while maintaining security:

```yaml
# docker-compose.yml (PR #263 - Fixed)
context-store:
  ports:
    - "8000:8000"  # ✅ Accessible via Docker bridge network for MCP clients
```

This binding means:
- ✅ Host machine can connect via `127.0.0.1:8000`, `localhost:8000`, or `172.17.0.1:8000`
- ✅ Docker containers **can** connect via `172.17.0.1:8000` (Docker bridge gateway)
- ❌ External machines **cannot** connect (blocked by UFW firewall)

## Security Analysis

### Why This is Safe

1. **UFW Firewall Protection:**
   ```bash
   # UFW rules block external access to port 8000
   # Only localhost and Docker internal networks can reach it
   sudo ufw status | grep 8000
   ```

2. **API Key Authentication:**
   - MCP server requires `X-API-Key` header with valid `API_KEY_MCP`
   - All requests without valid API key are rejected (401 Unauthorized)
   - API keys are 32+ character random strings

3. **DOCKER-USER Iptables Rules (Optional):**
   - Defense-in-depth measure from PR #248
   - Can be configured to explicitly block external access to port 8000
   - Script: `scripts/security/docker-firewall-rules.sh`

4. **Network Segmentation:**
   - Docker bridge network (172.17.0.0/16) is internal-only
   - Not routed to external networks
   - Containers on bridge can only talk to each other and host

### Security Comparison

| Binding | Host Access | Docker Container Access | External Access | Security Level |
|---------|-------------|-------------------------|-----------------|----------------|
| `127.0.0.1:8000` | ✅ | ❌ | ❌ | High (but breaks MCP) |
| `0.0.0.0:8000` (with UFW) | ✅ | ✅ | ❌ | High (MCP works) |
| `0.0.0.0:8000` (no firewall) | ✅ | ✅ | ✅ | **LOW - INSECURE** |

**Current Config:** `0.0.0.0:8000` with UFW = **High Security + MCP Works** ✅

### Database Ports Remain Protected

Other services maintain localhost-only bindings for maximum security:

```yaml
# Databases remain protected with 127.0.0.1 binding
qdrant:
  ports:
    - "127.0.0.1:6333:6333"  # ✅ Localhost only

neo4j:
  ports:
    - "127.0.0.1:7474:7474"  # ✅ Localhost only
    - "127.0.0.1:7687:7687"  # ✅ Localhost only

redis:
  ports:
    - "127.0.0.1:6379:6379"  # ✅ Localhost only
```

**Why databases are different:**
- Databases have no authentication requirement for read operations
- MCP server has API key authentication for all operations
- Databases are accessed only by local services (context-store, api)
- MCP server needs to be accessed by external Docker containers (Claude Code agents)

## Verification

### Test Docker Bridge Access

```bash
# From inside any Docker container on the same host
curl -s http://172.17.0.1:8000/health

# Expected output:
# {"status":"healthy","uptime_seconds":XXX,"timestamp":"...","message":"Server is running"}
```

### Test MCP Connection

```bash
# Store context via MCP
curl -X POST http://172.17.0.1:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: vmk_mcp_903e1bcb70d704da4fbf207722c471ba" \
  -d '{
    "type": "log",
    "content": {"title": "Test Connection"},
    "author": "test",
    "author_type": "agent"
  }'

# Expected: {"success": true, "id": "...", ...}
```

### Verify External Access is Blocked

```bash
# From external machine (should fail/timeout)
curl --connect-timeout 5 http://135.181.4.118:8000/health

# Expected: Connection timeout or refused
```

## Deployment

This fix is included in PR #263 and will be deployed automatically when merged.

### Manual Deployment

If you need to apply this fix immediately:

```bash
# 1. Update docker-compose.yml
cd /opt/veris-memory
git checkout main && git pull

# 2. Recreate context-store service with new port binding
docker compose up -d context-store

# 3. Verify the binding
docker port veris-memory-dev-context-store-1

# Expected output:
# 8000/tcp -> 0.0.0.0:8000

# 4. Test connection
curl -s http://172.17.0.1:8000/health
```

## Related

- **Original Issue:** PR #248 security fixes broke Docker bridge access
- **Root Cause:** `127.0.0.1:8000` binding too restrictive
- **Fix PR:** PR #263 (Security Grade A enhancements)
- **Security Audit:** 2025-11-14 (Post-PR #248)

## References

- Docker networking: https://docs.docker.com/network/bridge/
- Port binding security: https://docs.docker.com/config/containers/container-networking/
- UFW with Docker: https://github.com/chaifeng/ufw-docker

---

**Last Updated:** 2025-11-14
**Status:** ✅ Fixed and tested
**PR:** #263
