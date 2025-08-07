#!/bin/bash
set -euo pipefail

# Trap handler for cleanup on failure
cleanup_on_error() {
    local exit_code=$?
    error "Deployment failed with exit code $exit_code"
    log "Cleaning up temporary files..."
    # Add any specific cleanup tasks here
    exit $exit_code
}

trap cleanup_on_error ERR

# Hetzner Dedicated Server Deployment Script for Context Store
# Optimized for AMD Ryzen 5 5600X, 64GB RAM, RAID1 NVMe setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Configuration
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-veris-memory-hetzner}"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.hetzner.yml"
CONFIG_FILE="${PROJECT_ROOT}/.ctxrc.hetzner.yaml"
RAID1_PATH="/raid1/docker-data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if running as root or with sudo
check_privileges() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Use a regular user with sudo privileges."
        exit 1
    fi

    if ! sudo -n true 2>/dev/null; then
        error "This script requires sudo privileges. Please run 'sudo -v' first."
        exit 1
    fi
}

# Validate environment variables
validate_environment() {
    log "Validating environment variables..."

    local required_vars=(
        "NEO4J_PASSWORD"
        "TAILSCALE_AUTHKEY"
    )

    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            error "  - $var"
        done
        error "Please set these variables and try again."
        exit 1
    fi

    success "Environment validation passed"
}

# Check system requirements
check_system_requirements() {
    log "Checking system requirements..."

    # Check Ubuntu version
    if ! grep -q "Ubuntu 24.04" /etc/os-release; then
        warning "This script is optimized for Ubuntu 24.04. Current system may have compatibility issues."
    fi

    # Check available memory (should be ~64GB)
    local total_mem=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local total_mem_gb=$((total_mem / 1024 / 1024))

    if [[ $total_mem_gb -lt 60 ]]; then
        error "Insufficient memory: ${total_mem_gb}GB detected, 64GB recommended"
        exit 1
    fi

    log "Memory check passed: ${total_mem_gb}GB available"

    # Check CPU cores (should be 6 cores, 12 threads)
    local cpu_cores=$(nproc)
    if [[ $cpu_cores -lt 12 ]]; then
        warning "CPU cores: ${cpu_cores} detected, 12 threads (6 cores) recommended"
    fi

    # Check RAID1 mount point
    if [[ ! -d "$RAID1_PATH" ]]; then
        error "RAID1 mount point not found: $RAID1_PATH"
        error "Please ensure RAID1 is properly configured and mounted"
        exit 1
    fi

    success "System requirements check passed"
}

# Setup RAID1 directory structure
setup_raid1_directories() {
    log "Setting up RAID1 directory structure..."

    local directories=(
        "$RAID1_PATH"
        "$RAID1_PATH/qdrant"
        "$RAID1_PATH/neo4j/data"
        "$RAID1_PATH/neo4j/logs"
        "$RAID1_PATH/neo4j/import"
        "$RAID1_PATH/redis"
        "$RAID1_PATH/context-store"
        "$RAID1_PATH/logs"
        "$RAID1_PATH/monitoring"
        "$RAID1_PATH/backups"
        "$RAID1_PATH/duckdb-tmp"
    )

    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log "Creating directory: $dir"
            sudo mkdir -p "$dir"
            sudo chown -R "$(whoami):$(whoami)" "$dir"
            sudo chmod -R 755 "$dir"
        fi
    done

    success "RAID1 directories setup completed"
}

# Install Docker if not present
install_docker() {
    if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
        log "Docker already installed"
        return
    fi

    log "Installing Docker..."

    # Remove old versions
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Install dependencies
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg lsb-release

    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Add current user to docker group
    sudo usermod -aG docker "$(whoami)"

    # Install docker-compose (standalone) with checksum verification
    local compose_version="v2.29.7"
    local compose_url="https://github.com/docker/compose/releases/download/${compose_version}/docker-compose-linux-x86_64"
    local compose_checksum="7f73acd4a0c4afb8088100f28aba5e74c4bd1e14a2f78f1e0c4e7d93f73d18e9"
    
    log "Installing Docker Compose ${compose_version} with checksum verification..."
    curl -L "${compose_url}" -o /tmp/docker-compose
    
    local actual_checksum=$(sha256sum /tmp/docker-compose | cut -d' ' -f1)
    if [[ "${actual_checksum}" != "${compose_checksum}" ]]; then
        error "Docker Compose checksum verification failed!"
        error "Expected: ${compose_checksum}"
        error "Actual:   ${actual_checksum}"
        rm -f /tmp/docker-compose
        exit 1
    fi
    
    success "Docker Compose checksum verification passed"
    sudo mv /tmp/docker-compose /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    success "Docker installation completed"
    warning "Please log out and log back in for Docker group membership to take effect"
}

# Install Tailscale if not present
install_tailscale() {
    if command -v tailscale &> /dev/null; then
        log "Tailscale already installed"
        return
    fi

    log "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    success "Tailscale installation completed"
}

# Configure Tailscale
configure_tailscale() {
    log "Configuring Tailscale..."

    # Check if already connected
    if sudo tailscale status &> /dev/null; then
        log "Tailscale already connected"
        return
    fi

    # Connect to Tailscale
    log "Connecting to Tailscale with hostname: $TAILSCALE_HOSTNAME"
    sudo tailscale up --authkey="$TAILSCALE_AUTHKEY" --hostname="$TAILSCALE_HOSTNAME" \
        --accept-routes --accept-dns

    success "Tailscale configured successfully"
}

