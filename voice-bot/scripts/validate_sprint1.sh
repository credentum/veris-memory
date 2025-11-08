#!/bin/bash
# Sprint 1 Validation Script for Voice Bot Service
# Tests all Sprint 1 deliverables:
# 1. Voice-bot service deploys successfully
# 2. Facts persist across container restarts
# 3. No hallucinations on unknown facts
# 4. Latency <500ms for fact retrieval

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
VOICE_BOT_URL="${VOICE_BOT_URL:-http://localhost:8002}"
TEST_USER_ID="validation_test_$(date +%s)"
LATENCY_THRESHOLD_MS=500
CONTAINER_NAME="voice-bot"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_test() {
    echo -e "${YELLOW}TEST: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ PASS: $1${NC}"
    ((TESTS_PASSED++))
}

print_failure() {
    echo -e "${RED}✗ FAIL: $1${NC}"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${BLUE}INFO: $1${NC}"
}

# Measure request latency in milliseconds
measure_latency() {
    local url="$1"
    local method="${2:-GET}"
    local data="${3:-}"

    if [ "$method" = "POST" ]; then
        local start=$(date +%s%3N)
        if [ -n "$data" ]; then
            curl -s -X POST "$url" -H "Content-Type: application/json" -d "$data" > /dev/null
        else
            curl -s -X POST "$url" > /dev/null
        fi
        local end=$(date +%s%3N)
    else
        local start=$(date +%s%3N)
        curl -s "$url" > /dev/null
        local end=$(date +%s%3N)
    fi

    echo $((end - start))
}

# Check if service is running
check_service_running() {
    print_test "Service is running and responding"

    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        print_failure "Voice-bot container is not running"
        return 1
    fi

    local response=$(curl -s -o /dev/null -w "%{http_code}" "$VOICE_BOT_URL/")
    if [ "$response" = "200" ]; then
        print_success "Service is running and responding (HTTP $response)"
        return 0
    else
        print_failure "Service returned HTTP $response"
        return 1
    fi
}

# Test 1: Service Deployment
test_deployment() {
    print_header "Test 1: Service Deployment"

    # Check if container is running
    if ! check_service_running; then
        return 1
    fi

    # Check health endpoint
    print_test "Health endpoint returns healthy status"
    local health_response=$(curl -s "$VOICE_BOT_URL/health")
    local status=$(echo "$health_response" | jq -r '.status' 2>/dev/null || echo "error")

    if [ "$status" = "healthy" ]; then
        print_success "Health endpoint shows healthy status"
    else
        print_failure "Health endpoint shows status: $status"
        echo "Response: $health_response"
    fi

    # Check MCP server connectivity
    print_test "MCP server is connected"
    local mcp_connected=$(echo "$health_response" | jq -r '.checks.mcp_server' 2>/dev/null || echo "false")

    if [ "$mcp_connected" = "true" ]; then
        print_success "MCP server is connected"
    else
        print_failure "MCP server is not connected"
    fi

    # Check LiveKit connectivity
    print_test "LiveKit server is connected"
    local livekit_connected=$(echo "$health_response" | jq -r '.checks.livekit' 2>/dev/null || echo "false")

    if [ "$livekit_connected" = "true" ]; then
        print_success "LiveKit server is connected"
    else
        print_failure "LiveKit server is not connected"
    fi
}

