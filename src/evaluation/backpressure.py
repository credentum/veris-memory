"""
Backpressure and Overload Protection System for Phase 4.2

Implements intelligent backpressure mechanisms including:
- Request rate limiting with sliding windows and token buckets
- Queue-based load shedding with priority levels
- Circuit breaker patterns for downstream services
- Adaptive throttling based on system resource usage
- Graceful degradation strategies for overload conditions
"""

import asyncio
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
from abc import ABC, abstractmethod
import statistics
import psutil
import weakref

logger = logging.getLogger(__name__)


@dataclass
class BackpressureConfig:
    """Configuration for backpressure system."""
    
    # Rate limiting
    max_requests_per_second: float = 100.0
    burst_capacity: int = 200
    sliding_window_seconds: int = 60
    
    # Queue management
    max_queue_size: int = 1000
    queue_timeout_seconds: float = 30.0
    priority_levels: int = 3
    
    # Circuit breaker
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_max_calls: int = 3
    
    # Resource monitoring
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 85.0
    max_disk_io_percent: float = 90.0
    
    # Adaptive throttling
    enable_adaptive_throttling: bool = True
    throttle_step_percent: float = 10.0
    recovery_step_percent: float = 5.0
    
    # Graceful degradation
    enable_graceful_degradation: bool = True
    degradation_levels: List[str] = None
    
    def __post_init__(self):
        if self.degradation_levels is None:
            self.degradation_levels = ['normal', 'reduced_features', 'essential_only', 'maintenance_mode']


