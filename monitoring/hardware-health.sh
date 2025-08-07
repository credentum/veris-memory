#!/bin/bash
set -euo pipefail

# Hardware health check script for Docker healthcheck
# Quick checks for critical hardware issues

# Thresholds
CPU_TEMP_THRESHOLD=75    # Celsius - higher threshold for quick checks
MEMORY_THRESHOLD=95      # Percentage - higher threshold for emergencies
DISK_USAGE_THRESHOLD=90  # Percentage - higher threshold for emergencies

# Exit codes
EXIT_HEALTHY=0
EXIT_UNHEALTHY=1

# Quick temperature check
check_temperature() {
    if command -v sensors &> /dev/null; then
        local max_temp=$(sensors 2>/dev/null | grep -E "Core [0-9]+|Tdie|Tctl" | grep -oE '\+[0-9]+\.[0-9]+' | sed 's/+//g' | sort -n | tail -1 || echo "0")

        if [[ -n "$max_temp" ]] && (( $(echo "$max_temp > $CPU_TEMP_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
            echo "UNHEALTHY: CPU temperature ${max_temp}°C > ${CPU_TEMP_THRESHOLD}°C"
            return $EXIT_UNHEALTHY
        fi
    fi
    return $EXIT_HEALTHY
}

# Quick memory check
check_memory() {
    local usage_percent=$(free | awk '/^Mem:/{printf("%.0f", $3/$2*100)}')

    if [[ $usage_percent -gt $MEMORY_THRESHOLD ]]; then
        echo "UNHEALTHY: Memory usage ${usage_percent}% > ${MEMORY_THRESHOLD}%"
        return $EXIT_UNHEALTHY
    fi

    return $EXIT_HEALTHY
}

# Quick disk check
check_disk() {
    # Check RAID1 if available
    if [[ -d /raid1 ]]; then
        local raid1_usage=$(df /raid1 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")
        if [[ $raid1_usage -gt $DISK_USAGE_THRESHOLD ]]; then
            echo "UNHEALTHY: RAID1 usage ${raid1_usage}% > ${DISK_USAGE_THRESHOLD}%"
            return $EXIT_UNHEALTHY
        fi
    fi

    # Check root filesystem
    local root_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")
    if [[ $root_usage -gt $DISK_USAGE_THRESHOLD ]]; then
        echo "UNHEALTHY: Root usage ${root_usage}% > ${DISK_USAGE_THRESHOLD}%"
        return $EXIT_UNHEALTHY
    fi

    return $EXIT_HEALTHY
}

# Quick RAID health check
check_raid() {
    if [[ -f /proc/mdstat ]]; then
        # Check for failed drives (indicated by underscore)
        if grep -q "_" /proc/mdstat 2>/dev/null; then
            echo "UNHEALTHY: RAID has failed drives"
            return $EXIT_UNHEALTHY
        fi
    fi

    return $EXIT_HEALTHY
}

# Main health check
main() {
    local failed_checks=0
    local health_messages=()

    # Run all checks
    if ! check_temperature; then
        failed_checks=$((failed_checks + 1))
    fi

    if ! check_memory; then
        failed_checks=$((failed_checks + 1))
    fi

    if ! check_disk; then
        failed_checks=$((failed_checks + 1))
    fi

    if ! check_raid; then
        failed_checks=$((failed_checks + 1))
    fi

    if [[ $failed_checks -eq 0 ]]; then
        echo "HEALTHY: All hardware checks passed"
        exit $EXIT_HEALTHY
    else
        echo "UNHEALTHY: $failed_checks hardware issues detected"
        exit $EXIT_UNHEALTHY
    fi
}

# Run health check
main "$@"
