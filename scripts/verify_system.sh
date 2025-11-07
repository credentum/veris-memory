#!/bin/bash

# Phase 3: Complete System Verification
# Run this after Phase 2 to verify the entire system is working

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}         PHASE 3: SYSTEM INTEGRATION VERIFICATION          ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo

# Get API key from environment
if [ -z "$API_KEY_MCP" ]; then
    echo -e "${RED}ERROR: API_KEY_MCP environment variable not set${NC}"
    echo "Please set: export API_KEY_MCP=<your-key-from-env-file>"
    exit 1
fi

# Configuration
CONTEXT_STORE_URL="${CONTEXT_STORE_URL:-http://localhost:8000}"
API_URL="${API_URL:-http://localhost:8001}"
MONITORING_URL="${MONITORING_URL:-http://localhost:8080}"
SENTINEL_URL="${SENTINEL_URL:-http://localhost:9090}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
NEO4J_URL="${NEO4J_URL:-http://localhost:7474}"
REDIS_PORT="${REDIS_PORT:-6379}"

TOTAL_CHECKS=0
PASSED_CHECKS=0

# Helper function to run a check
run_check() {
    local description="$1"
    local command="$2"

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    if eval "$command" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $description"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} $description"
        return 1
    fi
}

# Helper function for detailed check
detailed_check() {
    local description="$1"
    local command="$2"
    local expected="$3"

    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    result=$(eval "$command" 2>/dev/null || echo "ERROR")

    if [[ "$result" == *"$expected"* ]]; then
        echo -e "  ${GREEN}✓${NC} $description: $result"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} $description: $result (expected: $expected)"
        return 1
    fi
}

echo -e "${BLUE}1. SERVICE CONNECTIVITY${NC}"
echo "─────────────────────────────"

run_check "Context Store (8000)" "nc -z localhost 8000"
run_check "API Service (8001)" "nc -z localhost 8001"
run_check "Monitoring Dashboard (8080)" "nc -z localhost 8080"
run_check "Sentinel (9090)" "nc -z localhost 9090"
run_check "Qdrant (6333)" "nc -z localhost 6333"
run_check "Neo4j (7474)" "nc -z localhost 7474"
run_check "Redis (6379)" "nc -z localhost 6379"

echo
echo -e "${BLUE}2. SERVICE HEALTH CHECKS${NC}"
echo "─────────────────────────────"

# Context Store health
health_status=$(curl -s "$CONTEXT_STORE_URL/health" | jq -r '.status // "unknown"' 2>/dev/null || echo "error")
if [[ "$health_status" == "healthy" ]]; then
    echo -e "  ${GREEN}✓${NC} Context Store: $health_status"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "  ${RED}✗${NC} Context Store: $health_status"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

# API health
api_health=$(curl -s "$API_URL/api/v1/health/live" | jq -r '.status // "unknown"' 2>/dev/null || echo "error")
if [[ "$api_health" == "healthy" ]]; then
    echo -e "  ${GREEN}✓${NC} API Service: $api_health"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "  ${RED}✗${NC} API Service: $api_health"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

# Sentinel health
sentinel_health=$(curl -s "$SENTINEL_URL/health" | jq -r '.status // "unknown"' 2>/dev/null || echo "error")
if [[ "$sentinel_health" == "healthy" ]]; then
    echo -e "  ${GREEN}✓${NC} Sentinel: $sentinel_health"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "  ${RED}✗${NC} Sentinel: $sentinel_health"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo
echo -e "${BLUE}3. AUTHENTICATION TESTS${NC}"
echo "─────────────────────────────"

# Test with API key
response_with_key=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$CONTEXT_STORE_URL/tools/retrieve_context" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY_MCP" \
    -d '{"query":"test","limit":1}' 2>/dev/null)

if [[ "$response_with_key" == "200" ]]; then
    echo -e "  ${GREEN}✓${NC} API authentication working (HTTP 200)"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "  ${RED}✗${NC} API authentication failed (HTTP $response_with_key)"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

# Test without API key (should fail)
response_without_key=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$CONTEXT_STORE_URL/tools/retrieve_context" \
    -H "Content-Type: application/json" \
    -d '{"query":"test","limit":1}' 2>/dev/null)

if [[ "$response_without_key" == "401" ]]; then
    echo -e "  ${GREEN}✓${NC} Authentication enforcement working (HTTP 401 without key)"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "  ${YELLOW}⚠${NC}  Authentication not enforced (HTTP $response_without_key without key)"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo
echo -e "${BLUE}4. DATA PRESENCE CHECKS${NC}"
echo "─────────────────────────────"

# Qdrant vectors
qdrant_count=$(curl -s "$QDRANT_URL/collections/contexts/points/count" 2>/dev/null | jq -r '.result.count // 0' || echo "0")
echo -e "  Qdrant vectors: ${YELLOW}$qdrant_count${NC}"
if [[ "$qdrant_count" -gt 0 ]]; then
    echo -e "    ${GREEN}✓${NC} Vector storage operational"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "    ${YELLOW}⚠${NC} No vectors (embeddings may be disabled)"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

# Neo4j nodes (if password is set)
if [ -n "$NEO4J_PASSWORD" ]; then
    neo4j_count=$(docker exec veris-memory_neo4j_1 cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
        "MATCH (n) RETURN count(n) as count" 2>/dev/null | grep -o '[0-9]*' | tail -1 || echo "0")
    echo -e "  Neo4j nodes: ${YELLOW}$neo4j_count${NC}"
    if [[ "$neo4j_count" -gt 0 ]]; then
        echo -e "    ${GREEN}✓${NC} Graph storage operational"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "    ${RED}✗${NC} No graph data"
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
else
    echo -e "  Neo4j: ${YELLOW}⚠${NC}  Cannot check (NEO4J_PASSWORD not set)"
