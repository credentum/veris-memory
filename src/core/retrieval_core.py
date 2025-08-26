#!/usr/bin/env python3
"""
Unified retrieval core for both API and MCP interfaces.

This module provides a single point of truth for context retrieval,
ensuring identical behavior across API and MCP endpoints while
properly tracking backend timings and utilizing the hybrid search architecture.
"""

import logging
from typing import Dict, List, Any, Optional

from ..interfaces.backend_interface import SearchOptions
from ..interfaces.memory_result import SearchResultResponse
from ..core.query_dispatcher import QueryDispatcher, SearchMode
from ..utils.logging_middleware import search_logger


logger = logging.getLogger(__name__)


class RetrievalCore:
    """
    Unified retrieval engine for both API and MCP interfaces.
    
    This ensures both API and MCP return identical results for identical inputs
    while properly utilizing the backend timing infrastructure.
    """
    
    def __init__(self, query_dispatcher: QueryDispatcher):
        """
        Initialize the unified retrieval core.
        
        Args:
            query_dispatcher: The configured query dispatcher with all backends
        """
        self.dispatcher = query_dispatcher
    
    async def search(
        self, 
        query: str, 
        limit: int = 10,
        search_mode: str = "hybrid",
        context_type: Optional[str] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0
    ) -> SearchResultResponse:
        """
        Execute unified search across all configured backends.
        
        Args:
            query: Search query text
            limit: Maximum number of results to return
            search_mode: Search mode ("vector", "graph", "kv", "hybrid", "auto")
            context_type: Optional context type filter
            metadata_filters: Optional metadata filters
            score_threshold: Minimum score threshold for results
            
        Returns:
            SearchResultResponse with results and backend timing information
            
        Raises:
            Exception: If search fails across all backends
        """
        try:
            # Convert search_mode string to SearchMode enum
            if search_mode not in SearchMode.__members__:
                logger.warning(f"Invalid search_mode '{search_mode}', defaulting to 'hybrid'")
                search_mode = "hybrid"
            
            search_mode_enum = SearchMode(search_mode)
            
            # Build search options
            search_options = SearchOptions(
                limit=limit,
                score_threshold=score_threshold,
                namespace=None,  # Could be derived from context_type if needed
                filters=metadata_filters or {}
            )
            
            # Add context_type to filters if specified
            if context_type:
                search_options.filters["type"] = context_type
            
            logger.info(
                f"RetrievalCore executing search: query_length={len(query)}, "
                f"mode={search_mode}, limit={limit}, score_threshold={score_threshold}"
            )
            
            # Execute search through unified dispatcher
            search_response = await self.dispatcher.search(
                query=query,
                options=search_options,
                search_mode=search_mode_enum
            )
            
            logger.info(
                f"RetrievalCore search completed: results={len(search_response.results)}, "
                f"backends_used={search_response.backends_used}, "
                f"backend_timings={search_response.backend_timings}"
            )
            
            return search_response
            
        except Exception as e:
            logger.error(f"RetrievalCore search failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all registered backends.
        
        Returns:
            Dict containing health status of all backends
        """
        try:
            backend_health = {}
            
            for backend_name, backend in self.dispatcher.backends.items():
                try:
                    health_status = await backend.health_check()
                    backend_health[backend_name] = {
                        "status": health_status.status,
                        "response_time_ms": health_status.response_time_ms,
                        "error_message": health_status.error_message,
                        "metadata": health_status.metadata
                    }
                except Exception as e:
                    backend_health[backend_name] = {
                        "status": "unhealthy",
                        "response_time_ms": -1,
                        "error_message": str(e),
                        "metadata": {"health_check_failed": True}
                    }
            
            # Determine overall health
            healthy_backends = sum(1 for health in backend_health.values() if health["status"] == "healthy")
            total_backends = len(backend_health)
            
            overall_status = "healthy" if healthy_backends == total_backends else \
                           "degraded" if healthy_backends > 0 else "unhealthy"
            
            return {
                "overall_status": overall_status,
                "backends": backend_health,
                "healthy_backends": healthy_backends,
                "total_backends": total_backends
            }
            
        except Exception as e:
            logger.error(f"RetrievalCore health check failed: {e}")
            return {
                "overall_status": "unhealthy",
                "error": str(e),
                "backends": {},
                "healthy_backends": 0,
                "total_backends": 0
            }


# Global instance to be shared between API and MCP
_retrieval_core_instance: Optional[RetrievalCore] = None


def get_retrieval_core() -> Optional[RetrievalCore]:
    """Get the global retrieval core instance."""
    return _retrieval_core_instance


def set_retrieval_core(retrieval_core: RetrievalCore) -> None:
    """Set the global retrieval core instance."""
    global _retrieval_core_instance
    _retrieval_core_instance = retrieval_core
    logger.info("RetrievalCore instance set globally")


def initialize_retrieval_core(query_dispatcher: QueryDispatcher) -> RetrievalCore:
    """
    Initialize and set the global retrieval core instance.
    
    Args:
        query_dispatcher: Configured query dispatcher with all backends
        
    Returns:
        The initialized RetrievalCore instance
    """
    retrieval_core = RetrievalCore(query_dispatcher)
    set_retrieval_core(retrieval_core)
    logger.info("RetrievalCore initialized and set globally")
    return retrieval_core