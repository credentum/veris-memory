# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the Context Store MCP server.

## Quick Diagnostics

### Health Check Commands

```bash
# Overall system health
curl http://localhost:8000/health

# Individual services
curl http://localhost:6333/health        # Qdrant
curl http://localhost:7474              # Neo4j Browser
redis-cli ping                          # Redis

# Docker services status
docker-compose ps

# Service logs
docker-compose logs context-store
docker-compose logs qdrant
docker-compose logs neo4j
docker-compose logs redis
```

### Common Quick Fixes

```bash
# Restart all services
docker-compose restart

# Restart with fresh data
docker-compose down -v
docker-compose up -d

# Check port conflicts
netstat -tlnp | grep -E ':(8000|6333|7687|6379)'

# Verify environment variables
cat .env
```

## Installation Issues

### Problem: `docker-compose up -d` fails

**Symptoms**:

```
ERROR: Couldn't connect to Docker daemon
ERROR: Version in "./docker-compose.yml" is unsupported
```

**Solutions**:

1. **Docker not running**:

   ```bash
   # Start Docker service
   sudo systemctl start docker
   # Or start Docker Desktop
   ```

2. **Docker Compose version**:

   ```bash
   # Check version
   docker-compose --version

   # Upgrade if needed
   pip install --upgrade docker-compose
   ```

