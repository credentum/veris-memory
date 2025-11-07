"""
Tests for LiveKit Voice Handler
Tests voice session management and LiveKit integration
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.voice_handler import VoiceHandler


@pytest.fixture
def voice_handler():
    """Create voice handler for testing"""
    return VoiceHandler(
        livekit_url="ws://test-livekit:7880",
        api_key="test_api_key",
        api_secret="test_api_secret"
    )


class TestVoiceHandlerInit:
    """Test voice handler initialization"""

    def test_handler_initialization(self, voice_handler):
        """Test basic initialization"""
        assert voice_handler.livekit_url == "ws://test-livekit:7880"
        assert voice_handler.api_key == "test_api_key"
        assert voice_handler.api_secret == "test_api_secret"
        assert voice_handler.room_service is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, voice_handler):
        """Test successful initialization"""
        with patch('app.voice_handler.api.RoomService') as mock_room_service:
            result = await voice_handler.initialize()

            assert result is True
            assert voice_handler.room_service is not None
            # Should convert ws:// to http:// for API
            mock_room_service.assert_called_once_with(
                "http://test-livekit:7880",
                "test_api_key",
                "test_api_secret"
            )

    @pytest.mark.asyncio
    async def test_initialize_wss_to_https(self):
        """Test WSS to HTTPS conversion"""
        handler = VoiceHandler(
            livekit_url="wss://test-livekit:7880",
            api_key="key",
            api_secret="secret"
        )

        with patch('app.voice_handler.api.RoomService') as mock_room_service:
            await handler.initialize()

            # Should convert wss:// to https://
            mock_room_service.assert_called_once_with(
                "https://test-livekit:7880",
                "key",
                "secret"
            )

    @pytest.mark.asyncio
    async def test_initialize_failure(self, voice_handler):
        """Test initialization failure"""
        with patch('app.voice_handler.api.RoomService', side_effect=Exception("Connection failed")):
            result = await voice_handler.initialize()

            assert result is False


class TestTokenCreation:
    """Test JWT token creation for participants"""

    def test_create_token_structure(self, voice_handler):
        """Test token creation with correct structure"""
        with patch('app.voice_handler.api.AccessToken') as mock_token_class:
            mock_token = MagicMock()
            mock_token.to_jwt.return_value = "test_jwt_token"
            mock_token_class.return_value = mock_token

            token = voice_handler.create_token("test_room", "test_user")

            assert token == "test_jwt_token"

            # Verify token was configured correctly
            mock_token.with_identity.assert_called_once_with("test_user")
            mock_token.with_name.assert_called_once_with("test_user")
            mock_token.with_grants.assert_called_once()

    def test_create_token_grants(self, voice_handler):
        """Test token grants are configured correctly"""
        with patch('app.voice_handler.api.AccessToken') as mock_token_class:
            with patch('app.voice_handler.api.VideoGrants') as mock_grants:
                mock_token = MagicMock()
                mock_token_class.return_value = mock_token

                voice_handler.create_token("test_room", "test_user")

                # Verify grants were configured
                mock_grants.assert_called_once_with(
                    room_join=True,
                    room="test_room",
                    can_publish=True,
                    can_subscribe=True
                )


class TestVoiceSessionCreation:
    """Test voice session creation"""

    @pytest.mark.asyncio
    async def test_create_voice_session_success(self, voice_handler):
        """Test successful voice session creation"""
        mock_room_service = MagicMock()
        mock_room_service.create_room = AsyncMock()
        voice_handler.room_service = mock_room_service

        with patch.object(voice_handler, 'create_token', return_value="test_token"):
            with patch('app.voice_handler.datetime') as mock_datetime:
                mock_datetime.now.return_value.timestamp.return_value = 1234567890
                mock_datetime.utcnow.return_value.isoformat.return_value = "2025-01-01T00:00:00"

                session = await voice_handler.create_voice_session("test_user")

        assert session["room_name"] == "voice_test_user_1234567890"
        assert session["token"] == "test_token"
        assert session["url"] == "ws://test-livekit:7880"
        assert session["user_id"] == "test_user"
        assert session["created_at"] == "2025-01-01T00:00:00"

        # Verify room was created with correct parameters
        mock_room_service.create_room.assert_called_once()
        call_args = mock_room_service.create_room.call_args[0][0]
        assert call_args.name == "voice_test_user_1234567890"
        assert call_args.max_participants == 2
        assert call_args.empty_timeout == 300

    @pytest.mark.asyncio
    async def test_create_voice_session_failure(self, voice_handler):
        """Test voice session creation failure"""
        mock_room_service = MagicMock()
        mock_room_service.create_room = AsyncMock(side_effect=Exception("Room creation failed"))
        voice_handler.room_service = mock_room_service

        with pytest.raises(Exception) as exc_info:
            await voice_handler.create_voice_session("test_user")

        assert "Room creation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_voice_session_unique_names(self, voice_handler):
        """Test that each session gets a unique room name"""
        mock_room_service = MagicMock()
        mock_room_service.create_room = AsyncMock()
        voice_handler.room_service = mock_room_service

        with patch.object(voice_handler, 'create_token', return_value="token"):
            session1 = await voice_handler.create_voice_session("user1")
            session2 = await voice_handler.create_voice_session("user1")

        # Room names should be different due to timestamp
        assert session1["room_name"] != session2["room_name"]


class TestHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_check_health_success(self, voice_handler):
        """Test successful health check"""
        mock_room_service = MagicMock()
        mock_room_service.list_rooms = AsyncMock()
        voice_handler.room_service = mock_room_service

        result = await voice_handler.check_health()

        assert result is True
        mock_room_service.list_rooms.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_no_service(self, voice_handler):
        """Test health check when service not initialized"""
        voice_handler.room_service = None

        result = await voice_handler.check_health()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_health_failure(self, voice_handler):
        """Test health check with service failure"""
        mock_room_service = MagicMock()
        mock_room_service.list_rooms = AsyncMock(side_effect=Exception("Connection error"))
        voice_handler.room_service = mock_room_service

        result = await voice_handler.check_health()

        assert result is False


class TestListActiveSessions:
    """Test listing active voice sessions"""

    @pytest.mark.asyncio
    async def test_list_active_sessions_success(self, voice_handler):
        """Test listing active sessions"""
        mock_room1 = MagicMock()
        mock_room1.name = "voice_user1_123"
        mock_room1.num_participants = 2
        mock_room1.creation_time = 1234567890

        mock_room2 = MagicMock()
        mock_room2.name = "voice_user2_456"
        mock_room2.num_participants = 1
        mock_room2.creation_time = 1234567891

        mock_response = MagicMock()
        mock_response.rooms = [mock_room1, mock_room2]

        mock_room_service = MagicMock()
        mock_room_service.list_rooms = AsyncMock(return_value=mock_response)
        voice_handler.room_service = mock_room_service

        sessions = await voice_handler.list_active_sessions()

        assert len(sessions) == 2
        assert sessions[0]["room_name"] == "voice_user1_123"
        assert sessions[0]["num_participants"] == 2
        assert sessions[1]["room_name"] == "voice_user2_456"

    @pytest.mark.asyncio
    async def test_list_active_sessions_empty(self, voice_handler):
        """Test listing sessions when none exist"""
        mock_response = MagicMock()
        mock_response.rooms = []

        mock_room_service = MagicMock()
        mock_room_service.list_rooms = AsyncMock(return_value=mock_response)
        voice_handler.room_service = mock_room_service

        sessions = await voice_handler.list_active_sessions()

        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_active_sessions_no_service(self, voice_handler):
        """Test listing sessions when service not initialized"""
        voice_handler.room_service = None

        sessions = await voice_handler.list_active_sessions()

        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_active_sessions_failure(self, voice_handler):
        """Test listing sessions with error"""
        mock_room_service = MagicMock()
        mock_room_service.list_rooms = AsyncMock(side_effect=Exception("API error"))
        voice_handler.room_service = mock_room_service

        sessions = await voice_handler.list_active_sessions()

        assert sessions == []


class TestEndSession:
    """Test ending voice sessions"""

    @pytest.mark.asyncio
    async def test_end_session_success(self, voice_handler):
        """Test successful session termination"""
        mock_room_service = MagicMock()
        mock_room_service.delete_room = AsyncMock()
        voice_handler.room_service = mock_room_service

        result = await voice_handler.end_session("voice_test_123")

        assert result is True
        mock_room_service.delete_room.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_session_no_service(self, voice_handler):
        """Test ending session when service not initialized"""
        voice_handler.room_service = None

        result = await voice_handler.end_session("voice_test_123")

        assert result is False

    @pytest.mark.asyncio
    async def test_end_session_failure(self, voice_handler):
        """Test ending session with error"""
        mock_room_service = MagicMock()
        mock_room_service.delete_room = AsyncMock(side_effect=Exception("Delete failed"))
        voice_handler.room_service = mock_room_service

        result = await voice_handler.end_session("voice_test_123")

        assert result is False


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_create_session_with_special_characters(self, voice_handler):
        """Test session creation with special characters in user_id"""
        mock_room_service = MagicMock()
        mock_room_service.create_room = AsyncMock()
        voice_handler.room_service = mock_room_service

        with patch.object(voice_handler, 'create_token', return_value="token"):
            session = await voice_handler.create_voice_session("user@test.com")

        # Should handle special characters in user_id
        assert "user@test.com" in session["room_name"]

    @pytest.mark.asyncio
    async def test_create_session_with_empty_user_id(self, voice_handler):
        """Test session creation with empty user_id"""
        mock_room_service = MagicMock()
        mock_room_service.create_room = AsyncMock()
        voice_handler.room_service = mock_room_service

        with patch.object(voice_handler, 'create_token', return_value="token"):
            session = await voice_handler.create_voice_session("")

        # Should still create a room (validation should happen at API level)
        assert session["room_name"].startswith("voice__")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.voice_handler", "--cov-report=term-missing"])
