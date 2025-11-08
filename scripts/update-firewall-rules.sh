#!/bin/bash
#
# Update firewall rules for Veris Memory services
# This script adds UFW rules for all exposed services
#

set -e

echo "🔥 Updating firewall rules for Veris Memory services..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Check if ufw is installed
if ! command -v ufw &> /dev/null; then
    echo "❌ UFW is not installed"
    exit 1
fi

echo "📋 Current UFW status:"
ufw status numbered

echo ""
echo "➕ Adding rules for Veris Memory services..."

# Core services
ufw allow 8000/tcp comment 'Veris Memory MCP Server'
ufw allow 8001/tcp comment 'Veris Memory REST API'
ufw allow 8002/tcp comment 'Voice-Bot API'
ufw allow 8080/tcp comment 'Monitoring Dashboard'
ufw allow 9090/tcp comment 'Sentinel Monitoring API'

# Database services (optional - only if external access needed)
# Uncomment these if you need external access to databases
# ufw allow 6333/tcp comment 'Qdrant Vector DB'
# ufw allow 6334/tcp comment 'Qdrant gRPC'
# ufw allow 7474/tcp comment 'Neo4j HTTP'
# ufw allow 7687/tcp comment 'Neo4j Bolt'
# ufw allow 6379/tcp comment 'Redis'

echo ""
echo "✅ Firewall rules added!"
echo ""
echo "📋 Updated UFW status:"
ufw status numbered

echo ""
echo "🎉 Firewall configuration complete!"
echo ""
echo "You can now access:"
echo "  - MCP Server: http://$(hostname -I | awk '{print $1}'):8000"
echo "  - REST API: http://$(hostname -I | awk '{print $1}'):8001"
echo "  - API Docs: http://$(hostname -I | awk '{print $1}'):8001/docs"
echo "  - Voice-Bot: http://$(hostname -I | awk '{print $1}'):8002"
echo "  - Voice Docs: http://$(hostname -I | awk '{print $1}'):8002/docs"
echo "  - Dashboard: http://$(hostname -I | awk '{print $1}'):8080"
echo "  - Sentinel: http://$(hostname -I | awk '{print $1}'):9090/status"