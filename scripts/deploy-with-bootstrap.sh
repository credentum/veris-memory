#!/bin/bash
#
# Deploy script with Qdrant bootstrap guard integration
# Ensures collection exists with correct configuration before deployment
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
QDRANT_URL=${QDRANT_URL:-"http://localhost:6333"}
COLLECTION_NAME=${COLLECTION_NAME:-"context_embeddings"}
VECTOR_DIMENSIONS=${VECTOR_DIMENSIONS:-384}
DISTANCE_METRIC=${DISTANCE_METRIC:-"Cosine"}

# Functions
status() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

# Parse arguments
SKIP_BOOTSTRAP=false
SKIP_MANIFEST_CHECK=false
DRY_RUN=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --skip-bootstrap)
            SKIP_BOOTSTRAP=true
            shift
            ;;
        --skip-manifest-check)
            SKIP_MANIFEST_CHECK=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-bootstrap      Skip Qdrant bootstrap step"
            echo "  --skip-manifest-check Skip manifest verification"
            echo "  --dry-run            Show what would be done without executing"
            echo "  --help               Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

echo "========================================="
echo "Deployment with Bootstrap Guard"
echo "========================================="
echo ""

# Step 1: Pre-deployment checks
echo "📋 Running pre-deployment checks..."

if [ "$DRY_RUN" = true ]; then
    warning "DRY RUN MODE - No actual changes will be made"
fi

# Check if required files exist
if [ ! -f "production_locked_config.yaml" ]; then
    error "production_locked_config.yaml not found!"
fi

if [ ! -f "docker/docker-compose.yml" ] && [ ! -f "docker/docker-compose.prod.yml" ]; then
    warning "No docker-compose file found"
fi

status "Pre-deployment checks passed"
echo ""

# Step 2: Manifest verification
if [ "$SKIP_MANIFEST_CHECK" = false ]; then
    echo "🔍 Verifying manifest parity..."
    
    if [ "$DRY_RUN" = true ]; then
        echo "   [DRY RUN] Would run: python ops/verify/manifest_verifier.py"
    else
        if [ -f "ops/verify/manifest_verifier.py" ]; then
            python ops/verify/manifest_verifier.py \
                --config production_locked_config.yaml \
                --qdrant-url "$QDRANT_URL" \
                --collection "$COLLECTION_NAME" || {
                    error "Manifest verification failed!"
                }
            status "Manifest verification passed"
        else
            warning "Manifest verifier not found, skipping"
        fi
    fi
else
    warning "Skipping manifest verification (--skip-manifest-check)"
fi
echo ""

# Step 3: Qdrant bootstrap
if [ "$SKIP_BOOTSTRAP" = false ]; then
    echo "🚀 Bootstrapping Qdrant collection..."
    
    if [ "$DRY_RUN" = true ]; then
        echo "   [DRY RUN] Would run: python ops/bootstrap/qdrant_bootstrap.py"
        echo "   Collection: $COLLECTION_NAME"
        echo "   Dimensions: $VECTOR_DIMENSIONS"
        echo "   Distance: $DISTANCE_METRIC"
    else
        python ops/bootstrap/qdrant_bootstrap.py \
            --collection "$COLLECTION_NAME" \
            --dimensions "$VECTOR_DIMENSIONS" \
            --distance "$DISTANCE_METRIC" \
            --qdrant-url "$QDRANT_URL" \
            --ensure-collection \
            --stats || {
                error "Qdrant bootstrap failed!"
            }
        status "Qdrant bootstrap completed"
    fi
else
    warning "Skipping Qdrant bootstrap (--skip-bootstrap)"
fi
echo ""

# Step 4: Deploy services
echo "🐳 Deploying services..."

if [ "$DRY_RUN" = true ]; then
    echo "   [DRY RUN] Would deploy Docker services"
else
    # Check which compose file to use
    if [ -f "docker/docker-compose.prod.yml" ]; then
        COMPOSE_FILE="docker/docker-compose.prod.yml"
    elif [ -f "docker/docker-compose.yml" ]; then
        COMPOSE_FILE="docker/docker-compose.yml"
    else
        error "No docker-compose file found in docker/ directory!"
    fi
    
    echo "   Using compose file: $COMPOSE_FILE"
    
    # Pull latest images
    docker-compose -f "$COMPOSE_FILE" pull
    
    # Deploy with zero-downtime (if services are already running)
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps --build
    
    status "Services deployed"
fi
echo ""

# Step 5: Post-deployment verification
echo "🔬 Running post-deployment verification..."

if [ "$DRY_RUN" = true ]; then
    echo "   [DRY RUN] Would run smoke tests"
else
    # Wait for services to be ready
    echo "   Waiting for services to be ready..."
    sleep 10
    
    # Run smoke tests
    if [ -f "scripts/recovery-phase-4-smoke.py" ]; then
        python scripts/recovery-phase-4-smoke.py || {
            warning "Some smoke tests failed"
        }
    else
        warning "Smoke test script not found"
    fi
    
    # Check collection stats
    echo ""
    echo "   Collection statistics:"
    python ops/bootstrap/qdrant_bootstrap.py --stats 2>/dev/null || true
    
    status "Post-deployment verification completed"
fi
echo ""

# Step 6: Summary
echo "========================================="
echo "Deployment Summary"
echo "========================================="

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "DRY RUN COMPLETED - No changes were made"
    echo ""
    echo "To perform actual deployment, run without --dry-run:"
    echo "  $0"
else
    echo ""
    status "Deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor service logs: docker-compose logs -f"
    echo "  2. Check metrics: curl http://localhost:8000/metrics"
    echo "  3. Run full test suite: make test-all"
fi

echo ""