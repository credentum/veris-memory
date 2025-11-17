#!/usr/bin/env python3
"""
Tests for Sentinel API Key Exemption in Rate Limit Middleware

Validates that:
1. Sentinel API key bypasses rate limiting
2. Invalid API keys still get rate limited
3. Missing API keys get rate limited
4. Security is maintained for public requests
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from fastapi.responses import JSONResponse

# Import the middleware
from src.api.rate_limit_middleware import RateLimitMiddleware


class TestSentinelRateLimitExemption:
    """Tests for Sentinel API key rate limit exemption."""

    @pytest.mark.asyncio
    async def test_sentinel_api_key_bypasses_rate_limit(self):
        """Test that valid Sentinel API key bypasses rate limiting."""
        # Setup
        sentinel_key = "vmk_sentinel_test123:user:role:agent"

        with patch.dict('os.environ', {'SENTINEL_API_KEY': sentinel_key}):
            # Create mock request with Sentinel API key
            mock_request = Mock(spec=Request)
            mock_request.headers = {"x-api-key": sentinel_key}
            mock_request.url = Mock()
            mock_request.url.path = "/api/v1/contexts/search"
            mock_request.client = Mock()
            mock_request.client.host = "172.18.0.10"

            # Create mock call_next
            mock_response = JSONResponse(content={"success": True})
            async def mock_call_next(request):
                return mock_response

            # Create middleware
            from slowapi import Limiter
            from slowapi.util import get_remote_address
            limiter = Limiter(key_func=get_remote_address)
            middleware = RateLimitMiddleware(
                app=Mock(),
                limiter=limiter,
                limit="20/minute"
            )

            # Execute
            response = await middleware.dispatch(mock_request, mock_call_next)

            # Verify exemption header was added
            assert response.headers.get("X-RateLimit-Exempt") == "sentinel_monitoring"

    @pytest.mark.asyncio
    async def test_invalid_api_key_gets_rate_limited(self):
        """Test that invalid API key does NOT bypass rate limiting."""
        sentinel_key = "vmk_sentinel_test123"
        invalid_key = "vmk_invalid_wrong456"

        with patch.dict('os.environ', {'SENTINEL_API_KEY': sentinel_key}):
            # Create middleware
            from slowapi import Limiter
            from slowapi.util import get_remote_address
            limiter = Limiter(key_func=get_remote_address)
            middleware = RateLimitMiddleware(
                app=Mock(),
                limiter=limiter,
                limit="2/minute"  # Low limit for testing
            )

            # Make 3 requests with invalid key (should hit rate limit on 3rd)
            for i in range(3):
                mock_request = Mock(spec=Request)
                mock_request.headers = {"x-api-key": invalid_key}
                mock_request.url = Mock()
                mock_request.url.path = "/test"
                mock_request.client = Mock()
                mock_request.client.host = "192.168.1.100"

                mock_response = JSONResponse(content={"success": True})
                async def mock_call_next(request):
                    return mock_response

                response = await middleware.dispatch(mock_request, mock_call_next)

                if i < 2:
                    # First 2 requests should succeed
                    assert response.status_code == 200
                else:
                    # 3rd request should be rate limited
                    assert response.status_code == 429
                    assert "RATE_LIMIT_EXCEEDED" in str(response.body)

    @pytest.mark.asyncio
    async def test_missing_api_key_gets_rate_limited(self):
        """Test that requests without API key get rate limited."""
        with patch.dict('os.environ', {'SENTINEL_API_KEY': 'vmk_test'}):
            # Create middleware
            from slowapi import Limiter
            from slowapi.util import get_remote_address
            limiter = Limiter(key_func=get_remote_address)
            middleware = RateLimitMiddleware(
                app=Mock(),
                limiter=limiter,
                limit="2/minute"
            )

            # Make requests without API key
            for i in range(3):
                mock_request = Mock(spec=Request)
                mock_request.headers = {}  # No API key
                mock_request.url = Mock()
                mock_request.url.path = "/test"
                mock_request.client = Mock()
                mock_request.client.host = "192.168.1.200"

                mock_response = JSONResponse(content={"success": True})
                async def mock_call_next(request):
                    return mock_response

                response = await middleware.dispatch(mock_request, mock_call_next)

                if i < 2:
                    assert response.status_code == 200
                else:
                    assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_sentinel_key_with_colon_format_works(self):
        """Test that Sentinel API key in colon format (vmk_xxx:user:role:agent) works."""
        sentinel_key = "vmk_test_abc123:sentinel_user:monitoring:agent"
        request_key = "vmk_test_abc123:different_user:role:agent"  # Different suffix, same base

        with patch.dict('os.environ', {'SENTINEL_API_KEY': sentinel_key}):
            mock_request = Mock(spec=Request)
            mock_request.headers = {"x-api-key": request_key}
            mock_request.url = Mock()
            mock_request.url.path = "/api/v1/contexts/search"
            mock_request.client = Mock()
            mock_request.client.host = "172.18.0.10"

            mock_response = JSONResponse(content={"success": True})
            async def mock_call_next(request):
                return mock_response

            from slowapi import Limiter
            from slowapi.util import get_remote_address
            limiter = Limiter(key_func=get_remote_address)
            middleware = RateLimitMiddleware(
                app=Mock(),
                limiter=limiter,
                limit="20/minute"
            )

            response = await middleware.dispatch(mock_request, mock_call_next)

            # Should be exempted (same base key before first colon)
            assert response.headers.get("X-RateLimit-Exempt") == "sentinel_monitoring"

    @pytest.mark.asyncio
    async def test_sentinel_can_make_50_requests_without_limit(self):
        """Test that Sentinel can make 50+ requests (full check cycle) without rate limiting."""
        sentinel_key = "vmk_sentinel_test"

        with patch.dict('os.environ', {'SENTINEL_API_KEY': sentinel_key}):
            from slowapi import Limiter
            from slowapi.util import get_remote_address
            limiter = Limiter(key_func=get_remote_address)
            middleware = RateLimitMiddleware(
                app=Mock(),
                limiter=limiter,
                limit="20/minute"  # Normal limit
            )

            # Make 50 requests with Sentinel key
            for i in range(50):
                mock_request = Mock(spec=Request)
                mock_request.headers = {"x-api-key": sentinel_key}
                mock_request.url = Mock()
                mock_request.url.path = f"/api/v1/contexts/search?query=test{i}"
                mock_request.client = Mock()
                mock_request.client.host = "172.18.0.5"

                mock_response = JSONResponse(content={"success": True})
                async def mock_call_next(request):
                    return mock_response

                response = await middleware.dispatch(mock_request, mock_call_next)

                # All requests should succeed (not rate limited)
                assert response.status_code == 200
                assert response.headers.get("X-RateLimit-Exempt") == "sentinel_monitoring"