3. **Permissions**:
   ```bash
   # Add user to docker group
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

### Problem: Port conflicts

**Symptoms**:

```
ERROR: for context-store  Cannot start service context-store:
driver failed programming external connectivity on endpoint:
bind: address already in use
```

**Solutions**:

1. **Find process using port**:

   ```bash
   sudo lsof -i :8000
   sudo kill -9 <PID>
   ```

2. **Use different ports**:

   ```bash
   # Edit .env file
   MCP_SERVER_PORT=8001
   QDRANT_PORT=6334
   NEO4J_HTTP_PORT=7475
   NEO4J_BOLT_PORT=7688
   REDIS_PORT=6380
   ```

3. **Stop conflicting services**:
   ```bash
   # Stop other docker containers
   docker stop $(docker ps -q)
   ```

## Service Startup Issues

### Problem: Neo4j fails to start

**Symptoms**:

```
neo4j_1  | Invalid value for setting 'dbms.default_database': ''
neo4j_1  | FATAL: Failed to start the Neo4j service
```

**Solutions**:

1. **Check password**:

   ```bash
   # Ensure NEO4J_PASSWORD is set in .env
   grep NEO4J_PASSWORD .env
   ```

2. **Clear Neo4j data**:

   ```bash
   docker-compose down
   docker volume rm context-store_neo4j_data
   docker-compose up -d
   ```

3. **Check memory limits**:
   ```bash
   # Increase Docker memory to at least 4GB
   # Check Docker settings
   ```

### Problem: Qdrant connection errors

**Symptoms**:

```
qdrant_1  | thread 'tokio-runtime-worker' panicked
context-store_1 | qdrant.exceptions.UnexpectedResponse:
Unexpected Response: 503 Service Unavailable
```

**Solutions**:

1. **Wait for initialization**:

   ```bash
   # Qdrant needs 30-60 seconds to initialize
   sleep 60 && curl http://localhost:6333/health
   ```

2. **Check disk space**:

   ```bash
   df -h
   # Ensure at least 1GB free space
   ```

3. **Reset Qdrant data**:
   ```bash
   docker-compose down
   docker volume rm context-store_qdrant_data
   docker-compose up -d
   ```

### Problem: Redis memory issues

**Symptoms**:

```
redis_1  | # WARNING: /proc/sys/vm/overcommit_memory is set to 0!
redis_1  | # Can't save in background: fork: Cannot allocate memory
```

**Solutions**:

1. **System configuration**:

   ```bash
   # Fix overcommit memory
   echo 'vm.overcommit_memory = 1' | sudo tee -a /etc/sysctl.conf
   sudo sysctl vm.overcommit_memory=1
   ```

2. **Reduce Redis memory**:
   ```bash
   # Edit docker-compose.yml
   command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
   ```

## API Issues

### Problem: MCP tools return "tool not found"

**Symptoms**:

```json
{
  "success": false,
  "error": "Unknown tool: store_context"
}
```

**Solutions**:

1. **Check server startup**:

   ```bash
   docker-compose logs context-store | grep "tools registered"
   ```

2. **Verify endpoint**:

   ```bash
   curl http://localhost:8000/mcp/list_tools
   ```

3. **Check API format**:
   ```json
   {
     "method": "call_tool",
     "params": {
       "name": "store_context",
       "arguments": {...}
     }
   }
   ```

### Problem: Rate limiting errors

**Symptoms**:

```json
{
  "success": false,
  "message": "Rate limit exceeded: 50 requests per minute",
  "error_type": "rate_limit"
}
```

**Solutions**:

1. **Implement backoff**:

   ```python
   import time

   def call_with_backoff(client, tool, args, max_retries=3):
       for i in range(max_retries):
           result = client.call_tool(tool, args)
           if result.get("error_type") != "rate_limit":
               return result
           time.sleep(2 ** i)  # Exponential backoff
       return result
   ```

2. **Adjust rate limits** (advanced):
   ```python
   # In server configuration
   RATE_LIMITS = {
       "store_context": 200,    # requests per minute
       "retrieve_context": 100,
       "query_graph": 50
   }
   ```

### Problem: Validation errors

**Symptoms**:

```json
{
  "success": false,
  "message": "Validation failed: missing required field 'type'",
  "error_type": "validation_error"
}
```

**Solutions**:

1. **Check required fields**:

   ```json
   {
     "content": { "title": "Required" },
     "type": "design" // Required field
   }
   ```

2. **Validate data types**:
   ```python
   # Ensure correct types
   arguments = {
       "content": dict(),        # Must be object
       "type": str(),           # Must be string
       "limit": int(),          # Must be integer
       "ttl": int()             # Must be integer
   }
   ```

## Performance Issues

### Problem: Slow response times

**Symptoms**:

- MCP tool calls taking >5 seconds
- High CPU usage
- Memory exhaustion

**Solutions**:

1. **Check resource usage**:

   ```bash
   docker stats
   htop
   ```

2. **Optimize queries**:

   ```cypher
   -- Bad: Cartesian product
   MATCH (a:Context), (b:Context) RETURN a, b

   -- Good: Specific relationships
   MATCH (a:Context)-[:RELATES_TO]->(b:Context)
   WHERE a.type = 'design'
   RETURN a, b LIMIT 10
   ```

3. **Increase resources**:
   ```yaml
   # docker-compose.yml
   services:
     context-store:
       deploy:
         resources:
           limits:
             memory: 2G
             cpus: "1.0"
   ```

### Problem: Memory leaks

**Symptoms**:

- Memory usage continuously growing
- Out of memory errors
- Container restarts

**Solutions**:

1. **Monitor memory**:

   ```bash
   # Watch memory usage
   watch 'docker stats --no-stream'
   ```

2. **Connection management**:

   ```python
   # Always close MCP clients
   async with MCPClient(url) as client:
       result = await client.call_tool(...)
   # Client automatically closed
   ```

3. **Restart periodically**:
   ```bash
   # Add to crontab for periodic restart
   0 2 * * * cd /path/to/context-store && docker-compose restart
   ```

## Data Issues

### Problem: Context not found after storage

**Symptoms**:

```json
{
  "success": true,
  "results": [],
  "message": "Found 0 matching contexts"
}
```

**Solutions**:

1. **Check storage backends**:

   ```bash
   curl http://localhost:8000/health
   # Verify all services are "healthy"
   ```

2. **Wait for indexing**:

   ```bash
   # Vector embeddings may take time to index
   sleep 30
   # Then retry retrieval
   ```

3. **Check search parameters**:
   ```json
   {
     "query": "exact title match", // Try exact matches first
     "search_mode": "hybrid", // Use hybrid search
     "limit": 50 // Increase limit
   }
   ```

### Problem: Graph relationships missing

**Symptoms**:

- Graph queries return no relationships
- `query_graph` shows isolated nodes

**Solutions**:

1. **Verify relationship creation**:

   ```json
   {
     "name": "store_context",
     "arguments": {
       "content": {...},
       "type": "design",
       "relationships": [
         {"type": "implements", "target": "req-001"}
       ]
     }
   }
   ```

2. **Check target nodes exist**:

   ```cypher
   MATCH (n:Context) WHERE n.id = 'req-001' RETURN n
   ```

3. **Manual relationship creation**:
   ```json
   {
     "name": "query_graph",
     "arguments": {
       "query": "MATCH (a:Context {id: 'ctx_123'}), (b:Context {id: 'req-001'}) CREATE (a)-[:IMPLEMENTS]->(b)"
     }
   }
   ```

## Network Issues

### Problem: Cannot connect to MCP server

**Symptoms**:

```
ConnectionError: [Errno 111] Connection refused
requests.exceptions.ConnectTimeout
```

**Solutions**:

1. **Check server is running**:

   ```bash
   docker-compose ps
   curl -I http://localhost:8000
   ```

2. **Verify firewall**:

   ```bash
   # Check if port is accessible
   telnet localhost 8000

   # Check firewall rules
   sudo ufw status
   ```

3. **Network configuration**:
   ```bash
   # Check Docker network
   docker network ls
   docker network inspect context-store_context-store-network
   ```

### Problem: SSL/TLS errors

**Symptoms**:

```
SSL: CERTIFICATE_VERIFY_FAILED
ssl.SSLError: [SSL: WRONG_VERSION_NUMBER]
```

**Solutions**:

1. **Disable SSL for local development**:

   ```env
   # .env
   NEO4J_DISABLE_SSL=true
   QDRANT_DISABLE_SSL=true
   REDIS_DISABLE_SSL=true
   ```

2. **Check certificate configuration**:
   ```bash
   # Verify SSL settings in docker-compose.yml
   # Ensure certificate files exist and are readable
   ```

## Environment Issues

### Problem: Environment variables not loaded

**Symptoms**:

```
KeyError: 'NEO4J_PASSWORD'
Environment variable not set
```

**Solutions**:

1. **Check .env file**:

   ```bash
   # Verify .env exists and has correct format
   ls -la .env
   cat .env | grep -v '^#' | grep '='
   ```

2. **Docker Compose env loading**:

   ```bash
   # Ensure docker-compose.yml references .env
   grep -A5 environment docker-compose.yml
   ```

3. **Manual environment export**:
   ```bash
   # Load environment manually
   export $(cat .env | grep -v '^#' | xargs)
   docker-compose up -d
   ```

## Debugging Tools

### Log Analysis

```bash
# Get all logs
docker-compose logs > context-store-logs.txt

