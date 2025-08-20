# Veris Memory Deployment Guide

Comprehensive deployment documentation for the Veris Memory system across different environments.

## Overview

The Veris Memory system is designed for flexible deployment across various environments, from local development to enterprise production. This guide covers deployment strategies, configuration options, and best practices for each environment.

## Quick Start

### Local Development

```bash
# Clone repository
git clone <repository-url>
cd veris-memory

# Setup environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start with Docker Compose (recommended)
docker-compose -f docker/docker-compose.yml up

# Or start manually
python -m src.api.main
```

### Docker Deployment

```bash
# Build image
docker build -f docker/Dockerfile -t veris-memory:latest .

# Run container
docker run -p 8000:8000 -e VERIS_MEMORY_ENV=production veris-memory:latest

# Or use Docker Compose
docker-compose -f docker/docker-compose.prod.yml up -d
```

### Cloud Deployment

```bash
# Deploy to cloud platform (example: fly.io)
fly deploy

# Or use Kubernetes
kubectl apply -f k8s/
```

## Environment Configurations

### Development Environment

**Purpose**: Local development and testing  
**Requirements**: Minimal resource usage, fast startup, debugging capabilities

```bash
# Environment variables
export VERIS_MEMORY_ENV=development
export VERIS_MEMORY_LOG_LEVEL=DEBUG
export VERIS_MEMORY_API_HOST=localhost
export VERIS_MEMORY_API_PORT=8000

# Features enabled
- Hot reloading
- Debug logging
- Mock backends (optional)
- API documentation endpoints
- Development middleware
```

**Docker Compose (Development)**:
```yaml
# docker/docker-compose.dev.yml
version: '3.8'
services:
  veris-memory:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - VERIS_MEMORY_ENV=development
      - VERIS_MEMORY_LOG_LEVEL=DEBUG
    volumes:
      - ../src:/app/src:ro
    command: ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Staging Environment

**Purpose**: Pre-production testing and validation  
**Requirements**: Production-like configuration, monitoring, testing tools

```bash
# Environment variables
export VERIS_MEMORY_ENV=staging
export VERIS_MEMORY_LOG_LEVEL=INFO
export VERIS_MEMORY_API_HOST=0.0.0.0
export VERIS_MEMORY_API_PORT=8000

# Backend configurations
export VECTOR_BACKEND_URL=postgresql://user:pass@vector-db:5432/veris_vector
export GRAPH_BACKEND_URL=neo4j://user:pass@graph-db:7687/veris_graph
export KV_BACKEND_URL=redis://kv-store:6379/0

# Features enabled
- Production middleware stack
- Real backend integrations
- Monitoring and metrics
- API rate limiting
- Security middleware
```

**Docker Compose (Staging)**:
```yaml
# docker/docker-compose.staging.yml
version: '3.8'
services:
  veris-memory:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - VERIS_MEMORY_ENV=staging
      - VERIS_MEMORY_LOG_LEVEL=INFO
      - VECTOR_BACKEND_URL=postgresql://user:pass@vector-db:5432/veris_vector
    depends_on:
      - vector-db
      - graph-db
      - kv-store
    restart: unless-stopped

  vector-db:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=veris_vector
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - vector_data:/var/lib/postgresql/data

  graph-db:
    image: neo4j:5.0
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - graph_data:/data

  kv-store:
    image: redis:7-alpine
    volumes:
      - kv_data:/data

volumes:
  vector_data:
  graph_data:
  kv_data:
```

### Production Environment

**Purpose**: Live system serving real users  
**Requirements**: High availability, security, performance, monitoring

```bash
# Environment variables
export VERIS_MEMORY_ENV=production
export VERIS_MEMORY_LOG_LEVEL=INFO
export VERIS_MEMORY_API_HOST=0.0.0.0
export VERIS_MEMORY_API_PORT=8000

# Security
export VERIS_MEMORY_SECRET_KEY=<secure-secret-key>
export VERIS_MEMORY_JWT_SECRET=<jwt-secret>

# Backend configurations (use secrets management)
export VECTOR_BACKEND_URL=${VECTOR_DATABASE_URL}
export GRAPH_BACKEND_URL=${GRAPH_DATABASE_URL}
export KV_BACKEND_URL=${KV_STORE_URL}

# Performance tuning
export VERIS_MEMORY_WORKERS=4
export VERIS_MEMORY_MAX_CONNECTIONS=100
export VERIS_MEMORY_CACHE_TTL=3600

