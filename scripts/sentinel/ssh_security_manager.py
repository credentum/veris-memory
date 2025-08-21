#!/usr/bin/env python3
"""
SSH Security Manager for Phase 3 Automation

Provides secure SSH command execution with allowlists, audit logging,
session recording, and comprehensive security controls.

Author: Claude Code Integration - Phase 3 Security
Date: 2025-08-21
"""

import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SSHSecurityManager:
    """
    Secure SSH command execution manager with comprehensive security controls.
    
    Features:
    - Command allowlist enforcement
    - Comprehensive audit logging
    - Session recording and tracking
    - Input validation and sanitization
    - Rate limiting and session controls
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize SSH security manager."""
        self.config = config
        self.ssh_config = config.get('ssh_config', {})
        self.audit_log_path = config.get('audit_log_path', '/tmp/ssh_audit.log')
        self.session_log_path = config.get('session_log_path', '/tmp/ssh_sessions.log')
        
        # Security settings
        self.max_session_duration = config.get('max_session_duration', 1800)  # 30 minutes
        self.max_commands_per_session = config.get('max_commands_per_session', 100)
        self.rate_limit_commands_per_minute = config.get('rate_limit_per_minute', 10)
        
        # Session tracking
        self.session_id = f"ssh-{int(time.time())}-{os.getpid()}"
        self.session_start = datetime.now()
        self.commands_executed = 0
        self.last_command_time = 0
        self.command_times = []
        
        # Initialize audit logging
        self._init_audit_logging()
        
        # Load command allowlist
        self.allowed_commands = self._load_command_allowlist()
        
        logger.info(f"SSH Security Manager initialized - Session: {self.session_id}")
        self._log_audit_event('SESSION_START', {'session_id': self.session_id})

    def _init_audit_logging(self):
        """Initialize comprehensive audit logging."""
        audit_handler = logging.FileHandler(self.audit_log_path)
        audit_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - SESSION:%(session)s - %(message)s'
        )
        audit_handler.setFormatter(audit_formatter)
        
        self.audit_logger = logging.getLogger(f'ssh_audit_{self.session_id}')
        self.audit_logger.addHandler(audit_handler)
        self.audit_logger.setLevel(logging.INFO)

    def _load_command_allowlist(self) -> Set[str]:
        """Load allowed SSH commands from configuration."""
        default_allowed_commands = {
            # System information
            'uptime', 'free', 'df', 'ps', 'top', 'htop', 'iostat', 'netstat', 'ss',
            
            # Service management
            'systemctl status', 'systemctl is-active', 'systemctl list-units',
            
            # Docker operations
            'docker ps', 'docker logs', 'docker stats', 'docker inspect',
            
            # Network diagnostics
            'ping', 'curl', 'wget', 'nc', 'nslookup', 'dig',
            
            # Log analysis
            'journalctl', 'tail', 'head', 'grep', 'awk', 'sed',
            
            # File system
            'ls', 'find', 'du', 'stat', 'file',
            
            # Emergency recovery (restricted)
            'systemctl restart', 'systemctl stop', 'systemctl start',
            'docker restart', 'docker stop', 'docker start',
            
            # Firewall (emergency)
            'ufw status', 'ufw enable', 'ufw disable', 'iptables -L'
        }
        
        # Load custom allowlist if provided
        custom_commands = self.config.get('allowed_commands', [])
        return default_allowed_commands.union(set(custom_commands))

    def _validate_command(self, command: str) -> bool:
        """Validate command against security allowlist."""
        # Remove leading/trailing whitespace
        command = command.strip()
        
        # Check explicit deny list first (complete command names)
        command_parts = command.split()
        if command_parts:
            base_command = command_parts[0].split('/')[-1]  # Get command name without path
            
            denied_commands = {
                # Destructive operations
                'rm', 'rmdir', 'shred', 'wipe', 'dd', 'mkfs', 'format',
                
                # Privilege escalation
                'sudo', 'su', 'passwd', 'chsh', 'chfn', 'newgrp',
                
                # Network operations  
                'nc', 'netcat', 'telnet', 'ssh', 'scp', 'sftp', 'rsync', 'ftp',
                
                # Process control
                'kill', 'killall', 'pkill', 'nohup', 'disown', 'bg', 'fg',
                
                # System modification
                'mount', 'umount', 'swapon', 'swapoff', 'fdisk', 'parted', 'lvm',
                
                # Package management
                'apt', 'apt-get', 'yum', 'dnf', 'zypper', 'pacman', 'pip', 'npm', 'gem',
                
                # Compilers and interpreters
                'gcc', 'g++', 'make', 'cmake', 'python', 'python3', 'perl', 'ruby', 'node', 'java',
                
                # Archive operations that could overwrite
                'tar', 'unzip', 'gunzip', 'bunzip2', 'unrar', '7z',
                
                # Text editors (could modify files)
                'vi', 'vim', 'nano', 'emacs', 'ed', 'joe', 'pico',
                
                # Database operations
                'mysql', 'psql', 'sqlite3', 'mongo', 'redis-cli',
                
                # System information that could leak sensitive data
                'lsof', 'strace', 'ltrace', 'gdb', 'objdump',
            }
            
            if base_command in denied_commands:
                logger.warning(f"Command blocked by explicit deny list: {base_command}")
                self._log_audit_event('COMMAND_BLOCKED_DENIED', {
                    'command': command,
                    'denied_command': base_command
                })
                return False
        
        # Check for dangerous patterns (comprehensive list)
        dangerous_patterns = [
            # Command substitution and execution
            r'\$\{[^}]*\}',                    # Variable expansion
            r'\$\([^)]*\)',                    # Command substitution  
            r'`[^`]*`',                        # Backtick substitution
            
            # Command chaining and control
            r'[;&]',                           # Command separators
            r'&&',                             # AND operator
            r'\|\|',                           # OR operator
            r'\|\s*(sh|bash|zsh|fish|csh|tcsh)', # Pipe to shell
            
            # Output redirection (file writing)
            r'>\s*/[^t]',                      # Write to root (except /tmp)
            r'>>\s*/[^t]',                     # Append to root (except /tmp)  
            r'>\s*/tmp/\.\.',                  # Write to /tmp with traversal
            r'>\s*/dev/',                      # Device file manipulation
            r'>\s*/proc/',                     # Proc filesystem
            r'>\s*/sys/',                      # Sys filesystem
            
            # Directory traversal
            r'\.\./',                          # Relative traversal
            r'/\.\.',                          # Absolute traversal
            r'~[^/\s]*/',                      # Home directory access
            
            # Destructive operations (multiple variations)
            r'\brm\s+.*-[rf]',                # rm with recursive/force
            r'\brm\s+-[rf]',                  # rm with flags
            r'\bmv\s+.*\s+/',                 # Moving to root
            r'\bcp\s+.*\s+/',                 # Copying to root
            r'\bdd\s+',                       # dd command
            r'\bshred\s+',                    # File shredding
            
            # Permission changes
            r'\bchmod\s+[0-9]*7[0-9]*',       # World writable
            r'\bchmod\s+\+[rwx]*w',           # Adding write permissions
            r'\bchown\s+root',                # Changing to root ownership
            r'\bchgrp\s+root',                # Changing to root group
            
            # Network operations
            r'\bwget\s+.*\|',                 # Wget with pipe
            r'\bcurl\s+.*\|',                 # Curl with pipe
            r'\bnc\s+.*-e',                   # Netcat with exec
            r'\bnc\s+.*-c',                   # Netcat with command
            
            # Sensitive file patterns
            r'/etc/(passwd|shadow|sudoers|hosts|fstab|crontab)',
            r'/root/\.',                       # Root dotfiles
            r'/home/[^/]+/\.(ssh|gnupg)',     # User sensitive dirs
            r'\.ssh/(id_|known_hosts|config)',# SSH files
            r'/var/log/',                      # Log files
            r'/proc/[0-9]+/',                  # Process information
            
            # Code execution patterns
            r'\bexec\s*\(',                   # Exec calls
            r'\beval\s*\(',                   # Eval calls
            r'\bsystem\s*\(',                 # System calls
            r'/bin/(sh|bash|zsh)',            # Direct shell access
            r'\bpython\s+-c',                 # Python code execution
            r'\bperl\s+-e',                   # Perl code execution
            
            # Process manipulation
            r'\bkill\s+-[0-9]+',              # Kill with specific signal
            r'\bkillall\s+',                  # Kill all matching
            r'\bnohup\s+.*&',                 # Background processes
            
            # Archive operations with overwrite potential
            r'\btar\s+.*-[xzjc].*/',          # Tar extract to root
            r'\bunzip.*\s+/',                 # Unzip to root
            r'\bgunzip.*>\s*/',               # Gunzip to root
            
            # Injection and malicious patterns
            r"';.*--",                        # SQL injection
            r'\bor\s+1=1',                   # Boolean injection
            r'<script[^>]*>',                 # XSS
            r'javascript:',                   # JS URLs
            r'data:.*base64',                 # Data URLs
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"Command blocked by security pattern: {pattern}")
                self._log_audit_event('COMMAND_BLOCKED_DANGEROUS', {
                    'command': command,
                    'pattern': pattern
                })
                return False
        
        # Check against allowlist
        command_base = command.split()[0] if command.split() else ''
        command_prefix = ' '.join(command.split()[:2]) if len(command.split()) >= 2 else command_base
        
        if command_base in self.allowed_commands or command_prefix in self.allowed_commands:
            return True
        
        # Check for partial matches (for commands with arguments)
        for allowed in self.allowed_commands:
            if command.startswith(allowed + ' ') or command == allowed:
                return True
        
        logger.warning(f"Command not in allowlist: {command}")
        self._log_audit_event('COMMAND_BLOCKED_ALLOWLIST', {'command': command})
        return False

    def _check_rate_limit(self) -> bool:
        """Check if command execution is within rate limits."""
        current_time = time.time()
        
        # Remove commands older than 1 minute
        self.command_times = [t for t in self.command_times if current_time - t < 60]
        
        # Check rate limit
        if len(self.command_times) >= self.rate_limit_commands_per_minute:
            logger.warning("Rate limit exceeded")
            self._log_audit_event('RATE_LIMIT_EXCEEDED', {
                'commands_per_minute': len(self.command_times)
            })
            return False
        
        return True

    def _check_session_limits(self) -> bool:
        """Check session duration and command count limits."""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        if session_duration > self.max_session_duration:
            logger.warning("Session duration limit exceeded")
            self._log_audit_event('SESSION_DURATION_EXCEEDED', {
                'duration_seconds': session_duration
            })
            return False
        
        if self.commands_executed >= self.max_commands_per_session:
            logger.warning("Session command count limit exceeded")
            self._log_audit_event('SESSION_COMMAND_LIMIT_EXCEEDED', {
                'commands_executed': self.commands_executed
            })
            return False
        
        return True

    def _log_audit_event(self, event_type: str, details: Dict[str, Any]):
        """Log comprehensive audit event."""
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'event_type': event_type,
            'details': details,
            'ssh_host': self.ssh_config.get('host'),
            'ssh_user': self.ssh_config.get('user')
        }
        
        # Log to audit file
        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')
        
        # Log to session file
        with open(self.session_log_path, 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')

    def execute_secure_command(
        self,
        command: str,
        description: str = "",
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Execute SSH command with comprehensive security controls.
        
        Args:
            command: The command to execute
            description: Human-readable description of the command
            timeout: Command timeout in seconds
            
        Returns:
            Dict containing execution results and security metadata
        """
        execution_start = time.time()
        command_hash = hashlib.sha256(command.encode()).hexdigest()[:8]
        
        result = {
            'command': command,
            'description': description,
            'command_hash': command_hash,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'output': '',
            'error': '',
            'security_checks': {
                'command_validated': False,
                'rate_limit_ok': False,
                'session_limits_ok': False
            },
            'execution_time_seconds': 0
        }
        
        try:
            # Security checks
            if not self._validate_command(command):
                result['error'] = 'Command blocked by security validation'
                self._log_audit_event('COMMAND_EXECUTION_BLOCKED', {
                    'command': command,
                    'reason': 'validation_failed'
                })
                return result
            
            result['security_checks']['command_validated'] = True
            
            if not self._check_rate_limit():
                result['error'] = 'Rate limit exceeded'
                self._log_audit_event('COMMAND_EXECUTION_BLOCKED', {
                    'command': command,
                    'reason': 'rate_limit'
                })
                return result
            
            result['security_checks']['rate_limit_ok'] = True
            
            if not self._check_session_limits():
                result['error'] = 'Session limits exceeded'
                self._log_audit_event('COMMAND_EXECUTION_BLOCKED', {
                    'command': command,
                    'reason': 'session_limits'
                })
                return result
            
            result['security_checks']['session_limits_ok'] = True
            
            # Execute SSH command
            ssh_command = [
                'ssh',
                '-i', self.ssh_config['key_path'],
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'LogLevel=ERROR',
                f"{self.ssh_config['user']}@{self.ssh_config['host']}",
                command
            ]
            
            # Log command execution start
            self._log_audit_event('COMMAND_EXECUTION_START', {
                'command': command,
                'description': description,
                'command_hash': command_hash
            })
            
            # Execute command
            process_result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            result['output'] = process_result.stdout
            result['error'] = process_result.stderr
            result['success'] = process_result.returncode == 0
            
            # Update session tracking
            self.commands_executed += 1
            self.command_times.append(time.time())
            
            # Log command completion
            self._log_audit_event('COMMAND_EXECUTION_COMPLETE', {
                'command': command,
                'command_hash': command_hash,
                'success': result['success'],
                'return_code': process_result.returncode,
                'output_length': len(result['output']),
                'error_length': len(result['error'])
            })
            
        except subprocess.TimeoutExpired:
            result['error'] = f'Command timed out after {timeout} seconds'
            self._log_audit_event('COMMAND_EXECUTION_TIMEOUT', {
                'command': command,
                'timeout_seconds': timeout
            })
            
        except Exception as e:
            result['error'] = f'Command execution error: {str(e)}'
            self._log_audit_event('COMMAND_EXECUTION_ERROR', {
                'command': command,
                'error': str(e)
            })
        
        finally:
            result['execution_time_seconds'] = time.time() - execution_start
        
        return result

    def close_session(self):
        """Close SSH session and finalize audit logging."""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        self._log_audit_event('SESSION_END', {
            'session_id': self.session_id,
            'duration_seconds': session_duration,
            'commands_executed': self.commands_executed
        })
        
        logger.info(f"SSH session closed - Duration: {session_duration:.1f}s, Commands: {self.commands_executed}")

    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive session summary for reporting."""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        return {
            'session_id': self.session_id,
            'start_time': self.session_start.isoformat(),
            'duration_seconds': session_duration,
            'commands_executed': self.commands_executed,
            'ssh_host': self.ssh_config.get('host'),
            'ssh_user': self.ssh_config.get('user'),
            'audit_log_path': self.audit_log_path,
            'session_log_path': self.session_log_path
        }


# Example usage and testing
if __name__ == '__main__':
    # Example configuration
    config = {
        'ssh_config': {
            'host': 'localhost',
            'user': 'test',
            'key_path': '/tmp/test_key'
        },
        'audit_log_path': '/tmp/ssh_audit_test.log',
        'session_log_path': '/tmp/ssh_session_test.log'
    }
    
    # Initialize security manager
    ssh_mgr = SSHSecurityManager(config)
    
    # Test command validation
    test_commands = [
        'uptime',                    # Should pass
        'systemctl status nginx',    # Should pass
        'rm -rf /',                 # Should fail
        'echo "test" > /etc/passwd', # Should fail
        'docker ps',                # Should pass
    ]
    
    print("Testing SSH Security Manager")
    print("=" * 40)
    
    for cmd in test_commands:
        valid = ssh_mgr._validate_command(cmd)
        status = "✅ ALLOWED" if valid else "❌ BLOCKED"
        print(f"{status}: {cmd}")
    
    # Show session summary
    print("\nSession Summary:")
    summary = ssh_mgr.get_session_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Close session
    ssh_mgr.close_session()