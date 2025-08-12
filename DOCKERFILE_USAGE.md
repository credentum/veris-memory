# Dockerfile Usage Guide

## Available Dockerfiles

### 1. `Dockerfile` (Default - Python API Only)
- **Use Case**: Docker Compose deployments where services run as separate containers
- **Used By**: `docker-compose.yml` (dev) and `docker-compose.prod.yml` (production)
- **Contains**: Only the Python API application
- **Services**: Relies on external Qdrant, Neo4j, and Redis containers

### 2. `Dockerfile.flyio` (All-in-One)
- **Use Case**: Fly.io deployment with single container
- **Contains**: Python API + embedded Qdrant + Neo4j + Redis
- **Note**: Do NOT use with docker-compose (would duplicate services)

### 3. `Dockerfile.hetzner` (All-in-One + Tailscale)
- **Use Case**: Standalone deployment on Hetzner dedicated server
- **Contains**: Python API + embedded services + Tailscale + hardware optimizations
- **Features**: RAID1 support, high memory configs, hardware monitoring
- **Note**: For standalone use, not with docker-compose

### 4. `Dockerfile.python-only`
- **Use Case**: Lightweight Python-only container for testing
- **Contains**: Minimal Python API without any services

## Deployment Scenarios

### Docker Compose (Dev/Prod on Hetzner)
```bash
# Uses Dockerfile (Python-only) + separate service containers
docker-compose up -d  # Dev environment
docker-compose -f docker-compose.prod.yml up -d  # Production
```

### Standalone on Fly.io
```bash
# Uses Dockerfile.flyio (all-in-one)
fly deploy --dockerfile Dockerfile.flyio
```

### Standalone on Hetzner (without docker-compose)
```bash
# Uses Dockerfile.hetzner (all-in-one with optimizations)
docker build -f Dockerfile.hetzner -t veris-memory-hetzner .
docker run -d --name veris-memory veris-memory-hetzner
```

## Important Notes

1. **Never use all-in-one Dockerfiles with docker-compose** - This would create duplicate services
2. **Dev and Prod use the same Dockerfile** - Environment differences are handled by docker-compose configs
3. **Port separation is handled by docker-compose** - Not by different Dockerfiles