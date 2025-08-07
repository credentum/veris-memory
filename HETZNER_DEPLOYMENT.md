# Hetzner Dedicated Server Deployment

This directory contains automation scripts for deploying the Context Store to Hetzner dedicated servers.

## Quick Deployment

### Prerequisites

1. SSH access to Hetzner server (135.181.4.118) configured
2. SSH key added to Codespace secrets as `HETZNER_SSH_KEY`
3. Server should be fresh Ubuntu 24.04 with RAID1 configured

### One-Command Deployment

```bash
# Deploy to Hetzner server
./hetzner-setup/deploy-to-hetzner.sh

# Monitor deployment
./hetzner-setup/monitor-hetzner.sh check
```

### Manual Server Setup

If you need to set up the server manually:

```bash
# SSH to server
ssh root@135.181.4.118

# Run fresh setup script
curl -sSL https://raw.githubusercontent.com/credentum/veris-memory/main/hetzner-setup/fresh-server-setup.sh | bash
```

## Monitoring

### Continuous Monitoring

```bash
# Start real-time monitoring dashboard
./hetzner-setup/monitor-hetzner.sh monitor
```

### Health Checks

```bash
# Quick health check
./hetzner-setup/monitor-hetzner.sh check

# Detailed validation
ssh root@135.181.4.118 "/opt/context-store/hetzner-setup/validate-deployment.sh"
```

### Service Access

Access services via SSH tunnel:

```bash
ssh -L 6379:localhost:6379 -L 7474:localhost:7474 -L 6333:localhost:6333 root@135.181.4.118
```

Then access:
- Redis: `localhost:6379`
- Neo4j: `localhost:7474` (HTTP), `localhost:7687` (Bolt)  
- Qdrant: `localhost:6333`

## Security Features

- UFW firewall (SSH only)
- fail2ban intrusion detection
- Daily security monitoring
- Container privilege restrictions
- Database services bound to localhost only

## Files Overview

- `hetzner-setup/fresh-server-setup.sh` - Complete server setup from scratch
- `hetzner-setup/deploy-to-hetzner.sh` - Deploy from local machine to server
- `hetzner-setup/monitor-hetzner.sh` - Real-time monitoring and health checks
- `hetzner-setup/validate-deployment.sh` - Comprehensive deployment validation
- `docker-compose.simple.yml` - Production Docker compose configuration
- `.ctxrc.hetzner.yaml` - High-performance configuration for 64GB system

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   ```bash
   # Check SSH key
   ssh-keygen -l -f ~/.ssh/id_rsa
   
   # Test connection
   ssh -v root@135.181.4.118
   ```

2. **Services Not Starting**
   ```bash
   # Check container logs
   ssh root@135.181.4.118 "docker logs redis"
   ssh root@135.181.4.118 "docker logs neo4j"
   ssh root@135.181.4.118 "docker logs qdrant"
   ```

3. **Performance Issues**
   ```bash
   # Check system resources
   ssh root@135.181.4.118 "free -h && df -h"
   
   # Monitor in real-time
   ./hetzner-setup/monitor-hetzner.sh monitor
   ```

### Support

For deployment issues, check logs at:
- Local: `/tmp/hetzner-deploy-*.log`
- Server: `/var/log/veris-setup/setup.log`
- Security: `/var/log/veris-security/security-snapshot-*.log`