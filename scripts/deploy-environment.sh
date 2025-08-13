#!/bin/bash
# Environment-aware Deployment Script for veris-memory
# Supports both dev (auto-deploy) and prod (manual) environments
# Usage: ./deploy-environment.sh [dev|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get environment argument (default to dev)
ENVIRONMENT="${1:-dev}"

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo -e "${RED}❌ Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

echo -e "${CYAN}🚀 Starting $ENVIRONMENT Deployment${NC}"
echo "================================================"

# Configuration based on environment
if [ "$ENVIRONMENT" = "dev" ]; then
    echo -e "${YELLOW}📦 Deploying to DEVELOPMENT environment${NC}"
    PROJECT_NAME="veris-memory-dev"
    COMPOSE_FILE="docker-compose.yml"  # Use standard compose for dev
    ENV_FILE=".env.dev"
    API_PORT=8000        # Standard ports for dev (what we test with)
    QDRANT_PORT=6333
    NEO4J_HTTP_PORT=7474
    NEO4J_BOLT_PORT=7687
    REDIS_PORT=6379
    HEALTH_ENDPOINT="http://localhost:8000/health"
else
    echo -e "${GREEN}📦 Deploying to PRODUCTION environment${NC}"
    PROJECT_NAME="veris-memory-prod"
    COMPOSE_FILE="docker-compose.prod.yml"  # Separate compose for prod
    ENV_FILE=".env"
    API_PORT=8001        # Alternate ports for production
    QDRANT_PORT=6334
    NEO4J_HTTP_PORT=7475
    NEO4J_BOLT_PORT=7688
    REDIS_PORT=6380
    HEALTH_ENDPOINT="http://localhost:8001/health"
fi

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.yml not found${NC}"
    echo "Please run this script from the context-store directory"
    exit 1
fi

# Check if environment-specific compose file exists
if [ ! -f "$COMPOSE_FILE" ] && [ "$ENVIRONMENT" = "prod" ]; then
    echo -e "${YELLOW}⚠️  Warning: $COMPOSE_FILE not found, creating from template${NC}"
    # Create prod compose file if it doesn't exist
    cat > docker-compose.prod.yml << 'EOF'
version: "3.8"

