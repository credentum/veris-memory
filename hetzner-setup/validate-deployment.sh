#!/bin/bash
# Hetzner Context Store Deployment Validation Script
# Runs comprehensive security and functionality tests

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Test functions
test_pass() {
    echo -e "${GREEN}✅ PASS: $1${NC}"
    ((PASS_COUNT++))
}

test_fail() {
    echo -e "${RED}❌ FAIL: $1${NC}"
    ((FAIL_COUNT++))
}

test_warn() {
    echo -e "${YELLOW}⚠️ WARN: $1${NC}"
}

test_info() {
    echo -e "${BLUE}ℹ️ INFO: $1${NC}"
}

echo "=============================================="
echo "🔍 HETZNER CONTEXT STORE DEPLOYMENT VALIDATION"
echo "=============================================="
echo ""

# Test 1: Database Connectivity
echo "🗄️ Testing Database Connectivity..."
if echo "PING" | nc -w 2 localhost 6379 | grep -q PONG; then
    test_pass "Redis responding on port 6379"
else
    test_fail "Redis not responding on port 6379"
fi

if timeout 3 bash -c "</dev/tcp/localhost/7474" 2>/dev/null; then
    test_pass "Neo4j HTTP port 7474 accessible"
else
    test_fail "Neo4j HTTP port 7474 not accessible"
fi

if timeout 3 bash -c "</dev/tcp/localhost/7687" 2>/dev/null; then
    test_pass "Neo4j Bolt port 7687 accessible"
else
    test_fail "Neo4j Bolt port 7687 not accessible"
fi

if curl -s -m 3 http://localhost:6333/ | grep -q "qdrant"; then
    test_pass "Qdrant responding on port 6333"
else
    test_fail "Qdrant not responding on port 6333"
fi

echo ""

# Test 2: Security Configuration
echo "🔒 Testing Security Configuration..."
if ss -tlnp | grep -E ":6379|:7474|:7687|:6333" | grep -q "127.0.0.1"; then
    test_pass "Database services bound to localhost only"
else
    test_fail "Database services not properly bound to localhost"
fi

external_ports=$(ss -tlnp | grep -v "127.0.0.1" | grep LISTEN | grep -v ":22" | wc -l)
if [ "$external_ports" -eq 0 ]; then
    test_pass "No unauthorized external ports exposed"
else
    test_fail "$external_ports unauthorized external ports detected"
fi

if ufw status | grep -q "Status: active"; then
    test_pass "UFW firewall is active"
else
    test_fail "UFW firewall is not active"
fi

if systemctl is-active fail2ban >/dev/null 2>&1; then
    test_pass "fail2ban IDS is running"
else
    test_fail "fail2ban IDS is not running"
fi

echo ""

# Test 3: Container Security
echo "🐳 Testing Container Security..."
privileged_containers=0
for container in $(docker ps --format "{{.Names}}" 2>/dev/null); do
    if docker inspect "$container" | grep -q '"Privileged": true'; then
        ((privileged_containers++))
    fi
done

if [ "$privileged_containers" -eq 0 ]; then
    test_pass "No privileged containers detected"
else
    test_fail "$privileged_containers privileged containers found"
fi

# Check container users
root_containers=0
for container in $(docker ps --format "{{.Names}}" 2>/dev/null); do
    if docker exec "$container" ps aux 2>/dev/null | grep -q "^root.*[^[]"; then
        container_processes=$(docker exec "$container" ps aux 2>/dev/null | grep "^root" | wc -l)
        if [ "$container_processes" -gt 1 ]; then  # Allow tini/init process
            ((root_containers++))
        fi
    fi
done

if [ "$root_containers" -eq 0 ]; then
    test_pass "Containers running with appropriate user privileges"
else
    test_warn "$root_containers containers may be running as root"
fi

echo ""

