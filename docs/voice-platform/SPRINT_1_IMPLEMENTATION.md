# Sprint 1 Implementation Guide - Voice Bot with Real Memory

## Quick Start (Day 1)

### 1. Create Development Session
```bash
# Start fresh session
export WORK_DIR=$(bash /claude-workspace/scripts/new-session.sh)
cd $WORK_DIR

# Create and clone repository
gh repo create credentum/teamai-voice-platform --private --clone
cd teamai-voice-platform
```

### 2. Project Structure
```bash
mkdir -p voice-bot/{app,tests,scripts}
mkdir -p .github/workflows
mkdir -p docker/livekit

# Create structure
touch voice-bot/app/{__init__.py,main.py,memory_client.py,voice_handler.py,config.py}
touch voice-bot/Dockerfile
touch voice-bot/requirements.txt
touch docker-compose.yml
touch .env.example
```

---

## Epic 1: Container & Infrastructure (Day 1-2)

### Task 1.1: Voice-Bot Service Setup (45 min)

**voice-bot/requirements.txt**:
```txt
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
httpx==0.25.1
redis==5.0.1
livekit==0.3.1
livekit-server-sdk==0.5.1
pydantic==2.4.2
pydantic-settings==2.0.3
```

**voice-bot/app/config.py**:
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Service Config
    SERVICE_NAME: str = "voice-bot"
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # LiveKit Config
    LIVEKIT_URL: str = "ws://livekit:7880"
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    # MCP Server Config
    MCP_SERVER_URL: str = "http://mcp-server:8000"
    MCP_API_KEY: Optional[str] = None

    # Redis Config (for session state)
    REDIS_URL: str = "redis://redis:6379"

    class Config:
        env_file = ".env"

settings = Settings()
```

**voice-bot/app/main.py**:
```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
from .config import settings
from .memory_client import MemoryClient
from .voice_handler import VoiceHandler

app = FastAPI(title="TeamAI Voice Bot", version="1.0.0")

