"""Configuration for Voice Bot Service"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Voice Bot Service Configuration"""

    # Service Config
    SERVICE_NAME: str = "voice-bot"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    LOG_LEVEL: str = "info"

    # LiveKit Config
    LIVEKIT_URL: str = "ws://livekit:7880"
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    # MCP Server Config (uses existing context-store)
    MCP_SERVER_URL: str = "http://context-store:8000"
    MCP_API_KEY: Optional[str] = None

    # Redis Config (for session state)
    REDIS_URL: str = "redis://redis:6379"

    # Voice Processing
    STT_PROVIDER: str = "deepgram"  # deepgram, whisper, google
    TTS_PROVIDER: str = "elevenlabs"  # elevenlabs, google, azure
    STT_API_KEY: Optional[str] = None
    TTS_API_KEY: Optional[str] = None

    # Feature Flags
    ENABLE_VOICE_COMMANDS: bool = True
    ENABLE_FACT_STORAGE: bool = True
    ENABLE_CONVERSATION_TRACE: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
