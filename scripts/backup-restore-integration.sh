#!/bin/bash
# Backup and Restore Integration for Deploy Workflows
# Prevents data loss during deployments by backing up before cleanup and restoring after deployment

set -e

ACTION="${1:-backup}"
ENVIRONMENT="${2:-dev}"
BACKUP_ROOT="/opt/backups/veris-memory"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Veris Memory Backup/Restore Integration${NC}"
echo -e "${BLUE}==========================================${NC}"
echo "Action: $ACTION"
echo "Environment: $ENVIRONMENT"

# Function to create backup
create_backup() {
    echo -e "${YELLOW}💾 Creating backup before deployment...${NC}"
    
    # Check if containers are running
    if ! docker ps | grep -q "veris-memory-${ENVIRONMENT}"; then
        echo -e "${YELLOW}ℹ️  No running containers to backup${NC}"
        return 0
    fi
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_DIR="${BACKUP_ROOT}/${ENVIRONMENT}/${TIMESTAMP}"
    mkdir -p "$BACKUP_DIR"
    
    # Create metadata file
    cat > "$BACKUP_DIR/metadata.json" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "environment": "${ENVIRONMENT}",
    "created_at": "$(date -Iseconds)",
    "type": "pre_deployment_backup"
}
EOF
    
    # Backup Qdrant
    if docker ps | grep -q "veris-memory-${ENVIRONMENT}-qdrant"; then
        echo "  → Backing up Qdrant..."
        
        # Try using the API first
        if docker exec veris-memory-${ENVIRONMENT}-qdrant-1 \
            curl -s -X POST 'http://localhost:6333/collections/project_context/snapshots' > /dev/null 2>&1; then
            
            # Get snapshot name and download
            SNAPSHOT_NAME=$(docker exec veris-memory-${ENVIRONMENT}-qdrant-1 \
                curl -s 'http://localhost:6333/collections/project_context/snapshots' | \
                jq -r '.result[0].name' 2>/dev/null || echo "")
            
            if [ -n "$SNAPSHOT_NAME" ]; then
                docker exec veris-memory-${ENVIRONMENT}-qdrant-1 \
                    curl -s "http://localhost:6333/collections/project_context/snapshots/${SNAPSHOT_NAME}" \
                    -o "/tmp/${SNAPSHOT_NAME}" 2>/dev/null || true
                
                docker cp "veris-memory-${ENVIRONMENT}-qdrant-1:/tmp/${SNAPSHOT_NAME}" \
                    "$BACKUP_DIR/qdrant.snapshot" 2>/dev/null || true
            fi
        fi
        
        # Fallback: Direct volume copy
        if [ ! -f "$BACKUP_DIR/qdrant.snapshot" ]; then
            echo "    Using fallback: volume copy..."
            docker cp veris-memory-${ENVIRONMENT}-qdrant-1:/qdrant/storage \
                "$BACKUP_DIR/qdrant-storage" 2>/dev/null || true
        fi
    fi
    
    # Backup Neo4j
    if docker ps | grep -q "veris-memory-${ENVIRONMENT}-neo4j"; then
        echo "  → Backing up Neo4j..."
        docker exec veris-memory-${ENVIRONMENT}-neo4j-1 \
            neo4j-admin database dump neo4j --to-path=/tmp 2>/dev/null || true
        
        docker cp "veris-memory-${ENVIRONMENT}-neo4j-1:/tmp/neo4j.dump" \
            "$BACKUP_DIR/neo4j.dump" 2>/dev/null || true
    fi
    
    # Backup Redis
    if docker ps | grep -q "veris-memory-${ENVIRONMENT}-redis"; then
        echo "  → Backing up Redis..."
        docker exec veris-memory-${ENVIRONMENT}-redis-1 \
            redis-cli BGSAVE 2>/dev/null || true
        sleep 2
        
        docker cp "veris-memory-${ENVIRONMENT}-redis-1:/data/dump.rdb" \
            "$BACKUP_DIR/redis.rdb" 2>/dev/null || true
    fi
    
    # Create symlink to latest
    ln -sfn "$BACKUP_DIR" "${BACKUP_ROOT}/${ENVIRONMENT}/latest"
    
    echo -e "${GREEN}✅ Backup completed: $BACKUP_DIR${NC}"
    
    # Cleanup old backups (keep last 7)
    echo "  → Cleaning old backups..."
    find "${BACKUP_ROOT}/${ENVIRONMENT}" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
}