# Features enabled
- Multi-worker deployment
- SSL/TLS termination
- Authentication and authorization
- Comprehensive monitoring
- Auto-scaling capabilities
- Backup and disaster recovery
```

## Platform-Specific Deployments

### Docker Deployment

#### Single Container Deployment

```dockerfile
# Dockerfile.prod
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY docker/entrypoint.sh ./

# Configure runtime
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```bash
# Build and run
docker build -f docker/Dockerfile.prod -t veris-memory:prod .
docker run -d -p 8000:8000 --name veris-memory veris-memory:prod
```

#### Multi-Container with Docker Compose

```yaml
# docker/docker-compose.prod.yml
version: '3.8'
services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - VERIS_MEMORY_ENV=production
    depends_on:
      - vector-db
      - graph-db
      - kv-store
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    restart: unless-stopped

  vector-db:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - vector_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    restart: unless-stopped

  graph-db:
    image: neo4j:5.0
    environment:
      - NEO4J_AUTH=${NEO4J_AUTH}
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
    volumes:
      - graph_data:/data
      - graph_logs:/logs
    restart: unless-stopped

  kv-store:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - kv_data:/data
    restart: unless-stopped

  monitoring:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    restart: unless-stopped

volumes:
  vector_data:
  graph_data:
  graph_logs:
  kv_data:
  prometheus_data:
```

### Kubernetes Deployment

#### Basic Kubernetes Manifests

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: veris-memory
---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: veris-memory-config
  namespace: veris-memory
data:
  VERIS_MEMORY_ENV: "production"
  VERIS_MEMORY_LOG_LEVEL: "INFO"
  VERIS_MEMORY_API_HOST: "0.0.0.0"
  VERIS_MEMORY_API_PORT: "8000"
---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: veris-memory-secrets
  namespace: veris-memory
type: Opaque
data:
  SECRET_KEY: <base64-encoded-secret>
  JWT_SECRET: <base64-encoded-jwt-secret>
  DATABASE_URL: <base64-encoded-db-url>
---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: veris-memory
  namespace: veris-memory
spec:
  replicas: 3
  selector:
    matchLabels:
      app: veris-memory
  template:
    metadata:
      labels:
        app: veris-memory
    spec:
      containers:
      - name: veris-memory
        image: veris-memory:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: veris-memory-config
        - secretRef:
            name: veris-memory-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: veris-memory-service
  namespace: veris-memory
spec:
  selector:
    app: veris-memory
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: veris-memory-ingress
  namespace: veris-memory
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.veris-memory.com
    secretName: veris-memory-tls
  rules:
  - host: api.veris-memory.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: veris-memory-service
            port:
              number: 80
```

#### Helm Chart Deployment

```yaml
# helm/veris-memory/Chart.yaml
apiVersion: v2
name: veris-memory
description: Veris Memory System Helm Chart
version: 1.0.0
appVersion: "1.0.0"

# helm/veris-memory/values.yaml
replicaCount: 3

image:
  repository: veris-memory
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.veris-memory.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: veris-memory-tls
      hosts:
        - api.veris-memory.com

resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

env:
  VERIS_MEMORY_ENV: production
  VERIS_MEMORY_LOG_LEVEL: INFO

secrets:
  SECRET_KEY: ""
  JWT_SECRET: ""
  DATABASE_URL: ""
```

```bash
# Deploy with Helm
helm install veris-memory ./helm/veris-memory \
  --namespace veris-memory \
  --create-namespace \
  --values ./helm/veris-memory/values.prod.yaml
