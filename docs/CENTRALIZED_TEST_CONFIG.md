# Centralized Test Configuration System

## Overview

The test configuration system has been centralized to eliminate hardcoded test data scattered throughout the codebase. All test configurations, credentials, and sample data are now managed through a single YAML configuration file.

## Configuration File Location

- **Primary**: `/config/test_defaults.yaml`
- **Fallback**: Hardcoded defaults in `src/core/test_config.py`

## Usage in Tests

### Basic Configuration Loading

```python
from src.core.test_config import get_test_config, get_minimal_config

# Get full test configuration (backward compatible)
config = get_test_config()
neo4j_config = config["neo4j"]

# Get minimal configuration for basic tests
minimal = get_minimal_config()
```

### Accessing Specific Data Types

```python
from src.core.test_config import (
    get_test_credentials,
    get_mock_responses, 
    get_test_data,
    get_database_url
)

# Get test credentials for specific services
neo4j_creds = get_test_credentials("neo4j")
test_password = neo4j_creds["test_pass"]

# Get mock responses for testing
mock_responses = get_mock_responses("neo4j")
success_message = mock_responses["successful_connection"]

# Get sample test data
sample_data = get_test_data("sample_contexts")

# Generate database URLs
neo4j_url = get_database_url("neo4j")  # bolt://localhost:7687
neo4j_ssl_url = get_database_url("neo4j", ssl=True)  # bolt+s://localhost:7687
```

### Alternative Configurations

```python
from src.core.test_config import get_alternative_config

# Get configuration for specific test scenarios
integration_config = get_alternative_config("integration_test")
ssl_config = get_alternative_config("ssl_test")
performance_config = get_alternative_config("performance_test")
```

### Using Fixtures

The `conftest.py` file provides ready-to-use fixtures:

```python
def test_with_centralized_config(test_credentials, mock_service_responses, sample_test_data):
    """Test using centralized configuration fixtures."""
    neo4j_creds = test_credentials["neo4j"]
    success_msg = mock_service_responses["neo4j"]["successful_connection"]
    contexts = sample_test_data["sample_contexts"]
```

## Configuration Structure

### Main Sections

1. **databases**: Connection settings for Neo4j, Qdrant, Redis
2. **storage**: File system and caching configuration  
3. **embedding**: AI embedding model settings
4. **security**: Authentication and SSL settings
5. **test_data**: Sample data for testing (contexts, vectors, graph data)
6. **test_credentials**: Non-production test credentials
7. **alternative_configs**: Specialized configurations for different test scenarios
8. **mock_responses**: Expected responses for mocking services
9. **paths**: File and directory paths for testing

### Database Configuration Example

```yaml
databases:
  neo4j:
    host: "localhost"
    port: 7687
    database: "test_context"
    username: "neo4j"
    password: "test_password"
    ssl: false
    uri_template: "bolt://{host}:{port}"
    ssl_uri_template: "bolt+s://{host}:{port}"
```

## Benefits

1. **Single Source of Truth**: All test configuration in one place
2. **Easy Maintenance**: Update test data without touching test files
3. **Environment Flexibility**: Different configurations for different test environments
4. **Consistency**: Same test data used across all tests
5. **Backward Compatibility**: Existing tests continue to work unchanged

## Migration from Hardcoded Values

### Before (Hardcoded)
```python
def test_neo4j_connection():
    config = {
        "neo4j": {
            "host": "localhost", 
            "port": 7687,
            "password": "test_password"
        }
    }
```

### After (Centralized)
```python
def test_neo4j_connection(test_config):
    neo4j_config = test_config["neo4j"]
    # or
    from src.core.test_config import get_test_config
    config = get_test_config()
```

## Adding New Test Data

To add new test data, edit `config/test_defaults.yaml`:

```yaml
test_data:
  your_new_data_type:
    - field1: "value1"
      field2: "value2"
```

Then access it in tests:

```python
from src.core.test_config import get_test_data
your_data = get_test_data("your_new_data_type")
```

## Error Handling

The system includes fallback mechanisms:

1. If `config/test_defaults.yaml` is not found, uses hardcoded fallback
2. If specific sections are missing, provides sensible defaults
3. If YAML parsing fails, logs error and uses fallback

## Security Notes

- Test credentials are clearly marked as non-production
- No real passwords or API keys in the configuration
- Test data is isolated from production systems

## Future Enhancements

- Environment-specific configuration overrides
- Dynamic test data generation
- Integration with CI/CD pipeline configuration
- Performance test data sets