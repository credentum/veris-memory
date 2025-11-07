#!/bin/bash
# Final Production Backup Script - Industry Standard Implementation
# Integrates with backup-large-volumes.sh for incremental backups

set -uo pipefail  # Don't exit on error, just log it

# Configuration
BACKUP_ROOT="/backup"
BACKUP_LOG="/var/log/backup-manager.log"

log() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] [$1] $2" | tee -a "$BACKUP_LOG"
}

# Check if container exists and is running
get_container_id() {
    local container_name_pattern="$1"
    local container_id

    container_id=$(docker ps --filter "name=${container_name_pattern}" -q | head -1)

    if [[ -z "$container_id" ]]; then
        log "WARN" "No running container found matching: ${container_name_pattern}"
        return 1
    fi

    echo "$container_id"
    return 0
}

# Validate backup directory before rm -rf
validate_backup_dir() {
    local dir="$1"

    # Safety checks before allowing deletion
    if [[ -z "$dir" ]]; then
        log "ERROR" "Empty directory path provided to validate_backup_dir"
        return 1
    fi

    # Must be under BACKUP_ROOT
    if [[ ! "$dir" =~ ^${BACKUP_ROOT}/ ]]; then
        log "ERROR" "Directory $dir is not under BACKUP_ROOT ($BACKUP_ROOT)"
        return 1
    fi

    # Must contain "backup-" in the name
    if [[ ! "$dir" =~ backup- ]]; then
        log "ERROR" "Directory $dir does not contain 'backup-' pattern"
        return 1
    fi

    return 0
}

perform_backup() {
    local backup_type="${1:-daily}"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="${BACKUP_ROOT}/${backup_type}/backup-${timestamp}"

    log "INFO" "Starting ${backup_type} backup: ${timestamp}"
    mkdir -p "$backup_dir"

    # 1. Backup Databases
    log "INFO" "Phase 1: Backing up databases..."
    mkdir -p "$backup_dir"/{neo4j,qdrant,redis}

    # Neo4j - with container existence check
    if neo4j_container=$(get_container_id "neo4j"); then
        if docker exec "$neo4j_container" tar czf /tmp/neo4j-backup.tar.gz /data 2>&1 | tee -a "$BACKUP_LOG"; then
            if docker cp "${neo4j_container}:/tmp/neo4j-backup.tar.gz" "$backup_dir/neo4j/" 2>&1 | tee -a "$BACKUP_LOG"; then
                log "INFO" "Neo4j backup completed"
            else
                log "WARN" "Failed to copy Neo4j backup from container"
            fi
        else
            log "WARN" "Neo4j backup tar command failed"
        fi
    else
        log "WARN" "Neo4j container not found or not running"
    fi

    # Qdrant - with container existence check
    if qdrant_container=$(get_container_id "qdrant"); then
        if docker cp "${qdrant_container}:/qdrant/storage" "$backup_dir/qdrant/" 2>&1 | tee -a "$BACKUP_LOG"; then
            log "INFO" "Qdrant backup completed"
        else
            log "WARN" "Qdrant backup failed"
        fi
    else
        log "WARN" "Qdrant container not found or not running"
    fi

    # Redis - with container existence check
    if redis_container=$(get_container_id "redis"); then
        if docker exec "$redis_container" redis-cli BGSAVE 2>&1 | tee -a "$BACKUP_LOG"; then
            sleep 2
            if docker cp "${redis_container}:/data/dump.rdb" "$backup_dir/redis/" 2>&1 | tee -a "$BACKUP_LOG"; then
                log "INFO" "Redis backup completed"
            else
                log "WARN" "Failed to copy Redis dump from container"
            fi
        else
            log "WARN" "Redis BGSAVE command failed"
        fi
    else
        log "WARN" "Redis container not found or not running"
    fi

    # 2. Backup Docker Volumes (skip large ones for speed)
    log "INFO" "Phase 2: Backing up Docker volumes..."
    mkdir -p "$backup_dir/docker-volumes"

    # Critical volumes only (under 100MB)
    for volume in $(docker volume ls -q); do
        # Check size first
        size_mb=$(docker run --rm -v "${volume}:/data:ro" alpine du -sm /data 2>/dev/null | cut -f1 || echo "999")

        if [ "$size_mb" -lt 100 ]; then
            log "INFO" "Backing up volume: $volume (${size_mb}MB)"
            docker run --rm \
                -v "${volume}:/source:ro" \
                -v "${backup_dir}/docker-volumes:/backup" \
                alpine tar czf "/backup/${volume}.tar.gz" -C /source . 2>/dev/null || \
                log "WARN" "Failed to backup volume: $volume"
        else
            log "INFO" "Skipping large volume: $volume (${size_mb}MB) - needs incremental backup"
        fi
    done

    # 3. Create manifest
    cat > "$backup_dir/manifest.json" << MANIFEST
{
    "timestamp": "$(date -Iseconds)",
    "type": "${backup_type}",
    "hostname": "$(hostname)",
    "size": "$(du -sh $backup_dir | cut -f1)",
    "databases": ["neo4j", "qdrant", "redis"],
    "volumes_count": $(ls -1 "$backup_dir/docker-volumes/" 2>/dev/null | wc -l)
}
MANIFEST

    log "INFO" "Backup completed: $(du -sh $backup_dir | cut -f1)"

    # 4. Cleanup old backups with safeguards
    log "INFO" "Phase 4: Cleaning up old backups..."

    local retention_days
    case "$backup_type" in
        daily)   retention_days=7 ;;
        weekly)  retention_days=28 ;;
        monthly) retention_days=90 ;;
        *) retention_days=7 ;;
    esac

    local cleanup_dir="${BACKUP_ROOT}/${backup_type}"

    # Safety check: ensure cleanup directory is valid
    if [[ ! -d "$cleanup_dir" ]]; then
        log "WARN" "Cleanup directory does not exist: $cleanup_dir"
        return 0
    fi

    # Find and safely delete old backups
    local deleted_count=0
    while IFS= read -r -d '' old_backup; do
        # Validate each directory before deletion
        if validate_backup_dir "$old_backup"; then
            log "INFO" "Removing old backup: $(basename "$old_backup")"
            if rm -rf "$old_backup"; then
                ((deleted_count++))
            else
                log "WARN" "Failed to remove: $old_backup"
            fi
        else
            log "WARN" "Skipping invalid backup directory: $old_backup"
        fi
    done < <(find "$cleanup_dir" -maxdepth 1 -type d -name "backup-*" -mtime +"$retention_days" -print0)

    if [[ $deleted_count -gt 0 ]]; then
        log "INFO" "Cleaned up $deleted_count old backups (retention: ${retention_days} days)"
    else
        log "INFO" "No old backups to clean up"
    fi
}

# Run backup
perform_backup "$@"

# 5. Backup large volumes using incremental method
# This calls backup-large-volumes.sh which has been fixed to remove obsolete volumes
log "INFO" "Phase 3: Backing up large volumes (incremental)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/backup-large-volumes.sh" backup 2>/dev/null || log "WARN" "Large volume backup had issues"
