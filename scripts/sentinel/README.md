# Sentinel Monitoring and Alert Response System

This directory contains all scripts and components related to the Veris Memory Sentinel monitoring system, including automated diagnostics, Claude Code integration, and intelligent alert response.

## 📁 Directory Structure

### Core Sentinel Components
- **`sentinel-main.py`** - Main Sentinel monitoring daemon
- **`sentinel-entrypoint.sh`** - Docker entrypoint script for Sentinel
- **`test-sentinel.py`** - Sentinel system tests

### Deployment and Validation
- **`deploy-monitoring-production.sh`** - Production deployment script
- **`validate-monitoring-deployment.sh`** - Deployment validation tests
- **`test_telegram_alerts.py`** - Telegram notification testing

### Phase 2: Enhanced Diagnostics System
- **`advanced-diagnostics/`** - Advanced diagnostic modules
  - **`dependency_mapper.py`** - Service dependency analysis
  - **`health_analyzer.py`** - System health assessment
  - **`intelligence_synthesizer.py`** - Root cause analysis and recommendations
  - **`log_collector.py`** - Centralized log analysis
  - **`metrics_collector.py`** - Performance metrics collection
- **`test-enhanced-diagnostics.py`** - Phase 2 diagnostic testing

### Phase 3: Claude Code SSH Integration
- **`claude-code-launcher.py`** - Emergency Claude Code session launcher
- **`automated-debugging-workflows.py`** - Intelligent SSH debugging workflows
- **`intelligent-fix-generator.py`** - Automated fix generation and application

## 🚀 Quick Start

### Running Sentinel
```bash
# Start Sentinel monitoring
./sentinel-entrypoint.sh

# Run specific diagnostic tests
python test-enhanced-diagnostics.py

# Test emergency Claude Code integration
python claude-code-launcher.py --help
```

### Deployment
```bash
# Deploy to production
./deploy-monitoring-production.sh

# Validate deployment
./validate-monitoring-deployment.sh
```

## 🎯 System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Sentinel      │    │   GitHub Actions │    │  Claude Code    │
│   Alert         │───▶│   Enhanced       │───▶│   Automated     │
│   System        │    │   Workflow       │    │   Session       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                        │
         │ Phase 2               │ SSH Connection         │ SSH Commands
         ▼                       ▼                        ▼
┌─────────────────┐    ┌─────────────────────────────────────────┐
│  Enhanced       │    │        Veris Memory Server              │
│  Diagnostics    │    │  • Direct system access                │
│  System         │    │  • Live log analysis                   │
└─────────────────┘    │  • Service debugging                   │
                       │  • Real-time diagnostics               │
                       │  • Automated fixes                     │
                       └─────────────────────────────────────────┘
```

## 📋 Phase Overview

### Phase 1: Basic Webhook Integration ✅
- GitHub Actions webhook response
- Basic alert processing
- Initial notification system

### Phase 2: Enhanced Diagnostics ✅ 
- Intelligent root cause analysis
- Dependency mapping
- Performance metrics collection
- Comprehensive health assessment

### Phase 3: Claude Code SSH Integration ✅
- Emergency Claude Code sessions with SSH access
- Automated debugging workflows
- Intelligent fix generation and application
- Automated PR creation with documentation

## 🛡️ Security & Safety

- **Controlled SSH Access**: Only during critical alerts
- **Time-Limited Sessions**: 30-minute maximum duration
- **Audit Logging**: All commands and changes tracked
- **Rollback Mechanisms**: Automatic rollback on failure
- **Safety Checks**: Health verification after each change

## 📊 Monitoring Coverage

- **Service Health**: All Veris Memory components
- **Database Connectivity**: Qdrant, Neo4j, Redis
- **Performance Metrics**: CPU, memory, disk, network
- **Security Monitoring**: Authentication, firewall, permissions
- **Application Metrics**: API response times, error rates

## 🔧 Configuration

Configuration files are located in:
- `config/sentinel-config.yaml` - Main Sentinel configuration
- `.github/workflows/sentinel-alert-response.yml` - GitHub Actions workflow

## 📚 Documentation

For detailed documentation, see:
- `docs/phase3-architecture.md` - Phase 3 architecture overview
- `DEPLOYMENT_TO_VERIS_MEMORY.md` - Deployment guide
- `DEPLOYMENT_TROUBLESHOOTING.md` - Troubleshooting guide