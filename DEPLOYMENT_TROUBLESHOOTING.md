# Context Store Deployment Troubleshooting Guide

This guide covers common deployment issues and their solutions based on real-world deployment experience.

## 🔐 Authentication Issues

### Neo4j Authentication Failures

**Symptoms:**
- Context Store logs show `Neo4j health check failed: authentication failure`
- `cypher-shell` returns "The client is unauthorized due to authentication failure"
- Docker containers running but Neo4j connection fails

**Root Cause:**
Password mismatch between systemd credentials and Docker Compose environment variables.

**Solution:**

1. **Check current passwords:**
   ```bash
   # Check systemd credential
   sudo cat /opt/context-store/credentials/neo4j_password
   
   # Check docker container password
   docker inspect context-store-neo4j-1 | grep NEO4J_AUTH
   
   # Check .env file
   cat /opt/context-store/.env | grep NEO4J_PASSWORD
   ```

2. **Synchronize passwords:**
   ```bash
   # Get the systemd credential password
   NEO4J_PASS=$(sudo cat /opt/context-store/credentials/neo4j_password)
   
   # Update .env file
   sed -i "s/NEO4J_PASSWORD=.*/NEO4J_PASSWORD=${NEO4J_PASS}/" /opt/context-store/.env
   
   # Restart services
   export NEO4J_PASSWORD="$NEO4J_PASS"
   docker-compose -f docker-compose.simple.yml restart neo4j
   systemctl restart context-store
   ```

3. **If Neo4j data is corrupted, reset (WARNING: loses data):**
   ```bash
   docker-compose -f docker-compose.simple.yml down neo4j
   sudo rm -rf /raid1/docker-data/neo4j/data/databases/*
   docker-compose -f docker-compose.simple.yml up -d neo4j
   ```

## ⚙️ Environment Configuration Issues

### Systemd Environment Variable Syntax

**Symptoms:**
- Systemd logs show "Ignoring invalid environment assignment 'export NEO4J_PASSWORD=...'"
- Service fails to start with "Configuration validation failed: missing NEO4J_PASSWORD"

**Root Cause:**
Using shell `export` syntax in systemd EnvironmentFile, which is invalid.

**Solution:**

1. **Fix .env file syntax:**
   ```bash
   # Wrong (shell syntax):
   export NEO4J_PASSWORD=password123
   
   # Correct (systemd syntax):
   NEO4J_PASSWORD=password123
   ```

2. **Recreate .env file with correct syntax:**
   ```bash
   cd /opt/context-store
   ./scripts/setup-secure-credentials.sh
   ```

### Missing CREDENTIALS_DIRECTORY

**Symptoms:**
- Python application can't load credentials
- Logs show "NEO4J_PASSWORD not found in systemd credentials"

**Root Cause:**
Systemd service not configured to load credentials properly.

**Solution:**

1. **Verify systemd service configuration:**
   ```bash
   grep -A 5 -B 5 "LoadCredential" /etc/systemd/system/context-store.service
   ```

2. **Should contain:**
   ```ini
   LoadCredential=neo4j_password:/opt/context-store/credentials/neo4j_password
   ```

