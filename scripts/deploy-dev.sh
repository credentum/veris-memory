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

  # =============================================================================
  # MINIMAL DOWNTIME DEPLOYMENT (PR #428)
  # Pull images FIRST while services are running, then atomic swap
  # Reduces downtime from 20+ minutes to ~30 seconds
  # =============================================================================

  # Dev uses volume-mounted compose file for fast deployments
  COMPOSE_FILE="docker-compose.deploy-dev.yml"

  echo "⚡ MINIMAL DOWNTIME DEPLOYMENT"
  echo "   Services stay UP while pulling new images"

  # Login to GHCR first
  if [ -n "\$GITHUB_TOKEN" ]; then
    echo "🔐 Logging in to GitHub Container Registry..."
    echo "\$GITHUB_TOKEN" | docker login ghcr.io -u "\$GITHUB_ACTOR" --password-stdin
  fi

  # STEP 1: Pull new images WHILE services are still running
  echo "📥 Pulling new images (services still running)..."
  PULL_START=\$(date +%s)
  if docker compose -p veris-memory-dev -f \$COMPOSE_FILE pull 2>/dev/null; then
    PULL_END=\$(date +%s)
    echo "✅ Images pulled in \$((PULL_END - PULL_START)) seconds"
  else
    echo "⚠️  GHCR pull had issues, will build locally if needed"
  fi

  # Build qdrant locally (custom Dockerfile) - also while services running
  echo "🔨 Building qdrant image..."
  docker compose -p veris-memory-dev -f \$COMPOSE_FILE build qdrant 2>/dev/null || true

  # STEP 2: Quick cleanup of orphaned containers (not running services!)
  echo "🧹 Cleaning up orphaned containers only..."
  # Only remove containers using OLD project name (without -dev)
  docker compose -p veris-memory down --remove-orphans 2>/dev/null || true
  # Remove old networks that might conflict
  docker network rm veris-memory_context-store-network 2>/dev/null || true
  docker network rm veris-memory_voice-network 2>/dev/null || true

  # STEP 3: Atomic swap - this is where the brief downtime happens
  echo "🔄 Atomic swap starting (brief downtime)..."
  SWAP_START=\$(date +%s)

  # =============================================================================
  # CONSOLIDATED DEPLOYMENT (Issue #416)
  # All .env creation and deployment logic in one place - no more fragmentation
  # =============================================================================

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
  # ATOMIC SWAP - Start new containers (images already pulled above)
  # =============================================================================
  echo "🚀 Starting services with atomic swap..."

  # Start services with force-recreate (uses freshly pulled images)
  # --no-build because we already pulled/built above
  docker compose -p veris-memory-dev -f \$COMPOSE_FILE up -d --force-recreate --no-build

  # Deploy voice-bot if available
  if [ -f "docker-compose.voice.yml" ]; then
    echo "🎙️  Deploying voice platform..."
    docker compose -p veris-memory-dev -f \$COMPOSE_FILE -f docker-compose.voice.yml up -d --force-recreate voice-bot
  fi

  # Logout from GHCR
  [ -n "\$GITHUB_TOKEN" ] && docker logout ghcr.io 2>/dev/null

  # Calculate swap time
  SWAP_END=\$(date +%s)
  echo "✅ Atomic swap completed in \$((SWAP_END - SWAP_START)) seconds"

  echo "⏳ Waiting for services to become healthy..."
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

  # =============================================================================
  # POST-DEPLOYMENT CLEANUP (runs after services are healthy)
  # =============================================================================
  echo "🧹 Post-deployment cleanup (services are running)..."

  # Remove dangling images only (not all unused)
  docker image prune -f 2>/dev/null || true

  # Remove old veris-memory images (keep latest)
  for repo in api context-store sentinel voice-bot; do
    OLD_IMAGES=\$(docker images "ghcr.io/credentum/veris-memory/\$repo" --format "{{.ID}} {{.Tag}}" 2>/dev/null | grep -v "latest" | awk '{print \$1}' || true)
    if [ -n "\$OLD_IMAGES" ]; then
      echo "   Removing old \$repo images..."
      echo "\$OLD_IMAGES" | xargs -r docker rmi -f 2>/dev/null || true
    fi
  done

  # Report disk usage
  DISK_FREE=\$(df -h /var/lib/docker 2>/dev/null | tail -1 | awk '{print \$4}' || echo "unknown")
  echo "   Disk space available: \$DISK_FREE"

  echo ""
  echo "🎉 DEPLOYMENT COMPLETE"
  echo "   Downtime was ~\$((SWAP_END - SWAP_START)) seconds (atomic swap only)"
EOSSH

echo "✅ Deployment script completed successfully"
