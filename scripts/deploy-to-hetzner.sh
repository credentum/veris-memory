#!/bin/bash
# Deploy Veris Memory (Context Store) to Hetzner Dedicated Server
# Fully automated deployment with bootstrap and verification

set -euo pipefail

# Configuration
# Use SSH alias from ~/.ssh/config or override with environment variables
HETZNER_HOST="${HETZNER_HOST:-hetzner-server}"
HETZNER_USER="${HETZNER_USER:-}"  # Empty by default, will use SSH config
REMOTE_DIR="/opt/veris-memory"
REPO_URL="https://github.com/credentum/veris-memory.git"
LOG_FILE="/tmp/hetzner-deploy-$(date +%Y%m%d-%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_FILE"
}

# SSH target configuration
SSH_TARGET="${HETZNER_USER:+$HETZNER_USER@}$HETZNER_HOST"

# Check prerequisites
check_prerequisites() {
    log "🔍 Checking prerequisites..."
    
    if ! command -v ssh &> /dev/null; then
        error "SSH client not found"
    fi
    
    # Test SSH connection
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$SSH_TARGET" "echo 'SSH test successful'" &>/dev/null; then
        error "Cannot connect to Hetzner server. Please ensure SSH key is configured."
    fi
    
    log "✅ Prerequisites check passed"
}

# Stop existing deployment
stop_existing() {
    log "🛑 Stopping existing containers..."
    
    ssh "$SSH_TARGET" << 'EOF'
# Stop any existing veris-memory containers
for project in veris-memory veris-memory-new; do
    if [ -d "/root/$project" ]; then
        cd "/root/$project" 2>/dev/null && docker-compose down 2>/dev/null || true
    fi
    if [ -d "/opt/$project" ]; then
        cd "/opt/$project" 2>/dev/null && docker-compose down 2>/dev/null || true
    fi
done

# Clean up old containers
docker container prune -f 2>/dev/null || true
EOF
    
    log "✅ Existing containers stopped"
}

# Deploy to server
deploy_to_server() {
    log "📦 Deploying Veris Memory to Hetzner server..."
    
    ssh "$SSH_TARGET" << EOF
set -euo pipefail

# Remove old deployment if exists
if [ -d "$REMOTE_DIR" ]; then
    echo "Removing old deployment..."
    rm -rf "$REMOTE_DIR"
fi

# Clone fresh repository
echo "Cloning repository..."
git clone "$REPO_URL" "$REMOTE_DIR"
cd "$REMOTE_DIR"

# Show latest commit
echo "Latest commit:"
git log --oneline -1

# Create .env file with required variables
cat > .env << 'ENVFILE'
NEO4J_PASSWORD=secure-password-123
NEO4J_AUTH=neo4j/secure-password-123
REDIS_PASSWORD=redis-password-123
EMBEDDING_DIM=384
EMBEDDING_MODEL=all-MiniLM-L6-v2
ENVFILE

echo ".env file created"
EOF
    
    log "✅ Repository deployed to server"
}

# Start services
start_services() {
    log "🚀 Starting services..."
    
    ssh "$SSH_TARGET" << EOF
set -euo pipefail
cd "$REMOTE_DIR"

# Use the simple compose file for core services
if [ -f "dockerfiles/docker-compose.simple.yml" ]; then
    echo "Starting services with dockerfiles/docker-compose.simple.yml..."
    docker-compose -f dockerfiles/docker-compose.simple.yml up -d
    
    # Wait for services to be ready
    echo "Waiting for services to start..."
    sleep 15
else
    error "dockerfiles/docker-compose.simple.yml not found!"
fi
EOF
    
    log "✅ Services started"
}

# Bootstrap Qdrant collection
bootstrap_qdrant() {
    log "🔧 Bootstrapping Qdrant collection..."
    
    ssh "$SSH_TARGET" << 'EOF'
set -euo pipefail
cd /opt/veris-memory

# Check if Qdrant is running
if ! curl -s http://localhost:6333/ | grep -q "qdrant"; then
    echo "ERROR: Qdrant is not running!"
    exit 1
fi

# Create collection with correct configuration
echo "Creating context_embeddings collection..."
curl -X PUT http://localhost:6333/collections/context_embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "size": 384,
      "distance": "Cosine"
    },
    "on_disk_payload": true,
    "optimizers_config": {
      "default_segment_number": 2
    },
    "replication_factor": 1
  }' 2>/dev/null

