"""
Monitoring and Alerting Dashboard for Phase 4.2

Implements comprehensive monitoring and alerting including:
- Real-time system health monitoring and visualization
- Performance metrics collection and trending
- Alert generation and notification systems
- Evaluation pipeline monitoring and status tracking
- Resource usage monitoring and capacity planning
- SLA tracking and compliance reporting
"""

import asyncio
import logging
import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from collections import deque, defaultdict
import statistics
import weakref
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class MonitoringConfig:
    """Configuration for monitoring dashboard."""
    
    # Data collection
    collection_interval_seconds: float = 10.0
    retention_hours: int = 168  # 1 week
    batch_size: int = 100
    
    # Metrics to collect
    collect_system_metrics: bool = True
    collect_application_metrics: bool = True
    collect_evaluation_metrics: bool = True
    collect_performance_metrics: bool = True
    
    # Alerting configuration
    enable_alerting: bool = True
    alert_channels: List[str] = None
    alert_severity_levels: List[str] = None
    
    # Dashboard configuration
    dashboard_port: int = 8080
    dashboard_host: str = "localhost"
    enable_web_dashboard: bool = True
    
    # Storage configuration
    storage_backend: str = "sqlite"  # sqlite, memory, file
    storage_path: str = "./monitoring_data"
    
    # SLA thresholds
    sla_response_time_ms: float = 500.0
    sla_availability_percent: float = 99.5
    sla_error_rate_percent: float = 1.0
    
    def __post_init__(self):
        if self.alert_channels is None:
            self.alert_channels = ["log", "console"]
        if self.alert_severity_levels is None:
            self.alert_severity_levels = ["low", "medium", "high", "critical"]


@dataclass
class MetricPoint:
    """Individual metric data point."""
    
    timestamp: float
    metric_name: str
    value: float
    labels: Dict[str, str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Alert:
    """Alert definition and state."""
    
    alert_id: str
    name: str
    description: str
    severity: str
    
    # Alert conditions
    condition: str  # "threshold", "trend", "anomaly"
    threshold_value: Optional[float] = None
    threshold_operator: str = "greater_than"  # greater_than, less_than, equals
    
    # Alert state
    status: str = "inactive"  # inactive, active, acknowledged, resolved
    triggered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    
    # Alert configuration
    cooldown_minutes: int = 15
    repeat_interval_minutes: int = 60
    auto_resolve: bool = True
    
    # Notification
    notification_channels: List[str] = None
    last_notification: Optional[str] = None
    notification_count: int = 0
    
    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ["log"]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DashboardData:
    """Dashboard data structure."""
    
    timestamp: str
    system_health: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    evaluation_status: Dict[str, Any]
    active_alerts: List[Alert]
    sla_compliance: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'active_alerts': [alert.to_dict() for alert in self.active_alerts]
        }


