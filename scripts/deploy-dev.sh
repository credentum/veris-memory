#!/bin/bash
# Development Deployment Script
# Called by .github/workflows/deploy-dev.yml
# Expects environment variables to be set for all secrets

set -e

# SIMPLE PASSWORD HANDLING:
# ========================
# Store the password as PLAIN TEXT in GitHub Secrets
# GitHub Secrets are already encrypted and secure
# No need for base64 encoding - it just adds complexity

# Verify required environment variables exist
if [ -z "$NEO4J_PASSWORD" ]; then
  echo "❌ ERROR: NEO4J_PASSWORD not set!"
  exit 1
fi

if [ -z "$HETZNER_USER" ]; then
  echo "❌ ERROR: HETZNER_USER not set!"
  exit 1
fi

if [ -z "$HETZNER_HOST" ]; then
  echo "❌ ERROR: HETZNER_HOST not set!"
  exit 1
fi

echo "✅ Required environment variables are set"

# Pass environment variables and execute deployment on remote server
# NOTE: Using unquoted heredoc to allow variable expansion
# SSH keepalive options prevent timeout during long Docker builds
ssh -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=~/.ssh/known_hosts \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=20 \
    -i ~/.ssh/id_ed25519 \
    $HETZNER_USER@$HETZNER_HOST << EOSSH
  set -e

  echo "🔵 DEVELOPMENT DEPLOYMENT STARTING"
  echo "Timestamp: \$(date '+%Y-%m-%d %H:%M:%S UTC')"
  echo "Host: \$(hostname)"
  echo "User: \$(whoami)"

  # GitHub Container Registry credentials (for pulling pre-built images)
  export GITHUB_TOKEN='$GITHUB_TOKEN'
  export GITHUB_ACTOR='$GITHUB_ACTOR'

  # SECURITY: Generate Redis password if not provided
  if [ -z '$REDIS_PASSWORD' ]; then
    echo "🔐 Generating secure Redis password..."
    export REDIS_PASSWORD=\$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
  else
    export REDIS_PASSWORD='$REDIS_PASSWORD'
  fi

  # Export all secrets as environment variables for scripts to use
  export NEO4J_PASSWORD='$NEO4J_PASSWORD'
  export NEO4J_RO_PASSWORD='$NEO4J_RO_PASSWORD'
  export TELEGRAM_BOT_TOKEN='$TELEGRAM_BOT_TOKEN'
  export TELEGRAM_CHAT_ID='$TELEGRAM_CHAT_ID'
  export API_KEY_MCP='$API_KEY_MCP'
  export LIVEKIT_API_KEY='$LIVEKIT_API_KEY'
  export LIVEKIT_API_SECRET='$LIVEKIT_API_SECRET'
  export LIVEKIT_API_WEBSOCKET='$LIVEKIT_API_WEBSOCKET'
  export API_KEY_VOICEBOT='$API_KEY_VOICEBOT'
  export OPENAI_API_KEY='$OPENAI_API_KEY'
  export OPENROUTER_API_KEY='$OPENROUTER_API_KEY'
  export SENTINEL_API_KEY='$SENTINEL_API_KEY'
  export HOST_CHECK_SECRET='$HOST_CHECK_SECRET'
  export VERIS_HERALD_API_KEY='$VERIS_HERALD_API_KEY'
  export VERIS_RESEARCH_API_KEY='$VERIS_RESEARCH_API_KEY'
  export VERIS_MEMORY_API_KEY='$VERIS_MEMORY_API_KEY'
  export ENVIRONMENT=development

  # Verify critical environment variables
  if [ -z "\$NEO4J_PASSWORD" ]; then
    echo "❌ ERROR: NEO4J_PASSWORD not exported to remote server!"
    exit 1
  fi
  echo "✅ Environment variables exported successfully"

  # Check if running as root
  if [ "\$(id -u)" -eq 0 ]; then
    echo "⚠️  WARNING: Running as root. Consider using a non-root user for deployments."
  fi

  cd /opt/veris-memory || exit 1

  # Backup current state before deployment
  echo "📦 Creating pre-deployment backup..."
  BACKUP_DIR="/opt/veris-memory-backups/\$(date +%Y%m%d-%H%M%S)"
  mkdir -p "\$BACKUP_DIR"

  # Backup .env file (contains secrets)
  if [ -f .env ]; then
    cp .env "\$BACKUP_DIR/.env.backup"
    echo "✅ Backed up .env to \$BACKUP_DIR"
  fi

  # Backup docker-compose.yml
  if [ -f docker-compose.yml ]; then
    cp docker-compose.yml "\$BACKUP_DIR/docker-compose.yml.backup"
  fi

  # Pull latest code
  echo "📥 Pulling latest code from main branch..."
  git fetch origin
  git checkout main
  git reset --hard origin/main
  echo "✅ Code updated to latest version: \$(git rev-parse --short HEAD)"

  # Show what changed
  echo "📝 Recent commits:"
  git log --oneline -5

  # BACKUP PHASE - Preserve data before cleanup (non-fatal)
  # PR #388: Make backup non-fatal - don't fail deployment if nothing to backup
  # This can happen when containers aren't running from a previous failed deployment
  echo "💾 Creating backup before cleanup..."
  if [ -f "/opt/veris-memory/scripts/backup-restore-integration.sh" ]; then
    if bash /opt/veris-memory/scripts/backup-restore-integration.sh backup dev; then
      echo "✅ Backup completed successfully"
    else
      echo "⚠️  Backup failed or nothing to backup (non-fatal, continuing deployment)"
    fi
  else
    echo "⚠️  Backup script not found, skipping backup"
  fi

  # Extensive cleanup
  echo "🧹 Performing comprehensive cleanup..."

  # Stop all containers first
  echo "🛑 Stopping all containers gracefully..."
  docker compose -p veris-memory-dev down --remove-orphans 2>/dev/null || true

  # CRITICAL: Also stop any containers using the OLD project name (without -dev)
  echo "🧹 Cleaning up old project name containers..."
  docker compose -p veris-memory down --remove-orphans 2>/dev/null || true

  # Remove old networks to force recreation with correct project name
  echo "🌐 Removing old Docker networks..."
  docker network rm veris-memory_context-store-network 2>/dev/null && echo "  ✓ Removed: veris-memory_context-store-network" || echo "  ℹ️ Already removed"
  docker network rm veris-memory_voice-network 2>/dev/null && echo "  ✓ Removed: veris-memory_voice-network" || echo "  ℹ️ Already removed"

  # Force stop any remaining containers with our project name
  # PR #384: Use -f flag and remove by ID to handle stuck containers
  echo "🛑 Force stopping any remaining veris-memory containers..."
  docker ps -a --filter "name=veris-memory" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
  docker ps -a --filter "name=veris-memory" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true

  # PR #384: Also remove by container ID to handle name conflicts
  echo "🧹 Removing containers by ID (handles name conflicts)..."
  VERIS_CONTAINERS=\$(docker ps -aq --filter "name=veris-memory" 2>/dev/null || true)
  if [ -n "\$VERIS_CONTAINERS" ]; then
    echo "   Found \$(echo "\$VERIS_CONTAINERS" | wc -l) containers to remove"
    echo "\$VERIS_CONTAINERS" | xargs -r docker rm -f 2>/dev/null || true
  fi

  # CRITICAL: Remove ALL instances of fixed-name containers
  echo "🛑 Stopping fixed-name containers (livekit-server, voice-bot)..."
  LIVEKIT_IDS=\$(docker ps -a -q --filter "name=livekit-server" 2>/dev/null || true)
  VOICEBOT_IDS=\$(docker ps -a -q --filter "name=voice-bot" 2>/dev/null || true)

  if [ -n "\$LIVEKIT_IDS" ] || [ -n "\$VOICEBOT_IDS" ]; then
    echo "  → Found containers, removing by ID..."
    [ -n "\$LIVEKIT_IDS" ] && echo "\$LIVEKIT_IDS" | xargs -r docker rm -f 2>&1 | grep -v "No such container" || true
    [ -n "\$VOICEBOT_IDS" ] && echo "\$VOICEBOT_IDS" | xargs -r docker rm -f 2>&1 | grep -v "No such container" || true
  else
    echo "  → No livekit/voice-bot containers found"
  fi

  # Kill non-docker processes on livekit ports
  for port in 7880 7882 5349; do
    PID=\$(lsof -ti tcp:\$port 2>/dev/null || true)
    [ -n "\$PID" ] && kill -9 \$PID 2>/dev/null || true
  done

  echo "⏳ Waiting 10 seconds for port release..."
  sleep 10

  # Stop containers by port (more aggressive)
  for port in 8000 8001 8080 6333 7474 7687 6379 7880 7882 3478 5349; do
    container=\$(docker ps --filter "publish=\$port" --format "{{.Names}}" 2>/dev/null | head -1)
    if [ -n "\$container" ]; then
      echo "Stopping container on port \$port: \$container"
      docker stop "\$container" 2>/dev/null || true
      docker rm "\$container" 2>/dev/null || true
    fi
  done

  # Prune system (removes dangling images/containers)
  echo "🗑️  Pruning Docker system..."
  docker system prune -f --volumes 2>/dev/null || true

  # CRITICAL: Remove old veris-memory images to prevent disk space accumulation
  # Each image is 7-8GB, so old versions quickly consume disk space
  echo "🧹 Removing old veris-memory Docker images..."

  # Get disk usage before cleanup
  DISK_BEFORE=\$(df -h /var/lib/docker 2>/dev/null | tail -1 | awk '{print \$4}' || echo "unknown")
  echo "   Disk space before image cleanup: \$DISK_BEFORE available"

  # Remove all unused images (not just dangling) - this is safe after containers are stopped
  echo "   Removing unused images..."
  docker image prune -a -f 2>/dev/null || true

  # Specifically target old veris-memory images from GHCR
  echo "   Cleaning GHCR veris-memory images..."
  for repo in api context-store sentinel voice-bot; do
    # Get all image IDs for this repo except the one tagged :latest
    OLD_IMAGES=\$(docker images "ghcr.io/credentum/veris-memory/\$repo" --format "{{.ID}} {{.Tag}}" 2>/dev/null | grep -v "latest" | awk '{print \$1}' || true)
    if [ -n "\$OLD_IMAGES" ]; then
      echo "   Removing old \$repo images..."
      echo "\$OLD_IMAGES" | xargs -r docker rmi -f 2>/dev/null || true
    fi
  done

  # Also clean up any locally built images with old tags
  echo "   Cleaning locally built veris-memory images..."
  docker images --filter "reference=*veris-memory*" --format "{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}}" 2>/dev/null | \
    grep -E "(weeks|months) ago" | awk '{print \$2}' | xargs -r docker rmi -f 2>/dev/null || true

  # Get disk usage after cleanup
  DISK_AFTER=\$(df -h /var/lib/docker 2>/dev/null | tail -1 | awk '{print \$4}' || echo "unknown")
  echo "   Disk space after image cleanup: \$DISK_AFTER available"

  # Wait for cleanup
  echo "⏳ Waiting 5 seconds for cleanup to complete..."
  sleep 5

  # Verify cleanup
  remaining_containers=\$(docker ps -a --filter "name=veris-memory" --format "{{.Names}}" | wc -l)
  remaining_volumes=\$(docker volume ls --filter "name=veris-memory" --format "{{.Name}}" | wc -l)
  remaining_images=\$(docker images --filter "reference=*veris-memory*" --format "{{.Repository}}" 2>/dev/null | wc -l || echo "0")

  echo "📊 Cleanup summary:"
  echo "  - Remaining containers: \$remaining_containers"
  echo "  - Remaining volumes: \$remaining_volumes"
  echo "  - Remaining images: \$remaining_images"

  if [ "\$remaining_containers" -eq 0 ] && [ "\$remaining_volumes" -eq 0 ]; then
    echo "🎉 Complete cleanup achieved!"
  else
    echo "⚠️  Some resources may still exist, but deployment will continue"
    docker ps -a --filter "name=veris-memory-dev" --format "table {{.Names}}\\t{{.Status}}" || true
  fi

  # =============================================================================
  # CONSOLIDATED DEPLOYMENT (Issue #416)
  # All .env creation and deployment logic in one place - no more fragmentation
  # =============================================================================

  # Dev uses volume-mounted compose file for fast deployments
  COMPOSE_FILE="docker-compose.deploy-dev.yml"
  echo "📦 Using volume-mounted compose for dev environment"
  echo "   → Code changes are instant (mounted from host)"
  echo "   → Hot reload enabled (auto-restart on file changes)"

  # Setup base environment file
  if [ -f ".env.dev" ]; then
    cp .env.dev .env
  elif [ -f ".env.template" ]; then
    cp .env.template .env
  else
    echo "# Auto-generated environment file" > .env
  fi

  # Remove ALL managed variables to ensure clean state (no duplicates)
  echo "🗑️  Removing managed variables from .env to prevent duplicates..."
  if [ -f .env ]; then
    # Create a clean .env by removing all managed variables
    sed -i '/^NEO4J/d; /^REDIS_PASSWORD/d; /^TELEGRAM/d; /^API_KEY/d; /^VERIS_/d; /^LIVEKIT/d; /^VOICE_BOT/d; /^STT_/d; /^TTS_/d; /^OPENAI_API_KEY/d; /^OPENROUTER_API_KEY/d; /^HYDE_/d; /^CROSS_ENCODER/d; /^SENTINEL/d; /^HOST_CHECK/d; /^AUTH_REQUIRED/d; /^ENVIRONMENT=/d; /^ENABLE_MCP/d; /^MCP_RETRY/d; /^STRICT_EMBEDDINGS/d; /^EMBEDDING_DIM/d; /^QDRANT_COLLECTION/d; /^SSL_/d; /^ENABLE_VOICE/d; /^ENABLE_FACT/d; /^ENABLE_CONVERSATION/d' .env
  fi

  # SECURITY: Validate required secrets before writing to .env
  echo "🔐 Validating required secrets..."
  VALIDATION_FAILED=0

  if [ -z "\$NEO4J_PASSWORD" ]; then
    echo "❌ ERROR: NEO4J_PASSWORD is not set or empty!"
    VALIDATION_FAILED=1
  fi

  if [ -z "\$NEO4J_RO_PASSWORD" ]; then
    echo "❌ ERROR: NEO4J_RO_PASSWORD is not set or empty!"
    VALIDATION_FAILED=1
  fi

  if [ -z "\$REDIS_PASSWORD" ]; then
    echo "❌ ERROR: REDIS_PASSWORD is not set or empty!"
    VALIDATION_FAILED=1
  fi

  if [ -z "\$API_KEY_MCP" ]; then
    echo "❌ ERROR: API_KEY_MCP is not set or empty!"
    VALIDATION_FAILED=1
  fi

  if [ -z "\$SENTINEL_API_KEY" ]; then
    echo "❌ ERROR: SENTINEL_API_KEY is not set or empty!"
    VALIDATION_FAILED=1
  fi

  if [ \$VALIDATION_FAILED -eq 1 ]; then
    echo ""
    echo "❌ DEPLOYMENT FAILED: Required secrets are missing!"
    echo "Fix by adding these secrets to GitHub Secrets:"
    echo "  https://github.com/credentum/veris-memory/settings/secrets/actions"
    exit 1
  fi
  echo "✅ All required secrets validated"

  # =============================================================================
  # CREATE COMPLETE .env FILE (Single Source of Truth)
  # All secrets written here - no more fragmented secret management
  # =============================================================================
  echo "📝 Creating .env file with ALL secrets..."
  {
    printf "# =============================================================================\\n"
    printf "# Veris Memory Environment Configuration\\n"
    printf "# Generated by deploy-dev.sh (Issue #416: Consolidated deployment)\\n"
    printf "# =============================================================================\\n\\n"

    # Database Credentials
    printf "# Neo4j Database\\n"
    printf "NEO4J_PASSWORD=%s\\n" "\$NEO4J_PASSWORD"
    printf "NEO4J_RO_PASSWORD=%s\\n" "\$NEO4J_RO_PASSWORD"
    printf "NEO4J_AUTH=neo4j/%s\\n" "\$NEO4J_PASSWORD"

    # Redis Authentication
    printf "\\n# Redis Authentication\\n"
    printf "REDIS_PASSWORD=%s\\n" "\$REDIS_PASSWORD"

    # MCP Server Authentication
    printf "\\n# MCP Server Authentication\\n"
    printf "API_KEY_MCP=%s\\n" "\$API_KEY_MCP"
    printf "AUTH_REQUIRED=true\\n"
    printf "ENVIRONMENT=development\\n"

    # Telegram Notifications
    if [ -n "\$TELEGRAM_BOT_TOKEN" ]; then
      printf "\\n# Telegram Notifications\\n"
      printf "TELEGRAM_BOT_TOKEN=%s\\n" "\$TELEGRAM_BOT_TOKEN"
      [ -n "\$TELEGRAM_CHAT_ID" ] && printf "TELEGRAM_CHAT_ID=%s\\n" "\$TELEGRAM_CHAT_ID"
    fi

    # Voice Platform Configuration
    printf "\\n# Voice Platform Configuration\\n"
    [ -n "\$LIVEKIT_API_KEY" ] && printf "LIVEKIT_API_KEY=%s\\n" "\$LIVEKIT_API_KEY"
    [ -n "\$LIVEKIT_API_SECRET" ] && printf "LIVEKIT_API_SECRET=%s\\n" "\$LIVEKIT_API_SECRET"
    [ -n "\$LIVEKIT_API_WEBSOCKET" ] && printf "LIVEKIT_API_WEBSOCKET=%s\\n" "\$LIVEKIT_API_WEBSOCKET"
    [ -n "\$API_KEY_VOICEBOT" ] && printf "API_KEY_VOICEBOT=%s\\n" "\$API_KEY_VOICEBOT"
    printf "VOICE_BOT_AUTHOR_PREFIX=voice_bot\\n"
    printf "ENABLE_MCP_RETRY=true\\n"
    printf "MCP_RETRY_ATTEMPTS=3\\n"
    printf "ENABLE_VOICE_COMMANDS=true\\n"
    printf "ENABLE_FACT_STORAGE=true\\n"
    printf "ENABLE_CONVERSATION_TRACE=true\\n"
    printf "SSL_KEYFILE=/app/certs/key.pem\\n"
    printf "SSL_CERTFILE=/app/certs/cert.pem\\n"

    # OpenAI for STT/TTS
    if [ -n "\$OPENAI_API_KEY" ]; then
      printf "\\n# OpenAI (STT/TTS)\\n"
      printf "OPENAI_API_KEY=%s\\n" "\$OPENAI_API_KEY"
      printf "STT_PROVIDER=whisper\\n"
      printf "STT_API_KEY=%s\\n" "\$OPENAI_API_KEY"
      printf "TTS_PROVIDER=openai\\n"
      printf "TTS_API_KEY=%s\\n" "\$OPENAI_API_KEY"
    fi

    # HyDE Configuration (OpenRouter)
    printf "\\n# HyDE Query Expansion\\n"
    if [ -n "\$OPENROUTER_API_KEY" ]; then
      printf "OPENROUTER_API_KEY=%s\\n" "\$OPENROUTER_API_KEY"
      printf "HYDE_ENABLED=true\\n"
      printf "HYDE_API_PROVIDER=openrouter\\n"
      printf "HYDE_MODEL=mistralai/mistral-small-3.1-24b-instruct-2503\\n"
    else
      printf "HYDE_ENABLED=false\\n"
    fi

    # Cross-Encoder Reranker
    printf "\\n# Cross-Encoder Reranker\\n"
    printf "CROSS_ENCODER_RERANKER_ENABLED=true\\n"
    printf "CROSS_ENCODER_TOP_K=50\\n"
    printf "CROSS_ENCODER_RETURN_K=10\\n"

    # Sentinel Monitoring
    printf "\\n# Sentinel Monitoring\\n"
    printf "SENTINEL_API_KEY=%s\\n" "\$SENTINEL_API_KEY"
    [ -n "\$HOST_CHECK_SECRET" ] && printf "HOST_CHECK_SECRET=%s\\n" "\$HOST_CHECK_SECRET"

    # Veris API Keys
    printf "\\n# Veris API Keys\\n"
    [ -n "\$VERIS_HERALD_API_KEY" ] && printf "VERIS_HERALD_API_KEY=%s\\n" "\$VERIS_HERALD_API_KEY"
    [ -n "\$VERIS_RESEARCH_API_KEY" ] && printf "VERIS_RESEARCH_API_KEY=%s\\n" "\$VERIS_RESEARCH_API_KEY"
    [ -n "\$VERIS_MEMORY_API_KEY" ] && printf "VERIS_MEMORY_API_KEY=%s\\n" "\$VERIS_MEMORY_API_KEY"

    # Cache and Embedding Configuration
    printf "\\n# Cache and Embedding Configuration\\n"
    printf "VERIS_CACHE_TTL_SECONDS=300\\n"
    printf "STRICT_EMBEDDINGS=false\\n"
    printf "EMBEDDING_DIM=384\\n"
    printf "QDRANT_COLLECTION_NAME=context_embeddings\\n"

  } >> .env 2>/dev/null

  # Verify critical secrets were written
  echo "🔍 Verifying .env configuration..."
  VERIFY_FAILED=0
  for secret in NEO4J_PASSWORD REDIS_PASSWORD API_KEY_MCP SENTINEL_API_KEY; do
    if grep -q "^\${secret}=" .env; then
      echo "  ✓ \$secret"
    else
      echo "  ✗ \$secret MISSING!"
      VERIFY_FAILED=1
    fi
  done

  if [ \$VERIFY_FAILED -eq 1 ]; then
    echo "❌ ERROR: Critical secrets missing from .env!"
    exit 1
  fi
  echo "✅ All secrets written to .env"

  # =============================================================================
  # SSL CERTIFICATES
  # =============================================================================
  echo "🔐 Checking SSL certificates for voice-bot..."
  CERT_DIR="/opt/veris-memory/voice-bot/certs"
  mkdir -p "\$CERT_DIR"

  if [ ! -f "\$CERT_DIR/key.pem" ] || [ ! -f "\$CERT_DIR/cert.pem" ]; then
    echo "📜 Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:4096 -nodes \
      -keyout "\$CERT_DIR/key.pem" \
      -out "\$CERT_DIR/cert.pem" \
      -days 365 \
      -subj "/C=US/ST=State/L=City/O=Personal/CN=\$(hostname -I | awk '{print \$1}')" \
      2>/dev/null && echo "✅ SSL certificates generated" || echo "⚠️  Certificate generation failed"
    chmod 600 "\$CERT_DIR/key.pem" 2>/dev/null
    chmod 644 "\$CERT_DIR/cert.pem" 2>/dev/null
  else
    echo "✅ SSL certificates already exist"
  fi

  # =============================================================================
  # PULL IMAGES AND START SERVICES
  # =============================================================================
  echo "🏗️  Starting deployment..."

  # Login to GHCR
  if [ -n "\$GITHUB_TOKEN" ]; then
    echo "🔐 Logging in to GitHub Container Registry..."
    echo "\$GITHUB_TOKEN" | docker login ghcr.io -u "\$GITHUB_ACTOR" --password-stdin
  fi

  # Pull images from GHCR
  echo "📥 Pulling images from GHCR..."
  if docker compose -p veris-memory-dev -f \$COMPOSE_FILE pull 2>/dev/null; then
    echo "✅ Images pulled from GHCR"

    # Build qdrant locally (custom Dockerfile)
    echo "🔨 Building qdrant image locally..."
    docker compose -p veris-memory-dev -f \$COMPOSE_FILE build qdrant

    # Start services
    echo "🚀 Starting services..."
    docker compose -p veris-memory-dev -f \$COMPOSE_FILE up -d --force-recreate --no-build
  else
    echo "⚠️  GHCR pull failed, building locally..."
    docker compose -p veris-memory-dev -f \$COMPOSE_FILE up -d --force-recreate --build
  fi

  # Deploy voice-bot if available
  if [ -f "docker-compose.voice.yml" ]; then
    echo "🎙️  Deploying voice platform..."
    docker compose -p veris-memory-dev -f \$COMPOSE_FILE -f docker-compose.voice.yml up -d --build voice-bot
  fi

  # Logout from GHCR
  [ -n "\$GITHUB_TOKEN" ] && docker logout ghcr.io 2>/dev/null

  echo "⏳ Waiting for services to start..."
  sleep 10

  # Show service status
  echo "📊 Service Status:"
  docker compose -p veris-memory-dev -f \$COMPOSE_FILE ps

  # =============================================================================
  # NEO4J SCHEMA INITIALIZATION
  # =============================================================================
  echo "🔧 Initializing Neo4j schema..."
  if [ -f "scripts/init-neo4j-schema.sh" ]; then
    chmod +x scripts/init-neo4j-schema.sh
    ./scripts/init-neo4j-schema.sh || echo "⚠️  Schema init exited with warnings (continuing)"
  else
    echo "⚠️  Schema init script not found, attempting manual init..."
    NEO4J_CONTAINER=\$(docker ps --filter "name=neo4j" --format "{{.Names}}" | head -1)
    if [ -n "\$NEO4J_CONTAINER" ]; then
      docker exec -e NEO4J_PASSWORD="\$NEO4J_PASSWORD" "\$NEO4J_CONTAINER" \
        sh -c 'cypher-shell -u neo4j -p "\$NEO4J_PASSWORD" "CREATE CONSTRAINT context_id_unique IF NOT EXISTS FOR (c:Context) REQUIRE c.id IS UNIQUE"' 2>/dev/null || true
      docker exec -e NEO4J_PASSWORD="\$NEO4J_PASSWORD" "\$NEO4J_CONTAINER" \
        sh -c 'cypher-shell -u neo4j -p "\$NEO4J_PASSWORD" "CREATE INDEX context_type_idx IF NOT EXISTS FOR (c:Context) ON (c.type)"' 2>/dev/null || true
      echo "✅ Basic schema initialization attempted"
    fi
  fi

  echo ""
  echo "✅ Development deployment completed!"

  # RESTORE PHASE - Restore data after deployment
  echo "♻️  Restoring backed up data..."
  if [ -f "/opt/veris-memory/scripts/backup-restore-integration.sh" ]; then
    bash /opt/veris-memory/scripts/backup-restore-integration.sh restore dev
  else
    echo "⚠️  Restore script not found, skipping restore"
  fi

  echo "✅ Deployment with backup/restore completed!"
EOSSH

echo "✅ Deployment script completed successfully"
