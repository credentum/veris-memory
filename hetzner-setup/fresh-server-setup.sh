#!/bin/bash
# Hetzner Fresh Server Setup Script
# Reproduces complete Context Store deployment from scratch
# 
# Usage: ./fresh-server-setup.sh
# Requirements: Fresh Ubuntu 24.04 server with RAID1 configured

set -euo pipefail

# Configuration
REPO_URL="https://github.com/credentum/veris-memory.git"
BRANCH="feature/hetzner-deployment"
INSTALL_DIR="/opt/context-store"
LOG_DIR="/var/log/veris-setup"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_DIR/setup.log"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_DIR/setup.log"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_DIR/setup.log"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_DIR/setup.log"
}

# Create log directory
mkdir -p "$LOG_DIR"

log "🚀 Starting Hetzner Context Store Fresh Server Setup"
log "=================================================="

# 1. System Update and Basic Tools
log "📦 Step 1: System Update and Essential Tools"
export DEBIAN_FRONTEND=noninteractive
apt update -y
apt upgrade -y
apt install -y \
    git \
    curl \
    wget \
    nano \
    htop \
    net-tools \
    bc \
    jq \
    netcat-openbsd

# 2. Docker Installation
log "🐳 Step 2: Docker Installation"
if ! command -v docker &> /dev/null; then
    apt install -y docker.io
    systemctl enable docker
    systemctl start docker
    log "✅ Docker installed and started"
else
    log "ℹ️ Docker already installed"
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    log "✅ Docker Compose installed"
fi

# 3. RAID1 Storage Setup Verification  
log "💾 Step 3: RAID1 Storage Verification"

# Validate RAID1 existence and health
validate_raid1() {
    if [ -d "/raid1" ]; then
        # Check if it's actually a RAID1 mount
        if mount | grep -q "/raid1"; then
            log "✅ RAID1 mount found at /raid1"
            # Verify RAID health if mdadm is available
            if command -v mdadm >/dev/null 2>&1; then
                local raid_status=$(cat /proc/mdstat 2>/dev/null | grep "raid1" | wc -l)
                if [ "$raid_status" -gt 0 ]; then
                    log "✅ RAID1 arrays detected and active"
                else
                    warn "⚠️ No RAID1 arrays found in /proc/mdstat"
                fi
            fi
            return 0
        else
            warn "⚠️ /raid1 directory exists but is not mounted"
            return 1
        fi
    else
        warn "⚠️ /raid1 not found"
        return 1
    fi
}

if validate_raid1; then
    mkdir -p /raid1/docker-data/{redis,neo4j,qdrant,logs,monitoring}
    log "✅ Docker data directories created on RAID1"
else
    warn "⚠️ RAID1 validation failed - creating fallback directory"
    mkdir -p /opt/docker-data/{redis,neo4j,qdrant,logs,monitoring}
    ln -s /opt/docker-data /raid1
    warn "⚠️ Using fallback storage at /opt/docker-data (linked as /raid1)"
fi

# 4. Context Store Repository Clone
log "📥 Step 4: Cloning Context Store Repository"
if [ -d "$INSTALL_DIR" ]; then
    log "ℹ️ Installation directory exists, backing up..."
    mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%s)"
fi

git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"
log "✅ Repository cloned to $INSTALL_DIR"

# 5. Environment Configuration
log "⚙️ Step 5: Environment Configuration"
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Context Store Environment Configuration
NEO4J_PASSWORD=secure_neo4j_password_$(openssl rand -hex 8)
TAILSCALE_AUTHKEY=\${TAILSCALE_AUTHKEY}
TAILSCALE_HOSTNAME=veris-memory-hetzner
EOF
    log "✅ Environment file created with secure random password"
else
    log "ℹ️ Environment file already exists"
fi

# 6. UFW Firewall Setup
log "🔥 Step 6: UFW Firewall Configuration"
if command -v ufw &> /dev/null; then
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw --force enable
    log "✅ UFW firewall configured (SSH-only access)"
else
    apt install -y ufw
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw --force enable
    log "✅ UFW installed and configured"
fi

