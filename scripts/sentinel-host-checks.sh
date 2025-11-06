#!/bin/bash
#
# Sentinel Host Checks - Firewall Monitoring
#
# This script runs on the HOST (not in Docker) to check security configurations
# that can only be validated from the host level.
#
# Installation:
#   1. Copy to: /opt/veris-memory/scripts/sentinel-host-checks.sh
#   2. Make executable: chmod +x /opt/veris-memory/scripts/sentinel-host-checks.sh
#   3. Add to crontab: */5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh
#

set -euo pipefail

# Configuration
SENTINEL_API_URL="${SENTINEL_API_URL:-http://localhost:9090}"
CHECK_ID="S11-firewall-status"
LOG_FILE="${LOG_FILE:-/var/log/sentinel-host-checks.log}"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages
log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

# Function to check UFW status
check_firewall_status() {
    local status="unknown"
    local is_active=false
    local rule_count=0
    local details=""
    local error_msg=""

    # Try to get UFW status
    if command -v ufw >/dev/null 2>&1; then
        if ufw_output=$(sudo ufw status verbose 2>&1); then
            # Check if firewall is active
            if echo "$ufw_output" | grep -q "Status: active"; then
                is_active=true
                status="pass"

                # Count rules
                rule_count=$(echo "$ufw_output" | grep -c "ALLOW\|DENY" || echo "0")

                details="UFW active with $rule_count rules configured"
            else
                is_active=false
                status="fail"
                details="UFW is installed but DISABLED - critical security risk"
                error_msg="Firewall is disabled. Run: sudo ufw --force enable"
            fi
        else
            status="fail"
            error_msg="Failed to check UFW status: $ufw_output"
            details="Cannot check UFW status - permission denied or UFW error"
        fi
    else
        # UFW not installed
        status="fail"
        error_msg="UFW not installed on this system"
        details="UFW package not found. Install with: sudo apt-get install ufw"
    fi

    # Check for required ports (basic security validation)
    local missing_rules=""
    if [ "$is_active" = true ]; then
        # Check critical ports
        for port in 22 8000 8001 8080 9090; do
            if ! echo "$ufw_output" | grep -q "$port"; then
                missing_rules="${missing_rules}${port},"
            fi
        done

        if [ -n "$missing_rules" ]; then
            status="warn"
            details="$details (missing rules for ports: ${missing_rules%,})"
        fi
    fi

    # Build JSON result
    local timestamp=$(date -Iseconds)
    local latency_ms=50  # Approximate

    local json_payload=$(cat <<EOF
{
  "check_id": "$CHECK_ID",
  "timestamp": "$timestamp",
  "status": "$status",
  "latency_ms": $latency_ms,
  "message": "$details",
  "details": {
    "ufw_active": $is_active,
    "rule_count": $rule_count,
    "missing_rules": "$missing_rules",
    "error": "$error_msg",
    "check_method": "host-based",
    "hostname": "$(hostname)"
  }
}
EOF
)

    echo "$json_payload"
}

# Function to send result to Sentinel API
send_to_sentinel() {
    local payload="$1"

    # Send to Sentinel API
    if response=$(curl -s -w "\n%{http_code}" -X POST \
        "$SENTINEL_API_URL/host-checks/firewall" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        --max-time 5 2>&1); then

        http_code=$(echo "$response" | tail -n1)
        response_body=$(echo "$response" | sed '$d')

        if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
            log "✅ Firewall check sent to Sentinel successfully (HTTP $http_code)"
            return 0
        else
            log "⚠️  Sentinel API returned HTTP $http_code: $response_body"
            return 1
        fi
    else
        log "❌ Failed to connect to Sentinel API at $SENTINEL_API_URL"
        return 1
    fi
}

# Main execution
main() {
    log "Starting firewall status check..."

    # Check firewall status
    check_result=$(check_firewall_status)

    # Log the result
    status=$(echo "$check_result" | jq -r '.status' 2>/dev/null || echo "unknown")
    message=$(echo "$check_result" | jq -r '.message' 2>/dev/null || echo "unknown")

    log "Firewall check result: [$status] $message"

    # Send to Sentinel
    if send_to_sentinel "$check_result"; then
        log "Host check cycle completed successfully"
    else
        log "Warning: Could not send result to Sentinel (API may be down)"
    fi
}

# Run main function
main "$@"
