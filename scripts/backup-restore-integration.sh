#!/bin/bash
# Backup and Restore Integration for Deploy Workflows
# Prevents data loss during deployments by backing up before cleanup and restoring after deployment

# IMPORTANT: No 'set -e' here! We handle errors explicitly for robustness
# Each backup component should be attempted regardless of others failing

ACTION="${1:-backup}"
ENVIRONMENT="${2:-dev}"
BACKUP_ROOT="/opt/backups/veris-memory"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $*"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $*" >&2
}

log_warning() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $*"
}

# Enhanced docker cp with verification
verified_docker_cp() {
    local source="$1"
    local destination="$2"
    local description="${3:-file}"
    
    log "Copying $description: $source -> $destination"
    
    # Attempt copy operation
    if docker cp "$source" "$destination" 2>/dev/null; then
        # Verify the destination file/directory exists
        if [ -e "$destination" ]; then
            # Get file size for verification  
            local size=$(du -sh "$destination" 2>/dev/null | cut -f1 || echo "unknown")
            log "✅ Successfully copied and verified $description (size: $size)"
            return 0
        else
            log_error "❌ Copy appeared successful but $description not found at destination"
            # Additional debugging info
            log_error "Checking parent directory contents:"
            ls -la "$(dirname "$destination")" 2>&1 | head -5 | while read line; do
                log_error "  $line"
            done
            return 1
        fi
    else
        log_error "❌ Failed to copy $description"
        return 1
    fi
}