# 7. fail2ban Installation
log "🛡️ Step 7: Intrusion Detection System (fail2ban)"
apt install -y fail2ban

# Configure fail2ban
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600

[docker-log-monitor]
enabled = true
port = all
filter = docker-log-monitor
logpath = /var/log/syslog
maxretry = 3
bantime = 7200
EOF

# Create Docker log filter
cat > /etc/fail2ban/filter.d/docker-log-monitor.conf << 'EOF'
[Definition]
failregex = ^.*dockerd.*error.*<HOST>.*$
            ^.*containerd.*error.*<HOST>.*$
ignoreregex =
EOF

systemctl enable fail2ban
systemctl start fail2ban
log "✅ fail2ban configured and started"

# 8. Daily Security Monitoring Setup
log "📊 Step 8: Security Monitoring Setup"
mkdir -p /opt/security-monitoring

cat > /opt/security-monitoring/daily-security-snapshot.sh << 'EOF'
#!/bin/bash
# Daily Security Snapshot Script for Veris Context Store
# Monitors container users, open ports, and system state

LOG_DIR="/var/log/veris-security"
DATE=$(date +%Y-%m-%d_%H%M%S)

# Create log directory
mkdir -p "$LOG_DIR"

echo "=== Daily Security Snapshot - $DATE ===" > "$LOG_DIR/security-snapshot-$DATE.log"

# 1. Container users and privileges
echo "== Container Users ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
docker ps --format "{{.Names}}: {{.Image}}: {{.Status}}" >> "$LOG_DIR/security-snapshot-$DATE.log" 2>/dev/null || echo "Docker not available" >> "$LOG_DIR/security-snapshot-$DATE.log"

echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== Container Privilege Check ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
for container in $(docker ps --format "{{.Names}}" 2>/dev/null); do
    echo "--- $container ---" >> "$LOG_DIR/security-snapshot-$DATE.log"
    docker inspect "$container" 2>/dev/null | grep -E "\"Privileged\"|\"User\"" >> "$LOG_DIR/security-snapshot-$DATE.log" || echo "Inspection failed" >> "$LOG_DIR/security-snapshot-$DATE.log"
done

# 2. Open ports (excluding localhost)
echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== External Open Ports ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
ss -tlnp | grep -v "127.0.0.1" >> "$LOG_DIR/security-snapshot-$DATE.log" 2>/dev/null || netstat -tulnp | grep -v "127.0.0.1" >> "$LOG_DIR/security-snapshot-$DATE.log" 2>/dev/null

# 3. System resource usage
echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== System Resources ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
free -h >> "$LOG_DIR/security-snapshot-$DATE.log"
df -h /raid1 >> "$LOG_DIR/security-snapshot-$DATE.log" 2>/dev/null

# 4. UFW status
echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== Firewall Status ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
ufw status verbose >> "$LOG_DIR/security-snapshot-$DATE.log" 2>/dev/null

# 5. fail2ban status
echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== Intrusion Detection ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
fail2ban-client status >> "$LOG_DIR/security-snapshot-$DATE.log" 2>/dev/null

# 6. Recent suspicious activity
echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== Recent Auth Attempts (last 24h) ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
grep "authentication failure\|Failed password" /var/log/auth.log 2>/dev/null | tail -20 >> "$LOG_DIR/security-snapshot-$DATE.log"

# 7. Container health
echo "" >> "$LOG_DIR/security-snapshot-$DATE.log"
echo "== Container Health ==" >> "$LOG_DIR/security-snapshot-$DATE.log"
for container in $(docker ps --format "{{.Names}}" 2>/dev/null); do
    echo "--- $container logs (last 5 lines) ---" >> "$LOG_DIR/security-snapshot-$DATE.log"
    docker logs --tail 5 "$container" 2>&1 | head -5 >> "$LOG_DIR/security-snapshot-$DATE.log"
done

# Archive old logs (keep 30 days)
find "$LOG_DIR" -name "security-snapshot-*.log" -mtime +30 -delete

echo "Security snapshot completed: $LOG_DIR/security-snapshot-$DATE.log"
EOF

