"""
Embedding Service for Veris Memory.

Provides a robust, configurable embedding generation service that handles:
- Multiple embedding models with automatic dimension adjustment
- Retry logic for failed embedding generation
- Caching for performance optimization
- Health monitoring and metrics
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union, OrderedDict
from dataclasses import dataclass
from enum import Enum
from collections import OrderedDict

# OpenTelemetry imports with fallback
try:
    from opentelemetry import trace, metrics
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    # Create dummy classes for when OpenTelemetry is not available
    class DummyStatus:
        def __init__(self, status_code, description=""):
            pass
    
    class DummyStatusCode:
        OK = "OK"
        ERROR = "ERROR"
    
    Status = DummyStatus
    StatusCode = DummyStatusCode
    
    class DummyTracer:
        def start_span(self, name, **kwargs):
            return DummySpan()
    
    class DummySpan:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def set_attribute(self, key, value):
            pass
        def set_status(self, status):
            pass
    
    class DummyMeter:
        def create_counter(self, name, **kwargs):
            return DummyCounter()
        def create_histogram(self, name, **kwargs):
            return DummyHistogram()
    
    class DummyCounter:
        def add(self, value, attributes=None):
            pass
    
    class DummyHistogram:
        def record(self, value, attributes=None):
            pass

logger = logging.getLogger(__name__)

class EmbeddingModel(Enum):
    """Supported embedding models with their dimensions."""
    MINI_LM_L6_V2 = ("all-MiniLM-L6-v2", 384)
    OPENAI_ADA_002 = ("text-embedding-ada-002", 1536)
    OPENAI_3_SMALL = ("text-embedding-3-small", 1536)
    OPENAI_3_LARGE = ("text-embedding-3-large", 3072)

@dataclass
class EmbeddingConfig:
    """Configuration for embedding service."""
    model: EmbeddingModel = EmbeddingModel.MINI_LM_L6_V2
    target_dimensions: int = 1536
    max_retries: int = 3
    timeout_seconds: float = 30.0
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    cache_max_memory_mb: int = 100
    batch_size: int = 100

class EmbeddingError(Exception):
    """Base exception for embedding operations."""
    pass

class ModelLoadError(EmbeddingError):
    """Error loading embedding model."""
    pass

class DimensionMismatchError(EmbeddingError):
    """Error with embedding dimensions."""
    pass

class EmbeddingService:
    """
    Robust embedding service with automatic dimension adjustment.
    
    Features:
    - Multiple model support with automatic fallback
    - Dimension padding/truncation for compatibility
    - Retry logic with exponential backoff
    - Performance monitoring and caching
    - Health checks and diagnostics
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._model = None
        self._model_loaded = False
        self._cache = OrderedDict() if self.config.cache_enabled else None
        self._cache_memory_usage = 0  # Track memory usage in bytes
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "cache_evictions": 0,
            "cache_memory_usage_mb": 0.0,
            "average_generation_time": 0.0,
            "model_load_time": None
        }
        
        # Initialize OpenTelemetry instrumentation
        if OTEL_AVAILABLE:
            self._tracer = trace.get_tracer(__name__)
            self._meter = metrics.get_meter(__name__)
            self._embedding_counter = self._meter.create_counter(
                "embedding_requests_total",
                description="Total number of embedding requests"
            )
            self._embedding_duration = self._meter.create_histogram(
                "embedding_generation_duration_seconds",
                description="Time taken to generate embeddings"
            )
            self._cache_counter = self._meter.create_counter(
                "embedding_cache_operations_total", 
                description="Total cache operations"
            )
        else:
            self._tracer = DummyTracer()
            self._meter = DummyMeter()
            self._embedding_counter = DummyCounter()
            self._embedding_duration = DummyHistogram()
            self._cache_counter = DummyCounter()
        
    async def initialize(self) -> bool:
        """
        Initialize the embedding service.
        
        Returns:
            bool: True if initialization successful
            
        Raises:
            ModelLoadError: If model cannot be loaded
        """
        start_time = time.time()
        
        try:
            logger.info(f"Loading embedding model: {self.config.model.value[0]}")
            
            # Try to load sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer
                model_name = self.config.model.value[0]
                self._model = SentenceTransformer(model_name)
                self._model_loaded = True
                
                load_time = time.time() - start_time
                self._metrics["model_load_time"] = load_time
                
                logger.info(
                    f"Successfully loaded model {model_name} "
                    f"in {load_time:.2f}s with {self.get_model_dimensions()} dimensions"
                )
                return True
                
            except ImportError as e:
                logger.error(f"sentence-transformers not available: {e}")
                raise ModelLoadError("sentence-transformers package not installed")
                
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            raise ModelLoadError(f"Model initialization failed: {e}")
    
    def get_model_dimensions(self) -> int:
        """Get the actual dimensions of the loaded model."""
        if not self._model_loaded or not self._model:
            return 0
        
        try:
            return self._model.get_sentence_embedding_dimension()
        except Exception:
            return self.config.model.value[1]  # Fallback to expected dimensions
    
    def get_target_dimensions(self) -> int:
        """Get the target dimensions for output."""
        return self.config.target_dimensions
    
    async def generate_embedding(
        self, 
        content: Union[str, Dict[str, Any]], 
        adjust_dimensions: bool = True
    ) -> List[float]:
        """
        Generate embedding with automatic dimension adjustment.
        
        Args:
            content: Text or structured content to embed
            adjust_dimensions: Whether to pad/truncate to target dimensions
            
        Returns:
            List[float]: Embedding vector
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        start_time = time.time()
        self._metrics["total_requests"] += 1
        
        # OpenTelemetry tracing
        with self._tracer.start_span("embedding.generate") as span:
            try:
                span.set_attribute("embedding.model", self.config.model.value[0])
                span.set_attribute("embedding.adjust_dimensions", adjust_dimensions)
                
                # Extract text from content
                text = self._extract_text(content)
                span.set_attribute("embedding.text_length", len(text))
                
                # Check cache first
                cache_hit = False
                if self._cache is not None:
                    cache_key = self._get_cache_key(text)
                    cached_embedding = self._get_from_cache(cache_key)
                    if cached_embedding is not None:
                        self._metrics["cache_hits"] += 1
                        cache_hit = True
                        span.set_attribute("embedding.cache_hit", True)
                        self._cache_counter.add(1, {"operation": "hit"})
                        return cached_embedding
                
                span.set_attribute("embedding.cache_hit", False)
                self._cache_counter.add(1, {"operation": "miss"})
                
                # Generate embedding with retries
                embedding = await self._generate_with_retries(text)
                
                # Adjust dimensions if requested
                if adjust_dimensions:
                    original_dims = len(embedding)
                    embedding = self._adjust_dimensions(embedding)
                    span.set_attribute("embedding.original_dimensions", original_dims)
                    span.set_attribute("embedding.final_dimensions", len(embedding))
                
                # Cache the result
                if self._cache is not None:
                    self._store_in_cache(cache_key, embedding)
                
                # Update metrics and OpenTelemetry
                generation_time = time.time() - start_time
                self._update_metrics(generation_time, success=True)
                
                span.set_attribute("embedding.generation_time_seconds", generation_time)
                span.set_status(Status(StatusCode.OK))
                
                # Record metrics
                self._embedding_counter.add(1, {"status": "success", "cache_hit": str(cache_hit)})
                self._embedding_duration.record(generation_time, {"status": "success"})
                
                logger.debug(f"Generated embedding in {generation_time:.3f}s")
                return embedding
                
            except Exception as e:
                generation_time = time.time() - start_time
                self._update_metrics(generation_time, success=False)
                
                # OpenTelemetry error handling
                span.set_attribute("embedding.error", str(e))
                span.set_status(Status(StatusCode.ERROR, str(e)))
                
                self._embedding_counter.add(1, {"status": "error"})
                self._embedding_duration.record(generation_time, {"status": "error"})
                
                logger.error(f"Embedding generation failed: {e}")
                raise EmbeddingError(f"Failed to generate embedding: {e}")
    
    async def _generate_with_retries(self, text: str) -> List[float]:
        """Generate embedding with retry logic."""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                if not self._model_loaded:
                    await self.initialize()
                
                # Generate embedding
                embedding = self._model.encode(text, convert_to_tensor=False)
                
                # Convert to list
                if hasattr(embedding, "tolist"):
                    embedding = embedding.tolist()
                else:
                    embedding = list(embedding)
                
                return embedding
                
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    f"Embedding generation attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
        
        raise EmbeddingError(f"All {self.config.max_retries} attempts failed. Last error: {last_error}")
    
    def _extract_text(self, content: Union[str, Dict[str, Any]]) -> str:
        """Extract text from content for embedding."""
        if isinstance(content, str):
            return content
        
        if isinstance(content, dict):
            # Extract meaningful text from structured content
            text_parts = []
            
            # Common text fields
            for field in ["title", "description", "text", "content", "body"]:
                if field in content and content[field]:
                    text_parts.append(str(content[field]))
            
            # If no text found, use JSON representation
            if not text_parts:
                import json
                text_parts = [json.dumps(content, sort_keys=True)]
            
            return " ".join(text_parts)
        
        return str(content)
    
    def _adjust_dimensions(self, embedding: List[float]) -> List[float]:
        """Adjust embedding dimensions to target size."""
        current_dim = len(embedding)
        target_dim = self.config.target_dimensions
        
        if current_dim == target_dim:
            return embedding
        
        if current_dim < target_dim:
            # Pad with zeros
            padding = [0.0] * (target_dim - current_dim)
            adjusted = embedding + padding
            logger.debug(f"Padded embedding from {current_dim} to {target_dim} dimensions")
            return adjusted
        
        else:
            # Truncate
            adjusted = embedding[:target_dim]
            logger.debug(f"Truncated embedding from {current_dim} to {target_dim} dimensions")
            return adjusted
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[List[float]]:
        """Get embedding from LRU cache."""
        if self._cache is None or key not in self._cache:
            return None
            
        entry = self._cache[key]
        
        # Check TTL
        if time.time() - entry["timestamp"] >= self.config.cache_ttl_seconds:
            self._remove_from_cache(key)
            return None
        
        # Move to end (mark as recently used)
        self._cache.move_to_end(key)
        return entry["embedding"]
    
    def _store_in_cache(self, key: str, embedding: List[float]) -> None:
        """Store embedding in LRU cache with memory management."""
        if self._cache is None:
            return
            
        # Calculate memory usage (rough estimate)
        entry_size = len(embedding) * 8 + 64  # 8 bytes per float + overhead
        
        # Store entry
        entry = {
            "embedding": embedding,
            "timestamp": time.time(),
            "size_bytes": entry_size
        }
        
        # Remove if already exists to update memory tracking
        if key in self._cache:
            self._remove_from_cache(key)
            
        self._cache[key] = entry
        self._cache_memory_usage += entry_size
        
        # Evict entries if necessary
        self._evict_if_necessary()
    
    def _remove_from_cache(self, key: str) -> None:
        """Remove entry from cache and update memory tracking."""
        if self._cache is None or key not in self._cache:
            return
            
        entry = self._cache[key]
        self._cache_memory_usage -= entry.get("size_bytes", 0)
        del self._cache[key]
        self._metrics["cache_evictions"] += 1
    
    def _evict_if_necessary(self) -> None:
        """Evict entries if cache exceeds size or memory limits."""
        if self._cache is None:
            return
        
        max_memory_bytes = self.config.cache_max_memory_mb * 1024 * 1024
        
        # Evict based on size limit or memory limit
        while (len(self._cache) > self.config.cache_max_size or 
               self._cache_memory_usage > max_memory_bytes):
            if not self._cache:
                break
                
            # Remove oldest entry (LRU)
            oldest_key = next(iter(self._cache))
            self._remove_from_cache(oldest_key)
    
    def _update_metrics(self, generation_time: float, success: bool) -> None:
        """Update performance metrics."""
        if success:
            self._metrics["successful_requests"] += 1
        else:
            self._metrics["failed_requests"] += 1
        
        # Update average generation time (simple moving average)
        total_successful = self._metrics["successful_requests"]
        if total_successful > 0:
            current_avg = self._metrics["average_generation_time"]
            self._metrics["average_generation_time"] = (
                (current_avg * (total_successful - 1) + generation_time) / total_successful
            )
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health and performance metrics with alerting thresholds."""
        # Calculate derived metrics for alerting
        total_requests = self._metrics["total_requests"]
        failed_requests = self._metrics["failed_requests"]
        
        # Calculate error rate
        error_rate = (failed_requests / total_requests) if total_requests > 0 else 0.0
        
        # Calculate cache hit rate
        cache_hit_rate = (self._metrics["cache_hits"] / total_requests) if total_requests > 0 else 0.0
        
        # Update cache memory usage metric
        self._metrics["cache_memory_usage_mb"] = self._cache_memory_usage / (1024 * 1024) if self._cache else 0.0
        
        # Determine alert levels
        alerts = []
        if not self._model_loaded:
            alerts.append({"level": "critical", "message": "Embedding model not loaded"})
        if error_rate > 0.1:  # > 10% error rate
            alerts.append({"level": "warning", "message": f"High error rate: {error_rate:.1%}"})
        if total_requests > 10 and cache_hit_rate < 0.2:  # < 20% cache hit rate with enough requests
            alerts.append({"level": "info", "message": f"Low cache efficiency: {cache_hit_rate:.1%}"})
        if self._metrics["average_generation_time"] > 5.0:  # > 5 seconds average
            alerts.append({"level": "warning", "message": f"High latency: {self._metrics['average_generation_time']:.1f}s"})
            
        # Determine overall status
        has_critical = any(alert["level"] == "critical" for alert in alerts)
        has_warning = any(alert["level"] == "warning" for alert in alerts)
        
        if has_critical:
            status = "critical"
        elif has_warning:
            status = "warning"
        elif not self._model_loaded:
            status = "unhealthy"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "model_loaded": self._model_loaded,
            "model_name": self.config.model.value[0] if self._model_loaded else None,
            "model_dimensions": self.get_model_dimensions(),
            "target_dimensions": self.config.target_dimensions,
            "cache_enabled": self.config.cache_enabled,
            "cache_size": len(self._cache) if self._cache else 0,
            "metrics": {
                **self._metrics.copy(),
                "error_rate": error_rate,
                "cache_hit_rate": cache_hit_rate
            },
            "alerts": alerts,
            "thresholds": {
                "max_error_rate": 0.1,
                "min_cache_hit_rate": 0.2,
                "max_average_latency": 5.0
            }
        }
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get current service configuration."""
        return {
            "model": self.config.model.value[0],
            "target_dimensions": self.config.target_dimensions,
            "max_retries": self.config.max_retries,
            "timeout_seconds": self.config.timeout_seconds,
            "cache_enabled": self.config.cache_enabled,
            "cache_ttl_seconds": self.config.cache_ttl_seconds,
            "batch_size": self.config.batch_size
        }

# Global service instance
_embedding_service: Optional[EmbeddingService] = None

async def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        await _embedding_service.initialize()
    
    return _embedding_service

async def generate_embedding(
    content: Union[str, Dict[str, Any]], 
    adjust_dimensions: bool = True
) -> List[float]:
    """
    Convenience function to generate embeddings.
    
    Args:
        content: Content to embed
        adjust_dimensions: Whether to adjust dimensions
        
    Returns:
        List[float]: Embedding vector
    """
    service = await get_embedding_service()
    return await service.generate_embedding(content, adjust_dimensions)