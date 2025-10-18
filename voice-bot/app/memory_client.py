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
            "method": "call_tool",
            "params": {
                "name": "store_context",
                "arguments": {
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
        """Direct key lookup using retrieve_context"""
        fact_key = f"facts:{namespace}:{user_id}:{key}"

        payload = {
            "method": "call_tool",
            "params": {
                "name": "retrieve_context",
                "arguments": {
                    "query": fact_key,
                    "namespaces": [namespace],
                    "limit": 1,
                    "filters": {
                        "metadata.fact_key": fact_key
                    }
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
            "method": "call_tool",
            "params": {
                "name": "retrieve_context",
                "arguments": {
                    "query": f"user facts for {user_id}",
                    "namespaces": [namespace],
                    "limit": limit,
                    "filters": {
                        "type": "fact",
                        "content.user_id": user_id
                    }
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
            "method": "call_tool",
            "params": {
                "name": "store_context",
                "arguments": {
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

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