chmod +x /opt/security-monitoring/daily-security-snapshot.sh

# Add to crontab
echo "0 2 * * * root /opt/security-monitoring/daily-security-snapshot.sh" >> /etc/crontab
log "✅ Daily security monitoring configured"

# 9. Deploy Context Store Services
log "🚀 Step 9: Context Store Service Deployment"
cd "$INSTALL_DIR"

# Create simplified compose file for reliable deployment
cat > docker-compose.simple.yml << 'EOF'
version: "3.8"

services:
  redis:
    image: redis:7.2.5-alpine@sha256:6aaf3f5e6bc8a592fbfe2cccf19eb36d27c39d12dab4f4b01556b7449e7b1f44
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - /raid1/docker-data/redis:/data
    command: >
      redis-server
      --appendonly yes
      --maxmemory 8gb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
      --save 60 10000
    restart: unless-stopped

  neo4j:
    image: neo4j:5.15-community@sha256:69c579facb7acab1e98f28952b91144c89e469a081804a5dafebd6c3030433b8
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
    volumes:
      - /raid1/docker-data/neo4j/data:/data
      - /raid1/docker-data/neo4j/logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_server_memory_heap_initial__size=20G
      - NEO4J_server_memory_heap_max__size=20G
      - NEO4J_server_memory_pagecache_size=16G
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.12.1@sha256:d774e7bb65744454984c6021637a0da89271f30df15e48601a9fafc926d26b1f
    ports:
      - "127.0.0.1:6333:6333"
    volumes:
      - /raid1/docker-data/qdrant:/qdrant/storage
    restart: unless-stopped
EOF

# Start services
docker-compose -f docker-compose.simple.yml up -d
log "✅ Context Store services started"

# 10. Health Check
log "🏥 Step 10: System Health Check"
sleep 30

# Check services
redis_status="FAIL"
neo4j_status="FAIL"
qdrant_status="FAIL"

if echo "PING" | nc -w 2 localhost 6379 | grep -q PONG; then
    redis_status="OK"
fi

if timeout 3 bash -c "</dev/tcp/localhost/7474" 2>/dev/null; then
    neo4j_status="OK"
fi

if curl -s -m 3 http://localhost:6333/ | grep -q "qdrant"; then
    qdrant_status="OK"
fi

# 11. Final Report
log "📋 Step 11: Deployment Summary"
log "=============================================="
log "🎉 HETZNER CONTEXT STORE DEPLOYMENT COMPLETE"
log "=============================================="
log ""
log "📊 Service Status:"
log "  Redis:  $redis_status"
log "  Neo4j:  $neo4j_status"
log "  Qdrant: $qdrant_status"
log ""
log "🔒 Security Status:"
log "  UFW Firewall: $(ufw status | grep -q "Status: active" && echo "ACTIVE" || echo "INACTIVE")"
log "  fail2ban IDS: $(systemctl is-active fail2ban)"
log "  Daily Monitoring: CONFIGURED"
log ""
log "📁 Important Locations:"
log "  Context Store: $INSTALL_DIR"
log "  Data Storage: /raid1/docker-data/"
log "  Security Logs: /var/log/veris-security/"
log "  Setup Logs: $LOG_DIR/"
log ""

if [ "$redis_status" = "OK" ] && [ "$neo4j_status" = "OK" ] && [ "$qdrant_status" = "OK" ]; then
    log "✅ OVERALL STATUS: SUCCESS - All services healthy"
    log "🚀 Context Store is ready for production use!"
else
    error "❌ OVERALL STATUS: FAILURE - Some services are down"
fi

log "=============================================="
log "🔗 Next Steps:"
log "1. Configure Tailscale with: export TAILSCALE_AUTHKEY=your_key"
log "2. Access databases via localhost ports:"
log "   - Redis: 127.0.0.1:6379"
log "   - Neo4j: 127.0.0.1:7474 (HTTP), 127.0.0.1:7687 (Bolt)"
log "   - Qdrant: 127.0.0.1:6333"
log "3. Monitor with: tail -f /var/log/veris-security/security-snapshot-*.log"
log "=============================================="