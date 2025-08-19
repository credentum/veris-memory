# Veris Memory Monitoring Dashboard

The Veris Memory monitoring dashboard provides comprehensive system monitoring with dual-format output (JSON for agents, ASCII for humans) and real-time streaming capabilities.

## Overview

The monitoring dashboard is a production-ready system that collects and visualizes metrics from all Veris Memory components:

- **System Resources**: CPU, memory, disk usage, load average, uptime
- **Service Health**: Status monitoring for Redis, Neo4j, Qdrant, MCP Server
- **Veris Metrics**: Memory operations, query performance, error rates
- **Security Status**: Authentication failures, WAF blocks, SSL certificate status
- **Backup Status**: Backup health, restore testing, offsite synchronization

## Quick Start

### Basic Usage

```python
from src.monitoring.dashboard import UnifiedDashboard

# Initialize dashboard
dashboard = UnifiedDashboard()

# Get JSON metrics for agents
metrics = await dashboard.collect_all_metrics()
json_output = dashboard.generate_json_dashboard(metrics)

# Get ASCII dashboard for humans
ascii_output = dashboard.generate_ascii_dashboard(metrics)
print(ascii_output)

# Clean shutdown
await dashboard.shutdown()
```

### Command Line Testing

```bash
# Test core dashboard functionality
python3 scripts/test_dashboard.py

# Run verification tests
python3 tests/verification/run_all_tests.py
python3 tests/verification/run_all_tests.py --quick
```

## Features

### Dual Format Output

#### JSON Format (Agent-Friendly)
- Structured data perfect for programmatic consumption
- Complete metrics with timestamps and metadata
- Configurable pretty-printing
- Internal timing information
- Trend analysis data

#### ASCII Format (Human-Friendly)
- Beautiful progress bars with emoji indicators
- Color-coded status displays (green/yellow/red)
- Terminal capability detection
- Automatic width adjustment
- Emoji fallbacks for limited terminals

### Real-Time Streaming

- WebSocket-based streaming for live updates
- Configurable refresh intervals (5-300 seconds)
- Delta compression for bandwidth optimization
- Client subscription management
- Adaptive refresh rates

### Integration with MetricsCollector

The dashboard integrates seamlessly with the existing `MetricsCollector`:

- Uses time-series data from collector when available
- Falls back to direct collection if needed
- Leverages existing system metric collectors
- Provides enhanced visualization of collected data

## Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌────────────────────┐
│   UnifiedDashboard  │    │   MetricsCollector   │    │   HealthChecker    │
│                     │────│                      │────│                    │
│ - Collect metrics   │    │ - Time series data   │    │ - Service health   │
│ - Generate output   │    │ - Built-in collectors│    │ - Status checks    │
│ - Cache management  │    │ - Custom collectors  │    │ - Dependency tests │
└─────────────────────┘    └──────────────────────┘    └────────────────────┘
           │
           ├── ASCIIRenderer ──── Terminal capability detection
           └── DashboardAPI  ──── WebSocket + REST endpoints
```

## Configuration

### Dashboard Configuration

```python
config = {
    'refresh_interval_seconds': 5,
    'cache_duration_seconds': 30,
    'ascii': {
        'width': 80,
        'use_color': True,
        'use_emoji': True,
        'progress_bar_width': 10
    },
    'json': {
        'pretty_print': True,
        'include_internal_timing': True,
        'include_trends': True
    },
    'thresholds': {
        'memory_warning_percent': 80,
        'memory_critical_percent': 95,
        'disk_warning_percent': 85,
        'disk_critical_percent': 95,
        'cpu_warning_percent': 80,
        'cpu_critical_percent': 95,
        'error_rate_warning_percent': 1.0,
        'error_rate_critical_percent': 5.0,
        'latency_warning_ms': 100,
        'latency_critical_ms': 500
    }
}

