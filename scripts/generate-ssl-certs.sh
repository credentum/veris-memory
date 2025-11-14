#!/bin/bash
#
# GENERATE SSL CERTIFICATES FOR VOICE-BOT
# Purpose: Generate self-signed SSL certificates for development/testing
#
# For production, replace with certificates from a trusted CA (Let's Encrypt, etc.)
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         SSL Certificate Generation for Voice-Bot          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CERTS_DIR="${REPO_ROOT}/voice-bot/certs"

# Parse arguments
CERT_TYPE="${1:-self-signed}"
DOMAIN="${2:-localhost}"
DAYS_VALID="${3:-365}"

# Create certs directory
mkdir -p "${CERTS_DIR}"

case "$CERT_TYPE" in
    self-signed)
        echo -e "${BLUE}Generating self-signed SSL certificate...${NC}"
        echo "  Domain: ${DOMAIN}"
        echo "  Valid for: ${DAYS_VALID} days"
        echo ""

        # Generate private key
        echo -e "${BLUE}[1/3] Generating private key...${NC}"
        openssl genrsa -out "${CERTS_DIR}/key.pem" 2048 2>/dev/null
        chmod 600 "${CERTS_DIR}/key.pem"
        echo -e "${GREEN}✓ Private key generated: ${CERTS_DIR}/key.pem${NC}"

        # Generate certificate signing request (CSR)
        echo -e "${BLUE}[2/3] Generating certificate signing request...${NC}"
        openssl req -new -key "${CERTS_DIR}/key.pem" -out "${CERTS_DIR}/csr.pem" \
            -subj "/C=US/ST=State/L=City/O=Veris Memory/OU=Voice Bot/CN=${DOMAIN}" 2>/dev/null
        echo -e "${GREEN}✓ CSR generated: ${CERTS_DIR}/csr.pem${NC}"

        # Generate self-signed certificate
        echo -e "${BLUE}[3/3] Generating self-signed certificate...${NC}"
        openssl x509 -req -days ${DAYS_VALID} \
            -in "${CERTS_DIR}/csr.pem" \
            -signkey "${CERTS_DIR}/key.pem" \
            -out "${CERTS_DIR}/cert.pem" \
            -extfile <(printf "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},DNS:localhost,IP:127.0.0.1") 2>/dev/null
        chmod 644 "${CERTS_DIR}/cert.pem"
        echo -e "${GREEN}✓ Certificate generated: ${CERTS_DIR}/cert.pem${NC}"

        # Verify certificate
        echo ""
        echo -e "${BLUE}Certificate Details:${NC}"
        openssl x509 -in "${CERTS_DIR}/cert.pem" -noout -subject -dates -ext subjectAltName 2>/dev/null

        # Create README
        cat > "${CERTS_DIR}/README.md" << EOF
# SSL Certificates for Voice-Bot

## Current Certificate Type: Self-Signed

**Generated:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Domain:** ${DOMAIN}
**Valid For:** ${DAYS_VALID} days
**Expires:** $(openssl x509 -in "${CERTS_DIR}/cert.pem" -noout -enddate 2>/dev/null | cut -d= -f2)

## Files

