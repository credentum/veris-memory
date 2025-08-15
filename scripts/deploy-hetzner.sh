#!/bin/bash
# Hetzner Deployment Script with Proper Cleanup
# This script handles the complete deployment process including cleanup of existing containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Hetzner Deployment${NC}"
echo "================================================"

# Configuration
DEPLOYMENT_DIR="/opt/veris-memory"
CONTEXT_STORE_DIR="$DEPLOYMENT_DIR/context-store"

# Navigate to deployment directory
if [ ! -d "$DEPLOYMENT_DIR" ]; then
    echo -e "${RED}❌ Error: Deployment directory $DEPLOYMENT_DIR not found${NC}"
    exit 1
fi

cd "$DEPLOYMENT_DIR"

# Pull latest changes
echo -e "${BLUE}📥 Pulling latest changes from repository...${NC}"
git fetch origin
git reset --hard origin/main

# Navigate to context-store
cd "$CONTEXT_STORE_DIR"

# Setup environment
echo -e "${BLUE}⚙️  Setting up environment...${NC}"
if [ -f ".env.hetzner" ]; then
    cp .env.hetzner .env
    echo "  → Using .env.hetzner configuration"
elif [ -f ".env.hetzner.template" ]; then
    cp .env.hetzner.template .env
    echo "  → Using .env.hetzner.template configuration"
else
    echo -e "${YELLOW}⚠️  Warning: No Hetzner environment file found${NC}"
fi

# Export environment variables if provided
if [ -n "$NEO4J_PASSWORD" ]; then
    export NEO4J_PASSWORD="$NEO4J_PASSWORD"
fi
if [ -n "$TAILSCALE_AUTHKEY" ]; then
    export TAILSCALE_AUTHKEY="$TAILSCALE_AUTHKEY"
fi
export TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-veris-memory-hetzner}"

# CRITICAL: Stop ALL existing containers that might use our ports
echo -e "${YELLOW}🛑 Stopping ALL existing containers...${NC}"

# Stop containers from different compose projects
echo "  → Checking for existing containers on ports..."
for port in 6333 6379 7474 7687 8000; do
    containers=$(docker ps --filter "publish=$port" --format "{{.Names}}" 2>/dev/null || true)
    if [ -n "$containers" ]; then
        echo "  → Stopping containers using port $port: $containers"
        docker stop $containers 2>/dev/null || true
        docker rm $containers 2>/dev/null || true
    fi
done

# Stop any context-store related containers
echo "  → Stopping context-store containers..."
docker ps --format "{{.Names}}" | grep -E "context-store|veris-memory|neo4j|redis|qdrant" | while read container; do
    echo "    - Stopping: $container"
    docker stop "$container" 2>/dev/null || true
    docker rm "$container" 2>/dev/null || true
done

# Try docker-compose down with different project names
echo "  → Running docker-compose cleanup..."
docker-compose down --remove-orphans 2>/dev/null || true
docker-compose -p veris-memory down --remove-orphans 2>/dev/null || true
docker-compose -p context-store down --remove-orphans 2>/dev/null || true

# Use the appropriate compose file
if [ -f "docker/docker-compose.hetzner.yml" ]; then
    COMPOSE_FILE="docker/docker-compose.hetzner.yml"
    DOCKERFILE="docker/Dockerfile.hetzner"
    echo -e "${GREEN}✅ Using Hetzner-specific configuration${NC}"
else
    COMPOSE_FILE="docker/docker-compose.yml"
    DOCKERFILE="docker/Dockerfile"
    echo -e "${YELLOW}⚠️  Using standard configuration (Hetzner config not found)${NC}"
fi

# Final cleanup with the target compose file
docker-compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

# Verify ports are free
echo -e "${BLUE}🔍 Verifying ports are available...${NC}"
for port in 6333 6379 7474 7687 8000; do
    if docker ps --filter "publish=$port" --format "{{.Names}}" | grep -q .; then
        echo -e "${RED}❌ Port $port is still in use!${NC}"
        docker ps --filter "publish=$port"
        exit 1
    else
        echo "  ✓ Port $port is free"
    fi
done

# Build new images
echo -e "${BLUE}🏗️  Building updated images...${NC}"
if [ -f "$DOCKERFILE" ]; then
    docker build -f "$DOCKERFILE" -t context-store:hetzner .
else
    echo -e "${YELLOW}⚠️  $DOCKERFILE not found, using compose build${NC}"
fi

# Start services
echo -e "${GREEN}🚀 Starting services with $COMPOSE_FILE...${NC}"
docker-compose -f "$COMPOSE_FILE" up -d --build

# Wait for services to be healthy
echo -e "${BLUE}⏳ Waiting for services to be healthy...${NC}"
timeout=300
count=0
health_endpoint="http://localhost:8000/health"

while [ $count -lt $timeout ]; do
    if curl -f "$health_endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Services are healthy!${NC}"
        break
    fi
    echo "  → Waiting for services... ($count/$timeout)"
    sleep 10
    count=$((count + 10))
done

if [ $count -ge $timeout ]; then
    echo -e "${RED}❌ Services failed to become healthy${NC}"
    echo "Showing logs from last 50 lines:"
    docker-compose -f "$COMPOSE_FILE" logs --tail=50
    exit 1
fi

# Verify deployment
echo -e "${BLUE}🔍 Verifying deployment...${NC}"
docker-compose -f "$COMPOSE_FILE" ps

# Run basic health checks
echo -e "${BLUE}🏥 Running health checks...${NC}"
echo -n "  → Redis: "
if echo "PING" | nc -w 2 localhost 6379 | grep -q PONG; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo -n "  → Neo4j: "
if timeout 3 bash -c "</dev/tcp/localhost/7474" 2>/dev/null; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo -n "  → Qdrant: "
if curl -s http://localhost:6333/health | grep -q "ok"; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo -n "  → API: "
if curl -s http://localhost:8000/health | grep -q "ok\|healthy"; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo "================================================"
echo "Services running:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAME|veris-memory|context-store"