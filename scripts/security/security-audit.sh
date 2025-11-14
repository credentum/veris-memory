#!/bin/bash
#
# SECURITY AUDIT AND VALIDATION SCRIPT
# Purpose: Verify security posture and identify vulnerabilities
#
# This script performs comprehensive security checks including:
# - Port exposure analysis
# - Authentication verification
# - Firewall configuration audit
# - Container security assessment
# - Compliance validation
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script metadata
AUDIT_VERSION="1.0.0"
AUDIT_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
AUDIT_ID=$(uuidgen 2>/dev/null || echo "audit-$(date +%s)")

# Report file
REPORT_DIR="/var/log/veris-memory-security"
REPORT_FILE="${REPORT_DIR}/security-audit-$(date +%Y%m%d-%H%M%S).json"
mkdir -p "${REPORT_DIR}"

# Scoring
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Security Audit and Validation Script             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Audit ID: ${AUDIT_ID}"
echo "Timestamp: ${AUDIT_DATE}"
echo ""

# Helper functions
check_pass() {
    local message=$1
    echo -e "${GREEN}✓${NC} ${message}"
    ((PASSED_CHECKS++))
    ((TOTAL_CHECKS++))
}

check_fail() {
    local message=$1
    echo -e "${RED}✗${NC} ${message}"
    ((FAILED_CHECKS++))
    ((TOTAL_CHECKS++))
}

check_warn() {
    local message=$1
    echo -e "${YELLOW}⚠${NC} ${message}"
    ((WARNING_CHECKS++))
    ((TOTAL_CHECKS++))
}

# Audit Section 1: Port Exposure Analysis
audit_port_exposure() {
    echo -e "${BLUE}[1/8] Port Exposure Analysis${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Database ports that should NOT be exposed
    local db_ports=(6333 6334 6379 7474 7687)

    echo "Checking if database ports are bound to localhost only..."
    for port in "${db_ports[@]}"; do
        if netstat -tlnp 2>/dev/null | grep ":${port}" | grep -q "0.0.0.0"; then
            check_fail "Port ${port} is bound to 0.0.0.0 (EXPOSED TO INTERNET)"
        elif netstat -tlnp 2>/dev/null | grep ":${port}" | grep -q "127.0.0.1"; then
            check_pass "Port ${port} is bound to 127.0.0.1 (localhost only)"
        else
            check_warn "Port ${port} is not listening"
        fi
    done

    echo ""
}

# Audit Section 2: Authentication Verification
audit_authentication() {
    echo -e "${BLUE}[2/8] Authentication Verification${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Test Redis authentication
    echo "Testing Redis authentication..."
    if echo "PING" | nc -w 2 localhost 6379 2>/dev/null | grep -q "NOAUTH"; then
        check_pass "Redis requires authentication"
    elif echo "PING" | nc -w 2 localhost 6379 2>/dev/null | grep -q "PONG"; then
        check_fail "Redis does NOT require authentication (CRITICAL)"
    else
        check_warn "Unable to test Redis authentication"
    fi

    # Test Neo4j authentication (check if it returns 401 without auth)
    echo "Testing Neo4j HTTP authentication..."
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:7474/ 2>/dev/null | grep -q "401\|403"; then
        check_pass "Neo4j HTTP requires authentication"
    else
        check_warn "Neo4j HTTP authentication status unclear"
    fi

    echo ""
}

# Audit Section 3: Firewall Configuration
audit_firewall() {
    echo -e "${BLUE}[3/8] Firewall Configuration Audit${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check UFW status
    echo "Checking UFW status..."
    if ufw status 2>/dev/null | grep -q "Status: active"; then
        check_pass "UFW firewall is active"
    else
        check_fail "UFW firewall is NOT active"
    fi

    # Check DOCKER-USER chain exists
    echo "Checking DOCKER-USER iptables chain..."
    if iptables -L DOCKER-USER -n &>/dev/null; then
        local rule_count=$(iptables -L DOCKER-USER -n | grep -c "^DROP\|^REJECT" || echo "0")
        if [[ ${rule_count} -gt 0 ]]; then
            check_pass "DOCKER-USER chain has ${rule_count} DROP/REJECT rules"
        else
            check_warn "DOCKER-USER chain exists but has no DROP/REJECT rules"
        fi
    else
        check_fail "DOCKER-USER chain does not exist (Docker bypasses firewall)"
    fi

    # Check fail2ban status
    echo "Checking fail2ban status..."
    if systemctl is-active --quiet fail2ban 2>/dev/null; then
        check_pass "fail2ban is active"
    else
        check_warn "fail2ban is not running"
    fi

    echo ""
}

