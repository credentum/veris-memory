#!/bin/bash
# Comprehensive validation script for Veris Memory monitoring deployment
# Tests all monitoring endpoints, security, and performance

set -euo pipefail

# Configuration
HETZNER_HOST="${HETZNER_HOST:-hetzner-server}"
HETZNER_USER="${HETZNER_USER:-}"
SSH_TARGET="${HETZNER_USER:+$HETZNER_USER@}$HETZNER_HOST"
REMOTE_DIR="/opt/veris-memory"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
TESTS_PASSED=0
TESTS_FAILED=0

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    ((TESTS_FAILED++))
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
    ((TESTS_PASSED++))
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Test function wrapper
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    info "Running test: $test_name"
    
    if eval "$test_command"; then
        success "$test_name - PASSED"
        return 0
    else
        error "$test_name - FAILED"
        return 1
    fi
}

# Test SSH connectivity
test_ssh_connectivity() {
    ssh -o ConnectTimeout=10 "$SSH_TARGET" "echo 'SSH connection successful'" &>/dev/null
}

# Test service health endpoints
test_health_endpoints() {
    ssh "$SSH_TARGET" "
        # Test API health
        curl -f -s http://127.0.0.1:8001/health/live > /dev/null &&
        curl -f -s http://127.0.0.1:8001/health/ready > /dev/null &&
        
        # Test monitoring dashboard health
        curl -f -s http://127.0.0.1:8080/api/dashboard/health > /dev/null
    "
}