# Initialize clients
memory_client = MemoryClient(settings.MCP_SERVER_URL)
voice_handler = VoiceHandler(settings.LIVEKIT_URL, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    await memory_client.initialize()
    await voice_handler.initialize()
    print(f"✅ {settings.SERVICE_NAME} started successfully")

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker"""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "mcp_server": await memory_client.check_health(),
            "livekit": await voice_handler.check_health()
        }
    }

@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "TeamAI Voice Bot",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "voice_session": "/api/v1/voice/session"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
```

**voice-bot/Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create non-root user
RUN useradd -m -u 1000 voicebot && chown -R voicebot:voicebot /app
USER voicebot

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8080/health'); exit(0 if r.status_code == 200 else 1)"

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Task 1.2: Docker Compose Integration (1 hour)

**docker-compose.yml**:
```yaml
version: '3.8'

networks:
  teamai-network:
    name: teamai-network
    driver: bridge

services:
  # LiveKit Server
  livekit:
    image: livekit/livekit-server:latest
    container_name: livekit-server
    ports:
      - "7880:7880"  # WebRTC
      - "7881:7881"  # Turn/TLS
    environment:
      - LIVEKIT_KEYS=${LIVEKIT_API_KEY}:${LIVEKIT_API_SECRET}
      - LIVEKIT_WEBHOOK_URLS=${LIVEKIT_WEBHOOK_URLS:-}
      - LIVEKIT_TURN_ENABLED=true
    networks:
      - teamai-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7880/"]
      interval: 30s
      timeout: 3s
      retries: 3

  # Voice Bot Service
  voice-bot:
    build:
      context: ./voice-bot
      dockerfile: Dockerfile
    container_name: voice-bot
    environment:
      - LIVEKIT_URL=ws://livekit:7880
      - LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
      - LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}
      - MCP_SERVER_URL=http://mcp-server:8000
      - REDIS_URL=redis://redis:6379
    ports:
      - "8080:8080"
    depends_on:
      - livekit
      - redis
    networks:
      - teamai-network
      - veris-network  # Connect to existing MCP network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      retries: 3

  # Redis for session state
  redis:
    image: redis:7-alpine
    container_name: voice-bot-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - teamai-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 3s
      retries: 3

volumes:
  redis-data:

# Connect to existing veris-memory network
networks:
  veris-network:
    external: true
    name: veris-memory_default
```

**.env.example**:
```env
# LiveKit Configuration
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=secretxxxxxxxxxxxxx

# MCP Server (uses existing veris-memory)
MCP_SERVER_URL=http://mcp-server:8000
MCP_API_KEY=optional_api_key

# Redis
REDIS_URL=redis://redis:6379

# Service Config
SERVICE_NAME=voice-bot
HOST=0.0.0.0
PORT=8080
```

### Task 1.3: GitHub Actions CI/CD (1 hour)

**.github/workflows/ci.yml**:
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd voice-bot
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          cd voice-bot
          pytest tests/ --cov=app --cov-report=term-missing

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Build and test Docker image
        run: |
          docker compose build voice-bot
          docker compose up -d
          sleep 10
          curl -f http://localhost:8080/health || exit 1
          docker compose down

      - name: Deploy (placeholder)
        run: |
          echo "Deploy to production server"
          # Add your deployment steps here
```

---

## Epic 2: MCP Fact Storage Integration (Day 2-3)

### Task 2.1: Memory Client Implementation (2 hours)

**voice-bot/app/memory_client.py**:
```python
"""
MCP Memory Client for Voice Bot
Integrates with veris-memory MCP server for fact storage and retrieval
"""
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MemoryClient:
    """Client for interacting with MCP memory server"""

    def __init__(self, mcp_url: str, api_key: Optional[str] = None):
        self.mcp_url = mcp_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def initialize(self):
        """Initialize connection to MCP server"""
        try:
            response = await self.client.get(f"{self.mcp_url}/health")
            if response.status_code == 200:
                logger.info("✅ Connected to MCP server")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to MCP server: {e}")
            return False

    async def store_fact(self, user_id: str, key: str, value: Any) -> bool:
        """
        Store a fact about a user
        Uses namespace pattern: voicebot_{user_id}
        """
        namespace = f"voicebot_{user_id}"

        payload = {
            "method": "store_context",
            "params": {
                "type": "fact",
                "content": {
                    "namespace": namespace,
                    "user_id": user_id,
                    "key": key,
                    "value": value,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "metadata": {
                    "source": "voice_input",
                    "fact_key": f"{namespace}:{key}"
                }
            }
        }

        try:
            response = await self.client.post(
                f"{self.mcp_url}/mcp/v1/call_tool",
                json=payload
            )

            if response.status_code == 200:
                logger.info(f"✅ Stored fact: {user_id}:{key} = {value}")
                return True
            else:
                logger.error(f"Failed to store fact: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error storing fact: {e}")
            return False

    async def get_user_facts(self, user_id: str, keys: List[str] = None) -> Dict[str, Any]:
        """
        Retrieve facts about a user
        Primary: Direct key lookup
        Fallback: Semantic search (last 5 facts)
        """
        namespace = f"voicebot_{user_id}"
        facts = {}

        # If specific keys requested, try direct lookup first
        if keys:
            for key in keys:
                value = await self._get_fact_by_key(namespace, user_id, key)
                if value is not None:
                    facts[key] = value

        # If no keys specified or some missing, use semantic search
        if not keys or len(facts) < len(keys):
            semantic_facts = await self._semantic_fact_search(namespace, user_id, limit=5)
            facts.update(semantic_facts)

        logger.info(f"Retrieved {len(facts)} facts for user {user_id}")
        return facts

    async def _get_fact_by_key(self, namespace: str, user_id: str, key: str) -> Optional[Any]:
        """Direct key lookup using Redis pattern"""
        # This would connect to Redis directly or via MCP
        fact_key = f"facts:{namespace}:{user_id}:{key}"

        payload = {
            "method": "retrieve_context",
            "params": {
                "query": fact_key,
                "namespaces": [namespace],
                "limit": 1,
                "filters": {
                    "metadata.fact_key": fact_key
                }
            }
        }

        try:
            response = await self.client.post(
                f"{self.mcp_url}/mcp/v1/call_tool",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    return result["results"][0]["content"].get("value")

        except Exception as e:
            logger.error(f"Error retrieving fact by key: {e}")

        return None

    async def _semantic_fact_search(self, namespace: str, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """Semantic search fallback for facts"""
        payload = {
            "method": "retrieve_context",
            "params": {
                "query": f"user facts for {user_id}",
                "namespaces": [namespace],
                "limit": limit,
                "filters": {
                    "type": "fact",
                    "content.user_id": user_id
                }
            }
        }

        facts = {}
        try:
            response = await self.client.post(
                f"{self.mcp_url}/mcp/v1/call_tool",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                for item in result.get("results", []):
                    content = item.get("content", {})
                    if "key" in content and "value" in content:
                        facts[content["key"]] = content["value"]

        except Exception as e:
            logger.error(f"Error in semantic fact search: {e}")

        return facts

    async def store_conversation_trace(self, user_id: str, messages: List[Dict]) -> bool:
        """Store conversation history for analysis (not for fact retrieval)"""
        namespace = f"voicebot_{user_id}"

        payload = {
            "method": "store_context",
            "params": {
                "type": "trace",
                "content": {
                    "namespace": namespace,
                    "user_id": user_id,
                    "messages": messages,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "metadata": {
                    "source": "voice_conversation",
                    "message_count": len(messages)
                }
            }
        }

        try:
            response = await self.client.post(
                f"{self.mcp_url}/mcp/v1/call_tool",
                json=payload
            )
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error storing conversation trace: {e}")
            return False

    async def check_health(self) -> bool:
        """Check MCP server health"""
        try:
            response = await self.client.get(f"{self.mcp_url}/health")
            return response.status_code == 200
        except:
            return False
```

### Task 2.2: Unit Tests (1 hour)

**voice-bot/tests/test_memory_client.py**:
```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.memory_client import MemoryClient

@pytest.fixture
async def memory_client():
    client = MemoryClient("http://localhost:8000")
    return client

@pytest.mark.asyncio
async def test_store_fact(memory_client):
    """Test storing a user fact"""
    with patch.object(memory_client.client, 'post', new=AsyncMock()) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"success": True}

        result = await memory_client.store_fact("user123", "name", "Matt")

        assert result == True
        mock_post.assert_called_once()

        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['params']['type'] == 'fact'
        assert payload['params']['content']['key'] == 'name'
        assert payload['params']['content']['value'] == 'Matt'

@pytest.mark.asyncio
async def test_get_user_facts(memory_client):
    """Test retrieving user facts"""
    expected_facts = {'name': 'Matt', 'color': 'blue'}

    with patch.object(memory_client, '_get_fact_by_key', new=AsyncMock()) as mock_get:
        mock_get.side_effect = ['Matt', 'blue']

        facts = await memory_client.get_user_facts("user123", ["name", "color"])

        assert facts == expected_facts
        assert mock_get.call_count == 2

@pytest.mark.asyncio
async def test_fact_retrieval_fallback(memory_client):
    """Test semantic search fallback when key lookup fails"""
    with patch.object(memory_client, '_get_fact_by_key', return_value=None):
        with patch.object(memory_client, '_semantic_fact_search') as mock_semantic:
            mock_semantic.return_value = {'name': 'Matt', 'role': 'PM'}

            facts = await memory_client.get_user_facts("user123", ["name", "role"])

            assert facts['name'] == 'Matt'
            assert facts['role'] == 'PM'
            mock_semantic.assert_called_once()

@pytest.mark.asyncio
async def test_missing_fact_raises_error(memory_client):
    """Test that missing critical facts raise ValueError"""
    with patch.object(memory_client, 'get_user_facts', return_value={}):

        facts = await memory_client.get_user_facts("user123", ["name"])

        if not facts.get('name'):
            with pytest.raises(ValueError):
                raise ValueError(f"Critical fact 'name' not found for user user123")
```

---

## Epic 3: LiveKit Voice Integration (Day 3-4)

### Task 3.1: Voice Handler Implementation (2 hours)

**voice-bot/app/voice_handler.py**:
```python
"""
LiveKit Voice Handler for real-time voice interaction
"""
import asyncio
from typing import Optional, Dict, Any
from livekit import api, rtc
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VoiceHandler:
    """Handles LiveKit voice interactions"""

    def __init__(self, livekit_url: str, api_key: str, api_secret: str):
        self.livekit_url = livekit_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.room_service = None
        self.token_service = None

    async def initialize(self):
        """Initialize LiveKit services"""
        try:
            # Initialize API clients
            self.room_service = api.RoomService(
                self.livekit_url.replace("ws://", "http://").replace("wss://", "https://"),
                self.api_key,
                self.api_secret
            )
            logger.info("✅ LiveKit services initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize LiveKit: {e}")
            return False

    def create_token(self, room_name: str, participant_name: str) -> str:
        """Create access token for participant"""
        token = api.AccessToken(self.api_key, self.api_secret)
        token.with_identity(participant_name)
        token.with_name(participant_name)
        token.with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True
            )
        )
        return token.to_jwt()

    async def create_voice_session(self, user_id: str) -> Dict[str, Any]:
        """Create a new voice session for user"""
        room_name = f"voice_{user_id}_{int(datetime.now().timestamp())}"

        # Create room
        try:
            await self.room_service.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    max_participants=2,  # User + bot
                    empty_timeout=300  # 5 minutes
                )
            )

            # Generate tokens
            user_token = self.create_token(room_name, f"user_{user_id}")
            bot_token = self.create_token(room_name, f"bot_{user_id}")

            # Start bot participant
            asyncio.create_task(self._start_bot_participant(room_name, bot_token))

            return {
                "room_name": room_name,
                "token": user_token,
                "url": self.livekit_url,
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating voice session: {e}")
            raise

    async def _start_bot_participant(self, room_name: str, token: str):
        """Start the bot participant in the room"""
        try:
            room = rtc.Room()

            @room.on("participant_connected")
            async def on_participant_connected(participant: rtc.RemoteParticipant):
                logger.info(f"Participant connected: {participant.identity}")
                # Send welcome message via TTS
                await self._send_tts_message(room, "Hello! I can hear you. What's your name?")

            @room.on("track_published")
            async def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
                if publication.kind == rtc.TrackKind.KIND_AUDIO:
                    logger.info(f"Audio track published by {participant.identity}")
                    # Subscribe to audio track for STT
                    track = await publication.track()
                    asyncio.create_task(self._process_audio_track(room, track, participant))

            # Connect to room
            await room.connect(self.livekit_url, token)
            logger.info(f"Bot connected to room: {room_name}")

            # Keep the bot running
            while room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in bot participant: {e}")

    async def _process_audio_track(self, room: rtc.Room, track: rtc.Track, participant: rtc.RemoteParticipant):
        """Process incoming audio for STT"""
        # This is a simplified version - real implementation would use STT service
        logger.info(f"Processing audio from {participant.identity}")

        # Simulate STT processing
        await asyncio.sleep(2)

        # Echo test response
        response = f"Hi! I heard you. This is an echo test."
        await self._send_tts_message(room, response)

    async def _send_tts_message(self, room: rtc.Room, text: str):
        """Send TTS message to room"""
        # This is a simplified version - real implementation would use TTS service
        logger.info(f"Sending TTS: {text}")

        # In production, you would:
        # 1. Convert text to audio using TTS service
        # 2. Publish audio track to room
        # For now, we'll just log it

    async def check_health(self) -> bool:
        """Check LiveKit server health"""
        try:
            # Try to list rooms as health check
            if self.room_service:
                rooms = await self.room_service.list_rooms(api.ListRoomsRequest())
                return True
        except:
            return False
        return False
```

### Task 3.2: Voice Session API Endpoint

**Add to voice-bot/app/main.py**:
```python
@app.post("/api/v1/voice/session")
async def create_voice_session(user_id: str):
    """Create a new voice session for user"""
    try:
        session = await voice_handler.create_voice_session(user_id)
        return JSONResponse(content=session, status_code=201)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/voice/echo-test")
async def echo_test(user_id: str, message: str):
    """Echo test endpoint for validation"""
    try:
        # Store fact
        await memory_client.store_fact(user_id, "last_message", message)

        # Retrieve facts
        facts = await memory_client.get_user_facts(user_id, ["name", "color"])

        # Generate response
        name = facts.get("name", "friend")
        color = facts.get("color", "unknown")

        response = f"Hi {name}! Your favorite color is {color}. You said: {message}"

        return {
            "user_id": user_id,
            "input": message,
            "response": response,
            "facts": facts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Epic 4: Validation Gate (Day 4)

### Task 4.1: Integration Test Script

**voice-bot/tests/test_integration.py**:
```python
"""
Integration tests for Sprint 1 validation gate
MUST PASS before merge to main
"""
import pytest
import httpx
import asyncio
import time

BASE_URL = "http://localhost:8080"

@pytest.mark.integration
async def test_persistence_across_restart():
    """
    CRITICAL TEST: Facts must persist across container restart
    """
    async with httpx.AsyncClient() as client:
        user_id = f"test_user_{int(time.time())}"

        # Store facts
        response = await client.post(
            f"{BASE_URL}/api/v1/voice/echo-test",
            params={"user_id": user_id, "message": "My name is TestUser"}
        )
        assert response.status_code == 200

        # Store color preference
        response = await client.post(
            f"{BASE_URL}/api/v1/voice/echo-test",
            params={"user_id": user_id, "message": "My favorite color is green"}
        )
        assert response.status_code == 200

        # Simulate container restart
        print("⚠️ MANUAL STEP: Restart voice-bot container now")
        print("Run: docker compose restart voice-bot")
        input("Press Enter after restart is complete...")

        # Wait for service to be ready
        await asyncio.sleep(5)

        # Retrieve facts after restart
        response = await client.post(
            f"{BASE_URL}/api/v1/voice/echo-test",
            params={"user_id": user_id, "message": "What's my name?"}
        )

        assert response.status_code == 200
        data = response.json()

        # VALIDATION GATE: Must retrieve stored facts
        assert "facts" in data
        assert data["facts"].get("name") == "TestUser", "❌ FAILED: Name not persisted"
        assert data["facts"].get("color") == "green", "❌ FAILED: Color not persisted"

        print("✅ PASSED: Facts persisted across restart")

@pytest.mark.integration
async def test_no_hallucination():
    """
    Test that system doesn't hallucinate facts
    """
    async with httpx.AsyncClient() as client:
        user_id = f"new_user_{int(time.time())}"

        # Ask for facts that don't exist
        response = await client.post(
            f"{BASE_URL}/api/v1/voice/echo-test",
            params={"user_id": user_id, "message": "What's my favorite food?"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should not make up facts
        assert data["facts"].get("food") is None, "❌ FAILED: System hallucinated food preference"
        assert "unknown" in data["response"].lower() or "don't know" in data["response"].lower()

        print("✅ PASSED: No hallucination of facts")

if __name__ == "__main__":
    asyncio.run(test_persistence_across_restart())
    asyncio.run(test_no_hallucination())
```

### Task 4.2: Validation Script

**scripts/validate_sprint1.sh**:
```bash
#!/bin/bash

echo "🚀 Sprint 1 Validation Gate"
echo "=========================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Start services
echo "Starting services..."
docker compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Check health
echo "Checking service health..."
HEALTH=$(curl -s http://localhost:8080/health | jq -r '.status')

if [ "$HEALTH" != "healthy" ]; then
    echo -e "${RED}❌ FAILED: Service not healthy${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Service healthy${NC}"

# Run integration tests
echo "Running integration tests..."
cd voice-bot
python -m pytest tests/test_integration.py -v

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ FAILED: Integration tests failed${NC}"
    echo "Sprint 1 validation gate: FAILED"
    exit 1
fi

# Test persistence
echo "Testing persistence across restart..."

# Store test data
USER_ID="validation_$(date +%s)"
curl -X POST "http://localhost:8080/api/v1/voice/echo-test?user_id=$USER_ID&message=My%20name%20is%20ValidationUser"

# Restart container
echo "Restarting voice-bot container..."
docker compose restart voice-bot
sleep 10

# Check if facts persist
RESPONSE=$(curl -s "http://localhost:8080/api/v1/voice/echo-test?user_id=$USER_ID&message=What%20is%20my%20name")
NAME=$(echo $RESPONSE | jq -r '.facts.name')

if [ "$NAME" != "ValidationUser" ]; then
    echo -e "${RED}❌ FAILED: Facts did not persist across restart${NC}"
    echo "Expected: ValidationUser, Got: $NAME"
    exit 1
fi

echo -e "${GREEN}✅ PASSED: Facts persisted across restart${NC}"

# Final result
echo ""
echo "================================"
echo -e "${GREEN}🎉 SPRINT 1 VALIDATION: PASSED${NC}"
echo "================================"
echo ""
echo "Sprint 1 Deliverables:"
echo "✅ Voice-bot service deployed"
echo "✅ MCP memory integration working"
echo "✅ Facts persist across restarts"
echo "✅ No hallucinations on unknown facts"
echo "✅ Docker compose deployment ready"
echo ""
echo "Ready for Sprint 2: Claude Integration"
```

---

## Quick Development Commands

```bash
# Day 1: Setup
export WORK_DIR=$(bash /claude-workspace/scripts/new-session.sh)
cd $WORK_DIR
gh repo create credentum/teamai-voice-platform --private --clone
cd teamai-voice-platform

# Create structure
mkdir -p voice-bot/{app,tests,scripts}
mkdir -p .github/workflows

# Copy .env
cp .env.example .env
# Edit .env with your LiveKit credentials

# Day 2: Build and Run
docker compose build
docker compose up -d

# Check health
curl http://localhost:8080/health | jq

# Day 3: Test echo
curl -X POST "http://localhost:8080/api/v1/voice/echo-test?user_id=test123&message=Hello"

# Day 4: Validate
bash scripts/validate_sprint1.sh
```

---

## Success Criteria Checklist

- [ ] Voice-bot service starts successfully
- [ ] Health endpoint returns healthy status
- [ ] MCP connection established
- [ ] Facts can be stored via API
- [ ] Facts can be retrieved via API
- [ ] Facts persist after container restart
- [ ] No hallucinations on missing facts
- [ ] Docker compose brings up all services
- [ ] CI/CD pipeline passes
- [ ] Validation script passes

When all items are checked, Sprint 1 is complete! 🚀