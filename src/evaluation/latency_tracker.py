"""
Real-time Latency Percentile Tracking for Phase 4.2

Implements comprehensive latency monitoring and percentile calculation including:
- Real-time p95/p99 latency calculation with sliding windows
- Latency distribution analysis and alerting
- Tail latency anomaly detection
- Integration with MCP server middleware for automatic tracking
- High-performance percentile estimation using quantile sketches
"""

import time
import threading
from collections import deque
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
import statistics
import bisect
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement:
    """Single latency measurement with context."""
    
    timestamp: float
    latency_ms: float
    operation: str
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    request_size: Optional[int] = None
    
    # Context about the measurement
    concurrent_requests: Optional[int] = None
    cache_hit: Optional[bool] = None
    retry_count: Optional[int] = None


@dataclass
class LatencySnapshot:
    """Latency percentiles snapshot for a time window."""
    
    timestamp: str
    window_duration_seconds: int
    measurement_count: int
    
    # Core percentiles
    p50_ms: float
    p95_ms: float
    p99_ms: float
    p999_ms: float
    
    # Additional statistics
    min_ms: float
    max_ms: float
    mean_ms: float
    std_dev_ms: float
    
    # Distribution information
    outlier_count: int
    outlier_threshold_ms: float
    
    # Performance assessment
    sla_violations: int  # Count of measurements above SLA threshold
    sla_threshold_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LatencyAlert:
    """Latency alert when thresholds are exceeded."""
    
    timestamp: str
    alert_type: str  # "threshold_exceeded", "spike_detected", "degradation_trend"
    severity: str    # "warning", "critical"
    
    # Alert details
    current_value_ms: float
    threshold_ms: float
    operation: Optional[str] = None
    
    # Context
    measurement_count: int
    window_duration_seconds: int
    
    description: str = ""


class QuantileSketch:
    """Efficient quantile estimation for streaming latency data."""
    
    def __init__(self, max_samples: int = 10000):
        """
        Initialize quantile sketch.
        
        Args:
            max_samples: Maximum samples to keep for exact quantiles
        """
        self.max_samples = max_samples
        self.samples: List[float] = []
        self.sorted = True
        self.total_count = 0
    
    def add(self, value: float):
        """Add new value to sketch."""
        self.samples.append(value)
        self.sorted = False
        self.total_count += 1
        
        # Keep only recent samples for memory efficiency
        if len(self.samples) > self.max_samples:
            # Remove oldest samples (approximate)
            remove_count = len(self.samples) - self.max_samples
            self.samples = self.samples[remove_count:]
        
        # Re-sort periodically for performance
        if len(self.samples) % 1000 == 0:
            self._ensure_sorted()
    
    def quantile(self, q: float) -> float:
        """
        Get quantile value.
        
        Args:
            q: Quantile (0.0 to 1.0)
            
        Returns:
            Quantile value
        """
        if not self.samples:
            return 0.0
        
        self._ensure_sorted()
        
        if q <= 0:
            return self.samples[0]
        if q >= 1:
            return self.samples[-1]
        
        index = q * (len(self.samples) - 1)
        
        if index.is_integer():
            return self.samples[int(index)]
        else:
            # Linear interpolation
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(self.samples) - 1)
            
            lower_value = self.samples[lower_index]
            upper_value = self.samples[upper_index]
            
            fraction = index - lower_index
            return lower_value + fraction * (upper_value - lower_value)
    
    def _ensure_sorted(self):
        """Ensure samples are sorted."""
        if not self.sorted:
            self.samples.sort()
            self.sorted = True


