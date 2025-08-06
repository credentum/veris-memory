# Error Codes Reference

This document provides comprehensive error codes, handling strategies, and troubleshooting guidance for the Context Store MCP server.

## Error Response Format

All tools return errors in a consistent format:

```json
{
  "success": false,
  "message": "Human-readable error description",
  "error_type": "machine_readable_error_code",
  "details": {
    "additional": "context-specific information"
  }
}
```

## Rate Limiting Errors

### `rate_limit`

**Description**: Request rate limit exceeded for the specific tool.

**Common Causes**:

- Too many requests in the time window
- Burst traffic patterns
- Insufficient rate limit configuration

**Response Example**:

```json
{
  "success": false,
  "message": "Rate limit exceeded: 50 requests per minute",
  "error_type": "rate_limit",
  "details": {
    "limit": 50,
    "window": "1 minute",
    "retry_after": 30
  }
}
```

**Resolution**:

- Wait for the time window to reset
- Implement exponential backoff in client code
- Consider upgrading rate limits if needed
- Batch requests where possible

---

## Validation Errors

### `validation_error`

**Description**: Input data failed schema validation.

**Common Causes**:

- Missing required fields
- Invalid data types
- Values outside allowed ranges
- Malformed JSON

**Response Example**:

```json
{
  "success": false,
  "message": "Validation failed: missing required field 'type'",
  "error_type": "validation_error",
  "details": {
    "field": "type",
    "expected": "string",
    "received": "undefined"
  }
}
```

**Resolution**:

- Check input against tool schema
- Ensure all required fields are present
- Validate data types before sending
- Use schema validation in client code

### `invalid_agent_id`

**Description**: Agent ID format validation failed.

**Common Causes**:

- Empty or null agent ID
- Special characters not allowed
- ID too long (>64 characters)
- Invalid format pattern

**Response Example**:

```json
{
  "success": false,
  "message": "Invalid agent ID format: agent-invalid@id",
  "error_type": "invalid_agent_id",
  "details": {
    "agent_id": "agent-invalid@id",
    "allowed_pattern": "^[a-zA-Z0-9_-]{1,64}$"
  }
}
```

**Resolution**:

- Use only alphanumeric characters, hyphens, and underscores
- Keep agent IDs under 64 characters
- Avoid special characters like @, #, $, etc.

### `invalid_key`

**Description**: Key format validation failed for scratchpad operations.

**Common Causes**:

- Key contains invalid characters
- Key too long (>128 characters)
- Reserved key names used
- Empty key string

**Response Example**:

```json
{
  "success": false,
  "message": "Invalid key format: my-key@#$",
  "error_type": "invalid_key",
  "details": {
    "key": "my-key@#$",
    "max_length": 128,
    "allowed_chars": "alphanumeric, underscore, hyphen"
  }
}
```

**Resolution**:

- Use descriptive but short key names
- Only use letters, numbers, underscores, hyphens
- Avoid reserved names like "system", "config", "internal"

### `content_too_large`

**Description**: Content exceeds maximum size limit.

**Common Causes**:

- Large text content in scratchpad
- Base64 encoded files stored as content
- Uncompressed data storage
- Memory exhaustion prevention

**Response Example**:

```json
{
  "success": false,
  "message": "Content exceeds maximum size (100KB)",
  "error_type": "content_too_large",
  "details": {
    "content_size": 150000,
    "max_allowed": 100000,
    "unit": "bytes"
  }
}
```

**Resolution**:

- Compress large content before storage
- Split large content into multiple entries
- Use external storage for large files
- Store references instead of full content

### `invalid_ttl`

**Description**: TTL (Time To Live) value outside allowed range.

**Common Causes**:

- TTL less than 60 seconds
- TTL greater than 86400 seconds (24 hours)
- Negative TTL values
- Non-integer TTL values

**Response Example**:

```json
{
  "success": false,
  "message": "TTL must be between 60 and 86400 seconds",
  "error_type": "invalid_ttl",
  "details": {
    "provided_ttl": 30,
    "min_ttl": 60,
    "max_ttl": 86400
  }
}
```

**Resolution**:

- Use TTL between 1 minute and 24 hours
- For permanent storage, use graph or vector storage
- Consider appropriate TTL for your use case

---

## Storage Errors

### `storage_unavailable`

**Description**: Required storage backend is not available.

**Common Causes**:

- Redis server down or unreachable
- Network connectivity issues
- Authentication failures
- Service not started in Docker

**Response Example**:

```json
{
  "success": false,
  "message": "Redis storage not available",
  "error_type": "storage_unavailable",
  "details": {
    "backend": "redis",
    "last_check": "2024-01-15T10:30:00Z"
  }
}
```

**Resolution**:

- Check Docker services: `docker-compose ps`
- Verify Redis connectivity: `redis-cli ping`
- Check network configuration
- Review authentication settings

### `storage_error`

**Description**: Storage operation failed due to backend error.

**Common Causes**:

- Disk space exhaustion
- Database corruption
- Connection timeouts
- Resource limits exceeded

**Response Example**:

```json
{
  "success": false,
  "message": "Failed to store content in Redis",
  "error_type": "storage_error",
  "details": {
    "backend": "redis",
    "operation": "setex",
    "error": "NOSPACE No space left on device"
  }
}
```

**Resolution**:

- Check available disk space
- Monitor database health
- Review resource limits
- Check backend-specific logs

### `storage_exception`

**Description**: Unexpected exception during storage operation.

**Common Causes**:

- Network interruptions
- Backend software bugs
- Configuration mismatches
- Resource exhaustion

**Response Example**:

```json
{
  "success": false,
  "message": "Storage operation failed: Connection reset by peer",
  "error_type": "storage_exception",
  "details": {
    "backend": "redis",
    "exception_type": "ConnectionError"
  }
}
```

**Resolution**:

- Retry with exponential backoff
- Check network stability
- Review backend logs
- Verify configuration settings

---

## Access Control Errors

### `access_denied`

**Description**: Agent doesn't have access to the requested resource.

**Common Causes**:

- Trying to access other agent's data
- Namespace isolation violations
- Invalid resource ownership
- Security policy violations

**Response Example**:

```json
{
  "success": false,
  "message": "Access denied to requested resource",
  "error_type": "access_denied",
  "details": {
    "requested_resource": "agent:other-agent:scratchpad:secret",
    "requesting_agent": "current-agent"
  }
}
```

**Resolution**:

- Ensure correct agent ID in requests
- Verify resource ownership
- Check namespace configuration
- Review access control policies

---

## Query Errors

### `forbidden_operation`

**Description**: Query contains operations that are not allowed.

**Common Causes**:

- Write operations in read-only queries
- Dangerous Cypher operations
- Security policy violations
- Invalid query patterns

**Response Example**:

```json
{
  "success": false,
  "error": "Query validation failed: Write operations not allowed",
  "error_type": "forbidden_operation",
  "details": {
    "forbidden_keywords": ["CREATE", "DELETE", "SET"],
    "query_snippet": "CREATE (n:Node)"
  }
}
```

**Resolution**:

- Use only read operations (MATCH, RETURN, WHERE)
- Remove write operations from queries
- Use appropriate tools for data modification
- Review query validation rules

### `query_complexity_exceeded`

**Description**: Query complexity score exceeds allowed limits.

**Common Causes**:

- Cartesian product queries
- Deep graph traversals
- Missing LIMIT clauses
- Inefficient query patterns

**Response Example**:

```json
{
  "success": false,
  "error": "Query complexity score too high: 850 (max: 500)",
  "error_type": "query_complexity_exceeded",
  "details": {
    "complexity_score": 850,
    "max_allowed": 500,
    "suggestion": "Add LIMIT clause or reduce traversal depth"
  }
}
```