# Audit Section 4: Container Security
audit_containers() {
    echo -e "${BLUE}[4/8] Container Security Assessment${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check if containers are running as non-root
    echo "Checking container user privileges..."
    local root_containers=$(docker ps --format "{{.Names}}" | while read container; do
        user=$(docker inspect --format='{{.Config.User}}' "$container" 2>/dev/null || echo "")
        if [[ -z "$user" || "$user" == "0" || "$user" == "root" ]]; then
            echo "$container"
        fi
    done)

    if [[ -z "$root_containers" ]]; then
        check_pass "No containers running as root"
    else
        check_warn "Some containers running as root: $(echo $root_containers | tr '\n' ' ')"
    fi

    # Check for containers with privileged mode
    echo "Checking for privileged containers..."
    local priv_containers=$(docker ps --format "{{.Names}}" | while read container; do
        if docker inspect --format='{{.HostConfig.Privileged}}' "$container" 2>/dev/null | grep -q "true"; then
            echo "$container"
        fi
    done)

    if [[ -z "$priv_containers" ]]; then
        check_pass "No privileged containers found"
    else
        check_warn "Privileged containers found: $(echo $priv_containers | tr '\n' ' ')"
    fi

    # Check container health status
    echo "Checking container health..."
    local unhealthy=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" | wc -l)
    if [[ ${unhealthy} -eq 0 ]]; then
        check_pass "All containers are healthy"
    else
        check_fail "${unhealthy} unhealthy containers found"
    fi

    echo ""
}

# Audit Section 5: SSH Configuration
audit_ssh() {
    echo -e "${BLUE}[5/8] SSH Security Audit${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check PermitRootLogin
    if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config; then
        check_pass "Root login via SSH is disabled"
    elif grep -q "^PermitRootLogin prohibit-password" /etc/ssh/sshd_config; then
        check_pass "Root login via SSH requires key (password disabled)"
    else
        check_warn "Root login via SSH may be enabled"
    fi

    # Check PasswordAuthentication
    if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config; then
        check_pass "Password authentication is disabled"
    else
        check_warn "Password authentication may be enabled"
    fi

    # Check SSH port
    local ssh_port=$(grep "^Port" /etc/ssh/sshd_config | awk '{print $2}' || echo "22")
    if [[ "$ssh_port" != "22" ]]; then
        check_pass "SSH running on non-standard port (${ssh_port})"
    else
        check_warn "SSH running on standard port 22"
    fi

    echo ""
}

# Audit Section 6: System Updates and Patches
audit_updates() {
    echo -e "${BLUE}[6/8] System Updates and Patch Level${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check for available updates (Ubuntu/Debian)
    if command -v apt-get &>/dev/null; then
        apt-get update -qq 2>/dev/null || true
        local updates=$(apt list --upgradable 2>/dev/null | grep -c "upgradable" || echo "0")
        if [[ ${updates} -eq 0 ]]; then
            check_pass "System is up to date (no pending updates)"
        else
            check_warn "${updates} package updates available"
        fi
    else
        check_warn "Unable to check system updates (not a Debian-based system)"
    fi

    # Check kernel version
    local kernel_version=$(uname -r)
    echo "Kernel version: ${kernel_version}"

    echo ""
}

# Audit Section 7: File Permissions and Secrets
audit_file_permissions() {
    echo -e "${BLUE}[7/8] File Permissions and Secrets Audit${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check .env file permissions
    if [[ -f "/opt/veris-memory/.env" ]]; then
        local env_perms=$(stat -c "%a" /opt/veris-memory/.env)
        if [[ "$env_perms" == "600" || "$env_perms" == "400" ]]; then
            check_pass ".env file has secure permissions (${env_perms})"
        else
            check_warn ".env file permissions too open (${env_perms}), should be 600 or 400"
        fi
    else
        check_warn ".env file not found at /opt/veris-memory/.env"
    fi

    # Check for exposed secrets in docker-compose files
    echo "Checking for exposed secrets in docker-compose files..."
    if find /opt/veris-memory -name "docker-compose*.yml" -exec grep -l "password\|secret\|key" {} \; 2>/dev/null | grep -q .; then
        check_warn "Potential secrets found in docker-compose files (verify they use environment variables)"
    else
        check_pass "No hardcoded secrets detected in docker-compose files"
    fi

    echo ""
}