class SlidingWindowTracker:
    """Sliding window for time-based latency tracking."""
    
    def __init__(self, window_duration_seconds: int = 60):
        """
        Initialize sliding window tracker.
        
        Args:
            window_duration_seconds: Window duration for tracking
        """
        self.window_duration = window_duration_seconds
        self.measurements: deque = deque()
        self.quantile_sketch = QuantileSketch()
        self.lock = threading.RLock()
    
    def add_measurement(self, measurement: LatencyMeasurement):
        """Add new latency measurement."""
        with self.lock:
            current_time = time.time()
            
            # Add new measurement
            self.measurements.append(measurement)
            self.quantile_sketch.add(measurement.latency_ms)
            
            # Remove old measurements outside window
            cutoff_time = current_time - self.window_duration
            while self.measurements and self.measurements[0].timestamp < cutoff_time:
                self.measurements.popleft()
    
    def get_percentiles(self) -> Tuple[float, float, float, float]:
        """
        Get current percentiles (p50, p95, p99, p999).
        
        Returns:
            Tuple of (p50, p95, p99, p999) in milliseconds
        """
        with self.lock:
            if not self.measurements:
                return 0.0, 0.0, 0.0, 0.0
            
            # Use quantile sketch for efficiency
            p50 = self.quantile_sketch.quantile(0.50)
            p95 = self.quantile_sketch.quantile(0.95)
            p99 = self.quantile_sketch.quantile(0.99)
            p999 = self.quantile_sketch.quantile(0.999)
            
            return p50, p95, p99, p999
    
    def get_statistics(self) -> Dict[str, float]:
        """Get comprehensive statistics for current window."""
        with self.lock:
            if not self.measurements:
                return {}
            
            latencies = [m.latency_ms for m in self.measurements]
            
            return {
                'count': len(latencies),
                'min': min(latencies),
                'max': max(latencies),
                'mean': statistics.mean(latencies),
                'std_dev': statistics.stdev(latencies) if len(latencies) > 1 else 0.0
            }
    
    def get_measurement_count(self) -> int:
        """Get number of measurements in current window."""
        with self.lock:
            return len(self.measurements)


