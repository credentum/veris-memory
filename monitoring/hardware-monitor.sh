#!/bin/bash
set -euo pipefail

# Hardware monitoring script for Hetzner dedicated server
# Monitors RAID1 health, CPU temperature, memory usage, and disk I/O

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/raid1/docker-data/logs/hardware-monitor.log"
ALERT_FILE="/raid1/docker-data/logs/hardware-alerts.log"
PID_FILE="/tmp/hardware-monitor.pid"

# Thresholds
CPU_TEMP_THRESHOLD=70    # Celsius
MEMORY_THRESHOLD=90      # Percentage
DISK_USAGE_THRESHOLD=85  # Percentage
RAID_CHECK_INTERVAL=300  # 5 minutes
MONITOR_INTERVAL=30      # 30 seconds

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[$timestamp]${NC} $message" | tee -a "$LOG_FILE"
}

alert() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ALERT $timestamp]${NC} $message" | tee -a "$LOG_FILE" "$ALERT_FILE"
}

warning() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING $timestamp]${NC} $message" | tee -a "$LOG_FILE"
}

success() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[OK $timestamp]${NC} $message" | tee -a "$LOG_FILE"
}

# Create PID file
create_pid_file() {
    echo $$ > "$PID_FILE"
}

# Remove PID file on exit
cleanup() {
    rm -f "$PID_FILE"
    log "Hardware monitor stopped"
    exit 0
}

trap cleanup EXIT INT TERM

# Check if already running
check_running() {
    if [[ -f "$PID_FILE" ]]; then
        local old_pid=$(cat "$PID_FILE")
        if ps -p "$old_pid" > /dev/null 2>&1; then
            echo "Hardware monitor already running with PID $old_pid"
            exit 1
        else
            rm -f "$PID_FILE"
        fi
    fi
}

# Initialize log directory
init_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    mkdir -p "$(dirname "$ALERT_FILE")"

    # Rotate logs if they get too large (>100MB)
    for logfile in "$LOG_FILE" "$ALERT_FILE"; do
        if [[ -f "$logfile" ]] && [[ $(stat -f%z "$logfile" 2>/dev/null || stat -c%s "$logfile") -gt 104857600 ]]; then
            mv "$logfile" "${logfile}.old"
            touch "$logfile"
        fi
    done
}

# Check RAID1 status
check_raid_status() {
    if [[ ! -f /proc/mdstat ]]; then
        warning "No software RAID detected (/proc/mdstat not found)"
        return 0
    fi

    local raid_status=$(cat /proc/mdstat)
    local raid_devices=$(echo "$raid_status" | grep "^md" | wc -l)

    if [[ $raid_devices -eq 0 ]]; then
        warning "No active RAID arrays found"
        return 0
    fi

    # Check each RAID array
    while IFS= read -r line; do
        if [[ $line =~ ^md[0-9]+ ]]; then
            local array_name=$(echo "$line" | awk '{print $1}')
            local array_status=$(echo "$line" | grep -o '\[.*\]' | tail -1)

            if [[ $array_status =~ U+$ ]]; then
                success "RAID array $array_name is healthy: $array_status"
            else
                alert "RAID array $array_name has failed disks: $array_status"
            fi
        fi
    done <<< "$raid_status"

    # Check for rebuilding arrays
    if echo "$raid_status" | grep -q "recovery"; then
        warning "RAID array is rebuilding - performance may be impacted"
    fi

    if echo "$raid_status" | grep -q "resync"; then
        warning "RAID array is resyncing - performance may be impacted"
    fi
}

