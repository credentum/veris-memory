#!/bin/bash

# Comprehensive Neo4j backup investigation and fix script
# This script diagnoses why Neo4j backup is failing and provides solutions

set -u  # Exit on undefined variables

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="${1:-veris-memory-dev-neo4j-1}"
TEST_BACKUP_DIR="/tmp/neo4j-backup-test-$$"

echo -e "${BLUE}=== Neo4j Backup Investigation ===${NC}"
echo "Container: $CONTAINER_NAME"
echo "Test directory: $TEST_BACKUP_DIR"
echo ""

# Create test directory
mkdir -p "$TEST_BACKUP_DIR"

# Step 1: Check if container exists and is running
echo -e "${YELLOW}Step 1: Container Status${NC}"
if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$CONTAINER_NAME"; then
    echo -e "${GREEN}✓ Container is running${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "$CONTAINER_NAME"
else
    echo -e "${RED}✗ Container not found or not running${NC}"
    echo "Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}" | head -5
    exit 1
fi
echo ""

# Step 2: Investigate Neo4j directory structure
echo -e "${YELLOW}Step 2: Neo4j Directory Structure Investigation${NC}"
echo "Checking various potential data locations..."

# Common Neo4j data locations
PATHS_TO_CHECK=(
    "/var/lib/neo4j/data"
    "/data"
    "/var/lib/neo4j"
    "/neo4j/data"
    "/"
)

FOUND_DATA_PATH=""
for path in "${PATHS_TO_CHECK[@]}"; do
    echo -n "Checking $path... "
    if docker exec "$CONTAINER_NAME" test -d "$path" 2>/dev/null; then
        echo -e "${GREEN}EXISTS${NC}"
        
        # Check what's inside
        echo "  Contents:"
        docker exec "$CONTAINER_NAME" ls -la "$path" 2>/dev/null | head -5 | sed 's/^/    /'
        
        # Check for Neo4j-specific directories
        if docker exec "$CONTAINER_NAME" test -d "$path/databases" 2>/dev/null; then
            echo -e "  ${GREEN}✓ Found databases directory${NC}"
            FOUND_DATA_PATH="$path"
        fi
        if docker exec "$CONTAINER_NAME" test -d "$path/transactions" 2>/dev/null; then
            echo -e "  ${GREEN}✓ Found transactions directory${NC}"
            FOUND_DATA_PATH="$path"
        fi
    else
        echo -e "${RED}NOT FOUND${NC}"
    fi
done
echo ""

# Step 3: Determine the actual data path
echo -e "${YELLOW}Step 3: Actual Data Path${NC}"
if [ -n "$FOUND_DATA_PATH" ]; then
    echo -e "${GREEN}✓ Neo4j data located at: $FOUND_DATA_PATH${NC}"
    
    # Get detailed info about the data directory
    echo "Detailed structure:"
    docker exec "$CONTAINER_NAME" find "$FOUND_DATA_PATH" -maxdepth 2 -type d 2>/dev/null | head -20 | sed 's/^/  /'
    
    # Check disk usage
    echo "Disk usage:"
    docker exec "$CONTAINER_NAME" du -sh "$FOUND_DATA_PATH" 2>/dev/null | sed 's/^/  /'
else
    echo -e "${RED}✗ Could not locate Neo4j data directory${NC}"
    echo "Searching for databases directory anywhere in container..."
    docker exec "$CONTAINER_NAME" find / -name "databases" -type d 2>/dev/null | head -5
fi
echo ""

# Step 4: Test different docker cp methods
echo -e "${YELLOW}Step 4: Testing Docker CP Methods${NC}"

