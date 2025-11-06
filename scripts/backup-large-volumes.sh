#!/bin/bash
# Production: Automated incremental backup for large volumes
# FIXED: Removed obsolete context-store_neo4j_data volume (no longer exists)

set -euo pipefail

# Configuration
RESTIC_REPOSITORY='/backup/restic-repo'

# SECURITY FIX: Load password from environment or secure file instead of hardcoding
if [[ -z "${RESTIC_PASSWORD:-}" ]]; then
    # Try to load from secure config file
    if [[ -f "/etc/backup/restic.conf" ]]; then
        # shellcheck disable=SC1091
        source /etc/backup/restic.conf
    else
        echo "ERROR: RESTIC_PASSWORD not set. Set environment variable or create /etc/backup/restic.conf"
        exit 1
    fi
fi

export RESTIC_REPOSITORY RESTIC_PASSWORD

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2" | tee -a /var/log/backup-large-volumes.log
}

# Dependency checks
check_dependencies() {
    local missing_deps=()

    if ! command -v docker &>/dev/null; then
        missing_deps+=("docker")
    fi

    if ! command -v restic &>/dev/null; then
        missing_deps+=("restic")
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log "ERROR" "Missing required dependencies: ${missing_deps[*]}"
        return 1
    fi

    # Verify Docker is running
    if ! docker info &>/dev/null; then
        log "ERROR" "Docker is not running"
        return 1
    fi

    # Verify restic repository exists
    if [[ ! -d "$RESTIC_REPOSITORY" ]]; then
        log "WARN" "Restic repository does not exist at: $RESTIC_REPOSITORY"
        log "INFO" "Initializing new restic repository..."
        if ! restic init 2>&1 | tee -a /var/log/backup-large-volumes.log; then
            log "ERROR" "Failed to initialize restic repository"
            return 1
        fi
    fi

    log "INFO" "Dependency checks passed"
    return 0
}

backup_large_volumes() {
    # Run dependency checks first
    if ! check_dependencies; then
        log "ERROR" "Dependency check failed, aborting backup"
        return 1
    fi
    log "INFO" "Starting automated large volume backups"

    # Create temp directory for volume mounts
    local temp_dir="/tmp/restic-mounts"
    mkdir -p "$temp_dir"

    # Large volumes to backup incrementally
    # FIXED: Removed context-store_neo4j_data (volume no longer exists)
    local volumes=(
        "claude-workspace"
        "veris-memory-dev_neo4j_data"
    )

    local backed_up=0

    for volume in "${volumes[@]}"; do
        if docker volume ls --format '{{.Name}}' | grep -q "^${volume}$"; then
            log "INFO" "Backing up large volume: $volume"

            # Create mount point for this volume
            local mount_point="${temp_dir}/${volume}"
            mkdir -p "$mount_point"

            # Mount volume and backup using local restic
            # FIX: Capture errors instead of suppressing with 2>/dev/null
            local docker_error
            docker_error=$(docker run --rm \
                -v "${volume}:${mount_point}:ro" \
                -v "${temp_dir}:${temp_dir}" \
                alpine sh -c "ls ${mount_point} > /dev/null" 2>&1)

            if [[ $? -eq 0 ]]; then
                # Backup using local restic with proper error logging
                local restic_error
                restic_error=$(restic backup "${mount_point}" \
                    --tag "volume:${volume}" \
                    --tag "type:large" \
                    --tag "date:$(date +%Y-%m-%d)" \
                    --exclude="*.log" \
                    --exclude="*.tmp" \
                    --exclude=".cache" \
                    2>&1)

                if [[ $? -eq 0 ]]; then
                    log "INFO" "✓ Successfully backed up $volume"
                    ((backed_up++))
                else
                    log "WARN" "✗ Failed to backup $volume: $restic_error"
                fi
            else
                log "WARN" "Cannot access volume: $volume - $docker_error"
            fi
        else
            log "WARN" "Volume not found: $volume"
        fi
    done

    # Cleanup temp directory
    rm -rf "$temp_dir"

    log "INFO" "Large volume backup completed: $backed_up volumes"

    # Show repository size
    local repo_size=$(restic stats --mode restore-size --quiet | tail -1 || echo "unknown")
    log "INFO" "Repository size: $repo_size"

    # Auto-cleanup old snapshots (keep last 7 daily, 4 weekly)
    local cleanup_error
    cleanup_error=$(restic forget --keep-daily 7 --keep-weekly 4 --prune --quiet 2>&1)
    if [[ $? -eq 0 ]]; then
        log "INFO" "Cleanup completed"
    else
        log "WARN" "Cleanup had issues: $cleanup_error"
    fi
}

# Input validation function
validate_command() {
    local cmd="$1"
    local valid_commands=("backup" "list" "stats")

    # Check if command is in valid list
    for valid_cmd in "${valid_commands[@]}"; do
        if [[ "$cmd" == "$valid_cmd" ]]; then
            return 0
        fi
    done

    return 1
}

# Main execution with input validation
COMMAND="${1:-backup}"

# Sanitize input - remove any dangerous characters
COMMAND=$(echo "$COMMAND" | tr -cd '[:alnum:]')

if ! validate_command "$COMMAND"; then
    echo "ERROR: Invalid command: $1"
    echo "Usage: $0 {backup|list|stats}"
    exit 1
fi

case "$COMMAND" in
    backup)
        backup_large_volumes
        ;;
    list)
        echo "Available snapshots:"
        if ! check_dependencies; then
            echo "ERROR: Dependencies not met"
            exit 1
        fi
        restic snapshots || echo "ERROR: Failed to list snapshots"
        ;;
    stats)
        echo "Repository statistics:"
        if ! check_dependencies; then
            echo "ERROR: Dependencies not met"
            exit 1
        fi
        restic stats || echo "ERROR: Failed to get repository stats"
        ;;
esac