fi

# Redis keys
redis_count=$(docker exec veris-memory_redis_1 redis-cli DBSIZE 2>/dev/null | grep -o '[0-9]*' || echo "0")
echo -e "  Redis keys: ${YELLOW}$redis_count${NC}"
if [[ "$redis_count" -gt 0 ]]; then
    echo -e "    ${GREEN}✓${NC} Cache operational"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "    ${YELLOW}⚠${NC} Cache empty (may be normal)"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))  # Don't fail for empty Redis
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo
echo -e "${BLUE}5. FUNCTIONAL TESTS${NC}"
echo "─────────────────────────────"

# Store a test context
store_response=$(curl -s -X POST "$CONTEXT_STORE_URL/tools/store_context" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY_MCP" \
    -d '{
        "type": "log",
        "content": {"title": "Phase 3 Test", "message": "Verification test"},
        "author": "verify_script",
        "author_type": "agent"
    }' 2>/dev/null)

store_success=$(echo "$store_response" | jq -r '.success // false' 2>/dev/null || echo "false")
if [[ "$store_success" == "true" ]]; then
    echo -e "  ${GREEN}✓${NC} Store context: Success"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))

    # Check embedding status
    embedding_status=$(echo "$store_response" | jq -r '.embedding_status // "unknown"' 2>/dev/null)
    if [[ "$embedding_status" == "completed" ]]; then
        echo -e "    ${GREEN}✓${NC} Embeddings: Working"
    else
        echo -e "    ${YELLOW}⚠${NC} Embeddings: $embedding_status"
    fi
else
    echo -e "  ${RED}✗${NC} Store context: Failed"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

# Retrieve contexts
retrieve_response=$(curl -s -X POST "$CONTEXT_STORE_URL/tools/retrieve_context" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY_MCP" \
    -d '{"query": "Phase 3 Test", "limit": 5}' 2>/dev/null)

retrieve_count=$(echo "$retrieve_response" | jq -r '.total_count // 0' 2>/dev/null || echo "0")
if [[ "$retrieve_count" -gt 0 ]]; then
    echo -e "  ${GREEN}✓${NC} Retrieve context: Found $retrieve_count results"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))

    # Check search mode
    search_mode=$(echo "$retrieve_response" | jq -r '.search_mode_used // "unknown"' 2>/dev/null)
    echo -e "    Search mode: ${YELLOW}$search_mode${NC}"
else
    echo -e "  ${RED}✗${NC} Retrieve context: No results"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo
echo -e "${BLUE}6. SENTINEL S2 CHECK${NC}"
echo "─────────────────────────────"

# Run S2 check if possible
if command -v docker &> /dev/null; then
    s2_output=$(docker exec veris-memory_sentinel_1 python -c "
import asyncio
from src.monitoring.sentinel.checks.s2_golden_fact_recall import GoldenFactRecall
from src.monitoring.sentinel.models import SentinelConfig

async def test():
    config = SentinelConfig()
    check = GoldenFactRecall(config)
    result = await check.run_check()
    print(f'{result.status}|{result.message}')

asyncio.run(test())
" 2>/dev/null || echo "error|Failed to run")

    s2_status=$(echo "$s2_output" | cut -d'|' -f1)
    s2_message=$(echo "$s2_output" | cut -d'|' -f2)

    if [[ "$s2_status" == "pass" ]]; then
        echo -e "  ${GREEN}✓${NC} S2 Golden Fact Recall: PASS"
        echo -e "    ${s2_message}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    elif [[ "$s2_status" == "warn" ]]; then
        echo -e "  ${YELLOW}⚠${NC} S2 Golden Fact Recall: WARN"
        echo -e "    ${s2_message}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "  ${RED}✗${NC} S2 Golden Fact Recall: FAIL"
        echo -e "    ${s2_message}"
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
else
    echo -e "  ${YELLOW}⚠${NC} Cannot run S2 check (docker not available)"
fi

echo
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}                    VERIFICATION SUMMARY                    ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo

# Calculate percentage
if [[ $TOTAL_CHECKS -gt 0 ]]; then
    PERCENTAGE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
else
    PERCENTAGE=0
fi

# Determine overall status
if [[ $PERCENTAGE -ge 90 ]]; then
    echo -e "${GREEN}✅ SYSTEM FULLY OPERATIONAL${NC}"
    echo -e "   Passed: $PASSED_CHECKS/$TOTAL_CHECKS checks ($PERCENTAGE%)"
    exit_code=0
elif [[ $PERCENTAGE -ge 70 ]]; then
    echo -e "${YELLOW}⚠️  SYSTEM PARTIALLY OPERATIONAL${NC}"
    echo -e "   Passed: $PASSED_CHECKS/$TOTAL_CHECKS checks ($PERCENTAGE%)"
    echo -e "   Some features may be degraded"
    exit_code=0
else
    echo -e "${RED}❌ SYSTEM NOT OPERATIONAL${NC}"
    echo -e "   Passed: $PASSED_CHECKS/$TOTAL_CHECKS checks ($PERCENTAGE%)"
    echo -e "   Critical issues detected"
    exit_code=1
fi

echo
echo "Next steps:"
if [[ $PERCENTAGE -eq 100 ]]; then
    echo "  ✓ System is ready for production use"
else
    echo "  - Review failed checks above"
    echo "  - Check service logs: docker-compose logs [service-name]"
    echo "  - Ensure Phase 1 (PR #168) is deployed"
    echo "  - Verify Phase 2 initialization completed successfully"
fi

exit $exit_code