dashboard = UnifiedDashboard(config)
```

### ASCII Rendering Options

The ASCII renderer automatically detects terminal capabilities:

- **Color Support**: Checks TERM, COLORTERM, NO_COLOR environment variables
- **Emoji Support**: Detects UTF-8 locales and modern terminal emulators
- **Width Detection**: Uses terminal size or falls back to environment variables
- **Graceful Degradation**: Safe defaults for limited terminals

## API Endpoints

### REST API

```bash
# Get dashboard metrics (JSON)
GET /api/dashboard

# Get ASCII dashboard
GET /api/dashboard?format=ascii

# Get specific sections
GET /api/dashboard?sections=system,services

# Force refresh metrics
POST /api/dashboard/refresh
```

### Docker Network Access

When running in Docker Compose, the dashboard is accessible at:

```bash
# From other containers in the same network
http://monitoring-dashboard:8080/api/dashboard

# From Docker host
http://localhost:8080/api/dashboard

# From Docker containers to host services
http://172.17.0.1:8080/api/dashboard
```

### WebSocket API

```javascript
// Connect to dashboard stream
const ws = new WebSocket('ws://localhost:8080/ws/dashboard');

// Configure stream
ws.send(JSON.stringify({
    format: 'json',
    sections: ['system', 'services'],
    refresh_interval_seconds: 30
}));

// Receive updates
ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    console.log('Dashboard update:', update);
};
```

## MCP Integration

The dashboard is fully integrated with the MCP (Model Context Protocol) system via tool contracts:

### Available MCP Tools

1. **`get_dashboard_metrics`**
   - Retrieve dashboard metrics in JSON or ASCII format
   - Filter by sections (system, services, veris, security, backups)
   - Force refresh option to bypass cache

2. **`stream_dashboard_updates`**
   - Establish WebSocket streaming connection
   - Configurable refresh intervals and filtering
   - Real-time metrics updates

3. **`run_verification_tests`**
   - Execute TLS/mTLS verification tests
   - Run backup restore drill simulations
   - Comprehensive test suite with reporting

### MCP Tool Usage

```python
# Via MCP client
response = await mcp_client.call_tool("get_dashboard_metrics", {
    "format": "json",
    "sections": ["system", "veris"],
    "force_refresh": True
})

# Streaming updates
stream_response = await mcp_client.call_tool("stream_dashboard_updates", {
    "websocket_endpoint": "ws://localhost:8080/ws/dashboard",
    "format": "ascii",
    "refresh_interval_seconds": 30
})
```

## Verification Testing

The dashboard includes standalone verification test scripts:

### Test Scripts

- **`tests/verification/tls_verifier.py`**: TLS/mTLS configuration testing
- **`tests/verification/restore_drill.py`**: Backup restore procedure testing
- **`tests/verification/run_all_tests.py`**: Comprehensive test runner

### Test Features

- **Realistic Error Simulation**: Environment variable controlled failures
- **Comprehensive Error Handling**: Network, SSL, filesystem, and timeout errors
- **Mock Implementations**: Safe testing without affecting production systems
- **Detailed Reporting**: JSON, summary, and detailed output formats

### Running Tests

```bash
# Individual tests
python3 tests/verification/tls_verifier.py
python3 tests/verification/restore_drill.py

# Test suite
python3 tests/verification/run_all_tests.py

# Quick check
python3 tests/verification/run_all_tests.py --quick

# Simulate failures for testing
MOCK_RESTORE_FAILURE=redis python3 tests/verification/restore_drill.py
MOCK_VERIFICATION_FAILURE=redis python3 tests/verification/restore_drill.py
```

## Sample Output

### ASCII Dashboard Example

```
🎯 VERIS MEMORY STATUS - Thu Aug 14 18:41 UTC
════════════════════════════════════════════════

💾 SYSTEM RESOURCES
CPU    [░░░░░░░░░░] 0.9% ✅ HEALTHY
Memory [░░░░░░░░░░] 5.8% (2.9GB/62.7GB) ✅ HEALTHY  
Disk   [█░░░░░░░░░] 16.2% (70.5GB/435.8GB) ✅ HEALTHY
Load   ⚡ 0.13 0.26 0.26 ✅ LOW
Uptime 7.0 days