services:
  # Context Store MCP Server - PROD Environment
  context-store:
    build:
      context: .
      dockerfile: Dockerfile.flyio
    container_name: veris-memory-prod-api
    ports:
      - "127.0.0.1:8001:8000"  # Prod API on 8001
    environment:
      - ENVIRONMENT=production
      - QDRANT_URL=http://qdrant:6333
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - REDIS_URL=redis://redis:6379
      - MCP_SERVER_PORT=8000
      - LOG_LEVEL=debug
    depends_on:
      qdrant:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - veris-prod-network

  # Vector Database (Qdrant) - DEV
  qdrant:
    image: qdrant/qdrant:v1.9.6
    platform: linux/amd64
    container_name: veris-memory-prod-qdrant
    ports:
      - "127.0.0.1:6334:6333"  # Prod Qdrant on 6334
      - "127.0.0.1:6335:6334"  # Prod gRPC on 6335
    volumes:
      - qdrant_prod_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    networks:
      - veris-prod-network

  # Graph Database (Neo4j) - DEV
  neo4j:
    image: neo4j:5.15-community
    platform: linux/amd64
    container_name: veris-memory-prod-neo4j
    ports:
      - "127.0.0.1:7475:7474"  # Prod HTTP on 7475
      - "127.0.0.1:7688:7687"  # Prod Bolt on 7688
    volumes:
      - neo4j_prod_data:/data
      - neo4j_prod_logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_default__listen__address=0.0.0.0
    healthcheck:
      test: ["CMD", "sh", "-c", "cypher-shell -u neo4j -p $$NEO4J_PASSWORD 'RETURN 1'"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped
    networks:
      - veris-prod-network

  # Cache/KV Store (Redis) - DEV
  redis:
    image: redis:7.2.5-alpine
    platform: linux/amd64
    container_name: veris-memory-prod-redis
    ports:
      - "127.0.0.1:6380:6379"  # Prod Redis on 6380
    volumes:
      - redis_prod_data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    networks:
      - veris-prod-network

networks:
  veris-prod-network:
    name: veris-memory-prod-network
    driver: bridge

volumes:
  qdrant_prod_data:
    name: veris-memory-prod-qdrant-data
  neo4j_prod_data:
    name: veris-memory-prod-neo4j-data
  neo4j_prod_logs:
    name: veris-memory-prod-neo4j-logs
  redis_prod_data:
    name: veris-memory-prod-redis-data
EOF
fi

# Setup environment file
echo -e "${BLUE}⚙️  Setting up environment...${NC}"
if [ -f "$ENV_FILE" ]; then
    echo "  → Using existing $ENV_FILE"
elif [ -f ".env.template" ]; then
    cp .env.template "$ENV_FILE"
    echo "  → Created $ENV_FILE from template"
else
    echo -e "${YELLOW}⚠️  Warning: No environment file found${NC}"
fi

# Create .env file with NEO4J_PASSWORD if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📝 Creating .env file with NEO4J_PASSWORD...${NC}"
    echo "# Auto-generated environment file" > .env
    echo "QDRANT_URL=http://localhost:6333" >> .env
    echo "NEO4J_URI=bolt://localhost:7687" >> .env
    echo "NEO4J_USER=neo4j" >> .env
    echo "REDIS_URL=redis://localhost:6379" >> .env
    echo "MCP_SERVER_PORT=8000" >> .env
    echo "LOG_LEVEL=info" >> .env
fi

# Ensure NEO4J_PASSWORD is in .env file (remove old and add new)
if [ -n "$NEO4J_PASSWORD" ]; then
    echo -e "${YELLOW}📝 Updating NEO4J_PASSWORD in .env file...${NC}"
    # Remove any existing NEO4J_PASSWORD lines
    grep -v "^NEO4J_PASSWORD=" .env > .env.tmp || true
    grep -v "^NEO4J_AUTH=" .env.tmp > .env || true
    rm -f .env.tmp
    
    # Add the password from environment variable
    echo "NEO4J_PASSWORD=$NEO4J_PASSWORD" >> .env
    echo "NEO4J_AUTH=neo4j/$NEO4J_PASSWORD" >> .env
    export NEO4J_PASSWORD="$NEO4J_PASSWORD"
    
    echo -e "${GREEN}✅ NEO4J_PASSWORD added to .env (${#NEO4J_PASSWORD} characters)${NC}"
else
    echo -e "${RED}❌ ERROR: NEO4J_PASSWORD environment variable not set!${NC}"
    echo "Please set NEO4J_PASSWORD before running this script"
    exit 1
fi

# Stop existing containers for this environment
echo -e "${YELLOW}🛑 Stopping existing $ENVIRONMENT containers...${NC}"

# Stop containers by project name (with volumes to ensure clean state)
docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true

# CRITICAL: Remove Neo4j volumes to ensure password changes take effect
echo -e "${YELLOW}🗑️  Removing Neo4j volumes for clean authentication...${NC}"
docker volume ls | grep "$PROJECT_NAME" | grep neo4j | awk '{print $2}' | xargs -r docker volume rm 2>/dev/null || true
# Try explicit volume names
docker volume rm "${PROJECT_NAME}_neo4j_data" "${PROJECT_NAME}_neo4j_logs" 2>/dev/null || true
echo -e "${GREEN}✅ Neo4j volumes removed - fresh password will be used${NC}"

# Also stop any containers using our target ports
echo "  → Checking for containers on $ENVIRONMENT ports..."
if [ "$ENVIRONMENT" = "dev" ]; then
    PORTS="$API_PORT $QDRANT_PORT $NEO4J_HTTP_PORT $NEO4J_BOLT_PORT $REDIS_PORT 6335"
else
    PORTS="$API_PORT $QDRANT_PORT $NEO4J_HTTP_PORT $NEO4J_BOLT_PORT $REDIS_PORT 6334"
fi

for port in $PORTS; do
    containers=$(docker ps --filter "publish=$port" --format "{{.Names}}" 2>/dev/null || true)
    if [ -n "$containers" ]; then
        echo "  → Stopping containers using port $port: $containers"
        docker stop $containers 2>/dev/null || true
        docker rm $containers 2>/dev/null || true
    fi
done

# Verify ports are free
echo -e "${BLUE}🔍 Verifying $ENVIRONMENT ports are available...${NC}"
all_ports_free=true
for port in $PORTS; do
    if docker ps --filter "publish=$port" --format "{{.Names}}" | grep -q .; then
        echo -e "${RED}❌ Port $port is still in use!${NC}"
        docker ps --filter "publish=$port"
        all_ports_free=false
    else
        echo "  ✓ Port $port is free"
    fi
done

if [ "$all_ports_free" = false ]; then
    echo -e "${RED}❌ Some ports are still in use. Please stop conflicting containers.${NC}"
    exit 1
fi

# Build and start services
echo -e "${GREEN}🚀 Starting $ENVIRONMENT services...${NC}"
docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build

# Wait for services to be healthy
echo -e "${BLUE}⏳ Waiting for $ENVIRONMENT services to be healthy...${NC}"
timeout=300
count=0

while [ $count -lt $timeout ]; do
    if curl -f "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $ENVIRONMENT services are healthy!${NC}"
        break
    fi
    echo "  → Waiting for services... ($count/$timeout)"
    sleep 10
    count=$((count + 10))
done

if [ $count -ge $timeout ]; then
    echo -e "${RED}❌ $ENVIRONMENT services failed to become healthy${NC}"
    echo "Showing logs from last 50 lines:"
    docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs --tail=50
    exit 1
fi

# Bootstrap Qdrant collection if needed
echo -e "${BLUE}🔧 Bootstrapping Qdrant collection...${NC}"
if [ -f "ops/bootstrap/qdrant_bootstrap.py" ]; then
    sleep 5  # Give services time to fully start
    python3 ops/bootstrap/qdrant_bootstrap.py --qdrant-url http://localhost:$QDRANT_PORT --ensure-collection || echo "  → Bootstrap completed or collection already exists"
else
    echo -e "${YELLOW}⚠️  Bootstrap script not found, skipping${NC}"
fi

# Run environment-specific health checks
echo -e "${BLUE}🏥 Running $ENVIRONMENT health checks...${NC}"
echo -n "  → Redis (port $REDIS_PORT): "
if echo "PING" | nc -w 2 localhost $REDIS_PORT | grep -q PONG; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo -n "  → Neo4j (port $NEO4J_HTTP_PORT): "
if timeout 3 bash -c "</dev/tcp/localhost/$NEO4J_HTTP_PORT" 2>/dev/null; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo -n "  → Qdrant (port $QDRANT_PORT): "
if curl -s http://localhost:$QDRANT_PORT/health | grep -q "ok"; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

echo -n "  → API (port $API_PORT): "
if curl -s http://localhost:$API_PORT/health | grep -q "ok\|healthy"; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
fi

# Show running containers
echo ""
echo -e "${BLUE}📊 $ENVIRONMENT containers running:${NC}"
docker-compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps

# Environment-specific instructions
echo ""
echo -e "${GREEN}🎉 $ENVIRONMENT deployment completed successfully!${NC}"
echo "================================================"
if [ "$ENVIRONMENT" = "dev" ]; then
    echo "Development services available at:"
    echo "  • API: http://localhost:$API_PORT"
    echo "  • Qdrant: http://localhost:$QDRANT_PORT"
    echo "  • Neo4j: http://localhost:$NEO4J_HTTP_PORT"
    echo "  • Redis: localhost:$REDIS_PORT"
    echo ""
    echo "Run tests with:"
    echo "  python ops/smoke/smoke_runner.py --api-url http://localhost:$API_PORT --qdrant-url http://localhost:$QDRANT_PORT"
else
    echo "Production services available at:"
    echo "  • API: http://localhost:$API_PORT"
    echo "  • Qdrant: http://localhost:$QDRANT_PORT"
    echo "  • Neo4j: http://localhost:$NEO4J_HTTP_PORT"
    echo "  • Redis: localhost:$REDIS_PORT"
    echo ""
    echo "Run tests with:"
    echo "  python ops/smoke/smoke_runner.py"
fi