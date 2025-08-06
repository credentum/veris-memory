#!/bin/bash
# Comprehensive health monitoring for Veris Memory services
set -euo pipefail

MONITORING_LOG="/app/logs/health-monitor.log"
ALERT_THRESHOLD_MEMORY=80  # Alert if memory usage > 80%
ALERT_THRESHOLD_DISK=85    # Alert if disk usage > 85%

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITORING_LOG"
}

check_service_health() {
    local service=$1
    local port=$2
    local endpoint=${3:-}

    if nc -z localhost "$port"; then
        if [ -n "$endpoint" ]; then
            if curl -f -s "http://localhost:$port$endpoint" >/dev/null; then
                log_message "✓ $service is healthy (port $port, endpoint $endpoint)"
                return 0
            else
                log_message "⚠️  $service port is open but endpoint $endpoint is not responding"
                return 1
            fi
        else
            log_message "✓ $service is healthy (port $port)"
            return 0
        fi
    else
        log_message "❌ $service is down (port $port not responding)"
        return 1
    fi
}

check_resource_usage() {
    # Memory usage
    local memory_percent=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')
    log_message "Memory usage: ${memory_percent}%"

    if (( $(echo "$memory_percent > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
        log_message "🚨 HIGH MEMORY USAGE: ${memory_percent}% (threshold: ${ALERT_THRESHOLD_MEMORY}%)"
    fi

    # Disk usage
    local disk_percent=$(df /app | tail -1 | awk '{print $5}' | sed 's/%//')
    log_message "Disk usage: ${disk_percent}%"

    if [ "$disk_percent" -gt "$ALERT_THRESHOLD_DISK" ]; then
        log_message "🚨 HIGH DISK USAGE: ${disk_percent}% (threshold: ${ALERT_THRESHOLD_DISK}%)"
    fi
}

check_process_health() {
    local processes=("supervisord" "redis-server" "qdrant" "neo4j" "uvicorn")

    for proc in "${processes[@]}"; do
        if pgrep -f "$proc" >/dev/null; then
            local pid=$(pgrep -f "$proc" | head -1)
            local memory_mb=$(ps -p "$pid" -o rss= | awk '{print int($1/1024)}')
            log_message "✓ $proc running (PID: $pid, Memory: ${memory_mb}MB)"
        else
            log_message "❌ $proc not running"
        fi
    done
}

generate_metrics() {
    log_message "=== System Health Report ==="

    # Service health checks
    check_service_health "MCP Server" 8000 "/health"
    check_service_health "Qdrant" 6333 "/health"
    check_service_health "Neo4j HTTP" 7474
    check_service_health "Neo4j Bolt" 7687
    check_service_health "Redis" 6379

    # Resource usage
    check_resource_usage

    # Process health
    check_process_health

    log_message "=== End Health Report ==="
}

# Main execution
main() {
    # Create logs directory if it doesn't exist
    mkdir -p /app/logs

    # Generate health report
    generate_metrics

    # Optional: Send metrics to external monitoring (placeholder)
    if [ "${EXTERNAL_MONITORING:-}" = "true" ]; then
        log_message "External monitoring integration would be called here"
        # Example: curl -X POST "$MONITORING_WEBHOOK_URL" -d "@$MONITORING_LOG"
    fi
}

main "$@"