🔧 SERVICE HEALTH
Redis        ✅ Healthy (6379)
Neo4j HTTP   ✅ Healthy (7474)
Neo4j Bolt   ✅ Healthy (7687)
Qdrant       ✅ Healthy (6334)
MCP Server   ✅ Healthy (8080)

🧠 VERIS METRICS
Total Memories: 84,532 (+1,247 today ↗️)
Query Latency:  23ms avg | 89ms p99 ⚡ FAST
Error Rate:     0.02% 🎯 EXCELLENT
Active Agents:  5 🤖

🛡️ SECURITY STATUS
Auth Failures:  0 ✅
Blocked IPs:    0 ✅
WAF Blocks:     12 today
SSL Expires:    87 days ✅ OK
RBAC Violations: 0 ✅

💾 BACKUP STATUS
Last Backup:    3h ago ✅
Backup Size:    4.7 GB
Restore Test:   PASSED (142s) ✅
Offsite Sync:   HEALTHY ✅
```

### JSON Output Example

```json
{
  "timestamp": "2025-08-14T18:41:00Z",
  "system": {
    "cpu_percent": 0.9,
    "memory_total_gb": 62.7,
    "memory_used_gb": 2.9,
    "memory_percent": 5.8,
    "disk_total_gb": 435.8,
    "disk_used_gb": 70.5,
    "disk_percent": 16.2,
    "load_average": [0.13, 0.26, 0.26],
    "uptime_hours": 168.0
  },
  "services": [
    {
      "name": "Redis",
      "status": "healthy",
      "port": 6379,
      "uptime_hours": 24.5,
      "connections": 12
    }
  ],
  "veris": {
    "total_memories": 84532,
    "memories_today": 1247,
    "avg_query_latency_ms": 23.0,
    "p99_latency_ms": 89.0,
    "error_rate_percent": 0.02,
    "active_agents": 5
  }
}
```

## Performance Considerations

### Caching Strategy
- Default cache duration: 30 seconds
- Force refresh available for real-time needs
- Cache invalidation on metric changes
- Memory-efficient storage

### Resource Usage
- Minimal CPU overhead during normal operation
- Memory usage scales with retention period
- Network bandwidth optimized for streaming
- Graceful degradation under high load

### Scalability
- Concurrent client support via WebSocket pooling
- Rate limiting prevents abuse
- Delta updates reduce bandwidth usage
- Adaptive refresh rates based on client needs

## Troubleshooting

### Common Issues

1. **Missing psutil dependency**
   ```bash
   pip install psutil
   ```

2. **Terminal display issues**
   - Check TERM and LANG environment variables
   - Use `NO_COLOR=1` to disable colors
   - Terminal may not support Unicode/emoji

3. **WebSocket connection failures**
   - Verify firewall settings
   - Check if port is available
   - Ensure CORS configuration

4. **High memory usage**
   - Reduce metrics retention period
   - Lower refresh frequency
   - Check for metric collector leaks

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

dashboard = UnifiedDashboard()
# Detailed logging will show metric collection details
```

## Contributing

### Adding New Metrics

1. **Extend data classes** in `dashboard.py`
2. **Add collection methods** following existing patterns
3. **Update ASCII renderer** with new display logic
4. **Add configuration options** for thresholds

### Adding New Visualizations

1. **Extend ASCIIRenderer** with new rendering methods
2. **Add terminal capability checks** if needed
3. **Update configuration schema** for new options
4. **Test across different terminal types**

## Security Considerations

- No sensitive data exposed in metrics output
- Rate limiting prevents resource abuse
- Input validation on all configuration parameters
- Secure WebSocket connections with authentication
- Audit logging for administrative actions

## License

This monitoring dashboard is part of the Veris Memory project and follows the same licensing terms.