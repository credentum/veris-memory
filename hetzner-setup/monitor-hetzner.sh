#!/bin/bash
# Monitor Hetzner Context Store Deployment
# Provides real-time monitoring and health checks

set -euo pipefail

# Configuration
HETZNER_HOST="135.181.4.118"
HETZNER_USER="root"
MONITOR_INTERVAL=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Status tracking
declare -A SERVICE_STATUS
declare -A LAST_CHECK

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check service health
check_service_health() {
    local service=$1
    local port=$2
    local check_cmd=$3
    
    ssh -o ConnectTimeout=5 "$HETZNER_USER@$HETZNER_HOST" "$check_cmd" &>/dev/null
    local status=$?
    
    if [ $status -eq 0 ]; then
        SERVICE_STATUS[$service]="✅ OK"
        return 0
    else
        SERVICE_STATUS[$service]="❌ FAIL"
        return 1
    fi
}

# Get system metrics
get_system_metrics() {
    ssh "$HETZNER_USER@$HETZNER_HOST" << 'EOF'
echo "=== SYSTEM METRICS ==="
echo "Time: $(date)"
echo "Uptime: $(uptime -p)"

echo ""
echo "=== MEMORY USAGE ==="
free -h | grep -E "^Mem:|^Swap:"

echo ""
echo "=== DISK USAGE ==="
df -h /raid1 2>/dev/null || df -h /

echo ""
echo "=== LOAD AVERAGE ==="
cat /proc/loadavg

echo ""
echo "=== CONTAINER STATUS ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== CONTAINER RESOURCES ==="
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
EOF
}

# Check security status
check_security_status() {
    ssh "$HETZNER_USER@$HETZNER_HOST" << 'EOF'
echo "=== SECURITY STATUS ==="
echo "UFW Firewall: $(ufw status | grep Status | cut -d: -f2)"
echo "fail2ban Status: $(systemctl is-active fail2ban 2>/dev/null || echo 'inactive')"

echo ""
echo "=== RECENT SECURITY EVENTS ==="
echo "Recent auth failures (last 10):"
grep "authentication failure\|Failed password" /var/log/auth.log 2>/dev/null | tail -5 || echo "No recent failures"

echo ""
echo "=== FIREWALL RULES ==="
ufw status numbered | head -10
EOF
}

# Monitor loop
monitor_loop() {
    while true; do
        clear
        echo "===========================================" 
        echo "🖥️  HETZNER CONTEXT STORE MONITOR"
        echo "🕐 $(date)"
        echo "🌐 Host: $HETZNER_HOST"
        echo "==========================================="
        echo ""
        
        # Check service health
        info "Checking service health..."
        check_service_health "Redis" "6379" "echo 'PING' | nc -w 2 localhost 6379 | grep -q PONG"
        check_service_health "Neo4j" "7474" "timeout 3 bash -c '</dev/tcp/localhost/7474'"
        check_service_health "Qdrant" "6333" "curl -s -m 3 http://localhost:6333/ | grep -q qdrant"
        
        # Display service status
        echo "🔧 SERVICE STATUS:"
        for service in "${!SERVICE_STATUS[@]}"; do
            echo "   $service: ${SERVICE_STATUS[$service]}"
        done
        echo ""
        
        # Get detailed metrics
        info "System metrics..."
        get_system_metrics
        echo ""
        
        info "Security status..."
        check_security_status
        
        echo ""
        echo "==========================================="
        info "Next check in $MONITOR_INTERVAL seconds (Ctrl+C to exit)"
        echo "==========================================="
        
        sleep $MONITOR_INTERVAL
    done
}

# One-time health check
health_check() {
    echo "===========================================" 
    echo "🏥 HETZNER CONTEXT STORE HEALTH CHECK"
    echo "🕐 $(date)"
    echo "==========================================="
    echo ""
    
    # Test SSH connection
    if ssh -o ConnectTimeout=10 "$HETZNER_USER@$HETZNER_HOST" "echo 'SSH connection successful'" &>/dev/null; then
        log "✅ SSH connection successful"
    else
        error "❌ SSH connection failed"
        exit 1
    fi
    
    # Check services
    info "Checking service health..."
    redis_ok=0
    neo4j_ok=0
    qdrant_ok=0
    
    if check_service_health "Redis" "6379" "echo 'PING' | nc -w 2 localhost 6379 | grep -q PONG"; then
        redis_ok=1
    fi
    
    if check_service_health "Neo4j" "7474" "timeout 3 bash -c '</dev/tcp/localhost/7474'"; then
        neo4j_ok=1
    fi
    
    if check_service_health "Qdrant" "6333" "curl -s -m 3 http://localhost:6333/ | grep -q qdrant"; then
        qdrant_ok=1
    fi
    
    # Display results
    echo ""
    echo "🔧 SERVICE STATUS:"
    echo "   Redis: ${SERVICE_STATUS[Redis]}"
    echo "   Neo4j: ${SERVICE_STATUS[Neo4j]}"
    echo "   Qdrant: ${SERVICE_STATUS[Qdrant]}"
    echo ""
    
    # Overall health
    if [ $redis_ok -eq 1 ] && [ $neo4j_ok -eq 1 ] && [ $qdrant_ok -eq 1 ]; then
        log "🎉 OVERALL HEALTH: EXCELLENT - All services operational"
        exit 0
    else
        warn "⚠️ OVERALL HEALTH: DEGRADED - Some services have issues"
        exit 1
    fi
}

# Show usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  monitor    Start continuous monitoring (default)"
    echo "  check      One-time health check"
    echo "  help       Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 monitor     # Start continuous monitoring"
    echo "  $0 check       # Quick health check"
}

# Main function
main() {
    local command="${1:-monitor}"
    
    case $command in
        monitor)
            log "Starting continuous monitoring..."
            monitor_loop
            ;;
        check)
            health_check
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Monitoring stopped by user${NC}"; exit 0' INT

# Run main function
main "$@"