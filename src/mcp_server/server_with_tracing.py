"""
Enhanced MCP Server with Tracing Integration for Phase 4.2

This is a wrapper around the existing MCP server that adds comprehensive
request tracing without modifying the original server implementation.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from .tracing import (
    TraceManager, 
    initialize_tracing, 
    trace_function, 
    TracingContext,
    SpanContext,
    get_current_trace_id,
    add_trace_metadata
)

# Import original server components  
from .server import *  # Import all from original server

logger = logging.getLogger(__name__)


class TracedContextStore:
    """Enhanced context store with tracing capabilities."""
    
    def __init__(self, original_server, trace_manager: TraceManager):
        """
        Initialize traced context store wrapper.
        
        Args:
            original_server: Original MCP server instance
            trace_manager: Trace manager for request tracking
        """
        self.original_server = original_server
        self.trace_manager = trace_manager
        self.logger = logging.getLogger(__name__)
    
    @trace_function("store_context")
    async def store_context_traced(
        self, 
        context_type: str, 
        content: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store context with tracing."""
        
        # Add request metadata to trace
        add_trace_metadata("operation", "store_context")
        add_trace_metadata("context_type", context_type)
        add_trace_metadata("content_size", len(str(content)))
        
        async with SpanContext("validate_input") as span:
            # Validate inputs
            if not context_type or not content:
                raise ValueError("context_type and content are required")
        
        async with SpanContext("storage_operation") as span:
            # Call original store method
            # This would need to be adapted based on the actual server API
            result = await self._call_original_store_context(context_type, content, metadata)
        
        # Add response metadata to trace
        add_trace_metadata("result_id", result.get("id"))
        add_trace_metadata("storage_time_ms", result.get("storage_time_ms"))
        
        return result
    
    @trace_function("retrieve_context")
    async def retrieve_context_traced(
        self, 
        query: str, 
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve context with comprehensive tracing."""
        
        # Add request metadata
        add_trace_metadata("operation", "retrieve_context")
        add_trace_metadata("query_length", len(query))
        add_trace_metadata("limit", limit)
        add_trace_metadata("has_filters", filters is not None)
        
        retrieval_start = time.time()
        
        async with SpanContext("query_preprocessing", {"query": query[:100]}) as span:
            # Query preprocessing and validation
            processed_query = query.strip()
            
        async with SpanContext("dense_retrieval") as span:
            # Dense retrieval phase
            dense_results = await self._perform_dense_retrieval(processed_query, limit * 2)
            if span:
                span.metadata["dense_result_count"] = len(dense_results)
        
        async with SpanContext("lexical_retrieval") as span:
            # Lexical retrieval phase (if applicable)
            lexical_results = await self._perform_lexical_retrieval(processed_query, limit * 2)
            if span:
                span.metadata["lexical_result_count"] = len(lexical_results)
        
        async with SpanContext("score_fusion") as span:
            # Score fusion
            fused_results = await self._fuse_retrieval_scores(dense_results, lexical_results)
            if span:
                span.metadata["fused_result_count"] = len(fused_results)
        
        rerank_span = None
        async with SpanContext("rerank_decision") as span:
            # Dynamic rerank gating
            should_rerank = await self._should_rerank_results(fused_results, query)
            if span:
                span.metadata["should_rerank"] = should_rerank
        
        final_results = fused_results
        if should_rerank:
            async with SpanContext("reranking") as span:
                rerank_span = span
                final_results = await self._rerank_results(query, fused_results[:limit * 2])
                if span:
                    span.metadata["reranked_count"] = len(final_results)
        
        async with SpanContext("result_formatting") as span:
            # Format final results
            formatted_results = await self._format_retrieval_results(final_results[:limit])
        
        total_time = (time.time() - retrieval_start) * 1000
        
        # Add comprehensive response metadata
        result = {
            "results": formatted_results,
            "total_results": len(formatted_results),
            "retrieval_time_ms": total_time,
            "trace_id": get_current_trace_id(),
            "retrieval_stages": {
                "dense_retrieval": len(dense_results) > 0,
                "lexical_retrieval": len(lexical_results) > 0,
                "reranking_applied": should_rerank,
                "score_fusion_applied": True
            }
        }
        
        add_trace_metadata("total_results", len(formatted_results))
        add_trace_metadata("retrieval_time_ms", total_time)
        add_trace_metadata("reranking_applied", should_rerank)
        
        return result
    
    async def _call_original_store_context(
        self, 
        context_type: str, 
        content: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Call original server's store_context method."""
        # This is a placeholder - would need to be implemented based on actual server API
        storage_start = time.time()
        
        # Simulate calling original server
        # In real implementation, this would call the actual server method
        result = {
            "id": f"ctx_{int(time.time())}",
            "stored_at": time.time(),
            "storage_time_ms": (time.time() - storage_start) * 1000
        }
        
        return result
    
    async def _perform_dense_retrieval(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Perform dense vector retrieval."""
        # Placeholder for dense retrieval
        await asyncio.sleep(0.01)  # Simulate retrieval time
        return [{"id": f"dense_{i}", "score": 0.9 - i * 0.1, "type": "dense"} for i in range(min(5, limit))]
    
    async def _perform_lexical_retrieval(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Perform lexical/keyword retrieval."""
        # Placeholder for lexical retrieval
        await asyncio.sleep(0.005)  # Simulate retrieval time
        return [{"id": f"lexical_{i}", "score": 0.8 - i * 0.1, "type": "lexical"} for i in range(min(3, limit))]
    
    async def _fuse_retrieval_scores(
        self, 
        dense_results: List[Dict[str, Any]], 
        lexical_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fuse dense and lexical retrieval scores."""
        # Simple fusion strategy - combine and deduplicate
        all_results = {}
        
        # Add dense results with weight 0.7
        for result in dense_results:
            result_id = result["id"]
            all_results[result_id] = {
                **result,
                "fused_score": result["score"] * 0.7,
                "sources": ["dense"]
            }
        
        # Add lexical results with weight 0.3, combine if duplicate
        for result in lexical_results:
            result_id = result["id"]
            if result_id in all_results:
                all_results[result_id]["fused_score"] += result["score"] * 0.3
                all_results[result_id]["sources"].append("lexical")
            else:
                all_results[result_id] = {
                    **result,
                    "fused_score": result["score"] * 0.3,
                    "sources": ["lexical"]
                }
        
        # Sort by fused score
        return sorted(all_results.values(), key=lambda x: x["fused_score"], reverse=True)
    
    async def _should_rerank_results(self, results: List[Dict[str, Any]], query: str) -> bool:
        """Determine if results should be reranked (dynamic gating)."""
        if len(results) < 2:
            return False
        
        # Skip reranking if top result has clear advantage
        score_gap = results[0]["fused_score"] - results[1]["fused_score"]
        rerank_threshold = 0.1
        
        # Also consider lexical agreement
        top_result_sources = results[0].get("sources", [])
        has_lexical_agreement = "lexical" in top_result_sources and "dense" in top_result_sources
        
        if score_gap > rerank_threshold and has_lexical_agreement:
            return False  # Skip reranking
        
        return True  # Apply reranking
    
    async def _rerank_results(
        self, 
        query: str, 
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rerank results using cross-encoder or similar."""
        # Placeholder for reranking
        await asyncio.sleep(0.02)  # Simulate reranking time
        
        # Simple reranking simulation - slightly adjust scores
        reranked = []
        for i, result in enumerate(results):
            rerank_boost = 0.05 * (len(results) - i) / len(results)  # Small boost based on position
            reranked_result = {
                **result,
                "rerank_score": result["fused_score"] + rerank_boost,
                "was_reranked": True
            }
            reranked.append(reranked_result)
        
        return sorted(reranked, key=lambda x: x["rerank_score"], reverse=True)
    
    async def _format_retrieval_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format final results for response."""
        formatted = []
        for result in results:
            formatted.append({
                "id": result["id"],
                "score": result.get("rerank_score", result.get("fused_score", result["score"])),
                "metadata": {
                    "original_score": result["score"],
                    "fused_score": result.get("fused_score"),
                    "rerank_score": result.get("rerank_score"),
                    "sources": result.get("sources", []),
                    "was_reranked": result.get("was_reranked", False)
                }
            })
        
        return formatted


class TracedMCPServer:
    """MCP Server wrapper with comprehensive tracing."""
    
    def __init__(self, storage_dir: str = "./trace_data"):
        """
        Initialize traced MCP server.
        
        Args:
            storage_dir: Directory for storing trace data
        """
        # Initialize tracing
        self.trace_manager = initialize_tracing(storage_dir)
        
        # Initialize original server components
        # This would be adapted based on the actual server initialization
        self.original_server = None  # Placeholder
        
        # Create traced wrapper
        self.context_store = TracedContextStore(self.original_server, self.trace_manager)
        
        self.logger = logging.getLogger(__name__)
    
    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request with tracing."""
        
        request_type = request.get("method", "unknown")
        
        async with TracingContext(
            request_type=f"mcp_{request_type}",
            request_metadata={
                "method": request_type,
                "params_keys": list(request.get("params", {}).keys()),
                "request_id": request.get("id")
            },
            trace_manager=self.trace_manager
        ) as trace_id:
            
            try:
                # Route to appropriate handler based on method
                if request_type == "tools/call":
                    return await self._handle_tool_call(request)
                elif request_type == "resources/list":
                    return await self._handle_resource_list(request)
                elif request_type == "resources/read":
                    return await self._handle_resource_read(request)
                else:
                    return await self._handle_unknown_method(request)
            
            except Exception as e:
                self.logger.error(f"Error handling MCP request {request_type}: {str(e)}")
                return {
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": {"trace_id": trace_id}
                    }
                }
    
    async def _handle_tool_call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call requests."""
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        add_trace_metadata("tool_name", tool_name)
        
        if tool_name == "store_context":
            result = await self.context_store.store_context_traced(
                context_type=arguments.get("type"),
                content=arguments.get("content"),
                metadata=arguments.get("metadata")
            )
            return {"result": result}
        
        elif tool_name == "retrieve_context":
            result = await self.context_store.retrieve_context_traced(
                query=arguments.get("query"),
                limit=arguments.get("limit", 10),
                filters=arguments.get("filters")
            )
            return {"result": result}
        
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
    
    async def _handle_resource_list(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resource list requests."""
        # Placeholder implementation
        return {
            "result": {
                "resources": []
            }
        }
    
    async def _handle_resource_read(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resource read requests."""
        # Placeholder implementation
        return {
            "result": {
                "contents": []
            }
        }
    
    async def _handle_unknown_method(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unknown method requests."""
        return {
            "error": {
                "code": -32601,
                "message": f"Method not found: {request.get('method')}"
            }
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get server performance statistics."""
        return {
            "overall": self.trace_manager.get_performance_stats(),
            "store_context": self.trace_manager.get_performance_stats("mcp_store_context"),
            "retrieve_context": self.trace_manager.get_performance_stats("mcp_retrieve_context"),
            "recent_failures": len(self.trace_manager.get_recent_failures()),
            "trace_counts": {
                "active": len(self.trace_manager.active_traces),
                "completed": len(self.trace_manager.completed_traces),
                "failed": len(self.trace_manager.failure_traces)
            }
        }
    
    def get_recent_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent failure traces for debugging."""
        failures = self.trace_manager.get_recent_failures(limit)
        return [trace.to_dict() for trace in failures]


# Factory function for creating traced server
def create_traced_mcp_server(
    storage_dir: str = "./trace_data",
    **server_kwargs
) -> TracedMCPServer:
    """
    Create MCP server with tracing enabled.
    
    Args:
        storage_dir: Directory for trace data storage
        **server_kwargs: Additional arguments for server configuration
        
    Returns:
        Traced MCP server instance
    """
    return TracedMCPServer(storage_dir)


# Main entry point for traced server
async def main():
    """Main entry point for traced MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create traced server
    server = create_traced_mcp_server()
    
    logger.info("Starting MCP server with tracing enabled")
    
    # This would start the actual MCP server with tracing middleware
    # Implementation depends on the MCP SDK server startup pattern
    
    # For now, just demonstrate the tracing capability
    sample_request = {
        "method": "tools/call",
        "params": {
            "name": "retrieve_context",
            "arguments": {
                "query": "test query for tracing demonstration",
                "limit": 5
            }
        },
        "id": "test-request-1"
    }
    
    response = await server.handle_mcp_request(sample_request)
    
    # Show performance stats
    stats = server.get_performance_stats()
    logger.info(f"Performance stats: {stats}")
    
    logger.info("Tracing demonstration completed")


if __name__ == "__main__":
    asyncio.run(main())