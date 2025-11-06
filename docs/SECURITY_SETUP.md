# Veris Memory Security Setup Guide

This guide covers the security configuration for Veris Memory, including firewall setup, host-based monitoring, and best practices.

## Table of Contents
- [Firewall Configuration](#firewall-configuration)
- [Host-Based Monitoring](#host-based-monitoring)
- [API Authentication](#api-authentication)
- [Network Security](#network-security)
- [Troubleshooting](#troubleshooting)

---

## Firewall Configuration

### Overview

Veris Memory runs in Docker containers, but the host firewall (UFW) must be configured to secure the server. The firewall protects your services while allowing necessary traffic.

### Initial Setup

Run these commands **ON THE HOST** (not inside Docker):

```bash
# 1. Install UFW if not already installed
sudo apt-get update
sudo apt-get install -y ufw

# 2. Set default policies (deny incoming, allow outgoing)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 3. Allow SSH (IMPORTANT: Do this first to avoid locking yourself out!)
sudo ufw allow 22/tcp
sudo ufw allow 2222/tcp  # Claude container SSH

# 4. Allow Docker services (localhost only for security)
sudo ufw allow from 127.0.0.1 to any port 8000 comment 'MCP Server'
sudo ufw allow from 127.0.0.1 to any port 8001 comment 'REST API'
sudo ufw allow from 127.0.0.1 to any port 8080 comment 'Dashboard'
sudo ufw allow from 127.0.0.1 to any port 9090 comment 'Sentinel API'

# 5. Allow Mosh (if using Mosh for remote access)
sudo ufw allow 60000:61000/udp comment 'Mosh'

# 6. Enable the firewall
sudo ufw --force enable

# 7. Verify the configuration
sudo ufw status verbose
```

### Expected Output

```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere
2222/tcp                   ALLOW IN    Anywhere
8000                       ALLOW IN    127.0.0.1              # MCP Server
8001                       ALLOW IN    127.0.0.1              # REST API
8080                       ALLOW IN    127.0.0.1              # Dashboard
9090                       ALLOW IN    127.0.0.1              # Sentinel API
60000:61000/udp            ALLOW IN    Anywhere               # Mosh
```

### Security Considerations

1. **Localhost-only Services**: MCP Server, API, Dashboard, and Sentinel are only accessible from localhost. Use SSH tunneling or a reverse proxy (nginx) for remote access.

2. **SSH Protection**: Consider additional SSH hardening:
   ```bash
   # Disable password authentication (use SSH keys only)
   sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
   sudo systemctl restart sshd
   ```

3. **Rate Limiting**: Add rate limiting for SSH:
   ```bash
   sudo ufw limit 22/tcp comment 'SSH rate limit'
   ```

---

## Host-Based Monitoring

### Why Host-Based?

Docker containers run in an isolated environment and cannot directly check the host's firewall status. To monitor security configurations like UFW, we use a host-based script that reports to Sentinel.

### Installation

#### Step 1: Configure Sudoers (Required)

The host monitoring script needs to run `sudo ufw status` without requiring a password prompt. Configure sudoers:

```bash
# Create sudoers file for sentinel monitoring
sudo visudo -f /etc/sudoers.d/sentinel-monitoring

# Add this line (replace 'your-username' with actual username):
your-username ALL=(ALL) NOPASSWD: /usr/sbin/ufw status verbose, /usr/sbin/ufw status numbered, /usr/bin/systemctl is-active ufw, /usr/sbin/iptables -L -n, /usr/sbin/iptables -L DOCKER -n

# Save and exit (Ctrl+X, then Y, then Enter)

# Verify the configuration
sudo visudo -c -f /etc/sudoers.d/sentinel-monitoring
```

**Security Note**: This configuration allows password-less sudo for specific UFW and iptables commands only. This is safe because:
- Commands are read-only (status, list)
- No destructive operations allowed
- Restricted to specific command paths
- Only affects the user running the script

#### Step 2: Copy the Monitoring Script

```bash
# Create the scripts directory if it doesn't exist
sudo mkdir -p /opt/veris-memory/scripts

# Copy the monitoring script
sudo cp scripts/sentinel-host-checks.sh /opt/veris-memory/scripts/

# Make it executable
sudo chmod +x /opt/veris-memory/scripts/sentinel-host-checks.sh

# Create log directory
sudo mkdir -p /var/log
sudo touch /var/log/sentinel-host-checks.log
```

#### Step 3: Set Authentication Secret

Configure the shared secret for authenticating with Sentinel:

```bash
# Generate a secure random secret (REQUIRED - do not use default!)
SECRET=$(openssl rand -hex 32)
echo "Generated secret: $SECRET"

# Set in environment for host script
echo "export HOST_CHECK_SECRET=\"$SECRET\"" | sudo tee -a /etc/environment

# Also set in docker-compose.sentinel.yml or .env file
echo "HOST_CHECK_SECRET=$SECRET" >> /opt/veris-memory/.env

# Verify it's set
echo $HOST_CHECK_SECRET
```

**🔒 CRITICAL SECURITY WARNING**:
- **NEVER use the default secret in production!** The default value `veris_host_check_default_secret_change_me` is insecure and must be changed.
- The secret must be at least 16 characters long
- Use only alphanumeric characters, dashes, underscores, or dots
- Avoid shell metacharacters: `;&|` \`$ (){}[]\
- The same secret must be set in both:
  1. Host environment (for script)
  2. Sentinel's docker-compose.sentinel.yml or .env

**Secret Validation**:
The host script will validate the secret on startup and reject:
- Secrets shorter than 16 characters (warning)
- Secrets containing shell metacharacters (fatal error)
- The default placeholder value (warning)

#### Step 4: Configure Cron Job

Add the script to crontab to run every 5 minutes:

```bash
# Edit crontab
sudo crontab -e

# Add this line (monitors every 5 minutes):
*/5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh >> /var/log/sentinel-host-checks.log 2>&1
```

#### Step 5: Verify Installation

```bash
# Run the script manually to test
sudo /opt/veris-memory/scripts/sentinel-host-checks.sh

# Check the logs
tail -f /var/log/sentinel-host-checks.log

# Verify Sentinel received the check
curl http://localhost:9090/status | jq '.host_check_results'
```

### Script Configuration

The monitoring script can be configured with environment variables:

```bash
# Optional: Set custom Sentinel API URL
export SENTINEL_API_URL=http://localhost:9090

# Optional: Set custom log file location
export LOG_FILE=/var/log/custom-sentinel-checks.log

# Run the script
/opt/veris-memory/scripts/sentinel-host-checks.sh
```

### Monitoring Checks

The host script currently performs:

1. **S11-firewall-status**: Checks UFW status and rule configuration
   - Verifies UFW is active
   - Counts configured rules
   - Checks for required ports
   - Reports missing security rules

Future checks may include:
- Disk space monitoring
- System resource usage
- Security patch status
- Certificate expiration

---

## API Authentication

### Sprint 13 Authentication

Veris Memory uses API key authentication for all MCP server endpoints.

#### Configuration

1. **Set API Key in Environment**:

```bash
# In your .env file
API_KEY_MCP=your_actual_api_key_here
```

2. **Sentinel Configuration**:

The Sentinel monitoring system automatically uses the same API key from the environment:

```yaml
# docker-compose.sentinel.yml
environment:
  - API_KEY_MCP=${API_KEY_MCP}
```

3. **Using the API**:

```bash
# Health check with authentication
curl -H "X-API-Key: your_actual_api_key_here" \
  http://localhost:8000/health

# Store context with authentication
curl -X POST http://localhost:8000/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_actual_api_key_here" \
  -d '{"type":"log","content":{"title":"Test"},"author":"me","author_type":"agent"}'
```

---

## Network Security

### Docker Network Configuration

Veris Memory uses an isolated Docker network:

```yaml
# docker-compose.yml
networks:
  context-store-network:
    driver: bridge
```

Services communicate internally using Docker's internal DNS:
- `context-store:8000` - MCP Server
- `api:8001` - REST API
- `qdrant:6333` - Vector Database
- `neo4j:7687` - Graph Database
- `redis:6379` - Cache

### External Access

By default, only the following ports are exposed to the host:

- `8000` - MCP Server (localhost only via UFW)
- `8001` - REST API (localhost only via UFW)
- `8080` - Dashboard (localhost only via UFW)
- `9090` - Sentinel API (localhost only via UFW)

To access from remote machines, use **SSH tunneling**:

```bash
# Forward MCP Server port
ssh -L 8000:localhost:8000 user@veris-server

# Forward multiple ports
ssh -L 8000:localhost:8000 -L 9090:localhost:9090 user@veris-server

# Now access via http://localhost:8000 on your local machine
```

### Reverse Proxy (Optional)

For production, consider using nginx as a reverse proxy with SSL:

```nginx
# /etc/nginx/sites-available/veris-memory
server {
    listen 443 ssl http2;
    server_name veris.example.com;

    ssl_certificate /etc/letsencrypt/live/veris.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/veris.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Troubleshooting

### Firewall Issues

#### Issue: Locked out after enabling UFW

**Solution**: Boot into recovery mode and disable UFW:
```bash
# In recovery mode
sudo ufw disable
```

Then reconfigure SSH rules before re-enabling.

#### Issue: Services not accessible

**Check if firewall is blocking**:
```bash
sudo ufw status verbose
```

**Allow the port**:
```bash
sudo ufw allow from 127.0.0.1 to any port <PORT>
```

### Host Monitoring Issues

#### Issue: No firewall data in Sentinel

**Check cron job is running**:
```bash
sudo crontab -l | grep sentinel-host-checks
```

**Run script manually**:
```bash
sudo /opt/veris-memory/scripts/sentinel-host-checks.sh
```

**Check logs**:
```bash
tail -f /var/log/sentinel-host-checks.log
```

#### Issue: "Permission denied" when running script

**Make script executable**:
```bash
sudo chmod +x /opt/veris-memory/scripts/sentinel-host-checks.sh
```

**Check sudo access**:
```bash
sudo -l | grep ufw
```

### API Authentication Issues

#### Issue: "Invalid API key" errors

**Verify environment variable is set**:
```bash
# In Docker container
echo $API_KEY_MCP

# On host
grep API_KEY_MCP .env
```

**Check docker-compose configuration**:
```bash
docker-compose config | grep API_KEY_MCP
```

**Restart services**:
```bash
docker-compose down
docker-compose up -d
```

---

## Security Checklist

Use this checklist to verify your Veris Memory security configuration:

- [ ] UFW firewall is enabled and active
- [ ] SSH is only accessible with key-based authentication
- [ ] Docker services are only accessible from localhost
- [ ] API key authentication is configured
- [ ] Host monitoring script is installed and running
- [ ] Cron job for host checks is active
- [ ] All services are running in Docker network isolation
- [ ] Logs are being collected and rotated
- [ ] Backups are configured and tested
- [ ] SSL/TLS certificates are valid (if using HTTPS)

---

## Additional Resources

- [UFW Documentation](https://help.ubuntu.com/community/UFW)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [SSH Hardening Guide](https://www.ssh.com/academy/ssh/server-hardening)
- [Veris Memory Sentinel Documentation](./VERIS_SENTINEL.md)

---

**Last Updated**: November 6, 2025
**Maintained By**: Veris Memory Team
