#!/bin/bash
# Script to apply metadata retrieval fix

set -e

echo "=================================================="
echo "        APPLYING METADATA RETRIEVAL FIX"
echo "=================================================="
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}This fix ensures metadata fields (like golden_fact) are returned${NC}"
echo -e "${YELLOW}separately in retrieve_context responses, fixing S2 checks.${NC}"
echo

# Restart the context-store service to apply changes
echo "Restarting context-store service with updated code..."
docker-compose restart context-store

echo

# Implement proper health check with retries
MAX_RETRIES=30
RETRY_DELAY=2
RETRY_COUNT=0

echo "Checking service health (max ${MAX_RETRIES} attempts)..."
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "healthy"; then
        echo -e "${GREEN}✓ Service is healthy after $((RETRY_COUNT * RETRY_DELAY)) seconds${NC}"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "  Attempt $RETRY_COUNT/$MAX_RETRIES - Service not ready, waiting ${RETRY_DELAY}s..."
        sleep $RETRY_DELAY
    else
        echo -e "${YELLOW}⚠️ Service health check timed out after $((MAX_RETRIES * RETRY_DELAY)) seconds${NC}"
        echo "  Service may still be starting. Check logs with: docker-compose logs context-store"
    fi
done

echo
echo "=================================================="
echo "          FIX APPLIED - READY TO TEST"
echo "=================================================="
echo
echo "To test the fix:"
echo "1. Run: python3 /claude-workspace/test_metadata_fix.py"
echo "2. Or run Phase 3 verification: python3 /claude-workspace/phase3_verify.py"
echo
echo "Expected outcome:"
echo "- Metadata fields will be returned separately in responses"
echo "- S2 golden fact recall checks should pass"