# Configure firewall for security
configure_firewall() {
    log "Configuring UFW firewall..."

    # Enable UFW
    sudo ufw --force enable

    # Default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing

    # Allow Tailscale subnet (CGNAT range)
    sudo ufw allow from 100.64.0.0/10

    # Allow SSH from Tailscale network only
    sudo ufw allow from 100.64.0.0/10 to any port 22

    # Allow Docker networks
    sudo ufw allow in on docker0
    sudo ufw allow in on br-context-store

    success "Firewall configured for Tailscale-only access"
}

# Build Docker images
build_images() {
    log "Building Docker images for Hetzner deployment..."

    cd "$PROJECT_ROOT"

    # Build the Hetzner-optimized image
    log "Building context-store:hetzner image..."
    docker build -f Dockerfile.hetzner -t context-store:hetzner .

    success "Docker images built successfully"
}

# Deploy services
deploy_services() {
    log "Deploying services with docker-compose..."

    cd "$PROJECT_ROOT"

    # Copy Hetzner configuration
    cp .ctxrc.hetzner.yaml .ctxrc.yaml

    # Pull latest images (except our custom build)
    docker-compose -f "$COMPOSE_FILE" pull redis neo4j

    # Start services
    log "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d

    success "Services deployed successfully"
}

# Wait for services to be healthy
wait_for_services() {
    log "Waiting for services to become healthy..."

    local max_attempts=30
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        local healthy_services=0
        local total_services=0

        # Check each service health
        for service in context-store qdrant neo4j redis; do
            total_services=$((total_services + 1))
            if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "healthy\|running"; then
                healthy_services=$((healthy_services + 1))
            fi
        done

        if [[ $healthy_services -eq $total_services ]]; then
            success "All services are healthy"
            return 0
        fi

        log "Services healthy: $healthy_services/$total_services (attempt $((attempt + 1))/$max_attempts)"
        sleep 10
        attempt=$((attempt + 1))
    done

    error "Services failed to become healthy within expected time"
    return 1
}

# Run post-deployment tests
run_tests() {
    log "Running post-deployment tests..."

    # Test MCP server health endpoint
    if curl -f http://localhost:8000/health &> /dev/null; then
        success "MCP server health check passed"
    else
        error "MCP server health check failed"
        return 1
    fi

    # Test Qdrant
    if curl -f http://localhost:6333/health &> /dev/null; then
        success "Qdrant health check passed"
    else
        error "Qdrant health check failed"
        return 1
    fi

    # Test Redis
    if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping | grep -q PONG; then
        success "Redis health check passed"
    else
        error "Redis health check failed"
        return 1
    fi

    # Test Neo4j (basic connection)
    if docker-compose -f "$COMPOSE_FILE" exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" &> /dev/null; then
        success "Neo4j health check passed"
    else
        error "Neo4j health check failed"
        return 1
    fi

    success "All post-deployment tests passed"
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring scripts..."

    # Make monitoring scripts executable
    chmod +x "${PROJECT_ROOT}/monitoring/"*.sh

    # Create systemd service for hardware monitoring
    sudo tee /etc/systemd/system/context-store-monitor.service > /dev/null <<EOF
[Unit]
Description=Context Store Hardware Monitor
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${PROJECT_ROOT}
ExecStart=${PROJECT_ROOT}/monitoring/hardware-monitor.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start monitoring service
    sudo systemctl daemon-reload
    sudo systemctl enable context-store-monitor
    sudo systemctl start context-store-monitor

    success "Monitoring setup completed"
}

# Display deployment summary
display_summary() {
    log "Deployment completed successfully!"
    echo
    success "Context Store is now running on Hetzner dedicated server"
    echo
    echo "Service URLs (Tailscale network only):"
    echo "  - MCP Server: http://localhost:8000"
    echo "  - Qdrant: http://localhost:6333"
    echo "  - Neo4j Browser: http://localhost:7474"
    echo "  - Redis: localhost:6379"
    echo
    echo "Configuration:"
    echo "  - Hardware: AMD Ryzen 5 5600X, 64GB RAM"
    echo "  - Storage: RAID1 NVMe at $RAID1_PATH"
    echo "  - Network: Tailscale mesh (hostname: $TAILSCALE_HOSTNAME)"
    echo "  - Security: UFW firewall, Tailscale-only access"
    echo
    echo "Management commands:"
    echo "  - View logs: docker-compose -f $COMPOSE_FILE logs -f"
    echo "  - Stop services: docker-compose -f $COMPOSE_FILE down"
    echo "  - Restart services: docker-compose -f $COMPOSE_FILE restart"
    echo "  - Monitor hardware: sudo systemctl status context-store-monitor"
    echo
    echo "Performance optimizations active:"
    echo "  - Neo4j: 20GB heap, 16GB pagecache"
    echo "  - Redis: 8GB memory allocation"
    echo "  - Qdrant: 8 search threads, gRPC enabled"
    echo "  - MCP: 64 concurrent agents, 128 Redis connections"
    echo
}

# Main deployment function
main() {
    log "Starting Hetzner dedicated server deployment..."
    echo "Hardware target: AMD Ryzen 5 5600X, 64GB RAM, RAID1 NVMe"
    echo "Software stack: Ubuntu 24.04, Docker, Tailscale"
    echo

    check_privileges
    validate_environment
    check_system_requirements
    setup_raid1_directories
    install_docker
    install_tailscale
    configure_tailscale
    configure_firewall
    build_images
    deploy_services
    wait_for_services
    run_tests
    setup_monitoring
    display_summary

    success "Deployment completed successfully!"
}

# Handle script interruption
trap 'error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"
