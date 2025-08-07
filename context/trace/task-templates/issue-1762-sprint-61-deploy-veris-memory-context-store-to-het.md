# ────────────────────────────────────────────────────────────────────────

# TASK: issue-1762-[sprint-6.1]-deploy-veris-memory-context-store-to-

# Generated from GitHub Issue #1762

# ────────────────────────────────────────────────────────────────────────

## 📌 Task Name

`fix-issue-1762-[sprint-6.1]-deploy-veris-memory-context-store-to-`

## 🎯 Goal (≤ 2 lines)

> [SPRINT-6.1] Deploy veris-memory context-store to Hetzner dedicated server with Ubuntu 24.04 optimization

## 🧠 Context

- **GitHub Issue**: #1762 - [SPRINT-6.1] Deploy veris-memory context-store to Hetzner dedicated server with Ubuntu 24.04 optimization
- **Labels**: sprint-current, infrastructure, performance, claude-ready
- **Component**: workflow-automation
- **Why this matters**: Resolves reported issue

## 🛠️ Subtasks

| File | Action | Prompt Tech | Purpose | Context Impact |
| ---- | ------ | ----------- | ------- | -------------- |
| TBD  | TBD    | TBD         | TBD     | TBD            |

## 📝 Issue Description

## Task Context

**Sprint**: sprint-6-1
**Phase**: Phase 1: Infrastructure Migration
**Component**: context-store deployment

## Scope Assessment

- [x] **Scope is clear** - Requirements are well-defined, proceed with implementation
- [ ] **Scope needs investigation** - Create investigation issue first (use investigation.md template)
- [ ] **Partially clear** - Some aspects need investigation (note below)

**Investigation Notes**: Complete analysis completed via ultrathink investigation. Hardware specs, performance requirements, and technical approach are well-defined.

## Acceptance Criteria

- [ ] Create Dockerfile.hetzner with Ubuntu 24.04 and Tailscale integration
- [ ] Create docker-compose.hetzner.yml optimized for 64GB RAM / 6-core system
- [ ] Update .ctxrc.yaml with performance tuning for high-spec hardware
- [ ] Implement RAID1 storage integration for Docker volumes
- [ ] Add Tailscale networking for secure private access
- [ ] Create deployment automation scripts for Hetzner environment
- [ ] Add hardware monitoring and RAID health checks
- [ ] Implement backup strategies leveraging RAID1 redundancy
- [ ] Performance benchmarks show 10x+ improvement over current Fly.io setup
- [ ] Security hardening with firewall rules and Tailscale-only access

## Claude Code Readiness Checklist

- [x] **Context URLs identified** (Hetzner docs, Tailscale integration guides, Ubuntu 24.04 migration)
- [x] **File scope estimated** (8-10 new files, ~600 LoC for configs and scripts)
- [x] **Dependencies mapped** (Docker, Tailscale, RAID1, Ubuntu 24.04 packages)
- [x] **Test strategy defined** (deployment verification, performance benchmarks, failover testing)
- [x] **Breaking change assessment** (New deployment target, backward compatible configs)

## Pre-Execution Context

**Key Files**:

- `context-store/Dockerfile.flyio` (base for new Dockerfile.hetzner)
- `context-store/docker-compose.yml` (base for hetzner version)
- `context-store/.ctxrc.yaml` (performance tuning needed)
- `context-store/src/core/utils.py` (already optimized for Neo4j)

**External Dependencies**:

- Hetzner dedicated server (AMD Ryzen 5 5600X, 64GB RAM, RAID1 NVMe)
- Ubuntu 24.04, Docker, Tailscale pre-installed
- Neo4j, Redis, Qdrant Docker images
- Tailscale mesh networking

**Configuration**:

- NEO4J_PASSWORD (existing secret)
- TAILSCALE_AUTHKEY (new required)
- TAILSCALE_HOSTNAME (new required)
- Hardware optimization environment variables

**Related Issues/PRs**:

- #1761 (veris-memory 503 fixes - provides context)
- temp-deploy/ directory has working production fixes

## Implementation Notes

### Technical Approach

1. **Performance Optimization**: Scale from 8GB to 64GB RAM utilization

   - Neo4j heap: 3GB → 20GB
   - Redis memory: 512MB → 8GB
   - Qdrant workers: 1 → 8
   - Connection pools and concurrency limits scaled accordingly

2. **Storage Strategy**: RAID1 NVMe integration

   - Separate Docker volumes for each service
   - Bind mounts to /raid1/docker-data/ paths
   - Automated backup strategies

3. **Security Model**: Tailscale private network

   - No public port exposure
   - UFW firewall restricting to Tailscale CGNAT ranges
   - Enhanced container security configurations

4. **Monitoring**: Hardware health integration
   - RAID status monitoring
   - CPU temperature monitoring
   - Performance metrics collection

### File Creation Plan

- `Dockerfile.hetzner` - Ubuntu 24.04 + Tailscale + optimizations
- `docker-compose.hetzner.yml` - Dedicated server configuration
- `deploy/hetzner/` directory with deployment scripts
- `monitoring/` scripts for hardware health
- `backup/` strategies for RAID1 environment

### Expected Performance Gains

- **Memory**: 8x increase enables massive database caching
- **Storage**: NVMe RAID1 vs cloud storage performance
- **Network**: Tailscale mesh vs public internet latency
- **CPU**: Dedicated cores vs shared cloud resources

---

## Claude Code Execution

**Session Started**: 2025-08-07T03:30:00Z
**Task Template Created**: This issue serves as the template
**Token Budget**: ~15,000 tokens estimated for implementation
**Completion Target**: 2-3 hours for full implementation and testing

_This issue will be updated during Claude Code execution with progress and results._

## Success Metrics

- [ ] All services deploy successfully on Hetzner hardware
- [ ] Performance benchmarks exceed current Fly.io deployment by 10x+
- [ ] RAID1 monitoring and backup automation working
- [ ] Tailscale secure access functional
- [ ] Zero-downtime deployment process documented

## Hardware Specifications

- **CPU**: AMD Ryzen 5 5600X (6 cores, 12 threads)
- **Memory**: 64GB DDR4 RAM
- **Storage**: 2×512GB NVMe SSD (RAID1)
- **OS**: Ubuntu 24.04
- **Networking**: Tailscale mesh network
- **Container Runtime**: Docker with resource optimization

## Migration Benefits

1. **Performance**: 10x+ improvement in memory and processing capacity
2. **Reliability**: RAID1 hardware redundancy vs single cloud disk
3. **Security**: Private Tailscale network vs public cloud endpoints
4. **Cost**: Predictable dedicated server costs vs cloud scaling
5. **Control**: Full hardware and OS control vs cloud platform limitations

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>

## 🔍 Verification & Testing

- Run CI checks locally
- Test the specific functionality
- Verify issue is resolved

## ✅ Acceptance Criteria

- Issue requirements are met
- Tests pass
- No regressions introduced
