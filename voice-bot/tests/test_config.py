"""
Tests for Voice Bot Configuration
Tests Sprint 13 configuration options
"""
import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSettingsDefaults:
    """Test default configuration values"""

    def test_default_values(self):
        """Test that defaults are set correctly"""
        # Create settings with minimal required fields
        settings = Settings(
            LIVEKIT_API_KEY="test_key",
            LIVEKIT_API_SECRET="test_secret"
        )

        # Service defaults
        assert settings.SERVICE_NAME == "voice-bot"
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8002
        assert settings.LOG_LEVEL == "info"

        # LiveKit defaults
        assert settings.LIVEKIT_URL == "ws://livekit:7880"

        # MCP defaults
        assert settings.MCP_SERVER_URL == "http://context-store:8000"
        assert settings.MCP_API_KEY is None

        # Sprint 13 defaults
        assert settings.VOICE_BOT_AUTHOR_PREFIX == "voice_bot"
        assert settings.ENABLE_MCP_RETRY is True
        assert settings.MCP_RETRY_ATTEMPTS == 3

        # Redis defaults
        assert settings.REDIS_URL == "redis://redis:6379"

        # Voice processing defaults
        assert settings.STT_PROVIDER == "deepgram"
        assert settings.TTS_PROVIDER == "elevenlabs"

        # Feature flags
        assert settings.ENABLE_VOICE_COMMANDS is True
        assert settings.ENABLE_FACT_STORAGE is True
        assert settings.ENABLE_CONVERSATION_TRACE is True


class TestRequiredFields:
    """Test required configuration fields"""

    def test_required_livekit_api_key(self, monkeypatch):
        """Test that LIVEKIT_API_KEY is required"""
        # Temporarily remove environment variable
        monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings(LIVEKIT_API_SECRET="secret")

        assert "LIVEKIT_API_KEY" in str(exc_info.value)

    def test_required_livekit_api_secret(self, monkeypatch):
        """Test that LIVEKIT_API_SECRET is required"""
        # Temporarily remove environment variable
        monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings(LIVEKIT_API_KEY="key")

        assert "LIVEKIT_API_SECRET" in str(exc_info.value)


class TestSprint13Configuration:
    """Test Sprint 13 specific configuration"""

    def test_mcp_api_key_optional(self):
        """Test that MCP_API_KEY is optional"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret"
        )

        assert settings.MCP_API_KEY is None

    def test_mcp_api_key_set(self):
        """Test MCP_API_KEY can be set"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            MCP_API_KEY="vmk_test_key"
        )

        assert settings.MCP_API_KEY == "vmk_test_key"

    def test_author_prefix_custom(self):
        """Test custom author prefix"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            VOICE_BOT_AUTHOR_PREFIX="custom_bot"
        )

        assert settings.VOICE_BOT_AUTHOR_PREFIX == "custom_bot"

    def test_retry_configuration(self):
        """Test retry configuration options"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            ENABLE_MCP_RETRY=False,
            MCP_RETRY_ATTEMPTS=5
        )

        assert settings.ENABLE_MCP_RETRY is False
        assert settings.MCP_RETRY_ATTEMPTS == 5


class TestServiceConfiguration:
    """Test service configuration options"""

    def test_custom_service_name(self):
        """Test custom service name"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            SERVICE_NAME="custom-voice-bot"
        )

        assert settings.SERVICE_NAME == "custom-voice-bot"

    def test_custom_port(self):
        """Test custom port configuration"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            PORT=9000
        )

        assert settings.PORT == 9000

    def test_custom_log_level(self):
        """Test custom log level"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            LOG_LEVEL="debug"
        )

        assert settings.LOG_LEVEL == "debug"


class TestLiveKitConfiguration:
    """Test LiveKit configuration"""

    def test_custom_livekit_url(self):
        """Test custom LiveKit URL"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            LIVEKIT_URL="wss://custom-livekit:7880"
        )

        assert settings.LIVEKIT_URL == "wss://custom-livekit:7880"

    def test_livekit_credentials(self):
        """Test LiveKit credentials are stored"""
        settings = Settings(
            LIVEKIT_API_KEY="test_api_key_123",
            LIVEKIT_API_SECRET="test_secret_456"
        )

        assert settings.LIVEKIT_API_KEY == "test_api_key_123"
        assert settings.LIVEKIT_API_SECRET == "test_secret_456"


