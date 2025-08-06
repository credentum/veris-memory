#!/bin/bash
# Secrets management helper for Fly.io deployment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="veris-memory"

show_usage() {
    cat << EOF
Veris Memory Secrets Management Helper

Usage: $0 COMMAND [OPTIONS]

Commands:
  setup-secrets          Set up all required secrets for production deployment
  validate-secrets       Validate that all required secrets are set
  rotate-neo4j-password  Rotate Neo4j password
  show-secrets           Show current secrets (names only, not values)
  help                   Show this help message

Options:
  --app-name NAME       Fly.io app name (default: veris-memory)
  --dry-run            Show what would be done without executing

Examples:
  $0 setup-secrets
  $0 validate-secrets --app-name my-veris-app
  $0 rotate-neo4j-password

Required Fly.io secrets:
  - NEO4J_PASSWORD: Strong password for Neo4j database
  
Optional secrets:
  - REDIS_MAXMEMORY: Redis memory limit (default: 512mb)
  - EMBEDDING_MODEL: Sentence transformers model (default: all-MiniLM-L6-v2)
  - EXTERNAL_MONITORING: Enable external monitoring (true/false)
  - MONITORING_WEBHOOK_URL: Webhook for health alerts
EOF
}

generate_secure_password() {
    # Generate a secure 32-character password with mixed case, numbers, and symbols
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

setup_secrets() {
    local app_name=${1:-$APP_NAME}
    local dry_run=${2:-false}
    
    echo "Setting up secrets for Fly.io app: $app_name"
    
    # Generate secure Neo4j password
    local neo4j_password
    neo4j_password=$(generate_secure_password)
    
    echo "Generated secure Neo4j password"
    
    if [ "$dry_run" = true ]; then
        echo "[DRY RUN] Would set NEO4J_PASSWORD"
        echo "[DRY RUN] Password would be: ${neo4j_password:0:8}... (truncated)"
    else
        echo "Setting NEO4J_PASSWORD secret..."
        if flyctl secrets set NEO4J_PASSWORD="$neo4j_password" --app "$app_name"; then
            echo "✓ NEO4J_PASSWORD set successfully"
        else
            echo "❌ Failed to set NEO4J_PASSWORD"
            return 1
        fi
    fi
    
    # Optional: Set other production secrets
    local optional_secrets=(
        "REDIS_MAXMEMORY=1gb"
        "EMBEDDING_MODEL=all-MiniLM-L6-v2"
        "LOG_LEVEL=info"
    )
    
    echo ""
    echo "Optional secrets (you can set these manually if needed):"
    for secret in "${optional_secrets[@]}"; do
        echo "  flyctl secrets set $secret --app $app_name"
    done
    
    echo ""
    echo "✅ Core secrets setup complete!"
    echo ""
    echo "IMPORTANT: Save your Neo4j password securely!"
    echo "Password: $neo4j_password"
    echo ""
    echo "Next steps:"
    echo "1. Deploy your application: flyctl deploy --app $app_name"
    echo "2. Check deployment status: flyctl status --app $app_name"
    echo "3. View logs: flyctl logs --app $app_name"
}

validate_secrets() {
    local app_name=${1:-$APP_NAME}
    
    echo "Validating secrets for app: $app_name"
    
    # Check required secrets
    local required_secrets=("NEO4J_PASSWORD")
    local missing_secrets=()
    
    for secret in "${required_secrets[@]}"; do
        if flyctl secrets list --app "$app_name" | grep -q "$secret"; then
            echo "✓ $secret is set"
        else
            echo "❌ $secret is missing"
            missing_secrets+=("$secret")
        fi
    done
    
    if [ ${#missing_secrets[@]} -eq 0 ]; then
        echo "✅ All required secrets are configured"
        return 0
    else
        echo "❌ Missing required secrets: ${missing_secrets[*]}"
        echo "Run: $0 setup-secrets --app-name $app_name"
        return 1
    fi
}

rotate_neo4j_password() {
    local app_name=${1:-$APP_NAME}
    local dry_run=${2:-false}
    
    echo "Rotating Neo4j password for app: $app_name"
    
    # Generate new password
    local new_password
    new_password=$(generate_secure_password)
    
    echo "Generated new secure password"
    
    if [ "$dry_run" = true ]; then
        echo "[DRY RUN] Would update NEO4J_PASSWORD"
        echo "[DRY RUN] New password would be: ${new_password:0:8}... (truncated)"
    else
        echo "⚠️  This will restart your application!"
        read -p "Continue with password rotation? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if flyctl secrets set NEO4J_PASSWORD="$new_password" --app "$app_name"; then
                echo "✓ Neo4j password rotated successfully"
                echo "New password: $new_password"
                echo "Please save this password securely!"
            else
                echo "❌ Failed to rotate password"
                return 1
            fi
        else
            echo "Password rotation cancelled"
        fi
    fi
}

show_secrets() {
    local app_name=${1:-$APP_NAME}
    
    echo "Current secrets for app: $app_name"
    echo "========================================"
    
    if command -v flyctl >/dev/null 2>&1; then
        flyctl secrets list --app "$app_name" 2>/dev/null || {
            echo "❌ Unable to retrieve secrets. Make sure you're logged in to Fly.io"
            echo "Run: flyctl auth login"
            return 1
        }
    else
        echo "❌ flyctl command not found. Please install Fly.io CLI"
        return 1
    fi
}

check_flyctl() {
    if ! command -v flyctl >/dev/null 2>&1; then
        echo "❌ Fly.io CLI (flyctl) not found"
        echo "Install it from: https://fly.io/docs/flyctl/installing/"
        return 1
    fi
    
    # Check if logged in
    if ! flyctl auth whoami >/dev/null 2>&1; then
        echo "❌ Not logged in to Fly.io"
        echo "Run: flyctl auth login"
        return 1
    fi
    
    return 0
}

main() {
    # Parse arguments
    local command=""
    local app_name="$APP_NAME"
    local dry_run=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            setup-secrets|validate-secrets|rotate-neo4j-password|show-secrets|help)
                command="$1"
                shift
                ;;
            --app-name)
                app_name="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    if [ -z "$command" ]; then
        show_usage
        exit 1
    fi
    
    # Check flyctl availability for commands that need it
    if [[ "$command" != "help" ]]; then
        check_flyctl || exit 1
    fi
    
    # Execute command
    case "$command" in
        setup-secrets)
            setup_secrets "$app_name" "$dry_run"
            ;;
        validate-secrets)
            validate_secrets "$app_name"
            ;;
        rotate-neo4j-password)
            rotate_neo4j_password "$app_name" "$dry_run"
            ;;
        show-secrets)
            show_secrets "$app_name"
            ;;
        help)
            show_usage
            ;;
    esac
}

main "$@"