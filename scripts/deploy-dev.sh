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
  export SENTINEL_API_KEY='$SENTINEL_API_KEY'
  export HOST_CHECK_SECRET='$HOST_CHECK_SECRET'
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

  # BACKUP PHASE - Preserve data before cleanup
  echo "💾 Creating backup before cleanup..."
  if [ -f "/opt/veris-memory/scripts/backup-restore-integration.sh" ]; then
    bash /opt/veris-memory/scripts/backup-restore-integration.sh backup dev
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
  echo "🛑 Force stopping any remaining veris-memory containers..."
  docker ps -a --filter "name=veris-memory" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
  docker ps -a --filter "name=veris-memory" --format "{{.Names}}" | xargs -r docker rm 2>/dev/null || true

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

  # Check if deployment script exists
  if [ -f "scripts/deploy-environment.sh" ]; then
    echo "🚀 Running environment deployment script for DEVELOPMENT..."
    chmod +x scripts/deploy-environment.sh
    ./scripts/deploy-environment.sh development
  else
    echo "⚠️ Environment deployment script not found, using fallback..."

    # Fallback deployment for dev
    echo "🛑 Stopping existing dev containers..."
    docker compose -p veris-memory-dev down --remove-orphans 2>/dev/null || true

    # CRITICAL: Also stop any containers using the OLD project name (without -dev)
    echo "🧹 Cleaning up old project name containers..."
    docker compose -p veris-memory down --remove-orphans 2>/dev/null || true

    # Remove old networks to force recreation with correct project name
    echo "🌐 Removing old Docker networks to force recreation..."
    docker network rm veris-memory_context-store-network 2>/dev/null && echo "  ✓ Removed old network: veris-memory_context-store-network" || echo "  ℹ️ Old network not found (already removed)"
    docker network rm veris-memory_voice-network 2>/dev/null && echo "  ✓ Removed old network: veris-memory_voice-network" || echo "  ℹ️ Voice network not found"

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

    # Stop containers on dev ports (standard ports we test with + livekit ports)
    for port in 8000 6333 7474 7687 6379 6334 7880 7882 3478 5349; do
      containers=\$(docker ps --filter "publish=\$port" --format "{{.Names}}" 2>/dev/null || true)
      if [ -n "\$containers" ]; then
        echo "Stopping containers on port \$port: \$containers"
        docker stop \$containers 2>/dev/null || true
        docker rm \$containers 2>/dev/null || true
      fi
    done

    # Dev uses volume-mounted compose file for fast deployments
    # Code is mounted from host, no rebuild needed for code changes
    COMPOSE_FILE="docker-compose.deploy-dev.yml"
    echo "✅ Using volume-mounted compose for dev environment"
    echo "   → Code changes are instant (mounted from host)"
    echo "   → Hot reload enabled (auto-restart on file changes)"

    # Setup dev environment file
    if [ -f ".env.dev" ]; then
      cp .env.dev .env
    elif [ -f ".env.template" ]; then
      cp .env.template .env
    fi

    # Configure environment variables

    # Remove ALL managed variables to ensure clean state (no duplicates)
    echo "🗑️  Removing managed variables from .env to prevent duplicates..."
    if [ -f .env ]; then
      # Remove NEO4J, REDIS, TELEGRAM, API keys, PR #170, Voice Platform, and Sentinel variables
      grep -v "^NEO4J" .env > .env.tmp || true
      grep -v "^REDIS_PASSWORD" .env.tmp > .env.tmp0 || true
      mv .env.tmp0 .env.tmp
      grep -v "^TELEGRAM" .env.tmp > .env.tmp2 || true
      grep -v "^API_KEY_MCP" .env.tmp2 > .env.tmp3 || true
      grep -v "^VERIS_CACHE_TTL" .env.tmp3 > .env.tmp4 || true
      grep -v "^STRICT_EMBEDDINGS" .env.tmp4 > .env.tmp5 || true
      grep -v "^EMBEDDING_DIM" .env.tmp5 > .env.tmp6 || true
      grep -v "^LIVEKIT" .env.tmp6 > .env.tmp7 || true
      grep -v "^API_KEY_VOICEBOT" .env.tmp7 > .env.tmp8 || true
      grep -v "^VOICE_BOT" .env.tmp8 > .env.tmp9 || true
      grep -v "^STT_" .env.tmp9 > .env.tmp10 || true
      grep -v "^TTS_" .env.tmp10 > .env.tmp11 || true
      grep -v "^OPENAI_API_KEY" .env.tmp11 > .env.tmp12 || true
      grep -v "^ENABLE_MCP_RETRY" .env.tmp12 > .env.tmp13 || true
      grep -v "^MCP_RETRY_ATTEMPTS" .env.tmp13 > .env.tmp14 || true
      grep -v "^SENTINEL_API_KEY" .env.tmp14 > .env.tmp15 || true
      grep -v "^HOST_CHECK_SECRET" .env.tmp15 > .env || true
      rm -f .env.tmp .env.tmp2 .env.tmp3 .env.tmp4 .env.tmp5 .env.tmp6 .env.tmp7 .env.tmp8 .env.tmp9 .env.tmp10 .env.tmp11 .env.tmp12 .env.tmp13 .env.tmp14 .env.tmp15
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
      echo "   This secret must be explicitly configured in GitHub Secrets."
      echo "   No default fallback is allowed for security reasons."
      VALIDATION_FAILED=1
    fi

    if [ -z "\$REDIS_PASSWORD" ]; then
      echo "❌ ERROR: REDIS_PASSWORD is not set or empty!"
      echo "   Redis requires authentication for security."
      VALIDATION_FAILED=1
    fi

    # Check minimum password lengths
    if [ -n "\$NEO4J_PASSWORD" ] && [ \${#NEO4J_PASSWORD} -lt 16 ]; then
      echo "⚠️  WARNING: NEO4J_PASSWORD is less than 16 characters (current: \${#NEO4J_PASSWORD})"
      echo "   Consider using a longer password for better security."
    fi

    if [ -n "\$NEO4J_RO_PASSWORD" ] && [ \${#NEO4J_RO_PASSWORD} -lt 16 ]; then
      echo "⚠️  WARNING: NEO4J_RO_PASSWORD is less than 16 characters (current: \${#NEO4J_RO_PASSWORD})"
      echo "   Consider using a longer password for better security."
    fi

    if [ -n "\$REDIS_PASSWORD" ] && [ \${#REDIS_PASSWORD} -lt 16 ]; then
      echo "⚠️  WARNING: REDIS_PASSWORD is less than 16 characters (current: \${#REDIS_PASSWORD})"
      echo "   Consider using a longer password for better security."
    fi

    if [ \$VALIDATION_FAILED -eq 1 ]; then
      echo ""
      echo "❌ DEPLOYMENT FAILED: Required secrets are missing!"
      echo ""
      echo "Fix by adding these secrets to GitHub Secrets:"
      echo "  1. Go to: https://github.com/credentum/veris-memory/settings/secrets/actions"
      echo "  2. Add the missing secrets listed above"
      echo "  3. Re-run the deployment workflow"
      echo ""
      exit 1
    fi

    echo "✅ All required secrets are present and valid"

    # Write secrets to .env without echoing them
    # Note: Secrets are passed as environment variables from GitHub Actions
    {
      printf "NEO4J_PASSWORD=%s\\n" "\$NEO4J_PASSWORD"
      printf "NEO4J_RO_PASSWORD=%s\\n" "\$NEO4J_RO_PASSWORD"
      printf "NEO4J_AUTH=neo4j/%s\\n" "\$NEO4J_PASSWORD"

      # SECURITY: Redis Password Authentication
      printf "\\n# Redis Authentication (Security Fix)\\n"
      printf "REDIS_PASSWORD=%s\\n" "\$REDIS_PASSWORD"

      # Add Telegram configuration if available
      if [ -n "\$TELEGRAM_BOT_TOKEN" ]; then
        printf "TELEGRAM_BOT_TOKEN=%s\\n" "\$TELEGRAM_BOT_TOKEN"
      fi
      if [ -n "\$TELEGRAM_CHAT_ID" ]; then
        printf "TELEGRAM_CHAT_ID=%s\\n" "\$TELEGRAM_CHAT_ID"
      fi

      # Sprint 13: MCP API Key Authentication
      printf "\\n# MCP Server Authentication (Sprint 13)\\n"
      if [ -n "\$API_KEY_MCP" ]; then
        printf "API_KEY_MCP=%s\\n" "\$API_KEY_MCP"
        printf "AUTH_REQUIRED=true\\n"
        printf "ENVIRONMENT=production\\n"
      else
        # Development fallback - use test key
        printf "API_KEY_MCP=vmk_mcp_test:mcp_server:writer:true\\n"
        printf "AUTH_REQUIRED=false\\n"
        printf "ENVIRONMENT=development\\n"
      fi

      # PR #170: Cache and Embedding Configuration
      printf "\\n# Veris Memory Cache Configuration (PR #170)\\n"
      printf "VERIS_CACHE_TTL_SECONDS=300\\n"
      printf "STRICT_EMBEDDINGS=false\\n"
      printf "EMBEDDING_DIM=384\\n"

      # Qdrant Collection Configuration (PR #238)
      printf "\\n# Qdrant Collection Name (must match across all components)\\n"
      printf "QDRANT_COLLECTION_NAME=context_embeddings\\n"

      # Voice Platform Configuration
      printf "\\n# TeamAI Voice Platform Configuration\\n"
      if [ -n "\$LIVEKIT_API_KEY" ]; then
        printf "LIVEKIT_API_KEY=%s\\n" "\$LIVEKIT_API_KEY"
      fi
      if [ -n "\$LIVEKIT_API_SECRET" ]; then
        printf "LIVEKIT_API_SECRET=%s\\n" "\$LIVEKIT_API_SECRET"
      fi
      if [ -n "\$LIVEKIT_API_WEBSOCKET" ]; then
        printf "LIVEKIT_API_WEBSOCKET=%s\\n" "\$LIVEKIT_API_WEBSOCKET"
      fi
      if [ -n "\$API_KEY_VOICEBOT" ]; then
        printf "API_KEY_VOICEBOT=%s\\n" "\$API_KEY_VOICEBOT"
      fi

      # Voice Bot Sprint 13 Configuration
      printf "VOICE_BOT_AUTHOR_PREFIX=voice_bot\\n"
      printf "ENABLE_MCP_RETRY=true\\n"
      printf "MCP_RETRY_ATTEMPTS=3\\n"

      # OpenAI for STT/TTS (Whisper + TTS)
      if [ -n "\$OPENAI_API_KEY" ]; then
        printf "OPENAI_API_KEY=%s\\n" "\$OPENAI_API_KEY"
        printf "STT_PROVIDER=whisper\\n"
        printf "STT_API_KEY=%s\\n" "\$OPENAI_API_KEY"
        printf "TTS_PROVIDER=openai\\n"
        printf "TTS_API_KEY=%s\\n" "\$OPENAI_API_KEY"
      fi

      # Voice Bot Feature Flags
      printf "ENABLE_VOICE_COMMANDS=true\\n"
      printf "ENABLE_FACT_STORAGE=true\\n"
      printf "ENABLE_CONVERSATION_TRACE=true\\n"

      # Voice Bot SSL Configuration (auto-generated)
      printf "\\n# SSL Configuration for Voice Bot\\n"
      printf "SSL_KEYFILE=/app/certs/key.pem\\n"
      printf "SSL_CERTFILE=/app/certs/cert.pem\\n"

      # Sentinel Monitoring Configuration
      printf "\\n# Sentinel Monitoring Authentication\\n"
      if [ -n "\$SENTINEL_API_KEY" ]; then
        printf "SENTINEL_API_KEY=%s\\n" "\$SENTINEL_API_KEY"
      fi
      if [ -n "\$HOST_CHECK_SECRET" ]; then
        printf "HOST_CHECK_SECRET=%s\\n" "\$HOST_CHECK_SECRET"
      fi
    } >> .env 2>/dev/null

    # Verify configuration was written correctly
    if ! grep -q "^NEO4J_PASSWORD=" .env; then
      echo "❌ ERROR: NEO4J_PASSWORD not found in .env!"
      exit 1
    fi
    echo "✅ Configuration file created successfully"

    # Generate SSL certificates for voice-bot if they don't exist
    echo "🔐 Checking SSL certificates for voice-bot..."
    CERT_DIR="/opt/veris-memory/voice-bot/certs"
    if [ ! -d "\$CERT_DIR" ]; then
      echo "📁 Creating certs directory..."
      mkdir -p "\$CERT_DIR"
    fi

    if [ ! -f "\$CERT_DIR/key.pem" ] || [ ! -f "\$CERT_DIR/cert.pem" ]; then
      echo "📜 Generating self-signed SSL certificate..."
      openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout "\$CERT_DIR/key.pem" \
        -out "\$CERT_DIR/cert.pem" \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=Personal/CN=\$(hostname -I | awk '{print \$1}')" \
        2>/dev/null || echo "⚠️  Certificate generation failed, voice-bot will use HTTP"

      if [ -f "\$CERT_DIR/key.pem" ] && [ -f "\$CERT_DIR/cert.pem" ]; then
        echo "✅ SSL certificates generated successfully"
        chmod 600 "\$CERT_DIR/key.pem"
        chmod 644 "\$CERT_DIR/cert.pem"
      fi
    else
      echo "✅ SSL certificates already exist"
      # Check certificate expiry (warn if less than 30 days)
      CERT_EXPIRY=\$(openssl x509 -enddate -noout -in "\$CERT_DIR/cert.pem" 2>/dev/null | cut -d= -f2)
      if [ -n "\$CERT_EXPIRY" ]; then
        EXPIRY_EPOCH=\$(date -d "\$CERT_EXPIRY" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=\$(date +%s)
        DAYS_LEFT=\$(( (\$EXPIRY_EPOCH - \$NOW_EPOCH) / 86400 ))

        if [ \$DAYS_LEFT -lt 30 ] && [ \$DAYS_LEFT -gt 0 ]; then
          echo "⚠️  SSL certificate expires in \$DAYS_LEFT days"
          echo "   Consider regenerating: rm -rf \$CERT_DIR && redeploy"
        elif [ \$DAYS_LEFT -le 0 ]; then
          echo "⚠️  SSL certificate has EXPIRED! Regenerating..."
          rm -f "\$CERT_DIR/key.pem" "\$CERT_DIR/cert.pem"
          openssl req -x509 -newkey rsa:4096 -nodes \
            -keyout "\$CERT_DIR/key.pem" \
            -out "\$CERT_DIR/cert.pem" \
            -days 365 \
            -subj "/C=US/ST=State/L=City/O=Personal/CN=\$(hostname -I | awk '{print \$1}')" \
            2>/dev/null && echo "✅ SSL certificate regenerated"
          chmod 600 "\$CERT_DIR/key.pem" 2>/dev/null
          chmod 644 "\$CERT_DIR/cert.pem" 2>/dev/null
        else
          echo "   Valid for \$DAYS_LEFT more days"
        fi
      fi
    fi

    # Pull pre-built images from GitHub Container Registry
    echo "🏗️  Starting deployment (pull + start services)..."

    # Login to GitHub Container Registry to pull CVE-validated images
    if [ -n "\$GITHUB_TOKEN" ]; then
      echo "🔐 Logging in to GitHub Container Registry..."
      echo "\$GITHUB_TOKEN" | docker login ghcr.io -u "\$GITHUB_ACTOR" --password-stdin
    else
      echo "⚠️  GITHUB_TOKEN not set, will try to pull public images without authentication"
    fi

    # Pull latest CVE-validated images (30 seconds vs 7 minutes build time)
    echo "📥 Pulling latest images from GHCR (CVE validated)..."
    if docker compose -p veris-memory-dev pull; then
      # Successfully pulled images from GHCR
      echo "✅ Images pulled from GHCR successfully"

      # Verify image digests for security (optional but recommended)
      echo "🔐 Verifying image digests..."
      for service in api context-store sentinel; do
        DIGEST=\$(docker inspect ghcr.io/credentum/veris-memory/\$service:latest --format='{{index .RepoDigests 0}}' 2>/dev/null || echo "not found")
        if [ "\$DIGEST" != "not found" ]; then
          echo "   ✓ \$service: \$DIGEST"
        else
          echo "   ⚠️  \$service: Could not verify digest (image may be built locally)"
        fi
      done

      # Build qdrant locally (not in GHCR - uses custom Dockerfile with curl/wget for health checks)
      echo "🔨 Building qdrant image locally (not available in GHCR)..."
      docker compose -p veris-memory-dev build qdrant

      echo "🚀 Starting main services with pulled images..."
      docker compose -p veris-memory-dev up -d --no-build
    else
      # GHCR pull failed - fall back to local build
      echo "⚠️  Failed to pull images from GHCR (registry unreachable or images not yet pushed)"
      echo "🏗️  Falling back to local build (this will take ~7 minutes)..."
      docker compose -p veris-memory-dev up -d --build
    fi

    # Deploy voice platform services (voice-bot + livekit)
    if [ -f "docker-compose.voice.yml" ]; then
      echo "🎙️  Deploying voice platform..."
      # Voice services still build locally (not in GHCR yet)
      docker compose -p veris-memory-dev -f \$COMPOSE_FILE -f docker-compose.voice.yml up -d --build voice-bot livekit nginx-voice-proxy
    else
      echo "⚠️  docker-compose.voice.yml not found, skipping voice-bot deployment"
    fi

    # Logout from GHCR
    if [ -n "\$GITHUB_TOKEN" ]; then
      docker logout ghcr.io
    fi

    echo "⏳ Waiting for services to start..."
    sleep 10

    # Show service status
    echo "📊 Service Status:"
    docker compose -p veris-memory-dev ps

    # Initialize Neo4j schema
    echo ""
    echo "🔧 Initializing Neo4j schema..."
    if [ -f "scripts/init-neo4j-schema.sh" ]; then
      chmod +x scripts/init-neo4j-schema.sh
      # Run schema initialization with proper error handling
      if ./scripts/init-neo4j-schema.sh; then
        echo "✅ Schema initialization completed successfully"
      else
        SCHEMA_EXIT_CODE=\$?
        # Non-zero exit could be warnings (e.g., already exists) or real errors
        # Log the warning but continue deployment
        echo "⚠️  Schema initialization exited with code \$SCHEMA_EXIT_CODE"
        echo "   Deployment will continue, but verify schema manually if needed"
      fi
    else
      echo "⚠️  Neo4j schema initialization script not found"
      echo "   Attempting manual initialization..."

      # Fallback: Run schema init via docker exec
      NEO4J_CONTAINER=\$(docker ps --filter "name=neo4j" --format "{{.Names}}" | head -1)
      if [ -n "\$NEO4J_CONTAINER" ]; then
        echo "   Found Neo4j container: \$NEO4J_CONTAINER"

        # Create constraint with proper error handling
        CONSTRAINT_OUTPUT=\$(docker exec -e NEO4J_PASSWORD="\$NEO4J_PASSWORD" "\$NEO4J_CONTAINER" \
          sh -c 'cypher-shell -u neo4j -p "\$NEO4J_PASSWORD" "CREATE CONSTRAINT context_id_unique IF NOT EXISTS FOR (c:Context) REQUIRE c.id IS UNIQUE"' 2>&1)
        CONSTRAINT_RESULT=\$?

        if [ \$CONSTRAINT_RESULT -eq 0 ]; then
          echo "   ✅ Context constraint created"
        elif echo "\$CONSTRAINT_OUTPUT" | grep -qi "already exists"; then
          echo "   ℹ️  Context constraint already exists (idempotent)"
        else
          echo "   ⚠️  Constraint creation failed: \$CONSTRAINT_OUTPUT"
        fi

        # Create index with proper error handling
        INDEX_OUTPUT=\$(docker exec -e NEO4J_PASSWORD="\$NEO4J_PASSWORD" "\$NEO4J_CONTAINER" \
          sh -c 'cypher-shell -u neo4j -p "\$NEO4J_PASSWORD" "CREATE INDEX context_type_idx IF NOT EXISTS FOR (c:Context) ON (c.type)"' 2>&1)
        INDEX_RESULT=\$?

        if [ \$INDEX_RESULT -eq 0 ]; then
          echo "   ✅ Context index created"
        elif echo "\$INDEX_OUTPUT" | grep -qi "already exists"; then
          echo "   ℹ️  Context index already exists (idempotent)"
        else
          echo "   ⚠️  Index creation failed: \$INDEX_OUTPUT"
        fi

        echo "   ✅ Basic schema initialization attempted"
      else
        echo "   ⚠️  Neo4j container not found, skipping schema init"
      fi
    fi

    # Show voice-bot status specifically
    echo ""
    echo "🎙️  Voice Platform Status:"
    docker compose -p veris-memory-dev -f \$COMPOSE_FILE -f docker-compose.voice.yml ps voice-bot livekit 2>/dev/null || echo "Voice services not running"

    echo ""
    echo "✅ Development deployment completed!"
  fi

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
