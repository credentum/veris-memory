#!/usr/bin/env python3
"""
Secure error handling for production environments.

Provides error sanitization to prevent sensitive information leakage
while maintaining detailed logging for debugging purposes.
"""

import os
import logging
import traceback
import re
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


def is_production() -> bool:
    """Check if running in production environment."""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    return environment in ("production", "prod")


def sanitize_error_message(error_msg: str, error_type: str = "unexpected_error") -> str:
    """Sanitize error message for production safety.
    
    Args:
        error_msg: Raw error message that may contain sensitive information
        error_type: Type of error for context
        
    Returns:
        Sanitized error message safe for production exposure
    """
    if not is_production():
        return error_msg
    
    # Define sensitive patterns to remove/replace
    sensitive_patterns = [
        (r'password[=:]\s*[^\s]+', 'password=***'),
        (r'token[=:]\s*[^\s]+', 'token=***'),
        (r'key[=:]\s*[^\s]+', 'key=***'),
        (r'secret[=:]\s*[^\s]+', 'secret=***'),
        (r'/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', '/***/***/***'),  # File paths
        (r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', 'X.X.X.X'),  # IP addresses
        (r':\d{4,5}', ':****'),  # Port numbers
        (r'Connection refused.*', 'Connection unavailable'),  # Connection details
    ]
    
    sanitized = error_msg
    for pattern, replacement in sensitive_patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    # Generic error messages for different error types
    generic_messages = {
        "storage_unavailable": "Storage service temporarily unavailable",
        "storage_error": "Storage operation failed",
        "storage_exception": "Storage service error",
        "invalid_agent_id": "Invalid agent identifier format",
        "invalid_key": "Invalid key format",
        "invalid_content_type": "Invalid content type",
        "rate_limit": "Request rate limit exceeded",
        "namespace_error": "Namespace access error",
        "unexpected_error": "Internal server error"
    }
    
    # If message still looks sensitive, use generic message
    if any(keyword in sanitized.lower() for keyword in [
        'traceback', 'stack trace', 'exception', 'error:', 'failed:', 'errno'
    ]):
        return generic_messages.get(error_type, "Internal server error")
    
    return sanitized


def create_error_response(
    success: bool = False,
    message: str = "",
    error_type: str = "unexpected_error",
    error_details: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create standardized error response with sanitization.
    
    Args:
        success: Operation success status
        message: Error message (will be sanitized in production)
        error_type: Classification of error type
        error_details: Detailed error information (logged but not exposed in production)
        **kwargs: Additional response fields
        
    Returns:
        Standardized error response dict
    """
    # Always log full details for debugging (regardless of environment)
    if error_details:
        logger.error(f"Error ({error_type}): {message} | Details: {error_details}")
    else:
        logger.error(f"Error ({error_type}): {message}")
    
    # Create base response
    response = {
        "success": success,
        "message": sanitize_error_message(message, error_type),
        "error_type": error_type
    }
    
    # Add error details only in non-production environments
    if not is_production() and error_details:
        response["error"] = error_details
    
    # Add any additional fields
    response.update(kwargs)
    
    return response


def handle_storage_error(e: Exception, operation: str = "storage operation") -> Dict[str, Any]:
    """Handle storage-related errors with proper classification.
    
    Args:
        e: Exception that occurred
        operation: Description of the operation that failed
        
    Returns:
        Standardized error response
    """
    error_details = str(e)
    
    # Classify error type based on exception
    if isinstance(e, ConnectionError):
        error_type = "storage_unavailable"
        message = f"{operation.title()} failed: storage unavailable"
    elif isinstance(e, TimeoutError):
        error_type = "storage_error"
        message = f"{operation.title()} failed: operation timeout"
    elif "connection refused" in str(e).lower():
        error_type = "storage_unavailable"
        message = f"{operation.title()} failed: storage unavailable"
    elif "timeout" in str(e).lower():
        error_type = "storage_error"
        message = f"{operation.title()} failed: operation timeout"
    else:
        error_type = "storage_exception"
        message = f"{operation.title()} failed: storage error"
    
    return create_error_response(
        message=message,
        error_type=error_type,
        error_details=error_details
    )


def handle_validation_error(e: Exception, field_name: str = "input") -> Dict[str, Any]:
    """Handle validation errors with proper sanitization.
    
    Args:
        e: Validation exception
        field_name: Name of the field that failed validation
        
    Returns:
        Standardized error response
    """
    error_details = str(e)
    
    # Determine error type based on validation failure
    if "pattern" in error_details.lower():
        error_type = f"invalid_{field_name}"
        message = f"Invalid {field_name} format"
    elif "length" in error_details.lower():
        error_type = f"invalid_{field_name}"
        message = f"{field_name.title()} length validation failed"
    elif "required" in error_details.lower():
        error_type = "missing_parameter"
        message = f"Required parameter '{field_name}' is missing"
    else:
        error_type = "invalid_input"
        message = f"Input validation failed for {field_name}"
    
    return create_error_response(
        message=message,
        error_type=error_type,
        error_details=error_details
    )


def handle_generic_error(e: Exception, operation: str = "operation") -> Dict[str, Any]:
    """Handle generic errors with sanitization.
    
    Args:
        e: Exception that occurred
        operation: Description of the operation that failed
        
    Returns:
        Standardized error response
    """
    error_details = str(e)
    
    # Log full traceback for debugging
    logger.error(f"Unexpected error in {operation}: {traceback.format_exc()}")
    
    return create_error_response(
        message=f"{operation.title()} failed unexpectedly",
        error_type="unexpected_error",
        error_details=error_details
    )