@dataclass
class BackpressureMetrics:
    """Metrics from backpressure system."""
    
    timestamp: str
    
    # Request metrics
    requests_allowed: int = 0
    requests_rejected: int = 0
    requests_queued: int = 0
    requests_timeout: int = 0
    
    # Rate limiting
    current_rate: float = 0.0
    tokens_available: int = 0
    rate_limit_active: bool = False
    
    # Queue metrics
    queue_size: int = 0
    avg_queue_time_ms: float = 0.0
    queue_full_rejections: int = 0
    
    # Circuit breaker
    circuit_state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    last_failure_time: Optional[str] = None
    
    # Resource usage
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_io_percent: float = 0.0
    
    # Throttling
    throttle_level: float = 0.0
    current_degradation: str = "normal"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RequestContext:
    """Context for individual request."""
    
    request_id: str
    timestamp: float
    priority: int = 1  # 0=highest, 2=lowest
    timeout_seconds: float = 30.0
    metadata: Dict[str, Any] = None
    
    # Processing info
    queue_time_ms: Optional[float] = None
    processing_time_ms: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RateLimiter:
    """Token bucket rate limiter with sliding window."""
    
    def __init__(self, config: BackpressureConfig):
        self.config = config
        self.tokens = config.burst_capacity
        self.last_refill = time.time()
        self.request_history = deque()
        self.lock = threading.Lock()
    
    def allow_request(self) -> Tuple[bool, Dict[str, Any]]:
        """Check if request should be allowed."""
        
        with self.lock:
            now = time.time()
            
            # Refill tokens
            time_passed = now - self.last_refill
            tokens_to_add = time_passed * self.config.max_requests_per_second
            self.tokens = min(self.config.burst_capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            
            # Clean old requests from sliding window
            cutoff_time = now - self.config.sliding_window_seconds
            while self.request_history and self.request_history[0] < cutoff_time:
                self.request_history.popleft()
            
            # Check rate in sliding window
            current_rate = len(self.request_history) / self.config.sliding_window_seconds
            
            # Check token availability
            if self.tokens >= 1:
                self.tokens -= 1
                self.request_history.append(now)
                
                return True, {
                    'tokens_remaining': int(self.tokens),
                    'current_rate': current_rate,
                    'rate_limit_active': False
                }
            else:
                return False, {
                    'tokens_remaining': 0,
                    'current_rate': current_rate,
                    'rate_limit_active': True,
                    'retry_after_seconds': 1.0 / self.config.max_requests_per_second
                }


class CircuitBreaker:
    """Circuit breaker for downstream service protection."""
    
    def __init__(self, config: BackpressureConfig):
        self.config = config
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self.lock = threading.Lock()
    
    def call_allowed(self) -> Tuple[bool, str]:
        """Check if call should be allowed."""
        
        with self.lock:
            now = time.time()
            
            if self.state == "closed":
                return True, "circuit_closed"
            
            elif self.state == "open":
                # Check if recovery timeout has passed
                if (self.last_failure_time and 
                    now - self.last_failure_time >= self.config.recovery_timeout_seconds):
                    self.state = "half_open"
                    self.half_open_calls = 0
                    return True, "circuit_half_open"
                else:
                    return False, "circuit_open"
            
            else:  # half_open
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True, "circuit_half_open"
                else:
                    return False, "circuit_half_open_limit"
    
    def record_success(self):
        """Record successful call."""
        
        with self.lock:
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
                self.half_open_calls = 0
    
    def record_failure(self):
        """Record failed call."""
        
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == "closed":
                if self.failure_count >= self.config.failure_threshold:
                    self.state = "open"
            elif self.state == "half_open":
                self.state = "open"
                self.half_open_calls = 0


class PriorityQueue:
    """Priority queue with timeout and size limits."""
    
    def __init__(self, config: BackpressureConfig):
        self.config = config
        self.queues = [deque() for _ in range(config.priority_levels)]
        self.size = 0
        self.condition = asyncio.Condition()
        self.metrics = {'timeouts': 0, 'rejections': 0}
    
    async def put(self, item: RequestContext) -> bool:
        """Add item to queue, return False if queue is full."""
        
        async with self.condition:
            if self.size >= self.config.max_queue_size:
                self.metrics['rejections'] += 1
                return False
            
            priority = min(item.priority, len(self.queues) - 1)
            self.queues[priority].append(item)
            self.size += 1
            self.condition.notify()
            return True
    
    async def get(self, timeout_seconds: Optional[float] = None) -> Optional[RequestContext]:
        """Get highest priority item from queue."""
        
        timeout_seconds = timeout_seconds or self.config.queue_timeout_seconds
        
        async with self.condition:
            end_time = time.time() + timeout_seconds
            
            while self.size == 0:
                remaining = end_time - time.time()
                if remaining <= 0:
                    return None
                
                try:
                    await asyncio.wait_for(self.condition.wait(), remaining)
                except asyncio.TimeoutError:
                    return None
            
            # Get from highest priority queue
            for queue in self.queues:
                if queue:
                    item = queue.popleft()
                    self.size -= 1
                    
                    # Check if item has timed out
                    if time.time() - item.timestamp > item.timeout_seconds:
                        self.metrics['timeouts'] += 1
                        continue
                    
                    return item
            
            return None
    
    def get_size(self) -> int:
        """Get current queue size."""
        return self.size
    
    def get_metrics(self) -> Dict[str, int]:
        """Get queue metrics."""
        return self.metrics.copy()


class ResourceMonitor:
    """Monitors system resources for adaptive throttling."""
    
    def __init__(self, config: BackpressureConfig):
        self.config = config
        self.cpu_history = deque(maxlen=60)  # 1 minute history
        self.memory_history = deque(maxlen=60)
        self.disk_io_history = deque(maxlen=60)
        self.last_update = 0
        self._process = psutil.Process()
    
    def update_metrics(self):
        """Update resource metrics."""
        
        now = time.time()
        if now - self.last_update < 1.0:  # Update at most once per second
            return
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_history.append(cpu_percent)
            
            # Memory usage
            memory_info = psutil.virtual_memory()
            self.memory_history.append(memory_info.percent)
            
            # Disk I/O (simplified)
            disk_io = psutil.disk_io_counters()
            if hasattr(self, '_last_disk_io'):
                io_delta = (disk_io.read_bytes + disk_io.write_bytes - 
                           self._last_disk_io.read_bytes - self._last_disk_io.write_bytes)
                # Convert to rough percentage (very simplified)
                io_percent = min(100, io_delta / 1024 / 1024)  # MB per second
            else:
                io_percent = 0
            
            self._last_disk_io = disk_io
            self.disk_io_history.append(io_percent)
            
            self.last_update = now
            
        except Exception as e:
            logger.warning(f"Error updating resource metrics: {e}")
    
    def get_resource_pressure(self) -> Dict[str, float]:
        """Get current resource pressure levels."""
        
        self.update_metrics()
        
        def avg_recent(history, window=10):
            recent = list(history)[-window:] if len(history) >= window else list(history)
            return statistics.mean(recent) if recent else 0
        
        return {
            'cpu_percent': avg_recent(self.cpu_history),
            'memory_percent': avg_recent(self.memory_history),
            'disk_io_percent': avg_recent(self.disk_io_history)
        }
    
    def is_overloaded(self) -> Tuple[bool, List[str]]:
        """Check if system is overloaded."""
        
        pressure = self.get_resource_pressure()
        issues = []
        
        if pressure['cpu_percent'] > self.config.max_cpu_percent:
            issues.append(f"CPU: {pressure['cpu_percent']:.1f}%")
        
        if pressure['memory_percent'] > self.config.max_memory_percent:
            issues.append(f"Memory: {pressure['memory_percent']:.1f}%")
        
        if pressure['disk_io_percent'] > self.config.max_disk_io_percent:
            issues.append(f"Disk I/O: {pressure['disk_io_percent']:.1f}%")
        
        return len(issues) > 0, issues


class BackpressureManager:
    """Main backpressure management system."""
    
    def __init__(self, config: Optional[BackpressureConfig] = None):
        """Initialize backpressure manager."""
        
        self.config = config or BackpressureConfig()
        
        # Initialize components
        self.rate_limiter = RateLimiter(self.config)
        self.circuit_breaker = CircuitBreaker(self.config)
        self.priority_queue = PriorityQueue(self.config)
        self.resource_monitor = ResourceMonitor(self.config)
        
        # State management
        self.throttle_level = 0.0  # 0.0 = no throttling, 1.0 = maximum throttling
        self.current_degradation = self.config.degradation_levels[0]  # 'normal'
        self.active = True
        
        # Metrics tracking
        self.metrics_history = deque(maxlen=1000)
        self.request_stats = {'allowed': 0, 'rejected': 0, 'queued': 0}
        
        # Background tasks
        self._monitoring_task = None
        self._started = False
        
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """Start background monitoring tasks."""
        
        if self._started:
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._started = True
        self.logger.info("Backpressure manager started")
    
    async def stop(self):
        """Stop background tasks."""
        
        self.active = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self._started = False
        self.logger.info("Backpressure manager stopped")
    
    async def process_request(
        self, 
        request_handler: Callable,
        request_context: RequestContext
    ) -> Tuple[Any, BackpressureMetrics]:
        """
        Process request through backpressure system.
        
        Args:
            request_handler: Async function to handle the request
            request_context: Request context and metadata
            
        Returns:
            Tuple of (result, metrics)
        """
        
        start_time = time.time()
        metrics_start = self._capture_metrics()
        
        try:
            # Step 1: Rate limiting check
            rate_allowed, rate_info = self.rate_limiter.allow_request()
            
            if not rate_allowed:
                self.request_stats['rejected'] += 1
                raise BackpressureException(
                    "Rate limit exceeded", 
                    retry_after=rate_info.get('retry_after_seconds', 1.0),
                    reason='rate_limit'
                )
            
            # Step 2: Circuit breaker check
            circuit_allowed, circuit_reason = self.circuit_breaker.call_allowed()
            
            if not circuit_allowed:
                self.request_stats['rejected'] += 1
                raise BackpressureException(
                    "Circuit breaker open",
                    retry_after=30.0,
                    reason='circuit_breaker'
                )
            
            # Step 3: Resource pressure check
            overloaded, pressure_issues = self.resource_monitor.is_overloaded()
            
            if overloaded and self.config.enable_adaptive_throttling:
                # Apply throttling
                await self._apply_throttling()
                
                if self.throttle_level > 0.8:  # Heavy throttling
                    self.request_stats['rejected'] += 1
                    raise BackpressureException(
                        f"System overloaded: {', '.join(pressure_issues)}",
                        retry_after=5.0,
                        reason='resource_pressure'
                    )
            
            # Step 4: Queue management (if needed)
            if self.priority_queue.get_size() > 0 or self.throttle_level > 0.5:
                # Queue the request
                queue_start = time.time()
                queued = await self.priority_queue.put(request_context)
                
                if not queued:
                    self.request_stats['rejected'] += 1
                    raise BackpressureException(
                        "Request queue full",
                        retry_after=2.0,
                        reason='queue_full'
                    )
                
                self.request_stats['queued'] += 1
                
                # Wait for queue processing
                processed_context = await self.priority_queue.get()
                if not processed_context:
                    raise BackpressureException(
                        "Request timeout in queue",
                        retry_after=1.0,
                        reason='queue_timeout'
                    )
                
                request_context.queue_time_ms = (time.time() - queue_start) * 1000
            
            # Step 5: Execute request with degradation if needed
            try:
                processing_start = time.time()
                
                if self.current_degradation != 'normal':
                    result = await self._execute_with_degradation(
                        request_handler, request_context
                    )
                else:
                    result = await request_handler(request_context)
                
                request_context.processing_time_ms = (time.time() - processing_start) * 1000
                request_context.result = result
                
                # Record success
                self.circuit_breaker.record_success()
                self.request_stats['allowed'] += 1
                
                return result, self._capture_metrics()
                
            except Exception as e:
                # Record failure
                self.circuit_breaker.record_failure()
                request_context.error = str(e)
                raise
        
        except BackpressureException:
            raise
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise BackpressureException(f"Request processing failed: {str(e)}", reason='processing_error')
    
    async def _monitoring_loop(self):
        """Background monitoring and adaptation loop."""
        
        while self.active:
            try:
                # Update resource metrics
                self.resource_monitor.update_metrics()
                
                # Adaptive throttling
                if self.config.enable_adaptive_throttling:
                    await self._update_throttling()
                
                # Graceful degradation
                if self.config.enable_graceful_degradation:
                    await self._update_degradation()
                
                # Record metrics
                metrics = self._capture_metrics()
                self.metrics_history.append(metrics)
                
                await asyncio.sleep(5.0)  # Monitor every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(1.0)
    
    async def _update_throttling(self):
        """Update adaptive throttling based on resource pressure."""
        
        overloaded, _ = self.resource_monitor.is_overloaded()
        
        if overloaded:
            # Increase throttling
            new_throttle = min(1.0, self.throttle_level + self.config.throttle_step_percent / 100)
            if new_throttle != self.throttle_level:
                self.throttle_level = new_throttle
                self.logger.info(f"Increased throttling to {self.throttle_level:.2f}")
        else:
            # Decrease throttling
            if self.throttle_level > 0:
                new_throttle = max(0.0, self.throttle_level - self.config.recovery_step_percent / 100)
                if new_throttle != self.throttle_level:
                    self.throttle_level = new_throttle
                    self.logger.info(f"Decreased throttling to {self.throttle_level:.2f}")
    
    async def _update_degradation(self):
        """Update graceful degradation level."""
        
        pressure = self.resource_monitor.get_resource_pressure()
        max_pressure = max(
            pressure['cpu_percent'] / self.config.max_cpu_percent,
            pressure['memory_percent'] / self.config.max_memory_percent,
            pressure['disk_io_percent'] / self.config.max_disk_io_percent
        )
        
        # Determine degradation level
        if max_pressure >= 1.2:
            target_degradation = 'maintenance_mode'
        elif max_pressure >= 1.0:
            target_degradation = 'essential_only'
        elif max_pressure >= 0.8:
            target_degradation = 'reduced_features'
        else:
            target_degradation = 'normal'
        
        if target_degradation != self.current_degradation:
            self.current_degradation = target_degradation
            self.logger.warning(f"Degradation level changed to: {target_degradation}")
    
    async def _execute_with_degradation(
        self, 
        request_handler: Callable,
        request_context: RequestContext
    ) -> Any:
        """Execute request with current degradation level."""
        
        # Add degradation metadata
        request_context.metadata['degradation_level'] = self.current_degradation
        
        if self.current_degradation == 'maintenance_mode':
            raise BackpressureException(
                "System in maintenance mode", 
                retry_after=60.0,
                reason='maintenance_mode'
            )
        
        # Execute with degradation context
        return await request_handler(request_context)
    
    async def _apply_throttling(self):
        """Apply current throttling level."""
        
        if self.throttle_level > 0:
            # Add delay based on throttle level
            delay = self.throttle_level * 0.1  # Up to 100ms delay
            await asyncio.sleep(delay)
    
    def _capture_metrics(self) -> BackpressureMetrics:
        """Capture current metrics snapshot."""
        
        pressure = self.resource_monitor.get_resource_pressure()
        queue_metrics = self.priority_queue.get_metrics()
        
        return BackpressureMetrics(
            timestamp=datetime.now().isoformat(),
            requests_allowed=self.request_stats['allowed'],
            requests_rejected=self.request_stats['rejected'],
            requests_queued=self.request_stats['queued'],
            requests_timeout=queue_metrics.get('timeouts', 0),
            current_rate=len(self.rate_limiter.request_history),
            tokens_available=int(self.rate_limiter.tokens),
            rate_limit_active=self.rate_limiter.tokens < 1,
            queue_size=self.priority_queue.get_size(),
            queue_full_rejections=queue_metrics.get('rejections', 0),
            circuit_state=self.circuit_breaker.state,
            failure_count=self.circuit_breaker.failure_count,
            last_failure_time=datetime.fromtimestamp(self.circuit_breaker.last_failure_time).isoformat() if self.circuit_breaker.last_failure_time else None,
            cpu_percent=pressure['cpu_percent'],
            memory_percent=pressure['memory_percent'],
            disk_io_percent=pressure['disk_io_percent'],
            throttle_level=self.throttle_level,
            current_degradation=self.current_degradation
        )
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive status summary."""
        
        metrics = self._capture_metrics()
        
        return {
            'active': self.active,
            'degradation_level': self.current_degradation,
            'throttle_level': self.throttle_level,
            'circuit_state': metrics.circuit_state,
            'queue_size': metrics.queue_size,
            'current_rate': metrics.current_rate,
            'resource_pressure': {
                'cpu': metrics.cpu_percent,
                'memory': metrics.memory_percent,
                'disk_io': metrics.disk_io_percent
            },
            'request_stats': self.request_stats.copy(),
            'health_score': self._calculate_health_score(metrics)
        }
    
    def _calculate_health_score(self, metrics: BackpressureMetrics) -> float:
        """Calculate overall system health score (0-1)."""
        
        # Start with perfect health
        health = 1.0
        
        # Resource pressure penalty
        max_resource = max(
            metrics.cpu_percent / self.config.max_cpu_percent,
            metrics.memory_percent / self.config.max_memory_percent,
            metrics.disk_io_percent / self.config.max_disk_io_percent
        )
        health -= min(0.4, max_resource - 0.7)  # Penalty starts at 70%
        
        # Circuit breaker penalty
        if metrics.circuit_state == 'open':
            health -= 0.3
        elif metrics.circuit_state == 'half_open':
            health -= 0.1
        
        # Queue pressure penalty
        queue_ratio = metrics.queue_size / self.config.max_queue_size
        health -= min(0.2, queue_ratio)
        
        # Throttling penalty
        health -= self.throttle_level * 0.1
        
        return max(0.0, health)


class BackpressureException(Exception):
    """Exception raised when backpressure limits are exceeded."""
    
    def __init__(self, message: str, retry_after: float = 1.0, reason: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.reason = reason


# Convenience functions

async def create_backpressure_manager(
    max_rps: float = 100,
    max_queue_size: int = 1000,
    enable_circuit_breaker: bool = True
) -> BackpressureManager:
    """Create and start backpressure manager with common settings."""
    
    config = BackpressureConfig(
        max_requests_per_second=max_rps,
        max_queue_size=max_queue_size,
        failure_threshold=5 if enable_circuit_breaker else 999999
    )
    
    manager = BackpressureManager(config)
    await manager.start()
    
    return manager


# Global instance for easy access
_global_backpressure_manager = None


async def get_global_backpressure_manager() -> BackpressureManager:
    """Get or create global backpressure manager."""
    
    global _global_backpressure_manager
    
    if _global_backpressure_manager is None:
        _global_backpressure_manager = await create_backpressure_manager()
    
    return _global_backpressure_manager