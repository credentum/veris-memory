# Voice Bot Service - TeamAI Voice Platform

Voice-enabled AI teammate with persistent memory integration via Veris MCP.

## Overview

The Voice Bot service adds real-time voice interaction capabilities to the Veris Memory platform, enabling users to interact with AI teammates through voice commands while maintaining persistent memory across sessions.

## Features

- **Real-time Voice**: LiveKit WebRTC integration for low-latency voice
- **Persistent Memory**: Fact-based storage using Veris MCP (not chat logs)
- **Session Management**: Isolated voice sessions per user
- **Health Monitoring**: Integration with existing monitoring infrastructure

## Architecture

```
User Voice → LiveKit → Voice Bot → MCP Server (Veris) → Storage (Qdrant/Neo4j/Redis)
```

## Quick Start

### Prerequisites

- Veris Memory platform running (`docker-compose.yml`)
- LiveKit API credentials
- Speech-to-Text API key (Deepgram, Whisper, etc.)
- Text-to-Speech API key (ElevenLabs, Google, etc.)

### Configuration

1. Copy environment template:
```bash
cp ../.env.voice.example ../.env.voice
```

2. Edit `.env.voice` with your credentials:
```env
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_secret
STT_API_KEY=your_stt_key
TTS_API_KEY=your_tts_key
```

### Running the Service

```bash
# From veris-memory root directory
docker compose -f docker-compose.yml -f docker-compose.voice.yml up -d
```

### Testing

#### Health Check
```bash
curl http://localhost:8002/health
```

#### Echo Test (Sprint 1 Validation)
```bash
# Store a fact
curl -X POST "http://localhost:8002/api/v1/voice/echo-test?user_id=test123&message=My%20name%20is%20Alice"

# Verify persistence (restart container first)
docker compose restart voice-bot
curl -X POST "http://localhost:8002/api/v1/voice/echo-test?user_id=test123&message=What%20is%20my%20name"
```

## API Endpoints

### Core Endpoints

- `GET /` - Service information
- `GET /health` - Health check with dependency status
- `GET /docs` - Interactive API documentation

### Voice Session Management

- `POST /api/v1/voice/session?user_id={id}` - Create voice session
  - Returns LiveKit room details and token

### Fact Management

- `POST /api/v1/facts/store` - Store user fact
  - Params: `user_id`, `key`, `value`

- `GET /api/v1/facts/{user_id}` - Retrieve user facts
  - Optional: `keys` (comma-separated)

### Testing

- `POST /api/v1/voice/echo-test` - Echo test for validation
  - Params: `user_id`, `message`
  - Tests fact storage and retrieval

## Development

### Project Structure

```
voice-bot/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── memory_client.py     # MCP integration
│   └── voice_handler.py     # LiveKit integration
├── tests/
│   └── test_memory_client.py
├── scripts/
├── Dockerfile
├── requirements.txt
└── README.md
```

### Local Development

```bash
# Install dependencies
cd voice-bot
pip install -r requirements.txt

# Run locally
python -m app.main
```

### Running Tests

```bash
pytest tests/ -v
```

## Sprint 1 Validation

The service must pass these criteria:

- ✅ Voice-bot service deploys successfully
- ✅ Facts persist across container restarts
- ✅ No hallucinations on unknown facts
- ✅ Latency <500ms for fact retrieval

### Validation Script

```bash
# From veris-memory root
bash voice-bot/scripts/validate_sprint1.sh
```

## Integration with Veris MCP

### Namespace Pattern

Facts are stored using namespace pattern:
```
voicebot_{user_id}
```

### Fact Storage

```python
# Store fact
POST /mcp/v1/call_tool
{
  "method": "store_context",
  "params": {
    "type": "fact",
    "content": {
      "namespace": "voicebot_user123",
      "key": "name",
      "value": "Alice"
    }
  }
}
```

### Fact Retrieval

Two-stage retrieval:
1. **Direct key lookup** - Fast Redis-backed lookup
2. **Semantic search** - Fallback using vector similarity

## Sprint 13 Integration