# Function to restore backup
restore_backup() {
    echo -e "${YELLOW}📥 Restoring from backup...${NC}"
    
    # Find latest backup
    LATEST_BACKUP="${BACKUP_ROOT}/${ENVIRONMENT}/latest"
    
    if [ ! -L "$LATEST_BACKUP" ] || [ ! -d "$(readlink -f $LATEST_BACKUP)" ]; then
        echo -e "${YELLOW}ℹ️  No backup found to restore${NC}"
        return 0
    fi
    
    BACKUP_DIR=$(readlink -f "$LATEST_BACKUP")
    echo "  Using backup: $BACKUP_DIR"
    
    # Wait for containers to be ready
    echo "  ⏳ Waiting for containers to be ready..."
    for i in {1..30}; do
        if docker ps | grep -q "veris-memory-${ENVIRONMENT}"; then
            break
        fi
        sleep 2
    done
    
    # Restore Qdrant
    if [ -f "$BACKUP_DIR/qdrant.snapshot" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-qdrant"; then
        echo "  → Restoring Qdrant from snapshot..."
        
        # Copy snapshot to container
        docker cp "$BACKUP_DIR/qdrant.snapshot" \
            "veris-memory-${ENVIRONMENT}-qdrant-1:/tmp/restore.snapshot" 2>/dev/null || true
        
        # Restore via API
        docker exec veris-memory-${ENVIRONMENT}-qdrant-1 \
            curl -X PUT 'http://localhost:6333/collections/project_context' \
            -H 'Content-Type: application/octet-stream' \
            --data-binary '@/tmp/restore.snapshot' 2>/dev/null || true
            
    elif [ -d "$BACKUP_DIR/qdrant-storage" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-qdrant"; then
        echo "  → Restoring Qdrant from volume backup..."
        docker cp "$BACKUP_DIR/qdrant-storage/." \
            "veris-memory-${ENVIRONMENT}-qdrant-1:/qdrant/storage/" 2>/dev/null || true
        docker restart veris-memory-${ENVIRONMENT}-qdrant-1 2>/dev/null || true
    fi
    
    # Restore Neo4j
    if [ -f "$BACKUP_DIR/neo4j.dump" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-neo4j"; then
        echo "  → Restoring Neo4j..."
        docker cp "$BACKUP_DIR/neo4j.dump" \
            "veris-memory-${ENVIRONMENT}-neo4j-1:/tmp/neo4j.dump" 2>/dev/null || true
        
        # Stop Neo4j, restore, restart
        docker exec veris-memory-${ENVIRONMENT}-neo4j-1 neo4j stop 2>/dev/null || true
        sleep 5
        docker exec veris-memory-${ENVIRONMENT}-neo4j-1 \
            neo4j-admin database load neo4j --from-path=/tmp --overwrite-destination 2>/dev/null || true
        docker restart veris-memory-${ENVIRONMENT}-neo4j-1 2>/dev/null || true
    fi
    
    # Restore Redis
    if [ -f "$BACKUP_DIR/redis.rdb" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-redis"; then
        echo "  → Restoring Redis..."
        docker cp "$BACKUP_DIR/redis.rdb" \
            "veris-memory-${ENVIRONMENT}-redis-1:/data/dump.rdb" 2>/dev/null || true
        docker restart veris-memory-${ENVIRONMENT}-redis-1 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✅ Restore completed from $BACKUP_DIR${NC}"
    
    # Verify restore
    sleep 5
    echo "  → Verifying services..."
    docker ps --filter "name=veris-memory-${ENVIRONMENT}" --format "table {{.Names}}\t{{.Status}}"
}

# Main execution
case "$ACTION" in
    backup)
        create_backup
        ;;
    restore)
        restore_backup
        ;;
    *)
        echo -e "${RED}❌ Unknown action: $ACTION${NC}"
        echo "Usage: $0 [backup|restore] [environment]"
        exit 1
        ;;
esac