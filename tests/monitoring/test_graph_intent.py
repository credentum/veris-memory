#!/usr/bin/env python3
"""
Unit tests for S9 Graph Intent Validation Check.

Tests the GraphIntentValidation check with mocked HTTP calls and graph analysis.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp

from src.monitoring.sentinel.checks.s9_graph_intent import GraphIntentValidation
from src.monitoring.sentinel.models import SentinelConfig


class TestGraphIntentValidation:
    """Test suite for GraphIntentValidation check."""
    
    @pytest.fixture
    def config(self) -> SentinelConfig:
        """Create a test configuration."""
        return SentinelConfig({
            "veris_memory_url": "http://test.example.com:8000",
            "s9_graph_timeout_sec": 30,
            "s9_max_traversal_depth": 3,
            "s9_graph_sample_size": 10,
            "s9_intent_scenarios": [
                {
                    "name": "test_scenario",
                    "description": "Test scenario for validation",
                    "contexts": [
                        "Test context one",
                        "Test context two"
                    ],
                    "expected_relationships": ["test", "context"]
                }
            ]
        })
    
    @pytest.fixture
    def check(self, config: SentinelConfig) -> GraphIntentValidation:
        """Create a GraphIntentValidation check instance."""
        return GraphIntentValidation(config)
    
    @pytest.mark.asyncio
    async def test_initialization(self, config: SentinelConfig) -> None:
        """Test check initialization."""
        check = GraphIntentValidation(config)
        
        assert check.check_id == "S9-graph-intent"
        assert check.description == "Graph intent validation"
        assert check.veris_memory_url == "http://test.example.com:8000"
        assert check.timeout_seconds == 30
        assert check.max_traversal_depth == 3
        assert check.graph_sample_size == 10
        assert len(check.intent_scenarios) == 1
    
    @pytest.mark.asyncio
    async def test_run_check_all_pass(self, check: GraphIntentValidation) -> None:
        """Test run_check when all graph intent tests pass."""
        mock_results = [
            {"passed": True, "message": "Relationship accuracy validated"},
            {"passed": True, "message": "Semantic connectivity confirmed"},
            {"passed": True, "message": "Graph traversal quality verified"},
            {"passed": True, "message": "Context clustering validated"},
            {"passed": True, "message": "Relationship inference successful"},
            {"passed": True, "message": "Graph coherence confirmed"},
            {"passed": True, "message": "Intent preservation validated"}
        ]
        
        with patch.object(check, '_test_relationship_accuracy', return_value=mock_results[0]):
            with patch.object(check, '_validate_semantic_connectivity', return_value=mock_results[1]):
                with patch.object(check, '_test_graph_traversal_quality', return_value=mock_results[2]):
                    with patch.object(check, '_validate_context_clustering', return_value=mock_results[3]):
                        with patch.object(check, '_test_relationship_inference', return_value=mock_results[4]):
                            with patch.object(check, '_validate_graph_coherence', return_value=mock_results[5]):
                                with patch.object(check, '_test_intent_preservation', return_value=mock_results[6]):
                                    
                                    result = await check.run_check()
        
        assert result.check_id == "S9-graph-intent"
        assert result.status == "pass"
        assert "All graph intent validation checks passed: 7 tests successful" in result.message
        assert result.details["total_tests"] == 7
        assert result.details["passed_tests"] == 7
        assert result.details["failed_tests"] == 0
    
    @pytest.mark.asyncio
    async def test_run_check_with_failures(self, check: GraphIntentValidation) -> None:
        """Test run_check when some graph intent tests fail."""
        mock_results = [
            {"passed": False, "message": "Relationship accuracy low"},
            {"passed": False, "message": "Semantic connectivity failed"},
            {"passed": True, "message": "Graph traversal quality verified"},
            {"passed": True, "message": "Context clustering validated"},
            {"passed": True, "message": "Relationship inference successful"},
            {"passed": True, "message": "Graph coherence confirmed"},
            {"passed": True, "message": "Intent preservation validated"}
        ]
        
        with patch.object(check, '_test_relationship_accuracy', return_value=mock_results[0]):
            with patch.object(check, '_validate_semantic_connectivity', return_value=mock_results[1]):
                with patch.object(check, '_test_graph_traversal_quality', return_value=mock_results[2]):
                    with patch.object(check, '_validate_context_clustering', return_value=mock_results[3]):
                        with patch.object(check, '_test_relationship_inference', return_value=mock_results[4]):
                            with patch.object(check, '_validate_graph_coherence', return_value=mock_results[5]):
                                with patch.object(check, '_test_intent_preservation', return_value=mock_results[6]):
                                    
                                    result = await check.run_check()
        
        assert result.status == "fail"
        assert "Graph intent validation issues detected: 2 problems found" in result.message
        assert result.details["passed_tests"] == 5
        assert result.details["failed_tests"] == 2
    
    @pytest.mark.asyncio
    async def test_relationship_accuracy_success(self, check: GraphIntentValidation) -> None:
        """Test successful relationship accuracy analysis."""
        # Mock context storage
        mock_store_response = AsyncMock()
        mock_store_response.status = 201
        mock_store_response.json = AsyncMock(return_value={"context_id": "test_ctx_123"})
        
        # Mock context retrieval
        mock_get_response = AsyncMock()
        mock_get_response.status = 200
        mock_get_response.json = AsyncMock(return_value={
            "content": {"text": "Test context about configuration"}
        })
        
        # Mock search results
        mock_search_response = AsyncMock()
        mock_search_response.status = 200
        mock_search_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "related_ctx", "content": {"text": "Configuration setup guide"}}
            ]
        })
        
        mock_session = AsyncMock()
        
        # Configure different responses for different endpoints
        def mock_request(method, url, **kwargs):
            ctx = AsyncMock()
            if method == "post" and "/contexts" in url and "search" not in url:
                ctx.__aenter__ = AsyncMock(return_value=mock_store_response)
            elif method == "get" and "/contexts/" in url:
                ctx.__aenter__ = AsyncMock(return_value=mock_get_response)
            elif method == "post" and "/search" in url:
                ctx.__aenter__ = AsyncMock(return_value=mock_search_response)
            return ctx
        
        mock_session.post.side_effect = lambda url, **kwargs: mock_request("post", url, **kwargs)
        mock_session.get.side_effect = lambda url, **kwargs: mock_request("get", url, **kwargs)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_relationship_accuracy()
        
        assert result["passed"] is True
        assert "Relationship accuracy" in result["message"]
        assert result["accuracy_score"] >= 0.0
        assert len(result["scenario_results"]) > 0
    
    @pytest.mark.asyncio
    async def test_semantic_connectivity_success(self, check: GraphIntentValidation) -> None:
        """Test successful semantic connectivity validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Database configuration setup"}, "score": 0.9},
                {"context_id": "ctx2", "content": {"text": "Database setup guide"}, "score": 0.8}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_semantic_connectivity()
        
        assert result["passed"] is True
        assert "Semantic connectivity" in result["message"]
        assert result["connectivity_ratio"] >= 0.0
        assert len(result["query_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_graph_traversal_quality_success(self, check: GraphIntentValidation) -> None:
        """Test successful graph traversal quality assessment."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Database configuration and setup"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_graph_traversal_quality()
        
        assert result["passed"] is True
        assert "Graph traversal quality" in result["message"]
        assert result["traversal_ratio"] >= 0.0
        assert len(result["concept_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_context_clustering_success(self, check: GraphIntentValidation) -> None:
        """Test successful context clustering validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Database operations setup"}, "score": 0.9},
                {"context_id": "ctx2", "content": {"text": "Database configuration"}, "score": 0.8}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_context_clustering()
        
        assert result["passed"] is True
        assert "Context clustering quality" in result["message"]
        assert result["clustering_ratio"] >= 0.0
        assert len(result["cluster_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_relationship_inference_success(self, check: GraphIntentValidation) -> None:
        """Test successful relationship inference."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Error handling with logging and monitoring for troubleshooting"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_relationship_inference()
        
        assert result["passed"] is True
        assert "Relationship inference" in result["message"]
        assert result["inference_ratio"] >= 0.0
        assert len(result["inference_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_graph_coherence_success(self, check: GraphIntentValidation) -> None:
        """Test successful graph coherence validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "Database performance monitoring system"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_graph_coherence()
        
        assert result["passed"] is True
        assert "Graph coherence" in result["message"]
        assert result["coherence_ratio"] >= 0.0
        assert len(result["coherence_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_intent_preservation_success(self, check: GraphIntentValidation) -> None:
        """Test successful intent preservation validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "contexts": [
                {"context_id": "ctx1", "content": {"text": "How to troubleshoot database connection issues with proper authentication"}, "score": 0.9}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._test_intent_preservation()
        
        assert result["passed"] is True
        assert "Intent preservation" in result["message"]
        assert result["preservation_ratio"] >= 0.0
        assert len(result["intent_tests"]) > 0
    
    @pytest.mark.asyncio
    async def test_calculate_semantic_coherence(self, check: GraphIntentValidation) -> None:
        """Test semantic coherence calculation."""
        contexts = [
            {"content": {"text": "database configuration setup"}},
            {"content": {"text": "database setup guide"}},
            {"content": {"text": "configuration database"}}
        ]
        query = "database configuration"
        
        coherence = check._calculate_semantic_coherence(contexts, query)
        
        assert 0.0 <= coherence <= 1.0
        # Should have high coherence since all contexts contain query terms
        assert coherence > 0.5
    
    @pytest.mark.asyncio
    async def test_calculate_path_relevance(self, check: GraphIntentValidation) -> None:
        """Test path relevance calculation."""
        source_text = "database configuration setup"
        target_text = "configuration database guide"
        
        relevance = check._calculate_path_relevance(source_text, target_text)
        
        assert 0.0 <= relevance <= 1.0
        # Should have some relevance due to shared terms
        assert relevance > 0.0
    
    @pytest.mark.asyncio
    async def test_analyze_cluster_coherence(self, check: GraphIntentValidation) -> None:
        """Test cluster coherence analysis."""
        contexts = [
            {"content": {"text": "database setup configuration"}},
            {"content": {"text": "database configuration guide"}},
            {"content": {"text": "setup database config"}}
        ]
        query = "database configuration"
        
        coherence = check._analyze_cluster_coherence(contexts, query)
        
        assert 0.0 <= coherence <= 1.0
        # Should have decent coherence for related contexts
        assert coherence > 0.0
    
    @pytest.mark.asyncio
    async def test_evaluate_inference_quality(self, check: GraphIntentValidation) -> None:
        """Test inference quality evaluation."""
        contexts = [
            {"content": {"text": "error handling with logging and monitoring for troubleshooting"}},
            {"content": {"text": "debugging system with monitoring tools"}}
        ]
        related_concepts = ["logging", "monitoring", "debugging"]
        expected_inference = "troubleshooting"
        
        quality = check._evaluate_inference_quality(contexts, related_concepts, expected_inference)
        
        assert 0.0 <= quality <= 1.0
        # Should have high quality since most concepts are present
        assert quality > 0.5
    
    @pytest.mark.asyncio
    async def test_calculate_cross_domain_coherence(self, check: GraphIntentValidation) -> None:
        """Test cross-domain coherence calculation."""
        contexts = [
            {"content": {"text": "database performance monitoring system"}},
            {"content": {"text": "monitoring database performance"}}
        ]
        query = "database performance monitoring"
        
        coherence = check._calculate_cross_domain_coherence(contexts, query)
        
        assert 0.0 <= coherence <= 1.0
        # Should have high coherence for comprehensive coverage
        assert coherence > 0.5
    
    @pytest.mark.asyncio
    async def test_calculate_intent_preservation(self, check: GraphIntentValidation) -> None:
        """Test intent preservation calculation."""
        contexts = [
            {"content": {"text": "troubleshoot database connection authentication issues"}},
            {"content": {"text": "database authentication troubleshooting guide"}}
        ]
        key_concepts = ["database", "connection", "troubleshoot"]
        
        preservation = check._calculate_intent_preservation(contexts, key_concepts)
        
        assert 0.0 <= preservation <= 1.0
        # Should be 1.0 since all key concepts are present
        assert preservation == 1.0
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, check: GraphIntentValidation) -> None:
        """Test handling of API errors."""
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientError("Connection failed")
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await check._validate_semantic_connectivity()
        
        assert result["passed"] is False
        assert "error" in result
        assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_empty_contexts_handling(self, check: GraphIntentValidation) -> None:
        """Test handling of empty context results."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"contexts": []})
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aender__.return_value = mock_response
        
        # Test semantic coherence with empty contexts
        coherence = check._calculate_semantic_coherence([], "test query")
        assert coherence == 0.0
        
        # Test path relevance with empty text
        relevance = check._calculate_path_relevance("", "test text")
        assert relevance == 0.0
        
        # Test intent preservation with empty contexts
        preservation = check._calculate_intent_preservation([], ["test"])
        assert preservation == 0.0
    
    @pytest.mark.asyncio
    async def test_analyze_traversal_paths_no_results(self, check: GraphIntentValidation) -> None:
        """Test traversal path analysis with no initial results."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"contexts": []})
        
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        
        quality = await check._analyze_traversal_paths(mock_session, "nonexistent", 3)
        
        assert quality == 0.0
    
    @pytest.mark.asyncio
    async def test_run_check_with_exception(self, check: GraphIntentValidation) -> None:
        """Test run_check when an exception occurs."""
        with patch.object(check, '_test_relationship_accuracy', side_effect=Exception("Graph error")):
            result = await check.run_check()
        
        assert result.status == "fail"
        assert "Graph intent validation failed with error: Graph error" in result.message
        assert result.details["error"] == "Graph error"
    
    @pytest.mark.asyncio
    async def test_default_intent_scenarios(self, check: GraphIntentValidation) -> None:
        """Test default intent scenarios configuration."""
        # Test with default configuration
        default_config = SentinelConfig({})
        default_check = GraphIntentValidation(default_config)
        
        assert len(default_check.intent_scenarios) == 5
        
        # Verify structure of default scenarios
        for scenario in default_check.intent_scenarios:
            assert "name" in scenario
            assert "description" in scenario
            assert "contexts" in scenario
            assert "expected_relationships" in scenario
            assert len(scenario["contexts"]) >= 3
            assert len(scenario["expected_relationships"]) >= 3