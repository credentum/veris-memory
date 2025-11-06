#!/bin/bash
# Backup monitoring script - alerts on disk usage and backup failures
# Add to crontab: 0 6 * * * /opt/scripts/backup-monitor.sh
#
# SECURE CREDENTIAL SETUP:
# 1. For Telegram alerts, set environment variables:
#    export TELEGRAM_BOT_TOKEN="your_bot_token"
#    export TELEGRAM_CHAT_ID="your_chat_id"
#
# 2. For production, add to /etc/environment or use systemd EnvironmentFile:
#    echo "TELEGRAM_BOT_TOKEN=your_token" | sudo tee -a /etc/backup/telegram.conf
#    echo "TELEGRAM_CHAT_ID=your_chat_id" | sudo tee -a /etc/backup/telegram.conf
#    chmod 600 /etc/backup/telegram.conf
#
# 3. For restic password, create /etc/backup/restic.conf:
#    echo "RESTIC_PASSWORD=your_secure_password" | sudo tee /etc/backup/restic.conf
#    chmod 600 /etc/backup/restic.conf

set -euo pipefail

# Load Telegram credentials from secure config if available
if [[ -f "/etc/backup/telegram.conf" ]] && [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    # shellcheck disable=SC1091
    source /etc/backup/telegram.conf
fi

# Configuration
DISK_USAGE_THRESHOLD=90
BACKUP_FAILURE_THRESHOLD=2
BACKUP_LOG="/var/log/backup-cron.log"
ALERT_LOG="/var/log/backup-monitor.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1" | tee -a "$ALERT_LOG"
}

warning() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1" | tee -a "$ALERT_LOG"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" | tee -a "$ALERT_LOG"
}

# Send Telegram alert (if configured)
send_telegram_alert() {
    local message="$1"
    local priority="${2:-normal}"

    # Check if Telegram is configured
    if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] || [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
        log "Telegram not configured, skipping alert"
        return 0
    fi

    local emoji
    case "$priority" in
        critical) emoji="🚨" ;;
        warning) emoji="⚠️" ;;
        info) emoji="ℹ️" ;;
        *) emoji="📊" ;;
    esac

    local full_message="${emoji} **Backup Monitor Alert**\n\n${message}"

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${full_message}" \
        -d "parse_mode=Markdown" \
        > /dev/null 2>&1 || warning "Failed to send Telegram alert"
}

