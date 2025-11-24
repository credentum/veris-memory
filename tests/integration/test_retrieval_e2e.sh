#!/bin/bash
set -e

API_URL="${API_URL:-http://172.17.0.1:8000}"
API_KEY="${API_KEY_MCP:-}"

# Validate API key is set
if [ -z "$API_KEY" ]; then
  echo "ERROR: API_KEY_MCP environment variable is not set"
  echo "Please set it before running this test:"
  echo "  export API_KEY_MCP=your_api_key"
  exit 1
fi

echo "=========================================="
echo "Integration Test: Retrieval Fix"
echo "=========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Store and retrieve manual context
echo "Test 1: Manual context retrieval..."
echo "-----------------------------------"

STORE_RESULT=$(curl -s -X POST $API_URL/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "type": "decision",
    "content": {
      "title": "Integration Test Banana Protocol",
      "description": "Testing banana retrieval after field fix",
      "keyword": "banana_integration_test"
    },
    "author": "test_agent",
    "author_type": "agent"
  }')

CONTEXT_ID=$(echo $STORE_RESULT | python3 -m json.tool 2>/dev/null | grep '"id"' | head -1 | cut -d'"' -f4)
echo "Stored context with ID: $CONTEXT_ID"

# Wait for indexing
echo "Waiting 2 seconds for indexing..."
sleep 2

RETRIEVE_RESULT=$(curl -s -X POST $API_URL/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "banana", "limit": 5}')

NUM_RESULTS=$(echo $RETRIEVE_RESULT | python3 -m json.tool 2>/dev/null | grep '"total_count"' | grep -o '[0-9]*')
echo "Retrieved $NUM_RESULTS results for query 'banana'"

if [ "$NUM_RESULTS" -eq 0 ] || [ -z "$NUM_RESULTS" ]; then
  echo -e "${RED}FAIL: No results returned${NC}"
  echo "Response: $RETRIEVE_RESULT"
  exit 1
fi

echo -e "${GREEN}PASS: Manual context retrieval works${NC}"
echo ""

# Test 2: Store and retrieve voice bot context
echo "Test 2: Voice bot context retrieval..."
echo "---------------------------------------"

STORE_RESULT=$(curl -s -X POST $API_URL/tools/store_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "type": "trace",
    "content": {
      "user_input": "Integration test sunshine message",
      "bot_response": "Integration test happiness response",
      "title": "Voice Test Conversation"
    },
    "author": "voice_bot",
    "author_type": "agent"
  }')

CONTEXT_ID=$(echo $STORE_RESULT | python3 -m json.tool 2>/dev/null | grep '"id"' | head -1 | cut -d'"' -f4)
echo "Stored voice context with ID: $CONTEXT_ID"

# Wait for indexing
sleep 2

RETRIEVE_RESULT=$(curl -s -X POST $API_URL/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "sunshine", "limit": 5}')

NUM_RESULTS=$(echo $RETRIEVE_RESULT | python3 -m json.tool 2>/dev/null | grep '"total_count"' | grep -o '[0-9]*')
echo "Retrieved $NUM_RESULTS results for query 'sunshine'"

if [ "$NUM_RESULTS" -eq 0 ] || [ -z "$NUM_RESULTS" ]; then
  echo -e "${RED}FAIL: No voice bot results returned${NC}"
  echo "Response: $RETRIEVE_RESULT"
  exit 1
fi

echo -e "${GREEN}PASS: Voice bot context retrieval works${NC}"
echo ""

# Test 3: Check backend timings are non-zero
echo "Test 3: Backend timings validation..."
echo "--------------------------------------"

BACKEND_TIMINGS=$(echo $RETRIEVE_RESULT | python3 -m json.tool 2>/dev/null | grep -A 5 '"backend_timings"')
echo "Backend timings: $BACKEND_TIMINGS"

# Check if any backend timing is greater than 0
GRAPH_TIMING=$(echo $RETRIEVE_RESULT | python3 -m json.tool 2>/dev/null | grep '"graph"' | grep -o '[0-9.]*' | head -1)
VECTOR_TIMING=$(echo $RETRIEVE_RESULT | python3 -m json.tool 2>/dev/null | grep '"vector"' | grep -o '[0-9.]*' | head -1)

echo "Graph backend: ${GRAPH_TIMING}ms"
echo "Vector backend: ${VECTOR_TIMING}ms"

if [ -z "$GRAPH_TIMING" ]; then
  GRAPH_TIMING="0.0"
fi

# Check if graph timing is greater than 0 (using bc for float comparison)
if [ $(echo "$GRAPH_TIMING > 0.0" | bc -l) -eq 0 ]; then
  echo -e "${RED}FAIL: Graph backend timing is 0.0${NC}"
  exit 1
fi

echo -e "${GREEN}PASS: Backend timings are non-zero${NC}"
echo ""

# Test 4: Verify existing contexts are searchable
echo "Test 4: Existing context retrieval..."
echo "--------------------------------------"

# Search for existing voice bot contexts (we know there are some with "sunshine")
RETRIEVE_RESULT=$(curl -s -X POST $API_URL/tools/retrieve_context \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query": "You are my sunshine", "limit": 10}')

NUM_RESULTS=$(echo $RETRIEVE_RESULT | python3 -m json.tool 2>/dev/null | grep '"total_count"' | grep -o '[0-9]*')
echo "Found $NUM_RESULTS existing contexts matching 'You are my sunshine'"

if [ "$NUM_RESULTS" -eq 0 ] || [ -z "$NUM_RESULTS" ]; then
  echo -e "${YELLOW}WARNING: No existing contexts found (may be expected if database was cleared)${NC}"
else
  echo -e "${GREEN}PASS: Existing contexts are searchable${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}All Critical Tests Passed!${NC}"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Manual context storage and retrieval"
echo "  ✓ Voice bot context storage and retrieval"
echo "  ✓ Backend timings are working"
echo "  ✓ Retrieval system is functional"
echo ""
