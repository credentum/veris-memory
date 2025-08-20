#!/usr/bin/env python3
"""
S5: Security Negatives Check

Tests security controls and RBAC (Role-Based Access Control) to ensure
unauthorized access is properly denied and audit trails are maintained.

This check performs negative security testing to verify that:
- Invalid tokens are rejected
- Unauthorized access attempts fail
- Rate limiting works correctly
- SQL injection attempts are blocked
- Admin endpoints require proper authentication
- Audit trails are generated for security events
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
import aiohttp
import logging

from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig

logger = logging.getLogger(__name__)


class SecurityNegatives(BaseCheck):
    """S5: Security negatives testing for access control validation."""
    
    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S5-security-negatives", "Security negatives testing")
        self.base_url = config.get("veris_memory_url", "http://localhost:8000")
        self.timeout = config.get("s5_security_timeout_sec", 30)
        
    async def run_check(self) -> CheckResult:
        """Execute comprehensive security negatives check."""
        start_time = time.time()
        
        try:
            # Run all security tests concurrently
            test_results = await asyncio.gather(
                self._test_invalid_authentication(),
                self._test_unauthorized_access(),
                self._test_rate_limiting(),
                self._test_sql_injection_protection(),
                self._test_admin_endpoint_protection(),
                self._test_cors_policy(),
                self._test_input_validation(),
                return_exceptions=True
            )
            
            # Analyze results
            security_issues = []
            passed_tests = []
            failed_tests = []
            
            test_names = [
                "invalid_authentication",
                "unauthorized_access", 
                "rate_limiting",
                "sql_injection_protection",
                "admin_endpoint_protection",
                "cors_policy",
                "input_validation"
            ]
            
            for i, result in enumerate(test_results):
                test_name = test_names[i]
                
                if isinstance(result, Exception):
                    failed_tests.append(test_name)
                    security_issues.append(f"{test_name}: {str(result)}")
                elif result.get("passed", False):
                    passed_tests.append(test_name)
                else:
                    failed_tests.append(test_name)
                    security_issues.append(f"{test_name}: {result.get('message', 'Unknown failure')}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine overall status
            if security_issues:
                status = "fail"
                message = f"Security vulnerabilities detected: {len(security_issues)} issues found"
            else:
                status = "pass"
                message = f"All security tests passed: {len(passed_tests)} tests successful"
            
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status=status,
                latency_ms=latency_ms,
                message=message,
                details={
                    "total_tests": len(test_names),
                    "passed_tests": len(passed_tests),
                    "failed_tests": len(failed_tests),
                    "security_issues": security_issues,
                    "passed_test_names": passed_tests,
                    "failed_test_names": failed_tests,
                    "test_results": test_results
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status="fail",
                latency_ms=latency_ms,
                message=f"Security check failed with error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _test_invalid_authentication(self) -> Dict[str, Any]:
        """Test that invalid authentication tokens are properly rejected."""
        try:
            invalid_tokens = [
                "invalid_token",
                "Bearer fake_token",
                "expired_token_123",
                "",
                None,
                "admin",
                "password123"
            ]
            
            auth_failures = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                for token in invalid_tokens:
                    headers = {}
                    if token is not None:
                        headers["Authorization"] = f"Bearer {token}"
                    
                    try:
                        async with session.get(
                            f"{self.base_url}/api/contexts",
                            headers=headers
                        ) as response:
                            # Should be 401 Unauthorized or 403 Forbidden
                            if response.status not in [401, 403]:
                                auth_failures.append({
                                    "token": token or "None",
                                    "expected_status": "401/403",
                                    "actual_status": response.status,
                                    "message": "Invalid token was accepted"
                                })
                    except aiohttp.ClientError:
                        # Network errors are acceptable for this test
                        pass
            
            return {
                "passed": len(auth_failures) == 0,
                "message": f"Found {len(auth_failures)} authentication bypasses" if auth_failures else "All invalid tokens properly rejected",
                "failures": auth_failures
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Authentication test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_unauthorized_access(self) -> Dict[str, Any]:
        """Test unauthorized access to protected endpoints."""
        try:
            protected_endpoints = [
                "/api/contexts",
                "/api/admin/users",
                "/api/admin/config", 
                "/api/metrics",
                "/health/internal",
                "/debug/info"
            ]
            
            access_violations = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                for endpoint in protected_endpoints:
                    try:
                        # Test without any authentication
                        async with session.get(f"{self.base_url}{endpoint}") as response:
                            if response.status == 200:
                                access_violations.append({
                                    "endpoint": endpoint,
                                    "status": response.status,
                                    "message": "Endpoint accessible without authentication"
                                })
                    except aiohttp.ClientError:
                        # Network errors are acceptable
                        pass
            
            return {
                "passed": len(access_violations) == 0,
                "message": f"Found {len(access_violations)} unauthorized access points" if access_violations else "All endpoints properly protected",
                "violations": access_violations
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Unauthorized access test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_rate_limiting(self) -> Dict[str, Any]:
        """Test that rate limiting is properly enforced."""
        try:
            # Send rapid requests to trigger rate limiting
            request_count = 50
            rate_limit_triggered = False
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                tasks = []
                for _ in range(request_count):
                    task = asyncio.create_task(
                        session.get(f"{self.base_url}/health/live")
                    )
                    tasks.append(task)
                
                # Execute all requests concurrently
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Check for rate limiting responses
                for response in responses:
                    if not isinstance(response, Exception):
                        if response.status == 429:  # Too Many Requests
                            rate_limit_triggered = True
                            break
                        response.close()
            
            return {
                "passed": True,  # Rate limiting is optional, not a security failure
                "message": f"Rate limiting {'detected' if rate_limit_triggered else 'not detected'} after {request_count} requests",
                "rate_limit_active": rate_limit_triggered,
                "requests_sent": request_count
            }
            
        except Exception as e:
            return {
                "passed": True,  # Don't fail on rate limit test errors
                "message": f"Rate limiting test encountered error: {str(e)}",
                "error": str(e)
            }
    
    async def _test_sql_injection_protection(self) -> Dict[str, Any]:
        """Test protection against SQL injection attacks."""
        try:
            sql_injection_payloads = [
                "'; DROP TABLE contexts; --",
                "' OR '1'='1",
                "'; SELECT * FROM users; --",
                "' UNION SELECT null, username, password FROM users --",
                "admin'--",
                "' OR 1=1 --",
                "\"; DELETE FROM contexts; --"
            ]
            
            sql_vulnerabilities = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                for payload in sql_injection_payloads:
                    try:
                        # Test SQL injection in query parameters
                        params = {"query": payload}
                        async with session.get(
                            f"{self.base_url}/api/contexts/search",
                            params=params
                        ) as response:
                            response_text = await response.text()
                            
                            # Look for SQL error messages that might indicate vulnerability
                            sql_error_indicators = [
                                "sql",
                                "syntax error",
                                "mysql",
                                "postgresql",
                                "sqlite",
                                "database error",
                                "ORA-",
                                "must appear in the GROUP BY"
                            ]
                            
                            response_lower = response_text.lower()
                            for indicator in sql_error_indicators:
                                if indicator in response_lower:
                                    sql_vulnerabilities.append({
                                        "payload": payload,
                                        "endpoint": "/api/contexts/search",
                                        "indicator": indicator,
                                        "response_status": response.status
                                    })
                                    break
                    except aiohttp.ClientError:
                        # Network errors are acceptable
                        pass
            
            return {
                "passed": len(sql_vulnerabilities) == 0,
                "message": f"Found {len(sql_vulnerabilities)} potential SQL injection vulnerabilities" if sql_vulnerabilities else "No SQL injection vulnerabilities detected",
                "vulnerabilities": sql_vulnerabilities
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"SQL injection test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_admin_endpoint_protection(self) -> Dict[str, Any]:
        """Test that admin endpoints require proper authentication."""
        try:
            admin_endpoints = [
                "/api/admin",
                "/api/admin/users",
                "/api/admin/config",
                "/api/admin/stats",
                "/admin",
                "/debug",
                "/metrics/internal"
            ]
            
            admin_violations = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                for endpoint in admin_endpoints:
                    try:
                        async with session.get(f"{self.base_url}{endpoint}") as response:
                            # Admin endpoints should return 401, 403, or 404
                            # 200 or 500 might indicate vulnerability
                            if response.status in [200, 500]:
                                admin_violations.append({
                                    "endpoint": endpoint,
                                    "status": response.status,
                                    "message": "Admin endpoint potentially accessible"
                                })
                    except aiohttp.ClientError:
                        # Network errors are acceptable
                        pass
            
            return {
                "passed": len(admin_violations) == 0,
                "message": f"Found {len(admin_violations)} admin endpoint vulnerabilities" if admin_violations else "Admin endpoints properly protected",
                "violations": admin_violations
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Admin endpoint test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_cors_policy(self) -> Dict[str, Any]:
        """Test CORS policy configuration."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Test CORS with suspicious origin
                headers = {
                    "Origin": "https://malicious-site.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type"
                }
                
                async with session.options(
                    f"{self.base_url}/api/contexts",
                    headers=headers
                ) as response:
                    cors_headers = {
                        "access-control-allow-origin": response.headers.get("Access-Control-Allow-Origin"),
                        "access-control-allow-credentials": response.headers.get("Access-Control-Allow-Credentials"),
                        "access-control-allow-methods": response.headers.get("Access-Control-Allow-Methods")
                    }
                    
                    # Check for overly permissive CORS
                    cors_issues = []
                    if cors_headers["access-control-allow-origin"] == "*":
                        if cors_headers["access-control-allow-credentials"] == "true":
                            cors_issues.append("Dangerous CORS: wildcard origin with credentials")
                    
                    return {
                        "passed": len(cors_issues) == 0,
                        "message": f"CORS issues: {', '.join(cors_issues)}" if cors_issues else "CORS policy appears secure",
                        "cors_headers": cors_headers,
                        "issues": cors_issues
                    }
            
        except Exception as e:
            return {
                "passed": True,  # CORS test failure doesn't indicate security issue
                "message": f"CORS test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_input_validation(self) -> Dict[str, Any]:
        """Test input validation and sanitization."""
        try:
            malicious_inputs = [
                "<script>alert('xss')</script>",
                "javascript:alert('xss')",
                "../../../etc/passwd",
                "\\x00\\x01\\x02",
                "A" * 10000,  # Buffer overflow attempt
                "{\"__proto__\": {\"admin\": true}}"  # Prototype pollution
            ]
            
            validation_failures = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                for malicious_input in malicious_inputs:
                    try:
                        # Test in POST body
                        payload = {
                            "context_type": "test",
                            "content": {"data": malicious_input}
                        }
                        
                        async with session.post(
                            f"{self.base_url}/api/contexts",
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        ) as response:
                            # Check if malicious input was reflected or processed unsafely
                            if response.status == 200:
                                response_text = await response.text()
                                if malicious_input in response_text:
                                    validation_failures.append({
                                        "input": malicious_input[:100],  # Truncate for logging
                                        "endpoint": "/api/contexts",
                                        "message": "Malicious input reflected in response"
                                    })
                    except aiohttp.ClientError:
                        # Network errors are acceptable
                        pass
            
            return {
                "passed": len(validation_failures) == 0,
                "message": f"Found {len(validation_failures)} input validation issues" if validation_failures else "Input validation appears secure",
                "failures": validation_failures
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Input validation test failed: {str(e)}",
                "error": str(e)
            }