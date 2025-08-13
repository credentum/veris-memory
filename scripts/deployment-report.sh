#!/bin/bash
# Generate deployment report in JSON format for agent consumption

set -euo pipefail

# Colors for terminal output (won't affect JSON)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Environment from argument or default to dev
ENVIRONMENT="${1:-dev}"
REPORT_FILE="/tmp/deployment-report-${ENVIRONMENT}.json"

# Initialize report structure
cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environment": "$ENVIRONMENT",
  "deployment_id": "$(uuidgen 2>/dev/null || echo "deploy-$(date +%s)")",
  "server": {
    "hostname": "$(hostname)",
    "ip": "$(hostname -I | awk '{print $1}')",
    "kernel": "$(uname -r)",
    "memory_total_mb": $(free -m | awk '/^Mem:/ {print $2}'),
    "memory_available_mb": $(free -m | awk '/^Mem:/ {print $7}'),
    "disk_usage_percent": $(df /opt/veris-memory 2>/dev/null | awk 'NR==2 {print int($5)}' || echo 0)
  },
  "services": {},
  "health_checks": {},
  "smoke_tests": {},
  "errors": [],
  "warnings": [],
  "success": false
}
EOF

# Function to update JSON report
update_report() {
    local key="$1"
    local value="$2"
    local temp_file="/tmp/report-update-$$.json"
    
    jq "$key = $value" "$REPORT_FILE" > "$temp_file" && mv "$temp_file" "$REPORT_FILE"
}

# Function to add error
add_error() {
    local error_msg="$1"
    local temp_file="/tmp/report-update-$$.json"
    
    jq ".errors += [\"$error_msg\"]" "$REPORT_FILE" > "$temp_file" && mv "$temp_file" "$REPORT_FILE"
}

# Function to add warning
add_warning() {
    local warning_msg="$1"
    local temp_file="/tmp/report-update-$$.json"
    
    jq ".warnings += [\"$warning_msg\"]" "$REPORT_FILE" > "$temp_file" && mv "$temp_file" "$REPORT_FILE"
}

# Check Docker services
echo -e "${BLUE}📊 Checking Docker services...${NC}"

PROJECT_NAME="veris-memory-${ENVIRONMENT}"

# Get container states
for service in context-store qdrant neo4j redis; do
    container_name="${PROJECT_NAME}-${service}-1"
    
    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        # Container exists and is running
        status=$(docker inspect "$container_name" --format '{{.State.Status}}' 2>/dev/null || echo "unknown")
        health=$(docker inspect "$container_name" --format '{{.State.Health.Status}}' 2>/dev/null || echo "none")
        uptime=$(docker inspect "$container_name" --format '{{.State.StartedAt}}' 2>/dev/null || echo "unknown")
        
        # Get container resource usage
        stats=$(docker stats "$container_name" --no-stream --format "{{json .}}" 2>/dev/null || echo '{}')
        cpu_percent=$(echo "$stats" | jq -r '.CPUPerc' | tr -d '%' || echo 0)
        mem_usage=$(echo "$stats" | jq -r '.MemUsage' | awk '{print $1}' || echo "0")
        
        service_info=$(cat << JSON
{
  "status": "$status",
  "health": "$health",
  "uptime": "$uptime",
  "container_name": "$container_name",
  "cpu_percent": $cpu_percent,
  "memory_usage": "$mem_usage"
}
JSON
)
        update_report ".services.\"$service\"" "$service_info"
    else
        # Container doesn't exist or isn't running
        update_report ".services.\"$service\"" '{"status": "not_found", "health": "unknown"}'
        add_error "Service $service container not found"
    fi
done

# Perform health checks
echo -e "${BLUE}🏥 Running health checks...${NC}"

# API Health Check
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    update_report '.health_checks.api' '{"status": "healthy", "endpoint": "http://localhost:8000/health"}'
else
    update_report '.health_checks.api' '{"status": "unhealthy", "endpoint": "http://localhost:8000/health"}'
    add_error "API health check failed"
fi