# Test 2: Fact Storage and Persistence
test_fact_persistence() {
    print_header "Test 2: Fact Persistence Across Restarts"

    # Store a fact
    print_test "Storing test fact: name=Alice"
    local store_response=$(curl -s -X POST "$VOICE_BOT_URL/api/v1/facts/store?user_id=$TEST_USER_ID&key=name&value=Alice")
    local store_status=$(echo "$store_response" | jq -r '.status' 2>/dev/null || echo "error")

    if [ "$store_status" = "success" ]; then
        print_success "Fact stored successfully"
    else
        print_failure "Failed to store fact"
        echo "Response: $store_response"
        return 1
    fi

    # Retrieve the fact
    print_test "Retrieving stored fact"
    local retrieve_response=$(curl -s "$VOICE_BOT_URL/api/v1/facts/$TEST_USER_ID?keys=name")
    local retrieved_name=$(echo "$retrieve_response" | jq -r '.facts.name' 2>/dev/null || echo "null")

    if [ "$retrieved_name" = "Alice" ]; then
        print_success "Fact retrieved successfully before restart"
    else
        print_failure "Failed to retrieve fact before restart (got: $retrieved_name)"
        return 1
    fi

    # Restart the container
    print_info "Restarting voice-bot container..."
    docker restart "$CONTAINER_NAME" > /dev/null 2>&1

    # Wait for service to be healthy
    print_info "Waiting for service to be healthy after restart..."
    local max_wait=60
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -s -f "$VOICE_BOT_URL/health" > /dev/null 2>&1; then
            break
        fi
        sleep 2
        waited=$((waited + 2))
    done

    if [ $waited -ge $max_wait ]; then
        print_failure "Service did not become healthy after restart"
        return 1
    fi

    print_info "Service is healthy after restart"

    # Retrieve the fact again
    print_test "Retrieving fact after restart"
    local retrieve_after_response=$(curl -s "$VOICE_BOT_URL/api/v1/facts/$TEST_USER_ID?keys=name")
    local retrieved_after_name=$(echo "$retrieve_after_response" | jq -r '.facts.name' 2>/dev/null || echo "null")

    if [ "$retrieved_after_name" = "Alice" ]; then
        print_success "Fact persisted across container restart"
    else
        print_failure "Fact did not persist (got: $retrieved_after_name)"
        return 1
    fi
}

# Test 3: No Hallucinations
test_no_hallucinations() {
    print_header "Test 3: No Hallucinations on Unknown Facts"

    # Query a fact that doesn't exist
    local unknown_user="unknown_user_$(date +%s)"
    print_test "Querying fact for unknown user"
    local response=$(curl -s "$VOICE_BOT_URL/api/v1/facts/$unknown_user?keys=favorite_color")
    local fact_count=$(echo "$response" | jq -r '.count' 2>/dev/null || echo "error")

    if [ "$fact_count" = "0" ]; then
        print_success "No hallucinations - returned 0 facts for unknown user"
    else
        print_failure "Hallucination detected - returned $fact_count facts for unknown user"
        echo "Response: $response"
    fi

    # Query a specific fact that doesn't exist for known user
    print_test "Querying non-existent fact for known user"
    local response2=$(curl -s "$VOICE_BOT_URL/api/v1/facts/$TEST_USER_ID?keys=nonexistent_key")
    local facts=$(echo "$response2" | jq -r '.facts' 2>/dev/null || echo "{}")

    # Should return empty object or not have the key
    if [ "$facts" = "{}" ] || ! echo "$facts" | jq -e '.nonexistent_key' > /dev/null 2>&1; then
        print_success "No hallucinations - non-existent fact not returned"
    else
        print_failure "Hallucination detected - returned value for non-existent fact"
        echo "Response: $response2"
    fi
}