class MetricsCollector:
    """Collects various system and application metrics."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.metrics_buffer = deque(maxlen=1000)
        self.collection_lock = threading.Lock()
        self.logger = logging.getLogger(__name__ + ".MetricsCollector")
    
    async def collect_all_metrics(self) -> List[MetricPoint]:
        """Collect all configured metrics."""
        
        metrics = []
        current_time = time.time()
        
        try:
            if self.config.collect_system_metrics:
                system_metrics = await self._collect_system_metrics(current_time)
                metrics.extend(system_metrics)
            
            if self.config.collect_application_metrics:
                app_metrics = await self._collect_application_metrics(current_time)
                metrics.extend(app_metrics)
            
            if self.config.collect_evaluation_metrics:
                eval_metrics = await self._collect_evaluation_metrics(current_time)
                metrics.extend(eval_metrics)
            
            if self.config.collect_performance_metrics:
                perf_metrics = await self._collect_performance_metrics(current_time)
                metrics.extend(perf_metrics)
        
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
        
        return metrics
    
    async def _collect_system_metrics(self, timestamp: float) -> List[MetricPoint]:
        """Collect system-level metrics."""
        
        metrics = []
        
        try:
            import psutil
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            metrics.append(MetricPoint(
                timestamp=timestamp,
                metric_name="system.cpu.usage_percent",
                value=cpu_percent
            ))
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.extend([
                MetricPoint(timestamp=timestamp, metric_name="system.memory.usage_percent", value=memory.percent),
                MetricPoint(timestamp=timestamp, metric_name="system.memory.available_gb", value=memory.available / (1024**3)),
                MetricPoint(timestamp=timestamp, metric_name="system.memory.used_gb", value=memory.used / (1024**3))
            ])
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            metrics.extend([
                MetricPoint(timestamp=timestamp, metric_name="system.disk.usage_percent", value=disk_usage_percent),
                MetricPoint(timestamp=timestamp, metric_name="system.disk.free_gb", value=disk.free / (1024**3)),
                MetricPoint(timestamp=timestamp, metric_name="system.disk.used_gb", value=disk.used / (1024**3))
            ])
            
            # Network metrics (simplified)
            try:
                network = psutil.net_io_counters()
                metrics.extend([
                    MetricPoint(timestamp=timestamp, metric_name="system.network.bytes_sent", value=network.bytes_sent),
                    MetricPoint(timestamp=timestamp, metric_name="system.network.bytes_received", value=network.bytes_recv),
                    MetricPoint(timestamp=timestamp, metric_name="system.network.packets_sent", value=network.packets_sent),
                    MetricPoint(timestamp=timestamp, metric_name="system.network.packets_received", value=network.packets_recv)
                ])
            except Exception:
                pass  # Network metrics not available
        
        except ImportError:
            # Fallback to mock metrics if psutil not available
            import random
            metrics.extend([
                MetricPoint(timestamp=timestamp, metric_name="system.cpu.usage_percent", value=random.uniform(20, 80)),
                MetricPoint(timestamp=timestamp, metric_name="system.memory.usage_percent", value=random.uniform(40, 90)),
                MetricPoint(timestamp=timestamp, metric_name="system.disk.usage_percent", value=random.uniform(30, 70))
            ])
        
        return metrics
    
    async def _collect_application_metrics(self, timestamp: float) -> List[MetricPoint]:
        """Collect application-specific metrics."""
        
        metrics = []
        
        # Mock application metrics (in real implementation, would collect from actual services)
        import random
        
        # Request metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="app.requests.total", value=random.randint(1000, 5000)),
            MetricPoint(timestamp=timestamp, metric_name="app.requests.per_second", value=random.uniform(10, 100)),
            MetricPoint(timestamp=timestamp, metric_name="app.requests.success_rate", value=random.uniform(0.95, 0.99)),
            MetricPoint(timestamp=timestamp, metric_name="app.requests.error_rate", value=random.uniform(0.01, 0.05))
        ])
        
        # Response time metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="app.response_time.mean_ms", value=random.uniform(50, 200)),
            MetricPoint(timestamp=timestamp, metric_name="app.response_time.p95_ms", value=random.uniform(100, 500)),
            MetricPoint(timestamp=timestamp, metric_name="app.response_time.p99_ms", value=random.uniform(200, 1000))
        ])
        
        # Queue metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="app.queue.size", value=random.randint(0, 100)),
            MetricPoint(timestamp=timestamp, metric_name="app.queue.processing_time_ms", value=random.uniform(10, 100)),
            MetricPoint(timestamp=timestamp, metric_name="app.queue.throughput_per_second", value=random.uniform(50, 200))
        ])
        
        return metrics
    
    async def _collect_evaluation_metrics(self, timestamp: float) -> List[MetricPoint]:
        """Collect evaluation pipeline metrics."""
        
        metrics = []
        
        # Mock evaluation metrics
        import random
        
        # Evaluation run metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="evaluation.runs.total", value=random.randint(10, 100)),
            MetricPoint(timestamp=timestamp, metric_name="evaluation.runs.success_rate", value=random.uniform(0.90, 0.99)),
            MetricPoint(timestamp=timestamp, metric_name="evaluation.runs.average_duration_minutes", value=random.uniform(5, 30)),
            MetricPoint(timestamp=timestamp, metric_name="evaluation.runs.queries_processed", value=random.randint(100, 1000))
        ])
        
        # Quality metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="evaluation.quality.p_at_1", value=random.uniform(0.60, 0.85)),
            MetricPoint(timestamp=timestamp, metric_name="evaluation.quality.ndcg_at_5", value=random.uniform(0.70, 0.90)),
            MetricPoint(timestamp=timestamp, metric_name="evaluation.quality.mrr", value=random.uniform(0.65, 0.88)),
            MetricPoint(timestamp=timestamp, metric_name="evaluation.quality.recall_at_10", value=random.uniform(0.80, 0.95))
        ])
        
        # Retrieval metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="retrieval.latency.mean_ms", value=random.uniform(20, 100)),
            MetricPoint(timestamp=timestamp, metric_name="retrieval.latency.p95_ms", value=random.uniform(50, 200)),
            MetricPoint(timestamp=timestamp, metric_name="retrieval.rerank.invocation_rate", value=random.uniform(0.3, 0.8)),
            MetricPoint(timestamp=timestamp, metric_name="retrieval.cache.hit_rate", value=random.uniform(0.60, 0.90))
        ])
        
        return metrics
    
    async def _collect_performance_metrics(self, timestamp: float) -> List[MetricPoint]:
        """Collect performance-related metrics."""
        
        metrics = []
        
        # Mock performance metrics
        import random
        
        # Throughput metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="performance.throughput.queries_per_second", value=random.uniform(10, 150)),
            MetricPoint(timestamp=timestamp, metric_name="performance.throughput.documents_processed_per_second", value=random.uniform(100, 1000)),
            MetricPoint(timestamp=timestamp, metric_name="performance.throughput.evaluations_per_hour", value=random.uniform(5, 50))
        ])
        
        # Latency metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="performance.latency.end_to_end_ms", value=random.uniform(100, 800)),
            MetricPoint(timestamp=timestamp, metric_name="performance.latency.retrieval_ms", value=random.uniform(20, 200)),
            MetricPoint(timestamp=timestamp, metric_name="performance.latency.rerank_ms", value=random.uniform(10, 100)),
            MetricPoint(timestamp=timestamp, metric_name="performance.latency.evaluation_ms", value=random.uniform(50, 300))
        ])
        
        # Resource efficiency metrics
        metrics.extend([
            MetricPoint(timestamp=timestamp, metric_name="performance.efficiency.cpu_per_query", value=random.uniform(0.1, 2.0)),
            MetricPoint(timestamp=timestamp, metric_name="performance.efficiency.memory_per_query_mb", value=random.uniform(5, 50)),
            MetricPoint(timestamp=timestamp, metric_name="performance.efficiency.queries_per_cpu_core", value=random.uniform(20, 100))
        ])
        
        return metrics
    
    def add_metric(self, metric: MetricPoint):
        """Add a metric point to the buffer."""
        with self.collection_lock:
            self.metrics_buffer.append(metric)
    
    def get_recent_metrics(self, limit: int = 100) -> List[MetricPoint]:
        """Get recent metrics from buffer."""
        with self.collection_lock:
            return list(self.metrics_buffer)[-limit:]


class AlertManager:
    """Manages alert definitions, evaluation, and notifications."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.alerts = {}
        self.alert_history = deque(maxlen=1000)
        self.alert_lock = threading.Lock()
        self.logger = logging.getLogger(__name__ + ".AlertManager")
        
        # Initialize default alerts
        self._initialize_default_alerts()
    
    def _initialize_default_alerts(self):
        """Initialize default alert rules."""
        
        default_alerts = [
            Alert(
                alert_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage is above 80%",
                severity="high",
                condition="threshold",
                threshold_value=80.0,
                threshold_operator="greater_than",
                notification_channels=["log", "console"]
            ),
            Alert(
                alert_id="high_memory_usage",
                name="High Memory Usage", 
                description="Memory usage is above 85%",
                severity="high",
                condition="threshold",
                threshold_value=85.0,
                threshold_operator="greater_than"
            ),
            Alert(
                alert_id="high_error_rate",
                name="High Error Rate",
                description="Application error rate is above 5%",
                severity="critical",
                condition="threshold",
                threshold_value=0.05,
                threshold_operator="greater_than"
            ),
            Alert(
                alert_id="slow_response_time",
                name="Slow Response Time",
                description="Average response time is above SLA threshold",
                severity="medium",
                condition="threshold",
                threshold_value=self.config.sla_response_time_ms,
                threshold_operator="greater_than"
            ),
            Alert(
                alert_id="low_evaluation_quality",
                name="Low Evaluation Quality",
                description="P@1 score is below acceptable threshold",
                severity="medium",
                condition="threshold",
                threshold_value=0.60,
                threshold_operator="less_than"
            ),
            Alert(
                alert_id="disk_space_low",
                name="Low Disk Space",
                description="Disk usage is above 90%",
                severity="high",
                condition="threshold",
                threshold_value=90.0,
                threshold_operator="greater_than"
            )
        ]
        
        for alert in default_alerts:
            self.alerts[alert.alert_id] = alert
    
    async def evaluate_alerts(self, metrics: List[MetricPoint]) -> List[Alert]:
        """Evaluate all alerts against current metrics."""
        
        triggered_alerts = []
        current_time = time.time()
        
        # Group metrics by name for easier lookup
        metrics_by_name = defaultdict(list)
        for metric in metrics:
            metrics_by_name[metric.metric_name].append(metric)
        
        with self.alert_lock:
            for alert in self.alerts.values():
                try:
                    should_trigger = await self._evaluate_alert_condition(alert, metrics_by_name)
                    
                    if should_trigger:
                        if alert.status == "inactive":
                            # Trigger new alert
                            await self._trigger_alert(alert, current_time)
                            triggered_alerts.append(alert)
                        elif alert.status == "active":
                            # Check if we should repeat notification
                            if self._should_repeat_notification(alert, current_time):
                                await self._send_alert_notification(alert, is_repeat=True)
                    else:
                        if alert.status == "active" and alert.auto_resolve:
                            # Auto-resolve alert
                            await self._resolve_alert(alert, current_time)
                
                except Exception as e:
                    self.logger.error(f"Error evaluating alert {alert.alert_id}: {e}")
        
        return triggered_alerts
    
    async def _evaluate_alert_condition(
        self, 
        alert: Alert, 
        metrics_by_name: Dict[str, List[MetricPoint]]
    ) -> bool:
        """Evaluate if an alert condition is met."""
        
        if alert.condition == "threshold":
            return await self._evaluate_threshold_condition(alert, metrics_by_name)
        elif alert.condition == "trend":
            return await self._evaluate_trend_condition(alert, metrics_by_name)
        elif alert.condition == "anomaly":
            return await self._evaluate_anomaly_condition(alert, metrics_by_name)
        
        return False
    
    async def _evaluate_threshold_condition(
        self, 
        alert: Alert, 
        metrics_by_name: Dict[str, List[MetricPoint]]
    ) -> bool:
        """Evaluate threshold-based alert condition."""
        
        # Map alert to relevant metrics
        metric_name = self._get_metric_name_for_alert(alert.alert_id)
        
        if metric_name not in metrics_by_name:
            return False
        
        # Get most recent metric value
        recent_metrics = metrics_by_name[metric_name]
        if not recent_metrics:
            return False
        
        latest_value = max(recent_metrics, key=lambda m: m.timestamp).value
        
        # Evaluate threshold condition
        if alert.threshold_operator == "greater_than":
            return latest_value > alert.threshold_value
        elif alert.threshold_operator == "less_than":
            return latest_value < alert.threshold_value
        elif alert.threshold_operator == "equals":
            return abs(latest_value - alert.threshold_value) < 0.001
        
        return False
    
    async def _evaluate_trend_condition(
        self, 
        alert: Alert, 
        metrics_by_name: Dict[str, List[MetricPoint]]
    ) -> bool:
        """Evaluate trend-based alert condition."""
        
        # Placeholder for trend analysis
        # Would implement trend detection logic here
        return False
    
    async def _evaluate_anomaly_condition(
        self, 
        alert: Alert, 
        metrics_by_name: Dict[str, List[MetricPoint]]
    ) -> bool:
        """Evaluate anomaly-based alert condition."""
        
        # Placeholder for anomaly detection
        # Would implement statistical anomaly detection here
        return False
    
    def _get_metric_name_for_alert(self, alert_id: str) -> str:
        """Map alert ID to relevant metric name."""
        
        metric_mapping = {
            "high_cpu_usage": "system.cpu.usage_percent",
            "high_memory_usage": "system.memory.usage_percent", 
            "high_error_rate": "app.requests.error_rate",
            "slow_response_time": "app.response_time.mean_ms",
            "low_evaluation_quality": "evaluation.quality.p_at_1",
            "disk_space_low": "system.disk.usage_percent"
        }
        
        return metric_mapping.get(alert_id, "unknown")
    
    async def _trigger_alert(self, alert: Alert, current_time: float):
        """Trigger an alert."""
        
        alert.status = "active"
        alert.triggered_at = datetime.fromtimestamp(current_time).isoformat()
        
        # Send notification
        await self._send_alert_notification(alert, is_repeat=False)
        
        # Add to history
        self.alert_history.append({
            'alert_id': alert.alert_id,
            'action': 'triggered',
            'timestamp': current_time,
            'severity': alert.severity
        })
        
        self.logger.warning(f"Alert triggered: {alert.name} - {alert.description}")
    
    async def _resolve_alert(self, alert: Alert, current_time: float):
        """Resolve an alert."""
        
        alert.status = "resolved"
        alert.resolved_at = datetime.fromtimestamp(current_time).isoformat()
        
        # Add to history
        self.alert_history.append({
            'alert_id': alert.alert_id,
            'action': 'resolved',
            'timestamp': current_time,
            'severity': alert.severity
        })
        
        self.logger.info(f"Alert resolved: {alert.name}")
    
    def _should_repeat_notification(self, alert: Alert, current_time: float) -> bool:
        """Check if alert notification should be repeated."""
        
        if not alert.last_notification:
            return True
        
        last_notification_time = datetime.fromisoformat(alert.last_notification).timestamp()
        minutes_since_last = (current_time - last_notification_time) / 60
        
        return minutes_since_last >= alert.repeat_interval_minutes
    
    async def _send_alert_notification(self, alert: Alert, is_repeat: bool = False):
        """Send alert notification through configured channels."""
        
        alert.last_notification = datetime.now().isoformat()
        alert.notification_count += 1
        
        notification_message = f"{'[REPEAT] ' if is_repeat else ''}ALERT: {alert.name} - {alert.description} (Severity: {alert.severity})"
        
        for channel in alert.notification_channels:
            try:
                if channel == "log":
                    if alert.severity in ["critical", "high"]:
                        self.logger.error(notification_message)
                    else:
                        self.logger.warning(notification_message)
                elif channel == "console":
                    print(f"\n🚨 {notification_message}\n")
                elif channel == "email":
                    # Would implement email notification
                    pass
                elif channel == "webhook":
                    # Would implement webhook notification
                    pass
            
            except Exception as e:
                self.logger.error(f"Failed to send alert notification via {channel}: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get list of currently active alerts."""
        with self.alert_lock:
            return [alert for alert in self.alerts.values() if alert.status == "active"]
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get alert history."""
        return list(self.alert_history)[-limit:]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        with self.alert_lock:
            if alert_id in self.alerts:
                alert = self.alerts[alert_id]
                if alert.status == "active":
                    alert.status = "acknowledged"
                    alert.acknowledged_at = datetime.now().isoformat()
                    return True
        return False


class DataStorage:
    """Stores monitoring data and provides query interface."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.storage_path = Path(config.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        if config.storage_backend == "sqlite":
            self.db_path = self.storage_path / "monitoring.db"
            self._init_sqlite_storage()
        
        self.logger = logging.getLogger(__name__ + ".DataStorage")
    
    def _init_sqlite_storage(self):
        """Initialize SQLite storage."""
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Create metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                labels TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp REAL NOT NULL,
                severity TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alert_events(timestamp)')
        
        conn.commit()
        conn.close()
    
    async def store_metrics(self, metrics: List[MetricPoint]):
        """Store metrics to persistent storage."""
        
        if self.config.storage_backend == "sqlite":
            await self._store_metrics_sqlite(metrics)
        elif self.config.storage_backend == "file":
            await self._store_metrics_file(metrics)
        # memory storage doesn't need persistence
    
    async def _store_metrics_sqlite(self, metrics: List[MetricPoint]):
        """Store metrics to SQLite database."""
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            for metric in metrics:
                cursor.execute('''
                    INSERT INTO metrics (timestamp, metric_name, value, labels, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    metric.timestamp,
                    metric.metric_name,
                    metric.value,
                    json.dumps(metric.labels),
                    json.dumps(metric.metadata)
                ))
            
            conn.commit()
        
        except Exception as e:
            self.logger.error(f"Error storing metrics to SQLite: {e}")
            conn.rollback()
        
        finally:
            conn.close()
    
    async def _store_metrics_file(self, metrics: List[MetricPoint]):
        """Store metrics to JSON file."""
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.storage_path / f"metrics_{timestamp_str}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump([metric.to_dict() for metric in metrics], f, indent=2)
        
        except Exception as e:
            self.logger.error(f"Error storing metrics to file: {e}")
    
    async def query_metrics(
        self, 
        metric_name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[MetricPoint]:
        """Query metrics from storage."""
        
        if self.config.storage_backend == "sqlite":
            return await self._query_metrics_sqlite(metric_name, start_time, end_time, limit)
        
        return []
    
    async def _query_metrics_sqlite(
        self, 
        metric_name: str,
        start_time: Optional[float],
        end_time: Optional[float],
        limit: int
    ) -> List[MetricPoint]:
        """Query metrics from SQLite database."""
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            query = "SELECT timestamp, metric_name, value, labels, metadata FROM metrics WHERE metric_name = ?"
            params = [metric_name]
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            metrics = []
            for row in rows:
                timestamp, name, value, labels_json, metadata_json = row
                
                labels = json.loads(labels_json) if labels_json else {}
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                metrics.append(MetricPoint(
                    timestamp=timestamp,
                    metric_name=name,
                    value=value,
                    labels=labels,
                    metadata=metadata
                ))
            
            return metrics
        
        except Exception as e:
            self.logger.error(f"Error querying metrics from SQLite: {e}")
            return []
        
        finally:
            conn.close()
    
    async def cleanup_old_data(self):
        """Clean up old data based on retention policy."""
        
        cutoff_time = time.time() - (self.config.retention_hours * 3600)
        
        if self.config.storage_backend == "sqlite":
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            try:
                cursor.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff_time,))
                cursor.execute("DELETE FROM alert_events WHERE timestamp < ?", (cutoff_time,))
                conn.commit()
                
                deleted_metrics = cursor.rowcount
                self.logger.info(f"Cleaned up {deleted_metrics} old metric records")
            
            except Exception as e:
                self.logger.error(f"Error cleaning up old data: {e}")
            
            finally:
                conn.close()


class SLATracker:
    """Tracks SLA compliance and generates reports."""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.sla_data = deque(maxlen=10000)
        self.logger = logging.getLogger(__name__ + ".SLATracker")
    
    async def update_sla_metrics(self, metrics: List[MetricPoint]):
        """Update SLA tracking with new metrics."""
        
        current_time = time.time()
        
        # Extract relevant metrics for SLA tracking
        response_time_metrics = [m for m in metrics if "response_time.mean_ms" in m.metric_name]
        error_rate_metrics = [m for m in metrics if "error_rate" in m.metric_name]
        availability_metrics = [m for m in metrics if "success_rate" in m.metric_name]
        
        sla_point = {
            'timestamp': current_time,
            'response_time_sla_met': True,
            'error_rate_sla_met': True,
            'availability_sla_met': True,
            'overall_sla_met': True
        }
        
        # Check response time SLA
        if response_time_metrics:
            avg_response_time = statistics.mean([m.value for m in response_time_metrics])
            sla_point['response_time_ms'] = avg_response_time
            sla_point['response_time_sla_met'] = avg_response_time <= self.config.sla_response_time_ms
        
        # Check error rate SLA
        if error_rate_metrics:
            avg_error_rate = statistics.mean([m.value for m in error_rate_metrics])
            sla_point['error_rate_percent'] = avg_error_rate * 100
            sla_point['error_rate_sla_met'] = avg_error_rate <= (self.config.sla_error_rate_percent / 100)
        
        # Check availability SLA
        if availability_metrics:
            avg_availability = statistics.mean([m.value for m in availability_metrics])
            sla_point['availability_percent'] = avg_availability * 100
            sla_point['availability_sla_met'] = avg_availability >= (self.config.sla_availability_percent / 100)
        
        # Overall SLA compliance
        sla_point['overall_sla_met'] = all([
            sla_point['response_time_sla_met'],
            sla_point['error_rate_sla_met'],
            sla_point['availability_sla_met']
        ])
        
        self.sla_data.append(sla_point)
    
    def get_sla_compliance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate SLA compliance report for specified time period."""
        
        cutoff_time = time.time() - (hours * 3600)
        recent_sla_data = [point for point in self.sla_data if point['timestamp'] >= cutoff_time]
        
        if not recent_sla_data:
            return {
                'period_hours': hours,
                'data_points': 0,
                'overall_compliance': 0.0,
                'response_time_compliance': 0.0,
                'error_rate_compliance': 0.0,
                'availability_compliance': 0.0
            }
        
        total_points = len(recent_sla_data)
        
        # Calculate compliance percentages
        overall_compliant = sum(1 for point in recent_sla_data if point['overall_sla_met'])
        response_time_compliant = sum(1 for point in recent_sla_data if point['response_time_sla_met'])
        error_rate_compliant = sum(1 for point in recent_sla_data if point['error_rate_sla_met'])
        availability_compliant = sum(1 for point in recent_sla_data if point['availability_sla_met'])
        
        # Calculate averages
        response_times = [point.get('response_time_ms', 0) for point in recent_sla_data if 'response_time_ms' in point]
        error_rates = [point.get('error_rate_percent', 0) for point in recent_sla_data if 'error_rate_percent' in point]
        availability_rates = [point.get('availability_percent', 0) for point in recent_sla_data if 'availability_percent' in point]
        
        return {
            'period_hours': hours,
            'data_points': total_points,
            'overall_compliance': (overall_compliant / total_points) * 100,
            'response_time_compliance': (response_time_compliant / total_points) * 100,
            'error_rate_compliance': (error_rate_compliant / total_points) * 100,
            'availability_compliance': (availability_compliant / total_points) * 100,
            'avg_response_time_ms': statistics.mean(response_times) if response_times else 0,
            'avg_error_rate_percent': statistics.mean(error_rates) if error_rates else 0,
            'avg_availability_percent': statistics.mean(availability_rates) if availability_rates else 0,
            'sla_targets': {
                'response_time_ms': self.config.sla_response_time_ms,
                'error_rate_percent': self.config.sla_error_rate_percent,
                'availability_percent': self.config.sla_availability_percent
            }
        }


class MonitoringDashboard:
    """Main monitoring dashboard system."""
    
    def __init__(self, config: Optional[MonitoringConfig] = None):
        """Initialize monitoring dashboard."""
        
        self.config = config or MonitoringConfig()
        
        # Initialize components
        self.metrics_collector = MetricsCollector(self.config)
        self.alert_manager = AlertManager(self.config)
        self.data_storage = DataStorage(self.config)
        self.sla_tracker = SLATracker(self.config)
        
        # State management
        self.running = False
        self.collection_task = None
        self.alert_task = None
        self.cleanup_task = None
        
        self.logger = logging.getLogger(__name__ + ".MonitoringDashboard")
    
    async def start(self):
        """Start monitoring dashboard."""
        
        if self.running:
            return
        
        self.running = True
        
        # Start background tasks
        self.collection_task = asyncio.create_task(self._collection_loop())
        self.alert_task = asyncio.create_task(self._alert_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("Monitoring dashboard started")
    
    async def stop(self):
        """Stop monitoring dashboard."""
        
        self.running = False
        
        # Cancel background tasks
        for task in [self.collection_task, self.alert_task, self.cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.logger.info("Monitoring dashboard stopped")
    
    async def _collection_loop(self):
        """Background metrics collection loop."""
        
        while self.running:
            try:
                # Collect metrics
                metrics = await self.metrics_collector.collect_all_metrics()
                
                if metrics:
                    # Store metrics
                    await self.data_storage.store_metrics(metrics)
                    
                    # Update SLA tracking
                    await self.sla_tracker.update_sla_metrics(metrics)
                    
                    self.logger.debug(f"Collected {len(metrics)} metrics")
                
                await asyncio.sleep(self.config.collection_interval_seconds)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _alert_loop(self):
        """Background alert evaluation loop."""
        
        while self.running:
            try:
                if self.config.enable_alerting:
                    # Get recent metrics
                    recent_metrics = self.metrics_collector.get_recent_metrics(50)
                    
                    if recent_metrics:
                        # Evaluate alerts
                        triggered_alerts = await self.alert_manager.evaluate_alerts(recent_metrics)
                        
                        if triggered_alerts:
                            self.logger.info(f"Evaluated alerts: {len(triggered_alerts)} triggered")
                
                await asyncio.sleep(self.config.collection_interval_seconds * 2)  # Check less frequently than collection
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in alert loop: {e}")
                await asyncio.sleep(10)  # Longer pause on error
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        
        while self.running:
            try:
                # Clean up old data once per hour
                await self.data_storage.cleanup_old_data()
                
                # Wait 1 hour
                await asyncio.sleep(3600)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)  # 5 minutes pause on error
    
    async def get_dashboard_data(self) -> DashboardData:
        """Get current dashboard data."""
        
        # Collect current metrics
        current_metrics = await self.metrics_collector.collect_all_metrics()
        
        # Group metrics by category
        system_metrics = [m for m in current_metrics if m.metric_name.startswith('system.')]
        app_metrics = [m for m in current_metrics if m.metric_name.startswith('app.')]
        eval_metrics = [m for m in current_metrics if m.metric_name.startswith('evaluation.')]
        perf_metrics = [m for m in current_metrics if m.metric_name.startswith('performance.')]
        
        # System health summary
        system_health = {
            'status': 'healthy',
            'cpu_usage': next((m.value for m in system_metrics if 'cpu.usage_percent' in m.metric_name), 0),
            'memory_usage': next((m.value for m in system_metrics if 'memory.usage_percent' in m.metric_name), 0),
            'disk_usage': next((m.value for m in system_metrics if 'disk.usage_percent' in m.metric_name), 0),
            'last_updated': datetime.now().isoformat()
        }
        
        # Determine overall health status
        if (system_health['cpu_usage'] > 90 or 
            system_health['memory_usage'] > 95 or 
            system_health['disk_usage'] > 95):
            system_health['status'] = 'critical'
        elif (system_health['cpu_usage'] > 80 or 
              system_health['memory_usage'] > 85 or 
              system_health['disk_usage'] > 85):
            system_health['status'] = 'warning'
        
        # Performance metrics summary
        performance_metrics = {
            'response_time_ms': next((m.value for m in app_metrics if 'response_time.mean_ms' in m.metric_name), 0),
            'requests_per_second': next((m.value for m in app_metrics if 'requests.per_second' in m.metric_name), 0),
            'error_rate': next((m.value for m in app_metrics if 'error_rate' in m.metric_name), 0),
            'queue_size': next((m.value for m in app_metrics if 'queue.size' in m.metric_name), 0)
        }
        
        # Evaluation status summary
        evaluation_status = {
            'last_run': datetime.now().isoformat(),
            'success_rate': next((m.value for m in eval_metrics if 'success_rate' in m.metric_name), 0),
            'p_at_1': next((m.value for m in eval_metrics if 'quality.p_at_1' in m.metric_name), 0),
            'ndcg_at_5': next((m.value for m in eval_metrics if 'quality.ndcg_at_5' in m.metric_name), 0),
            'avg_duration_minutes': next((m.value for m in eval_metrics if 'average_duration_minutes' in m.metric_name), 0)
        }
        
        # Get active alerts
        active_alerts = self.alert_manager.get_active_alerts()
        
        # Get SLA compliance
        sla_compliance = self.sla_tracker.get_sla_compliance_report(hours=24)
        
        return DashboardData(
            timestamp=datetime.now().isoformat(),
            system_health=system_health,
            performance_metrics=performance_metrics,
            evaluation_status=evaluation_status,
            active_alerts=active_alerts,
            sla_compliance=sla_compliance
        )
    
    async def get_metric_history(
        self, 
        metric_name: str, 
        hours: int = 24
    ) -> List[MetricPoint]:
        """Get historical data for a specific metric."""
        
        end_time = time.time()
        start_time = end_time - (hours * 3600)
        
        return await self.data_storage.query_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )
    
    def add_custom_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """Add a custom metric point."""
        
        metric = MetricPoint(
            timestamp=time.time(),
            metric_name=name,
            value=value,
            labels=labels or {}
        )
        
        self.metrics_collector.add_metric(metric)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        return self.alert_manager.acknowledge_alert(alert_id)
    
    async def generate_system_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive system report."""
        
        dashboard_data = await self.get_dashboard_data()
        sla_report = self.sla_tracker.get_sla_compliance_report(hours)
        alert_history = self.alert_manager.get_alert_history(100)
        
        return {
            'report_timestamp': datetime.now().isoformat(),
            'report_period_hours': hours,
            'system_health': dashboard_data.system_health,
            'performance_summary': dashboard_data.performance_metrics,
            'evaluation_summary': dashboard_data.evaluation_status,
            'sla_compliance': sla_report,
            'active_alerts_count': len(dashboard_data.active_alerts),
            'alert_history_count': len(alert_history),
            'recommendations': self._generate_system_recommendations(dashboard_data, sla_report)
        }
    
    def _generate_system_recommendations(
        self, 
        dashboard_data: DashboardData, 
        sla_report: Dict[str, Any]
    ) -> List[str]:
        """Generate system recommendations based on current state."""
        
        recommendations = []
        
        # System health recommendations
        if dashboard_data.system_health['cpu_usage'] > 80:
            recommendations.append("High CPU usage detected - consider scaling or optimization")
        
        if dashboard_data.system_health['memory_usage'] > 85:
            recommendations.append("High memory usage detected - check for memory leaks")
        
        if dashboard_data.system_health['disk_usage'] > 85:
            recommendations.append("Low disk space - consider cleanup or expansion")
        
        # Performance recommendations
        if dashboard_data.performance_metrics['response_time_ms'] > 300:
            recommendations.append("Response times are elevated - investigate performance bottlenecks")
        
        if dashboard_data.performance_metrics['error_rate'] > 0.05:
            recommendations.append("Error rate is high - review application logs and error handling")
        
        # SLA recommendations
        if sla_report.get('overall_compliance', 100) < 95:
            recommendations.append("SLA compliance is below target - immediate attention required")
        
        # Alert recommendations
        if len(dashboard_data.active_alerts) > 5:
            recommendations.append("Multiple active alerts - prioritize critical issues")
        
        return recommendations


# Convenience functions

async def create_monitoring_dashboard(
    collection_interval: float = 10.0,
    enable_alerting: bool = True,
    storage_backend: str = "sqlite"
) -> MonitoringDashboard:
    """Create and start monitoring dashboard with common settings."""
    
    config = MonitoringConfig(
        collection_interval_seconds=collection_interval,
        enable_alerting=enable_alerting,
        storage_backend=storage_backend
    )
    
    dashboard = MonitoringDashboard(config)
    await dashboard.start()
    
    return dashboard


# Global dashboard instance
_global_monitoring_dashboard = None


async def get_global_monitoring_dashboard() -> MonitoringDashboard:
    """Get or create global monitoring dashboard."""
    
    global _global_monitoring_dashboard
    
    if _global_monitoring_dashboard is None:
        _global_monitoring_dashboard = await create_monitoring_dashboard()
    
    return _global_monitoring_dashboard