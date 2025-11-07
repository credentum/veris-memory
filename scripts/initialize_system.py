#!/usr/bin/env python3
"""
Phase 2: Initialize veris-memory with seed data and verify all components.

This script:
1. Seeds initial data into the system
2. Verifies embeddings are working
3. Tests all storage backends
4. Reports system health
"""

import asyncio
import aiohttp
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
API_URL = os.getenv("CONTEXT_STORE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY_MCP", "")

if not API_KEY:
    logger.error("API_KEY_MCP environment variable not set!")
    logger.error("Please set: export API_KEY_MCP=<your-key-from-env-file>")
    sys.exit(1)


class SystemInitializer:
    """Initialize and verify veris-memory system."""

    def __init__(self):
        self.api_url = API_URL
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        self.stats = {
            "contexts_stored": 0,
            "contexts_retrieved": 0,
            "embeddings_successful": 0,
            "embeddings_failed": 0,
            "graph_nodes_created": 0
        }

    async def check_health(self, session: aiohttp.ClientSession) -> bool:
        """Check if the system is healthy."""
        try:
            async with session.get(f"{self.api_url}/health/detailed") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"System health: {data.get('status', 'unknown')}")

                    # Check service health
                    services = data.get('services', {})
                    for service, status in services.items():
                        logger.info(f"  {service}: {status}")

                    # Check embedding pipeline
                    embedding = data.get('embedding_pipeline', {})
                    if embedding.get('test_embedding_successful'):
                        logger.info("  ✓ Embeddings working")
                        return True
                    else:
                        logger.warning(f"  ✗ Embeddings not working: {embedding.get('error')}")
                        return True  # Continue even if embeddings fail
                else:
                    logger.error(f"Health check failed: HTTP {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

    def get_seed_data(self) -> List[Dict[str, Any]]:
        """Get initial seed data for the system."""
        return [
            # System initialization marker
            {
                "type": "log",
                "content": {
                    "title": "System Initialization",
                    "event": "Phase 2 - Data seeding started",
                    "timestamp": datetime.utcnow().isoformat(),
                    "initializer": "initialize_system.py"
                },
                "metadata": {"phase": "2", "system": "true"},
                "author": "system_initializer",
                "author_type": "agent"
            },

            # Architecture documentation
            {
                "type": "design",
                "content": {
                    "title": "Veris Memory Architecture",
                    "description": "Multi-database context storage with MCP interface",
                    "components": {
                        "vector_store": "Qdrant for semantic search",
                        "graph_store": "Neo4j for relationships",
                        "cache": "Redis for fast access",
                        "api": "FastAPI with MCP tools"
                    },
                    "version": "1.0.0"
                },
                "metadata": {"component": "architecture", "priority": "high"},
                "author": "architect",
                "author_type": "agent"
            },

            # Sprint 13 decision
            {
                "type": "decision",
                "content": {
                    "title": "Sprint 13: API Key Authentication",
                    "decision": "Implement API key-based authentication for all services",
                    "rationale": "Security requirement for production deployment",
                    "implementation": "X-API-Key header with vmk_ prefixed keys",
                    "status": "implemented"
                },
                "metadata": {"sprint": "13", "security": "authentication"},
                "author": "security_team",
                "author_type": "human"
            },

            # Golden fact for S2 testing
            {
                "type": "trace",
                "content": {
                    "title": "Golden Fact: System Name",
                    "fact": "This system is called Veris Memory",
                    "purpose": "Used for S2 golden fact recall testing",
                    "query_variations": ["What is this system?", "System name?", "What's this called?"]
                },
                "metadata": {"test": "s2_golden_fact", "sentinel": "true"},
                "author": "test_framework",
                "author_type": "agent"
            },

            # Operational knowledge
            {
                "type": "log",
                "content": {
                    "title": "Backup System Status",
                    "observation": "Backup system functional but backing up uninitialized state",
                    "action": "Initialize data before relying on backups",
                    "date": "2025-11-07"
                },
                "metadata": {"operational": "true", "priority": "high"},
                "author": "ops_team",
                "author_type": "human"
            },

            # Configuration reference
            {
                "type": "design",
                "content": {
                    "title": "Service Configuration",
                    "services": {
                        "context-store": "Port 8000, MCP interface",
                        "api": "Port 8001, REST interface",
                        "monitoring": "Port 8080, Dashboard",
                        "sentinel": "Port 9090, Health checks",
                        "qdrant": "Port 6333, Vector DB",
                        "neo4j": "Port 7474/7687, Graph DB",
                        "redis": "Port 6379, Cache"
                    }
                },
                "metadata": {"config": "services", "reference": "true"},
                "author": "devops",
                "author_type": "human"
            }
        ]

    async def store_context(
        self,
        session: aiohttp.ClientSession,
        context: Dict[str, Any]
    ) -> bool:
        """Store a single context."""
        try:
            async with session.post(
                f"{self.api_url}/tools/store_context",
                json=context,
                headers=self.headers
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()

                    # Track statistics
                    if result.get("success"):
                        self.stats["contexts_stored"] += 1

                        # Check embedding status
                        embedding_status = result.get("embedding_status", "unknown")
                        if embedding_status == "completed":
                            self.stats["embeddings_successful"] += 1
                        elif embedding_status == "failed":
                            self.stats["embeddings_failed"] += 1
                            logger.warning(f"  ⚠ Embedding failed: {result.get('embedding_message')}")

                        # Track relationships
                        relationships = result.get("relationships_created", 0)
                        if relationships > 0:
                            self.stats["graph_nodes_created"] += relationships

                        logger.info(f"  ✓ Stored: {context['content']['title']}")
                        return True
                    else:
                        logger.error(f"  ✗ Failed to store: {result.get('message')}")
                        return False
                else:
                    logger.error(f"  ✗ Store failed: HTTP {resp.status}")
                    text = await resp.text()
                    logger.error(f"    Response: {text}")
                    return False
        except Exception as e:
            logger.error(f"  ✗ Store error: {e}")
            return False

    async def verify_retrieval(
        self,
        session: aiohttp.ClientSession,
        query: str
    ) -> int:
        """Verify contexts can be retrieved."""
        try:
            payload = {
                "query": query,
                "limit": 10
            }

            async with session.post(
                f"{self.api_url}/tools/retrieve_context",
                json=payload,
                headers=self.headers
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        count = result.get("total_count", 0)
                        self.stats["contexts_retrieved"] = count

                        # Check search mode
                        mode = result.get("search_mode_used", "unknown")
                        logger.info(f"  Search mode: {mode}")

                        # Display some results
                        results = result.get("results", [])
                        for r in results[:3]:
                            content = r.get("content", {})
                            title = content.get("title", "Unknown")
                            score = r.get("score", 0)
                            source = r.get("source", "unknown")
                            logger.info(f"    - {title} (score: {score:.2f}, source: {source})")

                        return count
                    else:
                        logger.error(f"  Retrieval failed: {result.get('message')}")
                        return 0
                else:
                    logger.error(f"  Retrieval failed: HTTP {resp.status}")
                    return 0
        except Exception as e:
            logger.error(f"  Retrieval error: {e}")
            return 0

    async def run(self):
        """Run the complete initialization process."""
        logger.info("=" * 60)
        logger.info("PHASE 2: DATA INITIALIZATION")
        logger.info("=" * 60)

        async with aiohttp.ClientSession() as session:
            # Step 1: Check system health
            logger.info("\nStep 1: Checking system health...")
            if not await self.check_health(session):
                logger.error("System not healthy. Please ensure services are running.")
                return False

            # Step 2: Store seed data
            logger.info("\nStep 2: Storing seed data...")
            seed_data = self.get_seed_data()

            for i, context in enumerate(seed_data, 1):
                logger.info(f"\n[{i}/{len(seed_data)}] Storing context...")
                await self.store_context(session, context)

            # Step 3: Verify retrieval
            logger.info("\nStep 3: Verifying data retrieval...")

            test_queries = [
                ("system", "General system query"),
                ("Sprint 13", "Sprint-specific query"),
                ("authentication", "Security-related query"),
                ("Veris Memory", "Exact name match")
            ]

            for query, description in test_queries:
                logger.info(f"\nTesting: {description}")
                count = await self.verify_retrieval(session, query)
                logger.info(f"  Found {count} results for '{query}'")

            # Step 4: Report statistics
            logger.info("\n" + "=" * 60)
            logger.info("INITIALIZATION COMPLETE")
            logger.info("=" * 60)
            logger.info("\nStatistics:")
            logger.info(f"  Contexts stored: {self.stats['contexts_stored']}")
            logger.info(f"  Contexts retrieved: {self.stats['contexts_retrieved']}")
            logger.info(f"  Embeddings successful: {self.stats['embeddings_successful']}")
            logger.info(f"  Embeddings failed: {self.stats['embeddings_failed']}")
            logger.info(f"  Graph relationships: {self.stats['graph_nodes_created']}")

            # Determine overall status
            if self.stats['contexts_stored'] > 0:
                if self.stats['embeddings_successful'] > 0:
                    logger.info("\n✅ System fully operational with embeddings")
                elif self.stats['contexts_retrieved'] > 0:
                    logger.info("\n⚠️  System operational but embeddings not working")
                    logger.info("    (Using graph-only search fallback)")
                else:
                    logger.info("\n⚠️  Data stored but retrieval issues detected")
            else:
                logger.error("\n❌ Initialization failed - no data stored")
                return False

            return True


async def main():
    """Main entry point."""
    initializer = SystemInitializer()
    success = await initializer.run()

    if success:
        logger.info("\n✓ Phase 2 complete. Proceed to Phase 3 verification.")
        sys.exit(0)
    else:
        logger.error("\n✗ Phase 2 failed. Check logs and retry.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())