# Test 4: Latency Requirements
test_latency() {
    print_header "Test 4: Latency Requirements (<${LATENCY_THRESHOLD_MS}ms)"

    # Test health endpoint latency
    print_test "Health endpoint latency"
    local health_latency=$(measure_latency "$VOICE_BOT_URL/health")
    print_info "Health endpoint latency: ${health_latency}ms"

    if [ "$health_latency" -lt "$LATENCY_THRESHOLD_MS" ]; then
        print_success "Health endpoint latency within threshold (${health_latency}ms < ${LATENCY_THRESHOLD_MS}ms)"
    else
        print_failure "Health endpoint latency exceeded threshold (${health_latency}ms >= ${LATENCY_THRESHOLD_MS}ms)"
    fi

    # Test fact retrieval latency
    print_test "Fact retrieval latency"
    local fact_latency=$(measure_latency "$VOICE_BOT_URL/api/v1/facts/$TEST_USER_ID?keys=name")
    print_info "Fact retrieval latency: ${fact_latency}ms"

    if [ "$fact_latency" -lt "$LATENCY_THRESHOLD_MS" ]; then
        print_success "Fact retrieval latency within threshold (${fact_latency}ms < ${LATENCY_THRESHOLD_MS}ms)"
    else
        print_failure "Fact retrieval latency exceeded threshold (${fact_latency}ms >= ${LATENCY_THRESHOLD_MS}ms)"
    fi

    # Test echo endpoint latency
    print_test "Echo test endpoint latency"
    local echo_latency=$(measure_latency "$VOICE_BOT_URL/api/v1/voice/echo-test?user_id=$TEST_USER_ID&message=test" "POST")
    print_info "Echo test latency: ${echo_latency}ms"

    if [ "$echo_latency" -lt "$LATENCY_THRESHOLD_MS" ]; then
        print_success "Echo test latency within threshold (${echo_latency}ms < ${LATENCY_THRESHOLD_MS}ms)"
    else
        print_failure "Echo test latency exceeded threshold (${echo_latency}ms >= ${LATENCY_THRESHOLD_MS}ms)"
    fi
}

# Test 5: Sprint 13 Integration
test_sprint13_integration() {
    print_header "Test 5: Sprint 13 Integration Features"

    # Check detailed health endpoint (Sprint 13)
    print_test "Detailed health endpoint with embedding status"
    local detailed_health=$(curl -s "$VOICE_BOT_URL/health/detailed")
    local embedding_pipeline=$(echo "$detailed_health" | jq -r '.mcp_server.embedding_pipeline' 2>/dev/null || echo "null")

    if [ "$embedding_pipeline" != "null" ]; then
        print_success "Detailed health endpoint returns embedding pipeline status"
        print_info "Embedding status: $embedding_pipeline"
    else
        print_failure "Detailed health endpoint missing embedding pipeline status"
    fi

    # Test echo endpoint with Sprint 13 features
    print_test "Echo test with author attribution"
    local echo_response=$(curl -s -X POST "$VOICE_BOT_URL/api/v1/voice/echo-test?user_id=$TEST_USER_ID&message=Sprint13Test")
    local echo_success=$(echo "$echo_response" | jq -r '.user_id' 2>/dev/null || echo "null")

    if [ "$echo_success" = "$TEST_USER_ID" ]; then
        print_success "Echo test with Sprint 13 features working"
    else
        print_failure "Echo test failed"
        echo "Response: $echo_response"
    fi
}

# Main execution
main() {
    print_header "Voice Bot Sprint 1 Validation"
    print_info "Testing voice-bot service at: $VOICE_BOT_URL"
    print_info "Test user ID: $TEST_USER_ID"
    print_info "Latency threshold: ${LATENCY_THRESHOLD_MS}ms"
    echo ""

    # Check prerequisites
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}ERROR: jq is required but not installed${NC}"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}ERROR: docker is required but not installed${NC}"
        exit 1
    fi

    if ! command -v curl &> /dev/null; then
        echo -e "${RED}ERROR: curl is required but not installed${NC}"
        exit 1
    fi

    # Run tests
    test_deployment
    test_fact_persistence
    test_no_hallucinations
    test_latency
    test_sprint13_integration

    # Print summary
    print_header "Validation Summary"
    echo "Tests Passed: $TESTS_PASSED"
    echo "Tests Failed: $TESTS_FAILED"
    echo ""

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}✓ ALL TESTS PASSED - Sprint 1 deliverables validated!${NC}"
        exit 0
    else
        echo -e "${RED}✗ SOME TESTS FAILED - Review failures above${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