# Audit Section 8: Network Security
audit_network() {
    echo -e "${BLUE}[8/8] Network Security Audit${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check for listening services
    echo "Scanning for publicly listening services..."
    local public_services=$(netstat -tlnp 2>/dev/null | grep "0.0.0.0" | wc -l)
    if [[ ${public_services} -le 3 ]]; then
        # Typically SSH, HTTP, HTTPS are acceptable
        check_pass "Limited public services (${public_services} services listening on 0.0.0.0)"
    else
        check_warn "${public_services} services listening on 0.0.0.0 (review if all are necessary)"
    fi

    # Check Docker networks
    echo "Auditing Docker networks..."
    local docker_networks=$(docker network ls --format "{{.Name}}" | wc -l)
    echo "Docker networks: ${docker_networks}"

    echo ""
}

# Generate security grade
calculate_security_grade() {
    local pass_rate=$(awk "BEGIN {print ($PASSED_CHECKS / $TOTAL_CHECKS) * 100}")
    local grade="F"

    if (( $(echo "$pass_rate >= 95" | bc -l) )); then
        grade="A"
    elif (( $(echo "$pass_rate >= 85" | bc -l) )); then
        grade="B"
    elif (( $(echo "$pass_rate >= 75" | bc -l) )); then
        grade="C"
    elif (( $(echo "$pass_rate >= 65" | bc -l) )); then
        grade="D"
    fi

    echo "$grade"
}

# Generate JSON report
generate_report() {
    local grade=$(calculate_security_grade)
    local pass_rate=$(awk "BEGIN {print ($PASSED_CHECKS / $TOTAL_CHECKS) * 100}")

    cat > "${REPORT_FILE}" << EOF
{
  "security_audit": {
    "audit_id": "${AUDIT_ID}",
    "timestamp": "${AUDIT_DATE}",
    "version": "${AUDIT_VERSION}",
    "server": "$(hostname)",
    "ip_address": "$(hostname -I | awk '{print $1}')",
    "summary": {
      "security_grade": "${grade}",
      "pass_rate": ${pass_rate},
      "total_checks": ${TOTAL_CHECKS},
      "passed": ${PASSED_CHECKS},
      "failed": ${FAILED_CHECKS},
      "warnings": ${WARNING_CHECKS}
    },
    "status": $([ ${FAILED_CHECKS} -eq 0 ] && echo '"PASS"' || echo '"FAIL"'),
    "recommendations": [
      $([ ${FAILED_CHECKS} -gt 0 ] && echo '"Address all failed checks immediately",' || echo '')
      $([ ${WARNING_CHECKS} -gt 0 ] && echo '"Review and address warnings",' || echo '')
      "Schedule regular security audits",
      "Keep systems updated with latest patches",
      "Monitor security logs daily"
    ],
    "next_audit_recommended": "$(date -d '+1 week' -u +"%Y-%m-%dT%H:%M:%SZ")"
  }
}
EOF

    echo "Report saved to: ${REPORT_FILE}"
}

# Main execution
main() {
    audit_port_exposure
    audit_authentication
    audit_firewall
    audit_containers
    audit_ssh
    audit_updates
    audit_file_permissions
    audit_network

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}AUDIT SUMMARY${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Total Checks: ${TOTAL_CHECKS}"
    echo -e "${GREEN}Passed:${NC} ${PASSED_CHECKS}"
    echo -e "${RED}Failed:${NC} ${FAILED_CHECKS}"
    echo -e "${YELLOW}Warnings:${NC} ${WARNING_CHECKS}"

    local grade=$(calculate_security_grade)
    echo ""
    echo -e "Security Grade: ${BLUE}${grade}${NC}"

    generate_report

    echo ""
    if [[ ${FAILED_CHECKS} -eq 0 ]]; then
        echo -e "${GREEN}✓ Security audit PASSED${NC}"
        echo "No critical issues found"
        exit 0
    else
        echo -e "${RED}✗ Security audit FAILED${NC}"
        echo "Address failed checks before proceeding"
        exit 1
    fi
}

# Execute
main "$@"
