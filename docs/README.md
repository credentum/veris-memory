# Context Store Documentation

## Overview

This directory contains documentation for the Veris Memory (Context Store) system deployed on Hetzner infrastructure.

## Documentation Structure

### 📁 Testing Documentation

Located in `docs/testing/`:

- **[BURNIN-TESTING-GUIDE.md](testing/BURNIN-TESTING-GUIDE.md)** - Complete guide for running burn-in stability tests
- **[BURNIN-SUMMARY.md](testing/BURNIN-SUMMARY.md)** - Executive summary of latest burn-in test results

### 🚀 Deployment

- **[scripts/deploy-to-hetzner.sh](../scripts/deploy-to-hetzner.sh)** - Automated deployment script

### 🧪 Test Scripts

Located in `scripts/burnin/`:

- `server_burnin.py` - Recommended production burn-in test
- `comprehensive_burnin.py` - Full-featured test suite
- `execute_burnin.py` - Flexible local/remote executor
- `remote_burnin.sh` - Remote deployment wrapper
- `final_burnin.sh` - Shell-based tester
- `quick_burnin.sh` - Rapid validation script

### 📊 Test Results

Located in `burnin-results/`:

- `server-burnin-report.json` - Latest server test results
- `COMPREHENSIVE-BURNIN-REPORT.json` - Detailed test report
- Historical test results and logs

## Quick Reference

### Current Status

- **Status**: ✅ PRODUCTION READY
- **Server**: Hetzner (135.181.4.118)
- **Location**: `/opt/veris-memory`
- **Last Test**: 2025-08-11 (PASSED)
- **Tag**: `burnin-stable-20250811-185229`

### Key Metrics

- **p95 Latency**: 1.4ms baseline, 2.4ms under load
- **Error Rate**: 0%
- **Max QPS Tested**: 50
- **Stability**: 5/5 cycles passed

### Quick Commands

```bash
# Run burn-in test on server
ssh hetzner-server "cd /opt/veris-memory && python3 server_burnin.py"

# Check service status
ssh hetzner-server "docker ps"

# View Qdrant configuration
ssh hetzner-server "curl -s http://localhost:6333/collections/context_embeddings | jq"
```

## For New Contributors

1. Read the [BURNIN-TESTING-GUIDE.md](testing/BURNIN-TESTING-GUIDE.md) for comprehensive testing procedures
2. Review [BURNIN-SUMMARY.md](testing/BURNIN-SUMMARY.md) for current performance benchmarks
3. Use `server_burnin.py` for standard validation tests
4. Always test before major deployments

## Architecture

### Services

- **Qdrant**: Vector database (port 6333)
  - 384 dimensions
  - Cosine distance metric
  - Collection: `context_embeddings`
  
- **Neo4j**: Graph database (port 7474)
  - Version: 5.15.0
  
- **Redis**: Cache layer (port 6379)

### Docker Containers

- `veris-memory-qdrant-1`
- `veris-memory-neo4j-1`
- `veris-memory-redis-1`

## Support

For issues or questions:
- Check test results in `burnin-results/`
- Review logs on server: `/opt/veris-memory/`
- Consult burn-in testing guide for troubleshooting

---

*Documentation Last Updated: 2025-08-11*