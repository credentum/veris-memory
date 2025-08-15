#!/bin/bash
set -euo pipefail

# Auto-deployment setup script for Hetzner Context Store
# This script configures automatic startup of the main MCP server application

echo "🚀 Setting up auto-deployment for Context Store..."

# Ensure we're in the right directory
cd "$(dirname "$0")/.."

# Install Python dependencies if not already installed
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install -e .
pip install duckdb sentence-transformers scikit-learn

# Setup secure credentials first
echo "🔐 Setting up secure credentials..."
./scripts/setup-secure-credentials.sh

# Get the Neo4j password for docker-compose consistency
NEO4J_PASSWORD=$(sudo cat /opt/context-store/credentials/neo4j_password)
echo "🔗 Synchronizing Neo4j password with Docker containers..."

# If docker-compose is already running with different password, restart with correct one
if docker ps | grep -q neo4j; then
    echo "⚠️  Neo4j container running with potentially different password - restarting..."
    export NEO4J_PASSWORD="$NEO4J_PASSWORD"
    docker-compose -f docker/docker-compose.simple.yml down neo4j || true
    docker-compose -f docker/docker-compose.simple.yml up -d neo4j
    echo "⏳ Waiting for Neo4j to restart with new password..."
    sleep 15
fi

# Install systemd service
echo "🔧 Installing systemd service..."
sudo cp systemd/context-store.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable context-store

# Create data directories
echo "📁 Creating data directories..."
sudo mkdir -p /raid1/docker-data/{context-store,logs}
sudo chown -R $(whoami):$(whoami) /raid1/docker-data/ || true

# Start infrastructure services (Docker Compose)
echo "🐳 Starting infrastructure services..."
docker-compose -f docker/docker-compose.simple.yml up -d redis neo4j qdrant

# Start main application service
echo "⚡ Starting main application service..."
sudo systemctl start context-store

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health &>/dev/null; then
        echo "✅ Service is ready!"
        break
    fi
    echo "   Waiting... ($i/30)"
    sleep 2
done

# Show status
echo ""
echo "📊 Deployment Status:"
echo "Infrastructure services:"
docker-compose -f docker/docker-compose.simple.yml ps

echo ""
echo "Main application service:"
sudo systemctl status context-store --no-pager -l

echo ""
echo "Health check:"
curl -s http://localhost:8000/health | jq . 2>/dev/null || curl -s http://localhost:8000/health

echo ""
echo "🎉 Auto-deployment setup complete!"
echo "The Context Store will now start automatically on boot and restart on failure."