# Check disk usage
check_disk_usage() {
    log "Checking disk usage..."

    local partitions=("/backup" "/" "/var")
    local alerts=()

    for partition in "${partitions[@]}"; do
        if [[ -d "$partition" ]]; then
            local usage=$(df "$partition" | tail -1 | awk '{print int($5)}')
            local available=$(df -h "$partition" | tail -1 | awk '{print $4}')

            if [[ $usage -gt $DISK_USAGE_THRESHOLD ]]; then
                local message="Critical: ${partition} is ${usage}% full (${available} available)"
                error "$message"
                alerts+=("$message")
            elif [[ $usage -gt 80 ]]; then
                warning "${partition} is ${usage}% full (${available} available)"
            else
                log "${partition} is ${usage}% full (${available} available) ✓"
            fi
        fi
    done

    if [[ ${#alerts[@]} -gt 0 ]]; then
        local alert_msg=$(printf "%s\n" "${alerts[@]}")
        send_telegram_alert "Disk space critical:\n${alert_msg}" "critical"
        return 1
    fi

    return 0
}

# Check backup success/failure
check_backup_status() {
    log "Checking backup status..."

    if [[ ! -f "$BACKUP_LOG" ]]; then
        warning "Backup log not found: $BACKUP_LOG"
        return 1
    fi

    # Count recent failures (last 24 hours)
    local yesterday=$(date -d '24 hours ago' '+%Y-%m-%d')
    local failures=$(grep -c "\[ERROR\]\|\[WARN\].*Failed" "$BACKUP_LOG" | tail -1 || echo "0")
    local recent_failures=$(grep -A 1 "$yesterday" "$BACKUP_LOG" | grep -c "\[ERROR\]\|\[WARN\].*Failed" || echo "0")

    log "Total backup warnings/errors in log: $failures"
    log "Recent failures (last 24h): $recent_failures"

    if [[ $recent_failures -ge $BACKUP_FAILURE_THRESHOLD ]]; then
        local message="Backup failures detected: ${recent_failures} errors in last 24 hours"
        error "$message"

        # Get last few error lines
        local error_details=$(grep "\[ERROR\]\|\[WARN\].*Failed" "$BACKUP_LOG" | tail -5)
        send_telegram_alert "${message}\n\nRecent errors:\n${error_details}" "critical"
        return 1
    elif [[ $recent_failures -gt 0 ]]; then
        warning "Some backup warnings detected (${recent_failures}), but below threshold"
    else
        log "No recent backup failures ✓"
    fi

    return 0
}

# Check retention policy compliance
check_retention() {
    log "Checking backup retention compliance..."

    local backup_dirs=("/backup/docker-volumes" "/backup/databases")
    local issues=()

    for backup_dir in "${backup_dirs[@]}"; do
        if [[ -d "$backup_dir" ]]; then
            # Count backups older than 30 days (should have been cleaned up)
            local old_backups=$(find "$backup_dir" -type f -mtime +30 2>/dev/null | wc -l)

            if [[ $old_backups -gt 10 ]]; then
                local message="Retention policy issue: ${old_backups} backups older than 30 days in ${backup_dir}"
                warning "$message"
                issues+=("$message")
            else
                log "Retention policy compliant for ${backup_dir} ✓"
            fi
        fi
    done

    if [[ ${#issues[@]} -gt 0 ]]; then
        local issue_msg=$(printf "%s\n" "${issues[@]}")
        send_telegram_alert "Backup retention issues:\n${issue_msg}" "warning"
        return 1
    fi

    return 0
}

# Generate daily summary
generate_daily_summary() {
    log "Generating daily backup summary..."

    local summary=""
    summary+="**Daily Backup Report - $(date '+%Y-%m-%d')**\n\n"

    # Disk usage summary
    summary+="**Disk Usage:**\n"
    for partition in "/" "/backup" "/var"; do
        if [[ -d "$partition" ]]; then
            local usage=$(df -h "$partition" | tail -1 | awk '{print "  " $6 ": " $5 " used, " $4 " available"}')
            summary+="${usage}\n"
        fi
    done
    summary+="\n"

    # Backup status
    if [[ -f "$BACKUP_LOG" ]]; then
        local yesterday=$(date -d '24 hours ago' '+%Y-%m-%d')
        local successful=$(grep -c "Successfully backed up\|backup completed" "$BACKUP_LOG" 2>/dev/null || echo "0")
        local failed=$(grep -c "\[ERROR\]" "$BACKUP_LOG" 2>/dev/null || echo "0")

        summary+="**Backup Status (24h):**\n"
        summary+="  ✓ Successful: ${successful}\n"
        summary+="  ✗ Failed: ${failed}\n"
        summary+="\n"
    fi

    # Repository size (if using restic)
    if command -v restic &>/dev/null && [[ -d "/backup/restic-repo" ]]; then
        export RESTIC_REPOSITORY='/backup/restic-repo'

        # SECURITY FIX: Load password from environment or config file
        if [[ -z "${RESTIC_PASSWORD:-}" ]]; then
            if [[ -f "/etc/backup/restic.conf" ]]; then
                # shellcheck disable=SC1091
                source /etc/backup/restic.conf
            else
                log "Skipping restic stats - RESTIC_PASSWORD not configured"
                summary+="**Backup Repository Size:** Not available (password not configured)\n\n"
            fi
        fi

        if [[ -n "${RESTIC_PASSWORD:-}" ]]; then
            export RESTIC_PASSWORD
            local repo_size=$(restic stats --mode restore-size --quiet 2>/dev/null | tail -1 || echo "unknown")
            summary+="**Backup Repository Size:** ${repo_size}\n\n"
        fi
    fi

    echo -e "$summary"
    send_telegram_alert "$summary" "info"
}

# Main monitoring function
main() {
    log "========================================"
    log "Starting Backup Monitoring"
    log "========================================"

    local overall_status=0

    # Run checks
    if ! check_disk_usage; then
        overall_status=1
    fi

    if ! check_backup_status; then
        overall_status=1
    fi

    if ! check_retention; then
        overall_status=1
    fi

    # Generate daily summary (only on weekdays at 6 AM)
    local hour=$(date +%H)
    local day=$(date +%u)
    if [[ "$hour" == "06" ]] && [[ $day -le 5 ]]; then
        generate_daily_summary
    fi

    log "========================================"
    if [[ $overall_status -eq 0 ]]; then
        log "Monitoring completed: All checks passed ✓"
    else
        error "Monitoring completed: Issues detected"
    fi
    log "========================================"

    exit $overall_status
}

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$ALERT_LOG")"

# Run main function
main "$@"
