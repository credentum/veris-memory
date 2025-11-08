# Voice-Bot Integration Quick Reference

## Quick Start

### 1. Connect to Veris Memory

```python
import requests
import json

# Configuration
VERIS_URL = "http://localhost:8000"  # or http://context-store:8000 in Docker
USER_ID = "telegram_123456789"  # Unique telegram user ID
AGENT_ID = "voicebot_v1"
NAMESPACE = f"voicebot_telegram_{USER_ID}"

# Health check
response = requests.get(f"{VERIS_URL}/health")
assert response.status_code == 200, "Veris Memory not responding"
```

### 2. Store User Facts (Key-Value)

```python
# Store a fact via HTTP endpoint (if using main.py)
def store_user_fact(attribute, value, confidence=1.0):
    """Store a user fact with metadata"""
    response = requests.post(
        f"{VERIS_URL}/tools/update_scratchpad",
        json={
            "agent_id": AGENT_ID,
            "key": f"fact:{attribute}",
            "content": json.dumps({
                "value": value,
                "confidence": confidence,
                "user_id": USER_ID,
                "namespace": NAMESPACE
            }),
            "mode": "overwrite",
            "ttl": 2592000  # 30 days
        }
    )
    return response.json()

# Usage
store_user_fact("name", "Alice")
store_user_fact("timezone", "America/New_York", confidence=0.9)
store_user_fact("language", "English")
```

### 3. Retrieve Context (Semantic Search)

```python
def retrieve_user_context(query, limit=5):
    """Retrieve context relevant to user's query"""
    response = requests.post(
        f"{VERIS_URL}/tools/retrieve_context",
        json={
            "query": query,
            "search_mode": "hybrid",  # vector + graph + kv
            "limit": limit,
            "filters": {
                "namespaces": [NAMESPACE]  # Filter to this user
            }
        }
    )
    return response.json()

# Usage
results = retrieve_user_context("What are my preferences?")
for result in results["results"]:
    print(f"- {result['content']} (relevance: {result['score']})")
```

### 4. Manage Session State

```python
def update_session_state(state_dict):
    """Update conversation session state"""
    response = requests.post(
        f"{VERIS_URL}/tools/update_scratchpad",
        json={
            "agent_id": AGENT_ID,
            "key": f"session:{USER_ID}",
            "content": json.dumps(state_dict),
            "mode": "overwrite",
            "ttl": 3600  # 1 hour
        }
    )
    return response.json()

def get_session_state():
    """Retrieve current session state"""
    response = requests.post(
        f"{VERIS_URL}/tools/get_agent_state",
        json={
            "agent_id": AGENT_ID,
            "key": f"session:{USER_ID}",
            "prefix": "scratchpad"
        }
    )
    data = response.json()
    return json.loads(data["data"].get(f"session:{USER_ID}", "{}"))

# Usage
update_session_state({
    "turn_count": 42,
    "last_topic": "preferences",
    "conversation_id": "conv_123"
})

state = get_session_state()
print(f"Turn {state['turn_count']}: Discussing {state['last_topic']}")
```

### 5. Store Conversation History

```python
def log_conversation(messages, summary):
    """Store conversation as trace context"""
    response = requests.post(
        f"{VERIS_URL}/tools/store_context",
        json={
            "type": "trace",
            "content": {
                "user_id": USER_ID,
                "namespace": NAMESPACE,
                "messages": messages,
                "summary": summary,
                "timestamp": datetime.utcnow().isoformat()
            },
            "metadata": {
                "source": "telegram_voice_bot",
                "tags": ["conversation", USER_ID, "voice"]
            }
        }
    )
    return response.json()

# Usage
log_conversation(
    messages=[
        {"role": "user", "content": "What's my name?"},
        {"role": "assistant", "content": "Your name is Alice"}
    ],
    summary="User asked for their name"
)
```

---

## API Endpoint Reference

### POST /tools/store_context
Store structured data (design, decision, trace, sprint, log)

```json
{
  "type": "trace|design|decision|sprint|log",
  "content": {
    "title": "string",
    "description": "string",
    "data": {}
  },
  "metadata": {
    "source": "string",
    "tags": ["array", "of", "strings"],
    "priority": "low|medium|high|critical"
  },
  "relationships": [
    {"type": "RELATED_TO", "target": "other_id"}
  ]
}
```

**Response**: `{success, id, vector_id, graph_id, message}`

---

### POST /tools/retrieve_context
Retrieve context via hybrid search

```json
{
  "query": "search query",
  "type": "all|design|decision|trace|sprint|log",
  "search_mode": "vector|graph|kv|text|hybrid|auto",
  "limit": 1-100,
  "filters": {
    "namespaces": ["namespace1", "namespace2"],
    "date_from": "2025-01-01",
    "date_to": "2025-12-31",
    "tags": ["tag1", "tag2"]
  },
  "include_relationships": true,
  "sort_by": "timestamp|relevance"
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "id": "ctx_123",
      "content": {},
      "score": 0.95,
      "source": "vector|graph|kv|text",
      "type": "string",
      "namespace": "voicebot_telegram_123",
      "user_id": "123",
      "tags": ["array"],
      "relationships": []
    }
  ],
  "total_count": 1,
  "search_mode_used": "hybrid",
  "backend_timings": {"vector": 15.2, "graph": 8.5},
  "backends_used": ["vector", "graph"]
}
```

---

### POST /tools/update_scratchpad
Transient storage for agent state (expires after TTL)

