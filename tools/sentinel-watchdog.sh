#!/bin/bash
# Sentinel Watchdog - External monitor for the security monitor
# This script can be run as a cron job to ensure Sentinel is always running

# Configuration
SENTINEL_URL="http://localhost:9090/health"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"
MAX_FAILURES=3
FAILURE_FILE="/tmp/sentinel_failures"

# Function to send Telegram alert
send_alert() {
    local message="$1"
    if [[ -n "$TELEGRAM_BOT_TOKEN" && -n "$TELEGRAM_CHAT_ID" ]]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_CHAT_ID" \
            -d "text=🚨 SECURITY ALERT: $message" \
            -d "parse_mode=HTML" > /dev/null
    fi
    echo "$(date): $message" >> /var/log/sentinel-watchdog.log
}

# Check Sentinel health
check_sentinel() {
    if curl -f -s --max-time 5 "$SENTINEL_URL" > /dev/null 2>&1; then
        # Sentinel is healthy - reset failure counter
        rm -f "$FAILURE_FILE"
        return 0
    else
        # Sentinel is down - increment failure counter
        local failures=1
        if [[ -f "$FAILURE_FILE" ]]; then
            failures=$(cat "$FAILURE_FILE")
            failures=$((failures + 1))
        fi
        echo "$failures" > "$FAILURE_FILE"
        
        if [[ $failures -ge $MAX_FAILURES ]]; then
            send_alert "Sentinel security monitor is DOWN! System is BLIND to attacks. Failures: $failures"
            # Try to restart Sentinel container
            docker restart veris-memory-sentinel-1 2>/dev/null
        fi
        return 1
    fi
}

# Main execution
main() {
    if check_sentinel; then
        echo "$(date): Sentinel is healthy"
    else
        echo "$(date): Sentinel health check failed"
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi