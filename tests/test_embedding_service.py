"""
Comprehensive test suite for embedding service.

Tests all phases of the embedding fix implementation:
- Phase 1: Basic functionality
- Phase 2: Robust implementation with retries and error handling  
- Phase 3: Health monitoring and metrics
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any

from src.embedding import (
    EmbeddingService,
    EmbeddingConfig, 
    EmbeddingModel,
    EmbeddingError,
    ModelLoadError,
    DimensionMismatchError,
    generate_embedding
)

class TestPhase1BasicFunctionality:
    """Test Phase 1: Basic embedding functionality and dimension fixes."""
    
    @pytest.mark.asyncio
    async def test_dimension_padding(self):
        """Test that embeddings are padded to correct dimensions."""
        config = EmbeddingConfig(
            model=EmbeddingModel.MINI_LM_L6_V2,  # 384 dimensions
            target_dimensions=1536
        )
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            # Mock model that returns 384-dim embedding
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = [0.1] * 384  # 384 dimensions
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            embedding = await service.generate_embedding("test text")
            
            # Should be padded to 1536 dimensions
            assert len(embedding) == 1536
            assert embedding[:384] == [0.1] * 384  # Original values
            assert embedding[384:] == [0.0] * (1536 - 384)  # Padding
    
    @pytest.mark.asyncio
    async def test_dimension_truncation(self):
        """Test that embeddings are truncated when too large."""
        config = EmbeddingConfig(
            model=EmbeddingModel.OPENAI_3_LARGE,  # 3072 dimensions
            target_dimensions=1536
        )
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            # Mock model that returns 3072-dim embedding
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 3072
            mock_model.encode.return_value = list(range(3072))  # 0, 1, 2, ..., 3071
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            embedding = await service.generate_embedding("test text")
            
            # Should be truncated to 1536 dimensions
            assert len(embedding) == 1536
            assert embedding == list(range(1536))  # First 1536 values
    
    @pytest.mark.asyncio
    async def test_no_adjustment_when_disabled(self):
        """Test that dimension adjustment can be disabled."""
        config = EmbeddingConfig(target_dimensions=1536)
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = [0.1] * 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # Disable dimension adjustment
            embedding = await service.generate_embedding("test", adjust_dimensions=False)
            
            # Should keep original 384 dimensions
            assert len(embedding) == 384

class TestPhase2RobustImplementation:
    """Test Phase 2: Retry logic, error handling, and configuration."""
    
    @pytest.mark.asyncio
    async def test_retry_logic_success_after_failure(self):
        """Test that retry logic works when embedding fails initially."""
        config = EmbeddingConfig(max_retries=3)
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            
            # Fail twice, then succeed
            mock_model.encode.side_effect = [
                Exception("Connection error"),
                Exception("Timeout"),
                [0.1] * 384  # Success on third try
            ]
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            start_time = time.time()
            embedding = await service.generate_embedding("test text")
            elapsed = time.time() - start_time
            
            # Should succeed after retries
            assert len(embedding) == 1536  # With padding
            # Should have taken time for retries (exponential backoff: 1s + 2s)
            assert elapsed >= 3.0
            
            # Should have called encode 3 times
            assert mock_model.encode.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test that error is raised when all retries are exhausted."""
        config = EmbeddingConfig(max_retries=2)
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.side_effect = Exception("Persistent error")
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            with pytest.raises(EmbeddingError, match="All 2 attempts failed"):
                await service.generate_embedding("test text")
    
    @pytest.mark.asyncio 
    async def test_caching(self):
        """Test that caching works correctly."""
        config = EmbeddingConfig(cache_enabled=True)
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = [0.1] * 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # First call
            embedding1 = await service.generate_embedding("same text")
            
            # Second call with same text
            embedding2 = await service.generate_embedding("same text")
            
            # Should be identical and model should only be called once
            assert embedding1 == embedding2
            assert mock_model.encode.call_count == 1
            
            # Metrics should show cache hit
            metrics = service.get_health_status()["metrics"]
            assert metrics["cache_hits"] == 1
    
    @pytest.mark.asyncio
    async def test_text_extraction_from_dict(self):
        """Test text extraction from structured content."""
        config = EmbeddingConfig()
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = [0.1] * 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # Test with structured content
            content = {
                "title": "Test Title",
                "description": "Test Description", 
                "body": "Test Body",
                "other_field": "ignored"
            }
            
            await service.generate_embedding(content)
            
            # Should extract and combine title, description, body
            expected_text = "Test Title Test Description Test Body"
            mock_model.encode.assert_called_with(expected_text, convert_to_tensor=False)

