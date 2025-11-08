#!/usr/bin/env python3
"""Test Sentinel startup to diagnose container restart issue."""

import os
import sys
import asyncio

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set minimal required environment variables
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test_chat")
os.environ.setdefault("SENTINEL_CHECK_INTERVAL", "60")
os.environ.setdefault("TARGET_BASE_URL", "http://localhost:8000")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test_password")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

try:
    print("Testing Sentinel imports...")
    from src.monitoring.sentinel.runner import SentinelRunner
    from src.monitoring.sentinel.models import SentinelConfig
    print("✅ Imports successful")
    
    print("\nTesting config creation...")
    config = SentinelConfig.from_env()
    print(f"✅ Config created: check_interval_seconds={config.check_interval_seconds}, target_base_url={config.target_base_url}")
    
    print("\nTesting runner initialization...")
    runner = SentinelRunner(config)
    print("✅ Runner initialized")
    
    print("\n✅ All startup checks passed!")
    
except Exception as e:
    print(f"\n❌ Startup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)