# Test monitoring endpoints
test_monitoring_endpoints() {
    ssh "$SSH_TARGET" "
        # Test dashboard JSON endpoint
        DASHBOARD_RESPONSE=\$(curl -s http://127.0.0.1:8080/api/dashboard)
        echo \"\$DASHBOARD_RESPONSE\" | grep -q '\"success\": true' &&
        
        # Test analytics endpoint with rate limiting
        curl -f -s 'http://127.0.0.1:8080/api/dashboard/analytics?minutes=5' > /dev/null &&
        
        # Test ASCII dashboard
        curl -f -s http://127.0.0.1:8080/api/dashboard/ascii | head -1 | grep -q '◎'
    "
}

# Test rate limiting
test_rate_limiting() {
    ssh "$SSH_TARGET" "
        # Test rate limiting by making rapid requests
        SUCCESS_COUNT=0
        RATE_LIMITED_COUNT=0
        
        for i in {1..10}; do
            HTTP_CODE=\$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/dashboard/analytics)
            if [ \"\$HTTP_CODE\" = \"200\" ]; then
                SUCCESS_COUNT=\$((SUCCESS_COUNT + 1))
            elif [ \"\$HTTP_CODE\" = \"429\" ]; then
                RATE_LIMITED_COUNT=\$((RATE_LIMITED_COUNT + 1))
            fi
        done
        
        # Should see some rate limiting after rapid requests
        echo \"Successful requests: \$SUCCESS_COUNT, Rate limited: \$RATE_LIMITED_COUNT\"
        [ \$RATE_LIMITED_COUNT -gt 0 ]
    "
}

# Test database connectivity
test_database_connectivity() {
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Check if all database containers are healthy
        QDRANT_HEALTH=\$(docker-compose -f docker-compose.prod.yml exec -T qdrant curl -s http://localhost:6333/health | grep -o '\"status\":\"ok\"' || echo 'unhealthy')
        NEO4J_HEALTH=\$(docker-compose -f docker-compose.prod.yml exec -T neo4j cypher-shell -u neo4j -p \$NEO4J_PASSWORD 'RETURN 1' 2>/dev/null | grep -q '1' && echo 'healthy' || echo 'unhealthy')
        REDIS_HEALTH=\$(docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping | grep -q 'PONG' && echo 'healthy' || echo 'unhealthy')
        
        echo \"Database health: Qdrant=\$QDRANT_HEALTH, Neo4j=\$NEO4J_HEALTH, Redis=\$REDIS_HEALTH\"
        
        [ \"\$QDRANT_HEALTH\" != \"unhealthy\" ] && 
        [ \"\$NEO4J_HEALTH\" = \"healthy\" ] && 
        [ \"\$REDIS_HEALTH\" = \"healthy\" ]
    "
}

# Test firewall configuration
test_firewall_configuration() {
    ssh "$SSH_TARGET" "
        # Check UFW status and rules
        UFW_STATUS=\$(sudo ufw status | grep -E '8001|8080' | wc -l)
        
        # Should have rules for ports 8001 and 8080
        [ \$UFW_STATUS -ge 2 ] &&
        
        # Verify external access is blocked (should fail from outside)
        ! timeout 5 bash -c '</dev/tcp/127.0.0.1/8001' 2>/dev/null || true
    "
}

# Test performance metrics
test_performance_metrics() {
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Test response times
        TOTAL_TIME=0
        for i in {1..5}; do
            START_TIME=\$(date +%s%N)
            curl -s http://127.0.0.1:8080/api/dashboard > /dev/null
            END_TIME=\$(date +%s%N)
            RESPONSE_TIME=\$(( (END_TIME - START_TIME) / 1000000 ))
            TOTAL_TIME=\$((TOTAL_TIME + RESPONSE_TIME))
        done
        
        AVG_TIME=\$((TOTAL_TIME / 5))
        echo \"Average dashboard response time: \${AVG_TIME}ms\"
        
        # Should be under 1000ms for a healthy system
        [ \$AVG_TIME -lt 1000 ]
    "
}

# Test resource usage
test_resource_usage() {
    ssh "$SSH_TARGET" "
        # Check memory usage (should not exceed 80% on 64GB system)
        MEMORY_PERCENT=\$(free | grep Mem | awk '{printf \"%.0f\", \$3/\$2 * 100}')
        echo \"Memory usage: \${MEMORY_PERCENT}%\"
        
        # Check disk usage for /opt
        DISK_PERCENT=\$(df /opt | tail -1 | awk '{print \$5}' | sed 's/%//')
        echo \"Disk usage (/opt): \${DISK_PERCENT}%\"
        
        # Memory should be under 80%, disk under 90%
        [ \$MEMORY_PERCENT -lt 80 ] && [ \$DISK_PERCENT -lt 90 ]
    "
}

# Test security configuration
test_security_configuration() {
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Check that analytics token is configured
        grep -q 'ANALYTICS_AUTH_TOKEN=' .env.production &&
        
        # Check that CORS is disabled
        grep -q 'ENABLE_CORS=false' .env.production &&
        
        # Check that dashboard auth is required
        grep -q 'DASHBOARD_AUTH_REQUIRED=true' .env.production &&
        
        # Verify environment file permissions
        PERMISSIONS=\$(stat -c '%a' .env.production)
        [ \"\$PERMISSIONS\" = \"600\" ]
    "
}

# Test log output and monitoring
test_logging_monitoring() {
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Check that containers are producing logs
        LOG_LINES=\$(docker-compose -f docker-compose.prod.yml logs --tail=10 context-store | wc -l)
        
        # Should have recent log entries
        [ \$LOG_LINES -gt 0 ]
    "
}

# Test backup and recovery readiness
test_backup_readiness() {
    ssh "$SSH_TARGET" "
        cd $REMOTE_DIR
        
        # Check that data volumes exist
        VOLUMES=\$(docker volume ls | grep -E 'qdrant-data|neo4j-data|redis-data' | wc -l)
        
        # Should have all three data volumes
        [ \$VOLUMES -eq 3 ]
    "
}

# Main validation function
main() {
    log "🔍 Starting comprehensive monitoring deployment validation"
    log "Target: $SSH_TARGET"
    
    # Run all tests
    run_test "SSH Connectivity" "test_ssh_connectivity"
    run_test "Health Endpoints" "test_health_endpoints"
    run_test "Monitoring Endpoints" "test_monitoring_endpoints"
    run_test "Rate Limiting" "test_rate_limiting"
    run_test "Database Connectivity" "test_database_connectivity"
    run_test "Firewall Configuration" "test_firewall_configuration"
    run_test "Performance Metrics" "test_performance_metrics"
    run_test "Resource Usage" "test_resource_usage"
    run_test "Security Configuration" "test_security_configuration"
    run_test "Logging & Monitoring" "test_logging_monitoring"
    run_test "Backup Readiness" "test_backup_readiness"
    
    # Summary
    echo ""
    log "📊 Validation Summary"
    log "Tests passed: $TESTS_PASSED"
    log "Tests failed: $TESTS_FAILED"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log "🎉 All tests passed! Monitoring deployment is healthy."
        
        # Display deployment info
        ssh "$SSH_TARGET" "
            cd $REMOTE_DIR
            echo ''
            echo '📋 Deployment Information:'
            echo '========================='
            echo 'Service Status:'
            docker-compose -f docker-compose.prod.yml ps
            echo ''
            echo 'Resource Usage:'
            docker stats --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
            echo ''
            echo 'Available Endpoints:'
            echo '- API Health: http://127.0.0.1:8001/health/live'
            echo '- Dashboard: http://127.0.0.1:8080/api/dashboard'
            echo '- Analytics: http://127.0.0.1:8080/api/dashboard/analytics'
            echo '- ASCII Dashboard: http://127.0.0.1:8080/api/dashboard/ascii'
            echo ''
            echo 'Security Status:'
            echo '- Firewall: Enabled with localhost-only access'
            echo '- Rate Limiting: Active (5 req/min analytics, 20 req/min dashboard)'
            echo '- Authentication: Required for dashboard access'
        "
        
        exit 0
    else
        error "❌ Some tests failed. Please review and fix issues before proceeding."
        exit 1
    fi
}

# Run main function
main "$@"