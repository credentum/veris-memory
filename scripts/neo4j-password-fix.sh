#!/bin/bash
# Neo4j Password Fix Script
# This script ensures Neo4j password is properly synchronized

set -e

echo "🔐 Neo4j Password Synchronization Script"
echo "========================================"

# Get the password from environment or .env file
if [ -z "$NEO4J_PASSWORD" ]; then
    if [ -f .env ]; then
        export NEO4J_PASSWORD=$(grep "^NEO4J_PASSWORD=" .env | cut -d'=' -f2)
    fi
fi

if [ -z "$NEO4J_PASSWORD" ]; then
    echo "❌ ERROR: NEO4J_PASSWORD not found in environment or .env file"
    exit 1
fi

echo "✅ NEO4J_PASSWORD found (length: ${#NEO4J_PASSWORD} characters)"

# Function to test Neo4j connection
test_neo4j_connection() {
    local password=$1
    echo -n "Testing connection with provided password... "
    
    # Try to connect using cypher-shell
    if docker exec veris-memory-neo4j-1 cypher-shell \
        -u neo4j \
        -p "$password" \
        "RETURN 1 as test" >/dev/null 2>&1; then
        echo "✅ SUCCESS"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Function to reset Neo4j password
reset_neo4j_password() {
    echo "🔄 Resetting Neo4j to use new password..."
    
    # Stop Neo4j container
    echo "  1. Stopping Neo4j container..."
    docker stop veris-memory-neo4j-1 2>/dev/null || true
    docker rm veris-memory-neo4j-1 2>/dev/null || true
    
    # Remove Neo4j volumes (this will reset the password)
    echo "  2. Removing Neo4j persistent volumes..."
    docker volume rm veris-memory_neo4j_data 2>/dev/null || true
    docker volume rm veris-memory_neo4j_logs 2>/dev/null || true
    
    # Ensure NEO4J_AUTH is set in .env
    echo "  3. Updating .env file..."
    if ! grep -q "^NEO4J_AUTH=" .env; then
        echo "NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}" >> .env
    else
        sed -i "s|^NEO4J_AUTH=.*|NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}|" .env
    fi
    
    # Start Neo4j with new password
    echo "  4. Starting Neo4j with new password..."
    docker compose up -d neo4j
    
    # Wait for Neo4j to be ready
    echo "  5. Waiting for Neo4j to initialize (this may take 30-60 seconds)..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec veris-memory-neo4j-1 cypher-shell \
            -u neo4j \
            -p "$NEO4J_PASSWORD" \
            "RETURN 1 as test" >/dev/null 2>&1; then
            echo "  ✅ Neo4j is ready with new password!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    echo "  ❌ Neo4j failed to start with new password"
    return 1
}

# Main logic
echo ""
echo "🔍 Checking current Neo4j authentication status..."

# First, check if Neo4j container exists
if ! docker ps -a | grep -q veris-memory-neo4j-1; then
    echo "⚠️  Neo4j container doesn't exist. It will be created during deployment."
    exit 0
fi

# Test current connection
if test_neo4j_connection "$NEO4J_PASSWORD"; then
    echo "✅ Neo4j is already configured with the correct password!"
    exit 0
fi

echo "⚠️  Neo4j authentication failed with current password"
echo ""

# Ask for confirmation before resetting (in CI, auto-confirm)
if [ -z "$CI" ]; then
    read -p "Do you want to reset Neo4j to use the password from .env? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Aborted by user"
        exit 1
    fi
else
    echo "🤖 Running in CI mode - auto-confirming reset"
fi

# Reset Neo4j password
if reset_neo4j_password; then
    echo ""
    echo "✅ Neo4j password successfully synchronized!"
    echo ""
    
    # Final verification
    echo "🔍 Final verification..."
    if test_neo4j_connection "$NEO4J_PASSWORD"; then
        echo "✅ Neo4j is working correctly with the new password"
        exit 0
    else
        echo "❌ Verification failed - please check logs"
        exit 1
    fi
else
    echo ""
    echo "❌ Failed to reset Neo4j password"
    echo "Please check Docker logs for more information:"
    echo "  docker logs veris-memory-neo4j-1"
    exit 1
fi