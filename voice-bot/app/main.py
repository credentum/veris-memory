"""
TeamAI Voice Bot - Main FastAPI Application
Integrates LiveKit voice with Veris MCP memory system
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime
from .config import settings
import logging
import sys

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="TeamAI Voice Bot",
    description="Voice-enabled AI teammate with persistent memory",
    version="1.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - configured via CORS_ORIGINS environment variable
# For production, set CORS_ORIGINS to specific domains: "https://app.example.com,https://admin.example.com"
# For development, can use "*" but not recommended for production
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global clients (initialized on startup)
memory_client = None
voice_handler = None
redis_client = None


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global memory_client, voice_handler, redis_client

    logger.info(f"Starting {settings.SERVICE_NAME}...")

    # Initialize memory client (Sprint 13: with retry and author config)
    try:
        from .memory_client import MemoryClient
        memory_client = MemoryClient(
            mcp_url=settings.MCP_SERVER_URL,
            api_key=settings.MCP_API_KEY,
            author_prefix=settings.VOICE_BOT_AUTHOR_PREFIX,
            enable_retry=settings.ENABLE_MCP_RETRY,
            retry_attempts=settings.MCP_RETRY_ATTEMPTS
        )
        await memory_client.initialize()
        logger.info("✅ Memory client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize memory client: {e}")

    # Initialize voice handler
    try:
        from .voice_handler import VoiceHandler
        voice_handler = VoiceHandler(
            settings.LIVEKIT_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET
        )
        await voice_handler.initialize()
        logger.info("✅ Voice handler initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize voice handler: {e}")

    # Initialize Redis client for session state
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True
        )
        # Test connection
        await redis_client.ping()
        logger.info("✅ Redis client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Redis client: {e}")
        logger.warning("⚠️  Voice-bot will continue without Redis (session state disabled)")
        redis_client = None

    logger.info(f"✅ {settings.SERVICE_NAME} started successfully on port {settings.PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global redis_client
    logger.info(f"Shutting down {settings.SERVICE_NAME}...")

    # Close Redis connection
    if redis_client:
        try:
            await redis_client.close()
            logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing Redis connection: {e}")


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "TeamAI Voice Bot",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "voice_session": "/api/v1/voice/session",
            "echo_test": "/api/v1/voice/echo-test"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker"""
    checks = {
        "service": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

    # Check MCP connection
    if memory_client:
        checks["mcp_server"] = await memory_client.check_health()
    else:
        checks["mcp_server"] = False

    # Check LiveKit connection
    if voice_handler:
        checks["livekit"] = await voice_handler.check_health()
    else:
        checks["livekit"] = False

    # Overall status
    all_healthy = checks["mcp_server"] and checks["livekit"]
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        content={
            "status": "healthy" if all_healthy else "degraded",
            "service": settings.SERVICE_NAME,
            "checks": checks
        },
        status_code=status_code
    )


@app.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check including Sprint 13 embedding pipeline status
    Shows full MCP server health including embedding service
    """
    checks = {
        "service": "voice-bot",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mcp_server": None,
        "livekit": None
    }

    # Get detailed MCP health (Sprint 13: includes embedding pipeline)
    if memory_client:
        try:
            mcp_health = await memory_client.get_detailed_health()
            checks["mcp_server"] = mcp_health

            # Check embedding pipeline specifically
            embedding_status = mcp_health.get("services", {}).get("embeddings", "unknown")
            if embedding_status in ["unhealthy", "degraded"]:
                checks["status"] = "degraded"
                checks["warnings"] = [
                    f"Embedding pipeline is {embedding_status}",
                    "Semantic search may not work properly"
                ]
        except Exception as e:
            checks["mcp_server"] = {"status": "error", "error": str(e)}
            checks["status"] = "degraded"
    else:
        checks["mcp_server"] = {"status": "not_initialized"}
        checks["status"] = "degraded"

    # Check LiveKit
    if voice_handler:
        checks["livekit"] = await voice_handler.check_health()
    else:
        checks["livekit"] = False
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503

    return JSONResponse(content=checks, status_code=status_code)


@app.post("/api/v1/voice/session")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def create_voice_session(request: Request, user_id: str):
    """
    Create a new voice session for user
    Returns LiveKit connection details

    Rate limited to prevent abuse of voice session creation.
    """
    if not voice_handler:
        raise HTTPException(status_code=503, detail="Voice handler not initialized")

    try:
        session = await voice_handler.create_voice_session(user_id)
        logger.info(f"Created voice session for user {user_id}: {session['room_name']}")
        return JSONResponse(content=session, status_code=201)
    except Exception as e:
        logger.error(f"Error creating voice session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/voice/echo-test")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def echo_test(request: Request, user_id: str, message: str):
    """
    Echo test endpoint for Sprint 1 validation
    Tests fact storage and retrieval without full voice pipeline

    Rate limited to prevent abuse.
    """
    if not memory_client:
        raise HTTPException(status_code=503, detail="Memory client not initialized")

    try:
        # Store the message as a fact
        await memory_client.store_fact(user_id, "last_message", message)
        logger.info(f"Stored message for {user_id}: {message}")

        # Retrieve user facts
        facts = await memory_client.get_user_facts(user_id, ["name", "color", "last_message"])

        # Generate response based on facts
        name = facts.get("name", "friend")
        color = facts.get("color", "unknown")

        response = f"Hi {name}! Your favorite color is {color}. You just said: {message}"

        return {
            "user_id": user_id,
            "input": message,
            "response": response,
            "facts": facts,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in echo test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/facts/store")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def store_fact(request: Request, user_id: str, key: str, value: str):
    """
    Store a fact about a user

    Rate limited to prevent abuse of fact storage.
    Input validation prevents injection attacks.
    """
    if not memory_client:
        raise HTTPException(status_code=503, detail="Memory client not initialized")

    # Input validation to prevent injection attacks
    if not user_id or len(user_id) > 100 or not user_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid user_id. Must be alphanumeric with optional hyphens/underscores, max 100 chars"
        )

    if not key or len(key) > 100 or not key.replace("_", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="Invalid key. Must be alphanumeric with optional underscores, max 100 chars"
        )

    if not value or len(value) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Invalid value. Must be non-empty and max 1000 chars"
        )

    try:
        success = await memory_client.store_fact(user_id, key, value)
        if success:
            return {"status": "success", "user_id": user_id, "key": key, "value": value}
        else:
            raise HTTPException(status_code=500, detail="Failed to store fact")
    except Exception as e:
        logger.error(f"Error storing fact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/facts/{user_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def get_facts(request: Request, user_id: str, keys: str = None):
    """
    Retrieve facts about a user

    Rate limited to prevent abuse of fact retrieval.
    """
    if not memory_client:
        raise HTTPException(status_code=503, detail="Memory client not initialized")

    try:
        key_list = keys.split(",") if keys else None
        facts = await memory_client.get_user_facts(user_id, key_list)
        return {
            "user_id": user_id,
            "facts": facts,
            "count": len(facts),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error retrieving facts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
