"""
Request Tracing System for Phase 4.2 - Observability & Trace IDs

Implements comprehensive request tracing across MCP calls to enable:
- Per-request trace ID propagation
- Retrieval pipeline observability
- Performance debugging and analysis
- Error correlation and debugging
"""

import uuid
import time
import logging
from typing import Dict, List, Optional, Any, AsyncContextManager
from dataclasses import dataclass, asdict
from datetime import datetime
import contextvars
import asyncio
import json
from pathlib import Path

# Context variables for trace propagation
trace_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('trace_id', default=None)
request_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar('request_context', default=None)

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    """Individual span within a trace."""
    
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "started"  # started, completed, error
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def finish(self, error: Optional[str] = None):
        """Mark span as completed."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = "error" if error else "completed"
        if error:
            self.error = error


@dataclass 
class RequestTrace:
    """Complete trace for a request."""
    
    trace_id: str
    request_type: str
    start_time: float
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    spans: List[TraceSpan] = None
    request_metadata: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.spans is None:
            self.spans = []
        if self.request_metadata is None:
            self.request_metadata = {}
        if self.response_metadata is None:
            self.response_metadata = {}
    
    def add_span(self, span: TraceSpan):
        """Add span to trace."""
        self.spans.append(span)
    
    def finish(self):
        """Mark trace as completed."""
        self.end_time = time.time()
        self.total_duration_ms = (self.end_time - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for storage."""
        return {
            **asdict(self),
            'spans': [asdict(span) for span in self.spans]
        }


