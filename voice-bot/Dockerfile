FROM python:3.11-slim@sha256:fa9b525a0be0c5ae5e6f2209f4be6fdc5a15a36fed0222144d98ac0ad08f876d4

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create non-root user
RUN useradd -m -u 1000 voicebot && \
    chown -R voicebot:voicebot /app && \
    mkdir -p /app/logs && \
    chown -R voicebot:voicebot /app/logs

USER voicebot

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
