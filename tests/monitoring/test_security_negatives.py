#!/usr/bin/env python3
"""
Unit tests for S5 Security Negatives Check.

Tests the SecurityNegatives check with mocked HTTP calls.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp

from src.monitoring.sentinel.checks.s5_security_negatives import SecurityNegatives
from src.monitoring.sentinel.models import SentinelConfig


class TestSecurityNegatives:
    """Test suite for SecurityNegatives check."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return SentinelConfig({
            "veris_memory_url": "http://test.example.com",
            "s5_security_timeout_sec": 10
        })
    
    @pytest.fixture
    def check(self, config):
        """Create a SecurityNegatives check instance."""
        return SecurityNegatives(config)
    
    @pytest.mark.asyncio
    async def test_initialization(self, config):
        """Test check initialization."""
        check = SecurityNegatives(config)
        
        assert check.check_id == "S5-security-negatives"
        assert check.description == "Security negatives testing"
        assert check.base_url == "http://test.example.com"
        assert check.timeout == 10
    
    @pytest.mark.asyncio
    async def test_run_check_all_pass(self, check):
        """Test run_check when all security tests pass."""
        # Mock all test methods to return successful results
        mock_results = [
            {"passed": True, "message": "Authentication test passed"},
            {"passed": True, "message": "Unauthorized access test passed"},
            {"passed": True, "message": "Rate limiting test passed"},
            {"passed": True, "message": "SQL injection test passed"},
            {"passed": True, "message": "Admin endpoint test passed"},
            {"passed": True, "message": "CORS test passed"},
            {"passed": True, "message": "Input validation test passed"}
        ]
        
        with patch.object(check, '_test_invalid_authentication', return_value=mock_results[0]):
            with patch.object(check, '_test_unauthorized_access', return_value=mock_results[1]):
                with patch.object(check, '_test_rate_limiting', return_value=mock_results[2]):
                    with patch.object(check, '_test_sql_injection_protection', return_value=mock_results[3]):
                        with patch.object(check, '_test_admin_endpoint_protection', return_value=mock_results[4]):
                            with patch.object(check, '_test_cors_policy', return_value=mock_results[5]):
                                with patch.object(check, '_test_input_validation', return_value=mock_results[6]):
                                    
                                    result = await check.run_check()
        
        assert result.check_id == "S5-security-negatives"
        assert result.status == "pass"
        assert "All security tests passed: 7 tests successful" in result.message
        assert result.details["total_tests"] == 7
        assert result.details["passed_tests"] == 7
        assert result.details["failed_tests"] == 0
        assert len(result.details["security_issues"]) == 0
    
    @pytest.mark.asyncio
    async def test_run_check_with_failures(self, check):
        """Test run_check when some security tests fail."""
        mock_results = [
            {"passed": False, "message": "Authentication bypassed"},
            {"passed": True, "message": "Unauthorized access test passed"},
            {"passed": False, "message": "SQL injection vulnerability found"},
            {"passed": True, "message": "Admin endpoint test passed"},
            {"passed": True, "message": "CORS test passed"},
            {"passed": True, "message": "Input validation test passed"},
            {"passed": True, "message": "Rate limiting test passed"}
        ]
        
        with patch.object(check, '_test_invalid_authentication', return_value=mock_results[0]):
            with patch.object(check, '_test_unauthorized_access', return_value=mock_results[1]):
                with patch.object(check, '_test_rate_limiting', return_value=mock_results[6]):
                    with patch.object(check, '_test_sql_injection_protection', return_value=mock_results[2]):
                        with patch.object(check, '_test_admin_endpoint_protection', return_value=mock_results[3]):
                            with patch.object(check, '_test_cors_policy', return_value=mock_results[4]):
                                with patch.object(check, '_test_input_validation', return_value=mock_results[5]):
                                    
                                    result = await check.run_check()
        
        assert result.status == "fail"
        assert "Security vulnerabilities detected: 2 issues found" in result.message
        assert result.details["passed_tests"] == 5
        assert result.details["failed_tests"] == 2
        assert len(result.details["security_issues"]) == 2
    
    @pytest.mark.asyncio
    async def test_run_check_with_exception(self, check):
        """Test run_check when an exception occurs."""
        with patch.object(check, '_test_invalid_authentication', side_effect=Exception("Network error")):
            result = await check.run_check()
        
        assert result.status == "fail"
        assert "Security check failed with error: Network error" in result.message
        assert result.details["error"] == "Network error"
    
    @pytest.mark.asyncio
    async def test_invalid_authentication(self, check):
        """Test invalid authentication test."""
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 401  # Unauthorized
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__ = AsyncMock()
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_invalid_authentication()
        
        assert result["passed"] is True
        assert "All invalid tokens properly rejected" in result["message"]
        assert len(result["failures"]) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_authentication_with_bypass(self, check):
        """Test invalid authentication test when tokens are accepted."""
        # Mock aiohttp session that accepts invalid tokens
        mock_response = AsyncMock()
        mock_response.status = 200  # Should be 401/403
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_invalid_authentication()
        
        assert result["passed"] is False
        assert "authentication bypasses" in result["message"]
        assert len(result["failures"]) > 0
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, check):
        """Test unauthorized access test."""
        # Mock aiohttp session that properly protects endpoints
        mock_response = AsyncMock()
        mock_response.status = 403  # Forbidden
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_unauthorized_access()
        
        assert result["passed"] is True
        assert "All endpoints properly protected" in result["message"]
        assert len(result["violations"]) == 0
    
    @pytest.mark.asyncio
    async def test_unauthorized_access_with_violations(self, check):
        """Test unauthorized access test when endpoints are accessible."""
        # Mock aiohttp session that allows unauthorized access
        mock_response = AsyncMock()
        mock_response.status = 200  # Should be protected
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_unauthorized_access()
        
        assert result["passed"] is False
        assert "unauthorized access points" in result["message"]
        assert len(result["violations"]) > 0
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, check):
        """Test rate limiting test."""
        # Mock aiohttp session with some 429 responses
        mock_responses = []
        for i in range(50):
            mock_response = AsyncMock()
            mock_response.status = 429 if i > 30 else 200  # Rate limit after 30 requests
            mock_response.close = MagicMock()
            mock_responses.append(mock_response)
        
        async def mock_get(*args, **kwargs):
            return mock_responses.pop(0) if mock_responses else AsyncMock()
        
        mock_session = AsyncMock()
        mock_session.get.side_effect = mock_get
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_rate_limiting()
        
        assert result["passed"] is True  # Rate limiting test doesn't fail
        assert "Rate limiting detected" in result["message"]
        assert result["rate_limit_active"] is True
    
    @pytest.mark.asyncio
    async def test_sql_injection_protection(self, check):
        """Test SQL injection protection test."""
        # Mock aiohttp session that doesn't expose SQL errors
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid query parameter")
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_sql_injection_protection()
        
        assert result["passed"] is True
        assert "No SQL injection vulnerabilities detected" in result["message"]
        assert len(result["vulnerabilities"]) == 0
    
    @pytest.mark.asyncio
    async def test_sql_injection_vulnerability(self, check):
        """Test SQL injection test when vulnerability exists."""
        # Mock aiohttp session that exposes SQL errors
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Database error: syntax error near 'DROP'")
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_sql_injection_protection()
        
        assert result["passed"] is False
        assert "SQL injection vulnerabilities" in result["message"]
        assert len(result["vulnerabilities"]) > 0
    
    @pytest.mark.asyncio
    async def test_admin_endpoint_protection(self, check):
        """Test admin endpoint protection test."""
        # Mock aiohttp session that properly protects admin endpoints
        mock_response = AsyncMock()
        mock_response.status = 404  # Not found
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_admin_endpoint_protection()
        
        assert result["passed"] is True
        assert "Admin endpoints properly protected" in result["message"]
        assert len(result["violations"]) == 0
    
    @pytest.mark.asyncio
    async def test_cors_policy(self, check):
        """Test CORS policy test."""
        # Mock aiohttp session with secure CORS headers
        mock_response = AsyncMock()
        mock_response.headers = {
            "Access-Control-Allow-Origin": "https://trusted-site.com",
            "Access-Control-Allow-Credentials": "false",
            "Access-Control-Allow-Methods": "GET, POST"
        }
        
        mock_session = AsyncMock()
        mock_session.options.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_cors_policy()
        
        assert result["passed"] is True
        assert "CORS policy appears secure" in result["message"]
        assert len(result["issues"]) == 0
    
    @pytest.mark.asyncio
    async def test_cors_policy_dangerous(self, check):
        """Test CORS policy test with dangerous configuration."""
        # Mock aiohttp session with dangerous CORS headers
        mock_response = AsyncMock()
        mock_response.headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, DELETE"
        }
        
        mock_session = AsyncMock()
        mock_session.options.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_cors_policy()
        
        assert result["passed"] is False
        assert "CORS issues" in result["message"]
        assert len(result["issues"]) > 0
    
    @pytest.mark.asyncio
    async def test_input_validation(self, check):
        """Test input validation test."""
        # Mock aiohttp session that doesn't reflect malicious input
        mock_response = AsyncMock()
        mock_response.status = 400  # Bad request
        mock_response.text = AsyncMock(return_value="Invalid input format")
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_input_validation()
        
        assert result["passed"] is True
        assert "Input validation appears secure" in result["message"]
        assert len(result["failures"]) == 0
    
    @pytest.mark.asyncio
    async def test_input_validation_vulnerability(self, check):
        """Test input validation test when vulnerability exists."""
        # Mock aiohttp session that reflects malicious input
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="Created context with content: <script>alert('xss')</script>")
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_input_validation()
        
        assert result["passed"] is False
        assert "input validation issues" in result["message"]
        assert len(result["failures"]) > 0
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, check):
        """Test handling of network errors in individual tests."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get.side_effect = aiohttp.ClientError("Connection failed")
            mock_session_class.return_value = mock_session
            
            # Test should handle network errors gracefully
            result = await check._test_invalid_authentication()
            
            # Network errors are acceptable for security tests
            assert result["passed"] is True  # No auth bypasses detected
            assert len(result["failures"]) == 0