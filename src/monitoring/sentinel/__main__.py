#!/usr/bin/env python3
"""
Sentinel Monitoring Service Entry Point

Run the Sentinel monitoring system as a standalone service.
"""

import asyncio
import os
import sys
import argparse
import logging

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.monitoring.sentinel.runner import SentinelRunner
from src.monitoring.sentinel.models import SentinelConfig


def setup_logging():
    """Configure logging for Sentinel."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


async def main():
    """Main entry point for Sentinel monitoring service."""
    parser = argparse.ArgumentParser(description="Veris Sentinel Monitoring Service")
    parser.add_argument("--standalone", action="store_true", help="Run in standalone mode")
    parser.add_argument("--api-port", type=int, default=9090, help="API server port")
    parser.add_argument("--no-api", action="store_true", help="Disable API server")
    
    args = parser.parse_args()
    
    logger = setup_logging()
    logger.info("🚀 Starting Veris Sentinel Monitoring Service")
    
    # Create configuration from environment
    config = SentinelConfig.from_env()
    
    # Create and start runner
    runner = SentinelRunner(config)
    
    try:
        # Start API server if not disabled
        if not args.no_api:
            api_task = asyncio.create_task(runner.start_api_server(port=args.api_port))
            logger.info(f"✅ API server started on port {args.api_port}")
        
        # Start monitoring
        logger.info("✅ Starting monitoring checks")
        await runner.start_monitoring()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Received shutdown signal")
    except Exception as e:
        logger.error(f"❌ Sentinel failed: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Sentinel shutting down")


if __name__ == "__main__":
    asyncio.run(main())