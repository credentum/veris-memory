FROM python:3.11-slim@sha256:fa9b525a0be0c5ae5e6f2209f4be6fdc5a15a36fed0222144d98ac0d08f876d4

WORKDIR /app

# Install system dependencies (curl for healthcheck, Node.js for Claude CLI)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

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