# Check NVMe health using smartctl
check_nvme_health() {
    if ! command -v smartctl &> /dev/null; then
        warning "smartctl not available - install smartmontools for NVMe monitoring"
        return 0
    fi

    # Find NVMe devices
    local nvme_devices=$(ls /dev/nvme?n? 2>/dev/null || true)

    if [[ -z "$nvme_devices" ]]; then
        warning "No NVMe devices found"
        return 0
    fi

    for device in $nvme_devices; do
        local health_status=$(/usr/bin/sudo /usr/sbin/smartctl -H "$device" 2>/dev/null | grep "SMART overall-health" | awk '{print $NF}' || echo "UNKNOWN")
        local temp=$(/usr/bin/sudo /usr/sbin/smartctl -A "$device" 2>/dev/null | grep "Temperature:" | awk '{print $2}' | head -1 || echo "0")
        local wear_level=$(/usr/bin/sudo /usr/sbin/smartctl -A "$device" 2>/dev/null | grep "Percentage Used:" | awk '{print $3}' | tr -d '%' || echo "0")

        if [[ "$health_status" == "PASSED" ]]; then
            success "NVMe $device health: $health_status (${temp}°C, ${wear_level}% wear)"
        else
            alert "NVMe $device health: $health_status (${temp}°C, ${wear_level}% wear)"
        fi

        # Check temperature threshold
        if [[ "$temp" -gt 70 ]]; then
            alert "NVMe $device temperature critical: ${temp}°C"
        elif [[ "$temp" -gt 60 ]]; then
            warning "NVMe $device temperature high: ${temp}°C"
        fi

        # Check wear level
        if [[ "$wear_level" -gt 80 ]]; then
            alert "NVMe $device wear level critical: ${wear_level}%"
        elif [[ "$wear_level" -gt 60 ]]; then
            warning "NVMe $device wear level high: ${wear_level}%"
        fi
    done
}

