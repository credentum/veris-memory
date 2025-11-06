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

perform_backup() {
    local backup_type="${1:-daily}"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="${BACKUP_ROOT}/${backup_type}/backup-${timestamp}"

    log "INFO" "Starting ${backup_type} backup: ${timestamp}"
    mkdir -p "$backup_dir"

    # 1. Backup Databases
    log "INFO" "Phase 1: Backing up databases..."
    mkdir -p "$backup_dir"/{neo4j,qdrant,redis}

    # Neo4j
    docker exec $(docker ps --filter "name=neo4j" -q | head -1) tar czf /tmp/neo4j-backup.tar.gz /data 2>/dev/null && \
        docker cp $(docker ps --filter "name=neo4j" -q | head -1):/tmp/neo4j-backup.tar.gz "$backup_dir/neo4j/" 2>/dev/null || \
        log "WARN" "Neo4j backup failed"

    # Qdrant
    docker cp $(docker ps --filter "name=qdrant" -q | head -1):/qdrant/storage "$backup_dir/qdrant/" 2>/dev/null || \
        log "WARN" "Qdrant backup failed"

    # Redis
    docker exec $(docker ps --filter "name=redis" -q | head -1) redis-cli BGSAVE 2>/dev/null
    sleep 2
    docker cp $(docker ps --filter "name=redis" -q | head -1):/data/dump.rdb "$backup_dir/redis/" 2>/dev/null || \
        log "WARN" "Redis backup failed"

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

    # 4. Cleanup old backups
    case "$backup_type" in
        daily)   find "${BACKUP_ROOT}/daily" -maxdepth 1 -type d -name "backup-*" -mtime +7 -exec rm -rf {} \; ;;
        weekly)  find "${BACKUP_ROOT}/weekly" -maxdepth 1 -type d -name "backup-*" -mtime +28 -exec rm -rf {} \; ;;
        monthly) find "${BACKUP_ROOT}/monthly" -maxdepth 1 -type d -name "backup-*" -mtime +90 -exec rm -rf {} \; ;;
    esac
}

# Run backup
perform_backup "$@"

# 5. Backup large volumes using incremental method
# This calls backup-large-volumes.sh which has been fixed to remove obsolete volumes
log "INFO" "Phase 3: Backing up large volumes (incremental)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/backup-large-volumes.sh" backup 2>/dev/null || log "WARN" "Large volume backup had issues"
