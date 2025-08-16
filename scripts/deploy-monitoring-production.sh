#!/bin/bash
# Deploy Veris Memory Monitoring System to Hetzner Production
# Specialized script for monitoring infrastructure deployment

set -euo pipefail

# Configuration
HETZNER_HOST="${HETZNER_HOST:-hetzner-server}"
HETZNER_USER="${HETZNER_USER:-}"
REMOTE_DIR="/opt/veris-memory"
LOG_FILE="/tmp/monitoring-deploy-$(date +%Y%m%d-%H%M%S).log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# SSH target
SSH_TARGET="${HETZNER_USER:+$HETZNER_USER@}$HETZNER_HOST"

# Check prerequisites
check_prerequisites() {
    log "🔍 Checking prerequisites for monitoring deployment..."
    
    if ! command -v ssh &> /dev/null; then
        error "SSH client not found"
    fi
    
    # Test SSH connectivity
    if ! ssh -o ConnectTimeout=10 "$SSH_TARGET" "echo 'SSH connection successful'" &>/dev/null; then
        error "Cannot connect to Hetzner server. Check SSH configuration."
    fi
    
    # Check if docker and docker-compose are available
    if ! ssh "$SSH_TARGET" "command -v docker && command -v docker-compose" &>/dev/null; then
        error "Docker and docker-compose must be installed on the target server"
    fi
    
    log "✅ Prerequisites check passed"
}

# Configure firewall for monitoring
configure_firewall() {
    log "🔥 Configuring UFW firewall for monitoring endpoints..."
    
    ssh "$SSH_TARGET" "
        # Ensure UFW is available
        if ! command -v ufw &>/dev/null; then
            echo 'UFW not installed, installing...'
            sudo apt-get update && sudo apt-get install -y ufw
        fi
        
        # Configure firewall rules for monitoring
        echo 'Configuring UFW rules for Veris Memory monitoring...'
        
        # Allow SSH (if not already allowed)
        sudo ufw allow 22/tcp comment 'SSH access'
        
        # Allow local access to monitoring endpoints
        sudo ufw allow from 127.0.0.1 to any port 8001 comment 'Veris API (localhost only)'
        sudo ufw allow from 127.0.0.1 to any port 8080 comment 'Monitoring Dashboard (localhost only)'
        
        # Optional: Claude CLI dev port (if needed)
        sudo ufw allow 2222/tcp comment 'Claude CLI dev (optional)'
        
        # Enable UFW if not already enabled
        sudo ufw --force enable
        
        # Show current status
        echo 'Current UFW status:'
        sudo ufw status numbered
    "
    
    log "✅ Firewall configuration completed"
}

# Deploy monitoring configuration
deploy_monitoring_config() {
    log "⚙️ Deploying monitoring configuration..."
    
    # Copy production environment template
    scp .env.production.template "$SSH_TARGET:$REMOTE_DIR/.env.production.template"
    
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Create production environment file if it doesn't exist
        if [ ! -f .env.production ]; then
            echo 'Creating production environment file from template...'
            cp .env.production.template .env.production
            
            # Generate secure tokens
            NEO4J_PASS=\$(openssl rand -base64 32)
            ANALYTICS_TOKEN=\$(openssl rand -base64 48)
            
            # Update the environment file
            sed -i \"s/your_secure_neo4j_password_here/\$NEO4J_PASS/g\" .env.production
            sed -i \"s/your_secure_analytics_token_here/\$ANALYTICS_TOKEN/g\" .env.production
            
            echo '✅ Production environment file created with secure tokens'
        else
            echo '✅ Production environment file already exists'
        fi
        
        # Set secure permissions
        chmod 600 .env.production
        
        echo 'Production environment configured:'
        grep -E '^[A-Z_]+=.*' .env.production | grep -v PASSWORD | grep -v TOKEN || true
    "
    
    log "✅ Monitoring configuration deployed"
}

