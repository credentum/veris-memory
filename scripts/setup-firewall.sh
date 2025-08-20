#!/bin/bash
#
# Comprehensive UFW Firewall Setup for Veris Memory
# This script configures UFW with all required rules and ensures it stays active
#

set -e

echo "🔥 Veris Memory Firewall Configuration"
echo "======================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Check if UFW is installed
if ! command -v ufw &> /dev/null; then
    echo "📦 Installing UFW..."
    apt-get update && apt-get install -y ufw
fi

echo ""
echo "📋 Current UFW Status:"
ufw status verbose || true

echo ""
echo "🛡️ Configuring UFW defaults..."

# Set default policies
ufw default deny incoming
ufw default allow outgoing

echo ""
echo "➕ Adding essential service rules..."

# SSH (port 22) - Always allow to prevent lockout
ufw allow 22/tcp comment 'SSH'

# Claude dev container SSH
ufw allow 2222/tcp comment 'Claude CLI dev container'

# Mosh UDP range (for persistent mobile connections)
ufw allow 60000:61000/udp comment 'Mosh UDP range'

# Veris Memory services
ufw allow 8000/tcp comment 'Veris Memory API'
ufw allow 8080/tcp comment 'Monitoring Dashboard'
ufw allow 9090/tcp comment 'Sentinel Monitoring API'

# Optional: Database ports (comment out if not needed externally)
# ufw allow 6333/tcp comment 'Qdrant Vector DB'
# ufw allow 6334/tcp comment 'Qdrant gRPC'
# ufw allow 7474/tcp comment 'Neo4j HTTP'
# ufw allow 7687/tcp comment 'Neo4j Bolt'
# ufw allow 6379/tcp comment 'Redis'

# Allow specific IPs if needed (from existing config)
# These were in your saved rules:
ufw allow from 4.155.74.48 to any port 22 comment 'Specific SSH access'
ufw allow from 4.155.45.99 comment 'Trusted IP'

echo ""
echo "🐳 Configuring Docker compatibility..."

# Docker uses iptables directly, we need to configure UFW to work with it
# This prevents UFW from blocking Docker's port forwarding

# Check if Docker is installed
if command -v docker &> /dev/null; then
    # Update UFW to work with Docker
    if ! grep -q "# Docker compatibility" /etc/ufw/after.rules 2>/dev/null; then
        echo "Adding Docker compatibility rules..."
        cat >> /etc/ufw/after.rules << 'EOF'

# Docker compatibility - Added by Veris Memory setup
*filter
:DOCKER-USER - [0:0]
-A DOCKER-USER -j RETURN
COMMIT
EOF
    fi
fi

echo ""
echo "🔄 Enabling UFW and ensuring it starts on boot..."

# Enable UFW to start on boot
systemctl enable ufw

# Enable UFW (force to avoid prompt)
ufw --force enable

# Reload to apply all changes
ufw reload

echo ""
echo "✅ Firewall Configuration Complete!"
echo ""
echo "📊 Final UFW Status:"
ufw status numbered

echo ""
echo "🔍 Services Protected:"
echo "  ✅ SSH:        Port 22"
echo "  ✅ Claude:     Port 2222"
echo "  ✅ Mosh:       Ports 60000-61000/udp"
echo "  ✅ API:        Port 8000"
echo "  ✅ Dashboard:  Port 8080"
echo "  ✅ Sentinel:   Port 9090"

echo ""
echo "⚠️  Important Notes:"
echo "  - Firewall is now ACTIVE and will persist across reboots"
echo "  - Docker services remain accessible (Docker manages its own iptables rules)"
echo "  - Database ports are not exposed externally (access via Docker network only)"

# Verify critical services are still accessible
echo ""
echo "🧪 Testing service accessibility..."

# Test if services respond (don't fail script if they don't)
echo -n "  API (8000): "
timeout 2 curl -s http://localhost:8000 > /dev/null 2>&1 && echo "✅ Responding" || echo "⚠️ Not responding (service may be down)"

echo -n "  Dashboard (8080): "
timeout 2 curl -s http://localhost:8080 > /dev/null 2>&1 && echo "✅ Responding" || echo "⚠️ Not responding (service may be down)"

echo -n "  Sentinel (9090): "
timeout 2 curl -s http://localhost:9090/status > /dev/null 2>&1 && echo "✅ Responding" || echo "⚠️ Not responding (service may be down)"

echo ""
echo "🎉 Firewall setup complete!"