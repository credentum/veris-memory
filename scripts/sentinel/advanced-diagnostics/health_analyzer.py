#!/usr/bin/env python3
"""
Advanced Health Analyzer for Veris Memory Services

This module provides comprehensive health analysis capabilities for all Veris Memory
services, including deep performance analysis, resource monitoring, and intelligent
health assessment.

Author: Claude Code Integration - Phase 2
Date: 2025-08-20
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import aiohttp
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ServiceConfig:
    """Configuration for a service health check."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.host = config.get('host', 'localhost')
        self.port = config['port']
        self.health_endpoint = config.get('health_endpoint', '/health')
        self.metrics_endpoint = config.get('metrics_endpoint', '/metrics')
        self.log_path = config.get('log_path', f'/var/log/veris-memory/{name}.log')
        self.dependencies = config.get('dependencies', [])
        self.timeout = config.get('timeout', 5)
        self.critical = config.get('critical', True)
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @property
    def health_url(self) -> str:
        return f"{self.base_url}{self.health_endpoint}"
    
    @property
    def metrics_url(self) -> str:
        return f"{self.base_url}{self.metrics_endpoint}"


class HealthMetrics:
    """Container for health analysis metrics."""
    
    def __init__(self):
        self.response_time_ms: float = 0.0
        self.status_code: int = 0
        self.is_healthy: bool = False
        self.error_message: str = ""
        self.response_size: int = 0
        self.headers: Dict[str, str] = {}
        self.response_data: Dict[str, Any] = {}


