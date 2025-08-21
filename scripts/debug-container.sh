#!/bin/bash
# Container Debugging Script - Captures ALL information when container fails

set -e

CONTAINER_NAME="${1:-veris-memory-dev-api-1}"
echo "=========================================="
echo "🔍 CONTAINER DEBUG REPORT: $CONTAINER_NAME"
echo "=========================================="
echo "Time: $(date)"
echo ""

# Check if container exists
if ! docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ Container $CONTAINER_NAME does not exist!"
    exit 1
fi

# Get container status
echo "📊 CONTAINER STATUS:"
echo "===================="
docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.State}}"
echo ""

# Get container inspect details
echo "🔎 CONTAINER INSPECT (Key Fields):"
echo "==================================="
docker inspect "$CONTAINER_NAME" --format '
Status: {{.State.Status}}
Exit Code: {{.State.ExitCode}}
Started At: {{.State.StartedAt}}
Finished At: {{.State.FinishedAt}}
Error: {{.State.Error}}
OOMKilled: {{.State.OOMKilled}}
Restarting: {{.State.Restarting}}
Dead: {{.State.Dead}}
Pid: {{.State.Pid}}
' 2>/dev/null || echo "Failed to inspect container"
echo ""

# Get the actual command that was run
echo "🏃 COMMAND EXECUTED:"
echo "===================="
docker inspect "$CONTAINER_NAME" --format '{{join .Config.Cmd " "}}' 2>/dev/null || echo "No command found"
echo ""

# Get environment variables
echo "🌍 ENVIRONMENT VARIABLES:"
echo "========================="
docker inspect "$CONTAINER_NAME" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -E "(API|NEO4J|QDRANT|REDIS|LOG|PYTHON)" | head -20 || echo "No env vars"
echo ""

# Get the last 100 lines of logs
echo "📜 CONTAINER LOGS (Last 100 lines):"
echo "===================================="
docker logs "$CONTAINER_NAME" --tail 100 2>&1 || echo "No logs available"
echo ""

# Check what files are in the container
echo "📁 FILES IN CONTAINER /app:"
echo "==========================="
docker run --rm --entrypoint ls "${CONTAINER_NAME%%-*}/${CONTAINER_NAME##*-dev-}:latest" -la /app 2>/dev/null || \
    docker exec "$CONTAINER_NAME" ls -la /app 2>/dev/null || \
    echo "Cannot list files (container not running)"
echo ""

# Check if startup script exists
echo "🔍 STARTUP SCRIPT CHECK:"
echo "========================"
docker run --rm --entrypoint sh "${CONTAINER_NAME%%-*}/${CONTAINER_NAME##*-dev-}:latest" -c "
    if [ -f /app/api-startup.sh ]; then
        echo '✅ api-startup.sh exists'
        echo 'File size:' && stat -c%s /app/api-startup.sh
        echo 'Permissions:' && ls -la /app/api-startup.sh
        echo 'First 5 lines:' && head -5 /app/api-startup.sh
    else
        echo '❌ api-startup.sh NOT FOUND!'
    fi
" 2>/dev/null || echo "Cannot check startup script"
echo ""

# Test Python import directly
echo "🐍 PYTHON IMPORT TEST:"
echo "======================"
docker run --rm --entrypoint python3 "${CONTAINER_NAME%%-*}/${CONTAINER_NAME##*-dev-}:latest" -c "
import sys
print(f'Python version: {sys.version}')
try:
    from src.api import main
    print('✅ Import successful')
except Exception as e:
    print(f'❌ Import failed: {e}')
    import traceback
    traceback.print_exc()
" 2>&1 || echo "Python test failed"
echo ""

# Get events related to this container
echo "📅 CONTAINER EVENTS (Last 10):"
echo "==============================="
docker events --since 10m --until now --filter "container=${CONTAINER_NAME}" --format "{{.Time}} {{.Action}}: {{.Actor.Attributes.exitCode}}" | tail -10 || echo "No events"
echo ""

# Get health check status if any
echo "💊 HEALTH CHECK STATUS:"
echo "======================="
docker inspect "$CONTAINER_NAME" --format '{{json .State.Health}}' 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "No health check configured or container exited"
echo ""

# Final diagnosis
echo "🔬 DIAGNOSIS:"
echo "============="
STATUS=$(docker inspect "$CONTAINER_NAME" --format '{{.State.Status}}' 2>/dev/null)
EXIT_CODE=$(docker inspect "$CONTAINER_NAME" --format '{{.State.ExitCode}}' 2>/dev/null)

if [ "$STATUS" = "exited" ] && [ "$EXIT_CODE" != "0" ]; then
    echo "❌ Container exited with error code $EXIT_CODE"
    echo "This means the container crashed during startup."
    echo "Check the logs above for the actual error message."
elif [ "$STATUS" = "running" ]; then
    echo "✅ Container is running"
    HEALTH=$(docker inspect "$CONTAINER_NAME" --format '{{.State.Health.Status}}' 2>/dev/null)
    if [ "$HEALTH" = "unhealthy" ]; then
        echo "⚠️  But health checks are failing"
    fi
else
    echo "⚠️  Container status: $STATUS"
fi

echo ""
echo "=========================================="
echo "END OF DEBUG REPORT"
echo "=========================================="