# Deploy and start monitoring services
deploy_services() {
    log "🚀 Deploying monitoring services..."
    
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Stop existing services gracefully
        echo 'Stopping existing services...'
        docker-compose -f docker-compose.prod.yml down --timeout 30 || true
        
        # Pull latest images
        echo 'Pulling latest Docker images...'
        docker-compose -f docker-compose.prod.yml pull
        
        # Start services with production environment
        echo 'Starting production services with monitoring...'
        docker-compose -f docker-compose.prod.yml --env-file .env.production up -d
        
        # Wait for services to be ready
        echo 'Waiting for services to start...'
        sleep 30
        
        # Check service health
        echo 'Checking service health...'
        docker-compose -f docker-compose.prod.yml ps
    "
    
    log "✅ Services deployed and running"
}

# Validate monitoring deployment
validate_deployment() {
    log "🔍 Validating monitoring deployment..."
    
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Test health endpoints
        echo 'Testing health endpoints...'
        
        # Test API health
        if curl -f -s http://127.0.0.1:8001/health/live > /dev/null; then
            echo '✅ API health endpoint responding'
        else
            echo '❌ API health endpoint not responding'
            exit 1
        fi
        
        # Test monitoring dashboard
        if curl -f -s http://127.0.0.1:8080/api/dashboard/health > /dev/null; then
            echo '✅ Monitoring dashboard responding'
        else
            echo '❌ Monitoring dashboard not responding'
            exit 1
        fi
        
        # Test database connections
        echo 'Testing database connectivity...'
        
        # Check if all containers are healthy
        UNHEALTHY=\$(docker-compose -f docker-compose.prod.yml ps --filter 'health=unhealthy' -q)
        if [ -n \"\$UNHEALTHY\" ]; then
            echo '❌ Some containers are unhealthy:'
            docker-compose -f docker-compose.prod.yml ps --filter 'health=unhealthy'
            exit 1
        else
            echo '✅ All containers are healthy'
        fi
        
        # Get current system resource usage
        echo '📊 Current system resources:'
        echo 'Memory usage:'
        free -h
        echo 'CPU usage:'
        top -bn1 | grep 'Cpu(s)' || true
        echo 'Disk usage:'
        df -h /opt
        
        echo '🎉 Monitoring deployment validation successful!'
    "
    
    log "✅ Deployment validation completed"
}

# Performance test
performance_test() {
    log "⚡ Running performance test on 64GB system..."
    
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        echo 'Running performance smoke test...'
        
        # Simple load test using curl
        echo 'Testing API response times...'
        for i in {1..10}; do
            START_TIME=\$(date +%s%N)
            curl -s http://127.0.0.1:8001/health/live > /dev/null
            END_TIME=\$(date +%s%N)
            RESPONSE_TIME=\$(( (END_TIME - START_TIME) / 1000000 ))
            echo \"API call \$i: \${RESPONSE_TIME}ms\"
        done
        
        # Test monitoring endpoints
        echo 'Testing monitoring response times...'
        for i in {1..5}; do
            START_TIME=\$(date +%s%N)
            curl -s http://127.0.0.1:8080/api/dashboard > /dev/null
            END_TIME=\$(date +%s%N)
            RESPONSE_TIME=\$(( (END_TIME - START_TIME) / 1000000 ))
            echo \"Dashboard call \$i: \${RESPONSE_TIME}ms\"
        done
        
        # Check memory usage after load
        echo 'Memory usage after performance test:'
        docker stats --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
    "
    
    log "✅ Performance test completed"
}

# Main deployment flow
main() {
    log "🚀 Starting Veris Memory Monitoring Deployment to Hetzner"
    log "Target: $SSH_TARGET"
    log "Remote directory: $REMOTE_DIR"
    log "Log file: $LOG_FILE"
    
    check_prerequisites
    configure_firewall
    deploy_monitoring_config
    deploy_services
    validate_deployment
    performance_test
    
    log "🎉 Monitoring deployment completed successfully!"
    log "📊 Access monitoring dashboard at: http://127.0.0.1:8080/api/dashboard"
    log "🔗 API health check at: http://127.0.0.1:8001/health/live"
    log "📝 Deployment log saved to: $LOG_FILE"
    
    info "Next steps:"
    info "1. Set up external monitoring/alerting if needed"
    info "2. Configure backup schedules for monitoring data"
    info "3. Set up log rotation for application logs"
    info "4. Consider implementing the autonomous monitoring agent (Issue #46)"
}

# Run main function
main "$@"