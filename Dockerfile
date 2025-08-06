# Python-only build for context-store
FROM python:3.11-slim@sha256:2341b57325e6e93098fb8858facb767311137e796c9b392920db78662e43c87f

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r contextstore && useradd -r -g contextstore contextstore

# Set work directory
WORKDIR /app

# Copy Python requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source
COPY src/ ./src/

# Copy configuration files
COPY schemas/ ./schemas/
COPY contracts/ ./contracts/

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data && \
    chown -R contextstore:contextstore /app

# Switch to non-root user
USER contextstore

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["python", "-m", "uvicorn", "src.mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