# Test 4: Resource Utilization
echo "📊 Testing Resource Utilization..."
memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$memory_usage" -lt 90 ]; then
    test_pass "Memory usage: ${memory_usage}% (healthy)"
else
    test_warn "Memory usage: ${memory_usage}% (high)"
fi

if df /raid1 >/dev/null 2>&1; then
    disk_usage=$(df /raid1 | awk 'NR==2{print $5}' | sed 's/%//')
    if [ "$disk_usage" -lt 80 ]; then
        test_pass "RAID1 disk usage: ${disk_usage}% (healthy)"
    else
        test_warn "RAID1 disk usage: ${disk_usage}% (high)"
    fi
else
    test_fail "RAID1 storage not mounted at /raid1"
fi

echo ""

# Test 5: Monitoring and Logging
echo "📝 Testing Monitoring and Logging..."
if [ -f "/opt/security-monitoring/daily-security-snapshot.sh" ]; then
    test_pass "Security monitoring script installed"
else
    test_fail "Security monitoring script not found"
fi

if grep -q "security-snapshot" /etc/crontab; then
    test_pass "Daily security monitoring cron job configured"
else
    test_fail "Daily security monitoring cron job not configured"
fi

if [ -d "/var/log/veris-security" ]; then
    test_pass "Security log directory exists"
else
    test_fail "Security log directory not found"
fi

echo ""

# Test 6: Performance Benchmarks
echo "⚡ Running Performance Tests..."
start_time=$(date +%s.%N)
for i in {1..10}; do
    echo "SET perf:test$i $(date +%s)" | nc -w 1 localhost 6379 >/dev/null 2>&1
done
end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "1")

if (( $(echo "$duration < 5.0" | bc -l) )); then
    test_pass "Redis performance: ${duration}s for 10 operations (good)"
else
    test_warn "Redis performance: ${duration}s for 10 operations (slow)"
fi

echo ""

# Final Report
echo "=============================================="
echo "📋 VALIDATION SUMMARY"
echo "=============================================="
echo "✅ Passed: $PASS_COUNT tests"
echo "❌ Failed: $FAIL_COUNT tests"
echo ""

# Define specific exit codes for different failure types
EXIT_SUCCESS=0
EXIT_GENERAL_FAILURE=1
EXIT_DATABASE_FAILURE=2
EXIT_SECURITY_FAILURE=3
EXIT_CONTAINER_FAILURE=4
EXIT_RESOURCE_FAILURE=5

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo -e "${GREEN}🎉 OVERALL STATUS: VALIDATION PASSED${NC}"
    echo "Context Store deployment is healthy and secure!"
    exit $EXIT_SUCCESS
else
    echo -e "${RED}⚠️ OVERALL STATUS: VALIDATION ISSUES DETECTED${NC}"
    echo "Please review failed tests and address issues."
    
    # Determine specific failure type based on test results
    if echo "PING" | nc -w 1 localhost 6379 2>/dev/null | grep -q PONG; then
        database_ok=1
    else
        database_ok=0
    fi
    
    if ufw status | grep -q "Status: active"; then
        security_ok=1
    else
        security_ok=0
    fi
    
    container_count=$(docker ps --format "{{.Names}}" 2>/dev/null | wc -l)
    if [ "$container_count" -gt 0 ]; then
        container_ok=1
    else
        container_ok=0
    fi
    
    # Exit with specific code based on failure type
    if [ "$database_ok" -eq 0 ]; then
        echo "❌ Database connectivity issues detected"
        exit $EXIT_DATABASE_FAILURE
    elif [ "$security_ok" -eq 0 ]; then
        echo "❌ Security configuration issues detected"  
        exit $EXIT_SECURITY_FAILURE
    elif [ "$container_ok" -eq 0 ]; then
        echo "❌ Container issues detected"
        exit $EXIT_CONTAINER_FAILURE
    else
        echo "❌ General validation issues detected"
        exit $EXIT_GENERAL_FAILURE
    fi
fi