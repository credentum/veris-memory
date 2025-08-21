#!/bin/bash
# Enhanced Deployment Script with Maximum Debugging

set -e  # Exit on error

echo "=========================================="
echo "🚀 ENHANCED DEPLOYMENT WITH DEBUGGING"
echo "=========================================="
echo "Time: $(date)"
echo "Environment: ${1:-dev}"
echo ""

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="veris-memory-${ENVIRONMENT}"
COMPOSE_FILE="docker-compose.yml"

# Step 1: Clean up old containers and images
echo "🧹 STEP 1: COMPLETE CLEANUP"
echo "============================"
echo "Removing old containers..."
docker compose -p "$PROJECT_NAME" down --remove-orphans 2>/dev/null || true
docker ps -aq --filter "name=${PROJECT_NAME}" | xargs -r docker rm -f 2>/dev/null || true
echo "✅ Old containers removed"
echo ""

# Step 2: Remove old images to force rebuild
echo "🗑️  STEP 2: REMOVE CACHED IMAGES"
echo "================================"
echo "Removing cached API image..."
docker rmi "${PROJECT_NAME}-api" 2>/dev/null || true
docker rmi "$(docker images -q --filter "reference=*api*" --filter "reference=*${PROJECT_NAME}*")" 2>/dev/null || true
echo "✅ Cached images removed"
echo ""

# Step 3: Build with no cache
echo "🔨 STEP 3: BUILD WITHOUT CACHE"
echo "=============================="
echo "Building API container from scratch..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" build --no-cache api 2>&1 | tee /tmp/docker-build.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ Build failed! See /tmp/docker-build.log for details"
    tail -50 /tmp/docker-build.log
    exit 1
fi
echo "✅ API container built successfully"
echo ""

# Step 4: Start containers with detailed monitoring
echo "🚀 STEP 4: START CONTAINERS"
echo "==========================="
echo "Starting all services..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d 2>&1 | tee /tmp/docker-up.log
echo ""

# Step 5: Wait and monitor API container
echo "⏱️  STEP 5: MONITOR API CONTAINER"
echo "================================="
echo "Waiting 10 seconds for container to start..."
sleep 10

# Check API container status
API_CONTAINER="${PROJECT_NAME}-api-1"
API_STATUS=$(docker inspect "$API_CONTAINER" --format '{{.State.Status}}' 2>/dev/null || echo "not-found")
API_EXIT_CODE=$(docker inspect "$API_CONTAINER" --format '{{.State.ExitCode}}' 2>/dev/null || echo "N/A")

echo "API Container Status: $API_STATUS"
echo "API Exit Code: $API_EXIT_CODE"
echo ""

# Step 6: Capture debugging information if failed
if [ "$API_STATUS" != "running" ] || [ "$API_EXIT_CODE" != "0" ]; then
    echo "❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌"
    echo "❌ API CONTAINER FAILED TO START!"
    echo "❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌"
    echo ""
    
    # Capture ALL debugging information
    echo "📊 CONTAINER DETAILS:"
    docker ps -a --filter "name=$API_CONTAINER"
    echo ""
    
    echo "📜 LAST 200 LINES OF API CONTAINER LOGS:"
    echo "========================================="
    docker logs "$API_CONTAINER" --tail 200 2>&1 || echo "No logs available"
    echo ""
    
    echo "🔍 CONTAINER INSPECTION:"
    echo "========================"
    docker inspect "$API_CONTAINER" --format '
Container ID: {{.Id}}
Image: {{.Config.Image}}
Status: {{.State.Status}}
Exit Code: {{.State.ExitCode}}
Started At: {{.State.StartedAt}}
Finished At: {{.State.FinishedAt}}
Error Message: {{.State.Error}}
OOM Killed: {{.State.OOMKilled}}
Command: {{join .Config.Cmd " "}}
Working Dir: {{.Config.WorkingDir}}
    ' 2>/dev/null || echo "Inspection failed"
    echo ""
    
    echo "📁 FILES IN API CONTAINER:"
    echo "=========================="
    # Try to list files even if container is stopped
    docker run --rm --entrypoint ls veris-memory-dev-api:latest -la /app 2>&1 || \
        echo "Cannot list files"
    echo ""
    
    echo "🔍 CHECK FOR STARTUP SCRIPT:"
    echo "============================"
    docker run --rm --entrypoint sh veris-memory-dev-api:latest -c "
        echo 'Checking for api-startup.sh...'
        if [ -f /app/api-startup.sh ]; then
            echo '✅ Script exists'
            ls -la /app/api-startup.sh
            echo 'First 10 lines:'
            head -10 /app/api-startup.sh
        else
            echo '❌ Script NOT FOUND'
            echo 'Files in /app:'
            ls -la /app/
        fi
    " 2>&1 || echo "Check failed"
    echo ""
    
    echo "🐍 TEST PYTHON IMPORT:"
    echo "======================"
    docker run --rm --entrypoint python3 veris-memory-dev-api:latest -c "
import sys
print(f'Python: {sys.version}')
try:
    from src.api import main
    print('✅ Import OK')
except Exception as e:
    print(f'❌ Import failed: {e}')
    import traceback
    traceback.print_exc()
    " 2>&1 || echo "Python test failed"
    echo ""
    
    echo "🌍 ENVIRONMENT VARIABLES:"
    echo "========================"
    docker inspect "$API_CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | \
        grep -E "(API|NEO4J|QDRANT|REDIS|LOG)" || echo "No env vars"
    echo ""
    
    echo "📝 BUILD CACHE STATUS:"
    echo "====================="
    docker images --filter "reference=*api*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Created}}\t{{.Size}}"
    echo ""
    
    echo "❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌"
    echo "DEPLOYMENT FAILED - See debugging output above"
    echo "❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌"
    exit 1
fi

# Step 7: Health check
echo "✅ STEP 7: HEALTH CHECK"
echo "======================="
echo "API container is running. Checking health..."

# Wait for health endpoint
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -f http://localhost:8001/api/v1/health/live 2>/dev/null; then
        echo ""
        echo "✅ API is healthy!"
        break
    fi
    echo -n "."
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo ""
    echo "⚠️  Health check timed out after ${MAX_WAIT} seconds"
    echo "Container is running but not responding to health checks"
    echo ""
    echo "📜 Current API logs:"
    docker logs "$API_CONTAINER" --tail 50
fi

echo ""
echo "📊 FINAL STATUS:"
echo "================"
docker ps --filter "name=${PROJECT_NAME}"
echo ""
echo "✅ Deployment complete!"