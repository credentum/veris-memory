#!/bin/bash
#
# DOCKER FIREWALL RULES CONFIGURATION
# Purpose: Make Docker respect UFW/iptables firewall rules
#
# Problem: Docker manipulates iptables directly and bypasses UFW
# Solution: Add rules to DOCKER-USER chain which runs before Docker's rules
#
# This script implements the firewall rules described in:
# - SECURITY_REMEDIATION_PLAN.md Phase 1.1
# - FIREWALL-DOCKER.md
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Docker Firewall Rules Configuration (DOCKER-USER)    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR: This script must be run as root or with sudo${NC}"
    exit 1
fi

# Database ports that should be blocked from external access
BLOCKED_PORTS=(6333 6334 6379 7474 7687)

# Backup current iptables rules
backup_iptables() {
    echo -e "${BLUE}[1/5] Backing up current iptables rules...${NC}"

    BACKUP_DIR="/opt/veris-memory-backups/iptables"
    mkdir -p "${BACKUP_DIR}"

    BACKUP_FILE="${BACKUP_DIR}/iptables-backup-$(date +%Y%m%d-%H%M%S).rules"
    iptables-save > "${BACKUP_FILE}"

    echo -e "${GREEN}✓ Backup saved to: ${BACKUP_FILE}${NC}"
}

# Configure Docker daemon for security
configure_docker_daemon() {
    echo -e "${BLUE}[2/5] Configuring Docker daemon security settings...${NC}"

    DOCKER_CONFIG="/etc/docker/daemon.json"
    DOCKER_CONFIG_BACKUP="${DOCKER_CONFIG}.backup-$(date +%Y%m%d-%H%M%S)"

    # Backup existing config if it exists
    if [[ -f "${DOCKER_CONFIG}" ]]; then
        cp "${DOCKER_CONFIG}" "${DOCKER_CONFIG_BACKUP}"
        echo "Backed up existing daemon.json to: ${DOCKER_CONFIG_BACKUP}"
    fi

    # Create secure Docker daemon configuration
    cat > "${DOCKER_CONFIG}" << 'EOF'
{
  "icc": false,
  "userland-proxy": false,
  "iptables": true,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "no-new-privileges": true,
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 64000,
      "Soft": 64000
    }
  }
}
EOF

    echo -e "${GREEN}✓ Docker daemon configuration updated${NC}"
    echo -e "${YELLOW}NOTE: Docker daemon restart required for changes to take effect${NC}"
}

# Create DOCKER-USER iptables rules
create_docker_user_rules() {
    echo -e "${BLUE}[3/5] Creating DOCKER-USER iptables rules...${NC}"

    # Flush existing DOCKER-USER rules
    echo "Flushing existing DOCKER-USER chain..."
    iptables -F DOCKER-USER 2>/dev/null || true

    # Rule 1: Allow established and related connections
    echo "  → Adding rule: Allow ESTABLISHED,RELATED connections"
    iptables -A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

    # Rule 2: Allow all traffic from localhost
    echo "  → Adding rule: Allow localhost (127.0.0.0/8)"
    iptables -A DOCKER-USER -s 127.0.0.0/8 -j RETURN
    iptables -A DOCKER-USER -i lo -j RETURN

    # Rule 3: Allow Docker internal network communication
    echo "  → Adding rule: Allow Docker internal networks (172.16.0.0/12, 10.0.0.0/8)"
    iptables -A DOCKER-USER -s 172.16.0.0/12 -d 172.16.0.0/12 -j RETURN
    iptables -A DOCKER-USER -s 10.0.0.0/8 -d 10.0.0.0/8 -j RETURN

    # Rule 4: Allow Tailscale/VPN network (if configured)
    # Tailscale typically uses 100.64.0.0/10
    if ip addr | grep -q "100.64"; then
        echo "  → Adding rule: Allow Tailscale VPN network (100.64.0.0/10)"
        iptables -A DOCKER-USER -s 100.64.0.0/10 -j RETURN
    fi

    # Rule 5: Block external access to database ports
    echo "  → Adding rules: Block external access to database ports"
    for port in "${BLOCKED_PORTS[@]}"; do
        echo "    • Blocking port ${port}/tcp from external access"
        iptables -I DOCKER-USER -p tcp --dport ${port} ! -s 127.0.0.0/8 ! -s 172.16.0.0/12 ! -s 10.0.0.0/8 -j DROP

        echo "    • Blocking port ${port}/udp from external access"
        iptables -I DOCKER-USER -p udp --dport ${port} ! -s 127.0.0.0/8 ! -s 172.16.0.0/12 ! -s 10.0.0.0/8 -j DROP
    done

    # Rule 6: Log dropped packets (for monitoring)
    echo "  → Adding rule: Log dropped packets"
    iptables -A DOCKER-USER -j LOG --log-prefix "DOCKER-USER-DROP: " --log-level 4 -m limit --limit 5/min

    # Rule 7: Default return for allowed traffic
    echo "  → Adding rule: Default RETURN for allowed traffic"
    iptables -A DOCKER-USER -j RETURN

    echo -e "${GREEN}✓ DOCKER-USER rules created${NC}"
}

