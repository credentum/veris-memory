#!/usr/bin/env python3
"""
Custom Rate Limiting Middleware

Applies rate limiting to ALL requests, including 405/404 responses.
This runs before FastAPI routing to catch all requests at the ASGI level.

S5 Security Fix: Prevents authentication brute force attacks by limiting
ALL requests, not just those that reach route handlers.
"""

import os
import time
import asyncio
from typing import Callable, Dict, Tuple
from collections import defaultdict
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..utils.logging_middleware import api_logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies rate limiting to ALL HTTP requests.

    Unlike slowapi's application_limits, this middleware:
    - Runs before FastAPI routing
    - Counts 405 (Method Not Allowed) responses
    - Counts 404 (Not Found) responses
    - Prevents authentication brute force attacks

    This is critical for S5 security compliance because attackers can
    spam ANY endpoint (even non-existent ones) to perform reconnaissance
    or exhaust server resources.

    Uses in-memory storage for simplicity. For production with multiple
    instances, configure Redis backend for distributed rate limiting.
    """

    def __init__(
        self,
        app: ASGIApp,
        limiter: Limiter,
        limit: str = "20/minute"
    ) -> None:
        """
        Initialize rate limit middleware.

        Args:
            app: ASGI application
            limiter: slowapi Limiter instance (for compatibility)
            limit: Rate limit string (e.g., "20/minute", "100/hour")
        """
        super().__init__(app)
        self.limiter = limiter
        self.limit = limit

        # In-memory storage for rate limiting
        # Format: {(client_ip, window_start): request_count}
        self.request_counts: Dict[Tuple[str, int], int] = defaultdict(int)

        # Lock for thread-safe access
        self.lock = asyncio.Lock()

        # Parse limit string to extract rate
        self._parse_limit(limit)

        # Warning for production deployments with in-memory storage
        self._check_production_deployment()

    def _parse_limit(self, limit: str) -> None:
        """Parse limit string into rate and period."""
        try:
            rate_str, period_str = limit.split("/")
            self.rate = int(rate_str.strip())
            self.period = period_str.strip()

            # Convert period to seconds
            period_mapping = {
                "second": 1,
                "seconds": 1,
                "minute": 60,
                "minutes": 60,
                "hour": 3600,
                "hours": 3600,
                "day": 86400,
                "days": 86400
            }

            self.period_seconds = period_mapping.get(self.period, 60)

        except Exception as e:
            api_logger.warning(f"Failed to parse rate limit '{limit}': {e}, using defaults")
            self.rate = 20
            self.period = "minute"
            self.period_seconds = 60

    def _check_production_deployment(self) -> None:
        """
        Check if running in production with in-memory storage and warn.

        In-memory storage only works for single-instance deployments.
        Multi-instance deployments need Redis or another distributed storage backend.

        Raises a CRITICAL warning in production without Redis to ensure operators
        are aware of the limitation.
        """
        environment = os.getenv("ENVIRONMENT", "development").lower()
        redis_url = os.getenv("REDIS_URL", "")

        if environment in ["production", "prod"] and not redis_url:
            api_logger.critical(
                "🚨 CRITICAL: Rate limiting using IN-MEMORY storage in PRODUCTION environment. "
                "⚠️  WARNING: This WILL NOT WORK correctly with multiple instances. "
                "Rate limits will NOT be shared across instances, allowing attackers to bypass limits. "
                "🔧 FIX: Configure Redis backend by setting REDIS_URL environment variable. "
                "📖 For single-instance deployments, this is acceptable but should be documented.",
                environment=environment,
                redis_configured=False,
                single_instance_only=True,
                security_risk="rate_limit_bypass_in_multi_instance"
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Apply rate limiting to every request.

        This runs BEFORE FastAPI routing, so it catches:
        - Valid requests (200)
        - Authentication failures (401/403)
        - Method not allowed (405)
        - Not found (404)
        - All other responses

        EXEMPTIONS (Fix for Sentinel rate limit issue):
        - Sentinel monitoring: Exempt requests with valid SENTINEL_API_KEY
        - Allows Sentinel to run comprehensive checks (~48 queries/cycle)
        - Maintains security for public/unauthenticated requests
        """

        # EXEMPTION: Check for Sentinel API key (monitoring exemption)
        # Sentinel needs ~48 queries per cycle, which exceeds 20/min limit
        # This exemption allows monitoring while maintaining security for public requests
        api_key_header = request.headers.get("x-api-key", "")
        sentinel_api_key = os.getenv("SENTINEL_API_KEY", "")

        if api_key_header and sentinel_api_key:
            # Extract key portion (before colon if present: vmk_xxx_yyy:user:role:agent)
            api_key_base = api_key_header.split(":")[0]
            sentinel_key_base = sentinel_api_key.split(":")[0]

            if api_key_base == sentinel_key_base:
                # Bypass rate limit for Sentinel monitoring
                api_logger.debug(
                    "Rate limit bypassed for Sentinel monitoring",
                    path=request.url.path,
                    reason="sentinel_api_key_match"
                )
                response = await call_next(request)
                # Add headers to indicate exemption
                response.headers["X-RateLimit-Exempt"] = "sentinel_monitoring"
                return response

        # Get client IP address
        client_ip = get_remote_address(request)

        # Get current time window
        current_time = int(time.time())
        window_start = current_time - (current_time % self.period_seconds)

        try:
            async with self.lock:
                # Clean up old time windows (older than 2 periods)
                cutoff_time = window_start - (2 * self.period_seconds)
                keys_to_delete = [
                    key for key in self.request_counts.keys()
                    if key[1] < cutoff_time
                ]
                for key in keys_to_delete:
                    del self.request_counts[key]

                # Get current count for this IP in this time window
                count_key = (client_ip, window_start)
                current_count = self.request_counts[count_key]

                # Check if rate limit exceeded
                if current_count >= self.rate:
                    api_logger.warning(
                        "Rate limit exceeded",
                        client_ip=client_ip,
                        path=request.url.path,
                        count=current_count,
                        limit=self.rate,
                        period=self.period
                    )

                    # Return 429 Too Many Requests
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": f"Rate limit exceeded: {self.rate} requests per {self.period}",
                                "details": {
                                    "limit": self.rate,
                                    "period": self.period,
                                    "retry_after_seconds": self.period_seconds - (current_time % self.period_seconds)
                                }
                            }
                        },
                        headers={
                            "Retry-After": str(self.period_seconds - (current_time % self.period_seconds)),
                            "X-RateLimit-Limit": str(self.rate),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(window_start + self.period_seconds)
                        }
                    )

                # Increment count
                self.request_counts[count_key] += 1

                # Calculate remaining requests
                remaining = max(0, self.rate - self.request_counts[count_key])

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.rate)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(window_start + self.period_seconds)

            return response

        except RateLimitExceeded:
            # slowapi raised RateLimitExceeded (shouldn't happen with our implementation)
            api_logger.warning(
                "Rate limit exceeded (slowapi)",
                client_ip=client_ip,
                path=request.url.path
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded: {self.rate} requests per {self.period}"
                    }
                },
                headers={"Retry-After": str(self.period_seconds)}
            )

        except Exception as e:
            # Don't block requests on rate limit failures (fail open for availability)
            api_logger.error(
                "Rate limit check failed",
                error=str(e),
                client_ip=client_ip,
                path=request.url.path
            )

            # Process request anyway
            response = await call_next(request)
            return response