# Check CPU temperature
check_cpu_temperature() {
    if ! command -v sensors &> /dev/null; then
        warning "lm-sensors not available - install lm-sensors for temperature monitoring"
        return 0
    fi

    # Initialize sensors if not done
    if [[ ! -f /etc/sensors3.conf ]] || [[ ! -f /var/lib/sensors3/cache ]]; then
        /usr/bin/sudo /usr/bin/sensors-detect --auto > /dev/null 2>&1 || true
    fi

    local cpu_temps=$(sensors 2>/dev/null | grep -E "Core [0-9]+|Tdie|Tctl" | grep -oE '\+[0-9]+\.[0-9]+°C' | sed 's/+//g' | sed 's/°C//g' || echo "")

    if [[ -z "$cpu_temps" ]]; then
        warning "Could not read CPU temperatures"
        return 0
    fi

    local max_temp=0
    while IFS= read -r temp; do
        if [[ -n "$temp" ]] && (( $(echo "$temp > $max_temp" | bc -l 2>/dev/null || echo "0") )); then
            max_temp=$temp
        fi
    done <<< "$cpu_temps"

    if (( $(echo "$max_temp > $CPU_TEMP_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        alert "CPU temperature critical: ${max_temp}°C (threshold: ${CPU_TEMP_THRESHOLD}°C)"
    elif (( $(echo "$max_temp > $(echo "$CPU_TEMP_THRESHOLD - 10" | bc -l)" | bc -l 2>/dev/null || echo "0") )); then
        warning "CPU temperature high: ${max_temp}°C"
    else
        success "CPU temperature normal: ${max_temp}°C"
    fi
}

# Check memory usage
check_memory_usage() {
    local mem_info=$(cat /proc/meminfo)
    local total_mem=$(echo "$mem_info" | grep "MemTotal:" | awk '{print $2}')
    local avail_mem=$(echo "$mem_info" | grep "MemAvailable:" | awk '{print $2}')
    local used_mem=$((total_mem - avail_mem))
    local usage_percent=$((used_mem * 100 / total_mem))

    local total_gb=$((total_mem / 1024 / 1024))
    local used_gb=$((used_mem / 1024 / 1024))
    local avail_gb=$((avail_mem / 1024 / 1024))

    if [[ $usage_percent -gt $MEMORY_THRESHOLD ]]; then
        alert "Memory usage critical: ${usage_percent}% (${used_gb}GB/${total_gb}GB used, ${avail_gb}GB available)"
    elif [[ $usage_percent -gt $((MEMORY_THRESHOLD - 10)) ]]; then
        warning "Memory usage high: ${usage_percent}% (${used_gb}GB/${total_gb}GB used, ${avail_gb}GB available)"
    else
        success "Memory usage normal: ${usage_percent}% (${used_gb}GB/${total_gb}GB used, ${avail_gb}GB available)"
    fi
}

# Check disk usage
check_disk_usage() {
    local raid1_usage=$(df /raid1 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")
    local root_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")

    # Check RAID1 usage
    if [[ $raid1_usage -gt $DISK_USAGE_THRESHOLD ]]; then
        alert "RAID1 disk usage critical: ${raid1_usage}%"
    elif [[ $raid1_usage -gt $((DISK_USAGE_THRESHOLD - 10)) ]]; then
        warning "RAID1 disk usage high: ${raid1_usage}%"
    else
        success "RAID1 disk usage normal: ${raid1_usage}%"
    fi

    # Check root usage
    if [[ $root_usage -gt $DISK_USAGE_THRESHOLD ]]; then
        alert "Root disk usage critical: ${root_usage}%"
    elif [[ $root_usage -gt $((DISK_USAGE_THRESHOLD - 10)) ]]; then
        warning "Root disk usage high: ${root_usage}%"
    fi
}

# Check Docker containers health
check_docker_health() {
    if ! command -v docker &> /dev/null; then
        warning "Docker not available for container health checks"
        return 0
    fi

    local compose_file="/app/docker-compose.hetzner.yml"
    if [[ ! -f "$compose_file" ]]; then
        compose_file="$(dirname "$SCRIPT_DIR")/docker-compose.hetzner.yml"
    fi

    if [[ ! -f "$compose_file" ]]; then
        warning "Docker compose file not found - skipping container health checks"
        return 0
    fi

    local services=("context-store" "qdrant" "neo4j" "redis")
    local unhealthy_services=()

    for service in "${services[@]}"; do
        local status=$(docker-compose -f "$compose_file" ps "$service" 2>/dev/null | tail -n +3 | awk '{print $4}' || echo "unknown")

        if [[ "$status" =~ (healthy|running) ]]; then
            success "Docker service $service is healthy"
        else
            unhealthy_services+=("$service")
            alert "Docker service $service is unhealthy: $status"
        fi
    done

    if [[ ${#unhealthy_services[@]} -eq 0 ]]; then
        success "All Docker services are healthy"
    else
        alert "Unhealthy Docker services: ${unhealthy_services[*]}"
    fi
}

# Check network connectivity (Tailscale)
check_tailscale_connectivity() {
    if ! command -v tailscale &> /dev/null; then
        warning "Tailscale not available for connectivity checks"
        return 0
    fi

    if /usr/bin/sudo /usr/bin/tailscale status &> /dev/null; then
        local status=$(/usr/bin/sudo /usr/bin/tailscale status --json 2>/dev/null | jq -r '.BackendState' 2>/dev/null || echo "unknown")
        if [[ "$status" == "Running" ]]; then
            success "Tailscale connectivity healthy"
        else
            warning "Tailscale status: $status"
        fi
    else
        alert "Tailscale connectivity failed"
    fi
}

# Main monitoring loop
monitor_loop() {
    log "Starting hardware monitoring for Hetzner dedicated server"
    log "Thresholds: CPU ${CPU_TEMP_THRESHOLD}°C, Memory ${MEMORY_THRESHOLD}%, Disk ${DISK_USAGE_THRESHOLD}%"

    local raid_check_counter=0

    while true; do
        # Always check these
        check_cpu_temperature
        check_memory_usage
        check_disk_usage
        check_docker_health
        check_tailscale_connectivity

        # Check RAID less frequently
        if [[ $raid_check_counter -ge $((RAID_CHECK_INTERVAL / MONITOR_INTERVAL)) ]]; then
            check_raid_status
            check_nvme_health
            raid_check_counter=0
        else
            raid_check_counter=$((raid_check_counter + 1))
        fi

        # Sleep until next check
        sleep $MONITOR_INTERVAL
    done
}

# Health check mode (for Docker healthcheck)
health_check() {
    local failed_checks=0

    # Quick checks for health
    local mem_usage=$(free | awk '/^Mem:/{printf("%.0f", $3/$2*100)}')
    if [[ $mem_usage -gt $MEMORY_THRESHOLD ]]; then
        echo "UNHEALTHY: Memory usage ${mem_usage}% > ${MEMORY_THRESHOLD}%"
        failed_checks=$((failed_checks + 1))
    fi

    local disk_usage=$(df /raid1 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")
    if [[ $disk_usage -gt $DISK_USAGE_THRESHOLD ]]; then
        echo "UNHEALTHY: RAID1 usage ${disk_usage}% > ${DISK_USAGE_THRESHOLD}%"
        failed_checks=$((failed_checks + 1))
    fi

    if [[ $failed_checks -eq 0 ]]; then
        echo "HEALTHY"
        exit 0
    else
        exit 1
    fi
}

# Usage information
usage() {
    echo "Usage: $0 [--health-check] [--daemon]"
    echo "  --health-check  Run quick health check and exit"
    echo "  --daemon        Run as daemon (default)"
    echo "  --help          Show this help"
}

# Main function
main() {
    case "${1:---daemon}" in
        --health-check)
            health_check
            ;;
        --daemon)
            check_running
            create_pid_file
            init_logging
            monitor_loop
            ;;
        --help|-h)
            usage
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