# Make iptables rules persistent
make_persistent() {
    echo -e "${BLUE}[4/5] Making iptables rules persistent...${NC}"

    # Install iptables-persistent if not installed
    if ! command -v iptables-save &> /dev/null; then
        echo "Installing iptables-persistent..."
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
    fi

    # Save rules
    iptables-save > /etc/iptables/rules.v4
    ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true

    echo -e "${GREEN}✓ Iptables rules saved to /etc/iptables/rules.v4${NC}"

    # Create systemd service to restore rules on boot
    cat > /etc/systemd/system/docker-firewall.service << 'EOF'
[Unit]
Description=Docker Firewall Rules (DOCKER-USER)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable docker-firewall.service

    echo -e "${GREEN}✓ Systemd service created: docker-firewall.service${NC}"
}

# Verify configuration
verify_rules() {
    echo -e "${BLUE}[5/5] Verifying Docker firewall configuration...${NC}"

    local verification_failed=0

    # Check DOCKER-USER chain exists and has rules
    echo "Checking DOCKER-USER chain..."
    if iptables -L DOCKER-USER -n &>/dev/null; then
        local rule_count=$(iptables -L DOCKER-USER -n | grep -c "^" || echo "0")
        echo -e "${GREEN}✓ DOCKER-USER chain exists with ${rule_count} rules${NC}"
    else
        echo -e "${RED}✗ DOCKER-USER chain not found${NC}"
        verification_failed=1
    fi

    # Check if DROP rules exist for database ports
    echo "Checking DROP rules for database ports..."
    for port in "${BLOCKED_PORTS[@]}"; do
        if iptables -L DOCKER-USER -n | grep -q "dpt:${port}.*DROP"; then
            echo -e "${GREEN}✓ DROP rule exists for port ${port}${NC}"
        else
            echo -e "${RED}✗ DROP rule missing for port ${port}${NC}"
            verification_failed=1
        fi
    done

    # Display current DOCKER-USER rules
    echo ""
    echo "Current DOCKER-USER rules:"
    iptables -L DOCKER-USER -n -v --line-numbers

    if [[ ${verification_failed} -eq 0 ]]; then
        echo ""
        echo -e "${GREEN}✓ Docker firewall verification passed${NC}"
        return 0
    else
        echo ""
        echo -e "${RED}✗ Docker firewall verification failed${NC}"
        return 1
    fi
}

# Restart Docker daemon
restart_docker() {
    echo ""
    echo -e "${YELLOW}Docker daemon configuration has been updated.${NC}"
    read -p "Restart Docker daemon now? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Restarting Docker daemon..."
        systemctl restart docker
        sleep 5

        if systemctl is-active --quiet docker; then
            echo -e "${GREEN}✓ Docker daemon restarted successfully${NC}"
        else
            echo -e "${RED}✗ Docker daemon failed to restart${NC}"
            echo "Check logs with: journalctl -u docker -n 50"
            exit 1
        fi
    else
        echo -e "${YELLOW}Remember to restart Docker daemon later: sudo systemctl restart docker${NC}"
    fi
}

# Main execution
main() {
    backup_iptables
    configure_docker_daemon
    create_docker_user_rules
    make_persistent

    if verify_rules; then
        restart_docker

        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║    ✅ Docker Firewall Configuration Completed ✅          ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${BLUE}Next Steps:${NC}"
        echo "1. Test database ports are blocked from external access"
        echo "2. Verify services can still communicate internally"
        echo "3. Monitor logs: tail -f /var/log/kern.log | grep DOCKER-USER-DROP"
        echo "4. Proceed to Phase 1.2 of SECURITY_REMEDIATION_PLAN.md"
        echo ""
        echo -e "${BLUE}To view rules:${NC} iptables -L DOCKER-USER -n -v"
        echo -e "${BLUE}To disable:${NC} iptables -F DOCKER-USER"
        exit 0
    else
        echo ""
        echo -e "${RED}Configuration failed. Check the output above.${NC}"
        exit 1
    fi
}

# Execute
main "$@"