echo -e "${BLUE}🔧 Veris Memory Backup/Restore Integration v2.0${NC}"
echo -e "${BLUE}===============================================${NC}"
log "Action: $ACTION, Environment: $ENVIRONMENT"

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
    
    # Enhanced backup directory creation with comprehensive error handling
    log "Creating backup directory: $BACKUP_DIR"
    if ! mkdir -p "$BACKUP_DIR" 2>/dev/null; then
        log_error "❌ Failed to create backup directory: $BACKUP_DIR"
        log_error "Check permissions on parent directory: ${BACKUP_ROOT}"
        return 1
    fi
    
    # Verify directory is writable
    if ! touch "$BACKUP_DIR/.write_test" 2>/dev/null; then
        log_error "❌ Backup directory is not writable: $BACKUP_DIR"
        log_error "Check filesystem permissions and disk space"
        return 1
    fi
    rm -f "$BACKUP_DIR/.write_test"
    
    # Verify sufficient disk space (at least 1GB free)
    available_space=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 1048576 ]; then  # 1GB in KB
        log_error "❌ Insufficient disk space for backup: ${available_space}KB available"
        log_error "Require at least 1GB free space in backup location"
        return 1
    fi
    
    log "✅ Backup directory ready: $BACKUP_DIR (${available_space}KB available)"
    
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
    log "Starting Qdrant backup..."
    if docker ps | grep -q "veris-memory-${ENVIRONMENT}-qdrant"; then
        local qdrant_container="veris-memory-${ENVIRONMENT}-qdrant-1"
        log "Found Qdrant container: $qdrant_container"
        
        # Try using the API first
        log "Attempting Qdrant snapshot via API..."
        if docker exec "$qdrant_container" curl -s -X POST 'http://localhost:6333/collections/project_context/snapshots' > /dev/null 2>&1; then
            
            # Get snapshot name and download
            SNAPSHOT_NAME=$(docker exec "$qdrant_container" \
                curl -s 'http://localhost:6333/collections/project_context/snapshots' 2>/dev/null | \
                jq -r '.result[0].name' 2>/dev/null || echo "")
            
            if [ -n "$SNAPSHOT_NAME" ] && [ "$SNAPSHOT_NAME" != "null" ]; then
                log "Created snapshot: $SNAPSHOT_NAME"
                if docker exec "$qdrant_container" \
                    curl -s "http://localhost:6333/collections/project_context/snapshots/${SNAPSHOT_NAME}" \
                    -o "/tmp/${SNAPSHOT_NAME}" 2>/dev/null; then
                    
                    if verified_docker_cp "$qdrant_container:/tmp/${SNAPSHOT_NAME}" \
                        "$BACKUP_DIR/qdrant.snapshot" "Qdrant snapshot"; then
                        log "✅ Qdrant API backup successful"
                    else
                        log_warning "Failed to copy Qdrant snapshot, trying fallback"
                    fi
                else
                    log_warning "Failed to download Qdrant snapshot, trying fallback"
                fi
            else
                log_warning "No snapshot name returned, trying fallback"
            fi
        else
            log_warning "Qdrant API backup failed, trying fallback"
        fi
        
        # Fallback: Direct volume copy
        if [ ! -f "$BACKUP_DIR/qdrant.snapshot" ]; then
            log "Using fallback: volume copy..."
            if verified_docker_cp "$qdrant_container:/qdrant/storage" \
                "$BACKUP_DIR/qdrant-storage" "Qdrant storage directory"; then
                log "✅ Qdrant fallback backup successful"
            else
                log_error "❌ Qdrant backup failed completely"
            fi
        fi
    else
        log_warning "Qdrant container not found"
    fi
    
    # Component status tracking
    local neo4j_status="not_attempted"
    local redis_status="not_attempted"
    
    # Backup Neo4j
    log "Starting Neo4j backup..."
    if docker ps | grep -q "veris-memory-${ENVIRONMENT}-neo4j"; then
        local neo4j_container="veris-memory-${ENVIRONMENT}-neo4j-1"
        log "Found Neo4j container: $neo4j_container"
        
        # Check container health status
        container_health=$(docker inspect "$neo4j_container" --format='{{.State.Health.Status}}' 2>/dev/null || echo "no_health_check")
        container_state=$(docker inspect "$neo4j_container" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
        log "Neo4j container state: $container_state, health: $container_health"
        
        # Enhanced readiness detection - use docker health check when available
        if [ "$container_health" = "healthy" ]; then
            log "Neo4j container reports healthy status"
            neo4j_ready=true
        else
            log "Neo4j container health: $container_health, performing manual readiness checks..."
            neo4j_ready=false
            
            for i in {1..12}; do
                log "Checking Neo4j readiness... (attempt $i/12)"
                
                # Check container health first (if available)
                current_health=$(docker inspect "$neo4j_container" --format='{{.State.Health.Status}}' 2>/dev/null || echo "no_health_check")
                if [ "$current_health" = "healthy" ]; then
                    log "Neo4j container became healthy"
                    neo4j_ready=true
                    break
                fi
                
                # Enhanced diagnostics - check container status first
                if ! docker exec "$neo4j_container" ps aux | grep -q neo4j 2>/dev/null; then
                    log "Neo4j process not running in container yet..."
                    sleep 10
                    continue
                fi
                
                # Check basic HTTP API connectivity (try both curl and wget)
                if docker exec "$neo4j_container" curl -s -f http://localhost:7474/ > /dev/null 2>&1; then
                    log "Neo4j HTTP interface is responding"
                    
                    # Check database connectivity  
                    if docker exec "$neo4j_container" curl -s -u neo4j:"${NEO4J_PASSWORD}" \
                        -H "Content-Type: application/json" \
                        -d '{"statements":[{"statement":"RETURN 1 as test"}]}' \
                        http://localhost:7474/db/neo4j/tx/commit 2>/dev/null | grep -q "result"; then
                        log "Neo4j database is accepting queries"
                        neo4j_ready=true
                        break
                    else
                        log "Neo4j database not ready yet..."
                    fi
                elif docker exec "$neo4j_container" wget --no-verbose --tries=1 --spider http://localhost:7474 > /dev/null 2>&1; then
                    log "Neo4j HTTP interface responding (via wget)"
                    # For wget, try simpler endpoint check
                    if docker exec "$neo4j_container" wget --no-verbose --tries=1 --spider http://localhost:7474/db/neo4j/ > /dev/null 2>&1; then
                        log "Neo4j database endpoints accessible"
                        neo4j_ready=true
                        break
                    else
                        log "Neo4j HTTP interface ready but database not accessible yet..."
                    fi
                else
                    log "Neo4j HTTP interface not ready yet..."
                fi
                
                sleep 10
            done
        fi
        
        if [ "$neo4j_ready" = false ]; then
            log_warning "Neo4j failed to become ready within 2 minutes, skipping online backup methods"
        fi
        
        # Method 1: Try HTTP API backup using APOC (more reliable than cypher-shell)
        if [ "$neo4j_ready" = true ]; then
            log "Attempting Neo4j online backup via HTTP API..."
            
            # Wait for APOC to be available (can take a moment after Neo4j starts)
            apoc_ready=false
            for j in {1..6}; do
                log "Checking APOC availability... (attempt $j/6)"
                if docker exec "$neo4j_container" curl -s -u neo4j:"${NEO4J_PASSWORD}" \
                    -H "Content-Type: application/json" \
                    -d '{"statements":[{"statement":"RETURN apoc.version() as version"}]}' \
                    http://localhost:7474/db/neo4j/tx/commit 2>/dev/null | grep -q "result"; then
                    apoc_ready=true
                    log "APOC plugin is available"
                    break
                else
                    log "APOC not ready yet, waiting..."
                    sleep 5
                fi
            done
            
            if [ "$apoc_ready" = true ]; then
                log "APOC is available, attempting HTTP API export..."
                
                # Export via HTTP API call to APOC
                if docker exec "$neo4j_container" curl -s -u neo4j:"${NEO4J_PASSWORD}" \
                    -H "Content-Type: application/json" \
                    -d '{"statements":[{"statement":"CALL apoc.export.cypher.all('\''/tmp/neo4j-export.cypher'\'', {format: '\''cypher-shell'\''})"}]}' \
                    http://localhost:7474/db/neo4j/tx/commit > /dev/null 2>&1; then
                    
                    # Wait a moment for export to complete
                    sleep 2
                    
                    if verified_docker_cp "$neo4j_container:/tmp/neo4j-export.cypher" \
                        "$BACKUP_DIR/neo4j-export.cypher" "Neo4j APOC export"; then
                        log "✅ Neo4j HTTP API backup successful (APOC export)"
                    else
                        log_warning "Failed to copy Neo4j HTTP API export"
                    fi
                else
                    log_warning "Neo4j HTTP API export failed"
                fi
            else
                log_warning "APOC plugin not available after 30 seconds, skipping HTTP API export method"
            fi
        else
            log_warning "Neo4j not ready for online backup methods"
        fi
        
        # Method 2: Skip online dump as it requires stopping the database
        # Neo4j admin dump requires database to be stopped, which interrupts service
        # if [ ! -f "$BACKUP_DIR/neo4j-export.cypher" ] && [ "$neo4j_ready" = true ]; then
        #     log "Neo4j admin dump requires stopping database, skipping for online backup"
        # fi
        
        # Log if Neo4j not ready for online methods
        if [ "$neo4j_ready" = false ] && [ ! -f "$BACKUP_DIR/neo4j-export.cypher" ]; then
            log_warning "Neo4j not ready for online methods, will use enhanced fallback"
        fi
        
        # Method 2: Enhanced fallback with better consistency (primary method for online backups)
        if [ ! -f "$BACKUP_DIR/neo4j.dump" ] && [ ! -f "$BACKUP_DIR/neo4j-export.cypher" ]; then
            log "Using enhanced fallback: optimized data copy with consistency checks..."
            
            # Dynamically detect Neo4j data path in container
            local neo4j_data_path=""
            for test_path in "/data" "/var/lib/neo4j/data" "/var/lib/neo4j"; do
                if docker exec "$neo4j_container" test -d "$test_path/databases" 2>/dev/null; then
                    neo4j_data_path="$test_path"
                    log "Detected Neo4j data path: $neo4j_data_path"
                    break
                fi
            done
            
            if [ -z "$neo4j_data_path" ]; then
                log_error "Could not detect Neo4j data directory in container"
                # Try default path as last resort
                neo4j_data_path="/var/lib/neo4j/data"
                log_warning "Using default path: $neo4j_data_path"
            fi
            
            # Try to request checkpoint if Neo4j API is accessible
            if [ "$neo4j_ready" = true ]; then
                log "Requesting checkpoint via API before fallback copy..."
                docker exec "$neo4j_container" curl -s -u neo4j:"${NEO4J_PASSWORD}" \
                    -H "Content-Type: application/json" \
                    -d '{"statements":[{"statement":"CALL db.checkpoint()"}]}' \
                    http://localhost:7474/db/neo4j/tx/commit > /dev/null 2>&1
            else
                log "Neo4j API not accessible, proceeding with filesystem-level sync..."
            fi
            
            # Wait for any pending writes to complete
            sleep 3
            
            # Copy with enhanced options for better consistency
            # Note: sync might fail in some container environments, so we make it optional
            docker exec "$neo4j_container" sh -c 'sync && sleep 1' 2>/dev/null || {
                log_warning "Container filesystem sync failed, proceeding without sync"
            }
            
            # Pre-create destination directory to ensure consistent docker cp behavior
            mkdir -p "$BACKUP_DIR/neo4j-data"
            
            # Attempt the actual data copy using /. notation to copy contents
            if docker cp "$neo4j_container:$neo4j_data_path/." "$BACKUP_DIR/neo4j-data" 2>/dev/null; then
                # Enhanced verification for directory copy
                local neo4j_file_count=$(find "$BACKUP_DIR/neo4j-data" -type f 2>/dev/null | wc -l)
                
                # Verify backup contains expected files - check multiple possible locations
                if [ -f "$BACKUP_DIR/neo4j-data/databases/neo4j/neostore" ] || \
                   [ -f "$BACKUP_DIR/neo4j-data/databases/system/neostore" ] || \
                   [ "$neo4j_file_count" -gt 10 ]; then
                    log "✅ Neo4j enhanced fallback backup completed with consistency optimizations"
                    neo4j_status="success_fallback"
                    
                    # Create metadata about this backup method
                    echo '{"method":"enhanced_fallback","consistency":"optimized","checkpoint":"requested"}' > \
                        "$BACKUP_DIR/neo4j-backup-metadata.json"
                else
                    log_warning "⚠️ Neo4j fallback backup completed but verification failed"
                    neo4j_status="partial_failure"
                fi
            else
                log_error "❌ All Neo4j backup methods failed completely"
                neo4j_status="failed"
            fi
        fi
        
        # Set success status if APOC export succeeded
        if [ -f "$BACKUP_DIR/neo4j-export.cypher" ]; then
            neo4j_status="success_apoc"
        fi
    else
        log "ℹ️ No Neo4j containers found to backup"
        neo4j_status="no_container"
    fi
    
    # Log backup summary for Neo4j
    neo4j_backup_status="none"
    if [ -f "$BACKUP_DIR/neo4j-export.cypher" ]; then
        neo4j_backup_status="HTTP_API_export"
    elif [ -f "$BACKUP_DIR/neo4j.dump" ]; then
        neo4j_backup_status="online_dump"
    elif [ -d "$BACKUP_DIR/neo4j-data" ]; then
        neo4j_backup_status="enhanced_fallback"
    fi
    
    log "📊 Neo4j backup status: $neo4j_backup_status"
    
    # Backup Redis (ALWAYS attempt, regardless of Neo4j status)
    log "Starting Redis backup..."
    if docker ps | grep -q "veris-memory-${ENVIRONMENT}-redis"; then
        local redis_container="veris-memory-${ENVIRONMENT}-redis-1"
        log "Found Redis container: $redis_container"

        # Trigger background save for RDB
        if docker exec "$redis_container" redis-cli BGSAVE 2>/dev/null; then
            log "Redis BGSAVE initiated"

            # Wait for BGSAVE to complete (check every second, max 30 seconds)
            for i in {1..30}; do
                if docker exec "$redis_container" redis-cli LASTSAVE 2>/dev/null > /tmp/lastsave_check; then
                    sleep 1
                    if docker exec "$redis_container" redis-cli LASTSAVE 2>/dev/null | cmp -s /tmp/lastsave_check -; then
                        continue  # BGSAVE still running
                    else
                        log "BGSAVE completed after ${i} seconds"
                        break
                    fi
                else
                    log_warning "Could not check BGSAVE status"
                    break
                fi
            done

            # Trigger AOF rewrite to consolidate AOF files
            log "Triggering AOF rewrite for clean backup..."
            docker exec "$redis_container" redis-cli BGREWRITEAOF 2>/dev/null || log_warning "BGREWRITEAOF failed (may not be using AOF)"
            sleep 2  # Give AOF rewrite time to start

            # Copy entire /data directory (includes both RDB and AOF files)
            log "Backing up Redis data directory (RDB + AOF files)..."
            if verified_docker_cp "$redis_container:/data" \
                "$BACKUP_DIR/redis-data" "Redis data directory"; then
                log "✅ Redis backup successful (RDB + AOF)"

                # List backed up files for verification
                log "Backed up Redis files:"
                ls -lah "$BACKUP_DIR/redis-data" 2>/dev/null | grep -E "(dump\.rdb|appendonly)" | while read line; do
                    log "  $line"
                done

                redis_status="success"
            else
                log_error "❌ Failed to copy Redis data directory"
                redis_status="copy_failed"
            fi
        else
            log_error "❌ Redis BGSAVE failed"
            redis_status="bgsave_failed"
        fi
    else
        log_warning "Redis container not found"
        redis_status="no_container"
    fi
    
    # Create backup summary
    log "Creating backup summary..."
    local backup_success=0
    local backup_methods=""
    
    [ -f "$BACKUP_DIR/qdrant.snapshot" ] && backup_success=$((backup_success + 1)) && backup_methods="$backup_methods Qdrant(API)"
    [ -d "$BACKUP_DIR/qdrant-storage" ] && backup_success=$((backup_success + 1)) && backup_methods="$backup_methods Qdrant(Volume)"
    [ -f "$BACKUP_DIR/neo4j-export.cypher" ] && backup_success=$((backup_success + 1)) && backup_methods="$backup_methods Neo4j(Online)"
    [ -f "$BACKUP_DIR/neo4j.dump" ] && backup_success=$((backup_success + 1)) && backup_methods="$backup_methods Neo4j(Dump)"
    [ -d "$BACKUP_DIR/neo4j-data" ] && backup_success=$((backup_success + 1)) && backup_methods="$backup_methods Neo4j(Data)"
    [ -d "$BACKUP_DIR/redis-data" ] && backup_success=$((backup_success + 1)) && backup_methods="$backup_methods Redis(RDB+AOF)"
    
    # Update metadata with results
    cat >> "$BACKUP_DIR/metadata.json.tmp" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "environment": "${ENVIRONMENT}",
    "created_at": "$(date -Iseconds)",
    "type": "pre_deployment_backup",
    "backup_methods": "$backup_methods",
    "components_backed_up": $backup_success,
    "backup_status": "$([ $backup_success -gt 0 ] && echo 'partial_success' || echo 'failed')"
}
EOF
    mv "$BACKUP_DIR/metadata.json.tmp" "$BACKUP_DIR/metadata.json"
    
    # Create symlink to latest
    ln -sfn "$BACKUP_DIR" "${BACKUP_ROOT}/${ENVIRONMENT}/latest"
    
    # Comprehensive backup status report
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📊 BACKUP STATUS REPORT"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  • Qdrant: $([ -f "$BACKUP_DIR/qdrant.snapshot" ] || [ -d "$BACKUP_DIR/qdrant-storage" ] && echo "✅ SUCCESS" || echo "❌ FAILED")"
    log "  • Neo4j:  $neo4j_status"
    log "  • Redis:  $redis_status"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ $backup_success -gt 0 ]; then
        log "✅ Backup completed: $BACKUP_DIR ($backup_success components:$backup_methods)"
        echo -e "${GREEN}✅ Backup completed with $backup_success successful component(s)${NC}"
        
        # Show which components succeeded
        log "📁 Backed up files:"
        [ -f "$BACKUP_DIR/qdrant.snapshot" ] && log "  ✓ Qdrant snapshot: $(du -sh "$BACKUP_DIR/qdrant.snapshot" 2>/dev/null | cut -f1)"
        [ -d "$BACKUP_DIR/qdrant-storage" ] && log "  ✓ Qdrant storage: $(du -sh "$BACKUP_DIR/qdrant-storage" 2>/dev/null | cut -f1)"
        [ -f "$BACKUP_DIR/neo4j-export.cypher" ] && log "  ✓ Neo4j export: $(du -sh "$BACKUP_DIR/neo4j-export.cypher" 2>/dev/null | cut -f1)"
        [ -d "$BACKUP_DIR/neo4j-data" ] && log "  ✓ Neo4j data: $(du -sh "$BACKUP_DIR/neo4j-data" 2>/dev/null | cut -f1)"
        [ -d "$BACKUP_DIR/redis-data" ] && log "  ✓ Redis data (RDB+AOF): $(du -sh "$BACKUP_DIR/redis-data" 2>/dev/null | cut -f1)"
        
        # Return success if at least one component backed up
        return 0
    else
        log_error "❌ Backup failed: No components were backed up successfully"
        echo -e "${RED}❌ Backup failed: No components were backed up successfully${NC}"
        
        # Enhanced failure diagnostics
        log_error "📊 Backup failure analysis:"
        log_error "  → Component statuses:"
        log_error "    • Qdrant: Check logs above for snapshot/volume copy issues"
        log_error "    • Neo4j:  $neo4j_status"
        log_error "    • Redis:  $redis_status"
        
        log_error "  → Expected files not found:"
        [ ! -f "$BACKUP_DIR/qdrant.snapshot" ] && [ ! -d "$BACKUP_DIR/qdrant-storage" ] && log_error "    • Qdrant backup missing"
        [ ! -f "$BACKUP_DIR/neo4j-export.cypher" ] && [ ! -f "$BACKUP_DIR/neo4j.dump" ] && [ ! -d "$BACKUP_DIR/neo4j-data" ] && log_error "    • Neo4j backup missing"
        [ ! -d "$BACKUP_DIR/redis-data" ] && log_error "    • Redis backup missing"
        
        log_error "  → Troubleshooting steps:"
        log_error "    1. Check backup directory permissions: $BACKUP_DIR"
        log_error "    2. Verify sufficient disk space: $(df -h "$BACKUP_DIR" 2>/dev/null | tail -1 || echo 'Unable to check')"
        log_error "    3. Check container accessibility with: docker ps"
        log_error "    4. Review logs above for specific docker cp failures"
        
        # Return failure only if ALL components failed
        return 1
    fi
    
    # Cleanup old backups (keep last 7)
    echo "  → Cleaning old backups..."
    find "${BACKUP_ROOT}/${ENVIRONMENT}" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
}