**Resolution**:

- Add LIMIT clauses to queries
- Reduce traversal depth
- Use more specific WHERE conditions
- Break complex queries into smaller parts

---

## Resource Errors

### `key_not_found`

**Description**: Requested key doesn't exist in storage.

**Common Causes**:

- Key expired due to TTL
- Key never created
- Typo in key name
- Wrong agent ID or prefix

**Response Example**:

```json
{
  "success": false,
  "message": "Key 'nonexistent_key' not found",
  "error_type": "key_not_found",
  "details": {
    "key": "nonexistent_key",
    "agent_id": "test-agent",
    "prefix": "scratchpad"
  }
}
```

**Resolution**:

- Verify key name spelling
- Check if key has expired
- Confirm agent ID and prefix
- Use list operations to see available keys

---

## Network Errors

### `connection_timeout`

**Description**: Connection to backend service timed out.

**Common Causes**:

- Network latency issues
- Backend service overloaded
- Firewall blocking connections
- DNS resolution problems

**Response Example**:

```json
{
  "success": false,
  "message": "Connection timeout to Neo4j service",
  "error_type": "connection_timeout",
  "details": {
    "service": "neo4j",
    "timeout_duration": "30s",
    "endpoint": "bolt://neo4j:7687"
  }
}
```

**Resolution**:

- Check network connectivity
- Verify service endpoints
- Review timeout configuration
- Monitor service health

---

## Error Handling Best Practices

### Client Implementation

```python
import time
import random

def call_mcp_tool_with_retry(client, tool_name, arguments, max_retries=3):
    """Call MCP tool with exponential backoff retry logic."""

    for attempt in range(max_retries):
        try:
            result = client.call_tool(tool_name, arguments)

            if result.get("success"):
                return result

            error_type = result.get("error_type")

            # Handle specific error types
            if error_type == "rate_limit":
                # Exponential backoff for rate limits
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
                continue

            elif error_type in ["storage_unavailable", "connection_timeout"]:
                # Brief wait for transient issues
                time.sleep(1)
                continue

            elif error_type in ["validation_error", "forbidden_operation"]:
                # Don't retry validation or security errors
                return result

            else:
                # Retry other errors once
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return result

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    return {"success": False, "message": "Max retries exceeded"}
```

### Monitoring and Alerting

Set up monitoring for these error patterns:

- **High rate limit errors**: May indicate need for scaling
- **Storage unavailable**: Critical backend issues
- **Validation errors**: Potential client bugs
- **Query complexity exceeded**: Performance issues

### Logging

Log errors with appropriate detail levels:

```python
import logging

logger = logging.getLogger(__name__)

def handle_mcp_error(result):
    """Log MCP errors appropriately."""

    error_type = result.get("error_type")
    message = result.get("message")

    if error_type == "rate_limit":
        logger.warning(f"Rate limit hit: {message}")
    elif error_type in ["storage_unavailable", "storage_error"]:
        logger.error(f"Storage issue: {message}")
    elif error_type == "validation_error":
        logger.info(f"Validation failed: {message}")
    else:
        logger.error(f"Unexpected error ({error_type}): {message}")
```

### Health Checks

Implement health checks to detect error conditions:

```bash
# Check Context Store health
curl -f http://localhost:8000/health || echo "Context Store unhealthy"

# Check individual services
curl -f http://localhost:6333/health || echo "Qdrant unhealthy"
curl -f http://localhost:7474 || echo "Neo4j unhealthy"
redis-cli ping || echo "Redis unhealthy"
```

## Support Resources

- **Health Endpoint**: `GET /health` for service status
- **Logs**: `docker-compose logs context-store`
- **Metrics**: Available at `:9090/metrics` if enabled
- **Documentation**: [MCP Tools Reference](MCP_TOOLS.md)
- **Issues**: [GitHub Issues](https://github.com/credentum/context-store/issues)