if [ -n "$FOUND_DATA_PATH" ]; then
    # Method 1: Direct copy (current method)
    echo "Method 1: Direct copy"
    DEST1="$TEST_BACKUP_DIR/method1-neo4j-data"
    echo "  Command: docker cp $CONTAINER_NAME:$FOUND_DATA_PATH $DEST1"
    
    if docker cp "$CONTAINER_NAME:$FOUND_DATA_PATH" "$DEST1" 2>&1; then
        echo -e "  ${GREEN}✓ Docker cp succeeded${NC}"
        
        # Check what was created
        if [ -e "$DEST1" ]; then
            echo -e "  ${GREEN}✓ Destination exists${NC}"
            echo "  Type: $(file "$DEST1" | cut -d: -f2)"
            if [ -d "$DEST1" ]; then
                FILE_COUNT=$(find "$DEST1" -type f 2>/dev/null | wc -l)
                DIR_COUNT=$(find "$DEST1" -type d 2>/dev/null | wc -l)
                SIZE=$(du -sh "$DEST1" 2>/dev/null | cut -f1)
                echo "  Stats: $FILE_COUNT files, $DIR_COUNT directories, $SIZE total"
                
                # Check for Neo4j specific files
                if [ -d "$DEST1/databases" ]; then
                    echo -e "  ${GREEN}✓ Contains databases directory${NC}"
                fi
                if [ -d "$DEST1/data/databases" ]; then
                    echo -e "  ${YELLOW}⚠ WARNING: Double-nested data/databases structure${NC}"
                fi
            fi
        else
            echo -e "  ${RED}✗ Destination does not exist after copy!${NC}"
            echo "  Checking parent directory:"
            ls -la "$TEST_BACKUP_DIR/" | grep method1
        fi
    else
        echo -e "  ${RED}✗ Docker cp failed${NC}"
    fi
    echo ""
    
    # Method 2: Copy with trailing slash
    echo "Method 2: Copy with trailing slash (contents only)"
    DEST2="$TEST_BACKUP_DIR/method2-neo4j-data"
    mkdir -p "$DEST2"  # Pre-create directory
    echo "  Command: docker cp $CONTAINER_NAME:$FOUND_DATA_PATH/. $DEST2"
    
    if docker cp "$CONTAINER_NAME:$FOUND_DATA_PATH/." "$DEST2" 2>&1; then
        echo -e "  ${GREEN}✓ Docker cp succeeded${NC}"
        
        if [ -d "$DEST2/databases" ]; then
            echo -e "  ${GREEN}✓ Databases directory at correct level${NC}"
            FILE_COUNT=$(find "$DEST2" -type f 2>/dev/null | wc -l)
            SIZE=$(du -sh "$DEST2" 2>/dev/null | cut -f1)
            echo "  Stats: $FILE_COUNT files, $SIZE total"
        else
            echo -e "  ${RED}✗ Databases directory not found${NC}"
        fi
    else
        echo -e "  ${RED}✗ Docker cp failed${NC}"
    fi
    echo ""
    
    # Method 3: Using volumes (if available)
    echo "Method 3: Check for volumes"
    VOLUME_NAME=$(docker inspect "$CONTAINER_NAME" 2>/dev/null | jq -r '.[0].Mounts[] | select(.Destination | contains("neo4j")) | .Name' | head -1)
    if [ -n "$VOLUME_NAME" ] && [ "$VOLUME_NAME" != "null" ]; then
        echo -e "  ${GREEN}✓ Found volume: $VOLUME_NAME${NC}"
        # You could potentially copy from the volume mount point
    else
        echo -e "  ${YELLOW}⚠ No named volume found${NC}"
    fi
fi
echo ""

# Step 5: Permissions investigation
echo -e "${YELLOW}Step 5: Permissions Investigation${NC}"
echo "Checking file ownership in container..."
docker exec "$CONTAINER_NAME" stat -c "%U:%G %a %n" "$FOUND_DATA_PATH" 2>/dev/null
docker exec "$CONTAINER_NAME" ls -la "$FOUND_DATA_PATH" 2>/dev/null | head -3 | sed 's/^/  /'
echo ""

# Step 6: Proposed solution
echo -e "${BLUE}=== PROPOSED SOLUTION ===${NC}"
echo ""
echo "Based on the investigation, here's the recommended fix:"
echo ""

cat << 'EOF'
# Enhanced Neo4j backup function
backup_neo4j_robust() {
    local container="$1"
    local backup_dir="$2"
    
    # First, determine the actual data path in the container
    local neo4j_data_path=""
    for path in "/data" "/var/lib/neo4j/data" "/var/lib/neo4j"; do
        if docker exec "$container" test -d "$path/databases" 2>/dev/null; then
            neo4j_data_path="$path"
            break
        fi
    done
    
    if [ -z "$neo4j_data_path" ]; then
        echo "ERROR: Could not find Neo4j data directory"
        return 1
    fi
    
    echo "Found Neo4j data at: $neo4j_data_path"
    
    # Create destination directory first
    mkdir -p "$backup_dir/neo4j-data"
    
    # Copy using the /. notation to get contents, not the directory itself
    if docker cp "$container:$neo4j_data_path/." "$backup_dir/neo4j-data" 2>/dev/null; then
        # Verify the copy succeeded by checking for expected files
        if [ -d "$backup_dir/neo4j-data/databases" ]; then
            local file_count=$(find "$backup_dir/neo4j-data" -type f 2>/dev/null | wc -l)
            local size=$(du -sh "$backup_dir/neo4j-data" 2>/dev/null | cut -f1)
            echo "✓ Neo4j backup successful: $file_count files, $size"
            return 0
        else
            echo "ERROR: Backup completed but databases directory not found"
            return 1
        fi
    else
        echo "ERROR: Docker cp failed"
        return 1
    fi
}
EOF

echo ""
echo -e "${YELLOW}Key Changes:${NC}"
echo "1. Dynamically detect the actual Neo4j data path"
echo "2. Pre-create the destination directory"
echo "3. Use '/.' notation to copy contents, not the directory itself"
echo "4. Verify by checking for 'databases' directory, not just existence"
echo ""

# Cleanup
echo -e "${YELLOW}Test Results Summary:${NC}"
echo "Test backup directory: $TEST_BACKUP_DIR"
du -sh "$TEST_BACKUP_DIR"/* 2>/dev/null || echo "No successful backups"
echo ""
echo "To clean up test files: rm -rf $TEST_BACKUP_DIR"