3. **Reload and restart:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart context-store
   ```

## 🐳 Docker Issues

### Container Password Persistence

**Symptoms:**
- Neo4j container uses old password even after environment variable changes
- Password changes don't take effect until complete rebuild

**Root Cause:**
Neo4j stores credentials in its database, which persists across container restarts.

**Solution:**

1. **For running container - use admin reset:**
   ```bash
   # Stop container
   docker stop context-store-neo4j-1
   
   # Reset password using admin tool
   docker run --rm -v /raid1/docker-data/neo4j/data:/data \
     neo4j:5.15-community \
     neo4j-admin dbms set-initial-password "new_password"
   
   # Start container with matching environment
   export NEO4J_PASSWORD="new_password"
   docker start context-store-neo4j-1
   ```

2. **For fresh deployment:**
   ```bash
   # Ensure password is set before first startup
   export NEO4J_PASSWORD=$(sudo cat /opt/context-store/credentials/neo4j_password)
   docker-compose -f docker-compose.simple.yml up -d neo4j
   ```

### Image Digest Issues

**Symptoms:**
- `docker-compose up` fails with image digest errors
- "manifest unknown" or "digest not found" errors

**Root Cause:**
SHA256 digests can change when images are rebuilt or registries update.

**Solution:**

1. **Update to latest digest:**
   ```bash
   # Pull latest image
   docker pull qdrant/qdrant:v1.12.1
   
   # Get new digest
   docker inspect qdrant/qdrant:v1.12.1 --format='{{index .RepoDigests 0}}'
   
   # Update docker-compose.yml with new digest
   ```

2. **Or use version tags without digest (less secure):**
   ```yaml
   image: qdrant/qdrant:v1.12.1
   ```

## 🔍 Diagnostic Commands

### Quick Health Check
```bash
# Overall system status
./scripts/hetzner-setup/validate-deployment.sh

# Individual service checks
systemctl status context-store
docker ps
curl http://localhost:8000/health
```

### Database Connectivity
```bash
# Redis
echo "PING" | nc -w 2 localhost 6379

# Neo4j HTTP
curl -u neo4j:password http://localhost:7474/db/data/

# Neo4j Bolt
docker exec context-store-neo4j-1 cypher-shell -u neo4j -p password "RETURN 1;"

# Qdrant
curl http://localhost:6333/health
```

### Log Investigation
```bash
# Context Store application logs
journalctl -u context-store -f --no-pager

# Docker container logs
docker logs context-store-neo4j-1 --tail 50
docker logs context-store-qdrant-1 --tail 50
docker logs context-store-redis-1 --tail 50

# System logs for authentication issues
grep "authentication failure" /var/log/auth.log
```

## 🚀 Recovery Procedures

### Complete Service Reset
```bash
# 1. Stop all services
systemctl stop context-store
docker-compose -f docker-compose.simple.yml down

# 2. Reset credentials
sudo rm -f /opt/context-store/credentials/neo4j_password
./scripts/setup-secure-credentials.sh

# 3. Restart infrastructure
export NEO4J_PASSWORD=$(sudo cat /opt/context-store/credentials/neo4j_password)
docker-compose -f docker-compose.simple.yml up -d

# 4. Start application
systemctl start context-store

# 5. Verify
curl http://localhost:8000/health
```

### Credential Synchronization Script
```bash
#!/bin/bash
# sync-credentials.sh - Synchronize all credential sources

echo "🔄 Synchronizing Context Store credentials..."

NEO4J_PASS=$(sudo cat /opt/context-store/credentials/neo4j_password)

# Update .env file
sed -i "s/NEO4J_PASSWORD=.*/NEO4J_PASSWORD=${NEO4J_PASS}/" /opt/context-store/.env

# Export for docker-compose
export NEO4J_PASSWORD="$NEO4J_PASS"

# Restart services in order
docker-compose -f docker-compose.simple.yml restart neo4j
sleep 10
systemctl restart context-store

echo "✅ Credential synchronization complete"
echo "🔍 Verify with: curl http://localhost:8000/health"
```

## 🛡️ Prevention

### Pre-deployment Checklist
- [ ] Run `./scripts/setup-secure-credentials.sh`
- [ ] Verify `.env` file has no `export` statements
- [ ] Set `NEO4J_PASSWORD` environment variable before docker-compose
- [ ] Test credential loading: `python load-credentials.py`
- [ ] Validate systemd service: `systemd-analyze verify context-store.service`

### Monitoring
- Set up health check monitoring on `/health` endpoint
- Monitor systemd service status: `systemctl is-active context-store`
- Alert on authentication failures in logs
- Regular credential rotation (quarterly recommended)

## 📞 Emergency Contacts
- **Documentation**: `/workspaces/agent-context-template/context-store/`
- **Logs**: `journalctl -u context-store -f`
- **Health Check**: `curl http://localhost:8000/health`