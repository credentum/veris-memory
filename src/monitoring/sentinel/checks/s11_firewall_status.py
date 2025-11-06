#!/usr/bin/env python3
"""
S11: Firewall Status Check

Monitors UFW firewall status to ensure security is maintained.
Alerts if firewall is disabled or critical rules are missing.

NOTE: This check relies on host-based monitoring since Docker containers
cannot check the host's UFW firewall status. The host must run the
sentinel-host-checks.sh script which sends results to the Sentinel API.
"""

import asyncio
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig


class S11FirewallStatus(BaseCheck):
    """
    Check firewall status and configuration using host-based monitoring.

    This check retrieves results from the Sentinel API that were submitted
    by the host-based monitoring script (sentinel-host-checks.sh).
    """

    CHECK_ID = "S11-firewall-status"

    def __init__(self, config: SentinelConfig, api_instance=None):
        """
        Initialize firewall status check.

        Args:
            config: Sentinel configuration
            api_instance: SentinelAPI instance to retrieve host check results from
        """
        super().__init__(config, self.CHECK_ID, "Firewall status and security monitoring (host-based)")
        self.api_instance = api_instance
        self.max_age_minutes = 10  # Alert if no update in 10 minutes

    async def run_check(self) -> CheckResult:
        """
        Perform firewall status check by retrieving host-based results.

        Returns:
            CheckResult with firewall status
        """
        start_time = datetime.now()

        try:
            # Check if we have an API instance to retrieve results from
            if not self.api_instance:
                return CheckResult(
                    check_id=self.CHECK_ID,
                    timestamp=datetime.now(),
                    status="warn",
                    latency_ms=self._calculate_latency(start_time),
                    message="⚠️ Host-based monitoring not configured",
                    details={
                        "error": "No API instance provided to S11 check",
                        "setup_required": "Install and configure sentinel-host-checks.sh on the host",
                        "documentation": "See docs/SECURITY_SETUP.md"
                    }
                )

            # Get the most recent host check result
            host_result = self.api_instance.get_host_check_result(self.CHECK_ID)

            if not host_result:
                # No results received yet from host script
                return CheckResult(
                    check_id=self.CHECK_ID,
                    timestamp=datetime.now(),
                    status="warn",
                    latency_ms=self._calculate_latency(start_time),
                    message="⚠️ No firewall status data from host",
                    details={
                        "error": "Host monitoring script not reporting",
                        "action_required": "Verify sentinel-host-checks.sh is running on the host",
                        "setup_command": "crontab -e and add: */5 * * * * /opt/veris-memory/scripts/sentinel-host-checks.sh",
                        "documentation": "See docs/SECURITY_SETUP.md"
                    }
                )

            # Check if the result is too old
            age = datetime.now() - host_result.timestamp
            if age > timedelta(minutes=self.max_age_minutes):
                return CheckResult(
                    check_id=self.CHECK_ID,
                    timestamp=datetime.now(),
                    status="warn",
                    latency_ms=self._calculate_latency(start_time),
                    message=f"⚠️ Firewall status data is stale ({int(age.total_seconds() / 60)} minutes old)",
                    details={
                        "last_update": host_result.timestamp.isoformat(),
                        "age_minutes": int(age.total_seconds() / 60),
                        "max_age_minutes": self.max_age_minutes,
                        "last_status": host_result.status,
                        "last_message": host_result.message,
                        "action_required": "Check if host monitoring script is still running"
                    }
                )

            # Return the host-based result with freshness validation
            return CheckResult(
                check_id=self.CHECK_ID,
                timestamp=datetime.now(),
                status=host_result.status,
                latency_ms=self._calculate_latency(start_time),
                message=f"{host_result.message} (host-based check)",
                details={
                    **host_result.details,
                    "host_check_timestamp": host_result.timestamp.isoformat(),
                    "age_seconds": int(age.total_seconds()),
                    "check_method": "host-based"
                }
            )

        except Exception as e:
            return CheckResult(
                check_id=self.CHECK_ID,
                timestamp=datetime.now(),
                status="fail",
                latency_ms=self._calculate_latency(start_time),
                message=f"❌ Firewall check failed: {str(e)}",
                details={"error": str(e), "check_method": "host-based"}
            )
    
    async def _check_ufw_status(self) -> Dict[str, Any]:
        """Check if UFW is active."""
        try:
            # Run ufw status
            proc = await asyncio.create_subprocess_exec(
                'sudo', 'ufw', 'status', 'verbose',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            output = stdout.decode('utf-8')
            
            # Parse status
            is_active = 'Status: active' in output
            
            # Count rules
            rule_count = output.count('ALLOW') + output.count('DENY')
            
            return {
                'active': is_active,
                'rules': rule_count,
                'output': output[:500]  # First 500 chars for debugging
            }
            
        except Exception:
            # If we can't run sudo ufw, try checking systemctl
            try:
                proc = await asyncio.create_subprocess_exec(
                    'systemctl', 'is-active', 'ufw',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                
                return {
                    'active': stdout.decode('utf-8').strip() == 'active',
                    'rules': -1,  # Unknown
                    'method': 'systemctl'
                }
            except Exception:
                return {'active': False, 'rules': 0, 'error': 'Cannot check status'}
    
    async def _check_required_rules(self) -> list:
        """Check if required firewall rules exist."""
        missing = []
        
        try:
            # Get current rules
            proc = await asyncio.create_subprocess_exec(
                'sudo', 'ufw', 'status', 'numbered',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode('utf-8')
            
            # Check each required port
            for port in self.required_ports:
                if f"{port}/tcp" not in output and str(port) not in output:
                    missing.append(f"TCP port {port}")
            
            # Check UDP ranges
            for start, end in self.required_udp_ranges:
                range_str = f"{start}:{end}/udp"
                if range_str not in output:
                    missing.append(f"UDP range {start}-{end}")
                    
        except Exception:
            # If we can't check, try iptables as fallback
            try:
                proc = await asyncio.create_subprocess_exec(
                    'sudo', 'iptables', '-L', '-n',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                output = stdout.decode('utf-8')
                
                # Basic check for Docker rules (ports should be in DOCKER chain)
                for port in self.required_ports:
                    if f"dpt:{port}" not in output:
                        missing.append(f"Port {port} (iptables)")
                        
            except Exception:
                pass  # Can't check rules
        
        return missing
    
    async def _check_docker_rules(self) -> bool:
        """Check if Docker iptables rules are present."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'sudo', 'iptables', '-L', 'DOCKER', '-n',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                output = stdout.decode('utf-8')
                # Check if our service ports are in Docker chain
                has_api = 'dpt:8000' in output
                has_dashboard = 'dpt:8080' in output
                has_sentinel = 'dpt:9090' in output
                
                return has_api or has_dashboard or has_sentinel
            
            return False
            
        except Exception:
            return False
    
    def _calculate_latency(self, start_time: datetime) -> float:
        """Calculate latency in milliseconds."""
        delta = datetime.now() - start_time
        return delta.total_seconds() * 1000