The voice-bot has been updated to integrate with **Veris Memory Sprint 13** changes (PR #161).

### New Features

#### 1. API Key Authentication

Sprint 13 added mandatory API key authentication to the MCP server.

**Configuration** (`.env.voice`):
```env
# Required if veris-memory has AUTH_REQUIRED=true
MCP_API_KEY=vmk_voicebot_prod_key
```

**MCP Server Setup** (veris-memory `.env`):
```env
AUTH_REQUIRED=true
API_KEY_VOICEBOT=vmk_voicebot_prod_key:voice_bot:writer:true
```

#### 2. Author Attribution

All stored contexts now include author information for audit trails:
- `author`: `voice_bot_{user_id}` (e.g., `voice_bot_alice`)
- `author_type`: `agent` (identifies voice-bot as an AI agent)

**Configuration** (`.env.voice`):
```env
# Customize author prefix (default: voice_bot)
VOICE_BOT_AUTHOR_PREFIX=voice_bot
```

#### 3. Retry Logic with Exponential Backoff

Based on lessons from [veris-memory PR #3](https://github.com/credentum/veris-memory-mcp-server/pull/3):
- **Reduces error rate from 98% to <5%**
- 3 retry attempts with exponential backoff (1s, 2s, 4s)
- Automatic retry for transient failures (5xx errors)
- No retry for auth errors (401)

**Configuration** (`.env.voice`):
```env
ENABLE_MCP_RETRY=true
MCP_RETRY_ATTEMPTS=3
```

#### 4. Embedding Pipeline Visibility

Voice-bot now logs embedding status for all stored facts:
- ✅ `completed` - Semantic search available
- ⚠️ `failed` - Embedding generation failed (logs warning)
- ⚠️ `unavailable` - Embedding service not initialized

**New Endpoint**: `GET /health/detailed`
```bash
curl http://localhost:8002/health/detailed
```

Returns:
```json
{
  "service": "voice-bot",
  "status": "healthy",
  "mcp_server": {
    "embedding_pipeline": {
      "qdrant_connected": true,
      "embedding_service_loaded": true,
      "collection_created": true,
      "test_embedding_successful": true
    },
    "services": {
      "embeddings": "healthy"
    }
  }
}
```

#### 5. Relationship Auto-Detection

Sprint 13 automatically creates graph relationships between contexts:
- Temporal relationships (sequential facts)
- Reference relationships (PR #, issue #, context IDs)
- Hierarchical relationships (user → facts)

Voice-bot logs relationship creation count for debugging.

### Error Handling

#### Authentication Errors (401)

If `MCP_API_KEY` is missing or invalid:
```
❌ Authentication failed. Check MCP_API_KEY configuration.
```

**Solution**:
1. Verify `MCP_API_KEY` is set in `.env.voice`
2. Verify matching key is configured on MCP server
3. Check MCP server logs: `docker compose logs context-store`

#### Embedding Failures

If embedding service is down:
```
⚠️ Embedding unavailable for fact alice:name - semantic search will not work
```

**Impact**: Facts still stored, but semantic search unavailable (direct key lookup still works).

**Solution**: Check embedding service on MCP server:
```bash
curl http://localhost:8000/health/detailed | jq '.embedding_pipeline'
```

### Backward Compatibility

Voice-bot remains **fully backward compatible**:
- Works with `AUTH_REQUIRED=false` (no API key needed)
- Works with pre-Sprint-13 veris-memory (ignores new fields)
- All new features are additive (no breaking changes)

### Migration Guide

#### Upgrading from Pre-Sprint-13

1. **Pull latest veris-memory**: Ensure Sprint 13 is deployed
2. **Configure API key** (if `AUTH_REQUIRED=true`):
   ```bash
   # .env.voice
   MCP_API_KEY=vmk_voicebot_prod_key

   # veris-memory .env
   AUTH_REQUIRED=true
   API_KEY_VOICEBOT=vmk_voicebot_prod_key:voice_bot:writer:true
   ```
3. **Restart voice-bot**:
   ```bash
   docker compose restart voice-bot
   ```
4. **Verify health**:
   ```bash
   curl http://localhost:8002/health/detailed
   ```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LIVEKIT_URL` | LiveKit server URL | `ws://livekit:7880` |
| `LIVEKIT_API_KEY` | LiveKit API key | Required |
| `LIVEKIT_API_SECRET` | LiveKit API secret | Required |
| `MCP_SERVER_URL` | MCP server URL | `http://context-store:8000` |
| **`MCP_API_KEY`** | **Sprint 13: API key for MCP auth** | `None` (optional) |
| **`VOICE_BOT_AUTHOR_PREFIX`** | **Sprint 13: Author prefix** | `voice_bot` |
| **`ENABLE_MCP_RETRY`** | **Sprint 13: Enable retry logic** | `true` |
| **`MCP_RETRY_ATTEMPTS`** | **Sprint 13: Retry attempt count** | `3` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379` |
| `STT_PROVIDER` | Speech-to-text provider | `deepgram` |
| `TTS_PROVIDER` | Text-to-speech provider | `elevenlabs` |
| `PORT` | Service port | `8002` |
| `LOG_LEVEL` | Logging level | `info` |

## Troubleshooting

### Voice Bot Won't Start

```bash
# Check logs
docker compose logs voice-bot

# Check dependencies
docker compose ps
```

### Can't Connect to MCP Server

```bash
# Verify MCP server is running
curl http://localhost:8000/health

# Check network connectivity
docker compose exec voice-bot ping context-store
```

### Facts Not Persisting

```bash
# Check Redis connection
docker compose exec redis redis-cli ping

# Verify MCP storage
curl http://localhost:8001/api/v1/health/storage
```

## Documentation

- **[Platform Plan](../docs/voice-platform/TEAMAI_VOICE_PLATFORM_PLAN.md)** - Full roadmap
- **[Sprint 1 Implementation](../docs/voice-platform/SPRINT_1_IMPLEMENTATION.md)** - Detailed guide
- **[MCP Integration](../docs/voice-platform/VOICEBOT_INTEGRATION_GUIDE.md)** - Integration patterns

## License

Internal use only - Credentum proprietary
