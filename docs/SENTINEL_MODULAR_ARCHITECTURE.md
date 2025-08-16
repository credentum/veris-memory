# Sentinel Modular Architecture

## Overview

The Veris Sentinel has been refactored from a monolithic 1,800+ line file into a modular architecture for better maintainability, testability, and extensibility.

## Architecture Overview

```
src/monitoring/sentinel/
├── __init__.py              # Main package exports
├── models.py                # Data models (CheckResult, SentinelConfig)
├── base_check.py            # Base check interface and mixins
├── runner.py                # Core orchestration and scheduling
├── api.py                   # Web API endpoints
├── checks/                  # Individual check modules
│   ├── __init__.py         # Check registry and exports
│   ├── s1_health_probes.py # Health endpoint monitoring
│   ├── s2_golden_fact_recall.py # Data integrity testing
│   ├── s3_paraphrase_robustness.py # Semantic consistency
│   ├── s4_metrics_wiring.py # Monitoring infrastructure
│   ├── s5_security_negatives.py # RBAC and security
│   ├── s6_backup_restore.py # Data protection
│   ├── s7_config_parity.py # Configuration drift
│   ├── s8_capacity_smoke.py # Performance limits
│   ├── s9_graph_intent.py  # Graph query validation
│   └── s10_content_pipeline.py # Data processing
└── sentinel_migration.py   # Migration utilities and examples
```

## Key Components

### 1. Models (`models.py`)

Core data structures used throughout the system:

```python
from src.monitoring.sentinel import CheckResult, SentinelConfig

# Configuration
config = SentinelConfig.from_env()
config = SentinelConfig(
    target_base_url="http://localhost:8000",
    check_interval_seconds=60,
    enabled_checks=["S1-probes", "S2-golden-fact-recall"]
)

# Results
result = CheckResult(
    check_id="S1-probes",
    timestamp=datetime.utcnow(),
    status="pass",  # "pass", "warn", "fail"
    latency_ms=150.0,
    message="All endpoints healthy",
    details={"additional": "data"}
)
```

### 2. Base Check Interface (`base_check.py`)

All checks inherit from `BaseCheck` and implement the `run_check()` method:

```python
from src.monitoring.sentinel.base_check import BaseCheck, HealthCheckMixin

class MyCustomCheck(BaseCheck, HealthCheckMixin):
    def __init__(self, config: SentinelConfig):
        super().__init__(config, "MY-check", "My custom check description")
    
    async def run_check(self) -> CheckResult:
        # Your check implementation
        return CheckResult(...)
```

**Available Mixins:**
- `HealthCheckMixin`: HTTP endpoint health checking utilities
- `APITestMixin`: API call testing utilities

### 3. Check Registry (`checks/__init__.py`)

All checks are automatically registered and can be enabled/disabled via configuration:

```python
from src.monitoring.sentinel.checks import CHECK_REGISTRY

# Available checks
print(CHECK_REGISTRY.keys())
# ['S1-probes', 'S2-golden-fact-recall', ...]

# Create check instance
check_class = CHECK_REGISTRY['S1-probes']
check_instance = check_class(config)
```

### 4. Runner (`runner.py`)

Core orchestration engine that manages check execution, scheduling, and persistence:

```python
from src.monitoring.sentinel import SentinelRunner, SentinelConfig

config = SentinelConfig.from_env()
runner = SentinelRunner(config)

# Start monitoring
await runner.start()

# Get status
status = runner.get_status_summary()
```

### 5. API (`api.py`)

RESTful web interface for controlling and monitoring Sentinel:

```python
from src.monitoring.sentinel import SentinelAPI

api = SentinelAPI(runner, config)
app = api.get_app()

# Start server
await api.start_server(host='0.0.0.0', port=9090)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Overall Sentinel status |
| GET | `/checks` | List all checks and their status |
| GET | `/checks/{check_id}` | Detailed check information |
| GET | `/checks/{check_id}/history` | Check execution history |
| POST | `/checks/{check_id}/run` | Manually run a specific check |
| GET | `/health` | API health check |
| POST | `/start` | Start monitoring loop |
| POST | `/stop` | Stop monitoring loop |

### Example API Usage

```bash
# Get overall status
curl http://localhost:9090/status

# List all checks
curl http://localhost:9090/checks

# Get specific check details
curl http://localhost:9090/checks/S1-probes

# Run a check manually
curl -X POST http://localhost:9090/checks/S1-probes/run

# Start monitoring
curl -X POST http://localhost:9090/start
```

## Individual Checks

### S1: Health Probes (`s1_health_probes.py`)
- Tests `/health/live` and `/health/ready` endpoints
- Validates component health (Qdrant, Neo4j, Redis)
- **Status**: Fully implemented

### S2: Golden Fact Recall (`s2_golden_fact_recall.py`)
- Tests store/retrieve functionality with known facts
- Validates natural language queries return expected results
- **Status**: Fully implemented

### S3-S10: Remaining Checks
- All other checks have placeholder implementations
- Each check follows the same pattern and can be expanded
- **Status**: Modular structure ready, implementation TBD

## Configuration

### Environment Variables

```bash
# Target system to monitor
export SENTINEL_TARGET_URL="http://localhost:8000"

# Check execution interval (seconds)
export SENTINEL_CHECK_INTERVAL=60

# Alert threshold (failures before alerting)
export SENTINEL_ALERT_THRESHOLD=3

