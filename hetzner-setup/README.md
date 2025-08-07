# Hetzner Context Store Setup Guide

This directory contains scripts and documentation for deploying the Context Store to a Hetzner dedicated server with enterprise-grade security hardening.

## 🚀 Quick Start

### Prerequisites
- Fresh Ubuntu 24.04 server with RAID1 configured
- SSH access as root
- Internet connectivity

### One-Command Deployment
```bash
curl -sSL https://raw.githubusercontent.com/credentum/veris-memory/feature/hetzner-deployment/scripts/hetzner-setup/fresh-server-setup.sh | bash
```

### Manual Deployment
1. Copy `fresh-server-setup.sh` to your server
2. Make executable: `chmod +x fresh-server-setup.sh`
3. Run: `./fresh-server-setup.sh`

## 📋 What Gets Deployed

### Core Services
- **Redis**: High-performance caching (port 6379)
- **Neo4j**: Graph database (ports 7474/7687)
- **Qdrant**: Vector search engine (port 6333)

### Security Hardening
- **UFW Firewall**: SSH-only external access
- **fail2ban IDS**: Automated intrusion detection
- **Container Security**: Non-privileged containers only
- **Daily Monitoring**: Automated security snapshots

### Infrastructure
- **Docker**: Latest stable with Docker Compose
- **RAID1 Storage**: Data redundancy and persistence
- **Resource Optimization**: 64GB RAM configuration
- **Health Monitoring**: Service status tracking

## 🔒 Security Features

### Network Security
```bash
# Only SSH (port 22) exposed externally
# All database services localhost-only (127.0.0.1)
# UFW firewall with deny-by-default policy
```

### Container Security
```bash
# All containers run as non-root users
# Zero privileged containers
# Proper resource limits enforced
```

### Monitoring & Logging
```bash
# Daily security snapshots at 2 AM
# 30-day log retention
# Container privilege monitoring
# Authentication failure tracking
```

## 📁 Directory Structure

```
/opt/context-store/                 # Main installation
├── docker-compose.simple.yml      # Production services
├── .env                           # Environment configuration
└── logs/                          # Application logs

/raid1/docker-data/                # Persistent storage
├── redis/                         # Redis data
├── neo4j/                         # Neo4j data & logs  
├── qdrant/                        # Vector storage
└── logs/                          # Centralized logs

/var/log/veris-security/           # Security monitoring
├── security-snapshot-*.log        # Daily snapshots
└── setup.log                      # Installation logs

/opt/security-monitoring/          # Security scripts
└── daily-security-snapshot.sh     # Monitoring script
```

## 🔧 Configuration

### Environment Variables
Edit `/opt/context-store/.env`:
```bash
NEO4J_PASSWORD=your_secure_password
TAILSCALE_AUTHKEY=your_tailscale_key  
TAILSCALE_HOSTNAME=veris-memory-hetzner
```

### Service Management
```bash
# View service status
cd /opt/context-store
docker-compose -f docker-compose.simple.yml ps

# View logs
docker-compose -f docker-compose.simple.yml logs

# Restart services
docker-compose -f docker-compose.simple.yml restart

# Stop services
docker-compose -f docker-compose.simple.yml down

# Start services
docker-compose -f docker-compose.simple.yml up -d
```

## 🏥 Health Checks

### Quick Status Check
```bash
# Redis
echo "PING" | nc localhost 6379

# Neo4j  
curl http://localhost:7474

# Qdrant
curl http://localhost:6333/
```

### Comprehensive Health Check
```bash
# Run security snapshot
/opt/security-monitoring/daily-security-snapshot.sh

# View latest report
tail -50 /var/log/veris-security/security-snapshot-*.log
```

## 🔍 Security Validation

### Verify Firewall
```bash
sudo ufw status verbose
```

### Check Container Privileges
```bash
docker ps --format "{{.Names}}: {{.Image}}"
for container in $(docker ps --format "{{.Names}}"); do
    docker inspect $container | grep -E "\"Privileged\"|\"User\""
done
```

### Monitor Intrusion Attempts
```bash
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

## 🚨 Troubleshooting

### Services Won't Start
```bash
# Check Docker daemon
sudo systemctl status docker

# Check logs for errors
docker-compose -f docker-compose.simple.yml logs

# Verify RAID1 mount
df -h /raid1
```

### Memory Issues
```bash
# Check available memory
free -h

# Adjust Neo4j heap size in docker-compose.simple.yml
# Default: 20G heap, 16G page cache
```

### Network Connectivity
```bash
# Verify localhost binding
ss -tlnp | grep -E ":6379|:7474|:7687|:6333"

# Check external ports (should only show SSH)
ss -tlnp | grep -v "127.0.0.1"
```

## 📊 Performance Tuning

### For 64GB RAM System (Recommended)
- **Redis**: 8GB memory limit
- **Neo4j**: 20GB heap, 16GB page cache
- **Qdrant**: High-performance vector operations
- **System**: ~18GB available for OS and containers

### For 32GB RAM System
Edit `docker-compose.simple.yml`:
```yaml
neo4j:
  environment:
    - NEO4J_server_memory_heap_initial__size=10G
    - NEO4J_server_memory_heap_max__size=10G
    - NEO4J_server_memory_pagecache_size=8G

redis:
  command: >
    redis-server
    --maxmemory 4gb
    # ... other options
```

## 🔄 Backup & Recovery

### Manual Backup
```bash
# Stop services
docker-compose -f docker-compose.simple.yml down

# Backup data
tar -czf context-store-backup-$(date +%Y%m%d).tar.gz /raid1/docker-data/

# Restart services
docker-compose -f docker-compose.simple.yml up -d
```

### Recovery
```bash
# Stop services
docker-compose -f docker-compose.simple.yml down

# Restore data
tar -xzf context-store-backup-YYYYMMDD.tar.gz -C /

# Restart services
docker-compose -f docker-compose.simple.yml up -d
```

## 📞 Support

### Log Locations
- **Setup**: `/var/log/veris-setup/setup.log`
- **Security**: `/var/log/veris-security/security-snapshot-*.log`
- **Application**: `docker-compose logs`
- **System**: `/var/log/syslog`, `/var/log/auth.log`

### Common Commands
```bash
# View setup log
tail -f /var/log/veris-setup/setup.log

# Monitor security
tail -f /var/log/veris-security/security-snapshot-$(date +%Y-%m-%d)*.log

# Real-time container logs
docker-compose -f docker-compose.simple.yml logs -f

# System resource usage
htop
```

## 🎯 Production Checklist

- [ ] UFW firewall active (SSH-only)
- [ ] fail2ban monitoring SSH attempts  
- [ ] All database services localhost-only
- [ ] Zero privileged containers
- [ ] Daily security monitoring active
- [ ] RAID1 storage mounted and healthy
- [ ] Resource limits appropriate for system
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting configured