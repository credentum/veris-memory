#!/bin/bash
set -euo pipefail  # Exit on error, undefined variables, pipe failures

# Comprehensive error handling
trap cleanup_on_error EXIT ERR

cleanup_on_error() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "ERROR: Service startup failed with exit code $exit_code"
        echo "Attempting cleanup and graceful shutdown..."

        # Stop any running services
        pkill -f supervisord || true
        pkill -f redis-server || true
        pkill -f qdrant || true
        pkill -f neo4j || true

        # Log final status
        echo "Cleanup completed. Check logs in /app/logs/ for details."
        exit $exit_code
    fi
}

echo "Starting Veris Memory services with comprehensive error handling..."

# Validate critical environment variables
validate_environment() {
    echo "Validating environment configuration..."

    # Check Neo4j password
    NEO4J_PASSWORD=${NEO4J_PASSWORD:-}
    if [ -z "$NEO4J_PASSWORD" ]; then
        echo "ERROR: NEO4J_PASSWORD environment variable is required for production deployment"
        echo "Set it using: flyctl secrets set NEO4J_PASSWORD=your_secure_password"
        exit 1
    fi

    export NEO4J_AUTH="neo4j/$NEO4J_PASSWORD"
    echo "✓ Neo4j authentication configured"

    # Configure Redis memory limits
    REDIS_MAXMEMORY=${REDIS_MAXMEMORY:-512mb}
    echo "maxmemory $REDIS_MAXMEMORY" >> /etc/redis/redis.conf
    echo "✓ Redis memory limit set to $REDIS_MAXMEMORY"
}

validate_environment

# Create qdrant config
cat > /app/qdrant.yaml << EOF
service:
  http_port: 6333
  grpc_port: 6334
  enable_cors: true

storage:
  storage_path: /app/data/qdrant

log_level: INFO
EOF

# Create neo4j user if not exists
if ! id "neo4j" &>/dev/null; then
    useradd -r -s /bin/false neo4j
fi

# Set permissions
chown -R neo4j:neo4j /var/lib/neo4j /app/data/neo4j /app/logs
chmod -R 755 /var/lib/neo4j /app/data/neo4j

# Wait for services to be ready
wait_for_service() {
    local service=$1
    local host=$2
    local port=$3
    local max_attempts=30
    local attempt=1

    echo "Waiting for $service to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if nc -z $host $port; then
            echo "$service is ready!"
            return 0
        fi
        echo "Attempt $attempt/$max_attempts: $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "ERROR: $service failed to start after $max_attempts attempts"
    return 1
}

# Pre-flight checks
echo "Running pre-flight system checks..."
if ! command -v supervisord >/dev/null 2>&1; then
    echo "ERROR: supervisord not found in PATH"
    exit 1
fi

if [ ! -f /etc/supervisor/conf.d/supervisord.conf ]; then
    echo "ERROR: supervisord configuration file not found"
    exit 1
fi

echo "✓ All pre-flight checks passed"

# Start supervisor with monitoring
echo "Starting supervisor with service monitoring..."
supervisord -c /etc/supervisor/conf.d/supervisord.conf &
SUPERVISOR_PID=$!

# Wait a bit and check if supervisor started successfully
sleep 5
if ! kill -0 "$SUPERVISOR_PID" 2>/dev/null; then
    echo "ERROR: Supervisor failed to start"
    exit 1
fi

echo "✓ Supervisor started successfully (PID: $SUPERVISOR_PID)"

# Monitor supervisor process
wait $SUPERVISOR_PID
