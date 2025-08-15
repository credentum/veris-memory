#!/bin/bash
# Security scanning script for Veris Memory deployment
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

show_usage() {
    cat << EOF
Veris Memory Security Scanner

Usage: $0 COMMAND [OPTIONS]

Commands:
  install-trivy          Install Trivy security scanner
  scan-base-images       Scan Ubuntu base images for vulnerabilities
  scan-dockerfile        Scan both dev and production Dockerfiles for security issues
  scan-built-image       Build and scan both dev and production Docker images
  scan-dependencies      Scan Python dependencies for vulnerabilities
  full-scan             Run complete security audit
  help                  Show this help message

Options:
  --severity LEVEL      Set minimum severity (LOW,MEDIUM,HIGH,CRITICAL) [default: HIGH]
  --format FORMAT       Output format (table,json,sarif) [default: table]
  --output FILE         Output results to file
  --fail-on-vuln        Exit with code 1 if vulnerabilities found

Examples:
  $0 install-trivy
  $0 scan-base-images
  $0 scan-built-image --severity CRITICAL --fail-on-vuln
  $0 full-scan --format json --output security-report.json

EOF
}

install_trivy() {
    echo "Installing Trivy security scanner..."

    if command -v trivy >/dev/null 2>&1; then
        echo "✓ Trivy is already installed"
        trivy --version
        return 0
    fi

    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux installation
        sudo apt-get update
        sudo apt-get install -y wget apt-transport-https gnupg lsb-release
        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
        echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
        sudo apt-get update
        sudo apt-get install -y trivy
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS installation
        if command -v brew >/dev/null 2>&1; then
            brew install trivy
        else
            echo "Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    else
        echo "Unsupported OS: $OSTYPE"
        echo "Please install Trivy manually: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        exit 1
    fi

    echo "✓ Trivy installed successfully"
    trivy --version
}

scan_base_images() {
    local severity=${1:-HIGH}
    local format=${2:-table}
    local output_file=${3:-}
    local fail_on_vuln=${4:-false}

    echo "Scanning Ubuntu base image for vulnerabilities..."

    local trivy_cmd="trivy image --severity $severity --format $format"

    if [ -n "$output_file" ]; then
        trivy_cmd="$trivy_cmd --output $output_file"
    fi

    if [ "$fail_on_vuln" = "true" ]; then
        trivy_cmd="$trivy_cmd --exit-code 1"
    fi

    echo "Running: $trivy_cmd ubuntu:22.04@sha256:965fbcae990b0467ed5657caceaec165018ef44a4d2d46c7cdea80a9dff0d1ea"
    $trivy_cmd ubuntu:22.04@sha256:965fbcae990b0467ed5657caceaec165018ef44a4d2d46c7cdea80a9dff0d1ea
}

scan_dockerfile() {
    local severity=${1:-HIGH}
    local format=${2:-table}
    local output_file=${3:-}

    echo "Scanning Dockerfiles for security misconfigurations..."

    local trivy_cmd="trivy config --severity $severity --format $format"

    if [ -n "$output_file" ]; then
        trivy_cmd="$trivy_cmd --output $output_file"
    fi

    echo "\n=== Scanning Dev Dockerfile ==="
    echo "Running: $trivy_cmd $PROJECT_DIR/docker/Dockerfile"
    $trivy_cmd "$PROJECT_DIR/docker/Dockerfile"
    
    echo "\n=== Scanning Production Hetzner Dockerfile ==="
    echo "Running: $trivy_cmd $PROJECT_DIR/docker/Dockerfile.hetzner"
    $trivy_cmd "$PROJECT_DIR/docker/Dockerfile.hetzner"
}

