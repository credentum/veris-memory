#!/usr/bin/env python3
"""
Mock backend implementations for testing and development.

These mock backends provide the same interface as real backends but
store data in memory for fast testing and development.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from ..interfaces.backend_interface import BackendSearchInterface, SearchOptions, BackendHealthStatus
from ..interfaces.memory_result import MemoryResult, ResultSource, ContentType


class MockVectorBackend(BackendSearchInterface):
    """Mock vector backend for testing."""
    
    def __init__(self):
        """Initialize mock vector backend."""
        self.storage: Dict[str, MemoryResult] = {}
        self.search_count = 0
    
    @property
    def backend_name(self) -> str:
        return "vector"
    
    async def search(self, query: str, options: SearchOptions) -> List[MemoryResult]:
        """Mock vector search."""
        self.search_count += 1
        
        # Simple mock: return stored results that contain query terms
        results = []
        query_lower = query.lower()
        
        for context in self.storage.values():
            if query_lower in context.text.lower():
                # Simulate vector similarity score
                context.score = 0.8 + (hash(query + context.id) % 20) / 100
                context.source = ResultSource.VECTOR
                results.append(context)
        
        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:options.limit] if options.limit else results
    
    async def store_context(self, context: MemoryResult) -> bool:
        """Store context in mock vector backend."""
        self.storage[context.id] = context
        return True
    
    async def health_check(self) -> BackendHealthStatus:
        """Mock health check."""
        return BackendHealthStatus(
            backend_name="vector",
            is_healthy=True,
            response_time_ms=5.0,
            details={"storage_count": len(self.storage), "search_count": self.search_count}
        )


class MockGraphBackend(BackendSearchInterface):
    """Mock graph backend for testing."""
    
    def __init__(self):
        """Initialize mock graph backend."""
        self.storage: Dict[str, MemoryResult] = {}
        self.relationships: Dict[str, List[str]] = {}
        self.search_count = 0
    
    @property
    def backend_name(self) -> str:
        return "graph"
    
    async def search(self, query: str, options: SearchOptions) -> List[MemoryResult]:
        """Mock graph search."""
        self.search_count += 1
        
        # Simple mock: return stored results and related contexts
        results = []
        query_lower = query.lower()
        
        for context in self.storage.values():
            if query_lower in context.text.lower() or any(query_lower in tag.lower() for tag in context.tags):
                # Simulate graph relationship score
                context.score = 0.7 + (hash(query + context.id) % 30) / 100
                context.source = ResultSource.GRAPH
                results.append(context)
                
                # Add related contexts (mock relationship traversal)
                related_ids = self.relationships.get(context.id, [])
                for related_id in related_ids[:2]:  # Limit related results
                    if related_id in self.storage:
                        related_context = self.storage[related_id]
                        related_context.score = context.score - 0.1
                        related_context.source = ResultSource.GRAPH
                        results.append(related_context)
        
        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:options.limit] if options.limit else results
    
    async def store_context(self, context: MemoryResult) -> bool:
        """Store context in mock graph backend."""
        self.storage[context.id] = context
        return True
    
    async def health_check(self) -> BackendHealthStatus:
        """Mock health check."""
        return BackendHealthStatus(
            backend_name="graph",
            is_healthy=True,
            response_time_ms=8.0,
            details={
                "storage_count": len(self.storage), 
                "relationship_count": len(self.relationships),
                "search_count": self.search_count
            }
        )


class MockKVBackend(BackendSearchInterface):
    """Mock key-value backend for testing."""
    
    def __init__(self):
        """Initialize mock KV backend."""
        self.storage: Dict[str, MemoryResult] = {}
        self.indexes: Dict[str, List[str]] = {}  # tag -> context_ids
        self.search_count = 0
    
    @property
    def backend_name(self) -> str:
        return "kv"
    
    async def search(self, query: str, options: SearchOptions) -> List[MemoryResult]:
        """Mock KV search."""
        self.search_count += 1
        
        # Simple mock: exact matches and tag-based lookup
        results = []
        query_lower = query.lower()
        
        # Direct ID lookup
        if query in self.storage:
            context = self.storage[query]
            context.score = 1.0
            context.source = ResultSource.KV
            results.append(context)
        
        # Tag-based lookup
        for tag, context_ids in self.indexes.items():
            if query_lower in tag.lower():
                for context_id in context_ids:
                    if context_id in self.storage:
                        context = self.storage[context_id]
                        context.score = 0.9
                        context.source = ResultSource.KV
                        results.append(context)
        
        # Text-based lookup (fallback)
        for context in self.storage.values():
            if query_lower in context.text.lower() and context not in results:
                context.score = 0.6
                context.source = ResultSource.KV
                results.append(context)
        
        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:options.limit] if options.limit else results
    
    async def store_context(self, context: MemoryResult) -> bool:
        """Store context in mock KV backend."""
        self.storage[context.id] = context
        
        # Update tag indexes
        for tag in context.tags:
            if tag not in self.indexes:
                self.indexes[tag] = []
            if context.id not in self.indexes[tag]:
                self.indexes[tag].append(context.id)
        
        return True
    
    async def health_check(self) -> BackendHealthStatus:
        """Mock health check."""
        return BackendHealthStatus(
            backend_name="kv",
            is_healthy=True,
            response_time_ms=3.0,
            details={
                "storage_count": len(self.storage),
                "index_count": len(self.indexes),
                "search_count": self.search_count
            }
        )