#!/bin/bash
# Fast Code-Only Deployment Script
# Updates Python code in running containers without rebuilding images
# Total time: ~10-30 seconds

set -e

PROJECT_NAME="veris-memory-dev"

echo "⚡ FAST CODE-ONLY DEPLOYMENT"
echo "================================"
echo "This skips image building and just updates code in running containers"
echo ""

# Git pull latest changes
echo "📥 Pulling latest code from GitHub..."
git pull origin main

# Get list of running containers that need code updates
CONTAINERS=(
    "${PROJECT_NAME}-context-store-1"
    "${PROJECT_NAME}-api-1"
    "${PROJECT_NAME}-sentinel-1"
    "${PROJECT_NAME}-monitoring-dashboard-1"
)

# Copy updated code into each container
for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "📦 Updating code in ${container}..."

        # Copy src directory into container
        docker cp src/. ${container}:/app/src/

        # Copy schemas if they exist
        if [ -d "schemas" ]; then
            docker cp schemas/. ${container}:/app/schemas/
        fi

        echo "✅ Code updated in ${container}"
    else
        echo "⚠️  ${container} is not running, skipping..."
    fi
done

echo ""
echo "🔄 Restarting services to load new code..."

# Restart containers to load new code
docker compose -p ${PROJECT_NAME} restart context-store api sentinel monitoring-dashboard

echo ""
echo "⏱️  Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "🏥 Service Health Check:"
echo "========================"

for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        health=$(docker inspect --format='{{.State.Health.Status}}' ${container} 2>/dev/null || echo "no healthcheck")
        if [ "$health" = "healthy" ]; then
            echo "✅ ${container}: healthy"
        else
            echo "⚠️  ${container}: ${health} (may still be starting...)"
        fi
    fi
done

echo ""
echo "✅ CODE-ONLY DEPLOYMENT COMPLETE!"
echo "Total time: ~30 seconds"
echo ""
echo "Test the deployment:"
echo "  curl http://172.17.0.1:8000/health"