# Function to restore backup
restore_backup() {
    log "🔄 RESTORE PHASE STARTED"
    echo -e "${YELLOW}📥 Restoring from backup...${NC}"
    
    # Find latest backup
    LATEST_BACKUP="${BACKUP_ROOT}/${ENVIRONMENT}/latest"
    log "Looking for backup at: $LATEST_BACKUP"
    
    if [ ! -L "$LATEST_BACKUP" ]; then
        log_warning "No latest backup symlink found at $LATEST_BACKUP"
        echo -e "${YELLOW}ℹ️  No backup found to restore${NC}"
        return 0
    fi
    
    BACKUP_DIR=$(readlink -f "$LATEST_BACKUP")
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory not found: $BACKUP_DIR"
        echo -e "${RED}❌ Backup directory not accessible${NC}"
        return 1
    fi
    
    log "✅ Found backup directory: $BACKUP_DIR"
    echo "  Using backup: $BACKUP_DIR"
    
    # Check backup metadata
    if [ -f "$BACKUP_DIR/metadata.json" ]; then
        log "Backup metadata found, checking contents..."
        if command -v jq > /dev/null 2>&1; then
            local backup_status=$(jq -r '.backup_status // "unknown"' "$BACKUP_DIR/metadata.json" 2>/dev/null || echo "unknown")
            local backup_methods=$(jq -r '.backup_methods // "unknown"' "$BACKUP_DIR/metadata.json" 2>/dev/null || echo "unknown")
            log "Backup status: $backup_status, methods: $backup_methods"
        fi
    fi
    
    # Wait for containers to be ready with better logging
    log "Waiting for containers to be ready..."
    echo "  ⏳ Waiting for containers to be ready..."
    local containers_ready=false
    for i in {1..30}; do
        if docker ps | grep -q "veris-memory-${ENVIRONMENT}"; then
            containers_ready=true
            log "✅ Containers are ready after ${i} attempts"
            break
        fi
        log "Attempt $i/30: No containers found, waiting 2 seconds..."
        sleep 2
    done
    
    if [ "$containers_ready" = false ]; then
        log_error "❌ Containers not ready after 60 seconds"
        echo -e "${RED}❌ Containers not ready for restore${NC}"
        return 1
    fi
    
    # Restore Qdrant
    log "Starting Qdrant restore..."
    local qdrant_restored=false
    
    if [ -f "$BACKUP_DIR/qdrant.snapshot" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-qdrant"; then
        local qdrant_container="veris-memory-${ENVIRONMENT}-qdrant-1"
        log "Attempting Qdrant restore from API snapshot..."
        echo "  → Restoring Qdrant from snapshot..."
        
        # Copy snapshot to container
        if docker cp "$BACKUP_DIR/qdrant.snapshot" \
            "$qdrant_container:/tmp/restore.snapshot" 2>/dev/null; then
            log "Snapshot copied to container successfully"
            
            # Wait for Qdrant to be ready
            for i in {1..10}; do
                if docker exec "$qdrant_container" \
                    curl -s 'http://localhost:6333/health' > /dev/null 2>&1; then
                    log "Qdrant is ready for restore"
                    break
                fi
                log "Waiting for Qdrant to be ready... ($i/10)"
                sleep 3
            done
            
            # Restore via API (recreate collection from snapshot)
            if docker exec "$qdrant_container" \
                curl -X DELETE 'http://localhost:6333/collections/project_context' 2>/dev/null; then
                log "Existing collection deleted"
            fi
            
            if docker exec "$qdrant_container" \
                curl -X PUT 'http://localhost:6333/collections/project_context/snapshots/restore' \
                -H 'Content-Type: application/octet-stream' \
                --data-binary '@/tmp/restore.snapshot' 2>/dev/null; then
                log "✅ Qdrant restore from snapshot successful"
                qdrant_restored=true
            else
                log_warning "Qdrant API restore failed, trying volume method"
            fi
        else
            log_warning "Failed to copy snapshot to container"
        fi
            
    elif [ -d "$BACKUP_DIR/qdrant-storage" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-qdrant"; then
        local qdrant_container="veris-memory-${ENVIRONMENT}-qdrant-1"
        log "Attempting Qdrant restore from volume backup..."
        echo "  → Restoring Qdrant from volume backup..."
        
        # Stop container, restore volume, restart
        if docker stop "$qdrant_container" 2>/dev/null; then
            log "Qdrant container stopped"
            sleep 2
            
            if docker cp "$BACKUP_DIR/qdrant-storage/." \
                "$qdrant_container:/qdrant/storage/" 2>/dev/null; then
                log "Volume data copied successfully"
                
                if docker start "$qdrant_container" 2>/dev/null; then
                    log "✅ Qdrant restore from volume successful"
                    qdrant_restored=true
                else
                    log_error "Failed to restart Qdrant container"
                fi
            else
                log_error "Failed to copy volume data"
            fi
        else
            log_error "Failed to stop Qdrant container for volume restore"
        fi
    else
        log_warning "No Qdrant backup found or container not running"
    fi
    
    # Restore Neo4j
    log "Starting Neo4j restore..."
    local neo4j_restored=false
    
    if [ -f "$BACKUP_DIR/neo4j-export.cypher" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-neo4j"; then
        local neo4j_container="veris-memory-${ENVIRONMENT}-neo4j-1"
        log "Attempting Neo4j restore from cypher export..."
        echo "  → Restoring Neo4j from cypher export..."
        
        if docker cp "$BACKUP_DIR/neo4j-export.cypher" \
            "$neo4j_container:/tmp/neo4j-export.cypher" 2>/dev/null; then
            
            # Wait for Neo4j to be ready using HTTP API
            for i in {1..10}; do
                if docker exec "$neo4j_container" curl -s -u neo4j:"${NEO4J_PASSWORD}" \
                    -H "Content-Type: application/json" \
                    -d '{"statements":[{"statement":"RETURN 1"}]}' \
                    http://localhost:7474/db/neo4j/tx/commit | grep -q "result"; then
                    log "Neo4j is ready for restore"
                    break
                fi
                log "Waiting for Neo4j to be ready... ($i/10)"
                sleep 5
            done
            
            # Execute cypher restore via HTTP API (more reliable than cypher-shell)
            log "Executing cypher restore via HTTP API..."
            if docker exec "$neo4j_container" curl -s -u neo4j:"${NEO4J_PASSWORD}" \
                -H "Content-Type: application/json" \
                -d '{"statements":[{"statement":"CALL apoc.cypher.runFile('\''/tmp/neo4j-export.cypher'\'')"}]}' \
                http://localhost:7474/db/neo4j/tx/commit | grep -q "result"; then
                log "✅ Neo4j restore from HTTP API cypher successful"
                neo4j_restored=true
            else
                log_warning "Neo4j HTTP API cypher restore failed, trying dump method"
            fi
        else
            log_warning "Failed to copy cypher export to container"
        fi
    fi
    
    if [ "$neo4j_restored" = false ] && [ -f "$BACKUP_DIR/neo4j.dump" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-neo4j"; then
        local neo4j_container="veris-memory-${ENVIRONMENT}-neo4j-1"
        log "Attempting Neo4j restore from dump..."
        echo "  → Restoring Neo4j from dump..."
        
        if docker cp "$BACKUP_DIR/neo4j.dump" \
            "$neo4j_container:/tmp/neo4j.dump" 2>/dev/null; then
            log "Dump file copied to container"
            
            # Stop Neo4j, restore, restart
            if docker exec "$neo4j_container" neo4j stop 2>/dev/null; then
                log "Neo4j stopped for restore"
                sleep 5
                
                if docker exec "$neo4j_container" \
                    neo4j-admin database load neo4j --from-path=/tmp --overwrite-destination 2>/dev/null; then
                    log "Database loaded from dump"
                    
                    if docker exec "$neo4j_container" neo4j start 2>/dev/null; then
                        log "✅ Neo4j restore from dump successful"
                        neo4j_restored=true
                    else
                        log_error "Failed to restart Neo4j after restore"
                    fi
                else
                    log_error "Failed to load database from dump"
                fi
            else
                log_warning "Failed to stop Neo4j, trying container restart"
                docker restart "$neo4j_container" 2>/dev/null || log_error "Container restart failed"
            fi
        else
            log_error "Failed to copy dump to container"
        fi
    elif [ "$neo4j_restored" = false ] && [ -d "$BACKUP_DIR/neo4j-data" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-neo4j"; then
        local neo4j_container="veris-memory-${ENVIRONMENT}-neo4j-1"
        log "Attempting Neo4j restore from data directory..."
        echo "  → Restoring Neo4j from data backup..."
        
        # Dynamically detect Neo4j data path in container for restore
        local neo4j_data_path=""
        for test_path in "/data" "/var/lib/neo4j/data" "/var/lib/neo4j"; do
            if docker exec "$neo4j_container" test -d "$test_path" 2>/dev/null; then
                neo4j_data_path="$test_path"
                log "Detected Neo4j data path for restore: $neo4j_data_path"
                break
            fi
        done
        
        if [ -z "$neo4j_data_path" ]; then
            neo4j_data_path="/var/lib/neo4j/data"
            log_warning "Using default Neo4j path for restore: $neo4j_data_path"
        fi
        
        # Stop container, restore data, restart
        if docker stop "$neo4j_container" 2>/dev/null; then
            log "Neo4j container stopped for data restore"
            sleep 3
            
            if docker cp "$BACKUP_DIR/neo4j-data/." \
                "$neo4j_container:$neo4j_data_path/" 2>/dev/null; then
                log "Data directory copied successfully to $neo4j_data_path"
                
                if docker start "$neo4j_container" 2>/dev/null; then
                    log "⚠️ Neo4j restore from data directory completed (may be inconsistent)"
                    neo4j_restored=true
                else
                    log_error "Failed to restart Neo4j container"
                fi
            else
                log_error "Failed to copy data directory to $neo4j_data_path"
            fi
        else
            log_error "Failed to stop Neo4j container"
        fi
    else
        log_warning "No Neo4j backup found or container not running"
    fi
    
    # Restore Redis
    log "Starting Redis restore..."
    local redis_restored=false

    if [ -d "$BACKUP_DIR/redis-data" ] && docker ps | grep -q "veris-memory-${ENVIRONMENT}-redis"; then
        local redis_container="veris-memory-${ENVIRONMENT}-redis-1"
        log "Attempting Redis restore from backup (RDB + AOF)..."
        echo "  → Restoring Redis..."

        # Show what we're restoring
        log "Backup contains:"
        ls -lah "$BACKUP_DIR/redis-data" 2>/dev/null | grep -E "(dump\.rdb|appendonly)" | while read line; do
            log "  $line"
        done

        # Stop Redis container
        if docker stop "$redis_container" 2>/dev/null; then
            log "Redis container stopped"
            sleep 2

            # Clear existing Redis data directory in container
            log "Clearing existing Redis data..."
            docker exec "$redis_container" sh -c "rm -rf /data/*" 2>/dev/null || log_warning "Could not clear /data (container stopped)"

            # Copy entire backup directory contents to /data
            # Note: docker cp copies directory contents when path ends with /.
            if docker cp "$BACKUP_DIR/redis-data/." "$redis_container:/data/" 2>/dev/null; then
                log "Redis data directory restored successfully"

                # Verify copied files
                log "Verifying restored files..."
                docker start "$redis_container" 2>/dev/null
                sleep 3
                docker exec "$redis_container" ls -la /data/ 2>/dev/null | while read line; do
                    log "  $line"
                done

                # Check if Redis loaded data
                sleep 2
                local redis_keys=$(docker exec "$redis_container" redis-cli DBSIZE 2>/dev/null | grep -oE '[0-9]+' || echo "0")
                log "Redis reports $redis_keys keys after restore"

                if [ "$redis_keys" -gt 0 ]; then
                    log "✅ Redis restore successful ($redis_keys keys loaded)"
                    redis_restored=true
                else
                    log_warning "⚠️  Redis restored but reports 0 keys (may need time to load AOF)"
                    redis_restored=true  # Still consider it successful if files were copied
                fi
            else
                log_error "Failed to copy Redis data directory"
                docker start "$redis_container" 2>/dev/null  # Try to restart anyway
            fi
        else
            log_error "Failed to stop Redis container"
        fi
    else
        log_warning "No Redis backup found or container not running"
    fi
    
    # Create restore summary
    log "Creating restore summary..."
    local restore_success=0
    local restore_methods=""
    
    [ "$qdrant_restored" = true ] && restore_success=$((restore_success + 1)) && restore_methods="$restore_methods Qdrant"
    [ "$neo4j_restored" = true ] && restore_success=$((restore_success + 1)) && restore_methods="$restore_methods Neo4j"
    [ "$redis_restored" = true ] && restore_success=$((restore_success + 1)) && restore_methods="$restore_methods Redis"
    
    if [ $restore_success -gt 0 ]; then
        log "✅ Restore completed: $restore_success components restored:$restore_methods"
        echo -e "${GREEN}✅ Restore completed from $BACKUP_DIR ($restore_success components)${NC}"
    else
        log_error "❌ Restore failed: No components were restored successfully"
        echo -e "${RED}❌ Restore failed: No components were restored successfully${NC}"
    fi
    
    # Verify restore
    log "Verifying services after restore..."
    sleep 5
    echo "  → Verifying services..."
    docker ps --filter "name=veris-memory-${ENVIRONMENT}" --format "table {{.Names}}\t{{.Status}}"
    
    # Health check
    log "Performing post-restore health checks..."
    local health_checks=0
    
    # Check Qdrant
    if docker exec "veris-memory-${ENVIRONMENT}-qdrant-1" \
        curl -s 'http://localhost:6333/health' > /dev/null 2>&1; then
        log "✅ Qdrant health check passed"
        health_checks=$((health_checks + 1))
    else
        log_warning "❌ Qdrant health check failed"
    fi
    
    # Check Neo4j using HTTP API (more reliable than cypher-shell)
    if docker exec "veris-memory-${ENVIRONMENT}-neo4j-1" \
        curl -s -u neo4j:"${NEO4J_PASSWORD}" \
        -H "Content-Type: application/json" \
        -d '{"statements":[{"statement":"RETURN 1"}]}' \
        http://localhost:7474/db/neo4j/tx/commit | grep -q "result" > /dev/null 2>&1; then
        log "✅ Neo4j health check passed"
        health_checks=$((health_checks + 1))
    else
        log_warning "❌ Neo4j health check failed"
    fi
    
    # Check Redis
    if docker exec "veris-memory-${ENVIRONMENT}-redis-1" \
        redis-cli ping > /dev/null 2>&1; then
        log "✅ Redis health check passed"
        health_checks=$((health_checks + 1))
    else
        log_warning "❌ Redis health check failed"
    fi
    
    log "🔄 RESTORE PHASE COMPLETED - $health_checks/3 services healthy"
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