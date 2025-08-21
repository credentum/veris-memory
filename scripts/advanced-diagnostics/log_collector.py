#!/usr/bin/env python3
"""
Intelligent Log Collector for Veris Memory Services

This module provides sophisticated log collection and analysis capabilities,
including pattern recognition, error correlation, and intelligent filtering
for Veris Memory monitoring.

Author: Claude Code Integration - Phase 2
Date: 2025-08-20
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Pattern
from collections import defaultdict, Counter
import argparse
import aiofiles

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LogPattern:
    """Definition of a log pattern to match."""
    
    def __init__(self, name: str, pattern: str, severity: str, description: str):
        self.name = name
        self.pattern: Pattern = re.compile(pattern, re.IGNORECASE)
        self.severity = severity  # "critical", "high", "medium", "low"
        self.description = description
        self.matches: List[Dict[str, Any]] = []


class LogEntry:
    """Represents a single log entry."""
    
    def __init__(self, timestamp: str, level: str, message: str, source: str, line_number: int):
        self.timestamp = timestamp
        self.level = level
        self.message = message
        self.source = source
        self.line_number = line_number
        self.parsed_timestamp: Optional[datetime] = self._parse_timestamp(timestamp)
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        formats = [
            "%Y-%m-%d %H:%M:%S,%f",  # Python logging format
            "%Y-%m-%d %H:%M:%S.%f",  # Alternative format
            "%Y-%m-%dT%H:%M:%S.%fZ", # ISO format
            "%Y-%m-%d %H:%M:%S",     # Simple format
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.strip(), fmt)
            except ValueError:
                continue
        
        return None


class LogCollector:
    """
    Intelligent log collector and analyzer for Veris Memory services.
    
    Provides capabilities for:
    - Collecting logs from multiple sources
    - Pattern matching and error detection
    - Correlation analysis across services
    - Temporal analysis and trending
    - Intelligent filtering and summarization
    """
    
    def __init__(self):
        """Initialize the log collector."""
        self.service_logs = {
            "mcp_server": "/var/log/veris-memory/mcp.log",
            "rest_api": "/var/log/veris-memory/api.log", 
            "sentinel": "/var/log/veris-memory/sentinel.log",
            "dashboard": "/var/log/veris-memory/dashboard.log"
        }
        
        self.log_patterns = self._initialize_patterns()
        self.collected_logs: Dict[str, List[LogEntry]] = defaultdict(list)
    
    def _initialize_patterns(self) -> List[LogPattern]:
        """Initialize log patterns for detection."""
        patterns = [
            # Critical Database Issues
            LogPattern(
                "database_connection_failure",
                r"(connection.*refused|connection.*timeout|database.*unavailable|connection.*lost)",
                "critical",
                "Database connection issues detected"
            ),
            LogPattern(
                "database_deadlock",
                r"(deadlock.*detected|lock.*timeout|transaction.*deadlock)",
                "high",
                "Database deadlock or locking issues"
            ),
            LogPattern(
                "slow_query",
                r"(slow.*query|query.*timeout|execution.*time.*exceeded)",
                "medium",
                "Slow database query performance"
            ),
            
            # Memory Issues
            LogPattern(
                "out_of_memory",
                r"(out.*of.*memory|memory.*allocation.*failed|cannot.*allocate.*memory)",
                "critical",
                "Memory allocation failures"
            ),
            LogPattern(
                "memory_leak",
                r"(memory.*leak|heap.*overflow|memory.*usage.*high)",
                "high",
                "Potential memory leak indicators"
            ),
            LogPattern(
                "gc_overhead",
                r"(gc.*overhead.*limit|garbage.*collection.*time|gc.*frequency.*high)",
                "medium",
                "Garbage collection performance issues"
            ),
            
            # Network Issues
            LogPattern(
                "network_timeout",
                r"(network.*timeout|connection.*timed.*out|read.*timeout)",
                "high",
                "Network connectivity timeouts"
            ),
            LogPattern(
                "connection_refused",
                r"(connection.*refused|port.*unreachable|service.*unavailable)",
                "high",
                "Service connection failures"
            ),
            LogPattern(
                "ssl_errors",
                r"(ssl.*error|certificate.*error|tls.*handshake.*failed)",
                "medium",
                "SSL/TLS connection issues"
            ),
            
            # Application Errors
            LogPattern(
                "authentication_failure",
                r"(authentication.*failed|unauthorized.*access|invalid.*credentials)",
                "high",
                "Authentication and authorization failures"
            ),
            LogPattern(
                "api_errors",
                r"(internal.*server.*error|500.*error|api.*error|request.*failed)",
                "high",
                "API request failures"
            ),
            LogPattern(
                "validation_errors",
                r"(validation.*error|invalid.*input|schema.*validation.*failed)",
                "medium",
                "Input validation failures"
            ),
            
            # Performance Issues
            LogPattern(
                "high_latency",
                r"(high.*latency|response.*time.*exceeded|slow.*response)",
                "medium",
                "Performance degradation indicators"
            ),
            LogPattern(
                "queue_overflow",
                r"(queue.*full|buffer.*overflow|capacity.*exceeded)",
                "high",
                "Queue or buffer overflow issues"
            ),
            
            # Security Issues
            LogPattern(
                "security_violations",
                r"(security.*violation|suspicious.*activity|attack.*detected)",
                "critical",
                "Security-related events"
            ),
            LogPattern(
                "rate_limiting",
                r"(rate.*limit.*exceeded|too.*many.*requests|throttling)",
                "medium",
                "Rate limiting activations"
            ),
            
            # System Issues
            LogPattern(
                "disk_space",
                r"(disk.*full|no.*space.*left|storage.*capacity.*exceeded)",
                "critical",
                "Disk space issues"
            ),
            LogPattern(
                "service_restart",
                r"(service.*restarted|process.*died|unexpected.*shutdown)",
                "high",
                "Service restart or crash events"
            )
        ]
        
        return patterns
    
    async def collect_relevant_logs(
        self, 
        services: List[str] = None,
        time_window_minutes: int = 30,
        alert_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Collect and analyze logs relevant to the current alert.
        
        Args:
            services: List of services to collect logs from (None = all)
            time_window_minutes: Time window for log collection
            alert_context: Context from the triggering alert
            
        Returns:
            Dict containing collected logs and analysis
        """
        if services is None:
            services = list(self.service_logs.keys())
        
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        logger.info(f"Collecting logs from {len(services)} services for last {time_window_minutes} minutes")
        
        # Collect logs from all specified services
        collection_tasks = [
            self._collect_service_logs(service, cutoff_time)
            for service in services
        ]
        
        results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        
        # Process results
        for service, result in zip(services, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to collect logs from {service}: {result}")
                self.collected_logs[service] = []
            else:
                self.collected_logs[service] = result
        
        # Analyze collected logs
        analysis = await self._analyze_collected_logs(alert_context)
        
        return {
            "collection_timestamp": datetime.now().isoformat(),
            "time_window_minutes": time_window_minutes,
            "services_analyzed": services,
            "alert_context": alert_context,
            "log_analysis": analysis,
            "raw_logs": self._serialize_logs()
        }
    
    async def _collect_service_logs(self, service: str, cutoff_time: datetime) -> List[LogEntry]:
        """Collect logs for a specific service."""
        log_file = self.service_logs.get(service)
        if not log_file:
            logger.warning(f"No log file configured for service: {service}")
            return []
        
        if not os.path.exists(log_file):
            logger.warning(f"Log file not found: {log_file}")
            return []
        
        try:
            entries = []
            async with aiofiles.open(log_file, 'r') as f:
                line_number = 0
                async for line in f:
                    line_number += 1
                    line = line.strip()
                    if not line:
                        continue
                    
                    entry = self._parse_log_entry(line, service, line_number)
                    if entry and entry.parsed_timestamp and entry.parsed_timestamp >= cutoff_time:
                        entries.append(entry)
            
            logger.info(f"Collected {len(entries)} log entries from {service}")
            return entries
            
        except Exception as e:
            logger.error(f"Error reading log file {log_file}: {e}")
            return []
    
    def _parse_log_entry(self, line: str, service: str, line_number: int) -> Optional[LogEntry]:
        """Parse a single log entry."""
        # Common log formats to try
        formats = [
            # Python logging format: "2024-08-20 15:30:45,123 - INFO - message"
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.+)$",
            # Alternative format: "2024-08-20 15:30:45.123 INFO message"
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (\w+) (.+)$",
            # ISO format: "2024-08-20T15:30:45.123Z INFO message"
            r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z) (\w+) (.+)$",
            # Simple format: "2024-08-20 15:30:45 INFO message"
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$"
        ]
        
        for pattern in formats:
            match = re.match(pattern, line)
            if match:
                timestamp, level, message = match.groups()
                return LogEntry(timestamp, level, message, service, line_number)
        
        # If no format matches, treat as generic entry
        return LogEntry("unknown", "INFO", line, service, line_number)
    
    async def _analyze_collected_logs(self, alert_context: Optional[Dict]) -> Dict[str, Any]:
        """Analyze collected logs for patterns and insights."""
        analysis = {
            "total_entries": sum(len(entries) for entries in self.collected_logs.values()),
            "pattern_matches": {},
            "error_frequency": {},
            "temporal_analysis": {},
            "correlation_analysis": {},
            "alert_correlation": {},
            "recommendations": []
        }
        
        # Pattern matching analysis
        for pattern in self.log_patterns:
            pattern.matches = []  # Reset matches
            
            for service, entries in self.collected_logs.items():
                for entry in entries:
                    if pattern.pattern.search(entry.message):
                        pattern.matches.append({
                            "service": service,
                            "timestamp": entry.timestamp,
                            "level": entry.level,
                            "message": entry.message,
                            "line_number": entry.line_number
                        })
            
            if pattern.matches:
                analysis["pattern_matches"][pattern.name] = {
                    "pattern_name": pattern.name,
                    "description": pattern.description,
                    "severity": pattern.severity,
                    "match_count": len(pattern.matches),
                    "matches": pattern.matches[:10],  # Limit to first 10 matches
                    "services_affected": list(set(match["service"] for match in pattern.matches))
                }
        
        # Error frequency analysis
        analysis["error_frequency"] = self._analyze_error_frequency()
        
        # Temporal analysis
        analysis["temporal_analysis"] = self._analyze_temporal_patterns()
        
        # Correlation analysis
        analysis["correlation_analysis"] = await self._analyze_correlations()
        
        # Alert-specific correlation
        if alert_context:
            analysis["alert_correlation"] = await self._correlate_with_alert(alert_context)
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_log_recommendations(analysis)
        
        return analysis
    
    def _analyze_error_frequency(self) -> Dict[str, Any]:
        """Analyze frequency of different error types."""
        error_counts = Counter()
        level_counts = Counter()
        service_error_counts = defaultdict(Counter)
        
        for service, entries in self.collected_logs.items():
            for entry in entries:
                level_counts[entry.level] += 1
                service_error_counts[service][entry.level] += 1
                
                if entry.level in ["ERROR", "CRITICAL", "FATAL"]:
                    error_counts[f"{service}:{entry.level}"] += 1
        
        return {
            "error_counts_by_type": dict(error_counts),
            "log_levels_distribution": dict(level_counts),
            "errors_by_service": {
                service: dict(counts) for service, counts in service_error_counts.items()
            },
            "total_errors": sum(count for level, count in level_counts.items() 
                              if level in ["ERROR", "CRITICAL", "FATAL"])
        }
    
    def _analyze_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze temporal patterns in log entries."""
        timestamps = []
        for entries in self.collected_logs.values():
            for entry in entries:
                if entry.parsed_timestamp:
                    timestamps.append(entry.parsed_timestamp)
        
        if not timestamps:
            return {"note": "No parseable timestamps found"}
        
        timestamps.sort()
        
        # Calculate log frequency over time
        if len(timestamps) > 1:
            time_span = (timestamps[-1] - timestamps[0]).total_seconds()
            log_frequency = len(timestamps) / max(time_span, 1) * 60  # logs per minute
        else:
            log_frequency = 0
        
        # Find time periods with high activity
        minute_buckets = defaultdict(int)
        for ts in timestamps:
            minute_key = ts.strftime("%Y-%m-%d %H:%M")
            minute_buckets[minute_key] += 1
        
        # Find busiest minutes
        busiest_minutes = sorted(minute_buckets.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_log_entries": len(timestamps),
            "time_span_minutes": time_span / 60 if len(timestamps) > 1 else 0,
            "average_log_frequency_per_minute": log_frequency,
            "first_entry": timestamps[0].isoformat() if timestamps else None,
            "last_entry": timestamps[-1].isoformat() if timestamps else None,
            "busiest_minutes": [{"time": time, "count": count} for time, count in busiest_minutes]
        }
    
    async def _analyze_correlations(self) -> Dict[str, Any]:
        """Analyze correlations between different services and error types."""
        correlations = {}
        
        # Find simultaneous errors across services
        error_timestamps = defaultdict(list)
        
        for service, entries in self.collected_logs.items():
            for entry in entries:
                if entry.level in ["ERROR", "CRITICAL", "FATAL"] and entry.parsed_timestamp:
                    error_timestamps[service].append(entry.parsed_timestamp)
        
        # Look for errors within 1 minute of each other
        correlation_window = timedelta(minutes=1)
        correlated_errors = []
        
        services = list(error_timestamps.keys())
        for i, service1 in enumerate(services):
            for j, service2 in enumerate(services[i+1:], i+1):
                for ts1 in error_timestamps[service1]:
                    for ts2 in error_timestamps[service2]:
                        if abs(ts1 - ts2) <= correlation_window:
                            correlated_errors.append({
                                "service1": service1,
                                "service2": service2,
                                "timestamp1": ts1.isoformat(),
                                "timestamp2": ts2.isoformat(),
                                "time_difference_seconds": abs((ts1 - ts2).total_seconds())
                            })
        
        correlations["simultaneous_errors"] = correlated_errors[:10]  # Limit results
        correlations["correlation_count"] = len(correlated_errors)
        
        return correlations
    
    async def _correlate_with_alert(self, alert_context: Dict) -> Dict[str, Any]:
        """Correlate log entries with the specific alert that triggered analysis."""
        correlation = {
            "alert_time": alert_context.get("timestamp", "unknown"),
            "alert_check_id": alert_context.get("check_id", "unknown"),
            "relevant_logs": [],
            "time_proximity_matches": [],
            "keyword_matches": []
        }
        
        # Parse alert timestamp
        alert_time = None
        if alert_context.get("timestamp"):
            try:
                alert_time = datetime.fromisoformat(alert_context["timestamp"].replace("Z", "+00:00"))
            except:
                pass
        
        # Find logs around alert time
        if alert_time:
            time_window = timedelta(minutes=5)  # 5 minutes before/after alert
            
            for service, entries in self.collected_logs.items():
                for entry in entries:
                    if entry.parsed_timestamp and abs(entry.parsed_timestamp - alert_time) <= time_window:
                        correlation["time_proximity_matches"].append({
                            "service": service,
                            "timestamp": entry.timestamp,
                            "level": entry.level,
                            "message": entry.message,
                            "time_difference_seconds": abs((entry.parsed_timestamp - alert_time).total_seconds())
                        })
        
        # Find logs with keywords related to the alert
        alert_keywords = []
        check_id = alert_context.get("check_id", "")
        if "health" in check_id.lower():
            alert_keywords.extend(["health", "status", "endpoint", "response"])
        elif "security" in check_id.lower():
            alert_keywords.extend(["security", "auth", "permission", "unauthorized"])
        elif "firewall" in check_id.lower():
            alert_keywords.extend(["firewall", "ufw", "iptables", "blocked"])
        
        for service, entries in self.collected_logs.items():
            for entry in entries:
                for keyword in alert_keywords:
                    if keyword.lower() in entry.message.lower():
                        correlation["keyword_matches"].append({
                            "service": service,
                            "timestamp": entry.timestamp,
                            "level": entry.level,
                            "message": entry.message,
                            "keyword": keyword
                        })
                        break
        
        return correlation
    
    def _generate_log_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on log analysis."""
        recommendations = []
        
        # Check for critical patterns
        pattern_matches = analysis.get("pattern_matches", {})
        critical_patterns = [name for name, data in pattern_matches.items() 
                           if data["severity"] == "critical"]
        
        if critical_patterns:
            recommendations.append(f"🚨 Critical issues detected: {', '.join(critical_patterns)}")
            recommendations.append("🔧 Immediate investigation required for critical log patterns")
        
        # Check error frequency
        error_frequency = analysis.get("error_frequency", {})
        total_errors = error_frequency.get("total_errors", 0)
        
        if total_errors > 10:
            recommendations.append(f"⚠️ High error count detected: {total_errors} errors in time window")
            recommendations.append("🔧 Review error logs and identify root causes")
        
        # Check correlation patterns
        correlation = analysis.get("correlation_analysis", {})
        correlation_count = correlation.get("correlation_count", 0)
        
        if correlation_count > 3:
            recommendations.append(f"🔗 Service error correlations detected: {correlation_count} instances")
            recommendations.append("🔧 Investigate cascade failures between services")
        
        # Check for specific high-impact patterns
        if "database_connection_failure" in pattern_matches:
            recommendations.append("🗄️ Database connectivity issues detected")
            recommendations.append("🔧 Check database server status and connection pool configuration")
        
        if "out_of_memory" in pattern_matches:
            recommendations.append("💾 Memory allocation failures detected")
            recommendations.append("🔧 Check system memory usage and consider increasing allocation")
        
        if not recommendations:
            recommendations.append("✅ No critical issues found in log analysis")
            recommendations.append("📊 Continue monitoring for patterns")
        
        return recommendations
    
    def _serialize_logs(self) -> Dict[str, List[Dict]]:
        """Serialize collected logs for output."""
        serialized = {}
        
        for service, entries in self.collected_logs.items():
            serialized[service] = [
                {
                    "timestamp": entry.timestamp,
                    "level": entry.level,
                    "message": entry.message,
                    "line_number": entry.line_number
                }
                for entry in entries[:50]  # Limit to 50 entries per service
            ]
        
        return serialized