# Qdrant Health Check
if curl -sf http://localhost:6333/health > /dev/null 2>&1; then
    # Check if collection exists
    if curl -sf http://localhost:6333/collections/context_embeddings > /dev/null 2>&1; then
        collection_info=$(curl -s http://localhost:6333/collections/context_embeddings | jq -c '.result')
        update_report '.health_checks.qdrant' "{\"status\": \"healthy\", \"collection_exists\": true, \"collection_info\": $collection_info}"
    else
        update_report '.health_checks.qdrant' '{"status": "healthy", "collection_exists": false}'
        add_warning "Qdrant is healthy but collection 'context_embeddings' does not exist"
    fi
else
    update_report '.health_checks.qdrant' '{"status": "unhealthy"}'
    add_error "Qdrant health check failed"
fi

# Neo4j Health Check
if timeout 2 bash -c "</dev/tcp/localhost/7687" 2>/dev/null; then
    update_report '.health_checks.neo4j' '{"status": "healthy", "port": 7687}'
else
    update_report '.health_checks.neo4j' '{"status": "unhealthy", "port": 7687}'
    add_error "Neo4j health check failed"
fi

# Redis Health Check
if echo "PING" | nc -w 2 localhost 6379 | grep -q PONG; then
    update_report '.health_checks.redis' '{"status": "healthy", "port": 6379}'
else
    update_report '.health_checks.redis' '{"status": "unhealthy", "port": 6379}'
    add_error "Redis health check failed"
fi

# Run smoke tests if available
if [ -f "ops/smoke/smoke_runner.py" ]; then
    echo -e "${BLUE}🧪 Running smoke tests...${NC}"
    
    # Run smoke tests and capture output
    smoke_output="/tmp/smoke-output-$$.json"
    if python3 ops/smoke/smoke_runner.py \
        --api-url http://localhost:8000 \
        --qdrant-url http://localhost:6333 \
        --neo4j-url http://localhost:7474 \
        --export json \
        --output "$smoke_output" 2>/dev/null; then
        
        # Parse smoke test results
        if [ -f "$smoke_output" ]; then
            smoke_results=$(cat "$smoke_output")
            update_report '.smoke_tests' "$smoke_results"
            
            # Check if all tests passed
            failed_count=$(echo "$smoke_results" | jq '.summary.failed')
            if [ "$failed_count" -eq 0 ]; then
                echo -e "${GREEN}✅ All smoke tests passed${NC}"
            else
                echo -e "${YELLOW}⚠️  $failed_count smoke tests failed${NC}"
                add_warning "$failed_count smoke tests failed"
            fi
        fi
    else
        update_report '.smoke_tests' '{"error": "Failed to run smoke tests"}'
        add_warning "Smoke tests failed to execute"
    fi
    rm -f "$smoke_output"
else
    update_report '.smoke_tests' '{"skipped": true, "reason": "Smoke test runner not found"}'
fi

# Determine overall success
echo -e "${BLUE}📈 Calculating deployment status...${NC}"

# Count healthy services
healthy_services=$(jq '[.services | to_entries[] | select(.value.health == "healthy" or .value.health == "none")] | length' "$REPORT_FILE")
total_services=$(jq '.services | length' "$REPORT_FILE")

# Count healthy health checks
healthy_checks=$(jq '[.health_checks | to_entries[] | select(.value.status == "healthy")] | length' "$REPORT_FILE")
total_checks=$(jq '.health_checks | length' "$REPORT_FILE")

# Get error count
error_count=$(jq '.errors | length' "$REPORT_FILE")

# Determine success
if [ "$error_count" -eq 0 ] && [ "$healthy_services" -eq "$total_services" ] && [ "$healthy_checks" -eq "$total_checks" ]; then
    update_report '.success' 'true'
    update_report '.status' '"SUCCESS"'
    update_report '.message' '"All services deployed and healthy"'
    echo -e "${GREEN}✅ Deployment successful!${NC}"
else
    update_report '.success' 'false'
    update_report '.status' '"PARTIAL"'
    update_report '.message' "\"$healthy_services/$total_services services healthy, $healthy_checks/$total_checks health checks passed, $error_count errors\""
    echo -e "${YELLOW}⚠️  Deployment partially successful${NC}"
fi

# Add summary
summary=$(cat << JSON
{
  "services_healthy": $healthy_services,
  "services_total": $total_services,
  "health_checks_passed": $healthy_checks,
  "health_checks_total": $total_checks,
  "errors": $error_count,
  "warnings": $(jq '.warnings | length' "$REPORT_FILE")
}
JSON
)
update_report '.summary' "$summary"

# Output the final report
echo -e "${BLUE}📄 Deployment Report:${NC}"
cat "$REPORT_FILE" | jq '.'

# Also save to a permanent location
REPORT_DIR="/opt/veris-memory/deployment-reports"
mkdir -p "$REPORT_DIR"
FINAL_REPORT="$REPORT_DIR/deployment-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).json"
cp "$REPORT_FILE" "$FINAL_REPORT"

echo -e "${BLUE}📁 Report saved to: $FINAL_REPORT${NC}"

# Return appropriate exit code
if [ "$error_count" -gt 0 ]; then
    exit 1
fi