"""
LiveKit Voice Handler for real-time voice interaction
"""
import asyncio
from typing import Optional, Dict, Any, List
from livekit import api
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Handles LiveKit voice interactions"""

    def __init__(self, livekit_url: str, api_key: str, api_secret: str, livekit_ws_url: Optional[str] = None):
        self.livekit_url = livekit_url  # Internal URL for backend API calls
        self.livekit_ws_url = livekit_ws_url or livekit_url  # Public URL for browser clients
        self.api_key = api_key
        self.api_secret = api_secret
        self.lk_api = None

    async def initialize(self):
        """Initialize LiveKit services"""
        try:
            # Convert WebSocket URL to HTTP for API
            http_url = self.livekit_url.replace("ws://", "http://").replace("wss://", "https://")

            # Initialize API client (livekit-api 1.0.7+)
            self.lk_api = api.LiveKitAPI(
                url=http_url,
                api_key=self.api_key,
                api_secret=self.api_secret
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
            await self.lk_api.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    max_participants=2,  # User + bot
                    empty_timeout=300  # 5 minutes
                )
            )

            # Generate token for user
            user_token = self.create_token(room_name, f"user_{user_id}")

            return {
                "room_name": room_name,
                "token": user_token,
                "url": self.livekit_ws_url,  # Public URL for browser clients
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating voice session: {e}")
            raise

    async def check_health(self) -> bool:
        """
        Check LiveKit server health

        Returns True if LiveKit server is reachable and responding.
        This is a simple connectivity check that doesn't depend on room state.
        """
        try:
            if not self.lk_api:
                logger.warning("LiveKit API not initialized")
                return False

            # List rooms as health check - works even with empty room list
            # This verifies connectivity to LiveKit server without depending on room state
            result = await self.lk_api.room.list_rooms(api.ListRoomsRequest())

            # If we got a response (even empty list), LiveKit is healthy
            logger.debug(f"LiveKit health check: {len(result.rooms)} active rooms")
            return True

        except Exception as e:
            logger.error(f"LiveKit health check failed: {e}")
            return False

    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active voice sessions"""
        try:
            if not self.lk_api:
                return []

            response = await self.lk_api.room.list_rooms(api.ListRoomsRequest())
            sessions = []

            for room in response.rooms:
                sessions.append({
                    "room_name": room.name,
                    "num_participants": room.num_participants,
                    "created_at": room.creation_time
                })

            return sessions

        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []

    async def end_session(self, room_name: str) -> bool:
        """End a voice session"""
        try:
            if not self.lk_api:
                return False

            await self.lk_api.room.delete_room(
                api.DeleteRoomRequest(room=room_name)
            )
            logger.info(f"Ended voice session: {room_name}")
            return True

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return False
