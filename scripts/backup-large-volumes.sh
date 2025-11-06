#!/bin/bash
# Production: Automated incremental backup for large volumes
# FIXED: Removed obsolete context-store_neo4j_data volume (no longer exists)

set -euo pipefail

# Configuration
RESTIC_REPOSITORY='/backup/restic-repo'
RESTIC_PASSWORD='backup-secure-password-2024'
export RESTIC_REPOSITORY RESTIC_PASSWORD

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2" | tee -a /var/log/backup-large-volumes.log
}

backup_large_volumes() {
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
            if docker run --rm \
                -v "${volume}:${mount_point}:ro" \
                -v "${temp_dir}:${temp_dir}" \
                alpine sh -c "ls ${mount_point} > /dev/null" 2>/dev/null; then

                # Backup using local restic
                restic backup "${mount_point}" \
                    --tag "volume:${volume}" \
                    --tag "type:large" \
                    --tag "date:$(date +%Y-%m-%d)" \
                    --exclude="*.log" \
                    --exclude="*.tmp" \
                    --exclude=".cache" \
                    2>/dev/null && {
                    log "INFO" "✓ Successfully backed up $volume"
                    ((backed_up++))
                } || {
                    log "WARN" "✗ Failed to backup $volume"
                }
            else
                log "WARN" "Cannot access volume: $volume"
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
    restic forget --keep-daily 7 --keep-weekly 4 --prune --quiet 2>/dev/null || true
    log "INFO" "Cleanup completed"
}

# Main execution
case "${1:-backup}" in
    backup)
        backup_large_volumes
        ;;
    list)
        echo "Available snapshots:"
        restic snapshots 2>/dev/null || echo "No snapshots found"
        ;;
    stats)
        echo "Repository statistics:"
        restic stats 2>/dev/null || echo "No repository stats available"
        ;;
    *)
        echo "Usage: $0 {backup|list|stats}"
        exit 1
        ;;
esac