class LatencyTracker:
    """Main latency tracking and monitoring system."""
    
    def __init__(
        self,
        window_duration_seconds: int = 60,
        snapshot_interval_seconds: int = 10,
        results_dir: str = "./latency_tracking"
    ):
        """
        Initialize latency tracker.
        
        Args:
            window_duration_seconds: Sliding window duration
            snapshot_interval_seconds: How often to take snapshots
            results_dir: Directory for storing results
        """
        self.window_duration = window_duration_seconds
        self.snapshot_interval = snapshot_interval_seconds
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Tracking per operation type
        self.operation_trackers: Dict[str, SlidingWindowTracker] = {}
        
        # Global tracker for all operations
        self.global_tracker = SlidingWindowTracker(window_duration_seconds)
        
        # Alert configuration
        self.sla_thresholds = {
            'p95': 1000.0,  # 1 second P95 SLA
            'p99': 2000.0   # 2 second P99 SLA
        }
        self.outlier_threshold_multiplier = 3.0  # 3x mean is outlier
        
        # Alert tracking
        self.alerts: deque = deque(maxlen=1000)
        self.alert_callbacks: List[Callable[[LatencyAlert], None]] = []
        
        # Snapshot history
        self.snapshots: deque = deque(maxlen=10000)
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Background tasks
        self.snapshot_task = None
        self.stop_event = threading.Event()
        
        self.logger = logging.getLogger(__name__)
    
    def start(self):
        """Start background tracking tasks."""
        if self.snapshot_task is None or not self.snapshot_task.is_alive():
            self.stop_event.clear()
            self.snapshot_task = threading.Thread(target=self._snapshot_worker, daemon=True)
            self.snapshot_task.start()
            self.logger.info("Latency tracker started")
    
    def stop(self):
        """Stop background tracking tasks."""
        self.stop_event.set()
        if self.snapshot_task and self.snapshot_task.is_alive():
            self.snapshot_task.join(timeout=5)
        self.logger.info("Latency tracker stopped")
    
    def record_latency(
        self,
        latency_ms: float,
        operation: str = "default",
        trace_id: Optional[str] = None,
        **context
    ):
        """
        Record new latency measurement.
        
        Args:
            latency_ms: Latency in milliseconds
            operation: Operation name for categorization
            trace_id: Optional trace ID for correlation
            **context: Additional context (user_id, request_size, etc.)
        """
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            latency_ms=latency_ms,
            operation=operation,
            trace_id=trace_id,
            **context
        )
        
        with self.lock:
            # Add to global tracker
            self.global_tracker.add_measurement(measurement)
            
            # Add to operation-specific tracker
            if operation not in self.operation_trackers:
                self.operation_trackers[operation] = SlidingWindowTracker(self.window_duration)
            
            self.operation_trackers[operation].add_measurement(measurement)
        
        # Check for immediate alerts
        self._check_alerts(measurement)
    
    def get_current_percentiles(self, operation: Optional[str] = None) -> Tuple[float, float, float, float]:
        """
        Get current latency percentiles.
        
        Args:
            operation: Specific operation (None for global)
            
        Returns:
            Tuple of (p50, p95, p99, p999)
        """
        with self.lock:
            if operation and operation in self.operation_trackers:
                return self.operation_trackers[operation].get_percentiles()
            else:
                return self.global_tracker.get_percentiles()
    
    def get_current_snapshot(self, operation: Optional[str] = None) -> LatencySnapshot:
        """
        Get current latency snapshot.
        
        Args:
            operation: Specific operation (None for global)
            
        Returns:
            Current latency snapshot
        """
        with self.lock:
            tracker = (self.operation_trackers.get(operation, self.global_tracker) 
                      if operation else self.global_tracker)
            
            p50, p95, p99, p999 = tracker.get_percentiles()
            stats = tracker.get_statistics()
            
            # Calculate outliers
            outlier_threshold = stats.get('mean', 0) * self.outlier_threshold_multiplier
            outlier_count = 0
            
            for measurement in tracker.measurements:
                if measurement.latency_ms > outlier_threshold:
                    outlier_count += 1
            
            # Calculate SLA violations
            sla_violations = 0
            sla_threshold = self.sla_thresholds.get('p95', 1000.0)
            
            for measurement in tracker.measurements:
                if measurement.latency_ms > sla_threshold:
                    sla_violations += 1
            
            return LatencySnapshot(
                timestamp=datetime.now().isoformat(),
                window_duration_seconds=self.window_duration,
                measurement_count=stats.get('count', 0),
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                p999_ms=p999,
                min_ms=stats.get('min', 0),
                max_ms=stats.get('max', 0),
                mean_ms=stats.get('mean', 0),
                std_dev_ms=stats.get('std_dev', 0),
                outlier_count=outlier_count,
                outlier_threshold_ms=outlier_threshold,
                sla_violations=sla_violations,
                sla_threshold_ms=sla_threshold
            )
    
    def get_operation_list(self) -> List[str]:
        """Get list of tracked operations."""
        with self.lock:
            return list(self.operation_trackers.keys())
    
    def add_alert_callback(self, callback: Callable[[LatencyAlert], None]):
        """Add callback function for latency alerts."""
        self.alert_callbacks.append(callback)
    
    def get_recent_alerts(self, count: int = 10) -> List[LatencyAlert]:
        """Get recent latency alerts."""
        with self.lock:
            return list(self.alerts)[-count:]
    
    def get_snapshot_history(self, count: int = 100) -> List[LatencySnapshot]:
        """Get recent snapshot history."""
        with self.lock:
            return list(self.snapshots)[-count:]
    
    def _check_alerts(self, measurement: LatencyMeasurement):
        """Check if measurement triggers any alerts."""
        
        # Check SLA threshold alerts
        for percentile, threshold in self.sla_thresholds.items():
            if measurement.latency_ms > threshold:
                alert = LatencyAlert(
                    timestamp=datetime.now().isoformat(),
                    alert_type="threshold_exceeded",
                    severity="critical" if measurement.latency_ms > threshold * 2 else "warning",
                    current_value_ms=measurement.latency_ms,
                    threshold_ms=threshold,
                    operation=measurement.operation,
                    measurement_count=1,
                    window_duration_seconds=0,
                    description=f"Latency {measurement.latency_ms:.1f}ms exceeds {percentile} SLA {threshold}ms"
                )
                
                self._trigger_alert(alert)
        
        # Check for latency spikes
        p50, p95, p99, p999 = self.get_current_percentiles(measurement.operation)
        
        if measurement.latency_ms > p95 * 3:  # 3x P95 is a spike
            alert = LatencyAlert(
                timestamp=datetime.now().isoformat(),
                alert_type="spike_detected",
                severity="warning",
                current_value_ms=measurement.latency_ms,
                threshold_ms=p95 * 3,
                operation=measurement.operation,
                measurement_count=1,
                window_duration_seconds=0,
                description=f"Latency spike: {measurement.latency_ms:.1f}ms (3x P95: {p95*3:.1f}ms)"
            )
            
            self._trigger_alert(alert)
    
    def _trigger_alert(self, alert: LatencyAlert):
        """Trigger latency alert and notify callbacks."""
        with self.lock:
            self.alerts.append(alert)
        
        self.logger.warning(f"Latency alert: {alert.description}")
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Alert callback error: {str(e)}")
    
    def _snapshot_worker(self):
        """Background worker for taking periodic snapshots."""
        self.logger.info("Snapshot worker started")
        
        while not self.stop_event.wait(self.snapshot_interval):
            try:
                # Take global snapshot
                global_snapshot = self.get_current_snapshot()
                
                with self.lock:
                    self.snapshots.append(global_snapshot)
                
                # Check for performance degradation trends
                self._check_degradation_trends()
                
                # Periodically save snapshots
                if len(self.snapshots) % 100 == 0:  # Every 1000 snapshots
                    self._save_snapshots_to_disk()
                
            except Exception as e:
                self.logger.error(f"Snapshot worker error: {str(e)}")
        
        self.logger.info("Snapshot worker stopped")
    
    def _check_degradation_trends(self):
        """Check for latency degradation trends."""
        if len(self.snapshots) < 10:  # Need sufficient history
            return
        
        recent_snapshots = list(self.snapshots)[-10:]  # Last 10 snapshots
        
        # Check P95 trend
        p95_values = [s.p95_ms for s in recent_snapshots]
        
        # Simple trend detection: is P95 consistently increasing?
        increasing_count = 0
        for i in range(1, len(p95_values)):
            if p95_values[i] > p95_values[i-1]:
                increasing_count += 1
        
        # If P95 is increasing in >70% of recent snapshots, it's a trend
        if increasing_count >= 7:
            current_p95 = p95_values[-1]
            baseline_p95 = p95_values[0]
            
            if current_p95 > baseline_p95 * 1.5:  # 50% increase
                alert = LatencyAlert(
                    timestamp=datetime.now().isoformat(),
                    alert_type="degradation_trend",
                    severity="warning",
                    current_value_ms=current_p95,
                    threshold_ms=baseline_p95 * 1.5,
                    measurement_count=len(recent_snapshots),
                    window_duration_seconds=len(recent_snapshots) * self.snapshot_interval,
                    description=f"P95 latency degradation trend: {baseline_p95:.1f}ms → {current_p95:.1f}ms"
                )
                
                self._trigger_alert(alert)
    
    def _save_snapshots_to_disk(self):
        """Save snapshot history to disk."""
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"latency_snapshots_{timestamp_str}.json"
        filepath = self.results_dir / filename
        
        try:
            snapshots_data = {
                'timestamp': datetime.now().isoformat(),
                'window_duration_seconds': self.window_duration,
                'snapshot_interval_seconds': self.snapshot_interval,
                'snapshots': [s.to_dict() for s in list(self.snapshots)[-1000:]]  # Last 1000 snapshots
            }
            
            with open(filepath, 'w') as f:
                json.dump(snapshots_data, f, indent=2)
            
            self.logger.info(f"Saved {len(snapshots_data['snapshots'])} snapshots to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Failed to save snapshots: {str(e)}")


