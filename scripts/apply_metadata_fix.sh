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
echo "Waiting for service to be ready..."
sleep 10

# Test the service is up
echo "Testing service health..."
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}✓ Service is healthy${NC}"
else
    echo "⚠️ Service may not be ready yet"
fi

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