class AdvancedHealthAnalyzer:
    """
    Advanced health analyzer for Veris Memory services.
    
    Provides comprehensive health analysis including:
    - Basic connectivity and response checks
    - Performance metrics collection
    - Resource utilization monitoring
    - Error pattern analysis
    - Dependency health verification
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the health analyzer."""
        self.config = self._load_service_config(config_file)
        self.session: Optional[aiohttp.ClientSession] = None
        
    def _load_service_config(self, config_file: Optional[str]) -> Dict[str, ServiceConfig]:
        """Load service configuration."""
        default_config = {
            "mcp_server": {
                "port": 8000,
                "health_endpoint": "/",
                "metrics_endpoint": "/metrics",
                "log_path": "/var/log/veris-memory/mcp.log",
                "dependencies": ["qdrant", "neo4j", "redis"],
                "critical": True
            },
            "rest_api": {
                "port": 8001,
                "health_endpoint": "/api/v1/health",
                "metrics_endpoint": "/api/v1/metrics",
                "log_path": "/var/log/veris-memory/api.log",
                "dependencies": ["qdrant", "neo4j", "redis"],
                "critical": True
            },
            "sentinel": {
                "port": 9090,
                "health_endpoint": "/status",
                "metrics_endpoint": "/metrics",
                "log_path": "/var/log/veris-memory/sentinel.log",
                "dependencies": ["rest_api"],
                "critical": True
            },
            "dashboard": {
                "port": 8080,
                "health_endpoint": "/health",
                "metrics_endpoint": "/metrics",
                "log_path": "/var/log/veris-memory/dashboard.log",
                "dependencies": ["rest_api", "sentinel"],
                "critical": False
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    custom_config = json.load(f)
                default_config.update(custom_config)
            except Exception as e:
                logger.warning(f"Failed to load config file {config_file}: {e}")
        
        # Convert to ServiceConfig objects
        return {
            name: ServiceConfig(name, config) 
            for name, config in default_config.items()
        }
    
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
    
    async def analyze_service_health(self, service_name: str, alert_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform comprehensive health analysis for a specific service.
        
        Args:
            service_name: Name of the service to analyze
            alert_context: Optional context from the triggering alert
            
        Returns:
            Dict containing comprehensive health analysis
        """
        if service_name not in self.config:
            return {"error": f"Unknown service: {service_name}"}
        
        service_config = self.config[service_name]
        
        logger.info(f"Starting comprehensive health analysis for {service_name}")
        
        analysis = {
            "service_name": service_name,
            "analysis_timestamp": datetime.now().isoformat(),
            "alert_context": alert_context,
            "basic_health": await self._basic_health_check(service_config),
            "performance_metrics": await self._collect_performance_metrics(service_config),
            "resource_utilization": await self._check_resource_usage(service_config),
            "dependency_health": await self._check_dependencies(service_config),
            "error_analysis": await self._analyze_recent_errors(service_config),
            "trend_analysis": await self._analyze_trends(service_config),
            "recommendations": []
        }
        
        # Generate recommendations based on analysis
        analysis["recommendations"] = await self._generate_recommendations(analysis)
        
        # Calculate overall health score
        analysis["health_score"] = self._calculate_health_score(analysis)
        
        return analysis
    
    async def analyze_all_services(self, alert_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze health of all configured services.
        
        Args:
            alert_context: Optional context from the triggering alert
            
        Returns:
            Dict containing analysis for all services
        """
        logger.info("Starting comprehensive health analysis for all services")
        
        # Analyze all services concurrently
        tasks = [
            self.analyze_service_health(service_name, alert_context)
            for service_name in self.config.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_analysis = {
            "analysis_timestamp": datetime.now().isoformat(),
            "alert_context": alert_context,
            "services": {},
            "system_summary": {},
            "critical_issues": [],
            "recommendations": []
        }
        
        for service_name, result in zip(self.config.keys(), results):
            if isinstance(result, Exception):
                all_analysis["services"][service_name] = {
                    "error": str(result),
                    "health_score": 0
                }
            else:
                all_analysis["services"][service_name] = result
        
        # Generate system-wide summary
        all_analysis["system_summary"] = self._generate_system_summary(all_analysis["services"])
        
        return all_analysis
    
    async def _basic_health_check(self, service_config: ServiceConfig) -> Dict[str, Any]:
        """Perform basic health check for a service."""
        metrics = HealthMetrics()
        start_time = time.time()
        
        try:
            async with self.session.get(
                service_config.health_url,
                timeout=aiohttp.ClientTimeout(total=service_config.timeout)
            ) as response:
                end_time = time.time()
                metrics.response_time_ms = (end_time - start_time) * 1000
                metrics.status_code = response.status
                metrics.response_size = len(await response.read())
                metrics.headers = dict(response.headers)
                
                if response.content_type == 'application/json':
                    try:
                        metrics.response_data = await response.json()
                    except:
                        pass
                
                metrics.is_healthy = 200 <= response.status < 300
                
        except asyncio.TimeoutError:
            metrics.error_message = f"Timeout after {service_config.timeout}s"
            metrics.response_time_ms = service_config.timeout * 1000
        except aiohttp.ClientError as e:
            metrics.error_message = f"Connection error: {str(e)}"
        except Exception as e:
            metrics.error_message = f"Unexpected error: {str(e)}"
        
        return {
            "is_healthy": metrics.is_healthy,
            "response_time_ms": metrics.response_time_ms,
            "status_code": metrics.status_code,
            "error_message": metrics.error_message,
            "response_size": metrics.response_size,
            "response_data": metrics.response_data,
            "performance_category": self._categorize_performance(metrics.response_time_ms)
        }
    
    async def _collect_performance_metrics(self, service_config: ServiceConfig) -> Dict[str, Any]:
        """Collect detailed performance metrics."""
        metrics = {
            "response_times": [],
            "throughput_estimate": 0,
            "error_rate": 0,
            "availability": 0
        }
        
        # Perform multiple health checks to get performance baseline
        num_checks = 5
        successful_checks = 0
        response_times = []
        
        for i in range(num_checks):
            try:
                start_time = time.time()
                async with self.session.get(
                    service_config.health_url,
                    timeout=aiohttp.ClientTimeout(total=service_config.timeout)
                ) as response:
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    response_times.append(response_time)
                    
                    if 200 <= response.status < 300:
                        successful_checks += 1
                        
            except Exception as e:
                logger.debug(f"Performance check {i+1} failed: {e}")
                response_times.append(service_config.timeout * 1000)
            
            # Small delay between checks
            if i < num_checks - 1:
                await asyncio.sleep(0.5)
        
        if response_times:
            metrics["response_times"] = response_times
            metrics["avg_response_time"] = sum(response_times) / len(response_times)
            metrics["min_response_time"] = min(response_times)
            metrics["max_response_time"] = max(response_times)
            
        metrics["availability"] = (successful_checks / num_checks) * 100
        metrics["error_rate"] = ((num_checks - successful_checks) / num_checks) * 100
        
        # Estimate throughput (very rough)
        if metrics.get("avg_response_time", 0) > 0:
            metrics["throughput_estimate"] = 1000 / metrics["avg_response_time"]  # requests per second
        
        return metrics
    
    async def _check_resource_usage(self, service_config: ServiceConfig) -> Dict[str, Any]:
        """Check resource utilization (simplified version)."""
        # This is a simplified implementation
        # In production, you'd want to integrate with system monitoring tools
        
        return {
            "cpu_usage_percent": "unknown",
            "memory_usage_mb": "unknown", 
            "disk_usage_percent": "unknown",
            "network_connections": "unknown",
            "process_status": "unknown",
            "note": "Resource monitoring requires system-level access"
        }
    
    async def _check_dependencies(self, service_config: ServiceConfig) -> Dict[str, Any]:
        """Check health of service dependencies."""
        dependency_health = {}
        
        for dependency in service_config.dependencies:
            if dependency in self.config:
                # Check health of dependent service
                dep_config = self.config[dependency]
                health = await self._basic_health_check(dep_config)
                dependency_health[dependency] = {
                    "is_healthy": health["is_healthy"],
                    "response_time_ms": health["response_time_ms"],
                    "status": "healthy" if health["is_healthy"] else "unhealthy"
                }
            else:
                # External dependency (database, etc.)
                dependency_health[dependency] = await self._check_external_dependency(dependency)
        
        return {
            "dependencies": dependency_health,
            "all_dependencies_healthy": all(
                dep.get("is_healthy", False) 
                for dep in dependency_health.values()
            ),
            "unhealthy_dependencies": [
                name for name, health in dependency_health.items()
                if not health.get("is_healthy", False)
            ]
        }
    
    async def _check_external_dependency(self, dependency_name: str) -> Dict[str, Any]:
        """Check external dependency health (database, etc.)."""
        # Map of external dependencies to their typical health check methods
        external_deps = {
            "qdrant": {"port": 6333, "endpoint": "/"},
            "neo4j": {"port": 7474, "endpoint": "/browser/"},
            "redis": {"port": 6379, "endpoint": None}  # Redis doesn't have HTTP endpoint
        }
        
        if dependency_name not in external_deps:
            return {"is_healthy": False, "error": f"Unknown external dependency: {dependency_name}"}
        
        dep_config = external_deps[dependency_name]
        
        if dep_config["endpoint"]:
            # HTTP-based check
            try:
                url = f"http://localhost:{dep_config['port']}{dep_config['endpoint']}"
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return {
                        "is_healthy": 200 <= response.status < 400,
                        "response_time_ms": 0,  # Would need timing
                        "status_code": response.status
                    }
            except Exception as e:
                return {"is_healthy": False, "error": str(e)}
        else:
            # TCP-based check (simplified)
            return {"is_healthy": "unknown", "note": f"TCP check for {dependency_name} not implemented"}
    
    async def _analyze_recent_errors(self, service_config: ServiceConfig) -> Dict[str, Any]:
        """Analyze recent errors from logs."""
        # Simplified error analysis
        # In production, this would parse actual log files
        
        return {
            "recent_errors": [],
            "error_patterns": [],
            "error_frequency": "unknown",
            "critical_errors": [],
            "note": "Log analysis requires file system access to log files"
        }
    
    async def _analyze_trends(self, service_config: ServiceConfig) -> Dict[str, Any]:
        """Analyze performance trends."""
        # Simplified trend analysis
        # In production, this would query historical metrics
        
        return {
            "performance_trend": "unknown",
            "availability_trend": "unknown", 
            "error_rate_trend": "unknown",
            "capacity_trend": "unknown",
            "note": "Trend analysis requires historical metrics database"
        }
    
    def _categorize_performance(self, response_time_ms: float) -> str:
        """Categorize performance based on response time."""
        if response_time_ms < 100:
            return "excellent"
        elif response_time_ms < 500:
            return "good"
        elif response_time_ms < 2000:
            return "fair"
        elif response_time_ms < 5000:
            return "poor"
        else:
            return "critical"
    
    async def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Check basic health
        basic_health = analysis.get("basic_health", {})
        if not basic_health.get("is_healthy", False):
            recommendations.append(f"🚨 Service is not responding properly (status: {basic_health.get('status_code', 'unknown')})")
            recommendations.append("🔧 Check service logs and restart if necessary")
        
        # Check performance
        performance = analysis.get("performance_metrics", {})
        avg_response_time = performance.get("avg_response_time", 0)
        if avg_response_time > 2000:
            recommendations.append(f"⚠️ Slow response times detected (avg: {avg_response_time:.1f}ms)")
            recommendations.append("🔧 Investigate performance bottlenecks")
        
        availability = performance.get("availability", 100)
        if availability < 95:
            recommendations.append(f"⚠️ Low availability detected ({availability:.1f}%)")
            recommendations.append("🔧 Check for intermittent failures")
        
        # Check dependencies
        dependencies = analysis.get("dependency_health", {})
        unhealthy_deps = dependencies.get("unhealthy_dependencies", [])
        if unhealthy_deps:
            recommendations.append(f"🚨 Unhealthy dependencies detected: {', '.join(unhealthy_deps)}")
            recommendations.append("🔧 Resolve dependency issues before addressing service issues")
        
        return recommendations
    
    def _calculate_health_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall health score (0-100)."""
        score = 100.0
        
        # Basic health (40% of score)
        if not analysis.get("basic_health", {}).get("is_healthy", False):
            score -= 40
        
        # Performance (30% of score)
        performance = analysis.get("performance_metrics", {})
        availability = performance.get("availability", 100)
        score = score * (availability / 100) * 0.3 + score * 0.7
        
        # Dependencies (30% of score)
        dependencies = analysis.get("dependency_health", {})
        if not dependencies.get("all_dependencies_healthy", True):
            unhealthy_count = len(dependencies.get("unhealthy_dependencies", []))
            total_deps = len(dependencies.get("dependencies", {}))
            if total_deps > 0:
                dep_health_ratio = 1 - (unhealthy_count / total_deps)
                score = score * dep_health_ratio * 0.3 + score * 0.7
        
        return max(0, min(100, score))
    
    def _generate_system_summary(self, services_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate system-wide summary."""
        total_services = len(services_analysis)
        healthy_services = sum(
            1 for analysis in services_analysis.values()
            if analysis.get("basic_health", {}).get("is_healthy", False)
        )
        
        avg_health_score = sum(
            analysis.get("health_score", 0)
            for analysis in services_analysis.values()
        ) / total_services if total_services > 0 else 0
        
        critical_services = [
            name for name, analysis in services_analysis.items()
            if analysis.get("health_score", 0) < 50
        ]
        
        return {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "unhealthy_services": total_services - healthy_services,
            "system_health_percentage": (healthy_services / total_services) * 100 if total_services > 0 else 0,
            "average_health_score": avg_health_score,
            "critical_services": critical_services,
            "system_status": "healthy" if avg_health_score > 80 else "degraded" if avg_health_score > 50 else "critical"
        }


async def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Advanced Health Analyzer for Veris Memory")
    parser.add_argument("--service", help="Specific service to analyze")
    parser.add_argument("--alert-context", help="JSON string with alert context")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "summary"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    # Parse alert context
    alert_context = None
    if args.alert_context:
        try:
            alert_context = json.loads(args.alert_context)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid alert context JSON: {e}")
            sys.exit(1)
    
    # Perform analysis
    async with AdvancedHealthAnalyzer(args.config) as analyzer:
        if args.service:
            result = await analyzer.analyze_service_health(args.service, alert_context)
        else:
            result = await analyzer.analyze_all_services(alert_context)
    
    # Output results
    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        # Summary format
        if "services" in result:
            # System summary
            summary = result["system_summary"]
            output = f"""
Health Analysis Summary
=======================
System Status: {summary['system_status'].upper()}
Services: {summary['healthy_services']}/{summary['total_services']} healthy
Average Health Score: {summary['average_health_score']:.1f}/100

Critical Services: {', '.join(summary['critical_services']) if summary['critical_services'] else 'None'}
"""
        else:
            # Single service summary
            output = f"""
Service Health Analysis: {result['service_name']}
=================================================
Health Score: {result['health_score']:.1f}/100
Status: {'Healthy' if result['basic_health']['is_healthy'] else 'Unhealthy'}
Response Time: {result['basic_health']['response_time_ms']:.1f}ms

Recommendations:
{chr(10).join(f"- {rec}" for rec in result['recommendations'])}
"""
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Analysis saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())