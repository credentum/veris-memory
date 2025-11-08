#!/usr/bin/env python3
"""
Base check interface for Sentinel monitoring checks.

Provides the common interface and utilities that all check classes implement.
"""

import asyncio
import logging
import os
import re
import time
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from .models import CheckResult, SentinelConfig

logger = logging.getLogger(__name__)

# API key validation patterns
# Key-only format: vmk_{prefix}_{hash}
API_KEY_PATTERN = re.compile(r'^vmk_[a-zA-Z0-9]+_[a-zA-Z0-9]+$')
# Full format: vmk_{prefix}_{hash}:user_id:role:is_agent
FULL_FORMAT_PATTERN = re.compile(r'^vmk_[a-zA-Z0-9]+_[a-zA-Z0-9]+:[^:]+:[^:]+:(true|false)$')


class BaseCheck(ABC):
    """Abstract base class for all Sentinel checks."""
    
    def __init__(self, config: SentinelConfig, check_id: str, description: str):
        """
        Initialize base check.
        
        Args:
            config: Sentinel configuration
            check_id: Unique identifier for this check (e.g., "S1-probes")
            description: Human-readable description of what this check does
        """
        self.config = config
        self.check_id = check_id
        self.description = description
        self.last_result: Optional[CheckResult] = None
        self.execution_count = 0
        self.total_execution_time = 0.0
    
    @abstractmethod
    async def run_check(self) -> CheckResult:
        """
        Execute the check and return results.
        
        This method must be implemented by all check subclasses.
        
        Returns:
            CheckResult with the outcome of the check
        """
        pass
    
    async def execute(self) -> CheckResult:
        """
        Execute the check with timing and error handling.
        
        This is the main entry point that wraps run_check() with
        common functionality like timing, error handling, and result caching.
        
        Returns:
            CheckResult with the outcome of the check
        """
        start_time = time.time()
        self.execution_count += 1
        
        try:
            result = await self.run_check()
            
            # Ensure the result has the correct check_id
            if result.check_id != self.check_id:
                result.check_id = self.check_id
            
            # Cache the result
            self.last_result = result
            
            # Update timing statistics
            execution_time = time.time() - start_time
            self.total_execution_time += execution_time
            
            return result
            
        except Exception as e:
            # Create failure result for any unhandled exceptions
            execution_time = time.time() - start_time
            self.total_execution_time += execution_time
            
            result = CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status="fail",
                latency_ms=execution_time * 1000,
                message=f"Check execution failed: {str(e)}",
                details={"exception_type": type(e).__name__, "exception_message": str(e)}
            )
            
            self.last_result = result
            return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics for this check.
        
        Returns:
            Dictionary with timing and execution statistics
        """
        avg_execution_time = (
            self.total_execution_time / self.execution_count 
            if self.execution_count > 0 else 0.0
        )
        
        return {
            "check_id": self.check_id,
            "description": self.description,
            "execution_count": self.execution_count,
            "total_execution_time_seconds": self.total_execution_time,
            "average_execution_time_seconds": avg_execution_time,
            "last_result": self.last_result.to_dict() if self.last_result else None
        }
    
    def is_enabled(self) -> bool:
        """Check if this check is enabled in the configuration."""
        return self.config.is_check_enabled(self.check_id)
    
    async def run_with_timeout(self, timeout_seconds: float = 30.0) -> CheckResult:
        """
        Execute the check with a timeout.
        
        Args:
            timeout_seconds: Maximum time to allow for check execution
            
        Returns:
            CheckResult, with timeout failure if the check takes too long
        """
        try:
            return await asyncio.wait_for(self.execute(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status="fail",
                latency_ms=timeout_seconds * 1000,
                message=f"Check timed out after {timeout_seconds} seconds",
                details={"timeout_seconds": timeout_seconds}
            )


class HealthCheckMixin:
    """Mixin providing common health check utilities."""
    
    async def check_endpoint_health(
        self, 
        session,
        endpoint: str, 
        expected_status: int = 200,
        timeout: float = 5.0
    ) -> tuple[bool, str, float]:
        """
        Check if an endpoint is healthy.
        
        Args:
            session: aiohttp ClientSession
            endpoint: URL to check
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (success, message, latency_ms)
        """
        start_time = time.time()
        
        try:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                latency_ms = (time.time() - start_time) * 1000
                
                if resp.status == expected_status:
                    return True, f"Endpoint healthy (HTTP {resp.status})", latency_ms
                else:
                    return False, f"Unexpected status: HTTP {resp.status}", latency_ms
                    
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return False, f"Endpoint timeout after {timeout}s", latency_ms
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return False, f"Endpoint error: {str(e)}", latency_ms


class APITestMixin:
    """Mixin providing common API testing utilities."""
    
    async def test_api_call(
        self,
        session,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        expected_status: int = 200,
        timeout: float = 10.0
    ) -> tuple[bool, str, float, Optional[Dict[str, Any]]]:
        """
        Test an API call and return results.
        
        Args:
            session: aiohttp ClientSession
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint URL
            data: Request data (for POST/PUT)
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (success, message, latency_ms, response_data)
        """
        start_time = time.time()
        
        try:
            # Include API key authentication header with validation
            # Try SENTINEL_API_KEY first (dedicated monitoring key), fall back to API_KEY_MCP
            headers = {}
            api_key_env = os.getenv("SENTINEL_API_KEY") or os.getenv("API_KEY_MCP")
            if api_key_env:
                # Validate and extract key
                api_key_env = api_key_env.strip()
                if not api_key_env:
                    logger.warning("SENTINEL_API_KEY/API_KEY_MCP is empty after stripping whitespace.")
                else:
                    # Extract key portion from format: vmk_{prefix}_{hash}:user_id:role:is_agent
                    # Context-store expects only the key portion (before first colon)
                    # This matches how context-store's api_key_auth.py parses the env var
                    api_key_parts: list[str] = api_key_env.split(":")
                    api_key = api_key_parts[0]  # Extract key portion only

                    # Check if env var has full format (preferred) or just key
                    if FULL_FORMAT_PATTERN.match(api_key_env):
                        # Full format detected, extracted key portion
                        headers["X-API-Key"] = api_key
                        redacted_key = api_key[:12] + "..." if len(api_key) > 12 else "***"
                        logger.debug(f"Using API key (extracted from full format): {redacted_key}")
                    elif API_KEY_PATTERN.match(api_key):
                        # Key-only format
                        headers["X-API-Key"] = api_key
                        redacted_key = api_key[:12] + "..." if len(api_key) > 12 else "***"
                        logger.debug(f"Using API key: {redacted_key}")
                    else:
                        # Invalid format
                        redacted_key = api_key_env[:8] + "..." if len(api_key_env) > 8 else "***"
                        logger.warning(
                            f"SENTINEL_API_KEY/API_KEY_MCP format invalid. Expected: vmk_{{prefix}}_{{hash}} or vmk_{{prefix}}_{{hash}}:user_id:role:is_agent. "
                            f"Got: {redacted_key}"
                        )
            else:
                logger.warning(
                    "SENTINEL_API_KEY/API_KEY_MCP not found in environment. API calls may fail with authentication errors. "
                    "Please set SENTINEL_API_KEY or API_KEY_MCP environment variable."
                )

            request_kwargs = {
                "timeout": aiohttp.ClientTimeout(total=timeout),
                "headers": headers
            }

            if data and method.upper() in ['POST', 'PUT', 'PATCH']:
                request_kwargs["json"] = data

            async with getattr(session, method.lower())(endpoint, **request_kwargs) as resp:
                latency_ms = (time.time() - start_time) * 1000

                try:
                    response_data = await resp.json()
                except Exception as e:
                    logger.debug(f"Failed to parse JSON response: {e}. Response might not be JSON.")
                    response_data = None
                
                if resp.status == expected_status:
                    return True, f"API call successful (HTTP {resp.status})", latency_ms, response_data
                else:
                    return False, f"API call failed: HTTP {resp.status}", latency_ms, response_data
                    
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return False, f"API timeout after {timeout}s", latency_ms, None
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return False, f"API error: {str(e)}", latency_ms, None
