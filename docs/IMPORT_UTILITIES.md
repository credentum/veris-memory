# Import Utilities Documentation

## Overview

The import utilities (`src/core/import_utils.py`) provide a centralized, consistent way to handle complex import scenarios throughout the Veris Memory codebase. They eliminate repeated import patterns and provide better error handling, logging, and fallback mechanisms.

## Key Features

- **Safe imports** with comprehensive error handling
- **Fallback mechanisms** for missing dependencies
- **Bulk importing** for related modules
- **Relative-then-absolute** import patterns
- **Optional dependency** handling with install suggestions
- **Dynamic fallback class** creation
- **Consistent logging** across all import operations

## Core Functions

### `safe_import()`

The primary function for importing modules with fallback support.

```python
from src.core.import_utils import safe_import

# Basic usage
result = safe_import('redis')
if result.success:
    redis_module = result.module

# With fallback paths
result = safe_import(
    module_path='src.monitoring.dashboard',
    fallback_paths=['monitoring.dashboard', '.dashboard']
)

# With required attributes check
result = safe_import(
    module_path='qdrant_client',
    required_attrs=['QdrantClient', 'models']
)

# With fallback factory
def create_mock_redis():
    class MockRedis:
        def get(self, key): return None
        def set(self, key, value): return True
    return MockRedis()

result = safe_import(
    module_path='redis',
    fallback_factory=create_mock_redis
)
```

### `bulk_import()`

Import multiple related modules with individual configurations.

```python
from src.core.import_utils import bulk_import

import_specs = {
    'dashboard': {
        'module_path': 'src.monitoring.dashboard',
        'required_attrs': ['UnifiedDashboard']
    },
    'streaming': {
        'module_path': 'src.monitoring.streaming',
        'fallback_paths': ['.streaming']
    },
    'redis': {
        'module_path': 'redis',
        'fallback_factory': create_mock_redis
    }
}

results = bulk_import(import_specs)

# Access imported modules
for name, result in results.items():
    if result.success:
        print(f"{name}: {result.method}")
        module = result.module
    else:
        print(f"{name} failed: {result.error}")
```

### `try_relative_then_absolute()`

Handle the common pattern of trying relative imports first, then absolute imports.

```python
from src.core.import_utils import try_relative_then_absolute

result = try_relative_then_absolute(
    relative_import='.dashboard',
    absolute_import='src.monitoring.dashboard',
    required_attrs=['UnifiedDashboard']
)

if result.success:
    dashboard_module = result.module
    UnifiedDashboard = getattr(dashboard_module, 'UnifiedDashboard')
```

### `get_optional_dependency()`

Handle optional dependencies with helpful error messages.

```python
from src.core.import_utils import get_optional_dependency

available, torch, install_msg = get_optional_dependency(
    'torch',
    pip_install_name='torch',
    conda_install_name='pytorch'
)

if not available:
    logger.warning(f"PyTorch not available: {install_msg}")
else:
    # Use torch module
    pass
```

### `create_fallback_class()`

Dynamically create fallback classes for missing dependencies.

```python
from src.core.import_utils import create_fallback_class

MockRedis = create_fallback_class(
    'MockRedis',
    methods={
        'get': lambda self, key: None,
        'set': lambda self, key, value: True,
        'ping': lambda self: True
    },
    attributes={
        'connected': False,
        'host': 'localhost'
    }
)

redis_client = MockRedis()
```

## ImportResult Object

All import functions return an `ImportResult` object with these attributes:

- `success`: Boolean indicating if import succeeded
- `module`: The imported module (or fallback object)
- `error`: Exception if import failed
- `import_path`: The path that was successfully imported
- `method`: How the import succeeded ('primary', 'fallback_1', 'absolute', etc.)

```python
result = safe_import('some_module')

if result:  # Equivalent to result.success
    module = result.module
    print(f"Imported via {result.method}: {result.import_path}")
else:
    print(f"Import failed: {result.error}")
```

## Common Patterns

### 1. Database Client Imports

```python
# Redis with fallback
redis_result = safe_import(
    module_path='redis',
    fallback_factory=create_mock_redis
)

# Qdrant with fallback  
qdrant_result = safe_import(
    module_path='qdrant_client',
    required_attrs=['QdrantClient'],
    fallback_factory=create_mock_qdrant
)

# Neo4j with fallback
neo4j_result = safe_import(
    module_path='neo4j',
    required_attrs=['GraphDatabase'],
    fallback_factory=create_mock_neo4j
)
```

