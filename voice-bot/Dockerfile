# Stage 1: Install Claude CLI using official Node.js image
# Using pinned digest avoids curl-pipe-bash pattern and ensures reproducible builds
FROM node:20.18-slim@sha256:ffc11dbf16dd0abcbb7b837410601b4d5592db2d03741e13a4a5336ab74d7ccb AS node-builder

# Install Claude CLI with pinned version for reproducibility
RUN npm install -g @anthropic-ai/claude-code@2.0.55

# Stage 2: Python application
FROM python:3.11-slim@sha256:fa9b525a0be0c5ae5e6f2209f4be6fdc5a15a36fed0222144d98ac0d08f876d4

WORKDIR /app

# Security: Upgrade vulnerable packages to fix CVEs detected in base image
# CVE-2025-4802, CVE-2025-6965, CVE-2025-7458, CVE-2023-7104, CVE-2023-31484, CVE-2024-56406
RUN apt-get update && \
    apt-get upgrade -y \
        libc-bin \
        libc6 \
        libsqlite3-0 \
        perl-base && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Node.js runtime and Claude CLI from builder stage
COPY --from=node-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=node-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js /usr/local/bin/claude && \
    chmod +x /usr/local/bin/claude

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY app/ ./app/

# Copy frontend (served as static files)
COPY frontend/ ./frontend/

# Create non-root user for security
# Use UID 1000 to match typical host user for OAuth credential mounting
RUN useradd -m -u 1000 voicebot && \
    chown -R voicebot:voicebot /app && \
    mkdir -p /home/voicebot/.claude && \
    chown -R voicebot:voicebot /home/voicebot/.claude

USER voicebot

# Expose port
EXPOSE 8000

# Run from app directory
WORKDIR /app/app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
