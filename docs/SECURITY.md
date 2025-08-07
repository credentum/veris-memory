# Security Guide

This document outlines the security measures and scanning tools available for the Veris Memory project.

## CVE Scanning

### Overview

We use [Trivy](https://trivy.dev/) for comprehensive vulnerability scanning of:

- Base Docker images
- Built application images
- Python dependencies
- Dockerfile configurations

### Automated Scanning

CVE scanning runs automatically:

- **On every push** to the repository (GitHub Actions)
- **On pull requests** affecting the context-store directory
- **Daily at 2 AM UTC** for continuous monitoring

### Manual Scanning

Use the security scanning script for local testing:

```bash
# Install Trivy scanner
./scripts/security-scan.sh install-trivy

# Quick scan of base images
./scripts/security-scan.sh scan-base-images

# Complete security audit
./scripts/security-scan.sh full-scan

# Scan with custom settings
./scripts/security-scan.sh full-scan --severity CRITICAL --format json --output security-report.json
```

### Security Thresholds

- **HIGH and CRITICAL** vulnerabilities will fail CI builds
- **MEDIUM** vulnerabilities are reported but don't fail builds
- **LOW** vulnerabilities are tracked in detailed reports

### Build Arguments

The Dockerfile uses configurable build arguments for security:

```bash
# Build with custom Qdrant version and checksum
docker build \
  --build-arg QDRANT_VERSION=1.15.0 \
  --build-arg QDRANT_SHA256=new_checksum_here \
  -f Dockerfile.flyio .
```

## Security Features

### 1. Hardened Base Images

- Uses Ubuntu 22.04 with SHA256 digest pinning
- Multi-stage builds to reduce attack surface
- Non-root user execution where possible

### 2. Secrets Management

- No hardcoded passwords in configuration files
- Fly.io secrets integration for production deployment
- Secure password generation with `secrets-manager.sh`

### 3. Checksum Verification

- Mandatory SHA256 verification for all downloaded binaries
- Build fails if checksums don't match
- Configurable checksums via build arguments

### 4. Resource Limits

- Memory and file descriptor limits for all services
- Prevents resource exhaustion attacks
- Configurable Redis memory limits

### 5. Network Security

- Services bound to localhost by default
- Dedicated IPv4 addresses in production
- Secure DNS configuration (1.1.1.1, 8.8.8.8)

### 6. Monitoring & Alerting

- Comprehensive health monitoring
- Resource usage tracking with thresholds
- Automated alerts for high resource usage

## Production Deployment Security

### Fly.io Secrets Setup

```bash
# Generate and set secure Neo4j password
./secrets/secrets-manager.sh setup-secrets

# Validate all secrets are configured
./secrets/secrets-manager.sh validate-secrets

# Rotate passwords periodically
./secrets/secrets-manager.sh rotate-neo4j-password
```

### Security Checklist

Before deploying to production:

- [ ] Run security scan: `./scripts/security-scan.sh full-scan --fail-on-vuln`
- [ ] Set all required secrets: `./secrets/secrets-manager.sh validate-secrets`
- [ ] Review resource limits in `supervisord.conf`
- [ ] Enable monitoring: Set `EXTERNAL_MONITORING=true`
- [ ] Configure log retention and monitoring
- [ ] Test disaster recovery procedures

## Vulnerability Response

### When CVE Scanning Fails

1. **Review the vulnerability report** - Check severity and affected components
2. **Update base images** - Use newer Ubuntu versions if available
3. **Update dependencies** - Run `pip install --upgrade` for Python packages
4. **Apply patches** - Update specific vulnerable packages
5. **Update checksums** - If using new versions, update SHA256 checksums

### Emergency Response

For CRITICAL vulnerabilities in production:

1. **Immediate assessment** - Determine if production is affected
2. **Apply hotfixes** - Update vulnerable components immediately
3. **Redeploy** - Use `flyctl deploy` with updated security patches
4. **Monitor** - Watch logs for any exploitation attempts
5. **Document** - Record the incident and response actions

## Security Tools Reference

### Trivy Commands

```bash
# Scan specific image
trivy image ubuntu:22.04

# Scan with specific severity
trivy image --severity HIGH,CRITICAL myimage:latest

# Export JSON report
trivy image --format json --output report.json myimage:latest

# Scan Dockerfile for misconfigurations
trivy config Dockerfile.flyio

# Scan Python requirements
trivy fs requirements.txt
```

### Security Resources

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [Fly.io Security Features](https://fly.io/docs/security/)
- [OWASP Container Security](https://owasp.org/www-project-container-security/)

## Reporting Security Issues

For security vulnerabilities:

1. **DO NOT** create public GitHub issues
2. Email security concerns to the project maintainers
3. Include detailed reproduction steps
4. Allow reasonable time for response before disclosure