### 2. ML Library Imports

```python
# PyTorch (optional)
torch_available, torch, torch_msg = get_optional_dependency(
    'torch',
    pip_install_name='torch'
)

# Sentence Transformers (optional)
st_available, sentence_transformers, st_msg = get_optional_dependency(
    'sentence_transformers',
    pip_install_name='sentence-transformers'
)

# Use appropriate fallbacks if not available
if not torch_available:
    logger.warning(f"PyTorch features disabled: {torch_msg}")
```

### 3. Internal Module Imports

```python
# Monitoring modules
monitoring_specs = {
    'dashboard': {
        'module_path': '.dashboard',
        'fallback_paths': ['src.monitoring.dashboard'],
        'required_attrs': ['UnifiedDashboard']
    },
    'metrics': {
        'module_path': '.metrics_collector',
        'fallback_paths': ['src.monitoring.metrics_collector']
    }
}

monitoring_modules = bulk_import(monitoring_specs)
```

## Pre-built Fallback Factories

The module includes several pre-built fallback factories:

```python
from src.core.import_utils import (
    create_mock_redis,
    create_mock_qdrant, 
    create_mock_neo4j
)

# Use in safe_import
redis_result = safe_import('redis', fallback_factory=create_mock_redis)
```

## Migration Guide

### Before (scattered patterns):

```python
# Pattern 1: Basic try/except
try:
    import redis
except ImportError:
    redis = None

# Pattern 2: Relative then absolute
try:
    from .dashboard import UnifiedDashboard
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
    from src.monitoring.dashboard import UnifiedDashboard

# Pattern 3: Complex fallback creation
try:
    from qdrant_client import QdrantClient
except ImportError:
    class QdrantClient:
        def __init__(self, *args, **kwargs): pass
        def search(self, *args, **kwargs): return []
```

### After (using import_utils):

```python
from src.core.import_utils import (
    safe_import, 
    try_relative_then_absolute,
    create_mock_redis
)

# Pattern 1: Safe import with fallback
redis_result = safe_import('redis', fallback_factory=create_mock_redis)
redis = redis_result.module

# Pattern 2: Relative then absolute
dashboard_result = try_relative_then_absolute(
    '.dashboard', 
    'src.monitoring.dashboard',
    required_attrs=['UnifiedDashboard']
)
UnifiedDashboard = getattr(dashboard_result.module, 'UnifiedDashboard')

# Pattern 3: Safe import with mock
qdrant_result = safe_import(
    'qdrant_client',
    required_attrs=['QdrantClient'],
    fallback_factory=create_mock_qdrant
)
QdrantClient = getattr(qdrant_result.module, 'QdrantClient')
```

## Best Practices

1. **Use `safe_import()` for external dependencies** that might not be installed
2. **Use `try_relative_then_absolute()` for internal modules** that need import path flexibility
3. **Use `bulk_import()` for related modules** that are imported together
4. **Always check `result.success`** before using imported modules
5. **Provide fallback factories** for critical functionality
6. **Use appropriate log levels** ('debug' for expected failures, 'error' for critical failures)
7. **Document required attributes** in the import specifications

## Error Handling

The import utilities provide comprehensive error handling:

- `ImportError`: Module not found
- `ModuleNotFoundError`: Python 3.3+ specific module not found
- `AttributeError`: Required attributes missing from imported module
- Generic `Exception`: Fallback factory failures

All errors are logged appropriately and stored in the `ImportResult.error` field.

## Performance Considerations

- Import utilities add minimal overhead (microseconds per import)
- Fallback factories are only called when primary imports fail
- `sys.path` modifications are cached and reused
- Bulk imports can be more efficient than individual imports for related modules

## Integration with Testing

The import utilities work seamlessly with the centralized test configuration:

```python
# In tests
from src.core.import_utils import safe_import
from src.core.test_config import get_test_config

config = get_test_config()
redis_result = safe_import('redis', fallback_factory=create_mock_redis)

# Test with either real Redis or mock
redis_client = redis_result.module
```