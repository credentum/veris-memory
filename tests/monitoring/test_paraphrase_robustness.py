#!/usr/bin/env python3
"""
Unit tests for S3 Paraphrase Robustness Check.

Tests the ParaphraseRobustness check with mocked HTTP calls and semantic analysis.
"""

import asyncio
import statistics
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp

from src.monitoring.sentinel.checks.s3_paraphrase_robustness import ParaphraseRobustness
from src.monitoring.sentinel.models import SentinelConfig


class TestParaphraseRobustness:
    """Test suite for ParaphraseRobustness check."""
    
    @pytest.fixture
    def config(self) -> SentinelConfig:
        """Create a test configuration."""
        return SentinelConfig({
            "veris_memory_url": "http://test.example.com:8000",
            "s3_paraphrase_timeout_sec": 30,
            "s3_min_similarity_threshold": 0.7,
            "s3_max_result_variance": 0.3,
            "s3_test_paraphrase_sets": [
                {
                    "topic": "test_configuration",
                    "base_query": "How to configure test settings",
                    "paraphrases": [
                        "Setting up test configuration",
                        "Test setup configuration guide",
                        "Configure testing environment"
                    ],
                    "expected_similarity": 0.8
                }
            ]
        })
    
    @pytest.fixture
    def check(self, config: SentinelConfig) -> ParaphraseRobustness:
        """Create a ParaphraseRobustness check instance."""
        return ParaphraseRobustness(config)
    
    @pytest.mark.asyncio
    async def test_initialization(self, config: SentinelConfig) -> None:
        """Test check initialization."""
        check = ParaphraseRobustness(config)
        
        assert check.check_id == "S3-paraphrase-robustness"
        assert check.description == "Paraphrase robustness for semantic consistency"
        assert check.service_url == "http://test.example.com:8000"
        assert check.timeout_seconds == 30
        assert check.min_similarity_threshold == 0.7
        assert check.max_result_variance == 0.3
        assert len(check.test_paraphrase_sets) == 1
    
    @pytest.mark.asyncio
    async def test_run_check_all_pass(self, check: ParaphraseRobustness) -> None:
        """Test run_check when all semantic tests pass."""
        mock_results = [
            {"passed": True, "message": "Semantic similarity validated"},
            {"passed": True, "message": "Result consistency confirmed"},
            {"passed": True, "message": "Ranking stability verified"},
            {"passed": True, "message": "Context retrieval robust"},
            {"passed": True, "message": "Query expansion effective"},
            {"passed": True, "message": "Response quality consistent"}
        ]

        with patch.object(check, '_test_semantic_similarity', return_value=mock_results[0]):
            with patch.object(check, '_test_result_consistency', return_value=mock_results[1]):
                with patch.object(check, '_test_ranking_stability', return_value=mock_results[2]):
                    with patch.object(check, '_test_context_retrieval_robustness', return_value=mock_results[3]):
                        with patch.object(check, '_test_query_expansion', return_value=mock_results[4]):
                            with patch.object(check, '_test_response_quality_consistency', return_value=mock_results[5]):

                                result = await check.run_check()

        assert result.check_id == "S3-paraphrase-robustness"
        assert result.status == "pass"
        assert "All semantic robustness checks passed: 6 tests successful" in result.message
        assert result.details["total_tests"] == 6
        assert result.details["passed_tests"] == 6
        assert result.details["failed_tests"] == 0
    
    @pytest.mark.asyncio
    async def test_run_check_with_failures(self, check: ParaphraseRobustness) -> None:
        """Test run_check when some semantic tests fail."""
        mock_results = [
            {"passed": False, "message": "Semantic similarity too low"},
            {"passed": False, "message": "Result consistency failed"},
            {"passed": True, "message": "Ranking stability verified"},
            {"passed": True, "message": "Context retrieval robust"},
            {"passed": True, "message": "Query expansion effective"},
            {"passed": True, "message": "Response quality consistent"}
        ]

        with patch.object(check, '_test_semantic_similarity', return_value=mock_results[0]):
            with patch.object(check, '_test_result_consistency', return_value=mock_results[1]):
                with patch.object(check, '_test_ranking_stability', return_value=mock_results[2]):
                    with patch.object(check, '_test_context_retrieval_robustness', return_value=mock_results[3]):
                        with patch.object(check, '_test_query_expansion', return_value=mock_results[4]):
                            with patch.object(check, '_test_response_quality_consistency', return_value=mock_results[5]):

                                result = await check.run_check()

        assert result.status == "fail"
        assert "Semantic robustness issues detected: 2 problems found" in result.message
        assert result.details["passed_tests"] == 4
        assert result.details["failed_tests"] == 2
    
    @pytest.mark.asyncio
    async def test_semantic_similarity_success(self, check: ParaphraseRobustness) -> None:
        """Test successful semantic similarity analysis."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Test configuration guide"}, "score": 0.9},
                {"context_id": "ctx2", "content": {"text": "Configuration setup"}, "score": 0.8}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_semantic_similarity()
        
        assert result["passed"] is True
        assert "Semantic similarity score" in result["message"]
        assert result["avg_similarity_score"] >= 0.0
        assert len(result["paraphrase_analysis"]) > 0
    
    @pytest.mark.asyncio
    async def test_semantic_similarity_low_scores(self, check: ParaphraseRobustness) -> None:
        """Test semantic similarity with low similarity scores."""
        # Mock very different results for paraphrases
        mock_responses = [
            {
                "contexts": [
                    {"context_id": "ctx1", "content": {"text": "Configuration guide"}, "score": 0.9}
                ]
            },
            {
                "contexts": [
                    {"context_id": "ctx2", "content": {"text": "Completely different topic"}, "score": 0.1}
                ]
            }
        ]
        
        response_iter = iter(mock_responses)
        
        def mock_post(*args, **kwargs):
            ctx = AsyncMock()
            response = AsyncMock()
            response.status = 200
            response.json = AsyncMock(return_value=next(response_iter))
            ctx.__aenter__ = AsyncMock(return_value=response)
            return ctx
        
        mock_session = AsyncMock()
        mock_session.post.side_effect = mock_post
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_semantic_similarity()
        
        assert result["passed"] is False
        assert result["avg_similarity_score"] < check.min_similarity_threshold
    
    @pytest.mark.asyncio
    async def test_result_consistency_success(self, check: ParaphraseRobustness) -> None:
        """Test successful result consistency validation."""
        # Mock consistent results across paraphrases
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Configuration guide"}, "score": 0.9},
                {"context_id": "ctx2", "content": {"text": "Setup instructions"}, "score": 0.8}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_result_consistency()
        
        assert result["passed"] is True
        assert "Result consistency score" in result["message"]
        assert result["avg_consistency_score"] >= 0.0
        assert len(result["consistency_analysis"]) > 0
    
    @pytest.mark.asyncio
    async def test_ranking_stability_success(self, check: ParaphraseRobustness) -> None:
        """Test successful ranking stability validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Configuration guide"}, "score": 0.9},
                {"context_id": "ctx2", "content": {"text": "Setup instructions"}, "score": 0.8},
                {"context_id": "ctx3", "content": {"text": "Test setup"}, "score": 0.7}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_ranking_stability()
        
        assert result["passed"] is True
        assert "Ranking stability score" in result["message"]
        assert result["avg_stability_score"] >= 0.0
        assert len(result["stability_analysis"]) > 0
    
    @pytest.mark.asyncio
    async def test_context_retrieval_robustness_success(self, check: ParaphraseRobustness) -> None:
        """Test successful context retrieval robustness."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Configuration guide"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_context_retrieval_robustness()
        
        assert result["passed"] is True
        assert "Context retrieval robustness" in result["message"]
        assert result["avg_robustness_score"] >= 0.0
        assert len(result["robustness_analysis"]) > 0
    
    @pytest.mark.asyncio
    async def test_query_expansion_success(self, check: ParaphraseRobustness) -> None:
        """Test successful query expansion validation."""
        mock_responses = [
            # Simple query response
            {
                "contexts": [
                    {"context_id": "ctx1", "content": {"text": "Configuration"}, "score": 0.8}
                ]
            },
            # Expanded query response
            {
                "contexts": [
                    {"context_id": "ctx1", "content": {"text": "Configuration"}, "score": 0.9},
                    {"context_id": "ctx2", "content": {"text": "Setup guide"}, "score": 0.8}
                ]
            }
        ]
        
        response_iter = iter(mock_responses)
        
        def mock_post(*args, **kwargs):
            ctx = AsyncMock()
            response = AsyncMock()
            response.status = 200
            response.json = AsyncMock(return_value=next(response_iter))
            ctx.__aenter__ = AsyncMock(return_value=response)
            return ctx
        
        mock_session = AsyncMock()
        mock_session.post.side_effect = mock_post
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_query_expansion()
        
        assert result["passed"] is True
        assert "Query expansion effectiveness" in result["message"]
        assert result["avg_expansion_score"] >= 0.0
        assert len(result["expansion_analysis"]) > 0
    
    @pytest.mark.asyncio
    async def test_response_quality_consistency_success(self, check: ParaphraseRobustness) -> None:
        """Test successful response quality consistency."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "High quality response"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_response_quality_consistency()
        
        assert result["passed"] is True
        assert "Response quality consistency" in result["message"]
        assert result["avg_quality_score"] >= 0.0
        assert len(result["quality_analysis"]) > 0
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, check: ParaphraseRobustness) -> None:
        """Test handling of API errors."""
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientError("Connection failed")
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_semantic_similarity()
        
        assert result["passed"] is False
        assert "error" in result
        assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_calculate_result_overlap(self, check: ParaphraseRobustness) -> None:
        """Test result overlap calculation."""
        results1 = [{"context_id": "ctx1"}, {"context_id": "ctx2"}]
        results2 = [{"context_id": "ctx2"}, {"context_id": "ctx3"}]
        
        overlap_ratio = check._calculate_result_overlap(results1, results2)
        
        assert 0.0 <= overlap_ratio <= 1.0
        # Should be 0.5 since 1 out of 2 unique contexts overlap
        assert overlap_ratio == 0.5
    
    @pytest.mark.asyncio
    async def test_calculate_score_correlation(self, check: ParaphraseRobustness) -> None:
        """Test score correlation calculation."""
        scores1 = [0.9, 0.8, 0.7]
        scores2 = [0.85, 0.75, 0.65]
        
        correlation = check._calculate_score_correlation(scores1, scores2)
        
        assert -1.0 <= correlation <= 1.0
        # Should be positive correlation for similar score patterns
        assert correlation > 0.5
    
    @pytest.mark.asyncio
    async def test_calculate_score_correlation_edge_cases(self, check: ParaphraseRobustness) -> None:
        """Test score correlation with edge cases."""
        # Empty lists
        correlation = check._calculate_score_correlation([], [])
        assert correlation == 0.0
        
        # Single values
        correlation = check._calculate_score_correlation([0.5], [0.6])
        assert correlation == 0.0
        
        # Identical values (no variance)
        correlation = check._calculate_score_correlation([0.5, 0.5], [0.6, 0.6])
        assert correlation == 0.0
    
    @pytest.mark.asyncio
    async def test_calculate_ranking_stability(self, check: ParaphraseRobustness) -> None:
        """Test ranking stability calculation."""
        results1 = [
            {"context_id": "ctx1", "score": 0.9},
            {"context_id": "ctx2", "score": 0.8}
        ]
        results2 = [
            {"context_id": "ctx1", "score": 0.85},
            {"context_id": "ctx2", "score": 0.75}
        ]
        
        stability = check._calculate_ranking_stability(results1, results2)
        
        assert 0.0 <= stability <= 1.0
        # Should be 1.0 since ranking order is preserved
        assert stability == 1.0
    
    @pytest.mark.asyncio
    async def test_run_check_with_exception(self, check: ParaphraseRobustness) -> None:
        """Test run_check when an exception occurs."""
        with patch.object(check, '_test_semantic_similarity', side_effect=Exception("Test error")):
            result = await check.run_check()
        
        assert result.status == "fail"
        assert "Paraphrase robustness check failed with error: Test error" in result.message
        assert result.details["error"] == "Test error"
    
    @pytest.mark.asyncio
    async def test_default_paraphrase_sets(self, check: ParaphraseRobustness) -> None:
        """Test default paraphrase sets configuration."""
        # Test with default configuration
        default_config = SentinelConfig({})
        default_check = ParaphraseRobustness(default_config)
        
        assert len(default_check.test_paraphrase_sets) == 5
        
        # Verify structure of default sets
        for paraphrase_set in default_check.test_paraphrase_sets:
            assert "topic" in paraphrase_set
            assert "base_query" in paraphrase_set
            assert "paraphrases" in paraphrase_set
            assert "expected_similarity" in paraphrase_set
            assert len(paraphrase_set["paraphrases"]) == 5
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, check: ParaphraseRobustness) -> None:
        """Test configuration parameter validation."""
        # Test with invalid configuration
        invalid_config = SentinelConfig({
            "s3_min_similarity_threshold": 1.5,  # Invalid > 1.0
            "s3_max_result_variance": -0.1,     # Invalid < 0.0
            "s3_paraphrase_timeout_sec": -5     # Invalid < 0
        })
        
        # Should handle invalid config gracefully
        invalid_check = ParaphraseRobustness(invalid_config)
        assert invalid_check.min_similarity_threshold == 1.5  # Uses provided value
        assert invalid_check.max_result_variance == -0.1     # Uses provided value
        assert invalid_check.timeout_seconds == -5           # Uses provided value