# External integrations (optional)
export SENTINEL_WEBHOOK_URL="https://hooks.slack.com/..."
export GITHUB_TOKEN="ghp_..."
export SENTINEL_GITHUB_REPO="user/repo"

# Enable specific checks (comma-separated)
export SENTINEL_ENABLED_CHECKS="S1-probes,S2-golden-fact-recall,S3-paraphrase-robustness"
```

### Programmatic Configuration

```python
config = SentinelConfig(
    target_base_url="http://localhost:8000",
    check_interval_seconds=30,
    alert_threshold_failures=2,
    webhook_url="https://hooks.slack.com/services/...",
    github_token="ghp_...",
    github_repo="myorg/myrepo",
    enabled_checks=["S1-probes", "S2-golden-fact-recall"]
)
```

## Running the Modular Sentinel

### 1. Basic Usage

```python
import asyncio
from src.monitoring.sentinel import SentinelConfig, SentinelRunner, SentinelAPI

async def main():
    # Create configuration
    config = SentinelConfig.from_env()
    
    # Create runner
    runner = SentinelRunner(config)
    
    # Create API
    api = SentinelAPI(runner, config)
    
    # Start API server
    await api.start_server(port=9090)
    
    # Start monitoring
    await runner.start()

asyncio.run(main())
```

### 2. Docker Deployment

```yaml
version: '3.8'
services:
  sentinel:
    build:
      context: .
      dockerfile: docker/Dockerfile.sentinel
    ports:
      - "9090:9090"
    environment:
      - SENTINEL_TARGET_URL=http://veris-memory:8000
      - SENTINEL_CHECK_INTERVAL=60
    volumes:
      - sentinel_data:/var/lib/sentinel
    depends_on:
      - veris-memory

volumes:
  sentinel_data:
```

### 3. Systemd Service

```ini
[Unit]
Description=Veris Sentinel Monitoring
After=network.target

[Service]
Type=exec
User=sentinel
WorkingDirectory=/opt/veris-memory
ExecStart=/usr/bin/python3 -m src.monitoring.sentinel_migration
Environment=SENTINEL_TARGET_URL=http://localhost:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Migration from Legacy

### Backward Compatibility

The modular system is designed to be backward compatible:

```python
# Legacy import (still works)
from src.monitoring.veris_sentinel import SentinelRunner as LegacyRunner

# New modular import
from src.monitoring.sentinel import SentinelRunner as ModularRunner

# Migration manager helps transition
from src.monitoring.sentinel_migration import SentinelMigrationManager

migration = SentinelMigrationManager()
runner, api = migration.setup_modular_sentinel()
```

### Data Migration

```python
# Migrate data from legacy database
migration_manager = SentinelMigrationManager()
success = await migration_manager.migrate_data(
    legacy_db_path="/old/sentinel.db",
    new_db_path="/new/sentinel.db"
)
```

## Benefits of Modular Architecture

### 1. **Maintainability**
- Each check is self-contained (50-150 lines vs 1,800+ monolithic)
- Clear separation of concerns
- Easier to debug and test individual components

### 2. **Extensibility**
- Easy to add new checks by implementing `BaseCheck`
- Plugin-like architecture with automatic registration
- Mixins provide reusable functionality

### 3. **Testability**
- Individual checks can be tested in isolation
- Mock configurations and dependencies easily
- Better code coverage possible

### 4. **Configurability**
- Enable/disable checks without code changes
- Environment-based configuration
- Runtime check management via API

### 5. **Observability**
- Better structured logging per component
- Detailed metrics and statistics per check
- API provides real-time insight

## Development Guidelines

### Adding a New Check

1. Create new file in `checks/` directory:
```python
# checks/s11_my_new_check.py
from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig

class MyNewCheck(BaseCheck):
    def __init__(self, config: SentinelConfig):
        super().__init__(config, "S11-my-check", "My new check description")
    
    async def run_check(self) -> CheckResult:
        # Implementation here
        return CheckResult(...)
```

2. Register in `checks/__init__.py`:
```python
from .s11_my_new_check import MyNewCheck

CHECK_REGISTRY = {
    # ... existing checks ...
    "S11-my-check": MyNewCheck,
}
```

3. Add to configuration and test:
```python
config = SentinelConfig(enabled_checks=["S11-my-check"])
```

### Best Practices

1. **Use mixins** for common functionality (HTTP checks, API calls)
2. **Include detailed error information** in CheckResult.details
3. **Use appropriate timeouts** for async operations
4. **Log appropriately** - debug for normal operation, warning/error for issues
5. **Test both success and failure paths**
6. **Document check purpose and expected behavior**

## Performance Considerations

- **Concurrent execution**: Checks run concurrently using asyncio
- **Configurable intervals**: Adjust check frequency based on needs
- **Resource limits**: Each check has timeout protection
- **Data retention**: Ring buffers prevent unbounded memory growth
- **Database efficiency**: SQLite with proper indexing for persistence

## Future Enhancements

1. **Check Dependencies**: Allow checks to depend on others
2. **Dynamic Configuration**: Runtime configuration updates
3. **Plugin System**: External check plugins
4. **Advanced Alerting**: Integration with PagerDuty, OpsGenie, etc.
5. **Metrics Export**: Prometheus metrics endpoint
6. **Check Scheduling**: Cron-like scheduling for different checks
7. **Distributed Monitoring**: Multi-instance coordination