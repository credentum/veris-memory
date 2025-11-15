#!/bin/bash
# Backup Retention Cleanup Script
#
# Removes backup files older than the retention period to comply with
# S6 backup retention policy validation.
#
# Usage:
#   ./backup-retention-cleanup.sh [--retention-days DAYS] [--dry-run]
#
# Options:
#   --retention-days DAYS    Number of days to retain backups (default: 14)
#   --dry-run                Show what would be deleted without actually deleting
#   --help                   Show this help message

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
RETENTION_DAYS=14
DRY_RUN=false

# Backup directories to clean (matching S6 check configuration)
BACKUP_PATHS=(
    "/backup/health"
    "/backup/daily"
    "/backup/weekly"
    "/backup/monthly"
    "/backup/backup-weekly"
    "/backup/backup-monthly"
    "/backup/backup-ultimate"
)

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            grep "^#" "$0" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}📦 Backup Retention Cleanup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Retention period: ${RETENTION_DAYS} days"
echo "Dry run mode: ${DRY_RUN}"
echo ""

# Counters
TOTAL_FILES_FOUND=0
TOTAL_FILES_DELETED=0
TOTAL_SIZE_FREED=0

# Process each backup directory
for BACKUP_PATH in "${BACKUP_PATHS[@]}"; do
    if [ ! -d "$BACKUP_PATH" ]; then
        echo -e "${YELLOW}⚠️  Directory not found: ${BACKUP_PATH}${NC}"
        continue
    fi

    echo -e "${BLUE}📁 Processing: ${BACKUP_PATH}${NC}"

    # Find old backup files (.sql, .dump, .tar.gz)
    # Using -mtime +N finds files modified more than N days ago
    OLD_FILES=$(find "$BACKUP_PATH" \
        -type f \
        \( -name "*.sql" -o -name "*.dump" -o -name "*.tar.gz" \) \
        -mtime +${RETENTION_DAYS} \
        2>/dev/null || true)

    if [ -z "$OLD_FILES" ]; then
        echo -e "  ${GREEN}✓${NC} No old files to clean"
        continue
    fi

    # Process each old file
    while IFS= read -r file; do
        if [ -z "$file" ]; then
            continue
        fi

        TOTAL_FILES_FOUND=$((TOTAL_FILES_FOUND + 1))

        # Get file info
        FILE_SIZE=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0)
        FILE_SIZE_MB=$(echo "scale=2; $FILE_SIZE / 1024 / 1024" | bc)
        FILE_AGE_DAYS=$(( ($(date +%s) - $(stat -f%m "$file" 2>/dev/null || stat -c%Y "$file" 2>/dev/null)) / 86400 ))

        if [ "$DRY_RUN" = true ]; then
            echo -e "  ${YELLOW}[DRY RUN]${NC} Would delete: $(basename "$file") (${FILE_SIZE_MB}MB, ${FILE_AGE_DAYS} days old)"
        else
            echo -e "  ${RED}🗑${NC}  Deleting: $(basename "$file") (${FILE_SIZE_MB}MB, ${FILE_AGE_DAYS} days old)"
            rm -f "$file"
            TOTAL_FILES_DELETED=$((TOTAL_FILES_DELETED + 1))
            TOTAL_SIZE_FREED=$((TOTAL_SIZE_FREED + FILE_SIZE))
        fi
    done <<< "$OLD_FILES"

    echo ""
done

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Total old files found: ${TOTAL_FILES_FOUND}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}Files to be deleted: ${TOTAL_FILES_FOUND}${NC}"
    echo "Run without --dry-run to actually delete files"
else
    echo -e "${GREEN}Files deleted: ${TOTAL_FILES_DELETED}${NC}"
    TOTAL_SIZE_FREED_MB=$(echo "scale=2; $TOTAL_SIZE_FREED / 1024 / 1024" | bc)
    echo -e "${GREEN}Space freed: ${TOTAL_SIZE_FREED_MB} MB${NC}"
fi

echo ""

# Exit codes
if [ "$TOTAL_FILES_FOUND" -eq 0 ]; then
    echo -e "${GREEN}✅ No retention policy violations found${NC}"
    exit 0
elif [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  Retention policy violations found (dry run mode)${NC}"
    exit 0
else
    echo -e "${GREEN}✅ Backup retention cleanup completed${NC}"
    exit 0
fi