async def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Intelligent Log Collector for Veris Memory")
    parser.add_argument("--services", help="Comma-separated list of services to analyze")
    parser.add_argument("--time-window", type=int, default=30, help="Time window in minutes")
    parser.add_argument("--alert-context", help="JSON string with alert context")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["json", "summary"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    # Parse services
    services = None
    if args.services:
        services = [s.strip() for s in args.services.split(",")]
    
    # Parse alert context
    alert_context = None
    if args.alert_context:
        try:
            alert_context = json.loads(args.alert_context)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid alert context JSON: {e}")
            sys.exit(1)
    
    # Collect and analyze logs
    collector = LogCollector()
    result = await collector.collect_relevant_logs(services, args.time_window, alert_context)
    
    # Output results
    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        # Summary format
        analysis = result["log_analysis"]
        output = f"""
Log Analysis Summary
====================
Time Window: {result['time_window_minutes']} minutes
Total Log Entries: {analysis['total_entries']}
Services Analyzed: {', '.join(result['services_analyzed'])}

Pattern Matches:
{chr(10).join(f"- {name}: {data['match_count']} matches ({data['severity']})" 
              for name, data in analysis['pattern_matches'].items())}

Error Summary:
Total Errors: {analysis['error_frequency'].get('total_errors', 0)}

Recommendations:
{chr(10).join(f"- {rec}" for rec in analysis['recommendations'])}
"""
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Log analysis saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    asyncio.run(main())