- \`key.pem\` - Private key (keep secret!)
- \`cert.pem\` - Self-signed certificate
- \`csr.pem\` - Certificate signing request (for CA signing)

## Security Warning

⚠️ **Self-signed certificates are for DEVELOPMENT/TESTING ONLY!**

For production:
1. Use certificates from a trusted CA (Let's Encrypt, etc.)
2. Replace key.pem and cert.pem with CA-signed certificates
3. Ensure key.pem has proper permissions (600)

## Regenerate Certificates

To regenerate certificates:
\`\`\`bash
bash scripts/generate-ssl-certs.sh self-signed ${DOMAIN} ${DAYS_VALID}
\`\`\`

## Use Let's Encrypt (Production)

For production with Let's Encrypt:
\`\`\`bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ${CERTS_DIR}/key.pem
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ${CERTS_DIR}/cert.pem
sudo chmod 600 ${CERTS_DIR}/key.pem
sudo chmod 644 ${CERTS_DIR}/cert.pem
\`\`\`

## Browser Trust (Development)

To trust self-signed certificate in your browser:

**Chrome/Edge:**
1. Visit https://localhost:8443
2. Click "Advanced" → "Proceed to localhost (unsafe)"
3. Or add certificate to system trust store

**Firefox:**
1. Visit https://localhost:8443
2. Click "Advanced" → "Accept the Risk and Continue"

**System Trust (Linux):**
\`\`\`bash
sudo cp ${CERTS_DIR}/cert.pem /usr/local/share/ca-certificates/voice-bot.crt
sudo update-ca-certificates
\`\`\`
EOF

        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║    ✅ Self-Signed SSL Certificates Generated ✅           ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  WARNING: Self-signed certificates are for DEVELOPMENT ONLY!${NC}"
        echo -e "${YELLOW}   For production, use certificates from a trusted CA.${NC}"
        echo ""
        echo -e "${BLUE}Files created:${NC}"
        echo "  • ${CERTS_DIR}/key.pem (private key)"
        echo "  • ${CERTS_DIR}/cert.pem (certificate)"
        echo "  • ${CERTS_DIR}/csr.pem (certificate signing request)"
        echo "  • ${CERTS_DIR}/README.md (documentation)"
        echo ""
        echo -e "${BLUE}Next steps:${NC}"
        echo "  1. Review ${CERTS_DIR}/README.md for production setup"
        echo "  2. Deploy voice services: docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d"
        echo "  3. Access voice-bot at: https://localhost:8443 or https://${DOMAIN}:8443"
        echo ""
        ;;

    letsencrypt)
        echo -e "${BLUE}Setting up Let's Encrypt certificate...${NC}"
        echo "  Domain: ${DOMAIN}"
        echo ""

        # Check if certbot is installed
        if ! command -v certbot &> /dev/null; then
            echo -e "${RED}ERROR: certbot is not installed${NC}"
            echo "Install with: sudo apt-get install certbot"
            exit 1
        fi

        # Check if running as root
        if [[ $EUID -ne 0 ]]; then
            echo -e "${RED}ERROR: Let's Encrypt setup requires root privileges${NC}"
            echo "Run with: sudo $0 letsencrypt ${DOMAIN}"
            exit 1
        fi

        echo -e "${YELLOW}This will obtain a certificate from Let's Encrypt for: ${DOMAIN}${NC}"
        echo -e "${YELLOW}Make sure:${NC}"
        echo "  1. Domain ${DOMAIN} points to this server's public IP"
        echo "  2. Port 80 is accessible from the internet"
        echo "  3. No other service is using port 80"
        echo ""
        read -p "Continue? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Obtain certificate
            certbot certonly --standalone -d "${DOMAIN}"

            # Copy certificates
            cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${CERTS_DIR}/key.pem"
            cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${CERTS_DIR}/cert.pem"
            chmod 600 "${CERTS_DIR}/key.pem"
            chmod 644 "${CERTS_DIR}/cert.pem"

            echo -e "${GREEN}✓ Let's Encrypt certificate installed${NC}"
            echo ""
            echo "Certificate will auto-renew. To manually renew:"
            echo "  sudo certbot renew"
        else
            echo "Cancelled."
            exit 1
        fi
        ;;

    *)
        echo -e "${RED}ERROR: Invalid certificate type: ${CERT_TYPE}${NC}"
        echo ""
        echo "Usage: $0 [TYPE] [DOMAIN] [DAYS_VALID]"
        echo ""
        echo "Types:"
        echo "  self-signed  - Generate self-signed certificate (default)"
        echo "  letsencrypt  - Use Let's Encrypt (requires sudo)"
        echo ""
        echo "Examples:"
        echo "  $0 self-signed localhost 365"
        echo "  $0 letsencrypt voice.example.com"
        exit 1
        ;;
esac