class TraceManager:
    """Manages request tracing and storage."""
    
    def __init__(self, storage_dir: str = "./trace_data", max_traces: int = 1000):
        """
        Initialize trace manager.
        
        Args:
            storage_dir: Directory to store trace data
            max_traces: Maximum number of traces to keep in memory
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_traces = max_traces
        self.active_traces: Dict[str, RequestTrace] = {}
        self.completed_traces: List[RequestTrace] = []
        
        # Failure tracking for last 100 failures
        self.failure_traces: List[RequestTrace] = []
        self.max_failures = 100
        
        self.logger = logging.getLogger(__name__)
    
    def start_trace(
        self, 
        request_type: str, 
        request_metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Start new request trace.
        
        Args:
            request_type: Type of request being traced
            request_metadata: Optional metadata about the request
            trace_id: Optional existing trace ID to continue
            
        Returns:
            Trace ID
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        
        trace = RequestTrace(
            trace_id=trace_id,
            request_type=request_type,
            start_time=time.time(),
            request_metadata=request_metadata or {}
        )
        
        self.active_traces[trace_id] = trace
        
        # Set context
        trace_context.set(trace_id)
        request_context.set({
            'trace_id': trace_id,
            'request_type': request_type,
            'start_time': trace.start_time
        })
        
        self.logger.debug(f"Started trace {trace_id} for {request_type}")
        return trace_id
    
    def start_span(
        self, 
        operation_name: str, 
        metadata: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None
    ) -> Optional[TraceSpan]:
        """
        Start new span within current trace.
        
        Args:
            operation_name: Name of operation being traced
            metadata: Optional metadata about the operation
            parent_span_id: Optional parent span ID
            
        Returns:
            TraceSpan or None if no active trace
        """
        trace_id = trace_context.get()
        if not trace_id or trace_id not in self.active_traces:
            self.logger.warning(f"No active trace for span: {operation_name}")
            return None
        
        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        self.active_traces[trace_id].add_span(span)
        
        self.logger.debug(f"Started span {span.span_id}: {operation_name}")
        return span
    
    def finish_span(self, span: TraceSpan, error: Optional[str] = None):
        """
        Finish a span.
        
        Args:
            span: Span to finish
            error: Optional error message if span failed
        """
        span.finish(error)
        
        self.logger.debug(
            f"Finished span {span.span_id}: {span.operation_name} "
            f"({span.duration_ms:.2f}ms)"
        )
        
        # Log slow operations
        if span.duration_ms and span.duration_ms > 1000:  # > 1 second
            self.logger.warning(
                f"Slow operation detected: {span.operation_name} took {span.duration_ms:.2f}ms"
            )
    
    def finish_trace(
        self, 
        trace_id: Optional[str] = None, 
        response_metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Finish a trace.
        
        Args:
            trace_id: Trace ID to finish (uses current if None)
            response_metadata: Optional response metadata
            error: Optional error message if trace failed
        """
        if trace_id is None:
            trace_id = trace_context.get()
        
        if not trace_id or trace_id not in self.active_traces:
            self.logger.warning(f"Cannot finish trace: {trace_id} not found")
            return
        
        trace = self.active_traces.pop(trace_id)
        trace.finish()
        
        if response_metadata:
            trace.response_metadata.update(response_metadata)
        
        if error:
            trace.response_metadata['error'] = error
            self.failure_traces.append(trace)
            
            # Keep only last N failures
            if len(self.failure_traces) > self.max_failures:
                self.failure_traces.pop(0)
        
        # Store completed trace
        self.completed_traces.append(trace)
        
        # Cleanup old traces
        if len(self.completed_traces) > self.max_traces:
            self.completed_traces.pop(0)
        
        self.logger.debug(
            f"Finished trace {trace_id}: {trace.request_type} "
            f"({trace.total_duration_ms:.2f}ms)"
        )
        
        # Store trace to disk periodically
        self._maybe_store_traces()
    
    def get_trace_id(self) -> Optional[str]:
        """Get current trace ID from context."""
        return trace_context.get()
    
    def get_trace(self, trace_id: str) -> Optional[RequestTrace]:
        """Get trace by ID."""
        # Check active traces first
        if trace_id in self.active_traces:
            return self.active_traces[trace_id]
        
        # Check completed traces
        for trace in self.completed_traces:
            if trace.trace_id == trace_id:
                return trace
        
        # Check failure traces
        for trace in self.failure_traces:
            if trace.trace_id == trace_id:
                return trace
        
        return None
    
    def get_recent_failures(self, limit: int = 10) -> List[RequestTrace]:
        """Get recent failure traces for debugging."""
        return self.failure_traces[-limit:]
    
    def get_performance_stats(self, request_type: Optional[str] = None) -> Dict[str, Any]:
        """Get performance statistics from recent traces."""
        traces = self.completed_traces
        
        if request_type:
            traces = [t for t in traces if t.request_type == request_type]
        
        if not traces:
            return {}
        
        durations = [t.total_duration_ms for t in traces if t.total_duration_ms]
        
        if not durations:
            return {}
        
        durations.sort()
        n = len(durations)
        
        stats = {
            'request_count': len(traces),
            'avg_duration_ms': sum(durations) / n,
            'min_duration_ms': durations[0],
            'max_duration_ms': durations[-1],
            'p50_duration_ms': durations[n // 2],
            'p95_duration_ms': durations[int(n * 0.95)] if n >= 20 else durations[-1],
            'p99_duration_ms': durations[int(n * 0.99)] if n >= 100 else durations[-1],
        }
        
        # Add failure rate
        failure_count = len([t for t in traces if t.response_metadata.get('error')])
        stats['failure_rate'] = failure_count / len(traces) if traces else 0.0
        
        return stats
    
    def _maybe_store_traces(self):
        """Periodically store traces to disk."""
        # Store every 100 completed traces
        if len(self.completed_traces) % 100 == 0:
            asyncio.create_task(self._store_traces_to_disk())
    
    async def _store_traces_to_disk(self):
        """Store traces to disk for persistence."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"traces_{timestamp}.json"
        filepath = self.storage_dir / filename
        
        # Store recent traces
        traces_to_store = self.completed_traces[-100:] if len(self.completed_traces) > 100 else self.completed_traces
        
        trace_data = {
            'timestamp': datetime.now().isoformat(),
            'trace_count': len(traces_to_store),
            'traces': [trace.to_dict() for trace in traces_to_store]
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(trace_data, f, indent=2)
            
            self.logger.info(f"Stored {len(traces_to_store)} traces to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error storing traces: {str(e)}")


class TracingMiddleware:
    """ASGI middleware for automatic request tracing."""
    
    def __init__(self, app, trace_manager: TraceManager):
        self.app = app
        self.trace_manager = trace_manager
    
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        
        # Extract or generate trace ID
        headers = dict(scope.get('headers', []))
        existing_trace_id = headers.get(b'x-trace-id')
        
        if existing_trace_id:
            trace_id = existing_trace_id.decode()
        else:
            trace_id = self.trace_manager.start_trace(
                request_type='mcp_request',
                request_metadata={
                    'method': scope.get('method'),
                    'path': scope.get('path'),
                    'user_agent': headers.get(b'user-agent', b'').decode()
                }
            )
        
        # Set trace context
        trace_context.set(trace_id)
        
        async def send_with_trace(message):
            if message['type'] == 'http.response.start':
                # Add trace ID to response headers
                headers = list(message.get('headers', []))
                headers.append([b'x-trace-id', trace_id.encode()])
                message = {**message, 'headers': headers}
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_with_trace)
            
            # Finish trace successfully
            self.trace_manager.finish_trace(trace_id)
            
        except Exception as e:
            # Finish trace with error
            self.trace_manager.finish_trace(
                trace_id, 
                error=str(e)
            )
            raise


def trace_function(operation_name: str):
    """Decorator for tracing function calls."""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            trace_manager = get_trace_manager()
            if not trace_manager:
                return await func(*args, **kwargs)
            
            span = trace_manager.start_span(operation_name, {
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            })
            
            try:
                result = await func(*args, **kwargs)
                if span:
                    trace_manager.finish_span(span)
                return result
                
            except Exception as e:
                if span:
                    trace_manager.finish_span(span, str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            trace_manager = get_trace_manager()
            if not trace_manager:
                return func(*args, **kwargs)
            
            span = trace_manager.start_span(operation_name, {
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            })
            
            try:
                result = func(*args, **kwargs)
                if span:
                    trace_manager.finish_span(span)
                return result
                
            except Exception as e:
                if span:
                    trace_manager.finish_span(span, str(e))
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global trace manager instance
_global_trace_manager: Optional[TraceManager] = None


def initialize_tracing(storage_dir: str = "./trace_data", max_traces: int = 1000) -> TraceManager:
    """Initialize global trace manager."""
    global _global_trace_manager
    _global_trace_manager = TraceManager(storage_dir, max_traces)
    return _global_trace_manager


def get_trace_manager() -> Optional[TraceManager]:
    """Get global trace manager instance."""
    return _global_trace_manager


class TracingContext:
    """Context manager for manual tracing."""
    
    def __init__(
        self, 
        request_type: str, 
        request_metadata: Optional[Dict[str, Any]] = None,
        trace_manager: Optional[TraceManager] = None
    ):
        self.request_type = request_type
        self.request_metadata = request_metadata
        self.trace_manager = trace_manager or get_trace_manager()
        self.trace_id = None
    
    async def __aenter__(self) -> str:
        if self.trace_manager:
            self.trace_id = self.trace_manager.start_trace(
                self.request_type, 
                self.request_metadata
            )
        return self.trace_id or "no-trace"
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.trace_manager and self.trace_id:
            error = str(exc_val) if exc_val else None
            self.trace_manager.finish_trace(self.trace_id, error=error)


class SpanContext:
    """Context manager for span tracing."""
    
    def __init__(
        self, 
        operation_name: str, 
        metadata: Optional[Dict[str, Any]] = None,
        trace_manager: Optional[TraceManager] = None
    ):
        self.operation_name = operation_name
        self.metadata = metadata
        self.trace_manager = trace_manager or get_trace_manager()
        self.span = None
    
    async def __aenter__(self) -> Optional[TraceSpan]:
        if self.trace_manager:
            self.span = self.trace_manager.start_span(
                self.operation_name, 
                self.metadata
            )
        return self.span
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.trace_manager and self.span:
            error = str(exc_val) if exc_val else None
            self.trace_manager.finish_span(self.span, error)


# Convenience functions
def get_current_trace_id() -> Optional[str]:
    """Get current trace ID."""
    return trace_context.get()


def add_trace_metadata(key: str, value: Any):
    """Add metadata to current trace."""
    trace_id = trace_context.get()
    if trace_id:
        trace_manager = get_trace_manager()
        if trace_manager:
            trace = trace_manager.get_trace(trace_id)
            if trace:
                trace.request_metadata[key] = value