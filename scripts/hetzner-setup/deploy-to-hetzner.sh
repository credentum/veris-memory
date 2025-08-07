#!/bin/bash
# Deploy Context Store to Hetzner Dedicated Server
# This script should be run from the veris-memory repository with proper SSH access

set -euo pipefail

# Configuration
HETZNER_HOST="135.181.4.118"
HETZNER_USER="root"
REMOTE_DIR="/opt/context-store"
LOG_FILE="/tmp/hetzner-deploy-$(date +%s).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "🔍 Checking prerequisites..."
    
    if ! command -v ssh &> /dev/null; then
        error "SSH client not found"
    fi
    
    if ! command -v scp &> /dev/null; then
        error "SCP not found"
    fi
    
    # Test SSH connection
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$HETZNER_USER@$HETZNER_HOST" "echo 'SSH test successful'" &>/dev/null; then
        error "Cannot connect to Hetzner server. Please ensure SSH key is configured."
    fi
    
    log "✅ Prerequisites check passed"
}

# Deploy files to server
deploy_files() {
    log "📦 Deploying files to Hetzner server..."
    
    # Create remote directory
    ssh "$HETZNER_USER@$HETZNER_HOST" "mkdir -p $REMOTE_DIR"
    
    # Copy deployment files
    scp -r context-store/scripts/hetzner-setup/ "$HETZNER_USER@$HETZNER_HOST:$REMOTE_DIR/"
    scp context-store/docker-compose.simple.yml "$HETZNER_USER@$HETZNER_HOST:$REMOTE_DIR/"
    scp context-store/.ctxrc.hetzner.yaml "$HETZNER_USER@$HETZNER_HOST:$REMOTE_DIR/"
    
    log "✅ Files deployed successfully"
}

# Run deployment on server
run_deployment() {
    log "🚀 Running deployment on Hetzner server..."
    
    ssh "$HETZNER_USER@$HETZNER_HOST" << 'EOF'
set -euo pipefail
cd /opt/context-store

# Make scripts executable
chmod +x hetzner-setup/*.sh

# Run fresh server setup
echo "Starting fresh server setup..."
./hetzner-setup/fresh-server-setup.sh

echo "Deployment completed on server"
EOF
    
    log "✅ Deployment completed on server"
}

# Monitor deployment
monitor_deployment() {
    log "📊 Monitoring deployment health..."
    
    ssh "$HETZNER_USER@$HETZNER_HOST" << 'EOF'
set -euo pipefail
cd /opt/context-store

# Run validation script
if [ -f hetzner-setup/validate-deployment.sh ]; then
    echo "Running deployment validation..."
    ./hetzner-setup/validate-deployment.sh
else
    echo "Validation script not found, running basic health checks..."
    
    echo "=== Container Status ==="
    docker ps --format "{{.Names}}: {{.Status}}"
    
    echo "=== Service Health ==="
    echo -n "Redis: "
    if echo "PING" | nc -w 2 localhost 6379 | grep -q PONG; then
        echo "OK"
    else
        echo "FAIL"
    fi
    
    echo -n "Neo4j: "
    if timeout 3 bash -c "</dev/tcp/localhost/7474" 2>/dev/null; then
        echo "OK"
    else
        echo "FAIL"
    fi
    
    echo -n "Qdrant: "
    if curl -s -m 3 http://localhost:6333/ | grep -q "qdrant"; then
        echo "OK"
    else
        echo "FAIL"
    fi
    
    echo "=== Security Status ==="
    echo "UFW Status: $(ufw status | grep Status | cut -d: -f2)"
    echo "fail2ban Status: $(systemctl is-active fail2ban)"
fi
EOF
    
    log "✅ Deployment monitoring completed"
}

# Main deployment process
main() {
    log "🚀 Starting Hetzner Context Store Deployment"
    log "============================================"
    log "Target: $HETZNER_HOST"
    log "Remote Directory: $REMOTE_DIR"
    log "Log File: $LOG_FILE"
    log ""
    
    check_prerequisites
    deploy_files
    run_deployment
    monitor_deployment
    
    log ""
    log "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
    log "============================================"
    log "📊 Access services via SSH tunnel:"
    log "   ssh -L 6379:localhost:6379 -L 7474:localhost:7474 -L 6333:localhost:6333 $HETZNER_USER@$HETZNER_HOST"
    log "📝 View logs: cat $LOG_FILE"
    log "🔧 Monitor: ssh $HETZNER_USER@$HETZNER_HOST 'docker logs -f <container_name>'"
}

# Run main function
main "$@"