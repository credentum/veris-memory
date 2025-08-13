#!/usr/bin/env python3
"""
Security System Recovery Tool
Sprint 10 Phase 3 - Automatic recovery after attacks
"""

import os
import sys
import time
import psutil
import signal
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))


class SecurityRecovery:
    """Handles recovery operations after security attacks"""
    
    def __init__(self):
        self.recovery_log = []
    
    def log_recovery_action(self, action: str, success: bool = True, details: str = ""):
        """Log recovery actions"""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "success": success,
            "details": details
        }
        self.recovery_log.append(entry)
        status = "✅" if success else "❌"
        print(f"{status} {action}: {details}")
    
    def kill_hanging_processes(self, process_patterns: List[str]) -> bool:
        """Kill processes that match patterns and might be hanging"""
        killed_count = 0
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    cmdline = ' '.join(proc_info['cmdline'] or [])
                    
                    # Check if process matches any hanging pattern
                    for pattern in process_patterns:
                        if pattern.lower() in cmdline.lower():
                            print(f"🔍 Found potentially hanging process: {proc_info['name']} (PID: {proc_info['pid']})")
                            print(f"   Command: {cmdline[:100]}...")
                            
                            # Kill the process
                            proc.terminate()
                            time.sleep(2)
                            
                            if proc.is_running():
                                proc.kill()  # Force kill if terminate didn't work
                            
                            killed_count += 1
                            break
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.log_recovery_action(
                "Kill hanging processes",
                success=True,
                details=f"Killed {killed_count} processes"
            )
            return True
            
        except Exception as e:
            self.log_recovery_action(
                "Kill hanging processes",
                success=False,
                details=f"Error: {e}"
            )
            return False
    
    def reset_rate_limiters(self) -> bool:
        """Reset rate limiting state"""
        try:
            # Try to import and reset WAF rate limiter
            from src.security.waf import WAFRateLimiter
            
            # Create a new limiter to get access to the reset methods
            limiter = WAFRateLimiter()
            
            # Clear all rate limiting state
            limiter.request_counts.clear()
            limiter.blocked_clients.clear()
            limiter.global_requests.clear()
            
            self.log_recovery_action(
                "Reset rate limiters",
                success=True,
                details="Cleared all rate limiting state"
            )
            return True
            
        except Exception as e:
            self.log_recovery_action(
                "Reset rate limiters",
                success=False,
                details=f"Error: {e}"
            )
            return False
    
    def clear_security_logs(self) -> bool:
        """Clear security logs to prevent log file bloat"""
        try:
            log_dirs = [
                "logs/security",
                "../logs/security",
                "/tmp/security_logs"
            ]
            
            cleared_files = 0
            for log_dir in log_dirs:
                if os.path.exists(log_dir):
                    for filename in os.listdir(log_dir):
                        if filename.endswith('.log'):
                            filepath = os.path.join(log_dir, filename)
                            # Keep the file but truncate it
                            with open(filepath, 'w') as f:
                                f.write(f"# Log cleared by recovery tool at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            cleared_files += 1
            
            self.log_recovery_action(
                "Clear security logs",
                success=True,
                details=f"Cleared {cleared_files} log files"
            )
            return True
            
        except Exception as e:
            self.log_recovery_action(
                "Clear security logs",
                success=False,
                details=f"Error: {e}"
            )
            return False
    
    def reset_firewall_state(self) -> bool:
        """Reset network firewall state"""
        try:
            from src.security.port_filter import NetworkFirewall
            
            firewall = NetworkFirewall()
            
            # Clear blocked IPs if the firewall has such functionality
            if hasattr(firewall, 'blocked_ips'):
                firewall.blocked_ips.clear()
            
            if hasattr(firewall, 'scan_attempts'):
                firewall.scan_attempts.clear()
            
            self.log_recovery_action(
                "Reset firewall state",
                success=True,
                details="Cleared firewall blocking state"
            )
            return True
            
        except Exception as e:
            self.log_recovery_action(
                "Reset firewall state",
                success=False,
                details=f"Error: {e}"
            )
            return False
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resources and identify issues"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            resource_status = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "warnings": []
            }
            
            # Check for resource issues
            if cpu_percent > 90:
                resource_status["warnings"].append("High CPU usage detected")
            
            if memory.percent > 90:
                resource_status["warnings"].append("High memory usage detected")
            
            if disk.percent > 95:
                resource_status["warnings"].append("Low disk space detected")
            
            self.log_recovery_action(
                "Check system resources",
                success=True,
                details=f"CPU: {cpu_percent:.1f}%, Memory: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%"
            )
            
            return resource_status
            
        except Exception as e:
            self.log_recovery_action(
                "Check system resources",
                success=False,
                details=f"Error: {e}"
            )
            return {}
    
    def emergency_recovery(self) -> bool:
        """Perform emergency recovery sequence"""
        print("🚨 Starting Emergency Security Recovery")
        print("=" * 50)
        
        recovery_steps = [
            ("Checking system resources", self.check_system_resources),
            ("Killing hanging processes", lambda: self.kill_hanging_processes([
                "test_synthetic_abuse",
                "python.*security.*test",
                "pytest.*security"
            ])),
            ("Resetting rate limiters", self.reset_rate_limiters),
            ("Resetting firewall state", self.reset_firewall_state),
            ("Clearing security logs", self.clear_security_logs)
        ]
        
        successful_steps = 0
        total_steps = len(recovery_steps)
        
        for step_name, step_func in recovery_steps:
            print(f"\n🔧 {step_name}...")
            try:
                result = step_func()
                if result or result is None:  # None is acceptable for some steps
                    successful_steps += 1
            except Exception as e:
                self.log_recovery_action(step_name, success=False, details=str(e))
        
        success_rate = (successful_steps / total_steps) * 100
        
        print(f"\n📊 Recovery Summary")
        print(f"   Successful steps: {successful_steps}/{total_steps}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Emergency recovery completed successfully!")
            return True
        else:
            print("⚠️  Emergency recovery had issues - manual intervention may be needed")
            return False
    
    def get_recovery_report(self) -> str:
        """Generate a recovery report"""
        if not self.recovery_log:
            return "No recovery actions performed."
        
        report = ["Security Recovery Report", "=" * 30, ""]
        
        for entry in self.recovery_log:
            status = "SUCCESS" if entry['success'] else "FAILED"
            report.append(f"{entry['timestamp']} - {status}: {entry['action']}")
            if entry['details']:
                report.append(f"  Details: {entry['details']}")
            report.append("")
        
        return "\n".join(report)


def main():
    """Main entry point for security recovery"""
    recovery = SecurityRecovery()
    
    try:
        # Perform emergency recovery
        success = recovery.emergency_recovery()
        
        # Generate and save report
        report = recovery.get_recovery_report()
        
        # Save report to file
        report_file = f"recovery_report_{int(time.time())}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"\n📄 Recovery report saved to: {report_file}")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⏹️  Recovery interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Recovery failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())