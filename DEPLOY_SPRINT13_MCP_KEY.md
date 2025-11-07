# Deploy Sprint 13 MCP API Key

This guide explains how to add the MCP server API key to the running veris-memory deployment.

## Changes Made

1. **docker-compose.yml**: Added Sprint 13 environment variables to `context-store` service
2. **.env.example**: Documented new environment variables

## Deployment Steps

### Step 1: Update .env File on Server

SSH into the server where veris-memory is deployed and update the .env file:

```bash
# SSH to server (adjust hostname as needed)
ssh your-server

# Navigate to deployment directory
cd /opt/veris-memory

# Edit .env file
nano .env  # or vim .env
```

Add these lines to the .env file:

```bash
# Sprint 13: API Key Authentication
# Generate secure key: openssl rand -hex 16
API_KEY_MCP=vmk_mcp_YOUR_RANDOM_KEY_HERE:mcp_server:writer:true
AUTH_REQUIRED=true
ENVIRONMENT=development
```

Save and exit.

### Step 2: Pull Updated docker-compose.yml

```bash
# Pull latest changes from main branch (after PR is merged)
cd /opt/veris-memory
git pull origin main
```

### Step 3: Restart the Service

```bash
# Restart only the context-store service (minimal downtime)
docker-compose restart context-store

# OR restart all services (if you want a full restart)
docker-compose down && docker-compose up -d
```

### Step 4: Verify the Update

```bash
# Check that the service is running
docker-compose ps

# Check logs for any errors
docker-compose logs context-store | tail -50

# Test health endpoint
curl -s http://localhost:8000/health | jq .

# Test with API key
curl -s -X POST http://localhost:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "type": "decision",
    "content": {"title": "API Key Test", "description": "Testing Sprint 13 auth"}
  }' | jq .
```

Expected response should show `"success": true` or similar.

### Step 5: Update MCP Server Configuration

On the MCP server host (where the MCP server runs):

```bash
# Update MCP server .env
cd /claude-workspace/veris-memory-mcp-server

# Verify .env has the correct API key
cat .env | grep API_KEY

# Should show your API key in the format:
# VERIS_MEMORY_API_KEY=vmk_mcp_YOUR_KEY_HERE:mcp_server:writer:true

# Test MCP server connection
bash test_sprint13_connection.sh
```

## API Key Format

**Format**: `vmk_mcp_{random_hex}:user_id:role:is_agent`

**Example**: `vmk_mcp_a1b2c3d4e5f6789012345678:mcp_server:writer:true`

**Format Breakdown**:
- `vmk_mcp_{random}` - Unique key identifier (generate with `openssl rand -hex 16`)
- `mcp_server` - User ID
- `writer` - Role (can create and read contexts, use forget_context)
- `true` - is_agent flag (prevents hard delete operations)

**Generate Your Key**:
```bash
KEY_SUFFIX=$(openssl rand -hex 16)
echo "API_KEY_MCP=vmk_mcp_${KEY_SUFFIX}:mcp_server:writer:true"
```

## Troubleshooting

### Issue: "Invalid API key"

**Cause**: API key not configured in backend .env

**Solution**: Verify the API_KEY_MCP line is in `/opt/veris-memory/.env` and restart the service

### Issue: "API key required"

**Cause**: AUTH_REQUIRED=true but no X-API-Key header sent

**Solution**: Ensure MCP server is using the updated code from `sprint-13-api-key-support` branch

### Issue: Service won't start

**Cause**: Invalid .env syntax

**Solution**: Check .env file for syntax errors, ensure no trailing spaces

```bash
# Check container logs
docker-compose logs context-store

# Look for environment variable errors
docker-compose config | grep -A 5 "context-store"
```

## Rollback (If Needed)

If something goes wrong:

```bash
# Revert to previous version
cd /opt/veris-memory
git checkout HEAD~1

# Remove Sprint 13 variables from .env
nano .env
# Delete or comment out:
# - API_KEY_MCP
# - AUTH_REQUIRED
# - ENVIRONMENT

# Restart service
docker-compose restart context-store
```

## Security Notes

1. **Never commit the .env file with real API keys to git**
2. **Backup .env before making changes**: `cp .env .env.backup`
3. **Use secure credentials for production**: Generate new key with `openssl rand -hex 16`
4. **Rotate API keys regularly**: Every 90 days recommended

## Verification Checklist

- [ ] .env file updated with API_KEY_MCP
- [ ] docker-compose.yml pulled from main branch
- [ ] context-store service restarted
- [ ] Health check passes: `curl http://localhost:8000/health`
- [ ] API key authentication works (test curl command above)
- [ ] MCP server can connect and store contexts
- [ ] Logs show no errors

## Support

If you encounter issues:
1. Check container logs: `docker-compose logs context-store`
2. Verify environment variables: `docker-compose config`
3. Test health endpoint: `curl http://localhost:8000/health`
4. Verify API key format matches exactly
