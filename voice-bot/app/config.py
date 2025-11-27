"""
VoiceBot Configuration

All environment variables, constants, and shared clients.
"""

import os
import uuid

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---- OpenAI Client ----
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ---- Veris Memory config ----
# Default to context-store for Docker network, can override for local dev
MEMORY_API_BASE = os.environ.get("MEMORY_API_BASE", "http://context-store:8000")

# API key naming convention (Option B - consistent naming):
#   API_KEY_MCP      - For Claude CLI and MCP clients
#   API_KEY_VOICEBOT - For VoiceBot (this app)
#   API_KEY_SENTINEL - For Sentinel monitoring
#
# Key format: key:user_id:role:is_agent (e.g., vmk_voicebot_xxx:voice_bot:writer:true)
# Only the key portion (before first colon) should be sent in the X-API-Key header
_API_KEY_RAW = os.environ.get("API_KEY_VOICEBOT") or os.environ.get("MEMORY_API_KEY")
VERIS_API_KEY = _API_KEY_RAW.split(":")[0] if _API_KEY_RAW else None

# Stable user ID for fact persistence across sessions
# Can be set explicitly via VOICE_USER_ID, or defaults to "matt"
USER_ID = os.environ.get("VOICE_USER_ID", "matt")

# Session ID for tracking individual conversation sessions (not used for filtering)
SESSION_ID = os.environ.get("VOICE_SESSION_ID", f"voice_{uuid.uuid4().hex[:8]}")

# Debug flag for verbose logging
DEBUG_MEMORY = os.environ.get("DEBUG_MEMORY") == "1"

# ---- Claude Agent config ----
# Map of repo shortcuts to paths - add your repos here
# Say "review X in voicebot" or "check the voicebot code" to target a specific repo
REPO_PATHS = {
    "voicebot": os.environ.get("REPO_VOICEBOT", "/opt/veris-memory/voice-bot"),
    "voice bot": os.environ.get("REPO_VOICEBOT", "/opt/veris-memory/voice-bot"),  # speech variation
    "veris": os.environ.get("REPO_VERIS", "/opt/veris-memory"),
    "veris-memory": os.environ.get("REPO_VERIS", "/opt/veris-memory"),
}

# Default repo when no specific repo is mentioned
DEFAULT_REPO = os.environ.get("DEFAULT_REPO_PATH", "/opt/veris-memory")

# Quick keyword check before LLM (saves API calls for obvious non-code questions)
CODE_HINT_WORDS = ["code", "repo", "file", "function", "bug", "error", "implement", "backend", "frontend"]

# ---- Memory filtering ----
# Default sources to exclude from retrieval (test/system noise)
DEFAULT_EXCLUDE_SOURCES = [
    "sentinel_monitor", "test", "voice_bot_test", "mcp_server",
    "pr339_verification", "test_pr339", "documentation", "devops",
    "index_test",
]

# ---- Session Chat History ----
# Short-term memory for conversation flow within a session
# This enables follow-up questions like "yes please" or "tell me more"
CHAT_HISTORY: list[dict] = []  # Stores {"role": "user/assistant", "content": "..."}
MAX_CHAT_HISTORY = 10  # Keep last N exchanges (user + assistant = 2 messages each)


# ---- Shared HTTP Headers ----
def mem_headers() -> dict:
    """Headers for Veris API requests - sends only the key portion"""
    return {"X-API-Key": VERIS_API_KEY, "Content-Type": "application/json"}
