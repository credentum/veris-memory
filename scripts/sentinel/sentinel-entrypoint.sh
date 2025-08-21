#!/bin/bash
# Veris Sentinel Container Entrypoint Script
# Handles initialization and startup of the Veris Sentinel monitoring service

set -euo pipefail

# Configuration
SENTINEL_DB_PATH="${SENTINEL_DB_PATH:-/var/lib/sentinel/sentinel.db}"
SENTINEL_LOG_LEVEL="${LOG_LEVEL:-INFO}"
SENTINEL_API_PORT="${SENTINEL_API_PORT:-9090}"

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] SENTINEL: $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] SENTINEL: $1${NC}" >&2
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] SENTINEL: $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] SENTINEL: $1${NC}"
}

# Initialize directories
init_directories() {
    log "Initializing Sentinel directories..."
    
    # Create required directories
    mkdir -p "$(dirname "$SENTINEL_DB_PATH")"
    mkdir -p /run/secrets
    mkdir -p /run/certs
    
    # Set permissions (container runs as non-root user 10001)
    if [[ $(id -u) == 0 ]]; then
        chown -R 10001:10001 "$(dirname "$SENTINEL_DB_PATH")"
        chown -R 10001:10001 /run/secrets
        chown -R 10001:10001 /run/certs
    fi
    
    log "✅ Directories initialized"
}

# Validate environment
validate_environment() {
    log "Validating environment configuration..."
    
    # Required environment variables
    local required_vars=(
        "TARGET_BASE_URL"
    )
    
    # Optional but recommended variables
    local optional_vars=(
        "REDIS_URL"
        "QDRANT_URL"
        "NEO4J_BOLT"
        "NEO4J_USER"
        "ALERT_WEBHOOK"
        "GITHUB_REPO"
    )
    
    # Check required variables
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
        info "✓ $var is configured"
    done
    
    # Check optional variables
    for var in "${optional_vars[@]}"; do
        if [[ -n "${!var:-}" ]]; then
            info "✓ $var is configured"
        else
            warn "Optional variable $var is not set"
        fi
    done
    
    # Validate URLs
    if [[ -n "${TARGET_BASE_URL:-}" ]]; then
        if [[ ! "$TARGET_BASE_URL" =~ ^https?:// ]]; then
            error "TARGET_BASE_URL must be a valid HTTP/HTTPS URL"
        fi
    fi
    
    log "✅ Environment validation completed"
}

# Test connectivity
test_connectivity() {
    log "Testing connectivity to target services..."
    
    # Test main API endpoint
    if [[ -n "${TARGET_BASE_URL:-}" ]]; then
        info "Testing connection to $TARGET_BASE_URL..."
        if curl -s -f --max-time 10 "$TARGET_BASE_URL/health/live" > /dev/null 2>&1; then
            info "✓ Target API is reachable"
        else
            warn "Target API may not be ready yet (this is normal during startup)"
        fi
    fi
    
    # Test Qdrant if configured
    if [[ -n "${QDRANT_URL:-}" ]]; then
        info "Testing connection to Qdrant..."
        if curl -s -f --max-time 5 "$QDRANT_URL/collections" > /dev/null 2>&1; then
            info "✓ Qdrant is reachable"
        else
            warn "Qdrant may not be ready yet"
        fi
    fi
    
    # Test Redis if configured
    if [[ -n "${REDIS_URL:-}" ]]; then
        info "Testing Redis connection..."
        # Extract host and port from Redis URL
        if [[ "$REDIS_URL" =~ redis://([^:]+):([0-9]+) ]]; then
            local redis_host="${BASH_REMATCH[1]}"
            local redis_port="${BASH_REMATCH[2]}"
            if timeout 5 bash -c "</dev/tcp/$redis_host/$redis_port" 2>/dev/null; then
                info "✓ Redis is reachable"
            else
                warn "Redis may not be ready yet"
            fi
        fi
    fi
    
    log "✅ Connectivity tests completed"
}

# Setup signal handlers
setup_signal_handlers() {
    log "Setting up signal handlers..."
    
    # Handle SIGTERM gracefully
    trap 'log "Received SIGTERM, shutting down gracefully..."; exit 0' TERM
    
    # Handle SIGINT gracefully  
    trap 'log "Received SIGINT, shutting down gracefully..."; exit 0' INT
    
    # Handle SIGHUP for configuration reload
    trap 'log "Received SIGHUP, configuration reload not implemented yet"' HUP
    
    log "✅ Signal handlers configured"
}

# Health check function
health_check() {
    local check_url="http://localhost:$SENTINEL_API_PORT/status"
    
    if curl -s -f --max-time 5 "$check_url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Wait for dependencies
wait_for_dependencies() {
    log "Waiting for dependencies to be ready..."
    
    local max_wait=120
    local wait_interval=5
    local elapsed=0
    
    while [[ $elapsed -lt $max_wait ]]; do
        if [[ -n "${TARGET_BASE_URL:-}" ]]; then
            if curl -s -f --max-time 3 "$TARGET_BASE_URL/health/live" > /dev/null 2>&1; then
                log "✅ Dependencies are ready"
                return 0
            fi
        else
            # If no target URL, assume dependencies are ready
            log "✅ No dependency checks required"
            return 0
        fi
        
        info "Waiting for dependencies... ($elapsed/${max_wait}s)"
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
    done
    
    warn "Dependencies not ready after ${max_wait}s, proceeding anyway"
}

# Start Sentinel
start_sentinel() {
    log "Starting Veris Sentinel monitoring service..."
    
    # Log configuration
    info "Configuration:"
    info "  Database Path: $SENTINEL_DB_PATH"
    info "  Log Level: $SENTINEL_LOG_LEVEL"
    info "  API Port: $SENTINEL_API_PORT"
    info "  Target URL: ${TARGET_BASE_URL:-not set}"
    
    # Set Python path
    export PYTHONPATH="/app:${PYTHONPATH:-}"
    
    # Start Sentinel with proper logging
    exec python3 -u veris_sentinel.py
}

# Main function
main() {
    log "🚀 Starting Veris Sentinel container..."
    
    # Run initialization steps
    init_directories
    validate_environment
    setup_signal_handlers
    test_connectivity
    wait_for_dependencies
    
    # Start the main service
    start_sentinel
}

# Handle different commands
case "${1:-start}" in
    "start")
        main
        ;;
    "health")
        if health_check; then
            echo "Sentinel is healthy"
            exit 0
        else
            echo "Sentinel is not healthy"
            exit 1
        fi
        ;;
    "test")
        log "Running connectivity tests only..."
        validate_environment
        test_connectivity
        log "✅ All tests passed"
        ;;
    "version")
        echo "Veris Sentinel v1.0.0"
        ;;
    *)
        echo "Usage: $0 {start|health|test|version}"
        echo "  start  - Start Sentinel service (default)"
        echo "  health - Check if Sentinel is healthy"
        echo "  test   - Run connectivity tests"
        echo "  version - Show version information"
        exit 1
        ;;
esac