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

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LIVEKIT_URL` | LiveKit server URL | `ws://livekit:7880` |
| `LIVEKIT_API_KEY` | LiveKit API key | Required |
| `LIVEKIT_API_SECRET` | LiveKit API secret | Required |
| `MCP_SERVER_URL` | MCP server URL | `http://context-store:8000` |
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
