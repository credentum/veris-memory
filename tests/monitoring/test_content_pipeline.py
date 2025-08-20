#!/usr/bin/env python3
"""
Unit tests for S10 Content Pipeline Monitoring Check.

Tests the ContentPipelineMonitoring check with mocked HTTP calls and pipeline validation.
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp

from src.monitoring.sentinel.checks.s10_content_pipeline import ContentPipelineMonitoring
from src.monitoring.sentinel.models import SentinelConfig


class TestContentPipelineMonitoring:
    """Test suite for ContentPipelineMonitoring check."""
    
    @pytest.fixture
    def config(self) -> SentinelConfig:
        """Create a test configuration."""
        return SentinelConfig({
            "veris_memory_url": "http://test.example.com:8000",
            "s10_pipeline_timeout_sec": 30,
            "s10_pipeline_stages": ["ingestion", "validation", "storage", "retrieval"],
            "s10_performance_thresholds": {
                "ingestion_latency_ms": 3000,
                "retrieval_latency_ms": 1000,
                "pipeline_throughput_per_min": 5,
                "storage_consistency_ratio": 0.9
            },
            "s10_test_content_samples": [
                {
                    "type": "test_doc",
                    "content": {
                        "text": "Test document content",
                        "title": "Test Document"
                    },
                    "expected_features": ["test", "document"]
                }
            ]
        })
    
    @pytest.fixture
    def check(self, config: SentinelConfig) -> ContentPipelineMonitoring:
        """Create a ContentPipelineMonitoring check instance."""
        return ContentPipelineMonitoring(config)
    
    @pytest.mark.asyncio
    async def test_initialization(self, config: SentinelConfig) -> None:
        """Test check initialization."""
        check = ContentPipelineMonitoring(config)
        
        assert check.check_id == "S10-content-pipeline"
        assert check.description == "Content pipeline monitoring"
        assert check.veris_memory_url == "http://test.example.com:8000"
        assert check.timeout_seconds == 30
        assert len(check.pipeline_stages) == 4
        assert len(check.test_content_samples) == 1
        assert check.performance_thresholds["ingestion_latency_ms"] == 3000
    
    @pytest.mark.asyncio
    async def test_run_check_all_pass(self, check: ContentPipelineMonitoring) -> None:
        """Test run_check when all pipeline tests pass."""
        mock_results = [
            {"passed": True, "message": "Content ingestion successful"},
            {"passed": True, "message": "Pipeline stages operational"},
            {"passed": True, "message": "Content retrieval working"},
            {"passed": True, "message": "Storage consistency validated"},
            {"passed": True, "message": "Pipeline performance acceptable"},
            {"passed": True, "message": "Error handling working"},
            {"passed": True, "message": "Content lifecycle complete"}
        ]
        
        with patch.object(check, '_test_content_ingestion', return_value=mock_results[0]):
            with patch.object(check, '_validate_pipeline_stages', return_value=mock_results[1]):
                with patch.object(check, '_test_content_retrieval', return_value=mock_results[2]):
                    with patch.object(check, '_validate_storage_consistency', return_value=mock_results[3]):
                        with patch.object(check, '_test_pipeline_performance', return_value=mock_results[4]):
                            with patch.object(check, '_validate_error_handling', return_value=mock_results[5]):
                                with patch.object(check, '_test_content_lifecycle', return_value=mock_results[6]):
                                    
                                    result = await check.run_check()
        
        assert result.check_id == "S10-content-pipeline"
        assert result.status == "pass"
        assert "All content pipeline checks passed: 7 tests successful" in result.message
        assert result.details["total_tests"] == 7
        assert result.details["passed_tests"] == 7
        assert result.details["failed_tests"] == 0
    
    @pytest.mark.asyncio
    async def test_run_check_with_failures(self, check: ContentPipelineMonitoring) -> None:
        """Test run_check when some pipeline tests fail."""
        mock_results = [
            {"passed": False, "message": "Content ingestion failed"},
            {"passed": False, "message": "Pipeline stages unhealthy"},
            {"passed": True, "message": "Content retrieval working"},
            {"passed": True, "message": "Storage consistency validated"},
            {"passed": True, "message": "Pipeline performance acceptable"},
            {"passed": True, "message": "Error handling working"},
            {"passed": True, "message": "Content lifecycle complete"}
        ]
        
        with patch.object(check, '_test_content_ingestion', return_value=mock_results[0]):
            with patch.object(check, '_validate_pipeline_stages', return_value=mock_results[1]):
                with patch.object(check, '_test_content_retrieval', return_value=mock_results[2]):
                    with patch.object(check, '_validate_storage_consistency', return_value=mock_results[3]):
                        with patch.object(check, '_test_pipeline_performance', return_value=mock_results[4]):
                            with patch.object(check, '_validate_error_handling', return_value=mock_results[5]):
                                with patch.object(check, '_test_content_lifecycle', return_value=mock_results[6]):
                                    
                                    result = await check.run_check()
        
        assert result.status == "fail"
        assert "Content pipeline issues detected: 2 problems found" in result.message
        assert result.details["passed_tests"] == 5
        assert result.details["failed_tests"] == 2
    
    @pytest.mark.asyncio
    async def test_content_ingestion_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful content ingestion."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"context_id": "test_ctx_123"})
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_content_ingestion()
        
        assert result["passed"] is True
        assert "Content ingestion" in result["message"]
        assert result["success_rate"] >= 0.0
        assert result["successful_ingestions"] >= 0
        assert len(result["ingestion_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_content_ingestion_failure(self, check: ContentPipelineMonitoring) -> None:
        """Test content ingestion failure handling."""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_content_ingestion()
        
        assert result["passed"] is False
        assert result["success_rate"] < 0.8  # Below threshold
        assert result["successful_ingestions"] == 0
        
        # Check that error details are captured
        for test in result["ingestion_tests"]:
            assert test["ingestion_successful"] is False
            assert test["status_code"] == 400
    
    @pytest.mark.asyncio
    async def test_pipeline_stages_validation_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful pipeline stages validation."""
        mock_health_response = AsyncMock()
        mock_health_response.status = 200
        mock_health_response.json = AsyncMock(return_value={"status": "healthy"})
        
        mock_general_response = AsyncMock()
        mock_general_response.status = 200
        
        mock_session = AsyncMock()
        
        def mock_get(url, **kwargs):
            ctx = AsyncMock()
            if "/health/ready" in url:
                ctx.__aenter__ = AsyncMock(return_value=mock_general_response)
            else:
                ctx.__aenter__ = AsyncMock(return_value=mock_health_response)
            return ctx
        
        mock_session.get.side_effect = mock_get
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_pipeline_stages()
        
        assert result["passed"] is True
        assert "Pipeline stages" in result["message"]
        assert result["stage_health_ratio"] >= 0.0
        assert len(result["stage_validations"]) == len(check.pipeline_stages)
    
    @pytest.mark.asyncio
    async def test_content_retrieval_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful content retrieval."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Test content"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_content_retrieval()
        
        assert result["passed"] is True
        assert "Content retrieval" in result["message"]
        assert result["success_rate"] >= 0.0
        assert len(result["retrieval_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_storage_consistency_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful storage consistency validation."""
        # Mock successful storage
        mock_store_response = AsyncMock()
        mock_store_response.status = 201
        mock_store_response.json = AsyncMock(return_value={"context_id": "test_ctx_123"})
        
        # Mock successful retrieval
        mock_get_response = AsyncMock()
        mock_get_response.status = 200
        mock_get_response.json = AsyncMock(return_value={
            "context_id": "test_ctx_123",
            "content": {"text": "Test content"}
        })
        
        mock_session = AsyncMock()
        
        def mock_request(method_url, **kwargs):
            ctx = AsyncMock()
            if isinstance(method_url, str) and "/contexts/" in method_url:
                ctx.__aenter__ = AsyncMock(return_value=mock_get_response)
            else:
                ctx.__aenter__ = AsyncMock(return_value=mock_store_response)
            return ctx
        
        mock_session.post.side_effect = mock_request
        mock_session.get.side_effect = mock_request
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('asyncio.sleep', return_value=None):  # Speed up test
                result = await check._validate_storage_consistency()
        
        assert result["passed"] is True
        assert "Storage consistency" in result["message"]
        assert result["consistency_ratio"] >= 0.0
        assert len(result["consistency_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_pipeline_performance_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful pipeline performance validation."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"context_id": "test_ctx_123"})
        
        mock_search_response = AsyncMock()
        mock_search_response.status = 200
        mock_search_response.json = AsyncMock(return_value={
            "contexts": [{"context_id": "test_ctx_123"}]
        })
        
        mock_session = AsyncMock()
        
        def mock_request(*args, **kwargs):
            ctx = AsyncMock()
            if "search" in str(args):
                ctx.__aenter__ = AsyncMock(return_value=mock_search_response)
            else:
                ctx.__aenter__ = AsyncMock(return_value=mock_response)
            return ctx
        
        mock_session.post.side_effect = mock_request
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_pipeline_performance()
        
        assert result["passed"] is True
        assert "Pipeline performance" in result["message"]
        assert "performance_metrics" in result
        assert result["all_thresholds_met"] is True
    
    @pytest.mark.asyncio
    async def test_error_handling_validation_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful error handling validation."""
        mock_responses = [
            AsyncMock(status=400, text=AsyncMock(return_value="Bad Request")),  # Invalid content
            AsyncMock(status=413, text=AsyncMock(return_value="Payload Too Large")),  # Oversized
            AsyncMock(status=422, text=AsyncMock(return_value="Unprocessable Entity")),  # Invalid search
            AsyncMock(status=404, text=AsyncMock(return_value="Not Found"))  # Non-existent context
        ]
        
        response_iter = iter(mock_responses)
        
        def mock_request(*args, **kwargs):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=next(response_iter))
            return ctx
        
        mock_session = AsyncMock()
        mock_session.post.side_effect = mock_request
        mock_session.get.side_effect = mock_request
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_error_handling()
        
        assert result["passed"] is True
        assert "Error handling" in result["message"]
        assert result["error_handling_ratio"] >= 0.75
        assert len(result["error_handling_tests"]) == 4
        
        # Verify that errors were properly handled
        for test in result["error_handling_tests"]:
            assert test["properly_handled"] is True
    
    @pytest.mark.asyncio
    async def test_content_lifecycle_success(self, check: ContentPipelineMonitoring) -> None:
        """Test successful content lifecycle validation."""
        # Mock creation
        mock_create_response = AsyncMock()
        mock_create_response.status = 201
        mock_create_response.json = AsyncMock(return_value={"context_id": "lifecycle_test_123"})
        
        # Mock retrieval by ID
        mock_get_response = AsyncMock()
        mock_get_response.status = 200
        mock_get_response.json = AsyncMock(return_value={
            "context_id": "lifecycle_test_123",
            "content": {"text": "Content lifecycle test"}
        })
        
        # Mock search discovery
        mock_search_response = AsyncMock()
        mock_search_response.status = 200
        mock_search_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "lifecycle_test_123", "content": {"text": "Content lifecycle test"}}
            ]
        })
        
        mock_session = AsyncMock()
        
        def mock_request(method, url, **kwargs):
            ctx = AsyncMock()
            if method == "post" and "search" in url:
                ctx.__aenter__ = AsyncMock(return_value=mock_search_response)
            elif method == "get":
                ctx.__aenter__ = AsyncMock(return_value=mock_get_response)
            else:  # POST to create
                ctx.__aenter__ = AsyncMock(return_value=mock_create_response)
            return ctx
        
        mock_session.post.side_effect = lambda url, **kwargs: mock_request("post", url, **kwargs)
        mock_session.get.side_effect = lambda url, **kwargs: mock_request("get", url, **kwargs)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('asyncio.sleep', return_value=None):  # Speed up test
                result = await check._test_content_lifecycle()
        
        assert result["passed"] is True
        assert "Content lifecycle" in result["message"]
        assert result["lifecycle_success_ratio"] >= 0.75
        assert len(result["lifecycle_stages"]) >= 3
        
        # Verify all stages completed successfully
        successful_stages = [stage for stage in result["lifecycle_stages"] if stage.get("successful")]
        assert len(successful_stages) >= 3
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, check: ContentPipelineMonitoring) -> None:
        """Test handling of API errors."""
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientError("Connection failed")
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_content_ingestion()
        
        assert result["passed"] is False
        assert "error" in result
        assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_performance_thresholds(self, check: ContentPipelineMonitoring) -> None:
        """Test performance threshold validation."""
        # Test with slow responses
        slow_mock_response = AsyncMock()
        slow_mock_response.status = 201
        slow_mock_response.json = AsyncMock(return_value={"context_id": "test_ctx"})
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = slow_mock_response
        
        # Mock time.time to simulate slow response
        with patch('time.time', side_effect=[0, 5]):  # 5 second delay
            with patch('aiohttp.ClientSession', return_value=mock_session):
                result = await check._test_content_ingestion()
        
        # Should pass even with slow response if success rate is good
        assert result["passed"] is True
        assert result["avg_ingestion_latency_ms"] > 1000  # Should be > 1 second
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, check: ContentPipelineMonitoring) -> None:
        """Test concurrent operation handling in performance test."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"context_id": "test_ctx"})
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_pipeline_performance()
        
        assert result["passed"] is True
        concurrent_metrics = result["performance_metrics"]["concurrent_load_test"]
        assert concurrent_metrics["concurrent_operations"] == 5
        assert concurrent_metrics["success_rate"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_pipeline_stages_fallback(self, check: ContentPipelineMonitoring) -> None:
        """Test pipeline stages validation with fallback to general health."""
        # Mock stage-specific endpoints failing, but general health succeeding
        mock_general_response = AsyncMock()
        mock_general_response.status = 200
        
        mock_session = AsyncMock()
        
        def mock_get(url, **kwargs):
            ctx = AsyncMock()
            if "/health/ready" in url:
                ctx.__aenter__ = AsyncMock(return_value=mock_general_response)
            else:
                ctx.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Not found"))
            return ctx
        
        mock_session.get.side_effect = mock_get
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_pipeline_stages()
        
        assert result["passed"] is True
        # All stages should be marked as "assumed_healthy"
        for validation in result["stage_validations"]:
            assert validation["stage_operational"] is True
            assert validation["status"] == "assumed_healthy"
    
    @pytest.mark.asyncio
    async def test_run_check_with_exception(self, check: ContentPipelineMonitoring) -> None:
        """Test run_check when an exception occurs."""
        with patch.object(check, '_test_content_ingestion', side_effect=Exception("Pipeline error")):
            result = await check.run_check()
        
        assert result.status == "fail"
        assert "Content pipeline monitoring failed with error: Pipeline error" in result.message
        assert result.details["error"] == "Pipeline error"
    
    @pytest.mark.asyncio
    async def test_default_test_samples(self, check: ContentPipelineMonitoring) -> None:
        """Test default test content samples."""
        # Test with default configuration
        default_config = SentinelConfig({})
        default_check = ContentPipelineMonitoring(default_config)
        
        assert len(default_check.test_content_samples) == 5
        
        # Verify structure of default samples
        for sample in default_check.test_content_samples:
            assert "type" in sample
            assert "content" in sample
            assert "expected_features" in sample
            assert "text" in sample["content"]
            assert "title" in sample["content"]
    
    @pytest.mark.asyncio
    async def test_storage_consistency_failures(self, check: ContentPipelineMonitoring) -> None:
        """Test storage consistency with retrieval failures."""
        # Mock successful storage but failed retrieval
        mock_store_response = AsyncMock()
        mock_store_response.status = 201
        mock_store_response.json = AsyncMock(return_value={"context_id": "test_ctx_123"})
        
        mock_get_response = AsyncMock()
        mock_get_response.status = 404  # Not found
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_store_response
        mock_session.get.return_value.__aenter__.return_value = mock_get_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('asyncio.sleep', return_value=None):
                result = await check._validate_storage_consistency()
        
        assert result["passed"] is False
        assert result["consistency_ratio"] < 0.95  # Below threshold
        assert result["successful_retrievals"] == 0
    
    @pytest.mark.asyncio
    async def test_lifecycle_creation_failure(self, check: ContentPipelineMonitoring) -> None:
        """Test content lifecycle with creation failure."""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_content_lifecycle()
        
        assert result["passed"] is False
        assert "Content lifecycle test failed at creation stage" in result["message"]
        assert len(result["lifecycle_stages"]) == 1
        assert result["lifecycle_stages"][0]["successful"] is False