class TestMCPConfiguration:
    """Test MCP server configuration"""

    def test_custom_mcp_url(self):
        """Test custom MCP server URL"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            MCP_SERVER_URL="http://custom-mcp:9000"
        )

        assert settings.MCP_SERVER_URL == "http://custom-mcp:9000"

    def test_mcp_server_url_default(self):
        """Test default MCP server URL"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret"
        )

        assert settings.MCP_SERVER_URL == "http://context-store:8000"


class TestRedisConfiguration:
    """Test Redis configuration"""

    def test_custom_redis_url(self):
        """Test custom Redis URL"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            REDIS_URL="redis://custom-redis:6380"
        )

        assert settings.REDIS_URL == "redis://custom-redis:6380"


class TestVoiceProviderConfiguration:
    """Test STT/TTS provider configuration"""

    def test_custom_stt_provider(self):
        """Test custom STT provider"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            STT_PROVIDER="whisper"
        )

        assert settings.STT_PROVIDER == "whisper"

    def test_custom_tts_provider(self):
        """Test custom TTS provider"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            TTS_PROVIDER="google"
        )

        assert settings.TTS_PROVIDER == "google"

    def test_voice_api_keys(self):
        """Test voice API keys can be set"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            STT_API_KEY="stt_key_123",
            TTS_API_KEY="tts_key_456"
        )

        assert settings.STT_API_KEY == "stt_key_123"
        assert settings.TTS_API_KEY == "tts_key_456"

    def test_voice_api_keys_optional(self):
        """Test voice API keys are optional"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret"
        )

        assert settings.STT_API_KEY is None
        assert settings.TTS_API_KEY is None


class TestFeatureFlags:
    """Test feature flag configuration"""

    def test_disable_voice_commands(self):
        """Test disabling voice commands"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            ENABLE_VOICE_COMMANDS=False
        )

        assert settings.ENABLE_VOICE_COMMANDS is False

    def test_disable_fact_storage(self):
        """Test disabling fact storage"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            ENABLE_FACT_STORAGE=False
        )

        assert settings.ENABLE_FACT_STORAGE is False

    def test_disable_conversation_trace(self):
        """Test disabling conversation trace"""
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            ENABLE_CONVERSATION_TRACE=False
        )

        assert settings.ENABLE_CONVERSATION_TRACE is False


class TestEnvironmentLoading:
    """Test environment variable loading"""

    def test_settings_from_env(self, monkeypatch):
        """Test settings are loaded from environment"""
        monkeypatch.setenv("LIVEKIT_API_KEY", "env_key")
        monkeypatch.setenv("LIVEKIT_API_SECRET", "env_secret")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "debug")

        settings = Settings()

        assert settings.LIVEKIT_API_KEY == "env_key"
        assert settings.LIVEKIT_API_SECRET == "env_secret"
        assert settings.PORT == 9000
        assert settings.LOG_LEVEL == "debug"

    def test_sprint13_env_vars(self, monkeypatch):
        """Test Sprint 13 environment variables"""
        monkeypatch.setenv("LIVEKIT_API_KEY", "key")
        monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
        monkeypatch.setenv("MCP_API_KEY", "vmk_env_key")
        monkeypatch.setenv("VOICE_BOT_AUTHOR_PREFIX", "env_bot")
        monkeypatch.setenv("ENABLE_MCP_RETRY", "false")
        monkeypatch.setenv("MCP_RETRY_ATTEMPTS", "5")

        settings = Settings()

        assert settings.MCP_API_KEY == "vmk_env_key"
        assert settings.VOICE_BOT_AUTHOR_PREFIX == "env_bot"
        assert settings.ENABLE_MCP_RETRY is False
        assert settings.MCP_RETRY_ATTEMPTS == 5


class TestConfigValidation:
    """Test configuration validation"""

    def test_port_must_be_int(self):
        """Test port must be an integer"""
        with pytest.raises(ValidationError):
            Settings(
                LIVEKIT_API_KEY="key",
                LIVEKIT_API_SECRET="secret",
                PORT="invalid"
            )

    def test_retry_attempts_must_be_int(self):
        """Test retry attempts must be an integer"""
        with pytest.raises(ValidationError):
            Settings(
                LIVEKIT_API_KEY="key",
                LIVEKIT_API_SECRET="secret",
                MCP_RETRY_ATTEMPTS="invalid"
            )

    def test_boolean_fields(self):
        """Test boolean field validation"""
        # Should accept string representations
        settings = Settings(
            LIVEKIT_API_KEY="key",
            LIVEKIT_API_SECRET="secret",
            ENABLE_MCP_RETRY="true"
        )

        assert settings.ENABLE_MCP_RETRY is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.config", "--cov-report=term-missing"])
