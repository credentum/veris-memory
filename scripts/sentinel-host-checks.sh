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
#   3. Set HOST_CHECK_SECRET env var or add to /etc/environment
#   4. Add to crontab: */5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh
#
# Note: Removed 'set -e' for production resilience. Errors are handled explicitly.

# Exit codes
EXIT_SUCCESS=0
EXIT_FAILURE=1

# Configuration
SENTINEL_API_URL="${SENTINEL_API_URL:-http://localhost:9090}"
CHECK_ID="S11-firewall-status"
LOG_FILE="${LOG_FILE:-/var/log/sentinel-host-checks.log}"
HOST_CHECK_SECRET="${HOST_CHECK_SECRET:-veris_host_check_default_secret_change_me}"

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
    local response
    local http_code
    local response_body
    local exit_code

    # Check if secret is configured
    if [ "$HOST_CHECK_SECRET" = "veris_host_check_default_secret_change_me" ]; then
        log "⚠️  WARNING: Using default HOST_CHECK_SECRET. Set a unique secret in environment."
    fi

    # Send to Sentinel API with authentication
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "$SENTINEL_API_URL/host-checks/firewall" \
        -H "Content-Type: application/json" \
        -H "X-Host-Secret: $HOST_CHECK_SECRET" \
        -d "$payload" \
        --max-time 5 2>&1)
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        log "❌ Failed to connect to Sentinel API at $SENTINEL_API_URL (curl exit code: $exit_code)"
        return $EXIT_FAILURE
    fi

    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        log "✅ Firewall check sent to Sentinel successfully (HTTP $http_code)"
        return $EXIT_SUCCESS
    elif [ "$http_code" = "401" ] || [ "$http_code" = "403" ]; then
        log "🔒 Authentication failed (HTTP $http_code). Check HOST_CHECK_SECRET matches Sentinel configuration."
        return $EXIT_FAILURE
    else
        log "⚠️  Sentinel API returned HTTP $http_code: $response_body"
        return $EXIT_FAILURE
    fi
}

# Main execution
main() {
    local check_result
    local status
    local message
    local send_result

    log "Starting firewall status check..."

    # Check firewall status
    check_result=$(check_firewall_status)
    if [ $? -ne 0 ] || [ -z "$check_result" ]; then
        log "❌ Failed to perform firewall check"
        return $EXIT_FAILURE
    fi

    # Log the result (handle jq errors gracefully)
    status=$(echo "$check_result" | jq -r '.status' 2>/dev/null)
    if [ $? -ne 0 ]; then
        log "⚠️  Failed to parse check result JSON"
        status="unknown"
    fi

    message=$(echo "$check_result" | jq -r '.message' 2>/dev/null)
    if [ $? -ne 0 ]; then
        message="Failed to parse message"
    fi

    log "Firewall check result: [$status] $message"

    # Send to Sentinel
    send_to_sentinel "$check_result"
    send_result=$?

    if [ $send_result -eq $EXIT_SUCCESS ]; then
        log "Host check cycle completed successfully"
        return $EXIT_SUCCESS
    else
        log "Warning: Could not send result to Sentinel (API may be down or authentication failed)"
        return $EXIT_FAILURE
    fi
}

# Run main function and handle its exit code
main "$@"
exit_code=$?

# Exit with appropriate code (for cron monitoring)
exit $exit_code
