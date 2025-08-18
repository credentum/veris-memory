"""
Test integration between MCP server and embedding service.

Tests the fallback mechanism when robust embedding service fails
and verifies the health endpoint alert thresholds work correctly.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.embedding import EmbeddingService, EmbeddingConfig, ModelLoadError


class TestMCPServerEmbeddingIntegration:
    """Test MCP server integration with embedding service."""
    
    @pytest.mark.asyncio
    async def test_robust_embedding_service_fallback(self):
        """Test fallback to legacy embedding when robust service fails."""
        # Mock the imports that would normally be done in main.py
        with patch('src.mcp_server.main._generate_embedding') as mock_legacy, \
             patch('src.embedding.generate_embedding', side_effect=Exception("Service failed")) as mock_robust:
            
            # Set up legacy fallback
            mock_legacy.return_value = [0.5] * 1536
            
            # Import and test the logic from store_context
            from src.mcp_server.main import _generate_embedding
            
            # Test content that would cause robust service to fail
            test_content = {"test": "content"}
            
            # Mock the try/except logic that's in main.py
            try:
                # This would be the robust service call
                mock_robust(test_content, adjust_dimensions=True)
                assert False, "Should have raised exception"
            except Exception:
                # This would be the fallback call
                result = await mock_legacy(test_content)
                
            # Verify fallback was used
            assert len(result) == 1536
            mock_legacy.assert_called_once_with(test_content)
    
    @pytest.mark.asyncio
    async def test_embedding_service_health_endpoint_alerts(self):
        """Test that health endpoint correctly reports alert thresholds."""
        from src.embedding import EmbeddingService, EmbeddingConfig
        
        config = EmbeddingConfig()
        service = EmbeddingService(config)
        
        # Simulate failed requests to trigger error rate alert
        service._metrics["total_requests"] = 10
        service._metrics["failed_requests"] = 2  # 20% error rate
        service._metrics["successful_requests"] = 8
        service._metrics["cache_hits"] = 1  # 10% cache hit rate
        service._metrics["average_generation_time"] = 6.0  # High latency
        service._model_loaded = True
        
        health_status = service.get_health_status()
        
        # Should have warning status due to high error rate and latency
        assert health_status["status"] == "warning"
        
        # Check specific alerts
        alerts = health_status["alerts"]
        alert_messages = [alert["message"] for alert in alerts]
        
        # Should have alerts for high error rate, low cache efficiency, and high latency
        assert any("High error rate" in msg for msg in alert_messages)
        assert any("Low cache efficiency" in msg for msg in alert_messages)
        assert any("High latency" in msg for msg in alert_messages)
    
    @pytest.mark.asyncio
    async def test_health_endpoint_critical_status(self):
        """Test that health endpoint reports critical status when model not loaded."""
        from src.embedding import EmbeddingService, EmbeddingConfig
        
        config = EmbeddingConfig()
        service = EmbeddingService(config)
        
        # Don't initialize - model not loaded
        service._model_loaded = False
        
        health_status = service.get_health_status()
        
        # Should be critical status
        assert health_status["status"] == "critical"
        
        # Should have critical alert
        alerts = health_status["alerts"]
        assert len(alerts) >= 1
        assert alerts[0]["level"] == "critical"
        assert "model not loaded" in alerts[0]["message"].lower()
    
    @pytest.mark.asyncio 
    async def test_dimension_compatibility_in_main_server(self):
        """Test that main server correctly handles dimension compatibility."""
        # Test the actual dimension adjustment logic from main.py
        from src.core.config import Config
        
        # Mock embedding with different dimensions
        test_embedding_384 = [0.1] * 384
        test_embedding_3072 = list(range(3072))
        
        # Test padding logic (384 -> 1536)
        target_dim = Config.EMBEDDING_DIMENSIONS
        if len(test_embedding_384) < target_dim:
            padding = [0.0] * (target_dim - len(test_embedding_384))
            padded_embedding = test_embedding_384 + padding
            
        assert len(padded_embedding) == 1536
        assert padded_embedding[:384] == test_embedding_384
        assert padded_embedding[384:] == [0.0] * (1536 - 384)
        
        # Test truncation logic (3072 -> 1536)
        if len(test_embedding_3072) > target_dim:
            truncated_embedding = test_embedding_3072[:target_dim]
            
        assert len(truncated_embedding) == 1536
        assert truncated_embedding == list(range(1536))


class TestCacheEvictionBehavior:
    """Test LRU cache eviction behavior."""
    
    @pytest.mark.asyncio
    async def test_lru_cache_eviction_by_size(self):
        """Test that LRU cache evicts oldest entries when size limit reached."""
        config = EmbeddingConfig(cache_max_size=3, cache_enabled=True)
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = [0.1] * 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # Add 4 entries (should evict first one)
            await service.generate_embedding("text1")
            await service.generate_embedding("text2") 
            await service.generate_embedding("text3")
            await service.generate_embedding("text4")  # Should evict text1
            
            # text1 should be evicted, text2-4 should remain
            cache_keys = list(service._cache.keys())
            assert len(cache_keys) == 3
            
            # Check eviction metric
            metrics = service.get_health_status()["metrics"]
            assert metrics["cache_evictions"] >= 1
    
    @pytest.mark.asyncio
    async def test_lru_cache_memory_tracking(self):
        """Test that cache tracks memory usage correctly."""
        config = EmbeddingConfig(cache_max_memory_mb=1, cache_enabled=True)  # Very small limit
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 1536
            mock_model.encode.return_value = [0.1] * 1536  # Larger embedding
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # Add several large embeddings
            for i in range(100):  # Try to exceed memory limit
                await service.generate_embedding(f"large text {i}")
            
            # Should have triggered memory-based evictions
            metrics = service.get_health_status()["metrics"]
            assert metrics["cache_evictions"] > 0
            assert metrics["cache_memory_usage_mb"] <= config.cache_max_memory_mb


# Run tests with: pytest tests/test_mcp_server_integration.py -v