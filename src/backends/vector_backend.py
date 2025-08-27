#!/usr/bin/env python3
"""
Vector backend adapter for Qdrant vector database.

This module implements the BackendSearchInterface for Qdrant vector operations,
providing semantic search capabilities with embedding generation.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional

from ..interfaces.backend_interface import BackendSearchInterface, SearchOptions, BackendHealthStatus, BackendSearchError
from ..interfaces.memory_result import MemoryResult, ResultSource, ContentType
from ..utils.logging_middleware import backend_logger, log_backend_timing


class VectorBackend(BackendSearchInterface):
    """
    Vector search backend implementation using Qdrant.
    
    Provides semantic search capabilities by generating embeddings and
    performing similarity search in vector space.
    """
    
    def __init__(self, qdrant_client, embedding_generator):
        """
        Initialize vector backend.
        
        Args:
            qdrant_client: VectorDBInitializer instance for Qdrant operations
            embedding_generator: Service for generating embeddings from text
        """
        self.client = qdrant_client
        self.embedding_generator = embedding_generator
        self._collection_name = "context_embeddings"  # Default collection
    
    @property
    def backend_name(self) -> str:
        """Return the name of this backend."""
        return "vector"
    
    async def search(self, query: str, options: SearchOptions) -> List[MemoryResult]:
        """
        Search vector database using semantic similarity.
        
        Args:
            query: Search query text
            options: Search configuration options
            
        Returns:
            List of MemoryResult objects sorted by relevance score
            
        Raises:
            BackendSearchError: If vector search operation fails
        """
        async with log_backend_timing(self.backend_name, "search", backend_logger) as metadata:
            try:
                # Generate query embedding
                embed_start = time.time()
                query_vector = await self._generate_query_embedding(query)
                embed_time = (time.time() - embed_start) * 1000
                
                metadata["embedding_time_ms"] = embed_time
                metadata["embedding_dimensions"] = len(query_vector) if query_vector else 0
                
                # Perform vector search
                search_start = time.time()
                raw_results = await self._perform_vector_search(query_vector, options)
                search_time = (time.time() - search_start) * 1000
                
                metadata["search_time_ms"] = search_time
                metadata["raw_result_count"] = len(raw_results)
                
                # Convert to normalized format
                results = self._convert_to_memory_results(raw_results)
                
                # Apply additional filtering if needed
                filtered_results = self._apply_filters(results, options)
                
                metadata["result_count"] = len(filtered_results)
                metadata["top_score"] = filtered_results[0].score if filtered_results else 0.0
                
                backend_logger.info(
                    f"Vector search completed",
                    query_length=len(query),
                    **metadata
                )
                
                return filtered_results
                
            except Exception as e:
                error_msg = f"Vector search failed: {str(e)}"
                backend_logger.error(error_msg, error=str(e))
                raise BackendSearchError(self.backend_name, error_msg, e)
    
    async def health_check(self) -> BackendHealthStatus:
        """
        Check the health of the vector backend.
        
        Returns:
            BackendHealthStatus with current health information
        """
        start_time = time.time()
        
        try:
            # Test basic connectivity
            collections = self.client.get_collections()
            response_time = (time.time() - start_time) * 1000
            
            # Check if our collection exists
            collection_exists = any(
                col.name == self._collection_name 
                for col in collections.collections
            ) if hasattr(collections, 'collections') else False
            
            # Test embedding generation
            embed_test_success = True
            embed_error = None
            try:
                test_embedding = await self._generate_query_embedding("health test")
                embed_dimensions = len(test_embedding) if test_embedding else 0
            except Exception as e:
                embed_test_success = False
                embed_error = str(e)
                embed_dimensions = 0
            
            # Determine overall status
            if collection_exists and embed_test_success:
                status = "healthy"
            elif embed_test_success:
                status = "degraded"  # Can generate embeddings but collection missing
            else:
                status = "unhealthy"
            
            return BackendHealthStatus(
                status=status,
                response_time_ms=response_time,
                metadata={
                    "collection_exists": collection_exists,
                    "collection_name": self._collection_name,
                    "embedding_service_healthy": embed_test_success,
                    "embedding_dimensions": embed_dimensions,
                    "embedding_error": embed_error,
                    "total_collections": len(collections.collections) if hasattr(collections, 'collections') else 0
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return BackendHealthStatus(
                status="unhealthy",
                response_time_ms=response_time,
                error_message=str(e),
                metadata={
                    "connection_error": True,
                    "error_type": type(e).__name__
                }
            )
    
    async def initialize(self) -> None:
        """Initialize the vector backend."""
        backend_logger.info("Initializing vector backend")
        
        try:
            # Ensure collection exists
            if hasattr(self.client, 'create_collection'):
                self.client.create_collection(force=False)  # Don't overwrite existing
            
            # Test embedding service
            await self._generate_query_embedding("initialization test")
            
            backend_logger.info("Vector backend initialized successfully")
            
        except Exception as e:
            backend_logger.error(f"Vector backend initialization failed: {e}")
            raise BackendSearchError(self.backend_name, f"Initialization failed: {e}", e)
    
    async def cleanup(self) -> None:
        """Clean up vector backend resources."""
        backend_logger.info("Cleaning up vector backend")
        # No explicit cleanup needed for Qdrant client
    
    # Private helper methods
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query."""
        try:
            if self.embedding_generator:
                # Use the existing embedding service
                if asyncio.iscoroutinefunction(self.embedding_generator.generate_embedding):
                    return await self.embedding_generator.generate_embedding(query, adjust_dimensions=True)
                else:
                    # Handle sync embedding generators
                    return self.embedding_generator.generate_embedding(query, adjust_dimensions=True)
            else:
                raise ValueError("No embedding generator available")
                
        except Exception as e:
            backend_logger.error(f"Embedding generation failed: {e}")
            raise
    
    async def _perform_vector_search(self, query_vector: List[float], options: SearchOptions) -> List[Any]:
        """Perform the actual vector search operation."""
        try:
            # Call Qdrant search (compatible with v1.9.6 - no score_threshold parameter)
            results = self.client.search(
                collection_name=self._collection_name,
                query_vector=query_vector,
                limit=options.limit
            )
            
            # Apply score threshold manually for compatibility with v1.9.6
            if options.score_threshold > 0:
                results = [r for r in results if r.score >= options.score_threshold]
            
            return results
            
        except Exception as e:
            backend_logger.error(f"Qdrant search failed: {e}")
            raise
    
    def _convert_to_memory_results(self, raw_results: List[Any]) -> List[MemoryResult]:
        """Convert Qdrant results to normalized MemoryResult format."""
        results = []
        
        for result in raw_results:
            try:
                # Extract data from Qdrant result structure
                result_id = str(result.id) if hasattr(result, 'id') else str(id(result))
                payload = result.payload if hasattr(result, 'payload') else {}
                score = float(result.score) if hasattr(result, 'score') else 1.0
                
                # Extract text content
                text = payload.get('text', payload.get('content', ''))
                if not text and 'user_message' in payload:
                    text = payload['user_message']  # Legacy compatibility
                
                # Determine content type
                content_type = ContentType.GENERAL
                if payload.get('type'):
                    try:
                        content_type = ContentType(payload['type'])
                    except ValueError:
                        # Keep as GENERAL if unknown type
                        pass
                elif 'code' in text.lower():
                    content_type = ContentType.CODE
                elif any(word in text.lower() for word in ['document', 'guide', 'manual']):
                    content_type = ContentType.DOCUMENTATION
                
                # Extract tags
                tags = []
                if payload.get('tags'):
                    tags = payload['tags'] if isinstance(payload['tags'], list) else [payload['tags']]
                
                # Create normalized result
                memory_result = MemoryResult(
                    id=result_id,
                    text=text,
                    type=content_type,
                    score=min(max(score, 0.0), 1.0),  # Clamp to valid range
                    source=ResultSource.VECTOR,
                    tags=tags,
                    metadata={
                        **payload,
                        'qdrant_score': score,  # Preserve original score
                        'vector_search': True
                    },
                    namespace=payload.get('namespace'),
                    title=payload.get('title'),
                    user_id=payload.get('user_id')
                )
                
                results.append(memory_result)
                
            except Exception as e:
                backend_logger.warning(f"Failed to convert vector result: {e}", result_id=str(getattr(result, 'id', 'unknown')))
                continue
        
        return results
    
    def _apply_filters(self, results: List[MemoryResult], options: SearchOptions) -> List[MemoryResult]:
        """Apply additional filtering to results."""
        filtered = results
        
        # Apply namespace filter if specified
        if options.namespace:
            filtered = [r for r in filtered if r.namespace == options.namespace]
        
        # Apply custom filters from options
        if options.filters:
            for filter_key, filter_value in options.filters.items():
                if filter_key == "type":
                    filtered = [r for r in filtered if r.type == filter_value]
                elif filter_key == "tags":
                    filter_tags = filter_value if isinstance(filter_value, list) else [filter_value]
                    filtered = [r for r in filtered if any(tag in r.tags for tag in filter_tags)]
                elif filter_key == "user_id":
                    filtered = [r for r in filtered if r.user_id == filter_value]
        
        # Apply score threshold
        if options.score_threshold > 0:
            filtered = [r for r in filtered if r.score >= options.score_threshold]
        
        return filtered[:options.limit]  # Ensure we don't exceed limit