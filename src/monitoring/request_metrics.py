#!/usr/bin/env python3
"""
Request Metrics Middleware for Real-Time Latency and Error Tracking

Provides FastAPI middleware for tracking:
- Request latency (avg, p95, p99)
- Error rates by endpoint
- Request counts and throughput
- Time-series data for trending
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RequestMetric:
    """Individual request metric data point."""
    timestamp: datetime
    method: str
    path: str
    status_code: int
    duration_ms: float
    error: Optional[str] = None


@dataclass
class EndpointStats:
    """Statistics for a specific endpoint."""
    request_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    durations: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_request: Optional[datetime] = None
    
    @property
    def error_rate_percent(self) -> float:
        """Calculate error rate percentage."""
        if self.request_count == 0:
            return 0.0
        return (self.error_count / self.request_count) * 100
    
    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration."""
        if self.request_count == 0:
            return 0.0
        return self.total_duration_ms / self.request_count
    
    @property
    def p95_duration_ms(self) -> float:
        """Calculate 95th percentile duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]
    
    @property
    def p99_duration_ms(self) -> float:
        """Calculate 99th percentile duration."""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        idx = int(len(sorted_durations) * 0.99)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]


class RequestMetricsCollector:
    """Collects and aggregates request metrics in real-time."""
    
    def __init__(self, max_history_minutes: int = 60):
        self.max_history_minutes = max_history_minutes
        self.endpoint_stats: Dict[str, EndpointStats] = defaultdict(EndpointStats)
        self.recent_requests: deque = deque(maxlen=10000)  # Last 10k requests
        self.total_requests = 0
        self.total_errors = 0
        self._lock = asyncio.Lock()
        
    async def record_request(self, method: str, path: str, status_code: int, 
                           duration_ms: float, error: Optional[str] = None) -> None:
        """Record a request metric."""
        async with self._lock:
            endpoint_key = f"{method} {path}"
            metric = RequestMetric(
                timestamp=datetime.utcnow(),
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                error=error
            )
            
            # Update endpoint stats
            stats = self.endpoint_stats[endpoint_key]
            stats.request_count += 1
            stats.total_duration_ms += duration_ms
            stats.durations.append(duration_ms)
            stats.last_request = metric.timestamp
            
            if status_code >= 400:
                stats.error_count += 1
                self.total_errors += 1
            
            # Add to recent requests
            self.recent_requests.append(metric)
            self.total_requests += 1
            
            # Cleanup old data
            await self._cleanup_old_data()
    
    async def _cleanup_old_data(self) -> None:
        """Remove data older than max_history_minutes."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.max_history_minutes)
        
        # Clean recent requests
        while (self.recent_requests and 
               self.recent_requests[0].timestamp < cutoff_time):
            self.recent_requests.popleft()
    
    async def get_global_stats(self) -> Dict[str, float]:
        """Get global statistics across all endpoints."""
        async with self._lock:
            if not self.recent_requests:
                return {
                    'total_requests': 0,
                    'total_errors': 0,
                    'error_rate_percent': 0.0,
                    'avg_duration_ms': 0.0,
                    'p95_duration_ms': 0.0,
                    'p99_duration_ms': 0.0,
                    'requests_per_minute': 0.0
                }
            
            # Calculate from recent requests
            durations = [r.duration_ms for r in self.recent_requests]
            errors = [r for r in self.recent_requests if r.status_code >= 400]
            
            # Calculate requests per minute
            now = datetime.utcnow()
            one_minute_ago = now - timedelta(minutes=1)
            recent_minute_requests = [
                r for r in self.recent_requests 
                if r.timestamp >= one_minute_ago
            ]
            
            # Sort durations for percentiles
            sorted_durations = sorted(durations)
            
            return {
                'total_requests': len(self.recent_requests),
                'total_errors': len(errors),
                'error_rate_percent': (len(errors) / len(self.recent_requests)) * 100,
                'avg_duration_ms': sum(durations) / len(durations) if durations else 0.0,
                'p95_duration_ms': sorted_durations[int(len(sorted_durations) * 0.95)] if sorted_durations else 0.0,
                'p99_duration_ms': sorted_durations[int(len(sorted_durations) * 0.99)] if sorted_durations else 0.0,
                'requests_per_minute': len(recent_minute_requests)
            }
    
    async def get_endpoint_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics by endpoint."""
        async with self._lock:
            return {
                endpoint: {
                    'request_count': stats.request_count,
                    'error_count': stats.error_count,
                    'error_rate_percent': stats.error_rate_percent,
                    'avg_duration_ms': stats.avg_duration_ms,
                    'p95_duration_ms': stats.p95_duration_ms,
                    'p99_duration_ms': stats.p99_duration_ms,
                    'last_request': stats.last_request.isoformat() if stats.last_request else None
                }
                for endpoint, stats in self.endpoint_stats.items()
            }
    
    async def get_trending_data(self, minutes: int = 5) -> List[Dict[str, float]]:
        """Get trending data for the last N minutes."""
        async with self._lock:
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            recent = [r for r in self.recent_requests if r.timestamp >= cutoff_time]
            
            # Group by minute
            minute_buckets = defaultdict(list)
            for request in recent:
                minute_key = request.timestamp.replace(second=0, microsecond=0)
                minute_buckets[minute_key].append(request)
            
            # Calculate stats per minute
            trending = []
            for minute, requests in sorted(minute_buckets.items()):
                durations = [r.duration_ms for r in requests]
                errors = [r for r in requests if r.status_code >= 400]
                
                trending.append({
                    'timestamp': minute.isoformat(),
                    'request_count': len(requests),
                    'error_count': len(errors),
                    'avg_duration_ms': sum(durations) / len(durations) if durations else 0.0,
                    'error_rate_percent': (len(errors) / len(requests)) * 100 if requests else 0.0
                })
            
            return trending


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for request metrics collection."""
    
    def __init__(self, app, metrics_collector: RequestMetricsCollector):
        super().__init__(app)
        self.metrics_collector = metrics_collector
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.time()
        error_message = None
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Handle exceptions
            error_message = str(e)
            status_code = 500
            response = Response(
                content=f"Internal Server Error: {error_message}",
                status_code=500
            )
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Record metrics asynchronously
        asyncio.create_task(
            self.metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                error=error_message
            )
        )
        
        return response


# Global metrics collector instance
global_metrics_collector = RequestMetricsCollector()


def get_metrics_collector() -> RequestMetricsCollector:
    """Get the global metrics collector instance."""
    return global_metrics_collector


def create_metrics_middleware() -> RequestMetricsMiddleware:
    """Create a metrics middleware instance."""
    return RequestMetricsMiddleware(None, global_metrics_collector)