class LatencyMiddleware:
    """Middleware for automatic latency tracking in MCP server."""
    
    def __init__(self, tracker: LatencyTracker):
        """
        Initialize latency middleware.
        
        Args:
            tracker: Latency tracker instance
        """
        self.tracker = tracker
    
    async def __call__(self, request, call_next):
        """ASGI middleware for latency tracking."""
        
        # Extract operation from request
        operation = self._extract_operation_name(request)
        trace_id = self._extract_trace_id(request)
        
        # Measure latency
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Record successful request latency
            latency_ms = (time.time() - start_time) * 1000
            self.tracker.record_latency(
                latency_ms=latency_ms,
                operation=operation,
                trace_id=trace_id
            )
            
            return response
            
        except Exception as e:
            # Record failed request latency
            latency_ms = (time.time() - start_time) * 1000
            self.tracker.record_latency(
                latency_ms=latency_ms,
                operation=f"{operation}_error",
                trace_id=trace_id
            )
            raise
    
    def _extract_operation_name(self, request) -> str:
        """Extract operation name from request."""
        # This would be customized based on your request structure
        if hasattr(request, 'url') and hasattr(request.url, 'path'):
            path = request.url.path
            if '/retrieve_context' in path:
                return 'retrieve_context'
            elif '/store_context' in path:
                return 'store_context'
            else:
                return 'unknown'
        return 'unknown'
    
    def _extract_trace_id(self, request) -> Optional[str]:
        """Extract trace ID from request headers."""
        if hasattr(request, 'headers'):
            return request.headers.get('x-trace-id')
        return None


