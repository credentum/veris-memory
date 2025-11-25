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

# Get environment argument (default to development)
ENVIRONMENT="${1:-development}"

# Validate environment
if [[ "$ENVIRONMENT" != "development" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}❌ Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "Usage: $0 [development|production]"
    exit 1
fi

echo -e "${CYAN}🚀 Starting $ENVIRONMENT Deployment${NC}"
echo "================================================"

# Configuration based on environment
if [ "$ENVIRONMENT" = "development" ]; then
    echo -e "${YELLOW}📦 Deploying to DEVELOPMENT environment${NC}"
    PROJECT_NAME="veris-memory-dev"
    # Use volume-mounted compose for FAST code deployments (no rebuild needed)
    # Code is mounted from host, changes are instant with hot reload
    COMPOSE_FILE="docker-compose.deploy-dev.yml"
    ENV_FILE=".env.dev"
    API_PORT=8000        # Standard ports for dev (what we test with)
    QDRANT_PORT=6333
    NEO4J_HTTP_PORT=7474
    NEO4J_BOLT_PORT=7687
    REDIS_PORT=6379
    HEALTH_ENDPOINT="http://localhost:8000/health"
    echo -e "${GREEN}  → Using volume mounts for instant code changes${NC}"
    echo -e "${GREEN}  → Hot reload enabled (auto-restart on file changes)${NC}"
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
    echo "Please run this script from the veris-memory root directory"
    exit 1
fi

# CRITICAL: Verify dockerfile exists to prevent path truncation issue
echo -e "${BLUE}🔍 Verifying dockerfile paths...${NC}"
if [ ! -f "dockerfiles/Dockerfile" ]; then
    echo -e "${RED}❌ Error: dockerfiles/Dockerfile not found${NC}"
    echo "Expected path: $(pwd)/dockerfiles/Dockerfile"
    ls -la dockerfiles/ || true
    exit 1
fi
echo "  ✓ dockerfiles/Dockerfile exists"

# Additional verification for production dockerfile if needed
if [ "$ENVIRONMENT" = "production" ] && grep -q "Dockerfile.flyio" "$COMPOSE_FILE" 2>/dev/null; then
    if [ ! -f "dockerfiles/Dockerfile.flyio" ]; then
        echo -e "${RED}❌ Error: dockerfiles/Dockerfile.flyio not found${NC}"
        exit 1
    fi
    echo "  ✓ dockerfiles/Dockerfile.flyio exists"
fi

# Check if environment-specific compose file exists
if [ ! -f "$COMPOSE_FILE" ] && [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${YELLOW}⚠️  Warning: $COMPOSE_FILE not found, creating from template${NC}"
    # Create production compose file if it doesn't exist
    cat > docker-compose.prod.yml << 'EOF'
version: "3.8"

services:
  # Context Store MCP Server - PROD Environment
  context-store:
    build:
      context: .
      dockerfile: dockerfiles/Dockerfile.flyio
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
    image: qdrant/qdrant:v1.15.1
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

# Stop existing containers for this environment with ROBUST cleanup
echo -e "${YELLOW}🛑 Performing robust container cleanup for $ENVIRONMENT...${NC}"

# Debug: Show what containers exist before cleanup
echo -e "${BLUE}📊 Current Docker state before cleanup:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep "$PROJECT_NAME" || echo "  No $PROJECT_NAME containers running"

# Method 1: Stop using docker compose (modern syntax)
echo "  → Attempting docker compose down..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

# Method 2: Force remove containers by project name
echo "  → Force removing containers by project name..."
docker ps -a --filter "name=$PROJECT_NAME" --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true

# Method 3: Remove specific service containers if they still exist
echo "  → Checking for lingering service containers..."
for service in context-store qdrant neo4j redis; do
    container_name="${PROJECT_NAME}-${service}-1"
    if docker ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
        echo "    → Force removing $container_name"
        docker rm -f "$container_name" 2>/dev/null || true
    fi
done

# CRITICAL: Remove ALL instances of fixed-name containers (livekit-server, voice-bot)
echo "  → Force removing fixed-name containers (livekit-server, voice-bot)..."
# Find ALL containers with these names using filter (more reliable than grep)
LIVEKIT_IDS=$(docker ps -a -q --filter "name=livekit-server" 2>/dev/null || true)
VOICEBOT_IDS=$(docker ps -a -q --filter "name=voice-bot" 2>/dev/null || true)

if [ -n "$LIVEKIT_IDS" ] || [ -n "$VOICEBOT_IDS" ]; then
    echo "    → Found existing containers:"
    docker ps -a --filter "name=livekit-server" --filter "name=voice-bot" --format "table {{.Names}}\t{{.Status}}" || true

    # Remove by container ID (more reliable than by name)
    if [ -n "$LIVEKIT_IDS" ]; then
        echo "    → Removing livekit-server (IDs: $LIVEKIT_IDS)"
        echo "$LIVEKIT_IDS" | xargs -r docker rm -f 2>&1 | grep -v "No such container" || true
    fi
    if [ -n "$VOICEBOT_IDS" ]; then
        echo "    → Removing voice-bot (IDs: $VOICEBOT_IDS)"
        echo "$VOICEBOT_IDS" | xargs -r docker rm -f 2>&1 | grep -v "No such container" || true
    fi
else
    echo "    → No livekit/voice-bot containers found"
fi

# Kill any processes holding livekit ports (non-docker processes)
echo "  → Checking for non-docker processes on livekit ports..."
for port in 7880 7882 5349; do
    PID=$(lsof -ti tcp:$port 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "    → Found process $PID on port $port, killing..."
        kill -9 $PID 2>/dev/null || true
    fi
done

echo "  → Waiting 10 seconds for complete port release..."
sleep 10

# CRITICAL: Remove Neo4j volumes to ensure password changes take effect
echo -e "${YELLOW}🗑️  Removing Neo4j volumes for clean authentication...${NC}"
# List all volumes for this project
docker volume ls --filter "name=$PROJECT_NAME" --format "{{.Name}}" | while read vol; do
    echo "  → Removing volume: $vol"
    docker volume rm "$vol" 2>/dev/null || true
done

# Also try explicit volume names
docker volume rm "${PROJECT_NAME}_neo4j_data" "${PROJECT_NAME}_neo4j_logs" 2>/dev/null || true
docker volume rm "${PROJECT_NAME}_qdrant_data" 2>/dev/null || true
docker volume rm "${PROJECT_NAME}_redis_data" 2>/dev/null || true

echo -e "${GREEN}✅ Volumes removed - fresh state ensured${NC}"

# Stop any containers using our target ports
echo -e "${BLUE}🔍 Checking for port conflicts...${NC}"
if [ "$ENVIRONMENT" = "development" ]; then
    PORTS="$API_PORT $QDRANT_PORT $NEO4J_HTTP_PORT $NEO4J_BOLT_PORT $REDIS_PORT 6334 7880 7882 3478 5349"
else
    PORTS="$API_PORT $QDRANT_PORT $NEO4J_HTTP_PORT $NEO4J_BOLT_PORT $REDIS_PORT 6335 7880 7882 3478 5349"
fi

for port in $PORTS; do
    containers=$(docker ps --filter "publish=$port" --format "{{.Names}}" 2>/dev/null || true)
    if [ -n "$containers" ]; then
        echo "  → Port $port in use by: $containers"
        echo "    → Force removing conflicting containers..."
        echo "$containers" | xargs -r docker rm -f 2>/dev/null || true
    else
        echo "  → Port $port is free ✓"
    fi
done

# Final verification that cleanup was successful
echo -e "${BLUE}📊 Docker state after cleanup:${NC}"
remaining=$(docker ps -a --filter "name=$PROJECT_NAME" --format "{{.Names}}" | wc -l)
if [ "$remaining" -eq 0 ]; then
    echo -e "${GREEN}✅ All containers successfully removed${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: $remaining containers may still exist${NC}"
    docker ps -a --filter "name=$PROJECT_NAME" --format "table {{.Names}}\t{{.Status}}"
fi

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

# Generate SSL certificates for voice-bot if they don't exist
echo -e "${BLUE}🔐 Checking SSL certificates for voice-bot...${NC}"
CERT_DIR="/opt/veris-memory/voice-bot/certs"
if [ ! -d "$CERT_DIR" ]; then
    echo "  → Creating certs directory..."
    mkdir -p "$CERT_DIR"
fi

if [ ! -f "$CERT_DIR/key.pem" ] || [ ! -f "$CERT_DIR/cert.pem" ]; then
    echo "  → Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout "$CERT_DIR/key.pem" \
        -out "$CERT_DIR/cert.pem" \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=Personal/CN=$(hostname -I | awk '{print $1}')" \
        2>/dev/null || echo "⚠️  Certificate generation failed, voice-bot will use HTTP"

    if [ -f "$CERT_DIR/key.pem" ] && [ -f "$CERT_DIR/cert.pem" ]; then
        echo -e "${GREEN}  ✓ SSL certificates generated successfully${NC}"
        # Set permissions readable by container user (voicebot runs as UID 1000)
        chmod 644 "$CERT_DIR/key.pem"
        chmod 644 "$CERT_DIR/cert.pem"
    fi
else
    echo -e "${GREEN}  ✓ SSL certificates already exist${NC}"
    # Ensure correct permissions on existing certificates
    chmod 644 "$CERT_DIR/key.pem" 2>/dev/null
    chmod 644 "$CERT_DIR/cert.pem" 2>/dev/null
    # Check certificate expiry (warn if less than 30 days)
    CERT_EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_DIR/cert.pem" 2>/dev/null | cut -d= -f2)
    if [ -n "$CERT_EXPIRY" ]; then
        EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

        if [ $DAYS_LEFT -lt 30 ] && [ $DAYS_LEFT -gt 0 ]; then
            echo -e "${YELLOW}  ⚠️  SSL certificate expires in $DAYS_LEFT days${NC}"
            echo "     Consider regenerating: rm -rf $CERT_DIR && redeploy"
        elif [ $DAYS_LEFT -le 0 ]; then
            echo -e "${YELLOW}  ⚠️  SSL certificate has EXPIRED! Regenerating...${NC}"
            rm -f "$CERT_DIR/key.pem" "$CERT_DIR/cert.pem"
            openssl req -x509 -newkey rsa:4096 -nodes \
                -keyout "$CERT_DIR/key.pem" \
                -out "$CERT_DIR/cert.pem" \
                -days 365 \
                -subj "/C=US/ST=State/L=City/O=Personal/CN=$(hostname -I | awk '{print $1}')" \
                2>/dev/null && echo -e "${GREEN}  ✓ SSL certificate regenerated${NC}"
            # Set permissions readable by container user (voicebot runs as UID 1000)
            chmod 644 "$CERT_DIR/key.pem" 2>/dev/null
            chmod 644 "$CERT_DIR/cert.pem" 2>/dev/null
        else
            echo "     Valid for $DAYS_LEFT more days"
        fi
    fi
fi

# Build and start services (FIXED: separate build from up to prevent recreate race condition)
echo -e "${GREEN}🚀 Starting $ENVIRONMENT services...${NC}"
echo -e "${BLUE}🔍 DEBUG: Using docker compose command with:${NC}"
echo "  → Project: $PROJECT_NAME"
echo "  → Compose file: $COMPOSE_FILE"

# STEP 1: Pull pre-built images from GitHub Container Registry (30s vs 20min build)
echo -e "${BLUE}Step 1/3: Pulling CVE-validated images from GHCR...${NC}"

# Get current git commit SHA
GIT_SHA=$(git rev-parse HEAD)
echo "  → Git commit: $GIT_SHA"

# Log in to GHCR using GITHUB_TOKEN (if available)
if [ -n "$GITHUB_TOKEN" ]; then
    echo "  → Logging in to GitHub Container Registry..."
    echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin 2>&1 | grep -v "WARNING" || true
else
    echo "  ⚠️  GITHUB_TOKEN not set, trying public images..."
fi

# Disable exit-on-error temporarily for pull attempts
set +e

# Try pulling pre-built images
PULL_SUCCESS=true
REPO="ghcr.io/credentum/veris-memory"

# Helper function to pull and tag images
pull_image() {
    local service=$1
    local sha_tag="$REPO/$service:$GIT_SHA"
    local latest_tag="$REPO/$service:latest"

    echo "  → Pulling $service image..."

    # Try pulling by commit SHA first
    if docker pull "$sha_tag" >/dev/null 2>&1; then
        docker tag "$sha_tag" "$latest_tag"
        echo "  ✅ Pulled $service:$GIT_SHA"
        return 0
    else
        echo "  ⚠️  SHA image not found, trying :latest..."
        # Fallback to :latest tag
        if docker pull "$latest_tag" >/dev/null 2>&1; then
            echo "  ✅ Pulled $service:latest"
            return 0
        else
            echo "  ❌ Failed to pull $service image"
            return 1
        fi
    fi
}

# Pull all three images
pull_image "context-store" || PULL_SUCCESS=false
pull_image "api" || PULL_SUCCESS=false
pull_image "sentinel" || PULL_SUCCESS=false

# Re-enable exit-on-error
set -e

# Handle pull results
if [ "$PULL_SUCCESS" = "false" ]; then
    echo ""
    if [ "$ENVIRONMENT" = "development" ]; then
        # For development with volume mounts: STILL TRY TO START
        # The :latest images from previous successful CVE build should work
        # Code is mounted from host anyway, so image version doesn't matter much
        echo -e "${YELLOW}⚠️  Could not pull latest SHA images, but will try starting with existing images...${NC}"
        echo -e "${YELLOW}   Code is mounted from host via volumes, so this should still work.${NC}"
        echo -e "${YELLOW}   If services fail to start, wait for CVE workflow to push new images.${NC}"
        echo ""
        # Only fall back to build if there are NO images at all
        if ! docker images ghcr.io/credentum/veris-memory/context-store:latest -q 2>/dev/null | grep -q .; then
            echo -e "${RED}❌ No images available locally. Building is required (20+ minutes)...${NC}"
            echo -e "${RED}   To avoid this in future, ensure CVE workflow completes before deployment.${NC}"
            docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" build 2>&1 | tail -20
        fi
    else
        # For production: always build if pull fails (code must be in image)
        echo -e "${YELLOW}⚠️  Failed to pull pre-built images, falling back to local build...${NC}"
        echo -e "${YELLOW}   This will take 20+ minutes. Consider waiting for CVE workflow to complete.${NC}"
        echo ""
        docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" build 2>&1 | tail -20
    fi
else
    echo ""
    echo -e "${GREEN}  ✅ Successfully pulled all pre-built images from GHCR${NC}"
    if [ "$ENVIRONMENT" = "development" ]; then
        echo -e "${GREEN}     Code is mounted via volumes - instant updates, no rebuild needed!${NC}"
    else
        echo -e "${GREEN}     Deployment time: ~30 seconds (vs ~20 minutes for local build)${NC}"
    fi
fi

# STEP 2: Remove ALL containers for this project (prevents any recreate issues)
echo -e "${BLUE}Step 2/3: Removing ALL existing containers for clean start...${NC}"

# Remove ALL project containers (not just livekit/voice-bot)
echo "  → Stopping all $PROJECT_NAME containers..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down --remove-orphans 2>&1 | grep -E "(Stopping|Removing)" || echo "  → No containers to stop"

# Double-check livekit-server and voice-bot are gone
LIVEKIT_IDS=$(docker ps -a -q --filter "name=livekit-server" 2>/dev/null || true)
VOICEBOT_IDS=$(docker ps -a -q --filter "name=voice-bot" 2>/dev/null || true)
if [ -n "$LIVEKIT_IDS" ]; then
    echo "  → Force removing livekit-server containers"
    echo "$LIVEKIT_IDS" | xargs -r docker rm -f 2>&1 | grep -v "No such container" || true
fi
if [ -n "$VOICEBOT_IDS" ]; then
    echo "  → Force removing voice-bot containers"
    echo "$VOICEBOT_IDS" | xargs -r docker rm -f 2>&1 | grep -v "No such container" || true
fi

echo "  → Waiting 5 seconds for complete cleanup..."
sleep 5

# Verify no containers exist
REMAINING=$(docker ps -a --filter "name=$PROJECT_NAME" --format "{{.Names}}" 2>/dev/null || true)
REMAINING_FIXED=$(docker ps -a --filter "name=livekit-server" --filter "name=voice-bot" --format "{{.Names}}" 2>/dev/null || true)
if [ -n "$REMAINING" ] || [ -n "$REMAINING_FIXED" ]; then
    echo "  ⚠️  WARNING: Some containers still exist:"
    docker ps -a --filter "name=$PROJECT_NAME" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true
    docker ps -a --filter "name=livekit-server" --filter "name=voice-bot" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true
else
    echo "  ✅ All containers removed"
fi

# STEP 3: Start services (containers already removed in Step 2, so this is a clean start)
echo -e "${BLUE}Step 3/3: Starting services (clean start after removal, no rebuild)...${NC}"

# Final safety check: Ensure NO containers exist with our project name or fixed names
echo "  → Final container check before starting..."
EXISTING_PROJECT=$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT_NAME" 2>/dev/null | wc -l)
EXISTING_LIVEKIT=$(docker ps -aq --filter "name=livekit-server" 2>/dev/null | wc -l)
EXISTING_VOICEBOT=$(docker ps -aq --filter "name=voice-bot" 2>/dev/null | wc -l)

if [ "$EXISTING_PROJECT" -gt 0 ] || [ "$EXISTING_LIVEKIT" -gt 0 ] || [ "$EXISTING_VOICEBOT" -gt 0 ]; then
    echo "  ⚠️  WARNING: Found existing containers that should have been removed:"
    echo "    - Project containers: $EXISTING_PROJECT"
    echo "    - LiveKit: $EXISTING_LIVEKIT"
    echo "    - VoiceBot: $EXISTING_VOICEBOT"
    echo "  → Forcing removal of ALL containers..."

    # Nuclear option: remove all containers with our project label or fixed names
    docker ps -aq --filter "label=com.docker.compose.project=$PROJECT_NAME" | xargs -r docker rm -f 2>/dev/null || true
    docker ps -aq --filter "name=livekit-server" | xargs -r docker rm -f 2>/dev/null || true
    docker ps -aq --filter "name=voice-bot" | xargs -r docker rm -f 2>/dev/null || true

    echo "  → Waiting 5 seconds for ports to be released..."
    sleep 5
fi

# Use separate create and start commands to avoid the recreate race condition
echo "  → Creating containers without starting them..."
set +e
CREATE_OUTPUT=$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" create --no-build 2>&1)
CREATE_EXIT=$?
set -e

if [ $CREATE_EXIT -ne 0 ]; then
    echo -e "${RED}❌ Container creation failed:${NC}"
    echo "$CREATE_OUTPUT"
    exit 1
fi

echo "  → Starting created containers..."
set +e
START_OUTPUT=$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" start 2>&1)
START_EXIT=$?
set -e

if [ $START_EXIT -ne 0 ]; then
    echo -e "${RED}❌ Container start failed:${NC}"
    echo "$START_OUTPUT"
    COMPOSE_OUTPUT="$CREATE_OUTPUT\n$START_OUTPUT"
    COMPOSE_EXIT=$START_EXIT
else
    COMPOSE_OUTPUT="$CREATE_OUTPUT\n$START_OUTPUT"
    COMPOSE_EXIT=0
fi

if [ $COMPOSE_EXIT -ne 0 ]; then
    echo ""
    echo -e "${RED}========================================================================${NC}"
    echo -e "${RED}❌ Docker compose FAILED with exit code $COMPOSE_EXIT${NC}"
    echo -e "${RED}========================================================================${NC}"
    echo ""
    echo -e "${YELLOW}==================== Docker Compose Error Output ====================${NC}"
    echo "$COMPOSE_OUTPUT"
    echo -e "${YELLOW}=====================================================================${NC}"
    echo ""
    echo -e "${BLUE}Debugging information:${NC}"
    echo "  → Docker version: $(docker --version 2>/dev/null || echo 'Not found')"
    echo "  → Docker compose version: $(docker compose version 2>/dev/null || echo 'Not found')"
    echo "  → Current directory: $(pwd)"
    echo "  → Project name: $PROJECT_NAME"
    echo "  → Compose file: $COMPOSE_FILE"
    echo "  → Compose file exists: $(test -f "$COMPOSE_FILE" && echo 'Yes' || echo 'No')"
    echo "  → Dockerfile exists: $(test -f 'dockerfiles/Dockerfile' && echo 'Yes' || echo 'No')"
    echo ""
    echo -e "${BLUE}Validating compose file syntax:${NC}"
    docker compose -f "$COMPOSE_FILE" config --quiet 2>&1 || docker compose -f "$COMPOSE_FILE" config 2>&1 | head -50
    echo ""
    echo -e "${BLUE}Checking .env file:${NC}"
    if [ -f .env ]; then
        echo "  → .env file exists"
        echo "  → NEO4J_PASSWORD set: $(grep -q '^NEO4J_PASSWORD=' .env && echo 'Yes' || echo 'No')"
        echo "  → .env file size: $(wc -l < .env) lines"
        echo "  → First 10 env vars:"
        head -10 .env | sed 's/=.*/=***/'
    else
        echo "  → .env file missing!"
    fi
    echo ""
    echo -e "${RED}Deployment failed. Please review the error output above.${NC}"
    exit 1
else
    echo "$COMPOSE_OUTPUT"
    echo -e "${GREEN}✅ Docker Compose completed successfully${NC}"
fi

# Deploy voice platform services (voice-bot + livekit)
if [ -f "docker-compose.voice.yml" ]; then
    echo ""
    echo -e "${CYAN}🎙️  Deploying voice platform...${NC}"
    docker compose -p "$PROJECT_NAME" -f docker-compose.yml -f docker-compose.voice.yml up -d --build voice-bot livekit 2>&1
    echo -e "${GREEN}✅ Voice platform deployed${NC}"
else
    echo -e "${YELLOW}⚠️  docker-compose.voice.yml not found, skipping voice-bot deployment${NC}"
fi

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
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs --tail=50
    exit 1
fi

# CRITICAL: Trigger hot reload for volume-mounted code
# Problem: git pull updates files BEFORE containers start, so uvicorn's --reload
# doesn't detect any changes (files were already new when it started).
# Solution: Touch a source file to trigger uvicorn's file watcher and force reload.
if [ "$ENVIRONMENT" = "development" ]; then
    echo -e "${BLUE}🔄 Triggering hot reload for volume-mounted code...${NC}"

    # Touch __init__.py to trigger uvicorn's file watcher
    touch src/__init__.py 2>/dev/null || true
    touch src/mcp_server/__init__.py 2>/dev/null || true
    touch src/backends/__init__.py 2>/dev/null || true

    echo "  → Triggered file change, waiting 5s for uvicorn to reload..."
    sleep 5

    # Verify services are still healthy after reload
    if curl -f "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Hot reload completed, services healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Services reloading, waiting additional 10s...${NC}"
        sleep 10
    fi
fi

# Bootstrap Qdrant collection if needed
echo -e "${BLUE}🔧 Bootstrapping Qdrant collection...${NC}"
if [ -f "ops/bootstrap/qdrant_bootstrap.py" ]; then
    sleep 5  # Give services time to fully start
    python3 ops/bootstrap/qdrant_bootstrap.py --qdrant-url http://localhost:$QDRANT_PORT --ensure-collection || echo "  → Bootstrap completed or collection already exists"
else
    echo -e "${YELLOW}⚠️  Bootstrap script not found, skipping${NC}"
fi

# Initialize Neo4j schema (constraints and indexes)
echo ""
echo -e "${BLUE}🔧 Initializing Neo4j schema...${NC}"
if [ -f "scripts/init-neo4j-schema.sh" ]; then
    chmod +x scripts/init-neo4j-schema.sh
    # Set environment variables for the script
    export NEO4J_CONTAINER="${PROJECT_NAME}-neo4j-1"
    export NEO4J_HOST="localhost"
    export NEO4J_PORT=$NEO4J_BOLT_PORT
    export NEO4J_USER="neo4j"
    # NEO4J_PASSWORD already set from environment

    if ./scripts/init-neo4j-schema.sh; then
        echo -e "${GREEN}✅ Schema initialization completed successfully${NC}"
    else
        SCHEMA_EXIT_CODE=$?
        echo -e "${YELLOW}⚠️  Schema initialization exited with code $SCHEMA_EXIT_CODE${NC}"
        echo -e "${YELLOW}   Deployment will continue, but verify schema manually if needed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Neo4j schema initialization script not found${NC}"
    echo -e "${YELLOW}   Attempting manual initialization...${NC}"

    # Fallback: Run schema init via docker exec
    NEO4J_CONTAINER=$(docker ps --filter "name=${PROJECT_NAME}-neo4j" --format "{{.Names}}" | head -1)
    if [ -n "$NEO4J_CONTAINER" ]; then
        echo "   Found Neo4j container: $NEO4J_CONTAINER"

        # Create constraint with proper error handling
        CONSTRAINT_OUTPUT=$(docker exec -e NEO4J_PASSWORD="$NEO4J_PASSWORD" "$NEO4J_CONTAINER" \
            sh -c 'cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "CREATE CONSTRAINT context_id_unique IF NOT EXISTS FOR (c:Context) REQUIRE c.id IS UNIQUE"' 2>&1)
        CONSTRAINT_RESULT=$?

        if [ $CONSTRAINT_RESULT -eq 0 ]; then
            echo -e "${GREEN}   ✅ Context constraint created${NC}"
        elif echo "$CONSTRAINT_OUTPUT" | grep -qi "already exists"; then
            echo "   ℹ️  Context constraint already exists (idempotent)"
        else
            echo -e "${YELLOW}   ⚠️  Constraint creation failed: $CONSTRAINT_OUTPUT${NC}"
        fi

        # Create index with proper error handling
        INDEX_OUTPUT=$(docker exec -e NEO4J_PASSWORD="$NEO4J_PASSWORD" "$NEO4J_CONTAINER" \
            sh -c 'cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "CREATE INDEX context_type_idx IF NOT EXISTS FOR (c:Context) ON (c.type)"' 2>&1)
        INDEX_RESULT=$?

        if [ $INDEX_RESULT -eq 0 ]; then
            echo -e "${GREEN}   ✅ Context index created${NC}"
        elif echo "$INDEX_OUTPUT" | grep -qi "already exists"; then
            echo "   ℹ️  Context index already exists (idempotent)"
        else
            echo -e "${YELLOW}   ⚠️  Index creation failed: $INDEX_OUTPUT${NC}"
        fi

        echo -e "${GREEN}   ✅ Basic schema initialization attempted${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Neo4j container not found, skipping schema init${NC}"
    fi
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
if curl -s http://localhost:$QDRANT_PORT/ | grep -q "qdrant"; then
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

echo -n "  → Voice-Bot (port 8002): "
if curl -k -s https://localhost:8002/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Healthy (HTTPS)${NC}"
elif curl -s http://localhost:8002/health > /dev/null 2>&1; then
    echo -e "${YELLOW}✓ Healthy (HTTP - HTTPS not configured)${NC}"
else
    echo -e "${YELLOW}⚠ Not running${NC}"
fi

echo -n "  → LiveKit (port 7880): "
if curl -s http://localhost:7880/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${YELLOW}⚠ Not running${NC}"
fi

# Update firewall rules to ensure all service ports are accessible
echo ""
echo -e "${BLUE}🔥 Updating firewall rules for service ports...${NC}"
if [ -f "scripts/update-firewall-rules.sh" ]; then
    # Check if we have sudo access
    if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
        echo "  → Running firewall update with sudo..."
        if sudo bash scripts/update-firewall-rules.sh 2>&1 | tee /tmp/firewall-update.log; then
            echo -e "${GREEN}✅ Firewall rules updated successfully${NC}"

            # Show which ports are now open
            echo ""
            echo -e "${CYAN}📋 Open service ports:${NC}"
            sudo ufw status | grep -E "8000|8001|8002|8080|9090" || echo "  → UFW not configured or not showing expected ports"
        else
            echo -e "${YELLOW}⚠️  Firewall update encountered issues (non-blocking)${NC}"
            echo "  → Check /tmp/firewall-update.log for details"
            echo "  → Services may not be accessible externally"
            echo "  → Manual fix: sudo bash scripts/update-firewall-rules.sh"
        fi
    else
        echo -e "${YELLOW}⚠️  Sudo not available or requires password${NC}"
        echo "  → Firewall rules NOT updated automatically"
        echo "  → Manual step required: sudo bash scripts/update-firewall-rules.sh"
        echo "  → Services may not be accessible externally until firewall is configured"
    fi
else
    echo -e "${YELLOW}⚠️  Firewall update script not found at scripts/update-firewall-rules.sh${NC}"
    echo "  → Skipping automatic firewall configuration"
    echo "  → Ensure ports are manually opened if needed"
fi

# Show running containers
echo ""
echo -e "${BLUE}📊 $ENVIRONMENT containers running:${NC}"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps

# Generate deployment report
echo ""
echo -e "${BLUE}📊 Generating deployment report...${NC}"
if [ -f "scripts/deployment-report.sh" ]; then
    chmod +x scripts/deployment-report.sh
    ./scripts/deployment-report.sh "$ENVIRONMENT"
    
    # Check the exit code
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Deployment report generated successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Deployment report indicates issues${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Deployment report script not found${NC}"
fi

# Environment-specific instructions
echo ""
echo -e "${GREEN}🎉 $ENVIRONMENT deployment completed!${NC}"
echo "================================================"
if [ "$ENVIRONMENT" = "development" ]; then
    echo "Development services available at:"
    echo "  • MCP Server: http://localhost:8000"
    echo "  • REST API: http://localhost:8001"
    echo "  • Voice-Bot: https://localhost:8002 (HTTPS with self-signed cert)"
    echo "  • Dashboard: http://localhost:8080"
    echo "  • Sentinel: http://localhost:9090"
    echo "  • Qdrant: http://localhost:$QDRANT_PORT"
    echo "  • Neo4j: http://localhost:$NEO4J_HTTP_PORT"
    echo "  • Redis: localhost:$REDIS_PORT"
    echo "  • LiveKit: http://localhost:7880"
    echo ""
    echo "External access (if firewall configured):"
    echo "  • API Docs: http://$(hostname -I | awk '{print $1}'):8001/docs"
    echo "  • Voice UI: https://$(hostname -I | awk '{print $1}'):8002/ui (accept SSL warning)"
    echo "  • Voice Docs: https://$(hostname -I | awk '{print $1}'):8002/docs"
    echo "  • Dashboard: http://$(hostname -I | awk '{print $1}'):8080"
    echo ""
    echo "Run tests with:"
    echo "  python ops/smoke/smoke_runner.py --api-url http://localhost:$API_PORT --qdrant-url http://localhost:$QDRANT_PORT"
else
    echo "Production services available at:"
    echo "  • MCP Server: http://localhost:8000"
    echo "  • REST API: http://localhost:8001"
    echo "  • Voice-Bot: https://localhost:8002 (HTTPS with self-signed cert)"
    echo "  • Dashboard: http://localhost:8080"
    echo "  • Sentinel: http://localhost:9090"
    echo "  • Qdrant: http://localhost:$QDRANT_PORT"
    echo "  • Neo4j: http://localhost:$NEO4J_HTTP_PORT"
    echo "  • Redis: localhost:$REDIS_PORT"
    echo "  • LiveKit: http://localhost:7880"
    echo ""
    echo "Run tests with:"
    echo "  python ops/smoke/smoke_runner.py"
fi
echo ""
echo -e "${CYAN}📝 Note: Firewall configuration attempted during deployment${NC}"
echo "  → If services not accessible externally, run: sudo bash scripts/update-firewall-rules.sh"

# Output final JSON report location
LATEST_REPORT="/opt/veris-memory/deployment-reports/latest-${ENVIRONMENT}.json"
if [ -f "$LATEST_REPORT" ]; then
    echo ""
    echo -e "${BLUE}📄 Latest deployment report: $LATEST_REPORT${NC}"
    
    # Create a symlink to the latest report
    ln -sf "$(ls -t /opt/veris-memory/deployment-reports/deployment-${ENVIRONMENT}-*.json 2>/dev/null | head -1)" "$LATEST_REPORT" 2>/dev/null || true
fi