#!/bin/bash
set -euo pipefail

# RAID1 backup script for Context Store data
# Leverages RAID1 redundancy for high-performance backups

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="/raid1/docker-data"
BACKUP_DIR="/raid1/backups"
LOG_FILE="/raid1/docker-data/logs/backup.log"

# Configuration
RETENTION_DAYS=7
BACKUP_PREFIX="context-store"
COMPRESSION_LEVEL=6
PARALLEL_JOBS=4

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

error() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR $timestamp]${NC} $message" | tee -a "$LOG_FILE"
}

success() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS $timestamp]${NC} $message" | tee -a "$LOG_FILE"
}

warning() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING $timestamp]${NC} $message" | tee -a "$LOG_FILE"
}

# Initialize backup environment
init_backup() {
    log "Initializing RAID1 backup system..."

    # Create backup directories
    mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}
    mkdir -p "$(dirname "$LOG_FILE")"

    # Check available space
    local source_size=$(du -sb "$SOURCE_DIR" 2>/dev/null | cut -f1 || echo "0")
    local backup_free=$(df "$BACKUP_DIR" | tail -1 | awk '{print $4*1024}')

    if [[ $source_size -gt $backup_free ]]; then
        error "Insufficient backup space: need $(numfmt --to=iec $source_size), have $(numfmt --to=iec $backup_free)"
        return 1
    fi

    success "Backup environment initialized"
}

# Create incremental backup using rsync
create_incremental_backup() {
    local backup_type="$1"  # daily, weekly, monthly
    local timestamp=$(date +'%Y%m%d-%H%M%S')
    local backup_name="${BACKUP_PREFIX}-${backup_type}-${timestamp}"
    local backup_path="${BACKUP_DIR}/${backup_type}/${backup_name}"
    local latest_link="${BACKUP_DIR}/${backup_type}/latest"

    log "Creating ${backup_type} incremental backup: $backup_name"

    # Create backup directory
    mkdir -p "$backup_path"

    # Find the most recent backup for hardlinking
    local link_dest=""
    if [[ -L "$latest_link" && -d "$latest_link" ]]; then
        link_dest="--link-dest=$latest_link"
        log "Using hardlinks from previous backup: $latest_link"
    fi

    # Backup each service separately for better granularity
    local services=("qdrant" "neo4j" "redis" "context-store" "logs")
    local failed_services=()

    for service in "${services[@]}"; do
        local service_source="$SOURCE_DIR/$service"
        local service_backup="$backup_path/$service"

        if [[ ! -d "$service_source" ]]; then
            warning "Service directory not found: $service_source"
            continue
        fi

        log "Backing up $service..."

        # Use rsync for incremental backup with hardlinks
        if rsync -avH --delete --numeric-ids \
           --exclude="*.tmp" --exclude="*.lock" --exclude="*.pid" \
           $link_dest \
           "$service_source/" "$service_backup/" >> "$LOG_FILE" 2>&1; then
            success "$service backup completed"
        else
            error "$service backup failed"
            failed_services+=("$service")
        fi
    done

    # Update latest link
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        ln -sfn "$backup_path" "$latest_link"
        success "Incremental backup completed: $backup_name"

        # Create backup metadata
        create_backup_metadata "$backup_path" "$backup_type"

        return 0
    else
        error "Backup partially failed. Failed services: ${failed_services[*]}"
        return 1
    fi
}

# Create backup metadata
create_backup_metadata() {
    local backup_path="$1"
    local backup_type="$2"
    local metadata_file="$backup_path/backup-metadata.json"

    log "Creating backup metadata..."

    # Collect system information
    local hostname=$(hostname)
    local timestamp=$(date -Iseconds)
    local backup_size=$(du -sb "$backup_path" | cut -f1)

    # Create JSON metadata
    cat > "$metadata_file" << EOF
{
  "backup_info": {
    "timestamp": "$timestamp",
    "hostname": "$hostname",
    "backup_type": "$backup_type",
    "backup_size_bytes": $backup_size,
    "backup_size_human": "$(numfmt --to=iec $backup_size)",
    "source_directory": "$SOURCE_DIR",
    "retention_days": $RETENTION_DAYS
  },
  "system_info": {
    "kernel_version": "$(uname -r)",
    "os_release": "$(cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"')",
    "raid_status": "$(cat /proc/mdstat 2>/dev/null | grep "^md" | head -5 || echo 'No RAID detected')"
  },
  "services_backed_up": [
$(find "$backup_path" -mindepth 1 -maxdepth 1 -type d -not -name ".*" -exec basename {} \; | sed 's/^/    "/' | sed 's/$/",/' | sed '$ s/,$//')
  ]
}
EOF

    success "Backup metadata created"
}

