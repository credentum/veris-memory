#!/bin/bash
# Sentinel Host-Based Checks Script
#
# Runs security and system checks on the host machine that cannot be performed
# from inside Docker containers (e.g., firewall status, host security settings).
#
# This script submits results to the Sentinel API for S11 firewall status check.
#
# Usage:
#   ./sentinel-host-checks.sh [--dry-run]
#
# Setup (run as root or with sudo):
#   1. Copy this script to /opt/veris-memory/scripts/
#   2. Make it executable: chmod +x /opt/veris-memory/scripts/sentinel-host-checks.sh
#   3. Add to crontab: crontab -e
#   4. Add line: */5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh
#
# Requirements:
#   - ufw (Uncomplicated Firewall) installed
#   - curl installed
#   - Sentinel API accessible at http://localhost:9090

set -euo pipefail

# Configuration
SENTINEL_API_URL="http://localhost:9090"
DRY_RUN=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run]"
            exit 1
            ;;
    esac
done

# Colors (only if terminal supports it)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

log() {
    echo -e "${1}${2}${NC}"
}

# Check if UFW is installed
if ! command -v ufw &> /dev/null; then
    STATUS="fail"
    MESSAGE="❌ UFW firewall not installed"
    DETAILS='{
        "ufw_installed": false,
        "recommendation": "Install UFW: sudo apt-get install ufw"
    }'
else
    # Get UFW status
    UFW_STATUS=$(sudo ufw status 2>/dev/null || echo "error")

    if [ "$UFW_STATUS" = "error" ]; then
        STATUS="fail"
        MESSAGE="❌ Cannot check UFW status (permission denied or UFW not running)"
        DETAILS='{
            "ufw_installed": true,
            "ufw_accessible": false,
            "error": "Permission denied or UFW not running",
            "recommendation": "Run this script with sudo or check UFW installation"
        }'
    elif echo "$UFW_STATUS" | grep -q "Status: active"; then
        # Firewall is active
        ACTIVE_RULES=$(echo "$UFW_STATUS" | grep -c "ALLOW\|DENY\|REJECT" || echo 0)

        # Check for critical ports
        CRITICAL_PORTS_PROTECTED=0
        CRITICAL_PORTS_EXPOSED=0

        # Check if SSH (22) is configured
        if echo "$UFW_STATUS" | grep -q "22/tcp"; then
            CRITICAL_PORTS_PROTECTED=$((CRITICAL_PORTS_PROTECTED + 1))
        fi

        # Check if HTTP (80) is configured
        if echo "$UFW_STATUS" | grep -q "80/tcp"; then
            CRITICAL_PORTS_PROTECTED=$((CRITICAL_PORTS_PROTECTED + 1))
        fi

        # Check if HTTPS (443) is configured
        if echo "$UFW_STATUS" | grep -q "443/tcp"; then
            CRITICAL_PORTS_PROTECTED=$((CRITICAL_PORTS_PROTECTED + 1))
        fi

        STATUS="pass"
        MESSAGE="✅ Firewall active with ${ACTIVE_RULES} rules (${CRITICAL_PORTS_PROTECTED}/3 critical ports configured)"
        DETAILS=$(cat <<EOF
{
    "ufw_installed": true,
    "ufw_status": "active",
    "active_rules": ${ACTIVE_RULES},
    "critical_ports_protected": ${CRITICAL_PORTS_PROTECTED},
    "ssh_configured": $(echo "$UFW_STATUS" | grep -q "22/tcp" && echo "true" || echo "false"),
    "http_configured": $(echo "$UFW_STATUS" | grep -q "80/tcp" && echo "true" || echo "false"),
    "https_configured": $(echo "$UFW_STATUS" | grep -q "443/tcp" && echo "true" || echo "false")
}
EOF
)
    else
        # Firewall is inactive
        STATUS="fail"
        MESSAGE="❌ Firewall is INACTIVE - system is exposed!"
        DETAILS='{
            "ufw_installed": true,
            "ufw_status": "inactive",
            "security_risk": "high",
            "recommendation": "Enable firewall: sudo ufw enable"
        }'
    fi
fi

# Prepare JSON payload for Sentinel API
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PAYLOAD=$(cat <<EOF
{
    "check_id": "S11-firewall-status",
    "timestamp": "${TIMESTAMP}",
    "status": "${STATUS}",
    "message": "${MESSAGE}",
    "details": ${DETAILS}
}
EOF
)

if [ "$DRY_RUN" = true ]; then
    log "${YELLOW}" "[DRY RUN] Would submit to Sentinel API:"
    echo "$PAYLOAD" | jq '.' 2>/dev/null || echo "$PAYLOAD"
    exit 0
fi

# Submit to Sentinel API
RESPONSE=$(curl -s -X POST \
    "${SENTINEL_API_URL}/api/v1/host-checks/S11-firewall-status" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    2>&1 || echo "error")

if echo "$RESPONSE" | grep -q "success"; then
    log "${GREEN}" "✅ Firewall check submitted to Sentinel API"
else
    log "${RED}" "❌ Failed to submit to Sentinel API: $RESPONSE"
    exit 1
fi

# Output summary to stdout (for cron logging)
if [ "$STATUS" = "pass" ]; then
    log "${GREEN}" "$MESSAGE"
else
    log "${RED}" "$MESSAGE"
fi

exit 0
