#!/usr/bin/env python3
"""
Veris Sentinel Main Entry Point

Autonomous monitor/test/report agent for Veris Memory with:
- Continuous health monitoring
- Automated functional testing  
- Performance capacity testing
- Security validation
- Alerting and reporting
"""

import asyncio
import os
import sys
import signal
import logging
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.veris_sentinel import SentinelRunner, SentinelConfig, SentinelAPI


def setup_logging() -> None:
    """Configure logging for Sentinel."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure structured logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/var/lib/sentinel/sentinel.log')
        ]
    )
    
    # Suppress verbose HTTP client logs
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def load_config() -> SentinelConfig:
    """Load configuration from environment variables."""
    return SentinelConfig(
        target_base_url=os.getenv("TARGET_BASE_URL", "http://veris-memory-dev-context-store-1:8000"),
        redis_url=os.getenv("REDIS_URL", "redis://veris-memory-dev-redis-1:6379"),
        qdrant_url=os.getenv("QDRANT_URL", "http://veris-memory-dev-qdrant-1:6333"),
        neo4j_bolt=os.getenv("NEO4J_BOLT", "bolt://veris-memory-dev-neo4j-1:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "veris_ro"),
        schedule_cadence_sec=int(os.getenv("SCHEDULE_CADENCE_SEC", "60")),
        max_jitter_pct=int(os.getenv("MAX_JITTER_PCT", "20")),
        per_check_timeout_sec=int(os.getenv("PER_CHECK_TIMEOUT_SEC", "10")),
        cycle_budget_sec=int(os.getenv("CYCLE_BUDGET_SEC", "45")),
        max_parallel_checks=int(os.getenv("MAX_PARALLEL_CHECKS", "4")),
        alert_webhook=os.getenv("ALERT_WEBHOOK"),
        github_repo=os.getenv("GITHUB_REPO")
    )


async def main() -> None:
    """Main entry point for Veris Sentinel."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Veris Sentinel")
    
    # Load configuration
    config = load_config()
    logger.info(f"Configuration loaded: target={config.target_base_url}")
    
    # Initialize Sentinel
    db_path = os.getenv("SENTINEL_DB_PATH", "/var/lib/sentinel/sentinel.db")
    sentinel = SentinelRunner(config, db_path)
    
    # Initialize API server
    api_port = int(os.getenv("SENTINEL_API_PORT", "9090"))
    api_server = SentinelAPI(sentinel, api_port)
    
    # Start API server
    await api_server.start_server()
    logger.info(f"📊 API server started on port {api_port}")
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, initiating shutdown...")
        sentinel.stop()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Run initial cycle to verify connectivity
        logger.info("🔍 Running initial connectivity test...")
        initial_report = await sentinel.run_single_cycle()
        
        passed = initial_report["passed_checks"]
        total = initial_report["total_checks"]
        
        if passed == 0:
            logger.error("❌ Initial connectivity test failed completely - check configuration")
            sys.exit(1)
        elif passed < total:
            logger.warning(f"⚠️ Initial test partial success: {passed}/{total} checks passed")
        else:
            logger.info(f"✅ Initial connectivity test successful: {passed}/{total} checks passed")
        
        # Start continuous monitoring
        logger.info("🔄 Starting continuous monitoring scheduler...")
        await sentinel.start_scheduler()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        sys.exit(1)
    finally:
        sentinel.stop()
        logger.info("🛑 Veris Sentinel stopped")


if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs("/var/lib/sentinel", exist_ok=True)
    
    # Run main async function
    asyncio.run(main())