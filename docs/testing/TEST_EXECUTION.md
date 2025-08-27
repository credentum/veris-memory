# Test Execution Guide - Single Source of Truth

## 🎯 IMPORTANT: Use `./scripts/run-tests.sh` for ALL Testing

This document establishes the **SINGLE SOURCE OF TRUTH** for running tests in veris-memory.

### ⚠️ Critical Issues Fixed

1. **Coverage Discrepancy**: Tests were showing 0.4% instead of actual ~25% coverage
   - **Cause**: `simple-coverage-gate.sh` only ran ONE test file
   - **Fix**: Use `./scripts/run-tests.sh` which runs ALL tests

2. **Parallel Execution Failures**: Tests failed with `--timeout` flag
   - **Cause**: `pytest-timeout` was not installed
   - **Fix**: Installed `pytest-timeout` and `pytest-forked`

3. **Import Errors**: Tests couldn't import modules
   - **Cause**: Using `from core.monitoring` instead of `from src.core.monitoring`
   - **Fix**: Updated all test imports to use `src.` prefix

4. **No Parallel Coverage**: Coverage tests ran sequentially (slow)
   - **Cause**: Coverage mode didn't use `-n` flag for parallel execution
   - **Fix**: All modes now use parallel execution by default

## 📊 Quick Reference

```bash
# ALWAYS USE THIS COMMAND FOR TESTING
./scripts/run-tests.sh [mode]

# Modes:
quick     # Fast unit tests only (~30 seconds, parallel)
standard  # Default - all tests with coverage (2-3 minutes, parallel)  
coverage  # Full coverage with HTML report (2-3 minutes, parallel)
parallel  # Explicit parallel mode with custom workers
ci        # Match GitHub Actions configuration
debug     # Sequential with verbose output (for debugging)
```

## 🚀 Common Use Cases

### For Development (Fast Feedback)
```bash
# Quick unit tests while coding
./scripts/run-tests.sh quick
```

### For Pre-Commit (Standard Check)
```bash
# Run all tests with basic coverage
./scripts/run-tests.sh standard
# OR just:
./scripts/run-tests.sh
```

### For Coverage Analysis
```bash
# Get detailed coverage report with HTML output
./scripts/run-tests.sh coverage
# Open coverage_html/index.html in browser
```

### For CI/CD Matching
```bash
# Run exactly as GitHub Actions does
./scripts/run-tests.sh ci
```

## 📈 Current Test Coverage Status

Based on latest analysis:
- **Actual Coverage**: ~25% (NOT 0.4% as incorrectly reported)
- **Minimum Threshold**: 15% (configured in pytest.ini)
- **Target Goal**: 35% (working towards this)

### Coverage by Module
```
core       : ~30% coverage
security   : ~25% coverage  
storage    : ~20% coverage
mcp_server : ~15% coverage
validators : ~10% coverage
monitoring : ~5% coverage
```

## ⚙️ Configuration Files

### Primary Configuration: `pytest.ini`
- Default configuration for sequential tests
- Coverage settings
- Test discovery patterns
- Marker definitions

### Parallel Configuration: `pytest-parallel.ini`
- Optimized for parallel execution
- Auto-detects CPU cores
- Uses `loadscope` distribution strategy

## 🔧 How Parallel Execution Works

1. **Auto-Detection**: Detects CPU cores and uses `cores - 2` workers
   - Minimum: 2 workers
   - Maximum: 12 workers
   - Current system: 10 workers (12 cores available)

2. **Distribution Strategy**: `--dist loadscope`
   - Groups tests by class/module
   - Better isolation between test groups
   - Prevents race conditions

3. **Coverage Collection**: Uses `pytest-cov` with parallel support
   - Each worker collects coverage data
   - Data is merged after all tests complete
   - No loss of coverage information

## 🐛 Troubleshooting

### Problem: Tests fail with import errors
```python
# Wrong:
from core.monitoring import MCPMonitor

# Correct:
from src.core.monitoring import MCPMonitor
```

