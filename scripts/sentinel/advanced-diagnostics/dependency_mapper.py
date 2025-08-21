#!/usr/bin/env python3
"""
Service Dependency Mapper for Veris Memory Services

This module provides sophisticated service dependency analysis and impact assessment,
including cascade failure detection, critical path identification, and recovery
order optimization for Veris Memory infrastructure.

Author: Claude Code Integration - Phase 2
Date: 2025-08-20
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
import aiohttp
import argparse
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ServiceNode:
    """Represents a service in the dependency graph."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.dependencies: Set[str] = set(config.get('dependencies', []))
        self.dependents: Set[str] = set()
        self.health_status: str = "unknown"
        self.criticality: str = config.get('criticality', 'medium')
        self.recovery_priority: int = config.get('recovery_priority', 5)
        self.is_external: bool = config.get('external', False)


class DependencyMapper:
    """
    Advanced service dependency mapper and impact analyzer.
    
    Provides capabilities for:
    - Dependency graph construction and analysis
    - Cascade failure impact assessment
    - Critical path identification
    - Recovery order optimization
    - Service isolation impact analysis
    - Health propagation modeling
    """
    
    def __init__(self):
        """Initialize the dependency mapper."""
        self.service_graph: Dict[str, ServiceNode] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialize_service_graph()
    
    def _initialize_service_graph(self):
        """Initialize the service dependency graph."""
        # Define the complete service dependency configuration
        service_configs = {
            # Core Application Services
            "rest_api": {
                "port": 8001,
                "health_endpoint": "/api/v1/health",
                "dependencies": ["qdrant", "neo4j", "redis"],
                "criticality": "critical",
                "recovery_priority": 2,
                "description": "Main REST API service"
            },
            "mcp_server": {
                "port": 8000,
                "health_endpoint": "/",
                "dependencies": ["qdrant", "neo4j", "redis"],
                "criticality": "critical", 
                "recovery_priority": 1,
                "description": "MCP protocol server"
            },
            "sentinel": {
                "port": 9090,
                "health_endpoint": "/status",
                "dependencies": ["rest_api"],
                "criticality": "high",
                "recovery_priority": 4,
                "description": "Monitoring and alerting service"
            },
            "dashboard": {
                "port": 8080,
                "health_endpoint": "/health",
                "dependencies": ["rest_api", "sentinel"],
                "criticality": "medium",
                "recovery_priority": 5,
                "description": "Monitoring dashboard"
            },
            
            # External Dependencies (Infrastructure)
            "qdrant": {
                "port": 6333,
                "health_endpoint": "/",
                "dependencies": [],
                "criticality": "critical",
                "recovery_priority": 1,
                "external": True,
                "description": "Vector database for semantic search"
            },
            "neo4j": {
                "port": 7474,
                "health_endpoint": "/browser/",
                "dependencies": [],
                "criticality": "critical",
                "recovery_priority": 1,
                "external": True,
                "description": "Graph database for relationships"
            },
            "redis": {
                "port": 6379,
                "health_endpoint": None,  # Redis doesn't have HTTP endpoint
                "dependencies": [],
                "criticality": "high",
                "recovery_priority": 1,
                "external": True,
                "description": "Key-value cache and session storage"
            },
            
            # System-level Dependencies
            "docker": {
                "dependencies": [],
                "criticality": "critical",
                "recovery_priority": 0,
                "external": True,
                "description": "Container runtime"
            },
            "host_system": {
                "dependencies": [],
                "criticality": "critical",
                "recovery_priority": 0,
                "external": True,
                "description": "Host operating system"
            },
            "network": {
                "dependencies": ["host_system"],
                "criticality": "critical",
                "recovery_priority": 0,
                "external": True,
                "description": "Network connectivity"
            }
        }
        
        # Create service nodes
        for service_name, config in service_configs.items():
            self.service_graph[service_name] = ServiceNode(service_name, config)
        
        # Build dependency relationships
        for service_name, node in self.service_graph.items():
            for dependency in node.dependencies:
                if dependency in self.service_graph:
                    self.service_graph[dependency].dependents.add(service_name)
    
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
    
    async def analyze_dependency_impact(
        self,
        failed_service: str,
        alert_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive dependency impact analysis for a failed service.
        
        Args:
            failed_service: Name of the service that has failed
            alert_context: Optional context from the triggering alert
            
        Returns:
            Dict containing comprehensive dependency impact analysis
        """
        logger.info(f"Analyzing dependency impact for failed service: {failed_service}")
        
        # Update service health status
        await self._update_service_health_status()
        
        # Mark the failed service
        if failed_service in self.service_graph:
            self.service_graph[failed_service].health_status = "failed"
        
        analysis = {
            "analysis_timestamp": datetime.now().isoformat(),
            "failed_service": failed_service,
            "alert_context": alert_context,
            "immediate_impact": await self._analyze_immediate_impact(failed_service),
            "cascade_analysis": await self._analyze_cascade_impact(failed_service),
            "critical_path_analysis": await self._analyze_critical_paths(failed_service),
            "recovery_strategy": await self._generate_recovery_strategy(failed_service),
            "risk_assessment": await self._assess_service_risks(failed_service),
            "dependency_graph": self._export_dependency_graph(),
            "recommendations": []
        }
        
        # Generate comprehensive recommendations
        analysis["recommendations"] = await self._generate_dependency_recommendations(analysis)
        
        return analysis
    
    async def _update_service_health_status(self):
        """Update health status for all services."""
        for service_name, node in self.service_graph.items():
            if node.is_external or not hasattr(node.config, 'port'):
                continue
                
            try:
                port = node.config.get('port')
                health_endpoint = node.config.get('health_endpoint', '/health')
                
                if not port or not health_endpoint:
                    node.health_status = "unknown"
                    continue
                
                target_host = os.getenv('TARGET_HOST', 'localhost')
                url = f"http://{target_host}:{port}{health_endpoint}"
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if 200 <= response.status < 300:
                        node.health_status = "healthy"
                    else:
                        node.health_status = "unhealthy"
                        
            except Exception as e:
                logger.debug(f"Health check failed for {service_name}: {e}")
                node.health_status = "unhealthy"
    
    async def _analyze_immediate_impact(self, failed_service: str) -> Dict[str, Any]:
        """Analyze immediate impact of service failure."""
        if failed_service not in self.service_graph:
            return {"error": f"Unknown service: {failed_service}"}
        
        failed_node = self.service_graph[failed_service]
        
        # Direct dependents (immediately affected)
        directly_affected = list(failed_node.dependents)
        
        # Services that depend on the failed service
        affected_services = []
        for dependent in directly_affected:
            if dependent in self.service_graph:
                dep_node = self.service_graph[dependent]
                affected_services.append({
                    "service": dependent,
                    "criticality": dep_node.criticality,
                    "description": dep_node.config.get("description", ""),
                    "impact_type": "direct_dependency_failure"
                })
        
        # Count services by criticality
        criticality_impact = defaultdict(int)
        for service in affected_services:
            criticality_impact[service["criticality"]] += 1
        
        return {
            "failed_service_info": {
                "name": failed_service,
                "criticality": failed_node.criticality,
                "description": failed_node.config.get("description", ""),
                "is_external": failed_node.is_external
            },
            "directly_affected_services": affected_services,
            "affected_service_count": len(affected_services),
            "criticality_breakdown": dict(criticality_impact),
            "business_impact": self._assess_business_impact(affected_services)
        }
    
    async def _analyze_cascade_impact(self, failed_service: str) -> Dict[str, Any]:
        """Analyze potential cascade failure impact."""
        cascade_paths = []
        all_affected = set()
        
        # Use BFS to find cascade paths
        queue = deque([(failed_service, [failed_service])])
        visited = {failed_service}
        
        while queue:
            current_service, path = queue.popleft()
            
            if current_service in self.service_graph:
                for dependent in self.service_graph[current_service].dependents:
                    if dependent not in visited:
                        new_path = path + [dependent]
                        cascade_paths.append({
                            "path": new_path,
                            "length": len(new_path) - 1,
                            "services": new_path,
                            "final_impact": dependent
                        })
                        
                        queue.append((dependent, new_path))
                        visited.add(dependent)
                        all_affected.add(dependent)
        
        # Analyze cascade severity
        cascade_severity = "low"
        critical_services_affected = 0
        
        for service in all_affected:
            if service in self.service_graph:
                if self.service_graph[service].criticality == "critical":
                    critical_services_affected += 1
        
        if critical_services_affected > 0:
            cascade_severity = "critical"
        elif len(all_affected) > 3:
            cascade_severity = "high"
        elif len(all_affected) > 1:
            cascade_severity = "medium"
        
        return {
            "cascade_paths": cascade_paths,
            "total_affected_services": len(all_affected),
            "critical_services_affected": critical_services_affected,
            "cascade_severity": cascade_severity,
            "max_cascade_depth": max((path["length"] for path in cascade_paths), default=0),
            "affected_service_list": list(all_affected)
        }
    
    async def _analyze_critical_paths(self, failed_service: str) -> Dict[str, Any]:
        """Analyze critical paths affected by the failure."""
        critical_paths = []
        
        # Find paths through critical services
        for service_name, node in self.service_graph.items():
            if node.criticality == "critical" and service_name != failed_service:
                # Check if this critical service depends on the failed service
                path_to_failed = self._find_dependency_path(service_name, failed_service)
                if path_to_failed:
                    critical_paths.append({
                        "critical_service": service_name,
                        "path_to_failed": path_to_failed,
                        "path_length": len(path_to_failed) - 1,
                        "description": f"Critical service {service_name} affected via {' -> '.join(path_to_failed)}"
                    })
        
        # Identify single points of failure
        single_points_of_failure = []
        for service_name, node in self.service_graph.items():
            dependent_count = len(node.dependents)
            critical_dependents = sum(
                1 for dep in node.dependents 
                if dep in self.service_graph and self.service_graph[dep].criticality == "critical"
            )
            
            if dependent_count > 2 or critical_dependents > 0:
                single_points_of_failure.append({
                    "service": service_name,
                    "dependent_count": dependent_count,
                    "critical_dependents": critical_dependents,
                    "risk_level": "high" if critical_dependents > 0 else "medium"
                })
        
        return {
            "critical_paths_affected": critical_paths,
            "critical_path_count": len(critical_paths),
            "single_points_of_failure": single_points_of_failure,
            "infrastructure_risk": "high" if len(critical_paths) > 2 else "medium" if critical_paths else "low"
        }
    
    def _find_dependency_path(self, from_service: str, to_service: str) -> Optional[List[str]]:
        """Find dependency path from one service to another using BFS."""
        if from_service not in self.service_graph or to_service not in self.service_graph:
            return None
        
        queue = deque([(from_service, [from_service])])
        visited = {from_service}
        
        while queue:
            current, path = queue.popleft()
            
            if current == to_service:
                return path
            
            for dependency in self.service_graph[current].dependencies:
                if dependency not in visited and dependency in self.service_graph:
                    queue.append((dependency, path + [dependency]))
                    visited.add(dependency)
        
        return None
    
    async def _generate_recovery_strategy(self, failed_service: str) -> Dict[str, Any]:
        """Generate optimal recovery strategy."""
        recovery_order = self._calculate_recovery_order(failed_service)
        
        recovery_steps = []
        for i, service in enumerate(recovery_order):
            if service in self.service_graph:
                node = self.service_graph[service]
                recovery_steps.append({
                    "step": i + 1,
                    "service": service,
                    "action": "restart" if not node.is_external else "verify",
                    "priority": node.recovery_priority,
                    "criticality": node.criticality,
                    "estimated_time_minutes": self._estimate_recovery_time(service),
                    "dependencies_required": list(node.dependencies),
                    "health_check": node.config.get("health_endpoint"),
                    "description": f"{'Restart' if not node.is_external else 'Verify'} {service} service"
                })
        
        total_recovery_time = sum(step["estimated_time_minutes"] for step in recovery_steps)
        
        return {
            "recovery_order": recovery_order,
            "recovery_steps": recovery_steps,
            "total_estimated_time_minutes": total_recovery_time,
            "parallel_recovery_possible": self._identify_parallel_recovery_opportunities(recovery_order),
            "rollback_plan": self._generate_rollback_plan(failed_service)
        }
    
    def _calculate_recovery_order(self, failed_service: str) -> List[str]:
        """Calculate optimal recovery order using topological sort."""
        # Start with failed service and all affected services
        affected_services = {failed_service}
        
        # Add all services that depend on the failed service
        queue = deque([failed_service])
        while queue:
            current = queue.popleft()
            if current in self.service_graph:
                for dependent in self.service_graph[current].dependents:
                    if dependent not in affected_services:
                        affected_services.add(dependent)
                        queue.append(dependent)
        
        # Perform topological sort on affected services
        recovery_order = []
        visited = set()
        temp_visited = set()
        
        def dfs(service):
            if service in temp_visited:
                return  # Cycle detected, skip
            if service in visited:
                return
            
            temp_visited.add(service)
            
            # Visit dependencies first
            if service in self.service_graph:
                for dependency in self.service_graph[service].dependencies:
                    if dependency in affected_services:
                        dfs(dependency)
            
            temp_visited.remove(service)
            visited.add(service)
            recovery_order.append(service)
        
        # Sort by recovery priority first
        sorted_services = sorted(
            affected_services,
            key=lambda s: self.service_graph[s].recovery_priority if s in self.service_graph else 999
        )
        
        for service in sorted_services:
            if service not in visited:
                dfs(service)
        
        return recovery_order
    
    def _estimate_recovery_time(self, service: str) -> int:
        """Estimate recovery time for a service in minutes."""
        if service not in self.service_graph:
            return 5
        
        node = self.service_graph[service]
        
        # Base recovery times by service type
        base_times = {
            "critical": 10,
            "high": 7,
            "medium": 5,
            "low": 3
        }
        
        base_time = base_times.get(node.criticality, 5)
        
        # External services may take longer
        if node.is_external:
            base_time += 5
        
        # Services with many dependencies take longer
        dependency_penalty = len(node.dependencies) * 2
        
        return base_time + dependency_penalty
    
    def _identify_parallel_recovery_opportunities(self, recovery_order: List[str]) -> List[List[str]]:
        """Identify services that can be recovered in parallel."""
        parallel_groups = []
        remaining_services = set(recovery_order)
        
        while remaining_services:
            parallel_group = []
            
            for service in list(remaining_services):
                # Check if all dependencies of this service are already recovered
                if service in self.service_graph:
                    dependencies = self.service_graph[service].dependencies
                    if all(dep not in remaining_services for dep in dependencies):
                        parallel_group.append(service)
            
            if parallel_group:
                parallel_groups.append(parallel_group)
                remaining_services -= set(parallel_group)
            else:
                # Fallback: take the first service to avoid infinite loop
                if remaining_services:
                    service = list(remaining_services)[0]
                    parallel_groups.append([service])
                    remaining_services.remove(service)
        
        return parallel_groups
    
    def _generate_rollback_plan(self, failed_service: str) -> Dict[str, Any]:
        """Generate rollback plan in case recovery fails."""
        return {
            "rollback_strategy": "isolate_and_bypass",
            "isolation_steps": [
                f"Isolate {failed_service} from traffic",
                "Route traffic around failed service",
                "Enable degraded mode operation"
            ],
            "bypass_options": self._identify_bypass_options(failed_service),
            "data_consistency_checks": [
                "Verify data integrity",
                "Check transaction consistency",
                "Validate backup restoration points"
            ]
        }
    
    def _identify_bypass_options(self, failed_service: str) -> List[str]:
        """Identify potential bypass options for a failed service."""
        bypass_options = []
        
        if failed_service == "rest_api":
            bypass_options.extend([
                "Use MCP server directly for core operations",
                "Enable read-only mode for non-critical operations"
            ])
        elif failed_service == "mcp_server":
            bypass_options.extend([
                "Use REST API for compatible operations",
                "Enable manual operation mode"
            ])
        elif failed_service in ["qdrant", "neo4j", "redis"]:
            bypass_options.extend([
                "Enable cached responses for read operations",
                "Use alternative storage backends if available",
                "Enable offline mode with local storage"
            ])
        
        return bypass_options
    
    async def _assess_service_risks(self, failed_service: str) -> Dict[str, Any]:
        """Assess overall service risks and vulnerabilities."""
        risks = {
            "high_risk_services": [],
            "single_points_of_failure": [],
            "cascade_risks": [],
            "infrastructure_dependencies": []
        }
        
        for service_name, node in self.service_graph.items():
            # High-risk services (critical with many dependents)
            if node.criticality == "critical" and len(node.dependents) > 1:
                risks["high_risk_services"].append({
                    "service": service_name,
                    "dependent_count": len(node.dependents),
                    "risk_reason": "Critical service with multiple dependents"
                })
            
            # Single points of failure
            if len(node.dependents) > 2:
                risks["single_points_of_failure"].append({
                    "service": service_name,
                    "dependent_count": len(node.dependents),
                    "dependents": list(node.dependents)
                })
            
            # Infrastructure dependencies
            if node.is_external and node.criticality == "critical":
                risks["infrastructure_dependencies"].append({
                    "service": service_name,
                    "risk_level": "high",
                    "impact": "System-wide failure possible"
                })
        
        return risks
    
    def _assess_business_impact(self, affected_services: List[Dict]) -> str:
        """Assess business impact of service failures."""
        critical_count = sum(1 for s in affected_services if s["criticality"] == "critical")
        high_count = sum(1 for s in affected_services if s["criticality"] == "high")
        
        if critical_count > 0:
            return "severe"
        elif high_count > 1:
            return "high"
        elif len(affected_services) > 2:
            return "medium"
        else:
            return "low"
    
    def _export_dependency_graph(self) -> Dict[str, Any]:
        """Export dependency graph for visualization."""
        graph_data = {
            "nodes": [],
            "edges": []
        }
        
        for service_name, node in self.service_graph.items():
            graph_data["nodes"].append({
                "id": service_name,
                "label": service_name,
                "criticality": node.criticality,
                "health_status": node.health_status,
                "is_external": node.is_external,
                "recovery_priority": node.recovery_priority,
                "description": node.config.get("description", "")
            })
            
            for dependency in node.dependencies:
                graph_data["edges"].append({
                    "from": service_name,
                    "to": dependency,
                    "type": "depends_on"
                })
        
        return graph_data
    
    async def _generate_dependency_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on dependency analysis."""
        recommendations = []
        
        failed_service = analysis["failed_service"]
        immediate_impact = analysis["immediate_impact"]
        cascade_analysis = analysis["cascade_analysis"]
        critical_path_analysis = analysis["critical_path_analysis"]
        
        # Immediate response recommendations
        affected_count = immediate_impact["affected_service_count"]
        if affected_count > 0:
            recommendations.append(f"🚨 Service failure will impact {affected_count} dependent services")
            recommendations.append(f"🔧 Follow recovery order: {' → '.join(analysis['recovery_strategy']['recovery_order'])}")
        
        # Cascade failure recommendations
        cascade_severity = cascade_analysis["cascade_severity"]
        if cascade_severity in ["critical", "high"]:
            recommendations.append(f"⚠️ High cascade failure risk detected ({cascade_severity} severity)")
            recommendations.append("🔧 Implement circuit breakers to prevent cascade failures")
        
        # Critical path recommendations
        critical_paths = critical_path_analysis["critical_paths_affected"]
        if critical_paths:
            recommendations.append(f"🎯 {len(critical_paths)} critical service paths affected")
            recommendations.append("🔧 Priority recovery of critical infrastructure services")
        
        # Architecture recommendations
        spof_count = len(critical_path_analysis["single_points_of_failure"])
        if spof_count > 0:
            recommendations.append(f"⚠️ {spof_count} single points of failure identified")
            recommendations.append("🏗️ Consider implementing service redundancy and load balancing")
        
        # Recovery strategy recommendations
        recovery_time = analysis["recovery_strategy"]["total_estimated_time_minutes"]
        if recovery_time > 30:
            recommendations.append(f"⏱️ Estimated recovery time: {recovery_time} minutes")
            recommendations.append("🚀 Consider parallel recovery to reduce downtime")
        
        return recommendations


async def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Service Dependency Mapper for Veris Memory")
    parser.add_argument("--failed-service", required=True, help="Name of the failed service")
    parser.add_argument("--alert-context", help="JSON string with alert context")
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
    
    # Analyze dependency impact
    async with DependencyMapper() as mapper:
        result = await mapper.analyze_dependency_impact(args.failed_service, alert_context)
    
    # Output results
    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        # Summary format
        immediate = result["immediate_impact"]
        cascade = result["cascade_analysis"]
        recovery = result["recovery_strategy"]
        
        output = f"""
Dependency Impact Analysis: {args.failed_service}
================================================
Failed Service: {immediate['failed_service_info']['name']} ({immediate['failed_service_info']['criticality']})

Immediate Impact:
- Services Affected: {immediate['affected_service_count']}
- Business Impact: {immediate['business_impact']}

Cascade Analysis:
- Total Affected: {cascade['total_affected_services']}
- Severity: {cascade['cascade_severity']}
- Max Cascade Depth: {cascade['max_cascade_depth']}

Recovery Strategy:
- Recovery Steps: {len(recovery['recovery_steps'])}
- Estimated Time: {recovery['total_estimated_time_minutes']} minutes
- Recovery Order: {' → '.join(recovery['recovery_order'][:5])}

Recommendations:
{chr(10).join(f"- {rec}" for rec in result['recommendations'][:5])}
"""
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Dependency analysis saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())