# Verify backup integrity
verify_backup() {
    local backup_path="$1"

    log "Verifying backup integrity: $backup_path"

    local failed_checks=0

    # Check if all expected services were backed up
    local services=("qdrant" "neo4j" "redis" "context-store" "logs")
    for service in "${services[@]}"; do
        local service_backup="$backup_path/$service"
        if [[ -d "$service_backup" ]]; then
            local file_count=$(find "$service_backup" -type f | wc -l)
            if [[ $file_count -gt 0 ]]; then
                success "$service: $file_count files backed up"
            else
                warning "$service: no files found in backup"
                failed_checks=$((failed_checks + 1))
            fi
        else
            warning "$service: directory not found in backup"
            failed_checks=$((failed_checks + 1))
        fi
    done

    # Verify metadata file
    if [[ -f "$backup_path/backup-metadata.json" ]]; then
        if jq empty "$backup_path/backup-metadata.json" 2>/dev/null; then
            success "Backup metadata is valid JSON"
        else
            warning "Backup metadata is invalid JSON"
            failed_checks=$((failed_checks + 1))
        fi
    else
        warning "Backup metadata file missing"
        failed_checks=$((failed_checks + 1))
    fi

    if [[ $failed_checks -eq 0 ]]; then
        success "Backup verification passed"
        return 0
    else
        error "Backup verification failed ($failed_checks issues)"
        return 1
    fi
}

# Clean up old backups based on retention policy
cleanup_old_backups() {
    local backup_type="$1"
    local retention_days="$2"

    log "Cleaning up old ${backup_type} backups (retention: ${retention_days} days)"

    local backup_dir="${BACKUP_DIR}/${backup_type}"
    local deleted_count=0

    # Find backups older than retention period
    find "$backup_dir" -mindepth 1 -maxdepth 1 -type d -name "${BACKUP_PREFIX}-${backup_type}-*" \
         -mtime +$retention_days -print0 | while IFS= read -r -d '' old_backup; do

        local backup_name=$(basename "$old_backup")
        log "Removing old backup: $backup_name"

        if rm -rf "$old_backup"; then
            deleted_count=$((deleted_count + 1))
            success "Removed old backup: $backup_name"
        else
            error "Failed to remove old backup: $backup_name"
        fi
    done

    if [[ $deleted_count -gt 0 ]]; then
        success "Cleaned up $deleted_count old ${backup_type} backups"
    else
        log "No old ${backup_type} backups to clean up"
    fi
}

# Monitor RAID health before backup
check_raid_health() {
    if [[ ! -f /proc/mdstat ]]; then
        warning "No software RAID detected - skipping RAID health check"
        return 0
    fi

    log "Checking RAID health before backup..."

    local raid_status=$(cat /proc/mdstat)
    local raid_arrays=($(echo "$raid_status" | grep "^md" | awk '{print $1}'))

    if [[ ${#raid_arrays[@]} -eq 0 ]]; then
        warning "No active RAID arrays found"
        return 0
    fi

    # Check each RAID array with mdadm for detailed health information
    for array in "${raid_arrays[@]}"; do
        if command -v mdadm &> /dev/null; then
            local array_detail=$(/usr/bin/sudo /sbin/mdadm --detail "/dev/$array" 2>/dev/null || echo "")
            if [[ -n "$array_detail" ]]; then
                local array_state=$(echo "$array_detail" | grep "State :" | awk '{print $3}')
                local failed_devices=$(echo "$array_detail" | grep "Failed Devices" | awk '{print $4}')

                if [[ "$failed_devices" != "0" ]]; then
                    error "RAID array /dev/$array has $failed_devices failed devices - backup may be unreliable"
                    return 1
                fi

                if [[ "$array_state" != "clean" ]]; then
                    warning "RAID array /dev/$array state: $array_state - backup will continue but may be slower"
                fi

                success "RAID array /dev/$array is healthy: $array_state, $failed_devices failed devices"
            fi
        fi
    done

    # Fallback to /proc/mdstat check if mdadm not available
    if echo "$raid_status" | grep -q "_"; then
        error "RAID has failed drives indicated in /proc/mdstat - backup may be unreliable"
        return 1
    fi

    # Check for rebuilding arrays
    if echo "$raid_status" | grep -qE "(recovery|resync)"; then
        warning "RAID is rebuilding/resyncing - backup will continue but may be slower"
        return 0
    fi

    success "RAID health check passed"
    return 0
}

# Main backup function
perform_backup() {
    local backup_type="${1:-daily}"

    log "Starting $backup_type backup process..."

    # Check RAID health first
    if ! check_raid_health; then
        error "RAID health check failed - aborting backup"
        return 1
    fi

    # Initialize backup environment
    if ! init_backup; then
        error "Failed to initialize backup environment"
        return 1
    fi

    # Create the backup
    if create_incremental_backup "$backup_type"; then
        local latest_backup=$(readlink "${BACKUP_DIR}/${backup_type}/latest")

        # Verify the backup
        if verify_backup "$latest_backup"; then
            success "$backup_type backup completed and verified: $(basename "$latest_backup")"
        else
            warning "$backup_type backup completed but verification failed"
        fi

        # Clean up old backups
        case "$backup_type" in
            daily)
                cleanup_old_backups "daily" "$RETENTION_DAYS"
                ;;
            weekly)
                cleanup_old_backups "weekly" $((RETENTION_DAYS * 4))  # 4 weeks
                ;;
            monthly)
                cleanup_old_backups "monthly" $((RETENTION_DAYS * 12))  # 12 months
                ;;
        esac

        return 0
    else
        error "$backup_type backup failed"
        return 1
    fi
}