```json
{
  "agent_id": "voicebot_v1",
  "key": "session:user_123",
  "content": "string content (max 100KB)",
  "mode": "overwrite|append",
  "ttl": 60-86400
}
```

**Response**: `{success, agent_id, key, ttl, content_size, message}`

---

### POST /tools/get_agent_state
Retrieve agent state from Redis

```json
{
  "agent_id": "voicebot_v1",
  "key": "optional_specific_key",
  "prefix": "scratchpad|state"
}
```

**Response**: `{success, data: {key1: value1, key2: value2}, keys: ["key1", "key2"], agent_id, message}`

---

## Complete Integration Example

```python
from datetime import datetime
from typing import Optional, Dict, List
import requests
import json

class VoiceBotMemory:
    def __init__(self, user_id: str, veris_url: str = "http://localhost:8000"):
        self.user_id = user_id
        self.namespace = f"voicebot_telegram_{user_id}"
        self.agent_id = "voicebot_v1"
        self.veris_url = veris_url
        self.session = requests.Session()
    
    def store_fact(self, attribute: str, value: str, confidence: float = 1.0):
        """Store user fact"""
        response = self.session.post(
            f"{self.veris_url}/tools/update_scratchpad",
            json={
                "agent_id": self.agent_id,
                "key": f"fact:{attribute}",
                "content": json.dumps({
                    "user_id": self.user_id,
                    "namespace": self.namespace,
                    "value": value,
                    "confidence": confidence,
                    "updated_at": datetime.utcnow().isoformat()
                }),
                "mode": "overwrite",
                "ttl": 2592000
            }
        )
        return response.json()["success"]
    
    def retrieve_context(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for relevant context"""
        response = self.session.post(
            f"{self.veris_url}/tools/retrieve_context",
            json={
                "query": query,
                "search_mode": "hybrid",
                "limit": limit,
                "filters": {"namespaces": [self.namespace]}
            }
        )
        return response.json()["results"]
    
    def log_message(self, role: str, content: str):
        """Log a message in conversation"""
        session_state = self.get_session()
        messages = session_state.get("messages", [])
        messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.update_session({
            **session_state,
            "messages": messages,
            "turn_count": session_state.get("turn_count", 0) + 1
        })
    
    def get_session(self) -> Dict:
        """Get session state"""
        response = self.session.post(
            f"{self.veris_url}/tools/get_agent_state",
            json={
                "agent_id": self.agent_id,
                "key": f"session:{self.user_id}",
                "prefix": "scratchpad"
            }
        )
        data = response.json().get("data", {})
        key = f"session:{self.user_id}"
        if key in data:
            return json.loads(data[key]) if isinstance(data[key], str) else data[key]
        return {}
    
    def update_session(self, state_dict: Dict):
        """Update session state"""
        self.session.post(
            f"{self.veris_url}/tools/update_scratchpad",
            json={
                "agent_id": self.agent_id,
                "key": f"session:{self.user_id}",
                "content": json.dumps(state_dict),
                "mode": "overwrite",
                "ttl": 3600
            }
        )

# Usage
memory = VoiceBotMemory(user_id="telegram_123456789")

# On conversation start
memory.store_fact("name", "Alice")
memory.store_fact("language", "English")

# During conversation
memory.log_message("user", "What's the weather?")
context = memory.retrieve_context("weather forecast")
print(f"Found {len(context)} relevant contexts")

memory.log_message("assistant", "It's sunny today")

# Get conversation history
session = memory.get_session()
print(f"Conversation turn {session['turn_count']}")
for msg in session['messages']:
    print(f"{msg['role']}: {msg['content']}")
```

---

## Docker Network Configuration

### If voice-bot runs in Docker

Add to your docker-compose.yml:

```yaml
voice-bot:
  build: .
  environment:
    - VERIS_URL=http://context-store:8000  # Note: use service name
    - REDIS_URL=redis://redis:6379
  networks:
    - context-store-network
  depends_on:
    - context-store

networks:
  context-store-network:
    external: true  # Use existing Veris network
```

Then run:
```bash
# In veris-memory directory
docker-compose up -d

# In voice-bot directory
docker-compose up --network context-store-network -d
```

---

## Health Checks

### Check if Veris Memory is ready

```python
def check_veris_health():
    try:
        response = requests.get(f"{VERIS_URL}/status", timeout=5)
        data = response.json()
        return {
            "ready": data.get("agent_ready", False),
            "tools_available": len(data.get("tools", [])),
            "dependencies": data.get("deps", {})
        }
    except Exception as e:
        return {"ready": False, "error": str(e)}

# Usage
health = check_veris_health()
if health["ready"]:
    print("Veris Memory is ready!")
else:
    print(f"Veris Memory not ready: {health}")
```

---

## Troubleshooting

### Connection refused
```python
# Check if Veris is running
curl http://localhost:8000/health

# If Docker: check service name
curl http://context-store:8000/health
```

### Facts not found
- Verify namespace matches: `voicebot_telegram_{user_id}`
- Check search_mode is "hybrid" or "kv"
- Use `/tools/get_agent_state` to verify fact storage

### Performance issues
- Check backend_timings in retrieve_context response
- Consider limiting search to kv mode for fast lookup
- Use smaller limit (5 instead of 100)

### Redis connection errors
- Verify REDIS_URL environment variable
- Check Redis service is healthy: `redis-cli ping`
- For Docker: ensure same network