```

### Cloud Platform Deployments

#### AWS ECS Deployment

```json
{
  "family": "veris-memory",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "veris-memory",
      "image": "your-account.dkr.ecr.region.amazonaws.com/veris-memory:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "VERIS_MEMORY_ENV",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:ssm:region:account:parameter/veris-memory/secret-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/veris-memory",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

#### Google Cloud Run Deployment

```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: veris-memory
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 100
      containers:
      - image: gcr.io/project-id/veris-memory:latest
        ports:
        - containerPort: 8000
        env:
        - name: VERIS_MEMORY_ENV
          value: production
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: veris-memory-secrets
              key: secret-key
        resources:
          limits:
            cpu: "2"
            memory: "1Gi"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
```

```bash
# Deploy to Cloud Run
gcloud run deploy veris-memory \
  --image gcr.io/project-id/veris-memory:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars VERIS_MEMORY_ENV=production
```

#### Fly.io Deployment

```toml
# fly.toml
app = "veris-memory"
primary_region = "ord"

[build]
  dockerfile = "docker/Dockerfile.prod"

[env]
  VERIS_MEMORY_ENV = "production"
  VERIS_MEMORY_LOG_LEVEL = "INFO"

[[services]]
  http_checks = []
  internal_port = 8000
  processes = ["app"]
  protocol = "tcp"
  script_checks = []
  [services.concurrency]
    hard_limit = 100
    soft_limit = 80
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.tcp_checks]]
    grace_period = "10s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"

  [[services.http_checks]]
    interval = "10s"
    grace_period = "5s"
    method = "get"
    path = "/api/v1/health"
    protocol = "http"
    timeout = "2s"
    tls_skip_verify = false

[deploy]
  strategy = "rolling"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512
```

```bash
# Deploy to Fly.io
fly deploy
```

## Configuration Management

### Environment Variables

**Core Configuration**:
```bash
# Application
VERIS_MEMORY_ENV=production|staging|development
VERIS_MEMORY_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
VERIS_MEMORY_API_HOST=0.0.0.0
VERIS_MEMORY_API_PORT=8000

# Security
VERIS_MEMORY_SECRET_KEY=<secure-random-string>
VERIS_MEMORY_JWT_SECRET=<jwt-signing-secret>
VERIS_MEMORY_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

# Performance
VERIS_MEMORY_WORKERS=4
VERIS_MEMORY_MAX_CONNECTIONS=100
VERIS_MEMORY_TIMEOUT_SECONDS=30
```

**Backend Configuration**:
```bash
# Vector Database (PostgreSQL with pgvector)
VECTOR_BACKEND_URL=postgresql://user:pass@host:5432/database
VECTOR_BACKEND_POOL_SIZE=20
VECTOR_BACKEND_MAX_OVERFLOW=10

# Graph Database (Neo4j)
GRAPH_BACKEND_URL=neo4j://user:pass@host:7687/database
GRAPH_BACKEND_MAX_CONNECTIONS=50

# Key-Value Store (Redis)
KV_BACKEND_URL=redis://host:6379/0
KV_BACKEND_POOL_SIZE=20
```

**Monitoring and Observability**:
```bash
# Metrics
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Logging
LOG_FORMAT=json|text
LOG_OUTPUT=stdout|file
LOG_FILE_PATH=/var/log/veris-memory.log

# Tracing
JAEGER_ENABLED=true
JAEGER_ENDPOINT=http://jaeger:14268/api/traces
```

### Configuration Files

**Production Configuration**:
```yaml
# config/production.yaml
app:
  name: "Veris Memory API"
  version: "1.0.0"
  environment: "production"
  debug: false

server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  max_connections: 100
  timeout: 30

security:
  cors:
    enabled: true
    allowed_origins:
      - "https://app.example.com"
      - "https://admin.example.com"
    allowed_methods: ["GET", "POST", "PUT", "DELETE"]
    allowed_headers: ["*"]
  
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst_limit: 10

backends:
  vector:
    type: "postgresql"
    url: "${VECTOR_BACKEND_URL}"
    pool_size: 20
    timeout: 10

  graph:
    type: "neo4j"
    url: "${GRAPH_BACKEND_URL}"
    max_connections: 50
    timeout: 15

  kv:
    type: "redis"
    url: "${KV_BACKEND_URL}"
    pool_size: 20
    timeout: 5

monitoring:
  metrics:
    enabled: true
    prometheus_port: 9090
  
  logging:
    level: "INFO"
    format: "json"
    output: "stdout"
  
  health_checks:
    enabled: true
    interval: 30
    timeout: 10

caching:
  enabled: true
  ttl: 3600
  max_size: 1000
```

### Secrets Management

#### Environment-based Secrets

```bash
# Development (.env file)
SECRET_KEY=dev-secret-key-not-for-production
JWT_SECRET=dev-jwt-secret

# Production (use secrets manager)
SECRET_KEY=${AWS_SSM_SECRET_KEY}
JWT_SECRET=${AWS_SSM_JWT_SECRET}
DATABASE_PASSWORD=${VAULT_DATABASE_PASSWORD}
```

#### Docker Secrets

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  app:
    image: veris-memory:latest
    environment:
      - SECRET_KEY_FILE=/run/secrets/secret_key
      - JWT_SECRET_FILE=/run/secrets/jwt_secret
    secrets:
      - secret_key
      - jwt_secret

secrets:
  secret_key:
    external: true
  jwt_secret:
    external: true
```

#### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: veris-memory-secrets
type: Opaque
data:
  secret-key: <base64-encoded-secret>
  jwt-secret: <base64-encoded-jwt-secret>
  database-password: <base64-encoded-password>
```

## Monitoring and Observability

### Health Checks

**Basic Health Check**:
```bash
# Simple health check
curl http://localhost:8000/api/v1/health

# Detailed health check with backend status
curl http://localhost:8000/api/v1/health/detailed
```

**Load Balancer Health Checks**:
```yaml
# For load balancers and orchestrators
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Metrics and Monitoring

**Prometheus Configuration**:
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'veris-memory'
    static_configs:
      - targets: ['veris-memory:8000']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 10s
```

**Grafana Dashboard**:
```json
{
  "dashboard": {
    "title": "Veris Memory System",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      }
    ]
  }
}
```

### Logging

**Structured Logging Configuration**:
```python
# Configure structured logging for production
import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
```

**Log Aggregation (ELK Stack)**:
```yaml
# logstash.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][app] == "veris-memory" {
    json {
      source => "message"
    }
    
    date {
      match => [ "timestamp", "ISO8601" ]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "veris-memory-%{+YYYY.MM.dd}"
  }
}
```

## Security Considerations

### Network Security

**Firewall Configuration**:
```bash
# Only allow necessary ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw deny 8000/tcp   # Block direct API access
ufw enable
```

**Reverse Proxy (Nginx)**:
```nginx
# nginx.conf
upstream veris_memory {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.veris-memory.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.veris-memory.com;

    ssl_certificate /etc/ssl/certs/veris-memory.crt;
    ssl_certificate_key /etc/ssl/private/veris-memory.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
    
    location / {
        proxy_pass http://veris_memory;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
    }
}
```

### Application Security

**Security Headers**:
```python
# Middleware configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'"
}
```

**Authentication and Authorization**:
```python
# JWT token configuration
JWT_CONFIG = {
    "algorithm": "HS256",
    "expiration": 3600,  # 1 hour
    "refresh_expiration": 86400,  # 24 hours
    "issuer": "veris-memory-api",
    "audience": "veris-memory-clients"
}
```

## Backup and Disaster Recovery

### Database Backups

**Automated Backup Script**:
```bash
#!/bin/bash
# scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# PostgreSQL backup
pg_dump $VECTOR_DATABASE_URL > $BACKUP_DIR/vector_backup_$DATE.sql

# Neo4j backup
neo4j-admin backup --from=$GRAPH_DATABASE_URL --to=$BACKUP_DIR/graph_backup_$DATE

# Redis backup
redis-cli --rdb $BACKUP_DIR/kv_backup_$DATE.rdb

# Upload to cloud storage
aws s3 cp $BACKUP_DIR/ s3://veris-memory-backups/$(date +%Y/%m/%d)/ --recursive

# Cleanup old local backups (keep 7 days)
find $BACKUP_DIR -type f -mtime +7 -delete
```

**Backup Cron Job**:
```bash
# Crontab entry for daily backups at 2 AM
0 2 * * * /opt/veris-memory/scripts/backup.sh >> /var/log/backup.log 2>&1
```

### Disaster Recovery Plan

1. **Assessment**: Determine scope of failure
2. **Communication**: Notify stakeholders
3. **Recovery**: Execute recovery procedures
4. **Validation**: Verify system functionality
5. **Post-mortem**: Document lessons learned

**Recovery Procedures**:
```bash
# 1. Stop current services
docker-compose down

# 2. Restore from backup
./scripts/restore.sh 20240115_020000

# 3. Verify data integrity
python tools/cli/testing_tools.py validate

# 4. Start services
docker-compose up -d

# 5. Run health checks
python tools/cli/query_simulator.py --benchmark
```

## Performance Tuning

### Application Tuning

**Worker Configuration**:
```python
# Optimal worker count calculation
import multiprocessing
workers = min(4, multiprocessing.cpu_count() * 2 + 1)

# Gunicorn configuration
gunicorn_config = {
    "workers": workers,
    "worker_class": "uvicorn.workers.UvicornWorker",
    "worker_connections": 1000,
    "max_requests": 1000,
    "max_requests_jitter": 100,
    "preload_app": True,
    "timeout": 30,
    "keepalive": 5
}
```

**Connection Pooling**:
```python
# Database connection pools
DATABASE_POOLS = {
    "vector": {
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 3600
    },
    "graph": {
        "max_connections": 50,
        "connection_timeout": 15,
        "max_lifetime": 3600
    },
    "kv": {
        "pool_size": 20,
        "max_connections": 100,
        "timeout": 5
    }
}
```

### Infrastructure Tuning

**Operating System Tuning**:
```bash
# /etc/sysctl.conf optimizations
net.core.somaxconn=65535
net.ipv4.tcp_max_syn_backlog=65535
net.ipv4.tcp_fin_timeout=15
net.ipv4.tcp_keepalive_time=600
net.ipv4.tcp_keepalive_intvl=60
net.ipv4.tcp_keepalive_probes=9

# Apply changes
sysctl -p
```

**Container Resource Limits**:
```yaml
# Docker resource limits
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"

# JVM tuning for Neo4j
environment:
  - NEO4J_dbms_memory_heap_initial__size=1G
  - NEO4J_dbms_memory_heap_max__size=2G
  - NEO4J_dbms_memory_pagecache_size=1G
```

## Troubleshooting

### Common Issues

1. **Application Won't Start**
   ```bash
   # Check logs
   docker logs veris-memory
   
   # Verify configuration
   python -c "from src.core.config import settings; print(settings)"
   
   # Test database connections
   python tools/cli/testing_tools.py validate
   ```

2. **Performance Issues**
   ```bash
   # Run performance benchmarks
   python tools/benchmarks/performance_suite.py quick-benchmark
   
   # Check resource usage
   docker stats
   
   # Monitor database performance
   pg_stat_activity  # PostgreSQL
   neo4j-admin logs  # Neo4j
   redis-cli info    # Redis
   ```

3. **High Error Rates**
   ```bash
   # Check API logs
   tail -f /var/log/veris-memory.log | grep ERROR
   
   # Verify backend health
   curl http://localhost:8000/api/v1/health/detailed
   
   # Run system validation
   python tools/cli/testing_tools.py validate
   ```

### Debug Mode

**Enable Debug Logging**:
```bash
export VERIS_MEMORY_LOG_LEVEL=DEBUG
export VERIS_MEMORY_DEBUG=true
```

**Debug Container**:
```bash
# Run container with debug mode
docker run -it --rm \
  -e VERIS_MEMORY_LOG_LEVEL=DEBUG \
  -e VERIS_MEMORY_DEBUG=true \
  -p 8000:8000 \
  veris-memory:latest \
  python -m pdb src/api/main.py
```

## Scaling and High Availability

### Horizontal Scaling

**Load Balancer Configuration**:
```yaml
# HAProxy configuration
global
    daemon

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend veris_memory_frontend
    bind *:80
    default_backend veris_memory_backend

backend veris_memory_backend
    balance roundrobin
    option httpchk GET /api/v1/health
    server app1 veris-memory-1:8000 check
    server app2 veris-memory-2:8000 check
    server app3 veris-memory-3:8000 check
```

**Auto-scaling Configuration (Kubernetes)**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: veris-memory-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: veris-memory
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Database Scaling

**Read Replicas**:
```yaml
# PostgreSQL read replicas
VECTOR_DATABASE_WRITE_URL=postgresql://user:pass@master:5432/db
VECTOR_DATABASE_READ_URLS=postgresql://user:pass@replica1:5432/db,postgresql://user:pass@replica2:5432/db

# Neo4j cluster
GRAPH_DATABASE_CLUSTER=neo4j://user:pass@core1:7687,neo4j://user:pass@core2:7687,neo4j://user:pass@core3:7687

# Redis cluster
KV_DATABASE_CLUSTER=redis://cluster1:6379,redis://cluster2:6379,redis://cluster3:6379
```

**Connection Pooling and Load Balancing**:
```python
# Database connection management
class DatabaseManager:
    def __init__(self):
        self.write_pool = create_pool(WRITE_DATABASE_URL)
        self.read_pools = [create_pool(url) for url in READ_DATABASE_URLS]
        
    def get_write_connection(self):
        return self.write_pool.get_connection()
    
    def get_read_connection(self):
        return random.choice(self.read_pools).get_connection()
```

## Maintenance and Updates

### Rolling Updates

**Zero-downtime Deployment**:
```bash
#!/bin/bash
# scripts/rolling_update.sh

# Build new image
docker build -t veris-memory:new .

# Update instances one by one
for instance in veris-memory-1 veris-memory-2 veris-memory-3; do
    echo "Updating $instance..."
    
    # Remove from load balancer
    docker exec haproxy sh -c "echo 'disable server veris_memory_backend/$instance' | socat stdio /var/run/haproxy/admin.sock"
    
    # Wait for connections to drain
    sleep 30
    
    # Update instance
    docker stop $instance
    docker rm $instance
    docker run -d --name $instance veris-memory:new
    
    # Wait for health check
    while ! curl -f http://$instance:8000/api/v1/health; do
        sleep 5
    done
    
    # Add back to load balancer
    docker exec haproxy sh -c "echo 'enable server veris_memory_backend/$instance' | socat stdio /var/run/haproxy/admin.sock"
    
    echo "$instance updated successfully"
done

echo "Rolling update completed"
```

**Blue-Green Deployment**:
```bash
#!/bin/bash
# scripts/blue_green_deploy.sh

# Deploy to green environment
kubectl apply -f k8s/green/ --namespace veris-memory-green

# Wait for green environment to be ready
kubectl wait --for=condition=available deployment/veris-memory --namespace veris-memory-green --timeout=300s

# Run health checks on green environment
python tools/cli/testing_tools.py validate --endpoint http://green.veris-memory.internal

# Switch traffic to green
kubectl patch service veris-memory-service --patch '{"spec":{"selector":{"version":"green"}}}'

# Monitor for issues
sleep 60

# If successful, clean up blue environment
kubectl delete namespace veris-memory-blue
```

### Database Migrations

**Migration Script Template**:
```python
#!/usr/bin/env python3
# migrations/001_add_new_indexes.py

"""
Migration: Add performance indexes
Date: 2024-01-15
Description: Add database indexes to improve query performance
"""

import asyncio
from src.storage.backends import get_database_connection

async def migrate_up():
    """Apply migration."""
    conn = await get_database_connection('vector')
    
    # Add indexes
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contexts_timestamp 
        ON contexts(timestamp);
    """)
    
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contexts_tags 
        ON contexts USING GIN(tags);
    """)
    
    print("Migration applied successfully")

async def migrate_down():
    """Rollback migration."""
    conn = await get_database_connection('vector')
    
    # Remove indexes
    await conn.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_contexts_timestamp;")
    await conn.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_contexts_tags;")
    
    print("Migration rolled back successfully")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        asyncio.run(migrate_down())
    else:
        asyncio.run(migrate_up())
```

**Migration Runner**:
```bash
#!/bin/bash
# scripts/run_migrations.sh

MIGRATION_DIR="migrations"
MIGRATION_LOG="migration.log"

echo "Running database migrations..." | tee -a $MIGRATION_LOG

for migration in $(ls $MIGRATION_DIR/*.py | sort); do
    echo "Running migration: $migration" | tee -a $MIGRATION_LOG
    
    if python $migration; then
        echo "✅ Migration completed: $migration" | tee -a $MIGRATION_LOG
    else
        echo "❌ Migration failed: $migration" | tee -a $MIGRATION_LOG
        exit 1
    fi
done

echo "All migrations completed successfully" | tee -a $MIGRATION_LOG
```

## Cost Optimization

### Resource Optimization

**Right-sizing Instances**:
```bash
# Monitor actual resource usage
kubectl top pods --namespace veris-memory

# Adjust resource requests/limits based on usage
resources:
  requests:
    memory: "256Mi"    # Start conservative
    cpu: "250m"
  limits:
    memory: "512Mi"    # Allow bursting
    cpu: "500m"
```

**Spot Instances/Preemptible VMs**:
```yaml
# Kubernetes node affinity for spot instances
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: node.kubernetes.io/instance-type
            operator: In
            values: ["spot"]
```

### Database Cost Optimization

**Connection Pooling**:
```python
# Reduce database connections
DATABASE_CONFIG = {
    "pool_size": 5,        # Reduced from 20
    "max_overflow": 5,     # Reduced from 10
    "pool_timeout": 30,
    "pool_recycle": 1800   # Recycle connections more frequently
}
```

**Query Optimization**:
```python
# Use database query optimization
QUERY_OPTIMIZATION = {
    "enable_query_cache": True,
    "cache_ttl": 300,
    "max_cache_size": 100,
    "use_prepared_statements": True,
    "connection_timeout": 10
}
```

---

*This deployment guide covers the essential aspects of deploying Veris Memory in various environments. For specific deployment scenarios or troubleshooting, refer to the relevant sections or contact the development team.*