# List available backups
list_backups() {
    echo "Available backups in $BACKUP_DIR:"
    echo

    for backup_type in daily weekly monthly; do
        local type_dir="${BACKUP_DIR}/${backup_type}"
        if [[ -d "$type_dir" ]]; then
            echo "${backup_type^} backups:"
            find "$type_dir" -mindepth 1 -maxdepth 1 -type d -name "${BACKUP_PREFIX}-${backup_type}-*" \
                -printf "  %f (size: " -exec du -sh {} \; | awk '{print $1 " " $3 ")"}'
            echo
        fi
    done
}

# Restore from backup
restore_backup() {
    local backup_name="$1"
    local restore_path="${2:-$SOURCE_DIR}"

    # Find the backup
    local backup_path=""
    for backup_type in daily weekly monthly; do
        local candidate="${BACKUP_DIR}/${backup_type}/${backup_name}"
        if [[ -d "$candidate" ]]; then
            backup_path="$candidate"
            break
        fi
    done

    if [[ -z "$backup_path" ]]; then
        error "Backup not found: $backup_name"
        return 1
    fi

    warning "This will restore data to: $restore_path"
    warning "Current data will be backed up to: ${restore_path}.pre-restore-$(date +%s)"

    read -p "Are you sure you want to proceed? (yes/no): " -r
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log "Restore cancelled by user"
        return 1
    fi

    # Backup current data
    local backup_current="${restore_path}.pre-restore-$(date +%s)"
    if [[ -d "$restore_path" ]]; then
        log "Backing up current data to: $backup_current"
        mv "$restore_path" "$backup_current"
    fi

    # Restore from backup
    log "Restoring from backup: $backup_name"
    if rsync -avH --numeric-ids "$backup_path/" "$restore_path/"; then
        success "Restore completed successfully"
        log "Previous data saved at: $backup_current"
        return 0
    else
        error "Restore failed"
        # Try to restore the backup
        if [[ -d "$backup_current" ]]; then
            log "Restoring previous data due to failed restore"
            mv "$backup_current" "$restore_path"
        fi
        return 1
    fi
}

# Usage information
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  backup [daily|weekly|monthly]  Perform backup (default: daily)"
    echo "  list                          List available backups"
    echo "  verify BACKUP_NAME            Verify specific backup"
    echo "  restore BACKUP_NAME [PATH]    Restore from backup"
    echo "  cleanup [daily|weekly|monthly] Clean up old backups"
    echo
    echo "Examples:"
    echo "  $0 backup daily               # Create daily backup"
    echo "  $0 list                       # List all backups"
    echo "  $0 verify context-store-daily-20250807-020000"
    echo "  $0 restore context-store-daily-20250807-020000"
}

# Main function
main() {
    case "${1:-backup}" in
        backup)
            perform_backup "${2:-daily}"
            ;;
        list)
            list_backups
            ;;
        verify)
            if [[ -n "${2:-}" ]]; then
                verify_backup "${BACKUP_DIR}/*/${2}"
            else
                error "Please specify backup name to verify"
                usage
                exit 1
            fi
            ;;
        restore)
            if [[ -n "${2:-}" ]]; then
                restore_backup "$2" "${3:-}"
            else
                error "Please specify backup name to restore"
                usage
                exit 1
            fi
            ;;
        cleanup)
            cleanup_old_backups "${2:-daily}" "$RETENTION_DAYS"
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Run main function
main "$@"
