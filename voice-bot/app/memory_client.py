"""
MCP Memory Client for Voice Bot
Integrates with veris-memory MCP server for fact storage and retrieval

Sprint 13 Integration:
- API key authentication support
- Retry logic with exponential backoff
- Enhanced error handling for 401/embedding failures
- Support for author attribution and relationship detection
"""
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)


# Custom Exceptions
class MCPAuthenticationError(Exception):
    """Raised when MCP server returns 401 Unauthorized"""
    pass


class MCPConnectionError(Exception):
    """Raised when connection to MCP server fails"""
    pass


class MCPEmbeddingError(Exception):
    """Raised when embedding generation fails (warning, not critical)"""
    pass


class MemoryClient:
    """Client for interacting with MCP memory server"""

    def __init__(
        self,
        mcp_url: str,
        api_key: Optional[str] = None,
        author_prefix: str = "voice_bot",
        enable_retry: bool = True,
        retry_attempts: int = 3
    ):
        self.mcp_url = mcp_url.rstrip('/')
        self.api_key = api_key
        self.author_prefix = author_prefix
        self.enable_retry = enable_retry
        self.retry_attempts = retry_attempts
        self.client = httpx.AsyncClient(timeout=10.0)

    def _get_headers(self) -> Dict[str, str]:
        """Generate HTTP headers including API key if configured"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _retry_request(self, method: str, url: str, **kwargs):
        """
        Execute HTTP request with retry logic and exponential backoff

        Learned from veris-memory PR #3: Retry improves reliability from 98% error rate to <5%
        """
        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.request(method, url, **kwargs)

                # Handle authentication errors (don't retry)
                if response.status_code == 401:
                    raise MCPAuthenticationError(
                        f"Authentication failed. Check MCP_API_KEY configuration. "
                        f"Response: {response.text}"
                    )

                # Return successful or client error responses (don't retry client errors)
                if response.status_code < 500:
                    return response

                # Server errors: retry
                last_error = f"Server error {response.status_code}: {response.text}"
                logger.warning(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {last_error}")

            except httpx.RequestError as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/{self.retry_attempts} failed: {last_error}")

            # Exponential backoff (don't sleep on last attempt)
            if attempt < self.retry_attempts - 1:
                backoff = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(backoff)

        # All retries failed
        raise MCPConnectionError(f"Failed after {self.retry_attempts} attempts: {last_error}")

    async def initialize(self):
        """Initialize connection to MCP server"""
        try:
            response = await self._retry_request(
                "GET",
                f"{self.mcp_url}/health",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                logger.info("✅ Connected to MCP server")
                return True
        except MCPAuthenticationError as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to MCP server: {e}")
            return False

    async def store_fact(self, user_id: str, key: str, value: Any) -> bool:
        """
        Store a fact about a user
        Uses namespace pattern: voicebot_{user_id}
        Type: 'log' is used for fact storage (allowed types: design, decision, trace, sprint, log)

        Sprint 13: Adds author attribution and logs embedding status
        """
        namespace = f"voicebot_{user_id}"

        # Use correct MCP endpoint format (not wrapped in call_tool)
        payload = {
            "type": "log",  # Changed from 'fact' to allowed type 'log'
            "content": {
                "namespace": namespace,
                "user_id": user_id,
                "key": key,
                "value": value,
                "timestamp": datetime.utcnow().isoformat()
            },
            "metadata": {
                "source": "voice_input",
                "fact_key": f"{namespace}:{key}",
                "fact_type": "user_attribute"
            },
            # Sprint 13: Author attribution
            "author": f"{self.author_prefix}_{user_id}",
            "author_type": "agent"
        }

        try:
            # Use direct tool endpoint with retry logic
            response = await self._retry_request(
                "POST",
                f"{self.mcp_url}/tools/store_context",
                json=payload,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                result = response.json()

                # Sprint 13: Log embedding status
                embedding_status = result.get("embedding_status", "unknown")
                if embedding_status == "failed":
                    logger.warning(
                        f"⚠️ Embedding failed for fact {user_id}:{key} - "
                        f"{result.get('embedding_message', 'No details')}"
                    )
                elif embedding_status == "unavailable":
                    logger.warning(
                        f"⚠️ Embedding unavailable for fact {user_id}:{key} - "
                        f"semantic search will not work"
                    )

                # Log relationship creation (if any)
                if "relationships_created" in result:
                    logger.debug(
                        f"📊 Created {result['relationships_created']} relationships for {user_id}:{key}"
                    )

                logger.info(f"✅ Stored fact: {user_id}:{key} = {value} (embedding: {embedding_status})")
                return True
            else:
                logger.error(f"Failed to store fact: {response.text}")
                return False

        except MCPAuthenticationError as e:
            logger.error(f"❌ Authentication error storing fact: {e}")
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
        """Direct key lookup using retrieve_context (Sprint 13: with auth headers)"""
        fact_key = f"{namespace}:{key}"

        # Use correct MCP endpoint format (not wrapped in call_tool)
        payload = {
            "query": fact_key,
            "type": "log",  # Search for log type (where we store facts)
            "search_mode": "hybrid",
            "limit": 1,
            "filters": {
                "metadata.fact_key": f"voicebot_{user_id}:{key}",
                "content.user_id": user_id,
                "content.key": key
            }
        }

        try:
            # Use retry request with auth headers
            response = await self._retry_request(
                "POST",
                f"{self.mcp_url}/tools/retrieve_context",
                json=payload,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    return result["results"][0]["content"].get("value")

        except MCPAuthenticationError as e:
            logger.error(f"❌ Authentication error retrieving fact: {e}")
        except Exception as e:
            logger.error(f"Error retrieving fact by key: {e}")

        return None

    async def _semantic_fact_search(self, namespace: str, user_id: str, limit: int = 5) -> Dict[str, Any]:
        """Semantic search fallback for facts (Sprint 13: with auth headers)"""
        # Use correct MCP endpoint format (not wrapped in call_tool)
        payload = {
            "query": f"user facts for {user_id}",
            "type": "log",  # Search for log type (where we store facts)
            "search_mode": "hybrid",
            "limit": limit,
            "filters": {
                "content.user_id": user_id,
                "metadata.fact_type": "user_attribute"
            }
        }

        facts = {}
        try:
            # Use retry request with auth headers
            response = await self._retry_request(
                "POST",
                f"{self.mcp_url}/tools/retrieve_context",
                json=payload,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                result = response.json()
                for item in result.get("results", []):
                    content = item.get("content", {})
                    if "key" in content and "value" in content:
                        facts[content["key"]] = content["value"]

        except MCPAuthenticationError as e:
            logger.error(f"❌ Authentication error in semantic search: {e}")
        except Exception as e:
            logger.error(f"Error in semantic fact search: {e}")

        return facts

    async def store_conversation_trace(self, user_id: str, messages: List[Dict]) -> bool:
        """
        Store conversation history for analysis (not for fact retrieval)
        Sprint 13: Adds author attribution and retry logic
        """
        namespace = f"voicebot_{user_id}"

        # Use correct MCP endpoint format (not wrapped in call_tool)
        payload = {
            "type": "trace",  # Correct type for conversation traces
            "content": {
                "namespace": namespace,
                "user_id": user_id,
                "messages": messages,
                "timestamp": datetime.utcnow().isoformat()
            },
            "metadata": {
                "source": "voice_conversation",
                "message_count": len(messages)
            },
            # Sprint 13: Author attribution
            "author": f"{self.author_prefix}_{user_id}",
            "author_type": "agent"
        }

        try:
            # Use retry request with auth headers
            response = await self._retry_request(
                "POST",
                f"{self.mcp_url}/tools/store_context",
                json=payload,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                result = response.json()
                embedding_status = result.get("embedding_status", "unknown")
                logger.info(
                    f"✅ Stored conversation trace for {user_id} "
                    f"({len(messages)} messages, embedding: {embedding_status})"
                )
                return True
            else:
                logger.error(f"Failed to store conversation trace: {response.text}")
                return False

        except MCPAuthenticationError as e:
            logger.error(f"❌ Authentication error storing trace: {e}")
            return False
        except Exception as e:
            logger.error(f"Error storing conversation trace: {e}")
            return False

    async def check_health(self) -> bool:
        """Check MCP server health (Sprint 13: with auth headers)"""
        try:
            response = await self._retry_request(
                "GET",
                f"{self.mcp_url}/health",
                headers=self._get_headers()
            )
            return response.status_code == 200
        except:
            return False

    async def get_detailed_health(self) -> Dict[str, Any]:
        """
        Get detailed health status including Sprint 13 embedding pipeline info

        Returns:
            {
                "mcp_server": "healthy" | "unhealthy",
                "embedding_pipeline": {...},  # Sprint 13 info
                "services": {...}
            }
        """
        health_data = {
            "mcp_server": "unhealthy",
            "embedding_pipeline": None,
            "services": {}
        }

        try:
            response = await self._retry_request(
                "GET",
                f"{self.mcp_url}/health/detailed",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                result = response.json()
                health_data["mcp_server"] = result.get("status", "unknown")
                health_data["embedding_pipeline"] = result.get("embedding_pipeline", {})
                health_data["services"] = result.get("services", {})

                # Log warnings if embedding pipeline is degraded
                embedding_status = health_data["services"].get("embeddings", "unknown")
                if embedding_status in ["unhealthy", "degraded"]:
                    logger.warning(
                        f"⚠️ Embedding pipeline is {embedding_status} - "
                        f"semantic search may not work properly"
                    )

        except MCPAuthenticationError as e:
            logger.error(f"❌ Authentication error checking health: {e}")
        except Exception as e:
            logger.error(f"Error checking detailed health: {e}")

        return health_data

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