scan_built_image() {
    local severity=${1:-HIGH}
    local format=${2:-table}
    local output_file=${3:-}
    local fail_on_vuln=${4:-false}

    echo "Building and scanning complete Docker image..."

    cd "$PROJECT_DIR"

    # Build and scan dev image
    echo "Building dev image (veris-memory-dev:latest)..."
    docker build -t veris-memory-dev:latest -f docker/Dockerfile .
    
    echo "\n=== Scanning Dev Image ==="
    local trivy_cmd_dev="trivy image --severity $severity --format $format"
    if [ -n "$output_file" ]; then
        trivy_cmd_dev="$trivy_cmd_dev --output ${output_file%.json}-dev.json"
    fi
    $trivy_cmd_dev veris-memory-dev:latest
    
    # Build and scan production image
    echo "\nBuilding production image (veris-memory-prod:latest)..."
    docker build -t veris-memory-prod:latest -f docker/Dockerfile.hetzner .

    # Scan production image
    echo "\n=== Scanning Production Image ==="
    local trivy_cmd="trivy image --severity $severity --format $format"

    if [ -n "$output_file" ]; then
        trivy_cmd="$trivy_cmd --output ${output_file%.json}-prod.json"
    fi

    if [ "$fail_on_vuln" = "true" ]; then
        trivy_cmd="$trivy_cmd --exit-code 1"
    fi

    echo "Running: $trivy_cmd veris-memory-prod:latest"
    $trivy_cmd veris-memory-prod:latest
}

scan_dependencies() {
    local severity=${1:-HIGH}
    local format=${2:-table}
    local output_file=${3:-}

    echo "Scanning Python dependencies for vulnerabilities..."

    local trivy_cmd="trivy fs --severity $severity --format $format"

    if [ -n "$output_file" ]; then
        trivy_cmd="$trivy_cmd --output $output_file"
    fi

    echo "Running: $trivy_cmd $PROJECT_DIR/requirements.txt"
    $trivy_cmd "$PROJECT_DIR/requirements.txt"

    echo "Scanning development dependencies..."
    echo "Running: $trivy_cmd $PROJECT_DIR/requirements-dev.txt"
    $trivy_cmd "$PROJECT_DIR/requirements-dev.txt"
}

full_scan() {
    local severity=${1:-HIGH}
    local format=${2:-table}
    local output_file=${3:-}
    local fail_on_vuln=${4:-false}

    echo "Running complete security audit..."
    echo "======================================"

    # Create output directory if needed
    if [ -n "$output_file" ]; then
        mkdir -p "$(dirname "$output_file")"
    fi

    # Base image scan
    echo -e "\n1. Scanning base Ubuntu image..."
    scan_base_images "$severity" "$format" "${output_file:+${output_file}.base-image}" "$fail_on_vuln"

    # Dockerfile scan
    echo -e "\n2. Scanning Dockerfile configuration..."
    scan_dockerfile "$severity" "$format" "${output_file:+${output_file}.dockerfile}"

    # Dependencies scan
    echo -e "\n3. Scanning Python dependencies..."
    scan_dependencies "$severity" "$format" "${output_file:+${output_file}.dependencies}"

    # Built image scan
    echo -e "\n4. Building and scanning complete image..."
    scan_built_image "$severity" "$format" "${output_file:+${output_file}.full-image}" "$fail_on_vuln"

    echo -e "\n✅ Complete security audit finished"

    if [ -n "$output_file" ]; then
        echo "Reports saved to: ${output_file}.*"
    fi
}

check_trivy() {
    if ! command -v trivy >/dev/null 2>&1; then
        echo "❌ Trivy not found. Installing..."
        install_trivy
    fi
}

main() {
    # Parse arguments
    local command=""
    local severity="HIGH"
    local format="table"
    local output_file=""
    local fail_on_vuln=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            install-trivy|scan-base-images|scan-dockerfile|scan-built-image|scan-dependencies|full-scan|help)
                command="$1"
                shift
                ;;
            --severity)
                severity="$2"
                shift 2
                ;;
            --format)
                format="$2"
                shift 2
                ;;
            --output)
                output_file="$2"
                shift 2
                ;;
            --fail-on-vuln)
                fail_on_vuln=true
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

    # Check Trivy availability for commands that need it
    if [[ "$command" != "help" && "$command" != "install-trivy" ]]; then
        check_trivy
    fi

    # Execute command
    case "$command" in
        install-trivy)
            install_trivy
            ;;
        scan-base-images)
            scan_base_images "$severity" "$format" "$output_file" "$fail_on_vuln"
            ;;
        scan-dockerfile)
            scan_dockerfile "$severity" "$format" "$output_file"
            ;;
        scan-built-image)
            scan_built_image "$severity" "$format" "$output_file" "$fail_on_vuln"
            ;;
        scan-dependencies)
            scan_dependencies "$severity" "$format" "$output_file"
            ;;
        full-scan)
            full_scan "$severity" "$format" "$output_file" "$fail_on_vuln"
            ;;
        help)
            show_usage
            ;;
    esac
}

main "$@"
