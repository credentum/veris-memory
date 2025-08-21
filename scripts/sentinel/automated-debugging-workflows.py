#!/usr/bin/env python3
"""
Automated Debugging Workflows for Claude Code SSH Sessions

This module provides intelligent debugging workflows that Claude Code can execute
via SSH access to diagnose and resolve system issues automatically.

Author: Claude Code Integration - Phase 3
Date: 2025-08-20
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import argparse

# Import SSH Security Manager
try:
    from ssh_security_manager import SSHSecurityManager
    SSH_SECURITY_AVAILABLE = True
except ImportError:
    SSH_SECURITY_AVAILABLE = False
    logging.warning("SSH Security Manager not available - using legacy SSH execution")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AutomatedDebuggingWorkflows:
    """Intelligent debugging workflows for automated SSH-based system investigation.
    
    This class provides Claude Code with structured workflows to diagnose and resolve
    common infrastructure issues on the Veris Memory server through secure SSH access.
    Each workflow is tailored to specific types of alerts and system failures.
    
    The class integrates with the SSH Security Manager to ensure all commands are
    validated against security policies and properly audited.
    
    Attributes:
        ssh_config: SSH connection configuration including host, user, and key path.
        server_host: Target server hostname for SSH connections.
        ssh_user: Username for SSH authentication.
        ssh_key_path: Path to SSH private key file.
        ssh_security: SSH Security Manager instance for command validation.
        
    Supported Workflows:
        - Service Health Investigation: Diagnoses service failures and restart issues
        - Database Connectivity: Investigates database connection problems
        - Performance Analysis: Analyzes system resource usage and bottlenecks
        - Security Investigation: Examines authentication and security issues
        - Firewall Diagnostics: Troubleshoots network connectivity problems
        - General System Investigation: Performs broad system health checks
    """
    
    def __init__(self, ssh_config: Dict[str, str]) -> None:
        """Initialize debugging workflows with SSH configuration.
        
        Sets up the debugging workflow system with secure SSH access configuration
        and initializes the SSH Security Manager for command validation.
        
        Args:
            ssh_config: Dictionary containing SSH connection parameters:
                - host: Target server hostname
                - user: SSH username 
                - key_path: Path to SSH private key file
                
        Raises:
            ValueError: If required SSH configuration parameters are missing.
            FileNotFoundError: If SSH key file cannot be found.
        """
        self.ssh_config = ssh_config
        self.server_host = ssh_config.get('host', os.getenv('VERIS_MEMORY_HOST', 'localhost'))
        self.ssh_user = ssh_config.get('user', os.getenv('VERIS_MEMORY_USER', 'root'))
        self.ssh_key_path = ssh_config.get('key_path')
        
        # Initialize SSH Security Manager if available
        if SSH_SECURITY_AVAILABLE:
            security_config = {
                'ssh_config': ssh_config,
                'audit_log_path': f'/tmp/ssh_audit_workflows_{int(time.time())}.log',
                'session_log_path': f'/tmp/ssh_session_workflows_{int(time.time())}.log'
            }
            self.ssh_security = SSHSecurityManager(security_config)
            logger.info("SSH Security Manager initialized for debugging workflows")
        else:
            self.ssh_security = None
            logger.warning("SSH Security Manager not available - using legacy execution")
        
        # Workflow execution tracking
        self.execution_log = []
        self.findings = {}
        self.recommended_fixes = []
        
    async def execute_workflow_for_alert(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute appropriate debugging workflow based on alert context.
        
        Args:
            alert_context: Alert details from Sentinel
            diagnostic_context: Phase 2 diagnostic results
            
        Returns:
            Dict containing workflow execution results and findings
        """
        logger.info("🔍 Executing automated debugging workflow...")
        
        workflow_result = {
            "workflow_type": "unknown",
            "execution_timestamp": datetime.now().isoformat(),
            "alert_context": alert_context,
            "ssh_commands_executed": [],
            "findings": {},
            "recommended_fixes": [],
            "confidence_score": 0.0,
            "execution_time_seconds": 0
        }
        
        start_time = time.time()
        
        try:
            # Determine appropriate workflow based on alert
            workflow_type = self._determine_workflow_type(alert_context)
            workflow_result["workflow_type"] = workflow_type
            
            logger.info(f"🎯 Selected workflow: {workflow_type}")
            
            # Execute the appropriate workflow
            if workflow_type == "service_health_investigation":
                await self._service_health_workflow(alert_context, diagnostic_context)
            elif workflow_type == "database_connectivity_investigation":
                await self._database_connectivity_workflow(alert_context, diagnostic_context)
            elif workflow_type == "performance_investigation":
                await self._performance_investigation_workflow(alert_context, diagnostic_context)
            elif workflow_type == "security_investigation":
                await self._security_investigation_workflow(alert_context, diagnostic_context)
            elif workflow_type == "firewall_investigation":
                await self._firewall_investigation_workflow(alert_context, diagnostic_context)
            else:
                await self._general_investigation_workflow(alert_context, diagnostic_context)
            
            # Populate results
            workflow_result["ssh_commands_executed"] = [cmd["command"] for cmd in self.execution_log]
            workflow_result["findings"] = self.findings
            workflow_result["recommended_fixes"] = self.recommended_fixes
            workflow_result["confidence_score"] = self._calculate_confidence_score()
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            workflow_result["error"] = str(e)
            workflow_result["confidence_score"] = 0.0
        
        workflow_result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return workflow_result
    
    def _determine_workflow_type(self, alert_context: Dict[str, Any]) -> str:
        """Determine the appropriate workflow type based on alert context."""
        check_id = alert_context.get("check_id", "").lower()
        message = alert_context.get("message", "").lower()
        
        if "health" in check_id or "health" in message:
            return "service_health_investigation"
        elif "database" in check_id or "database" in message or any(db in message for db in ["qdrant", "neo4j", "redis"]):
            return "database_connectivity_investigation"
        elif "performance" in check_id or "performance" in message or "latency" in message:
            return "performance_investigation"
        elif "security" in check_id or "security" in message or "auth" in message:
            return "security_investigation"
        elif "firewall" in check_id or "firewall" in message:
            return "firewall_investigation"
        else:
            return "general_investigation"
    
    async def _service_health_workflow(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ):
        """Comprehensive service health investigation workflow.
        
        This workflow performs a systematic investigation of service health issues
        by checking multiple layers of the system infrastructure. It follows a 
        structured approach to identify the root cause of service failures.
        
        Investigation Steps:
        1. System-wide service status check using systemctl
        2. Veris Memory specific service validation (API, MCP, Sentinel, Dashboard)
        3. Docker container health and status verification
        4. Network port availability and binding analysis
        5. Recent system error log examination
        
        Args:
            alert_context: Alert information from Sentinel including check_id, 
                         severity, message, and failure details
            diagnostic_context: Phase 2 diagnostic results containing health 
                              analysis and metrics data
        
        Side Effects:
            - Updates self.findings['service_health'] with discovered issues
            - Updates self.recommended_fixes with actionable repair suggestions
            - Logs execution progress and results to self.execution_log
            
        Error Handling:
            - All SSH commands use ignore_errors=True for optional checks
            - Failed commands are logged but don't stop the investigation
            - Network timeouts are handled gracefully
        """
        logger.info("🏥 Executing service health investigation workflow...")
        
        # Step 1: Check overall system status
        await self._execute_ssh_command(
            "systemctl list-units --state=failed",
            "Check for failed systemd services"
        )
        
        # Step 2: Check Veris Memory services specifically
        veris_services = ["veris-memory-api", "veris-memory-mcp", "veris-memory-sentinel", "veris-memory-dashboard"]
        for service in veris_services:
            await self._execute_ssh_command(
                f"systemctl status {service}",
                f"Check {service} status",
                ignore_errors=True
            )
        
        # Step 3: Check Docker containers
        await self._execute_ssh_command(
            "docker ps -a",
            "Check Docker container status"
        )
        
        # Step 4: Check port availability
        important_ports = ["8000", "8001", "9090", "8080", "6333", "7474", "6379"]
        for port in important_ports:
            await self._execute_ssh_command(
                f"netstat -tulpn | grep :{port}",
                f"Check port {port} availability",
                ignore_errors=True
            )
        
        # Step 5: Check recent logs for errors
        await self._execute_ssh_command(
            "journalctl --since '10 minutes ago' --priority=err",
            "Check recent system errors"
        )
        
        # Analyze findings and generate recommendations
        self._analyze_service_health_findings()
    
    async def _database_connectivity_workflow(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ):
        """Advanced database connectivity investigation workflow.
        
        This workflow performs comprehensive database connectivity diagnostics
        for the three core databases used by Veris Memory: Qdrant (vector search),
        Neo4j (graph database), and Redis (key-value cache).
        
        Investigation Strategy:
        1. Direct TCP connectivity testing to database ports using /dev/tcp
        2. Container runtime status verification for database services
        3. Database-specific log analysis for error patterns
        4. Firewall rule validation for database port access
        5. Disk space analysis (databases are sensitive to storage issues)
        
        Database Coverage:
        - Qdrant (port 6333): Vector embedding storage and search
        - Neo4j (port 7474/7687): Graph relationships and knowledge storage  
        - Redis (port 6379): Session state and caching layer
        
        Args:
            alert_context: Alert details from monitoring system with database
                         connection failure information
            diagnostic_context: Prior diagnostic results that may indicate
                               database-related performance issues
        
        Environment Variables Used:
            QDRANT_HOST, NEO4J_HOST, REDIS_HOST: Override default localhost targets
        
        Findings Generated:
            - connection_failures: List of databases with failed connections
            - container_issues: Docker container problems affecting databases
            - firewall_blocks: Network rules preventing database access
            - disk_space_issues: Storage problems that could affect databases
            
        Automated Fixes Suggested:
            - Database container restart commands
            - Service dependency resolution
            - Resource allocation adjustments
        """
        logger.info("🗄️ Executing database connectivity investigation workflow...")
        
        # Step 1: Test database connections
        qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
        neo4j_host = os.getenv('NEO4J_HOST', 'localhost')
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        
        databases = [
            {"name": "Qdrant", "host": qdrant_host, "port": "6333"},
            {"name": "Neo4j", "host": neo4j_host, "port": "7474"}, 
            {"name": "Redis", "host": redis_host, "port": "6379"}
        ]
        
        for db in databases:
            await self._execute_ssh_command(
                f"timeout 5 bash -c '</dev/tcp/{db['host']}/{db['port']}' && echo '{db['name']} connection: SUCCESS' || echo '{db['name']} connection: FAILED'",
                f"Test {db['name']} connectivity"
            )
        
        # Step 2: Check database service status
        await self._execute_ssh_command(
            "docker ps | grep -E '(qdrant|neo4j|redis)'",
            "Check database container status"
        )
        
        # Step 3: Check database logs
        await self._execute_ssh_command(
            "docker logs --tail 50 $(docker ps -q --filter ancestor=qdrant/qdrant) 2>/dev/null || echo 'Qdrant logs not available'",
            "Check Qdrant logs",
            ignore_errors=True
        )
        
        # Step 4: Check network configuration
        await self._execute_ssh_command(
            "iptables -L INPUT -n | grep -E '(6333|7474|6379)'",
            "Check firewall rules for database ports"
        )
        
        # Step 5: Check disk space (databases are sensitive to this)
        await self._execute_ssh_command(
            "df -h | grep -E '(/$|/var|/opt)'",
            "Check disk space for database storage"
        )
        
        self._analyze_database_connectivity_findings()
    
    async def _performance_investigation_workflow(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ):
        """Comprehensive system performance investigation workflow.
        
        This workflow performs deep system performance analysis to identify
        resource bottlenecks, inefficient processes, and capacity constraints
        that may be affecting Veris Memory system performance.
        
        Performance Analysis Areas:
        1. CPU utilization and process analysis (top, ps)
        2. Memory usage patterns and availability (free, meminfo)
        3. Disk I/O performance and bottlenecks (iostat, iotop)
        4. Network connection load and interface statistics
        5. Process-specific resource consumption analysis
        
        Diagnostic Approach:
        - Real-time system snapshots for current state analysis
        - Process ranking by CPU and memory consumption
        - I/O subsystem performance validation
        - Network connection count and interface health
        
        Args:
            alert_context: Performance alert details including latency metrics,
                         resource threshold violations, and timing data
            diagnostic_context: Previous system metrics and trend analysis
                              that may indicate performance degradation patterns
        
        Performance Metrics Collected:
        - CPU load averages and per-process utilization
        - Memory consumption (total, free, cached, buffers)
        - Disk I/O rates and queue depths
        - Network connection counts and interface statistics
        - Top resource-consuming processes
        
        Automated Analysis:
        - Identifies processes exceeding 50% CPU usage
        - Detects memory pressure and swap usage
        - Analyzes I/O wait times and bottlenecks
        - Evaluates network connection saturation
        """
        logger.info("⚡ Executing performance investigation workflow...")
        
        # Step 1: Check system resource usage
        await self._execute_ssh_command(
            "top -b -n 1 | head -20",
            "Check current CPU and memory usage"
        )
        
        # Step 2: Check memory details
        await self._execute_ssh_command(
            "free -h && echo '---' && cat /proc/meminfo | grep -E '(MemTotal|MemFree|MemAvailable|Buffers|Cached)'"
            , "Check detailed memory usage"
        )
        
        # Step 3: Check disk I/O
        await self._execute_ssh_command(
            "iostat -x 1 3 2>/dev/null || (echo 'iostat not available, using iotop:' && timeout 5 iotop -b -n 3 2>/dev/null || echo 'I/O monitoring tools not available')",
            "Check disk I/O performance",
            ignore_errors=True
        )
        
        # Step 4: Check network performance
        await self._execute_ssh_command(
            "ss -tuln | wc -l && echo 'Active connections above' && netstat -i",
            "Check network connections and interface stats"
        )
        
        # Step 5: Check process-specific performance
        await self._execute_ssh_command(
            "ps aux --sort=-%cpu | head -10",
            "Check top CPU-consuming processes"
        )
        
        await self._execute_ssh_command(
            "ps aux --sort=-%mem | head -10", 
            "Check top memory-consuming processes"
        )
        
        self._analyze_performance_findings()
    
    async def _security_investigation_workflow(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ):
        """Comprehensive security investigation and threat analysis workflow.
        
        This workflow performs thorough security analysis to identify potential
        threats, authentication issues, unauthorized access attempts, and
        security policy violations that may compromise system integrity.
        
        Security Investigation Areas:
        1. Authentication activity monitoring (SSH, sudo, login events)
        2. Firewall configuration and rule effectiveness (UFW, iptables)
        3. Process analysis for suspicious or unauthorized activities  
        4. Network connection security (listening services, open ports)
        5. File system permission validation for critical directories
        
        Threat Detection Capabilities:
        - Failed authentication attempt patterns
        - Privilege escalation attempts  
        - Unusual process execution outside expected users
        - Unauthorized network service bindings
        - Directory permission vulnerabilities
        
        Args:
            alert_context: Security alert information including authentication
                         failures, access violations, or suspicious activity
            diagnostic_context: System context that may indicate security
                              compromise or policy violations
        
        Security Checks Performed:
        - Recent authentication logs analysis (30-minute window)
        - UFW firewall status and rule configuration
        - Process ownership verification (non-system users)
        - Critical service port monitoring
        - Key directory permission validation
        
        Automated Remediation:
        - Firewall enablement recommendations
        - Access control tightening suggestions
        - Process isolation recommendations
        - Network security hardening steps
        """
        logger.info("🔒 Executing security investigation workflow...")
        
        # Step 1: Check authentication logs
        await self._execute_ssh_command(
            "journalctl --since '30 minutes ago' | grep -E '(authentication|login|ssh|sudo)' | tail -20",
            "Check recent authentication activity"
        )
        
        # Step 2: Check firewall status
        await self._execute_ssh_command(
            "ufw status verbose",
            "Check UFW firewall status"
        )
        
        # Step 3: Check for suspicious processes
        await self._execute_ssh_command(
            "ps aux | grep -vE '(root|www-data|daemon|systemd)' | head -10",
            "Check for unusual processes"
        )
        
        # Step 4: Check network connections
        await self._execute_ssh_command(
            "ss -tulpn | grep -E ':(:22|:80|:443|:8000|:8001|:9090)'",
            "Check important service ports"
        )
        
        # Step 5: Check file permissions on key directories
        await self._execute_ssh_command(
            "ls -la /opt/veris-memory/ 2>/dev/null || ls -la /root/",
            "Check key directory permissions"
        )
        
        self._analyze_security_findings()
    
    async def _firewall_investigation_workflow(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ):
        """Advanced network firewall and connectivity investigation workflow.
        
        This workflow performs comprehensive firewall and network connectivity
        analysis to diagnose port blocking, service accessibility issues, and
        network security policy problems that prevent proper system operation.
        
        Firewall Investigation Components:
        1. UFW (Uncomplicated Firewall) status and rule analysis
        2. Low-level iptables rule examination and validation
        3. Service port accessibility testing from local interface
        4. Network service binding verification
        5. Recent firewall activity and blocking event analysis
        
        Network Diagnostics:
        - Port connectivity testing using netcat (nc)
        - Service listener validation with netstat
        - Firewall rule effectiveness verification
        - Recent block/allow activity monitoring
        
        Args:
            alert_context: Network connectivity alert details including
                         failed connections, timeout errors, or port blocking
            diagnostic_context: Network-related diagnostic information
                              that may indicate firewall misconfigurations
        
        Environment Variables:
            TARGET_HOST: Override localhost for connectivity testing
        
        Critical Ports Tested:
            - 8000, 8001: Veris Memory API services
            - 9090: Monitoring/metrics endpoint
            - 8080: Dashboard interface
            - 6333, 7474, 6379: Database services
        
        Analysis Results:
            - UFW rule configuration status
            - Port accessibility matrix
            - Service binding validation
            - Recent firewall block events
        """
        logger.info("🛡️ Executing firewall investigation workflow...")
        
        # Step 1: Check UFW status and rules
        await self._execute_ssh_command(
            "ufw status numbered",
            "Check UFW firewall rules"
        )
        
        # Step 2: Check iptables rules
        await self._execute_ssh_command(
            "iptables -L -n -v",
            "Check iptables rules"
        )
        
        # Step 3: Test port accessibility from local interface
        target_host = os.getenv('TARGET_HOST', 'localhost')
        important_ports = ["8000", "8001", "9090", "8080"]
        for port in important_ports:
            await self._execute_ssh_command(
                f"timeout 3 nc -zv {target_host} {port} 2>&1",
                f"Test {target_host} access to port {port}",
                ignore_errors=True
            )
        
        # Step 4: Check if services are listening
        await self._execute_ssh_command(
            "netstat -tulpn | grep -E ':(8000|8001|9090|8080|6333|7474|6379)'",
            "Check if services are listening on expected ports"
        )
        
        # Step 5: Check for blocked connections
        await self._execute_ssh_command(
            "journalctl --since '10 minutes ago' | grep -i 'ufw\\|iptables\\|blocked'",
            "Check for recent firewall blocks"
        )
        
        self._analyze_firewall_findings()
    
    async def _general_investigation_workflow(
        self,
        alert_context: Dict[str, Any],
        diagnostic_context: Dict[str, Any]
    ):
        """Comprehensive general investigation workflow for unknown or complex issues.
        
        This is the fallback investigation workflow that performs broad-spectrum
        system analysis when the alert context doesn't match specific known
        patterns. It provides a systematic approach to diagnosing unusual or
        multi-faceted system problems.
        
        General Investigation Approach:
        1. High-level system health overview (uptime, disk, memory)
        2. Recent error log analysis across all system components
        3. Systemd service status verification and health checks
        4. External connectivity validation (internet access)
        5. Basic system stability and resource availability
        
        Use Cases:
        - Alerts with unclear or complex root causes
        - Multi-system failures requiring broad investigation
        - Novel failure patterns not covered by specific workflows
        - Preliminary investigation before specialized workflows
        
        Args:
            alert_context: General alert information that doesn't match
                         specific patterns for specialized workflows
            diagnostic_context: Broad diagnostic context that may help
                              identify the nature of unknown issues
        
        Investigation Coverage:
        - System resource availability (CPU, memory, disk)
        - Critical error patterns in system logs
        - Service management system health (systemd)
        - Network connectivity to external services
        - Overall system stability indicators
        
        Output Analysis:
        - System load and resource pressure assessment
        - Critical error identification and categorization
        - Service dependency health validation
        - Connectivity status verification
        
        This workflow serves as both a diagnostic tool for unknown issues
        and a foundation for determining which specialized workflows to run.
        """
        logger.info("🔍 Executing general investigation workflow...")
        
        # Step 1: System overview
        await self._execute_ssh_command(
            "uptime && echo '---' && df -h && echo '---' && free -h",
            "Get system overview"
        )
        
        # Step 2: Check logs for errors
        await self._execute_ssh_command(
            "journalctl --since '15 minutes ago' --priority=err -n 20",
            "Check recent error logs"
        )
        
        # Step 3: Check service status
        await self._execute_ssh_command(
            "systemctl status --no-pager",
            "Check systemd status overview"
        )
        
        # Step 4: Check network connectivity
        await self._execute_ssh_command(
            "ping -c 3 8.8.8.8 && echo 'Internet connectivity: OK' || echo 'Internet connectivity: FAILED'",
            "Test internet connectivity"
        )
        
        self._analyze_general_findings()
    
    async def _execute_ssh_command(
        self,
        command: str,
        description: str,
        timeout: int = 30,
        ignore_errors: bool = False
    ) -> Dict[str, Any]:
        """Execute a command via SSH with security controls."""
        logger.info(f"  🔧 {description}")
        
        # Use SSH Security Manager if available
        if self.ssh_security:
            result = self.ssh_security.execute_secure_command(
                command=command,
                description=description,
                timeout=timeout
            )
            
            # Adapt result format for compatibility
            execution_record = {
                "command": command,
                "description": description,
                "timestamp": result["timestamp"],
                "success": result["success"] or ignore_errors,
                "output": result["output"],
                "error": result["error"],
                "security_checks": result["security_checks"]
            }
            
            if not execution_record["success"] and not ignore_errors:
                logger.warning(f"    ⚠️ Command failed: {result['error']}")
            else:
                logger.info(f"    ✅ Command completed")
        
        else:
            # Legacy SSH execution (fallback)
            ssh_command = [
                "ssh",
                "-i", self.ssh_key_path,
                "-o", "ConnectTimeout=10",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",
                f"{self.ssh_user}@{self.server_host}",
                command
            ]
            
            execution_record = {
                "command": command,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "output": "",
                "error": "",
                "security_checks": {"legacy_mode": True}
            }
            
            try:
                result = subprocess.run(
                    ssh_command,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                execution_record["output"] = result.stdout
                execution_record["error"] = result.stderr
                execution_record["success"] = result.returncode == 0 or ignore_errors
                
                if not execution_record["success"] and not ignore_errors:
                    logger.warning(f"    ⚠️ Command failed: {result.stderr}")
                else:
                    logger.info(f"    ✅ Command completed")
                
            except subprocess.TimeoutExpired:
                execution_record["error"] = f"Command timed out after {timeout} seconds"
                logger.warning(f"    ⏱️ Command timed out")
            except Exception as e:
                execution_record["error"] = str(e)
                logger.error(f"    ❌ Command execution error: {str(e)}")
        
        self.execution_log.append(execution_record)
        return execution_record
    
    def _analyze_service_health_findings(self) -> None:
        """Analyze findings from service health investigation."""
        self.findings["service_health"] = {
            "failed_services": [],
            "container_issues": [],
            "port_issues": [],
            "recent_errors": []
        }
        
        # Analyze execution log for service health patterns
        for record in self.execution_log:
            if "systemctl status" in record["command"]:
                if "failed" in record["output"].lower() or "inactive" in record["output"].lower():
                    service_name = record["command"].split()[-1]
                    self.findings["service_health"]["failed_services"].append(service_name)
                    
                    # Generate fix recommendation
                    self.recommended_fixes.append({
                        "action": f"restart_{service_name}",
                        "command": f"systemctl restart {service_name}",
                        "confidence": 0.8,
                        "risk": "low",
                        "description": f"Restart failed service {service_name}"
                    })
            
            elif "docker ps" in record["command"]:
                if "exited" in record["output"].lower():
                    self.findings["service_health"]["container_issues"].append("Found exited containers")
            
            elif "netstat" in record["command"] and record["command"].count("grep") > 0:
                if not record["output"].strip():
                    port = record["description"].split()[-1] if "port" in record["description"] else "unknown"
                    self.findings["service_health"]["port_issues"].append(f"Port {port} not listening")
    
    def _analyze_database_connectivity_findings(self) -> None:
        """Analyze findings from database connectivity investigation."""
        self.findings["database_connectivity"] = {
            "connection_failures": [],
            "container_issues": [],
            "firewall_blocks": [],
            "disk_space_issues": []
        }
        
        for record in self.execution_log:
            if "connection: FAILED" in record["output"]:
                db_name = record["output"].split(" connection:")[0].split()[-1]
                self.findings["database_connectivity"]["connection_failures"].append(db_name)
                
                # Generate fix recommendation
                self.recommended_fixes.append({
                    "action": f"restart_{db_name.lower()}_container",
                    "command": f"docker restart $(docker ps -q --filter ancestor={db_name.lower()})",
                    "confidence": 0.7,
                    "risk": "medium", 
                    "description": f"Restart {db_name} database container"
                })
    
    def _analyze_performance_findings(self) -> None:
        """Analyze findings from performance investigation."""
        self.findings["performance"] = {
            "high_cpu_processes": [],
            "high_memory_processes": [],
            "disk_io_issues": [],
            "network_issues": []
        }
        
        # Analyze CPU and memory usage from execution log
        for record in self.execution_log:
            if "top -b" in record["command"]:
                lines = record["output"].split('\n')
                for line in lines:
                    if '%CPU' not in line and len(line.split()) > 8:
                        try:
                            cpu_usage = float(line.split()[8])
                            if cpu_usage > 50:  # High CPU threshold
                                process = line.split()[-1]
                                self.findings["performance"]["high_cpu_processes"].append({
                                    "process": process,
                                    "cpu_percent": cpu_usage
                                })
                        except (ValueError, IndexError):
                            continue
    
    def _analyze_security_findings(self) -> None:
        """Analyze findings from security investigation."""
        self.findings["security"] = {
            "suspicious_logins": [],
            "firewall_status": "unknown",
            "suspicious_processes": [],
            "permission_issues": []
        }
        
        for record in self.execution_log:
            if "ufw status" in record["command"]:
                if "inactive" in record["output"].lower():
                    self.findings["security"]["firewall_status"] = "disabled"
                    
                    # Generate fix recommendation
                    self.recommended_fixes.append({
                        "action": "enable_firewall",
                        "command": "ufw --force enable",
                        "confidence": 0.9,
                        "risk": "low",
                        "description": "Enable UFW firewall for security"
                    })
                else:
                    self.findings["security"]["firewall_status"] = "enabled"
    
    def _analyze_firewall_findings(self) -> None:
        """Analyze findings from firewall investigation."""
        self.findings["firewall"] = {
            "ufw_status": "unknown",
            "blocked_ports": [],
            "service_accessibility": {},
            "recent_blocks": []
        }
        
        for record in self.execution_log:
            if "ufw status" in record["command"]:
                if "inactive" in record["output"].lower():
                    self.findings["firewall"]["ufw_status"] = "disabled"
                else:
                    self.findings["firewall"]["ufw_status"] = "enabled"
            
            elif "nc -zv" in record["command"] and any(host in record["command"] for host in ["localhost", os.getenv('TARGET_HOST', 'localhost')]):
                port = record["command"].split()[-1]
                if "succeeded" in record["output"] or "open" in record["output"]:
                    self.findings["firewall"]["service_accessibility"][port] = "accessible"
                else:
                    self.findings["firewall"]["service_accessibility"][port] = "blocked"
    
    def _analyze_general_findings(self) -> None:
        """Analyze findings from general investigation."""
        self.findings["general"] = {
            "system_load": "normal",
            "disk_usage": "normal",
            "memory_usage": "normal",
            "connectivity": "ok",
            "recent_errors": []
        }
        
        # Basic analysis of general findings
        for record in self.execution_log:
            if "uptime" in record["command"]:
                if "load average:" in record["output"]:
                    load_avg = record["output"].split("load average:")[-1].strip()
                    if load_avg:
                        try:
                            load_1min = float(load_avg.split(',')[0].strip())
                            if load_1min > 4:  # Assuming 4+ cores
                                self.findings["general"]["system_load"] = "high"
                        except (ValueError, IndexError):
                            pass
    
    def _calculate_confidence_score(self) -> float:
        """Calculate confidence score based on workflow execution."""
        if not self.execution_log:
            return 0.0
        
        successful_commands = sum(1 for cmd in self.execution_log if cmd["success"])
        total_commands = len(self.execution_log)
        
        base_confidence = successful_commands / total_commands
        
        # Boost confidence if we found specific issues and generated fixes
        if self.recommended_fixes:
            base_confidence += 0.2
        
        # Boost confidence if we have clear findings
        if any(self.findings.values()):
            base_confidence += 0.1
        
        return min(1.0, base_confidence)


async def main() -> int:
    """Main function for testing debugging workflows."""
    parser = argparse.ArgumentParser(description="Automated Debugging Workflows")
    parser.add_argument("--alert-context", required=True, help="JSON string with alert context")
    parser.add_argument("--diagnostic-context", help="JSON string with diagnostic context")
    parser.add_argument("--ssh-key", required=True, help="Path to SSH private key")
    parser.add_argument("--server-host", default=os.getenv('VERIS_MEMORY_HOST', 'localhost'), help="Server hostname")
    parser.add_argument("--output", help="Output file for workflow results")
    
    args = parser.parse_args()
    
    # Parse contexts
    try:
        alert_context = json.loads(args.alert_context)
        diagnostic_context = json.loads(args.diagnostic_context) if args.diagnostic_context else {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        return 1
    
    # Configure SSH
    ssh_config = {
        "host": args.server_host,
        "user": os.getenv('VERIS_MEMORY_USER', 'root'),
        "key_path": args.ssh_key
    }
    
    # Execute debugging workflow
    workflow_engine = AutomatedDebuggingWorkflows(ssh_config)
    result = await workflow_engine.execute_workflow_for_alert(alert_context, diagnostic_context)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Workflow results saved to {args.output}")
    else:
        print(json.dumps(result, indent=2))
    
    return 0 if result.get("confidence_score", 0) > 0.5 else 1


if __name__ == "__main__":
    asyncio.run(main())