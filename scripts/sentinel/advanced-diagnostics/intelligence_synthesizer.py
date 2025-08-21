#!/usr/bin/env python3
"""
Intelligence Synthesizer for Veris Memory Diagnostics

This module provides AI-powered analysis that combines all diagnostic data sources
into actionable intelligence, including root cause analysis, impact assessment,
and automated recommendation generation for Veris Memory monitoring.

Author: Claude Code Integration - Phase 2
Date: 2025-08-20
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import argparse
from collections import defaultdict, Counter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RootCausePattern:
    """Represents a root cause pattern with diagnostic indicators."""
    
    def __init__(self, name: str, description: str, indicators: List[str], confidence_threshold: float):
        self.name = name
        self.description = description
        self.indicators = indicators
        self.confidence_threshold = confidence_threshold
        self.matched_indicators: List[str] = []
        self.confidence_score: float = 0.0


class IntelligenceSynthesizer:
    """
    AI-powered intelligence synthesizer for comprehensive diagnostic analysis.
    
    Combines data from:
    - Health analyzer (service health, performance)
    - Log collector (error patterns, correlations)
    - Metrics collector (system resources, performance trends)
    - Dependency mapper (cascade analysis, recovery strategies)
    
    Provides:
    - Root cause analysis with confidence scoring
    - Impact assessment and prioritization
    - Automated recommendation generation
    - Preventive strategy suggestions
    - Recovery action planning
    """
    
    def __init__(self):
        """Initialize the intelligence synthesizer."""
        self.root_cause_patterns = self._initialize_root_cause_patterns()
        self.intelligence_rules = self._initialize_intelligence_rules()
    
    def _initialize_root_cause_patterns(self) -> List[RootCausePattern]:
        """Initialize root cause detection patterns."""
        patterns = [
            # Database-related issues
            RootCausePattern(
                "database_overload",
                "Database is experiencing high load or connection exhaustion",
                [
                    "high_db_connections", "slow_query_times", "connection_timeouts",
                    "database_connection_failure", "deadlock_detected", "high_latency"
                ],
                0.7
            ),
            RootCausePattern(
                "database_connectivity",
                "Database connectivity issues preventing service operation",
                [
                    "database_connection_failure", "connection_refused", "network_timeout",
                    "unhealthy_dependencies", "service_unavailable"
                ],
                0.8
            ),
            
            # Memory-related issues
            RootCausePattern(
                "memory_exhaustion",
                "System or service memory exhaustion causing failures",
                [
                    "out_of_memory", "memory_allocation_failed", "high_memory_usage",
                    "gc_overhead", "memory_leak", "system_memory_critical"
                ],
                0.8
            ),
            
            # Performance degradation
            RootCausePattern(
                "performance_degradation",
                "Service performance has degraded significantly",
                [
                    "high_latency", "slow_response", "high_response_time",
                    "performance_category_poor", "availability_low", "throughput_low"
                ],
                0.6
            ),
            
            # Network issues
            RootCausePattern(
                "network_connectivity",
                "Network connectivity issues affecting service communication",
                [
                    "network_timeout", "connection_refused", "ssl_errors",
                    "connection_failed", "network_unreachable", "dns_resolution_failed"
                ],
                0.7
            ),
            
            # Resource exhaustion
            RootCausePattern(
                "resource_exhaustion",
                "System resources (CPU, disk, etc.) are exhausted",
                [
                    "high_cpu_usage", "disk_space_full", "high_disk_usage",
                    "system_cpu_critical", "system_disk_critical", "load_average_high"
                ],
                0.8
            ),
            
            # Security issues
            RootCausePattern(
                "security_incident",
                "Security-related issues affecting service operation",
                [
                    "authentication_failure", "security_violations", "unauthorized_access",
                    "rate_limiting", "firewall_blocked", "certificate_error"
                ],
                0.7
            ),
            
            # Configuration issues
            RootCausePattern(
                "configuration_drift",
                "Configuration issues or environment inconsistencies",
                [
                    "config_validation_failed", "environment_mismatch", "missing_config",
                    "version_mismatch", "dependency_version_conflict"
                ],
                0.6
            ),
            
            # Cascade failures
            RootCausePattern(
                "cascade_failure",
                "Failure in one service is causing cascade failures in dependent services",
                [
                    "cascade_severity_high", "multiple_service_failures", "dependency_failure",
                    "simultaneous_errors", "service_correlation"
                ],
                0.8
            ),
            
            # Infrastructure issues
            RootCausePattern(
                "infrastructure_failure",
                "Underlying infrastructure or platform issues",
                [
                    "host_system_failure", "docker_issues", "network_infrastructure",
                    "external_service_failure", "platform_degradation"
                ],
                0.9
            )
        ]
        
        return patterns
    
    def _initialize_intelligence_rules(self) -> Dict[str, Any]:
        """Initialize intelligence analysis rules."""
        return {
            "urgency_factors": {
                "critical_service_count": 0.4,
                "cascade_severity": 0.3,
                "system_resource_usage": 0.2,
                "error_frequency": 0.1
            },
            "confidence_adjustments": {
                "multiple_indicators": 0.2,
                "log_correlation": 0.15,
                "metrics_correlation": 0.15,
                "dependency_correlation": 0.1
            },
            "priority_weights": {
                "business_impact": 0.35,
                "technical_complexity": 0.25,
                "recovery_time": 0.25,
                "risk_level": 0.15
            }
        }
    
    async def synthesize_intelligence(
        self,
        health_analysis: Dict[str, Any],
        log_analysis: Dict[str, Any],
        metrics_analysis: Dict[str, Any],
        dependency_analysis: Dict[str, Any],
        alert_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Synthesize comprehensive intelligence from all diagnostic sources.
        
        Args:
            health_analysis: Results from health analyzer
            log_analysis: Results from log collector
            metrics_analysis: Results from metrics collector
            dependency_analysis: Results from dependency mapper
            alert_context: Original alert context
            
        Returns:
            Dict containing synthesized intelligence and recommendations
        """
        logger.info("Synthesizing intelligence from all diagnostic sources")
        
        # Extract key indicators from all sources
        indicators = await self._extract_indicators(
            health_analysis, log_analysis, metrics_analysis, dependency_analysis
        )
        
        # Perform root cause analysis
        root_cause_analysis = await self._analyze_root_causes(indicators)
        
        # Assess overall impact
        impact_assessment = await self._assess_comprehensive_impact(
            health_analysis, log_analysis, metrics_analysis, dependency_analysis
        )
        
        # Generate prioritized recommendations
        recommendations = await self._generate_intelligent_recommendations(
            root_cause_analysis, impact_assessment, dependency_analysis
        )
        
        # Calculate urgency and priority
        urgency_assessment = await self._assess_urgency(
            root_cause_analysis, impact_assessment, metrics_analysis
        )
        
        # Generate prevention strategies
        prevention_strategies = await self._generate_prevention_strategies(
            root_cause_analysis, indicators
        )
        
        # Create executive summary
        executive_summary = await self._create_executive_summary(
            root_cause_analysis, impact_assessment, urgency_assessment
        )
        
        return {
            "synthesis_timestamp": datetime.now().isoformat(),
            "alert_context": alert_context,
            "executive_summary": executive_summary,
            "root_cause_analysis": root_cause_analysis,
            "impact_assessment": impact_assessment,
            "urgency_assessment": urgency_assessment,
            "prioritized_recommendations": recommendations,
            "prevention_strategies": prevention_strategies,
            "diagnostic_correlation": await self._analyze_diagnostic_correlations(
                health_analysis, log_analysis, metrics_analysis, dependency_analysis
            ),
            "confidence_metrics": self._calculate_confidence_metrics(root_cause_analysis),
            "next_steps": await self._generate_next_steps(recommendations, urgency_assessment)
        }
    
    async def _extract_indicators(
        self,
        health_analysis: Dict[str, Any],
        log_analysis: Dict[str, Any],
        metrics_analysis: Dict[str, Any],
        dependency_analysis: Dict[str, Any]
    ) -> List[str]:
        """Extract diagnostic indicators from all analysis sources."""
        indicators = []
        
        # Health analysis indicators
        if isinstance(health_analysis, dict):
            for service_name, analysis in health_analysis.get("services", {}).items():
                if not analysis.get("basic_health", {}).get("is_healthy", True):
                    indicators.append("service_unhealthy")
                
                perf_category = analysis.get("basic_health", {}).get("performance_category", "")
                if perf_category in ["poor", "critical"]:
                    indicators.append("high_latency")
                
                deps = analysis.get("dependency_health", {})
                if not deps.get("all_dependencies_healthy", True):
                    indicators.append("unhealthy_dependencies")
        
        # Log analysis indicators
        if isinstance(log_analysis, dict):
            pattern_matches = log_analysis.get("log_analysis", {}).get("pattern_matches", {})
            for pattern_name, pattern_data in pattern_matches.items():
                if pattern_data.get("match_count", 0) > 0:
                    indicators.append(pattern_name)
            
            error_frequency = log_analysis.get("log_analysis", {}).get("error_frequency", {})
            total_errors = error_frequency.get("total_errors", 0)
            if total_errors > 10:
                indicators.append("high_error_frequency")
        
        # Metrics analysis indicators
        if isinstance(metrics_analysis, dict):
            system_metrics = metrics_analysis.get("system_metrics", {})
            
            # CPU indicators
            cpu_percent = system_metrics.get("cpu_percent", 0)
            if cpu_percent > 90:
                indicators.append("system_cpu_critical")
            elif cpu_percent > 80:
                indicators.append("high_cpu_usage")
            
            # Memory indicators
            memory = system_metrics.get("memory", {})
            memory_percent = memory.get("percent_used", 0)
            if memory_percent > 95:
                indicators.append("system_memory_critical")
            elif memory_percent > 85:
                indicators.append("high_memory_usage")
            
            # Service performance indicators
            service_metrics = metrics_analysis.get("service_metrics", {})
            for service_name, metrics in service_metrics.items():
                if isinstance(metrics, dict) and "error" not in metrics:
                    perf_category = metrics.get("performance_category", "")
                    if perf_category in ["poor", "critical"]:
                        indicators.append("performance_category_poor")
                    
                    availability = metrics.get("availability_percent", 100)
                    if availability < 90:
                        indicators.append("availability_low")
        
        # Dependency analysis indicators
        if isinstance(dependency_analysis, dict):
            cascade_analysis = dependency_analysis.get("cascade_analysis", {})
            cascade_severity = cascade_analysis.get("cascade_severity", "low")
            if cascade_severity in ["high", "critical"]:
                indicators.append("cascade_severity_high")
            
            affected_count = cascade_analysis.get("total_affected_services", 0)
            if affected_count > 2:
                indicators.append("multiple_service_failures")
        
        return list(set(indicators))  # Remove duplicates
    
    async def _analyze_root_causes(self, indicators: List[str]) -> Dict[str, Any]:
        """Analyze potential root causes based on indicators."""
        root_causes = []
        
        for pattern in self.root_cause_patterns:
            # Check how many indicators match this pattern
            matched_indicators = [ind for ind in indicators if ind in pattern.indicators]
            
            if matched_indicators:
                # Calculate confidence score
                base_confidence = len(matched_indicators) / len(pattern.indicators)
                
                # Apply confidence adjustments
                adjustments = self.intelligence_rules["confidence_adjustments"]
                if len(matched_indicators) > 2:
                    base_confidence += adjustments["multiple_indicators"]
                
                pattern.matched_indicators = matched_indicators
                pattern.confidence_score = min(1.0, base_confidence)
                
                if pattern.confidence_score >= pattern.confidence_threshold:
                    root_causes.append({
                        "root_cause": pattern.name,
                        "description": pattern.description,
                        "confidence_score": round(pattern.confidence_score, 3),
                        "matched_indicators": matched_indicators,
                        "indicator_count": len(matched_indicators),
                        "evidence_strength": "high" if pattern.confidence_score > 0.8 else "medium" if pattern.confidence_score > 0.6 else "low"
                    })
        
        # Sort by confidence score
        root_causes.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        return {
            "identified_root_causes": root_causes,
            "primary_root_cause": root_causes[0] if root_causes else None,
            "root_cause_count": len(root_causes),
            "confidence_distribution": self._analyze_confidence_distribution(root_causes),
            "all_indicators": indicators
        }
    
    async def _assess_comprehensive_impact(
        self,
        health_analysis: Dict[str, Any],
        log_analysis: Dict[str, Any],
        metrics_analysis: Dict[str, Any],
        dependency_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess comprehensive impact across all dimensions."""
        impact = {
            "business_impact": "unknown",
            "technical_impact": "unknown",
            "user_impact": "unknown",
            "operational_impact": "unknown",
            "impact_scope": {},
            "affected_capabilities": [],
            "severity_score": 0.0
        }
        
        severity_factors = []
        
        # Assess business impact from dependency analysis
        if isinstance(dependency_analysis, dict):
            immediate_impact = dependency_analysis.get("immediate_impact", {})
            business_impact = immediate_impact.get("business_impact", "low")
            impact["business_impact"] = business_impact
            
            if business_impact == "severe":
                severity_factors.append(0.9)
            elif business_impact == "high":
                severity_factors.append(0.7)
            elif business_impact == "medium":
                severity_factors.append(0.5)
            else:
                severity_factors.append(0.3)
            
            # Affected services
            affected_count = immediate_impact.get("affected_service_count", 0)
            impact["impact_scope"]["affected_services"] = affected_count
            
            if affected_count > 3:
                severity_factors.append(0.8)
            elif affected_count > 1:
                severity_factors.append(0.6)
        
        # Assess technical impact from health analysis
        if isinstance(health_analysis, dict):
            if "services" in health_analysis:
                unhealthy_services = []
                for service, analysis in health_analysis["services"].items():
                    if not analysis.get("basic_health", {}).get("is_healthy", True):
                        unhealthy_services.append(service)
                
                impact["impact_scope"]["unhealthy_services"] = len(unhealthy_services)
                impact["technical_impact"] = "high" if len(unhealthy_services) > 1 else "medium" if unhealthy_services else "low"
        
        # Assess operational impact from metrics
        if isinstance(metrics_analysis, dict):
            anomaly_analysis = metrics_analysis.get("anomaly_analysis", {})
            critical_anomalies = anomaly_analysis.get("severity_breakdown", {}).get("critical", 0)
            high_anomalies = anomaly_analysis.get("severity_breakdown", {}).get("high", 0)
            
            if critical_anomalies > 0:
                impact["operational_impact"] = "critical"
                severity_factors.append(0.9)
            elif high_anomalies > 0:
                impact["operational_impact"] = "high"
                severity_factors.append(0.7)
            else:
                impact["operational_impact"] = "medium"
                severity_factors.append(0.4)
        
        # Assess user impact
        if impact["business_impact"] in ["severe", "high"] or impact["technical_impact"] == "high":
            impact["user_impact"] = "high"
        elif impact["business_impact"] == "medium" or impact["technical_impact"] == "medium":
            impact["user_impact"] = "medium"
        else:
            impact["user_impact"] = "low"
        
        # Calculate overall severity score
        if severity_factors:
            impact["severity_score"] = round(sum(severity_factors) / len(severity_factors), 3)
        
        return impact
    
    async def _generate_intelligent_recommendations(
        self,
        root_cause_analysis: Dict[str, Any],
        impact_assessment: Dict[str, Any],
        dependency_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate prioritized, intelligent recommendations."""
        recommendations = []
        
        # Root cause specific recommendations
        primary_root_cause = root_cause_analysis.get("primary_root_cause")
        if primary_root_cause:
            cause_name = primary_root_cause["root_cause"]
            confidence = primary_root_cause["confidence_score"]
            
            # Generate specific recommendations based on root cause
            cause_recommendations = self._get_root_cause_recommendations(cause_name, confidence)
            recommendations.extend(cause_recommendations)
        
        # Impact-based recommendations
        severity_score = impact_assessment.get("severity_score", 0)
        if severity_score > 0.8:
            recommendations.append({
                "action": "Initiate incident response procedure",
                "priority": "critical",
                "category": "immediate_response",
                "estimated_time_minutes": 5,
                "description": "High severity incident detected - activate incident response team"
            })
        
        # Dependency-based recommendations
        if isinstance(dependency_analysis, dict):
            recovery_strategy = dependency_analysis.get("recovery_strategy", {})
            recovery_order = recovery_strategy.get("recovery_order", [])
            
            if recovery_order:
                recommendations.append({
                    "action": f"Follow recovery order: {' → '.join(recovery_order[:3])}",
                    "priority": "high",
                    "category": "recovery",
                    "estimated_time_minutes": recovery_strategy.get("total_estimated_time_minutes", 30),
                    "description": "Optimal service recovery sequence based on dependency analysis"
                })
        
        # Prioritize recommendations
        for i, rec in enumerate(recommendations):
            rec["execution_order"] = i + 1
            rec["confidence"] = self._calculate_recommendation_confidence(rec, root_cause_analysis)
        
        # Sort by priority and confidence
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: (priority_order.get(x["priority"], 4), -x["confidence"]))
        
        return recommendations
    
    def _get_root_cause_recommendations(self, cause_name: str, confidence: float) -> List[Dict[str, Any]]:
        """Get specific recommendations for a root cause."""
        recommendations_map = {
            "database_overload": [
                {
                    "action": "Check database connection pool configuration",
                    "priority": "high",
                    "category": "database",
                    "estimated_time_minutes": 10
                },
                {
                    "action": "Analyze slow queries and optimize database performance",
                    "priority": "medium",
                    "category": "optimization",
                    "estimated_time_minutes": 30
                }
            ],
            "memory_exhaustion": [
                {
                    "action": "Restart services to clear memory leaks",
                    "priority": "high",
                    "category": "immediate_action",
                    "estimated_time_minutes": 5
                },
                {
                    "action": "Increase memory allocation for affected services",
                    "priority": "medium",
                    "category": "scaling",
                    "estimated_time_minutes": 15
                }
            ],
            "network_connectivity": [
                {
                    "action": "Check network configuration and connectivity",
                    "priority": "high",
                    "category": "network",
                    "estimated_time_minutes": 10
                },
                {
                    "action": "Verify firewall rules and security groups",
                    "priority": "medium",
                    "category": "security",
                    "estimated_time_minutes": 15
                }
            ],
            "cascade_failure": [
                {
                    "action": "Implement circuit breaker pattern to prevent cascades",
                    "priority": "high",
                    "category": "resilience",
                    "estimated_time_minutes": 20
                },
                {
                    "action": "Isolate failed service to prevent further cascade",
                    "priority": "critical",
                    "category": "immediate_action",
                    "estimated_time_minutes": 5
                }
            ]
        }
        
        base_recommendations = recommendations_map.get(cause_name, [])
        
        # Adjust priority based on confidence
        for rec in base_recommendations:
            if confidence > 0.9 and rec["priority"] == "medium":
                rec["priority"] = "high"
            elif confidence < 0.7 and rec["priority"] == "high":
                rec["priority"] = "medium"
        
        return base_recommendations
    
    def _calculate_recommendation_confidence(
        self,
        recommendation: Dict[str, Any],
        root_cause_analysis: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a recommendation."""
        base_confidence = 0.7
        
        # Adjust based on root cause confidence
        primary_cause = root_cause_analysis.get("primary_root_cause")
        if primary_cause:
            cause_confidence = primary_cause.get("confidence_score", 0.5)
            base_confidence = (base_confidence + cause_confidence) / 2
        
        # Adjust based on recommendation category
        category_confidence = {
            "immediate_action": 0.9,
            "recovery": 0.8,
            "database": 0.7,
            "network": 0.6,
            "optimization": 0.5
        }
        
        category = recommendation.get("category", "unknown")
        category_boost = category_confidence.get(category, 0.5)
        
        return min(1.0, (base_confidence + category_boost) / 2)
    
    async def _assess_urgency(
        self,
        root_cause_analysis: Dict[str, Any],
        impact_assessment: Dict[str, Any],
        metrics_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess urgency level and response timeline."""
        urgency_factors = self.intelligence_rules["urgency_factors"]
        urgency_score = 0.0
        
        # Factor 1: Critical service count
        severity_score = impact_assessment.get("severity_score", 0)
        urgency_score += severity_score * urgency_factors["critical_service_count"]
        
        # Factor 2: Root cause confidence and severity
        primary_cause = root_cause_analysis.get("primary_root_cause")
        if primary_cause:
            cause_urgency = {
                "infrastructure_failure": 0.9,
                "cascade_failure": 0.8,
                "memory_exhaustion": 0.7,
                "database_overload": 0.6
            }
            cause_name = primary_cause["root_cause"]
            urgency_score += cause_urgency.get(cause_name, 0.5) * urgency_factors["cascade_severity"]
        
        # Factor 3: System resource usage
        if isinstance(metrics_analysis, dict):
            anomalies = metrics_analysis.get("anomaly_analysis", {})
            critical_anomalies = anomalies.get("severity_breakdown", {}).get("critical", 0)
            if critical_anomalies > 0:
                urgency_score += 0.9 * urgency_factors["system_resource_usage"]
        
        urgency_level = "low"
        response_time_minutes = 60
        
        if urgency_score > 0.8:
            urgency_level = "critical"
            response_time_minutes = 5
        elif urgency_score > 0.6:
            urgency_level = "high"
            response_time_minutes = 15
        elif urgency_score > 0.4:
            urgency_level = "medium"
            response_time_minutes = 30
        
        return {
            "urgency_level": urgency_level,
            "urgency_score": round(urgency_score, 3),
            "recommended_response_time_minutes": response_time_minutes,
            "escalation_required": urgency_score > 0.7,
            "immediate_action_required": urgency_score > 0.8
        }
    
    async def _generate_prevention_strategies(
        self,
        root_cause_analysis: Dict[str, Any],
        indicators: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate prevention strategies to avoid similar issues."""
        strategies = []
        
        primary_cause = root_cause_analysis.get("primary_root_cause")
        if primary_cause:
            cause_name = primary_cause["root_cause"]
            
            prevention_map = {
                "database_overload": [
                    {"strategy": "Implement database connection pooling", "timeframe": "short_term"},
                    {"strategy": "Set up database performance monitoring", "timeframe": "medium_term"},
                    {"strategy": "Consider database scaling or sharding", "timeframe": "long_term"}
                ],
                "memory_exhaustion": [
                    {"strategy": "Implement memory usage monitoring and alerting", "timeframe": "short_term"},
                    {"strategy": "Optimize application memory usage", "timeframe": "medium_term"},
                    {"strategy": "Implement auto-scaling based on memory usage", "timeframe": "long_term"}
                ],
                "cascade_failure": [
                    {"strategy": "Implement circuit breaker patterns", "timeframe": "short_term"},
                    {"strategy": "Add service mesh for better resilience", "timeframe": "medium_term"},
                    {"strategy": "Design for graceful degradation", "timeframe": "long_term"}
                ]
            }
            
            strategies.extend(prevention_map.get(cause_name, []))
        
        # General prevention strategies
        strategies.extend([
            {"strategy": "Enhance monitoring and alerting coverage", "timeframe": "short_term"},
            {"strategy": "Implement comprehensive health checks", "timeframe": "short_term"},
            {"strategy": "Regular disaster recovery testing", "timeframe": "medium_term"}
        ])
        
        return strategies
    
    async def _create_executive_summary(
        self,
        root_cause_analysis: Dict[str, Any],
        impact_assessment: Dict[str, Any],
        urgency_assessment: Dict[str, Any]
    ) -> str:
        """Create executive summary of the incident."""
        primary_cause = root_cause_analysis.get("primary_root_cause")
        
        if primary_cause:
            cause_desc = primary_cause["description"]
            confidence = primary_cause["confidence_score"]
            confidence_text = "high" if confidence > 0.8 else "medium" if confidence > 0.6 else "low"
        else:
            cause_desc = "Root cause analysis inconclusive"
            confidence_text = "low"
        
        business_impact = impact_assessment.get("business_impact", "unknown")
        urgency_level = urgency_assessment.get("urgency_level", "unknown")
        response_time = urgency_assessment.get("recommended_response_time_minutes", 60)
        
        summary = f"""
INCIDENT ANALYSIS SUMMARY

Root Cause: {cause_desc} (confidence: {confidence_text})
Business Impact: {business_impact.upper()}
Urgency Level: {urgency_level.upper()}
Recommended Response Time: {response_time} minutes

The incident requires {urgency_level} priority response with focus on {cause_desc.lower() if primary_cause else 'comprehensive diagnosis'}.
        """.strip()
        
        return summary
    
    async def _analyze_diagnostic_correlations(
        self,
        health_analysis: Dict[str, Any],
        log_analysis: Dict[str, Any],
        metrics_analysis: Dict[str, Any],
        dependency_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze correlations between different diagnostic sources."""
        correlations = {
            "health_log_correlation": 0.0,
            "metrics_dependency_correlation": 0.0,
            "cross_source_consistency": "unknown",
            "correlation_strength": "low"
        }
        
        # This is a simplified correlation analysis
        # In production, this would use more sophisticated correlation algorithms
        
        correlation_indicators = 0
        total_indicators = 0
        
        # Check health-log correlation
        if isinstance(health_analysis, dict) and isinstance(log_analysis, dict):
            total_indicators += 1
            # Simple correlation based on service health and error logs
            log_patterns = log_analysis.get("log_analysis", {}).get("pattern_matches", {})
            if log_patterns and any(not svc.get("basic_health", {}).get("is_healthy", True) 
                                  for svc in health_analysis.get("services", {}).values()):
                correlation_indicators += 1
        
        # Check metrics-dependency correlation
        if isinstance(metrics_analysis, dict) and isinstance(dependency_analysis, dict):
            total_indicators += 1
            metrics_anomalies = metrics_analysis.get("anomaly_analysis", {}).get("anomaly_count", 0)
            cascade_severity = dependency_analysis.get("cascade_analysis", {}).get("cascade_severity", "low")
            if metrics_anomalies > 0 and cascade_severity in ["high", "critical"]:
                correlation_indicators += 1
        
        if total_indicators > 0:
            correlation_score = correlation_indicators / total_indicators
            correlations["cross_source_consistency"] = "high" if correlation_score > 0.7 else "medium" if correlation_score > 0.3 else "low"
            correlations["correlation_strength"] = correlations["cross_source_consistency"]
        
        return correlations
    
    def _calculate_confidence_metrics(self, root_cause_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate confidence metrics for the analysis."""
        root_causes = root_cause_analysis.get("identified_root_causes", [])
        
        if not root_causes:
            return {"overall_confidence": 0.0, "confidence_level": "very_low"}
        
        # Calculate overall confidence
        total_confidence = sum(cause["confidence_score"] for cause in root_causes)
        avg_confidence = total_confidence / len(root_causes)
        
        # Weight by evidence strength
        high_confidence_causes = sum(1 for cause in root_causes if cause["confidence_score"] > 0.8)
        confidence_boost = high_confidence_causes * 0.1
        
        overall_confidence = min(1.0, avg_confidence + confidence_boost)
        
        confidence_level = "very_high" if overall_confidence > 0.9 else \
                          "high" if overall_confidence > 0.7 else \
                          "medium" if overall_confidence > 0.5 else \
                          "low" if overall_confidence > 0.3 else "very_low"
        
        return {
            "overall_confidence": round(overall_confidence, 3),
            "confidence_level": confidence_level,
            "root_cause_count": len(root_causes),
            "high_confidence_causes": high_confidence_causes
        }
    
    def _analyze_confidence_distribution(self, root_causes: List[Dict]) -> Dict[str, int]:
        """Analyze distribution of confidence levels."""
        distribution = {"high": 0, "medium": 0, "low": 0}
        
        for cause in root_causes:
            confidence = cause["confidence_score"]
            if confidence > 0.8:
                distribution["high"] += 1
            elif confidence > 0.6:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1
        
        return distribution
    
    async def _generate_next_steps(
        self,
        recommendations: List[Dict[str, Any]],
        urgency_assessment: Dict[str, Any]
    ) -> List[str]:
        """Generate immediate next steps."""
        next_steps = []
        
        urgency_level = urgency_assessment.get("urgency_level", "medium")
        
        if urgency_level == "critical":
            next_steps.extend([
                "🚨 IMMEDIATE: Activate incident response team",
                "📞 Notify stakeholders of critical incident",
                "🔧 Begin recovery procedures immediately"
            ])
        elif urgency_level == "high":
            next_steps.extend([
                "⚠️ HIGH PRIORITY: Investigate root cause immediately",
                "📋 Assign incident commander",
                "🔧 Implement immediate remediation steps"
            ])
        
        # Add top recommendations as next steps
        for i, rec in enumerate(recommendations[:3]):
            if rec.get("priority") in ["critical", "high"]:
                next_steps.append(f"🎯 Step {i+1}: {rec['action']}")
        
        if not next_steps:
            next_steps.extend([
                "📊 Continue monitoring system health",
                "🔍 Investigate potential root causes",
                "📋 Document findings for analysis"
            ])
        
        return next_steps


async def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Intelligence Synthesizer for Veris Memory Diagnostics")
    parser.add_argument("--health", required=True, help="Path to health analysis JSON file")
    parser.add_argument("--logs", required=True, help="Path to log analysis JSON file")
    parser.add_argument("--metrics", required=True, help="Path to metrics analysis JSON file")
    parser.add_argument("--dependencies", required=True, help="Path to dependency analysis JSON file")
    parser.add_argument("--alert-context", help="JSON string with alert context")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "summary"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    # Load analysis files
    try:
        with open(args.health, 'r') as f:
            health_analysis = json.load(f)
        with open(args.logs, 'r') as f:
            log_analysis = json.load(f)
        with open(args.metrics, 'r') as f:
            metrics_analysis = json.load(f)
        with open(args.dependencies, 'r') as f:
            dependency_analysis = json.load(f)
    except Exception as e:
        logger.error(f"Error loading analysis files: {e}")
        sys.exit(1)
    
    # Parse alert context
    alert_context = None
    if args.alert_context:
        try:
            alert_context = json.loads(args.alert_context)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid alert context JSON: {e}")
            sys.exit(1)
    
    # Synthesize intelligence
    synthesizer = IntelligenceSynthesizer()
    result = await synthesizer.synthesize_intelligence(
        health_analysis, log_analysis, metrics_analysis, dependency_analysis, alert_context
    )
    
    # Output results
    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        # Summary format
        summary = result["executive_summary"]
        root_cause = result["root_cause_analysis"]
        recommendations = result["prioritized_recommendations"]
        
        # Safely extract root cause information
        primary_root_cause = root_cause.get('primary_root_cause') if root_cause else None
        root_cause_desc = "No primary root cause identified"
        root_cause_confidence = 0.0
        
        if primary_root_cause:
            root_cause_desc = primary_root_cause.get('description', 'No description available')
            root_cause_confidence = primary_root_cause.get('confidence_score', 0.0)
        
        output = f"""
Intelligence Analysis Summary
=============================
{summary}

Root Cause Analysis:
{root_cause_desc}
Confidence: {root_cause_confidence:.3f}

Top Recommendations:
{chr(10).join(f"- {rec.get('action', 'No action specified')} (Priority: {rec.get('priority', 'unknown')})" for rec in recommendations[:5] if isinstance(rec, dict))}

Next Steps:
{chr(10).join(f"- {step}" for step in result.get('next_steps', [])[:5])}
"""
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Intelligence analysis saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())