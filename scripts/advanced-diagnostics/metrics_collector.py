#!/usr/bin/env python3
"""
Performance Metrics Collector for Veris Memory Services

This module provides comprehensive performance metrics collection and analysis,
including system resource monitoring, service performance tracking, and
trend analysis for Veris Memory infrastructure.

Author: Claude Code Integration - Phase 2
Date: 2025-08-20
"""

import asyncio
import json
import logging
import os
import sys
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import aiohttp
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SystemMetrics:
    """Container for system-level metrics."""
    
    def __init__(self):
        self.cpu_percent: float = 0.0
        self.memory_percent: float = 0.0
        self.memory_available_gb: float = 0.0
        self.memory_total_gb: float = 0.0
        self.disk_usage_percent: float = 0.0
        self.disk_free_gb: float = 0.0
        self.disk_total_gb: float = 0.0
        self.network_connections: int = 0
        self.load_average: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.boot_time: datetime = datetime.now()
        self.uptime_hours: float = 0.0


class ServiceMetrics:
    """Container for service-specific metrics."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.response_times: List[float] = []
        self.status_codes: List[int] = []
        self.error_count: int = 0
        self.success_count: int = 0
        self.total_requests: int = 0
        self.availability_percent: float = 0.0
        self.avg_response_time: float = 0.0
        self.min_response_time: float = 0.0
        self.max_response_time: float = 0.0
        self.p95_response_time: float = 0.0
        self.p99_response_time: float = 0.0
        self.throughput_rps: float = 0.0
        self.error_rate_percent: float = 0.0


class MetricsCollector:
    """
    Comprehensive performance metrics collector for Veris Memory services.
    
    Provides capabilities for:
    - System resource monitoring (CPU, memory, disk, network)
    - Service performance metrics (response times, throughput, errors)
    - Historical trend analysis
    - Performance baseline establishment
    - Anomaly detection
    """
    
    def __init__(self):
        """Initialize the metrics collector."""
        self.service_config = {
            "mcp_server": {
                "port": 8000,
                "health_endpoint": "/",
                "metrics_endpoint": "/metrics"
            },
            "rest_api": {
                "port": 8001,
                "health_endpoint": "/api/v1/health",
                "metrics_endpoint": "/api/v1/metrics"
            },
            "sentinel": {
                "port": 9090,
                "health_endpoint": "/status",
                "metrics_endpoint": "/metrics"
            },
            "dashboard": {
                "port": 8080,
                "health_endpoint": "/health",
                "metrics_endpoint": "/metrics"
            }
        }
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def collect_comprehensive_metrics(
        self,
        services: List[str] = None,
        time_range: str = "5m",
        sample_count: int = 10
    ) -> Dict[str, Any]:
        """
        Collect comprehensive performance metrics for all services and system.
        
        Args:
            services: List of services to monitor (None = all)
            time_range: Time range for metrics collection
            sample_count: Number of samples to collect for each service
            
        Returns:
            Dict containing comprehensive metrics analysis
        """
        if services is None:
            services = list(self.service_config.keys())
        
        logger.info(f"Collecting comprehensive metrics for {len(services)} services")
        
        # Collect system metrics
        system_metrics = await self._collect_system_metrics()
        
        # Collect service metrics
        service_metrics = {}
        for service in services:
            logger.info(f"Collecting metrics for service: {service}")
            service_metrics[service] = await self._collect_service_metrics(service, sample_count)
        
        # Analyze performance trends
        trend_analysis = await self._analyze_performance_trends(service_metrics)
        
        # Detect anomalies
        anomaly_analysis = await self._detect_anomalies(system_metrics, service_metrics)
        
        # Generate performance recommendations
        recommendations = await self._generate_performance_recommendations(
            system_metrics, service_metrics, anomaly_analysis
        )
        
        return {
            "collection_timestamp": datetime.now().isoformat(),
            "time_range": time_range,
            "sample_count": sample_count,
            "services_analyzed": services,
            "system_metrics": system_metrics,
            "service_metrics": service_metrics,
            "trend_analysis": trend_analysis,
            "anomaly_analysis": anomaly_analysis,
            "performance_summary": self._generate_performance_summary(system_metrics, service_metrics),
            "recommendations": recommendations
        }
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-level performance metrics."""
        metrics = SystemMetrics()
        
        try:
            # CPU metrics
            metrics.cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.memory_percent = memory.percent
            metrics.memory_available_gb = memory.available / (1024**3)
            metrics.memory_total_gb = memory.total / (1024**3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics.disk_usage_percent = (disk.used / disk.total) * 100
            metrics.disk_free_gb = disk.free / (1024**3)
            metrics.disk_total_gb = disk.total / (1024**3)
            
            # Network metrics
            connections = psutil.net_connections()
            metrics.network_connections = len(connections)
            
            # Load average (Unix systems)
            try:
                metrics.load_average = os.getloadavg()
            except (OSError, AttributeError):
                metrics.load_average = (0.0, 0.0, 0.0)
            
            # System uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            metrics.boot_time = boot_time
            metrics.uptime_hours = (datetime.now() - boot_time).total_seconds() / 3600
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        return {
            "cpu_percent": metrics.cpu_percent,
            "memory": {
                "percent_used": metrics.memory_percent,
                "available_gb": round(metrics.memory_available_gb, 2),
                "total_gb": round(metrics.memory_total_gb, 2),
                "used_gb": round(metrics.memory_total_gb - metrics.memory_available_gb, 2)
            },
            "disk": {
                "percent_used": round(metrics.disk_usage_percent, 2),
                "free_gb": round(metrics.disk_free_gb, 2),
                "total_gb": round(metrics.disk_total_gb, 2),
                "used_gb": round(metrics.disk_total_gb - metrics.disk_free_gb, 2)
            },
            "network": {
                "active_connections": metrics.network_connections
            },
            "load_average": {
                "1_min": metrics.load_average[0],
                "5_min": metrics.load_average[1],
                "15_min": metrics.load_average[2]
            },
            "uptime": {
                "boot_time": metrics.boot_time.isoformat(),
                "uptime_hours": round(metrics.uptime_hours, 2)
            },
            "collection_timestamp": datetime.now().isoformat()
        }
    
    async def _collect_service_metrics(self, service_name: str, sample_count: int) -> Dict[str, Any]:
        """Collect detailed performance metrics for a specific service."""
        if service_name not in self.service_config:
            return {"error": f"Unknown service: {service_name}"}
        
        config = self.service_config[service_name]
        metrics = ServiceMetrics(service_name)
        
        # Collect multiple samples for statistical analysis
        start_time = time.time()
        
        for i in range(sample_count):
            try:
                sample_start = time.time()
                
                url = f"http://localhost:{config['port']}{config['health_endpoint']}"
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    sample_end = time.time()
                    response_time = (sample_end - sample_start) * 1000  # Convert to ms
                    
                    metrics.response_times.append(response_time)
                    metrics.status_codes.append(response.status)
                    metrics.total_requests += 1
                    
                    if 200 <= response.status < 300:
                        metrics.success_count += 1
                    else:
                        metrics.error_count += 1
                        
            except Exception as e:
                logger.debug(f"Sample {i+1} failed for {service_name}: {e}")
                metrics.response_times.append(10000)  # 10s timeout
                metrics.status_codes.append(0)
                metrics.error_count += 1
                metrics.total_requests += 1
            
            # Small delay between samples
            if i < sample_count - 1:
                await asyncio.sleep(0.5)
        
        total_time = time.time() - start_time
        
        # Calculate derived metrics
        if metrics.response_times:
            metrics.avg_response_time = sum(metrics.response_times) / len(metrics.response_times)
            metrics.min_response_time = min(metrics.response_times)
            metrics.max_response_time = max(metrics.response_times)
            
            # Calculate percentiles
            sorted_times = sorted(metrics.response_times)
            metrics.p95_response_time = sorted_times[int(0.95 * len(sorted_times))]
            metrics.p99_response_time = sorted_times[int(0.99 * len(sorted_times))]
        
        if metrics.total_requests > 0:
            metrics.availability_percent = (metrics.success_count / metrics.total_requests) * 100
            metrics.error_rate_percent = (metrics.error_count / metrics.total_requests) * 100
            metrics.throughput_rps = metrics.total_requests / max(total_time, 1)
        
        return {
            "service_name": service_name,
            "sample_count": sample_count,
            "total_requests": metrics.total_requests,
            "success_count": metrics.success_count,
            "error_count": metrics.error_count,
            "response_times": {
                "avg_ms": round(metrics.avg_response_time, 2),
                "min_ms": round(metrics.min_response_time, 2),
                "max_ms": round(metrics.max_response_time, 2),
                "p95_ms": round(metrics.p95_response_time, 2),
                "p99_ms": round(metrics.p99_response_time, 2),
                "all_samples": [round(rt, 2) for rt in metrics.response_times]
            },
            "availability_percent": round(metrics.availability_percent, 2),
            "error_rate_percent": round(metrics.error_rate_percent, 2),
            "throughput_rps": round(metrics.throughput_rps, 2),
            "status_codes": metrics.status_codes,
            "performance_category": self._categorize_service_performance(metrics),
            "collection_duration_seconds": round(total_time, 2)
        }
    
    def _categorize_service_performance(self, metrics: ServiceMetrics) -> str:
        """Categorize service performance based on metrics."""
        if metrics.availability_percent < 50:
            return "critical"
        elif metrics.avg_response_time > 5000:
            return "critical"
        elif metrics.availability_percent < 90:
            return "poor"
        elif metrics.avg_response_time > 2000:
            return "poor"
        elif metrics.availability_percent < 99:
            return "fair"
        elif metrics.avg_response_time > 500:
            return "fair"
        elif metrics.avg_response_time > 100:
            return "good"
        else:
            return "excellent"
    
    async def _analyze_performance_trends(self, service_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance trends across services."""
        trends = {
            "overall_health": "unknown",
            "services_by_performance": {
                "excellent": [],
                "good": [],
                "fair": [],
                "poor": [],
                "critical": []
            },
            "average_response_time": 0.0,
            "average_availability": 0.0,
            "total_error_rate": 0.0,
            "performance_distribution": {}
        }
        
        if not service_metrics:
            return trends
        
        total_response_time = 0
        total_availability = 0
        total_errors = 0
        total_requests = 0
        
        for service_name, metrics in service_metrics.items():
            if "error" in metrics:
                continue
                
            # Categorize service performance
            category = metrics.get("performance_category", "unknown")
            trends["services_by_performance"][category].append(service_name)
            
            # Aggregate metrics
            total_response_time += metrics.get("response_times", {}).get("avg_ms", 0)
            total_availability += metrics.get("availability_percent", 0)
            total_errors += metrics.get("error_count", 0)
            total_requests += metrics.get("total_requests", 0)
        
        service_count = len([m for m in service_metrics.values() if "error" not in m])
        
        if service_count > 0:
            trends["average_response_time"] = round(total_response_time / service_count, 2)
            trends["average_availability"] = round(total_availability / service_count, 2)
        
        if total_requests > 0:
            trends["total_error_rate"] = round((total_errors / total_requests) * 100, 2)
        
        # Determine overall health
        critical_services = len(trends["services_by_performance"]["critical"])
        poor_services = len(trends["services_by_performance"]["poor"])
        
        if critical_services > 0:
            trends["overall_health"] = "critical"
        elif poor_services > 0:
            trends["overall_health"] = "degraded"
        elif trends["average_availability"] > 99:
            trends["overall_health"] = "excellent"
        elif trends["average_availability"] > 95:
            trends["overall_health"] = "good"
        else:
            trends["overall_health"] = "fair"
        
        # Performance distribution
        for category, services in trends["services_by_performance"].items():
            if services:
                trends["performance_distribution"][category] = len(services)
        
        return trends
    
    async def _detect_anomalies(self, system_metrics: Dict[str, Any], service_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Detect performance anomalies in system and service metrics."""
        anomalies = {
            "system_anomalies": [],
            "service_anomalies": {},
            "anomaly_count": 0,
            "severity_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0}
        }
        
        # System-level anomaly detection
        cpu_percent = system_metrics.get("cpu_percent", 0)
        memory_percent = system_metrics.get("memory", {}).get("percent_used", 0)
        disk_percent = system_metrics.get("disk", {}).get("percent_used", 0)
        
        if cpu_percent > 90:
            anomalies["system_anomalies"].append({
                "type": "high_cpu",
                "severity": "critical",
                "value": cpu_percent,
                "threshold": 90,
                "description": f"CPU usage critically high: {cpu_percent}%"
            })
        elif cpu_percent > 80:
            anomalies["system_anomalies"].append({
                "type": "high_cpu",
                "severity": "high",
                "value": cpu_percent,
                "threshold": 80,
                "description": f"CPU usage high: {cpu_percent}%"
            })
        
        if memory_percent > 95:
            anomalies["system_anomalies"].append({
                "type": "high_memory",
                "severity": "critical",
                "value": memory_percent,
                "threshold": 95,
                "description": f"Memory usage critically high: {memory_percent}%"
            })
        elif memory_percent > 85:
            anomalies["system_anomalies"].append({
                "type": "high_memory",
                "severity": "high",
                "value": memory_percent,
                "threshold": 85,
                "description": f"Memory usage high: {memory_percent}%"
            })
        
        if disk_percent > 95:
            anomalies["system_anomalies"].append({
                "type": "high_disk",
                "severity": "critical",
                "value": disk_percent,
                "threshold": 95,
                "description": f"Disk usage critically high: {disk_percent}%"
            })
        elif disk_percent > 85:
            anomalies["system_anomalies"].append({
                "type": "high_disk",
                "severity": "high",
                "value": disk_percent,
                "threshold": 85,
                "description": f"Disk usage high: {disk_percent}%"
            })
        
        # Service-level anomaly detection
        for service_name, metrics in service_metrics.items():
            if "error" in metrics:
                continue
                
            service_anomalies = []
            
            avg_response_time = metrics.get("response_times", {}).get("avg_ms", 0)
            availability = metrics.get("availability_percent", 100)
            error_rate = metrics.get("error_rate_percent", 0)
            
            # Response time anomalies
            if avg_response_time > 5000:
                service_anomalies.append({
                    "type": "high_latency",
                    "severity": "critical",
                    "value": avg_response_time,
                    "threshold": 5000,
                    "description": f"Response time critically high: {avg_response_time}ms"
                })
            elif avg_response_time > 2000:
                service_anomalies.append({
                    "type": "high_latency",
                    "severity": "high",
                    "value": avg_response_time,
                    "threshold": 2000,
                    "description": f"Response time high: {avg_response_time}ms"
                })
            
            # Availability anomalies
            if availability < 50:
                service_anomalies.append({
                    "type": "low_availability",
                    "severity": "critical",
                    "value": availability,
                    "threshold": 50,
                    "description": f"Availability critically low: {availability}%"
                })
            elif availability < 90:
                service_anomalies.append({
                    "type": "low_availability",
                    "severity": "high",
                    "value": availability,
                    "threshold": 90,
                    "description": f"Availability low: {availability}%"
                })
            elif availability < 99:
                service_anomalies.append({
                    "type": "low_availability",
                    "severity": "medium",
                    "value": availability,
                    "threshold": 99,
                    "description": f"Availability below target: {availability}%"
                })
            
            # Error rate anomalies
            if error_rate > 50:
                service_anomalies.append({
                    "type": "high_error_rate",
                    "severity": "critical",
                    "value": error_rate,
                    "threshold": 50,
                    "description": f"Error rate critically high: {error_rate}%"
                })
            elif error_rate > 10:
                service_anomalies.append({
                    "type": "high_error_rate",
                    "severity": "high",
                    "value": error_rate,
                    "threshold": 10,
                    "description": f"Error rate high: {error_rate}%"
                })
            elif error_rate > 1:
                service_anomalies.append({
                    "type": "high_error_rate",
                    "severity": "medium",
                    "value": error_rate,
                    "threshold": 1,
                    "description": f"Error rate elevated: {error_rate}%"
                })
            
            if service_anomalies:
                anomalies["service_anomalies"][service_name] = service_anomalies
        
        # Count anomalies by severity
        all_anomalies = anomalies["system_anomalies"]
        for service_anomalies in anomalies["service_anomalies"].values():
            all_anomalies.extend(service_anomalies)
        
        for anomaly in all_anomalies:
            severity = anomaly["severity"]
            anomalies["severity_breakdown"][severity] += 1
        
        anomalies["anomaly_count"] = len(all_anomalies)
        
        return anomalies
    
    async def _generate_performance_recommendations(
        self,
        system_metrics: Dict[str, Any],
        service_metrics: Dict[str, Any],
        anomaly_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate performance recommendations based on metrics analysis."""
        recommendations = []
        
        # System-level recommendations
        system_anomalies = anomaly_analysis.get("system_anomalies", [])
        for anomaly in system_anomalies:
            if anomaly["type"] == "high_cpu":
                recommendations.append(f"🔥 High CPU usage detected ({anomaly['value']}%) - investigate CPU-intensive processes")
                recommendations.append("🔧 Consider scaling up CPU resources or optimizing application performance")
            elif anomaly["type"] == "high_memory":
                recommendations.append(f"💾 High memory usage detected ({anomaly['value']}%) - check for memory leaks")
                recommendations.append("🔧 Consider increasing memory allocation or optimizing memory usage")
            elif anomaly["type"] == "high_disk":
                recommendations.append(f"💽 High disk usage detected ({anomaly['value']}%) - clean up disk space")
                recommendations.append("🔧 Consider log rotation, cleanup scripts, or disk expansion")
        
        # Service-level recommendations
        service_anomalies = anomaly_analysis.get("service_anomalies", {})
        for service_name, anomalies in service_anomalies.items():
            for anomaly in anomalies:
                if anomaly["type"] == "high_latency":
                    recommendations.append(f"⏱️ High response time in {service_name} ({anomaly['value']}ms) - investigate performance bottlenecks")
                    recommendations.append(f"🔧 Review {service_name} logs and database query performance")
                elif anomaly["type"] == "low_availability":
                    recommendations.append(f"📉 Low availability in {service_name} ({anomaly['value']}%) - investigate service reliability")
                    recommendations.append(f"🔧 Check {service_name} error logs and dependency health")
                elif anomaly["type"] == "high_error_rate":
                    recommendations.append(f"🚨 High error rate in {service_name} ({anomaly['value']}%) - investigate error causes")
                    recommendations.append(f"🔧 Review {service_name} error logs and fix underlying issues")
        
        # General recommendations based on overall performance
        if not recommendations:
            recommendations.append("✅ No critical performance issues detected")
            recommendations.append("📊 Continue monitoring for performance trends")
        else:
            recommendations.append("🔍 Consider implementing performance monitoring alerts")
            recommendations.append("📈 Review performance trends over time for capacity planning")
        
        return recommendations
    
    def _generate_performance_summary(
        self,
        system_metrics: Dict[str, Any],
        service_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a high-level performance summary."""
        summary = {
            "overall_status": "unknown",
            "total_services": len(service_metrics),
            "healthy_services": 0,
            "degraded_services": 0,
            "critical_services": 0,
            "system_health": "unknown",
            "key_metrics": {}
        }
        
        # Analyze system health
        cpu_percent = system_metrics.get("cpu_percent", 0)
        memory_percent = system_metrics.get("memory", {}).get("percent_used", 0)
        disk_percent = system_metrics.get("disk", {}).get("percent_used", 0)
        
        if cpu_percent > 90 or memory_percent > 95 or disk_percent > 95:
            summary["system_health"] = "critical"
        elif cpu_percent > 80 or memory_percent > 85 or disk_percent > 85:
            summary["system_health"] = "degraded"
        else:
            summary["system_health"] = "healthy"
        
        # Analyze service health
        for service_name, metrics in service_metrics.items():
            if "error" in metrics:
                summary["critical_services"] += 1
                continue
                
            category = metrics.get("performance_category", "unknown")
            if category in ["excellent", "good"]:
                summary["healthy_services"] += 1
            elif category in ["fair"]:
                summary["degraded_services"] += 1
            else:
                summary["critical_services"] += 1
        
        # Determine overall status
        if summary["critical_services"] > 0 or summary["system_health"] == "critical":
            summary["overall_status"] = "critical"
        elif summary["degraded_services"] > 0 or summary["system_health"] == "degraded":
            summary["overall_status"] = "degraded"
        else:
            summary["overall_status"] = "healthy"
        
        # Key metrics summary
        if service_metrics:
            avg_response_times = [
                metrics.get("response_times", {}).get("avg_ms", 0)
                for metrics in service_metrics.values()
                if "error" not in metrics
            ]
            avg_availability = [
                metrics.get("availability_percent", 0)
                for metrics in service_metrics.values()
                if "error" not in metrics
            ]
            
            if avg_response_times:
                summary["key_metrics"]["avg_response_time_ms"] = round(sum(avg_response_times) / len(avg_response_times), 2)
            if avg_availability:
                summary["key_metrics"]["avg_availability_percent"] = round(sum(avg_availability) / len(avg_availability), 2)
        
        summary["key_metrics"]["system_cpu_percent"] = cpu_percent
        summary["key_metrics"]["system_memory_percent"] = memory_percent
        summary["key_metrics"]["system_disk_percent"] = disk_percent
        
        return summary


async def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Performance Metrics Collector for Veris Memory")
    parser.add_argument("--services", help="Comma-separated list of services to analyze")
    parser.add_argument("--time-range", default="5m", help="Time range for metrics collection")
    parser.add_argument("--samples", type=int, default=10, help="Number of samples per service")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "summary"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    # Parse services
    services = None
    if args.services:
        services = [s.strip() for s in args.services.split(",")]
    
    # Collect metrics
    async with MetricsCollector() as collector:
        result = await collector.collect_comprehensive_metrics(services, args.time_range, args.samples)
    
    # Output results
    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        # Summary format
        summary = result["performance_summary"]
        system = result["system_metrics"]
        anomalies = result["anomaly_analysis"]
        
        output = f"""
Performance Metrics Summary
===========================
Overall Status: {summary['overall_status'].upper()}
System Health: {summary['system_health'].upper()}

Services: {summary['healthy_services']} healthy, {summary['degraded_services']} degraded, {summary['critical_services']} critical

System Resources:
- CPU: {system['cpu_percent']:.1f}%
- Memory: {system['memory']['percent_used']:.1f}% ({system['memory']['used_gb']:.1f}GB used)
- Disk: {system['disk']['percent_used']:.1f}% ({system['disk']['used_gb']:.1f}GB used)

Performance Metrics:
- Avg Response Time: {summary['key_metrics'].get('avg_response_time_ms', 'N/A')}ms
- Avg Availability: {summary['key_metrics'].get('avg_availability_percent', 'N/A')}%

Anomalies Detected: {anomalies['anomaly_count']}
- Critical: {anomalies['severity_breakdown']['critical']}
- High: {anomalies['severity_breakdown']['high']}
- Medium: {anomalies['severity_breakdown']['medium']}

Recommendations:
{chr(10).join(f"- {rec}" for rec in result['recommendations'][:5])}
"""
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Metrics analysis saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())