### Problem: Coverage shows 0.4%
```bash
# Wrong - only runs one test file:
./scripts/simple-coverage-gate.sh

# Correct - runs all tests:
./scripts/run-tests.sh coverage
```

### Problem: Tests hang or timeout
```bash
# Check for missing dependencies:
pip install pytest-timeout pytest-forked pytest-xdist

# Run in debug mode to see what's happening:
./scripts/run-tests.sh debug
```

### Problem: Parallel tests fail but sequential pass
```bash
# Run without parallelization to debug:
./scripts/run-tests.sh debug

# Common causes:
# - Shared state between tests
# - File system race conditions
# - Missing tmp_path/tmpdir fixtures
```

## 📝 Writing Parallel-Safe Tests

### Use Temporary Directories
```python
def test_file_operations(tmp_path):
    # ✅ Good - isolated temporary directory
    test_file = tmp_path / "test.json"
    
def test_bad():
    # ❌ Bad - shared file system location
    test_file = "/tmp/test.json"
```

### Mock External Services
```python
@patch('src.storage.neo4j_client.GraphDatabase.driver')
def test_neo4j(mock_driver):
    # ✅ Good - mocked external service
    mock_driver.return_value = Mock()
```

### Avoid Global State
```python
# ❌ Bad - global variable
GLOBAL_COUNTER = 0

def test_increment():
    global GLOBAL_COUNTER
    GLOBAL_COUNTER += 1  # Race condition!

# ✅ Good - isolated state
def test_increment():
    counter = 0
    counter += 1
```

## 🎯 Test Execution Best Practices

1. **Always use `./scripts/run-tests.sh`** - It's the single source of truth
2. **Run `quick` mode frequently** during development (30 seconds)
3. **Run `standard` mode before commits** (2-3 minutes)
4. **Run `coverage` mode weekly** to track progress
5. **Use parallel execution by default** - it's 6-8x faster
6. **Fix import errors immediately** - they break coverage reporting

## 📊 Metrics and Goals

### Current State (as of last update)
- **Test Files**: 159
- **Test Functions**: ~2000+
- **Execution Time (Sequential)**: 10+ minutes
- **Execution Time (Parallel)**: 1-3 minutes
- **Coverage**: ~25%

### Goals
- **Coverage Target**: 35% (next milestone)
- **All imports fixed**: 100% tests should run
- **Parallel by default**: All modes use parallel execution
- **Single command**: `./scripts/run-tests.sh` for everything

## 🔄 Migration from Old Scripts

### Old Script → New Command

```bash
# Instead of:
./scripts/simple-coverage-gate.sh
# Use:
./scripts/run-tests.sh coverage

# Instead of:
./scripts/run-parallel-tests.sh fast
# Use:
./scripts/run-tests.sh quick

# Instead of:
./scripts/coverage-gate.sh
# Use:
./scripts/run-tests.sh standard

# Instead of:
python -m pytest tests/
# Use:
./scripts/run-tests.sh
```

## ✅ Verification Checklist

Run these commands to verify everything is working:

```bash
# 1. Check dependencies
pip list | grep pytest

# 2. Run quick test
./scripts/run-tests.sh quick

# 3. Check coverage
./scripts/run-tests.sh coverage | grep "Current Coverage"

# 4. Verify parallel execution
./scripts/run-tests.sh standard | grep "Parallel:"
```

Expected output:
- Quick tests: ~30 seconds, 200+ tests pass
- Coverage: Shows ~25% (NOT 0.4%)
- Parallel: Shows "Parallel: 10 workers" (or similar)

## 📚 Additional Resources

- `tests/README.md` - Test development guidelines
- `pytest.ini` - Main pytest configuration
- `pytest-parallel.ini` - Parallel execution configuration
- `.github/workflows/` - CI/CD test configuration

---

**Remember**: `./scripts/run-tests.sh` is THE way to run tests. All other methods are deprecated.