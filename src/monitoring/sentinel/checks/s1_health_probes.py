#!/usr/bin/env python3
"""
S1: Health Probes Check

Tests the liveness and readiness endpoints of Veris Memory
to ensure the system is operational and all components are healthy.
"""

import asyncio
import os
import time
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional

from ..base_check import BaseCheck, HealthCheckMixin
from ..models import CheckResult, SentinelConfig


class VerisHealthProbe(BaseCheck, HealthCheckMixin):
    """S1: Health probes for live/ready endpoints."""

    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S1-probes", "Health probes for live/ready endpoints")
        # Get API key from environment for Sprint 13 authentication
        self.api_key = os.getenv('API_KEY_MCP')
        
    async def run_check(self) -> CheckResult:
        """Execute health probe check."""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                # Test liveness endpoint
                liveness_result = await self._check_liveness(session)
                if not liveness_result["success"]:
                    return self._create_result("fail", liveness_result["message"], start_time)
                
                # Test readiness endpoint
                readiness_result = await self._check_readiness(session)
                if not readiness_result["success"]:
                    return self._create_result("fail", readiness_result["message"], start_time)
                
                # All checks passed
                latency_ms = (time.time() - start_time) * 1000
                return CheckResult(
                    check_id=self.check_id,
                    timestamp=datetime.utcnow(),
                    status="pass",
                    latency_ms=latency_ms,
                    message="All health endpoints responding correctly",
                    details={
                        "liveness": liveness_result["details"],
                        "readiness": readiness_result["details"],
                        "latency_ms": latency_ms,
                        "status_bool": 1.0
                    }
                )
                
        except Exception as e:
            return self._create_result("fail", f"Health check exception: {str(e)}", start_time)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests including Sprint 13 authentication."""
        headers = {}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        return headers

    async def _check_liveness(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Check the liveness endpoint."""
        endpoint = f"{self.config.target_base_url}/health/live"

        try:
            # Include API key header if available
            headers = self._get_headers()

            success, message, latency = await self.check_endpoint_health(session, endpoint)
            if not success:
                return {"success": False, "message": message, "details": {"endpoint": endpoint}}

            # Get the actual response data with authentication
            async with session.get(endpoint, headers=headers) as resp:
                live_data = await resp.json()
                
                if live_data.get("status") != "alive":
                    return {
                        "success": False,
                        "message": f"Liveness status not 'alive': {live_data.get('status')}",
                        "details": {"endpoint": endpoint, "response": live_data}
                    }
                
                return {
                    "success": True,
                    "message": "Liveness check passed",
                    "details": {"endpoint": endpoint, "response": live_data}
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Liveness check error: {str(e)}",
                "details": {"endpoint": endpoint, "error": str(e)}
            }
    
    async def _check_readiness(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Check the readiness endpoint and component health."""
        endpoint = f"{self.config.target_base_url}/health/ready"

        try:
            # Include API key header if available
            headers = self._get_headers()

            success, message, latency = await self.check_endpoint_health(session, endpoint)
            if not success:
                return {"success": False, "message": message, "details": {"endpoint": endpoint}}

            # Get the actual response data with authentication
            async with session.get(endpoint, headers=headers) as resp:
                ready_data = await resp.json()
                
                # Verify component statuses
                components = ready_data.get("components", [])
                component_details = {}
                
                for component in components:
                    status = component.get("status", "unknown")
                    name = component.get("name", "unknown")
                    component_details[name] = {"status": status}
                    
                    # Check critical components
                    if name == "qdrant" and status not in ["ok", "healthy"]:
                        return {
                            "success": False,
                            "message": f"Qdrant not healthy: {status}",
                            "details": {
                                "endpoint": endpoint,
                                "response": ready_data,
                                "failed_component": name,
                                "component_status": status
                            }
                        }
                    elif name in ["redis", "neo4j"] and status not in ["ok", "healthy", "degraded"]:
                        return {
                            "success": False,
                            "message": f"{name} not healthy: {status}",
                            "details": {
                                "endpoint": endpoint,
                                "response": ready_data,
                                "failed_component": name,
                                "component_status": status
                            }
                        }
                
                return {
                    "success": True,
                    "message": "Readiness check passed",
                    "details": {
                        "endpoint": endpoint,
                        "response": ready_data,
                        "component_statuses": component_details
                    }
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Readiness check error: {str(e)}",
                "details": {"endpoint": endpoint, "error": str(e)}
            }
    
    def _create_result(self, status: str, message: str, start_time: float) -> CheckResult:
        """Create a CheckResult with consistent timing."""
        latency_ms = (time.time() - start_time) * 1000
        return CheckResult(
            check_id=self.check_id,
            timestamp=datetime.utcnow(),
            status=status,
            latency_ms=latency_ms,
            message=message
        )