# Verify collection
echo "Verifying collection configuration..."
COLLECTION_INFO=$(curl -s http://localhost:6333/collections/context_embeddings)
if echo "$COLLECTION_INFO" | grep -q '"size":384'; then
    echo "✅ Collection created with 384 dimensions"
else
    echo "❌ Collection configuration error!"
    echo "$COLLECTION_INFO"
    exit 1
fi

# Create text index on content field
echo "Creating text index..."
curl -X PUT http://localhost:6333/collections/context_embeddings/index \
  -H 'Content-Type: application/json' \
  -d '{
    "field_name": "content",
    "field_schema": {
      "type": "text",
      "tokenizer": "word",
      "min_token_len": 2,
      "max_token_len": 20,
      "lowercase": true
    }
  }' 2>/dev/null || echo "Text index may already exist"

echo "✅ Qdrant bootstrap completed"
EOF
    
    log "✅ Qdrant collection bootstrapped"
}

# Run smoke tests
run_smoke_tests() {
    log "🧪 Running smoke tests..."
    
    ssh "$SSH_TARGET" << 'EOF'
set -euo pipefail
cd /opt/veris-memory

# Install minimal Python dependencies for testing
apt-get update > /dev/null 2>&1
apt-get install -y python3-requests python3-yaml python3-colorama > /dev/null 2>&1

# Create minimal smoke test
cat > /tmp/smoke_test.py << 'PYTEST'
#!/usr/bin/env python3
import requests
import sys

def test_service(name, url, expected_content=None):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            if expected_content and expected_content not in r.text:
                print(f"❌ {name}: Unexpected content")
                return False
            print(f"✅ {name}: OK")
            return True
        else:
            print(f"❌ {name}: HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name}: {str(e)}")
        return False

def test_qdrant_collection():
    try:
        r = requests.get("http://localhost:6333/collections/context_embeddings", timeout=5)
        if r.status_code == 200:
            data = r.json()
            config = data.get("result", {}).get("config", {})
            params = config.get("params", {})
            vectors = params.get("vectors", {})
            
            if vectors.get("size") == 384 and vectors.get("distance") == "Cosine":
                print(f"✅ Qdrant Collection: 384 dimensions, Cosine distance")
                return True
            else:
                print(f"❌ Qdrant Collection: Wrong configuration")
                return False
    except Exception as e:
        print(f"❌ Qdrant Collection: {str(e)}")
        return False

print("\n=== SMOKE TEST RESULTS ===\n")
results = []
results.append(test_service("Qdrant", "http://localhost:6333/", "qdrant"))
results.append(test_service("Neo4j", "http://localhost:7474"))
results.append(test_service("Redis", "http://localhost:6379", expected_content=None))
results.append(test_qdrant_collection())

print(f"\n=== SUMMARY ===")
passed = sum(results)
total = len(results)
print(f"Passed: {passed}/{total}")

if passed < total:
    sys.exit(1)
PYTEST

python3 /tmp/smoke_test.py
EOF
    
    log "✅ Smoke tests completed"
}

# Monitor deployment
monitor_deployment() {
    log "📊 Final deployment status..."
    
    ssh "$SSH_TARGET" << EOF
echo ""
echo "=== Container Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== Qdrant Collection Info ==="
curl -s http://localhost:6333/collections/context_embeddings | python3 -m json.tool | grep -E '"size"|"distance"|"vectors_count"' || true

echo ""
echo "=== Disk Usage ==="
df -h /opt/veris-memory

echo ""
echo "=== Memory Usage ==="
free -h
EOF
    
    log "✅ Monitoring completed"
}

# Main deployment process
main() {
    log "🚀 Starting Hetzner Veris Memory Deployment"
    log "============================================"
    log "Target: $HETZNER_HOST"
    log "Remote Directory: $REMOTE_DIR"
    log "Repository: $REPO_URL"
    log "Log File: $LOG_FILE"
    log ""
    
    check_prerequisites
    stop_existing
    deploy_to_server
    start_services
    bootstrap_qdrant
    run_smoke_tests
    monitor_deployment
    
    log ""
    log "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
    log "============================================"
    log "📊 Access services via SSH tunnel:"
    log "   ssh -L 6333:localhost:6333 -L 7474:localhost:7474 -L 6379:localhost:6379 $HETZNER_USER@$HETZNER_HOST"
    log "📝 View logs: cat $LOG_FILE"
    log ""
    log "✅ All services deployed with correct configuration:"
    log "   - Qdrant: 384 dimensions, Cosine distance"
    log "   - Neo4j: Graph database ready"
    log "   - Redis: Cache ready"
}

# Run main function
main "$@"