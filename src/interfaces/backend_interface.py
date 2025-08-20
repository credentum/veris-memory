#!/usr/bin/env python3
"""
Backend interface definitions for Veris Memory search backends.

This module defines the common interface that all search backends must implement
to enable consistent querying across vector, graph, and key-value stores.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SearchOptions(BaseModel):
    """Configuration options for backend search operations."""
    
    limit: int = Field(default=10, ge=1, le=1000, description="Maximum number of results to return")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Backend-specific filters")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum score threshold")
    include_metadata: bool = Field(default=True, description="Include metadata in results")
    namespace: Optional[str] = Field(default=None, description="Optional namespace for query scoping")
    
    class Config:
        schema_extra = {
            "example": {
                "limit": 10,
                "filters": {"type": "code", "tags": ["python"]},
                "score_threshold": 0.5,
                "include_metadata": True,
                "namespace": "agent_123"
            }
        }


class BackendHealthStatus(BaseModel):
    """Health status information for a backend."""
    
    status: str = Field(..., description="Health status (healthy/degraded/unhealthy)")
    response_time_ms: Optional[float] = Field(default=None, description="Last health check response time")
    error_message: Optional[str] = Field(default=None, description="Error message if unhealthy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Backend-specific health metadata")


class BackendSearchInterface(ABC):
    """
    Abstract interface for search backends in Veris Memory.
    
    All concrete backend implementations (Vector, Graph, KV) must implement this interface
    to ensure consistent behavior and enable pluggable backend architectures.
    """
    
    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the name of this backend (e.g., 'vector', 'graph', 'kv')."""
        pass
    
    @abstractmethod
    async def search(
        self, 
        query: str, 
        options: SearchOptions
    ) -> List[Dict[str, Any]]:
        """
        Search the backend and return normalized results.
        
        Args:
            query: The search query string
            options: Search configuration options
            
        Returns:
            List of results in normalized format (will be converted to MemoryResult)
            
        Raises:
            BackendSearchError: If the search operation fails
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> BackendHealthStatus:
        """
        Check the health status of this backend.
        
        Returns:
            BackendHealthStatus indicating current health and performance
        """
        pass
    
    async def initialize(self) -> None:
        """
        Initialize the backend (optional).
        
        Concrete implementations can override this for setup operations.
        """
        pass
    
    async def cleanup(self) -> None:
        """
        Clean up backend resources (optional).
        
        Concrete implementations can override this for cleanup operations.
        """
        pass


class BackendSearchError(Exception):
    """Exception raised when backend search operations fail."""
    
    def __init__(self, backend_name: str, message: str, original_error: Optional[Exception] = None):
        self.backend_name = backend_name
        self.message = message
        self.original_error = original_error
        super().__init__(f"Backend '{backend_name}' search failed: {message}")