# Global latency tracker instance
_global_tracker: Optional[LatencyTracker] = None


def get_global_tracker() -> LatencyTracker:
    """Get global latency tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LatencyTracker()
        _global_tracker.start()
    return _global_tracker


def record_latency(latency_ms: float, operation: str = "default", **context):
    """Convenience function to record latency globally."""
    tracker = get_global_tracker()
    tracker.record_latency(latency_ms, operation, **context)


def get_current_percentiles(operation: Optional[str] = None) -> Tuple[float, float, float, float]:
    """Convenience function to get current percentiles globally."""
    tracker = get_global_tracker()
    return tracker.get_current_percentiles(operation)


# Context manager for automatic latency tracking
class LatencyContext:
    """Context manager for automatic latency measurement."""
    
    def __init__(self, operation: str, tracker: Optional[LatencyTracker] = None, **context):
        """
        Initialize latency context.
        
        Args:
            operation: Operation name
            tracker: Latency tracker (uses global if None)
            **context: Additional context
        """
        self.operation = operation
        self.tracker = tracker or get_global_tracker()
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            latency_ms = (time.time() - self.start_time) * 1000
            
            # Add error context if exception occurred
            if exc_type is not None:
                self.context['error'] = str(exc_val)
                operation = f"{self.operation}_error"
            else:
                operation = self.operation
            
            self.tracker.record_latency(latency_ms, operation, **self.context)


# Async context manager version
class AsyncLatencyContext:
    """Async context manager for latency measurement."""
    
    def __init__(self, operation: str, tracker: Optional[LatencyTracker] = None, **context):
        self.operation = operation
        self.tracker = tracker or get_global_tracker()
        self.context = context
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            latency_ms = (time.time() - self.start_time) * 1000
            
            if exc_type is not None:
                self.context['error'] = str(exc_val)
                operation = f"{self.operation}_error"
            else:
                operation = self.operation
            
            self.tracker.record_latency(latency_ms, operation, **self.context)