class TestPhase3HealthAndMonitoring:
    """Test Phase 3: Health checks, metrics, and monitoring."""
    
    @pytest.mark.asyncio
    async def test_health_status_healthy(self):
        """Test health status when service is working."""
        config = EmbeddingConfig()
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # Generate some embeddings to populate metrics
            mock_model.encode.return_value = [0.1] * 384
            await service.generate_embedding("test 1")
            await service.generate_embedding("test 2")
            
            health = service.get_health_status()
            
            assert health["status"] == "healthy"
            assert health["model_loaded"] is True
            assert health["model_dimensions"] == 384
            assert health["target_dimensions"] == 1536
            assert health["metrics"]["total_requests"] == 2
            assert health["metrics"]["successful_requests"] == 2
            assert health["metrics"]["failed_requests"] == 0
    
    @pytest.mark.asyncio
    async def test_health_status_unhealthy(self):
        """Test health status when model fails to load."""
        config = EmbeddingConfig()
        
        with patch('sentence_transformers.SentenceTransformer', side_effect=ImportError("No module")):
            service = EmbeddingService(config)
            
            with pytest.raises(ModelLoadError):
                await service.initialize()
            
            health = service.get_health_status()
            
            assert health["status"] == "critical"
            assert health["model_loaded"] is False
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Test that metrics are properly tracked."""
        config = EmbeddingConfig(max_retries=2)
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            service = EmbeddingService(config)
            await service.initialize()
            
            # One successful embedding
            mock_model.encode.return_value = [0.1] * 384
            await service.generate_embedding("success")
            
            # One failed embedding (exhaust retries)
            mock_model.encode.side_effect = Exception("Error")
            try:
                await service.generate_embedding("failure")
            except EmbeddingError:
                pass
            
            metrics = service.get_health_status()["metrics"]
            
            assert metrics["total_requests"] == 2
            assert metrics["successful_requests"] == 1
            assert metrics["failed_requests"] == 1
            assert metrics["average_generation_time"] > 0
    
    @pytest.mark.asyncio
    async def test_configuration_retrieval(self):
        """Test that configuration can be retrieved."""
        config = EmbeddingConfig(
            model=EmbeddingModel.MINI_LM_L6_V2,
            target_dimensions=1536,
            max_retries=5,
            cache_enabled=True
        )
        
        service = EmbeddingService(config)
        config_dict = service.get_configuration()
        
        assert config_dict["model"] == "all-MiniLM-L6-v2"
        assert config_dict["target_dimensions"] == 1536
        assert config_dict["max_retries"] == 5
        assert config_dict["cache_enabled"] is True

class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_storage_scenario(self):
        """Test complete storage scenario with embedding service."""
        # This would test the actual MCP server integration
        # but requires more setup, so just test the interface
        
        test_content = {
            "text": "Testing end-to-end embedding storage",
            "file_path": "test.py",
            "repository": "veris-memory"
        }
        
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = [0.1] * 384
            mock_st.return_value = mock_model
            
            # Test the convenience function
            embedding = await generate_embedding(test_content)
            
            # Should return properly sized embedding
            assert len(embedding) == 1536
            assert isinstance(embedding, list)
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_dimension_compatibility_validation(self):
        """Test validation of dimension compatibility."""
        # Test various model/target combinations
        test_cases = [
            (EmbeddingModel.MINI_LM_L6_V2, 1536, True),   # Needs padding
            (EmbeddingModel.OPENAI_ADA_002, 1536, True),  # Perfect match
            (EmbeddingModel.OPENAI_3_LARGE, 1536, True),  # Needs truncation
        ]
        
        for model, target_dims, should_work in test_cases:
            config = EmbeddingConfig(model=model, target_dimensions=target_dims)
            
            with patch('sentence_transformers.SentenceTransformer') as mock_st:
                mock_model = Mock()
                mock_model.get_sentence_embedding_dimension.return_value = model.value[1]
                mock_model.encode.return_value = [0.1] * model.value[1]
                mock_st.return_value = mock_model
                
                service = EmbeddingService(config)
                await service.initialize()
                
                embedding = await service.generate_embedding("test")
                
                if should_work:
                    assert len(embedding) == target_dims
                    
                    # Verify health status
                    health = service.get_health_status()
                    assert health["status"] == "healthy"

# Run tests with: pytest tests/test_embedding_service.py -v