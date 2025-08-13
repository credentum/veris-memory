# Production Dockerfile for Context Store API
# This is the Python-only container for use with docker-compose
# where other services (Qdrant, Neo4j, Redis) run as separate containers

FROM python:3.11-slim as builder

# Build arguments
ARG ENVIRONMENT=production

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser schemas/ ./schemas/
COPY --chown=appuser:appuser contracts/ ./contracts/
# Use Docker-specific config file with service names instead of localhost
COPY --chown=appuser:appuser .ctxrc.docker.yaml ./.ctxrc.yaml

# Optional directories - commented out since they don't exist in current structure
# COPY --chown=appuser:appuser monitoring/ ./monitoring/
# COPY --chown=appuser:appuser secrets/ ./secrets/

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Environment variables (will be overridden by docker-compose)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MCP_SERVER_PORT=8000
ENV LOG_LEVEL=info

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Start the application with FastAPI/Uvicorn for HTTP endpoints
CMD ["python", "-m", "uvicorn", "src.mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000"]