#!/bin/bash
#
# Manifest Hygiene - Archive old/incorrect manifests and maintain clean state
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ARCHIVE_DIR="manifests/archive/$(date +%Y%m%d)"
MANIFEST_DIRS=("manifests" "configs" "deploy")
EXPECTED_DIM=384
EXPECTED_DISTANCE="Cosine"

# Counters
ARCHIVED_COUNT=0
VALID_COUNT=0
TOTAL_COUNT=0

# Functions
status() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Parse arguments
DRY_RUN=false
VERBOSE=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Archive old/incorrect manifests and maintain clean state"
            echo ""
            echo "Options:"
            echo "  --dry-run   Show what would be archived without moving files"
            echo "  --verbose   Show detailed information about each manifest"
            echo "  --help      Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "========================================="
echo "Manifest Hygiene Check"
echo "========================================="
echo ""
echo "Expected configuration:"
echo "  Dimensions: $EXPECTED_DIM"
echo "  Distance: $EXPECTED_DISTANCE"
echo ""

if [ "$DRY_RUN" = true ]; then
    warning "DRY RUN MODE - No files will be moved"
    echo ""
fi

# Create archive directory if needed (even in dry-run to show intent)
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$ARCHIVE_DIR"
    status "Archive directory created: $ARCHIVE_DIR"
else
    info "Would create archive directory: $ARCHIVE_DIR"
fi
echo ""

# Function to check manifest
check_manifest() {
    local file="$1"
    local should_archive=false
    local reasons=()
    
    ((TOTAL_COUNT++))
    
    # Check file extension
    if [[ "$file" == *.yaml ]] || [[ "$file" == *.yml ]]; then
        # Check for dimension configuration
        if grep -q "dim\|dimension" "$file" 2>/dev/null; then
            local dim=$(grep -E "dim.*:.*[0-9]+" "$file" | grep -oE "[0-9]+" | head -1)
            
            if [ ! -z "$dim" ] && [ "$dim" != "$EXPECTED_DIM" ]; then
                should_archive=true
                reasons+=("incorrect dimensions: $dim (expected $EXPECTED_DIM)")
            fi
        fi
        
        # Check for distance metric
        if grep -q "distance\|metric" "$file" 2>/dev/null; then
            local distance=$(grep -E "distance.*:" "$file" | sed 's/.*distance.*: *//' | tr -d '"' | tr -d "'" | head -1)
            
            if [ ! -z "$distance" ] && [ "${distance,,}" != "${EXPECTED_DISTANCE,,}" ]; then
                should_archive=true
                reasons+=("incorrect distance: $distance (expected $EXPECTED_DISTANCE)")
            fi
        fi
        
        # Check for deprecated configurations
        if grep -q "deprecated\|obsolete\|old_" "$file" 2>/dev/null; then
            should_archive=true
            reasons+=("contains deprecated configuration")
        fi
        
        # Check for test/example configurations that shouldn't be in production
        if [[ "$file" == *test* ]] || [[ "$file" == *example* ]] || [[ "$file" == *sample* ]]; then
            if [[ "$file" != *keep* ]]; then  # Unless explicitly marked to keep
                should_archive=true
                reasons+=("test/example configuration")
            fi
        fi
    fi
    
    # Handle the file
    if [ "$should_archive" = true ]; then
        ((ARCHIVED_COUNT++))
        
        if [ "$VERBOSE" = true ] || [ "$DRY_RUN" = true ]; then
            warning "Archive: $file"
            for reason in "${reasons[@]}"; do
                echo "         Reason: $reason"
            done
        fi
        
        if [ "$DRY_RUN" = false ]; then
            # Create subdirectory structure in archive
            local dir=$(dirname "$file")
            mkdir -p "$ARCHIVE_DIR/$dir"
            
            # Move file with timestamp
            local basename=$(basename "$file")
            local archived_name="${basename%.yaml}_$(date +%H%M%S).yaml"
            mv "$file" "$ARCHIVE_DIR/$dir/$archived_name"
            
            # Create a manifest record
            echo "$(date -Iseconds): Archived $file -> $ARCHIVE_DIR/$dir/$archived_name" >> "$ARCHIVE_DIR/manifest.log"
            echo "  Reasons: ${reasons[*]}" >> "$ARCHIVE_DIR/manifest.log"
        fi
    else
        ((VALID_COUNT++))
        
        if [ "$VERBOSE" = true ]; then
            status "Valid: $file"
        fi
    fi
}

# Scan directories for manifests
echo "Scanning for manifests..."
echo ""

for dir in "${MANIFEST_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        info "Checking directory: $dir"
        
        # Find all YAML files
        while IFS= read -r -d '' file; do
            check_manifest "$file"
        done < <(find "$dir" -name "*.yaml" -o -name "*.yml" -print0 2>/dev/null)
    else
        if [ "$VERBOSE" = true ]; then
            info "Directory not found: $dir (skipping)"
        fi
    fi
done

# Also check root directory configs
for file in *.yaml *.yml; do
    if [ -f "$file" ]; then
        check_manifest "$file"
    fi
done 2>/dev/null

echo ""
echo "========================================="
echo "Manifest Hygiene Summary"
echo "========================================="
echo ""
echo "Total manifests checked: $TOTAL_COUNT"
echo "Valid manifests: $VALID_COUNT"
echo "Manifests to archive: $ARCHIVED_COUNT"

if [ "$ARCHIVED_COUNT" -gt 0 ]; then
    echo ""
    if [ "$DRY_RUN" = true ]; then
        warning "Run without --dry-run to archive $ARCHIVED_COUNT manifest(s)"
    else
        status "Archived $ARCHIVED_COUNT manifest(s) to $ARCHIVE_DIR"
        echo ""
        echo "Archive log: $ARCHIVE_DIR/manifest.log"
    fi
fi

# Create current state report
if [ "$DRY_RUN" = false ] && [ "$TOTAL_COUNT" -gt 0 ]; then
    REPORT_FILE="manifests/current_state_$(date +%Y%m%d).json"
    
    cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "expected_config": {
    "dimensions": $EXPECTED_DIM,
    "distance": "$EXPECTED_DISTANCE"
  },
  "summary": {
    "total_checked": $TOTAL_COUNT,
    "valid": $VALID_COUNT,
    "archived": $ARCHIVED_COUNT
  },
  "archive_location": "$ARCHIVE_DIR"
}
EOF
    
    echo ""
    status "Current state report: $REPORT_FILE"
fi

echo ""

# Exit with error if invalid manifests remain in dry-run
if [ "$DRY_RUN" = true ] && [ "$ARCHIVED_COUNT" -gt 0 ]; then
    exit 1
fi

exit 0