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

# Validate environment variables for security compliance
validate_environment_variables() {
    log "🔒 Validating environment variables for security compliance..."
    
    # Check for required environment variables
    local required_vars=(
        "HETZNER_HOST"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
    done
    
    # Validate HETZNER_HOST format (should be IP or FQDN)
    if [[ ! "$HETZNER_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$ ]] && [[ ! "$HETZNER_HOST" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        error "HETZNER_HOST must be a valid hostname or IP address"
    fi
    
    # Validate HETZNER_USER if provided
    if [[ -n "${HETZNER_USER:-}" ]]; then
        if [[ ! "$HETZNER_USER" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]]; then
            error "HETZNER_USER must be a valid username (alphanumeric, underscore, hyphen)"
        fi
        if [[ ${#HETZNER_USER} -gt 32 ]]; then
            error "HETZNER_USER too long (max 32 characters)"
        fi
    fi
    
    # Check for potentially insecure environment variables
    local insecure_patterns=(
        "password=.*"
        "token=.*"
        "secret=.*"
        "key=.*"
    )
    
    for pattern in "${insecure_patterns[@]}"; do
        if env | grep -i "$pattern" | grep -v "^_" > /dev/null 2>&1; then
            warn "Potentially sensitive data found in environment variables"
            warn "Ensure secrets are properly protected and not logged"
        fi
    done
    
    log "✅ Environment variable validation passed"
}

# Validate environment file content on remote host
validate_remote_environment() {
    log "🔐 Validating remote environment file security..."
    
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        if [ -f .env.production ]; then
            echo 'Validating .env.production file...'
            
            # Check file permissions
            perm=\$(stat -c '%a' .env.production)
            if [ \"\$perm\" != \"600\" ]; then
                echo 'ERROR: .env.production has insecure permissions (\$perm). Should be 600.'
                exit 1
            fi
            
            # Check for placeholder values that weren't replaced
            if grep -q 'your_secure.*_here' .env.production; then
                echo 'ERROR: Found unreplaced placeholder values in .env.production'
                grep 'your_secure.*_here' .env.production
                exit 1
            fi
            
            # Validate password complexity
            if grep -q '^NEO4J_PASSWORD=' .env.production; then
                neo4j_pass=\$(grep '^NEO4J_PASSWORD=' .env.production | cut -d'=' -f2)
                if [ \${#neo4j_pass} -lt 16 ]; then
                    echo 'ERROR: NEO4J_PASSWORD too short (minimum 16 characters)'
                    exit 1
                fi
            fi
            
            # Validate required variables are present
            required_vars=(
                'VERIS_HOST'
                'REDIS_PASSWORD'
                'NEO4J_PASSWORD'
                'JWT_SECRET_KEY'
            )
            
            for var in \"\${required_vars[@]}\"; do
                if ! grep -q \"^\$var=\" .env.production; then
                    echo \"ERROR: Required variable \$var not found in .env.production\"
                    exit 1
                fi
                
                # Check for empty values
                value=\$(grep \"^\$var=\" .env.production | cut -d'=' -f2)
                if [ -z \"\$value\" ]; then
                    echo \"ERROR: Variable \$var has empty value\"
                    exit 1
                fi
            done
            
            # Validate JWT secret length
            jwt_secret=\$(grep '^JWT_SECRET_KEY=' .env.production | cut -d'=' -f2)
            if [ \${#jwt_secret} -lt 32 ]; then
                echo 'ERROR: JWT_SECRET_KEY too short (minimum 32 characters)'
                exit 1
            fi
            
            echo '✅ Environment file validation passed'
        else
            echo 'WARNING: .env.production file not found'
        fi
    " || error "Environment validation failed on remote host"
    
    log "✅ Remote environment validation passed"
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
            REDIS_PASS=\$(openssl rand -base64 32)
            NEO4J_PASS=\$(openssl rand -base64 32)
            JWT_SECRET=\$(openssl rand -base64 48)
            ANALYTICS_TOKEN=\$(openssl rand -base64 48)
            
            # Update the environment file (fill in empty values with secure tokens)
            sed -i \"s/^REDIS_PASSWORD=$/REDIS_PASSWORD=\$REDIS_PASS/g\" .env.production
            sed -i \"s/^NEO4J_PASSWORD=$/NEO4J_PASSWORD=\$NEO4J_PASS/g\" .env.production
            sed -i \"s/^JWT_SECRET_KEY=$/JWT_SECRET_KEY=\$JWT_SECRET/g\" .env.production
            sed -i \"s/^ANALYTICS_AUTH_TOKEN=$/ANALYTICS_AUTH_TOKEN=\$ANALYTICS_TOKEN/g\" .env.production
            
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

# Trigger post-deployment backup
trigger_post_deployment_backup() {
    log "💾 Triggering post-deployment backup to refresh backup data..."

    # SECURITY: Validate SSH_TARGET before using in remote commands
    if [[ -z "$SSH_TARGET" ]]; then
        error "SSH_TARGET not set, cannot trigger backup"
    fi

    # SECURITY: Validate REMOTE_DIR is set and doesn't contain suspicious characters
    if [[ -z "$REMOTE_DIR" ]]; then
        error "REMOTE_DIR not set, cannot trigger backup"
    fi
    if [[ "$REMOTE_DIR" =~ [';|&$`'] ]]; then
        error "REMOTE_DIR contains suspicious characters, possible command injection attempt"
    fi

    ssh "$SSH_TARGET" "
        # SECURITY: Change to directory safely
        cd \"\$REMOTE_DIR\" || {
            echo 'ERROR: Could not change to REMOTE_DIR'
            exit 1
        }

        echo 'Creating post-deployment backup...'

        # PR #274: Check if backup script exists
        # This script is required for S6 backup validation to pass
        # Script location: scripts/backup-production-final.sh
        # Script verified to exist in repository (6647 bytes, executable)
        if [ -f ./scripts/backup-production-final.sh ]; then
            echo 'Running backup script...'
            # Execute with timeout to prevent hanging
            timeout 300 bash ./scripts/backup-production-final.sh || {
                echo 'Warning: Backup script failed or timed out, but continuing deployment'
                exit 0  # Don't fail deployment if backup fails
            }
        else
            echo 'Warning: Backup script not found at ./scripts/backup-production-final.sh'
            echo 'Attempting alternative backup methods...'

            # Alternative: Trigger backup via API if available
            if curl -f -s http://127.0.0.1:8001/admin/backup > /dev/null 2>&1; then
                echo 'Triggered backup via API'
            else
                echo 'Warning: Could not trigger backup via API'
                echo 'S6 backup validation may fail until next scheduled backup runs'
            fi
        fi

        echo '✅ Post-deployment backup attempt completed'
    " || warn "Post-deployment backup failed, but continuing deployment"

    log "✅ Post-deployment backup triggered (S6 will validate on next run)"
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
    validate_environment_variables
    configure_firewall
    deploy_monitoring_config
    validate_remote_environment
    deploy_services
    validate_deployment
    trigger_post_deployment_backup  # Refresh backup data for S6 validation
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