#!/usr/bin/env python3
"""
S11: Firewall Status Check

Monitors UFW firewall status to ensure security is maintained.
Alerts if firewall is disabled or critical rules are missing.
"""

import asyncio
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime

from ..models import CheckResult


class S11FirewallStatus:
    """Check firewall status and configuration."""
    
    CHECK_ID = "S11-firewall-status"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize firewall status check."""
        self.config = config or {}
        self.required_ports = [
            22,     # SSH
            2222,   # Claude container
            8000,   # MCP Server
            8001,   # REST API
            8080,   # Dashboard
            9090,   # Sentinel
        ]
        self.required_udp_ranges = [
            (60000, 61000),  # Mosh
        ]
    
    async def check(self) -> CheckResult:
        """
        Perform firewall status check.
        
        Returns:
            CheckResult with firewall status
        """
        start_time = datetime.now()
        
        try:
            # Check if UFW is active
            ufw_status = await self._check_ufw_status()
            
            if not ufw_status['active']:
                return CheckResult(
                    check_id=self.CHECK_ID,
                    timestamp=datetime.now(),
                    status="fail",
                    latency_ms=self._calculate_latency(start_time),
                    message="❌ CRITICAL: Firewall is DISABLED!",
                    details={
                        "ufw_active": False,
                        "security_risk": "HIGH",
                        "recommendation": "Run: sudo ufw --force enable"
                    }
                )
            
            # Check required rules
            missing_rules = await self._check_required_rules()
            
            if missing_rules:
                return CheckResult(
                    check_id=self.CHECK_ID,
                    timestamp=datetime.now(),
                    status="warn",
                    latency_ms=self._calculate_latency(start_time),
                    message=f"⚠️ Firewall active but missing {len(missing_rules)} rules",
                    details={
                        "ufw_active": True,
                        "missing_rules": missing_rules,
                        "configured_rules": ufw_status.get('rules', 0)
                    }
                )
            
            # Check if Docker iptables rules exist
            docker_rules = await self._check_docker_rules()
            
            return CheckResult(
                check_id=self.CHECK_ID,
                timestamp=datetime.now(),
                status="pass",
                latency_ms=self._calculate_latency(start_time),
                message="✅ Firewall active with all required rules",
                details={
                    "ufw_active": True,
                    "configured_rules": ufw_status.get('rules', 0),
                    "docker_integration": docker_rules,
                    "protected_ports": self.required_ports
                }
            )
            
        except Exception as e:
            return CheckResult(
                check_id=self.CHECK_ID,
                timestamp=datetime.now(),
                status="fail",
                latency_ms=self._calculate_latency(start_time),
                message=f"❌ Firewall check failed: {str(e)}",
                details={"error": str(e)}
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