# Follow logs in real-time
docker-compose logs -f

# Service-specific logs with timestamps
docker-compose logs -t context-store
docker-compose logs -t qdrant
docker-compose logs -t neo4j
docker-compose logs -t redis

# Search for errors
docker-compose logs | grep -i error
docker-compose logs | grep -i "failed\|exception\|timeout"
```

### Connection Testing

```bash
# Test MCP endpoints
curl -X POST http://localhost:8000/mcp/list_tools
curl -X POST http://localhost:8000/mcp/list_resources
curl http://localhost:8000/health

# Test database connections
curl http://localhost:6333/health
curl http://localhost:7474
redis-cli ping

# Test from inside containers
docker exec -it context-store_context-store_1 curl http://qdrant:6333/health
docker exec -it context-store_context-store_1 curl http://neo4j:7474
```

### Performance Monitoring

```bash
# Resource usage
docker stats --no-stream

# Database-specific monitoring
curl http://localhost:6333/metrics    # Qdrant metrics
curl http://localhost:7474/db/data/   # Neo4j API

# System monitoring
htop
iotop
```

## FAQ

### Q: Can I run Context Store without Docker?

**A**: Yes, but it's more complex:

```bash
# Install dependencies
pip install -r requirements.txt

# Start databases manually
qdrant-server &
neo4j start
redis-server &

# Set environment variables
export NEO4J_PASSWORD=your_password
export QDRANT_URL=http://localhost:6333
export REDIS_URL=redis://localhost:6379

# Start MCP server
python -m src.mcp_server.main
```

### Q: How do I backup Context Store data?

**A**: Backup the Docker volumes:

```bash
# Stop services
docker-compose down

# Backup volumes
docker run --rm -v context-store_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j-backup.tar.gz -C /data .
docker run --rm -v context-store_qdrant_data:/data -v $(pwd):/backup alpine tar czf /backup/qdrant-backup.tar.gz -C /data .
docker run --rm -v context-store_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .

# Restart services
docker-compose up -d
```

### Q: How do I scale Context Store?

**A**: Use Docker Compose scaling:

```bash
# Scale MCP servers
docker-compose up -d --scale context-store=3

# Use load balancer (nginx, traefik)
# Configure multiple endpoints in client
```

### Q: Can I use external databases?

**A**: Yes, update the connection strings:

```env
# .env
QDRANT_URL=http://your-qdrant-server:6333
NEO4J_URI=bolt://your-neo4j-server:7687
REDIS_URL=redis://your-redis-server:6379
```

### Q: How do I monitor Context Store in production?

**A**: Use monitoring tools:

```bash
# Enable metrics endpoint
# Add to docker-compose.yml
environment:
  - ENABLE_METRICS=true
  - METRICS_PORT=9090

# Access metrics
curl http://localhost:9090/metrics

# Use Prometheus + Grafana for monitoring
```

### Q: What's the maximum context size?

**A**: Current limits:

- **Context content**: No hard limit (practical limit ~10MB per context)
- **Scratchpad content**: 100KB per entry
- **Query results**: 1000 rows max
- **Concurrent connections**: 100 by default

### Q: How do I update Context Store?

**A**: Update with Docker:

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose down
docker-compose up -d

# Verify update
curl http://localhost:8000/health
```

## Getting Help

### Before asking for help:

1. **Check logs**: `docker-compose logs`
2. **Verify health**: `curl http://localhost:8000/health`
3. **Test basic functionality**: Run hello world example
4. **Check documentation**: Read relevant guide sections

### Where to get help:

- **GitHub Issues**: [Bug reports and feature requests](https://github.com/credentum/context-store/issues)
- **GitHub Discussions**: [Questions and community help](https://github.com/credentum/context-store/discussions)
- **Documentation**: [Complete documentation](../README.md)

### Information to include when reporting issues:

```bash
# System information
uname -a
docker --version
docker-compose --version

# Service status
docker-compose ps
curl -s http://localhost:8000/health | jq

# Recent logs
docker-compose logs --tail=50

# Environment (redact sensitive info)
cat .env | sed 's/=.*/=***/'
```
