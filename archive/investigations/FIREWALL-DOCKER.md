# Docker Compose Firewall Configuration

This document outlines firewall and security considerations for the Context Store Docker Compose deployment.

## Port Overview

The Docker Compose setup exposes several ports that require careful firewall configuration:

### Exposed Ports by Service

| Service | Port | Protocol | Purpose | Public Access |
|---------|------|----------|---------|---------------|
| context-store | 8000 | HTTP | MCP Server API | **Required** |
| qdrant | 6333 | HTTP | Vector DB REST API | **Internal Only** |
| qdrant | 6334 | gRPC | Vector DB gRPC API | **Internal Only** |
| neo4j | 7474 | HTTP | Neo4j Browser/API | **Internal Only** |
| neo4j | 7687 | Bolt | Neo4j Database Protocol | **Internal Only** |
| redis | 6379 | TCP | Redis Cache/KV Store | **Internal Only** |

## Recommended Firewall Rules

### Production Deployment (UFW Example)

```bash
# Allow only the Context Store MCP API
sudo ufw allow 8000/tcp comment "Context Store MCP API"

# Block all database ports from external access
sudo ufw deny 6333/tcp comment "Block external Qdrant HTTP"
sudo ufw deny 6334/tcp comment "Block external Qdrant gRPC"
sudo ufw deny 7474/tcp comment "Block external Neo4j HTTP"
sudo ufw deny 7687/tcp comment "Block external Neo4j Bolt"
sudo ufw deny 6379/tcp comment "Block external Redis"

# Allow SSH for management
sudo ufw allow 22/tcp comment "SSH access"

# Enable firewall
sudo ufw enable
```

### iptables Configuration

```bash
# Allow Context Store MCP API
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# Block database ports from external access
iptables -A INPUT -p tcp --dport 6333 -j DROP
iptables -A INPUT -p tcp --dport 6334 -j DROP
iptables -A INPUT -p tcp --dport 7474 -j DROP
iptables -A INPUT -p tcp --dport 7687 -j DROP
iptables -A INPUT -p tcp --dport 6379 -j DROP

# Allow localhost connections (Docker containers)
iptables -A INPUT -i lo -j ACCEPT

# Save rules (Ubuntu/Debian)
iptables-save > /etc/iptables/rules.v4
```

### Docker-Specific Considerations

#### Network Isolation

The services use a dedicated Docker network (`context-store-network`) which provides:
- Inter-service communication without exposing ports to host
- Network isolation from other Docker containers
- Internal DNS resolution between services

#### Port Binding Security

Current configuration binds to all interfaces (`0.0.0.0`). For enhanced security, consider binding only to localhost:

```yaml
# More secure port binding (localhost only)
ports:
  - "127.0.0.1:6333:6333"  # Qdrant
  - "127.0.0.1:7474:7474"  # Neo4j HTTP
  - "127.0.0.1:7687:7687"  # Neo4j Bolt
  - "127.0.0.1:6379:6379"  # Redis
```

## Security Best Practices

### 1. Reverse Proxy Setup

Use a reverse proxy (nginx/Apache) for the Context Store API:

```nginx
# /etc/nginx/sites-available/context-store
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL configuration
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/private.key;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. VPN Access for Database Management

For database administration access:

```bash
# Example: Access via SSH tunnel
ssh -L 7474:localhost:7474 -L 7687:localhost:7687 user@server
# Then access Neo4j browser at http://localhost:7474
```

### 3. Docker Daemon Security

Secure Docker daemon configuration:

```json
// /etc/docker/daemon.json
{
  "icc": false,
  "userland-proxy": false,
  "no-new-privileges": true
}
```

### 4. Container Security

Add security options to services:

```yaml
security_opt:
  - no-new-privileges:true
  - seccomp:unconfined
read_only: true
tmpfs:
  - /tmp
  - /var/cache
```

## Monitoring and Alerting

### Failed Connection Monitoring

Monitor for unauthorized access attempts:

```bash
# Monitor failed connections to database ports
sudo tail -f /var/log/ufw.log | grep -E "(6333|6334|7474|7687|6379)"

# Alert on suspicious activity
fail2ban-regex /var/log/ufw.log '<HOST>.*DPT=(6333|6334|7474|7687|6379)'
```

### Docker Network Monitoring

Monitor Docker network traffic:

```bash
# Monitor network connections
docker exec context-store netstat -ant

# Check container network isolation
docker network inspect context-store_context-store-network
```

## Cloud Provider Specific Configuration

### AWS Security Groups

```bash
# Allow Context Store API from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0

# Block database ports (default deny applies)
# No additional rules needed - databases are blocked by default
```

### GCP Firewall Rules

```bash
# Allow Context Store API
gcloud compute firewall-rules create allow-context-store-api \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --description "Context Store MCP API"

# Deny database ports (if not using default deny)
gcloud compute firewall-rules create deny-database-ports \
  --action deny \
  --rules tcp:6333,tcp:6334,tcp:7474,tcp:7687,tcp:6379 \
  --source-ranges 0.0.0.0/0 \
  --description "Block external database access"
```

## Troubleshooting

### Connection Issues

1. **Context Store API unreachable:**
   ```bash
   # Check if port 8000 is listening
   netstat -tlnp | grep :8000
   
   # Test firewall rules
   telnet your-server 8000
   ```

2. **Services can't communicate internally:**
   ```bash
   # Check Docker network
   docker network ls
   docker network inspect context-store_context-store-network
   
   # Test inter-service connectivity
   docker exec context-store ping qdrant
   docker exec context-store ping neo4j
   ```

3. **Database connection errors:**
   ```bash
   # Check if services are up
   docker-compose ps
   
   # Check service logs
   docker-compose logs qdrant
   docker-compose logs neo4j
   docker-compose logs redis
   ```

## Emergency Access

In case you need emergency access to databases:

```bash
# Temporary firewall rule for database access
# WARNING: Remove immediately after use
sudo ufw allow from YOUR_IP_ADDRESS to any port 7474
sudo ufw allow from YOUR_IP_ADDRESS to any port 7687

# Remember to remove the rule
sudo ufw delete allow from YOUR_IP_ADDRESS to any port 7474
sudo ufw delete allow from YOUR_IP_ADDRESS to any port 7687
```

---

**Important:** Always test firewall rules in a development environment before applying to production. Incorrect firewall configuration can lock you out of your server or expose sensitive services to the internet.