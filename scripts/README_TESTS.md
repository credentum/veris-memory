# Test Scripts - IMPORTANT

## ⚠️ USE ONLY `run-tests.sh`

**`./scripts/run-tests.sh`** is the SINGLE SOURCE OF TRUTH for running tests.

All other test scripts are DEPRECATED and just redirect to `run-tests.sh`:
- ❌ `simple-coverage-gate.sh` → Use `run-tests.sh coverage`
- ❌ `coverage-gate.sh` → Use `run-tests.sh coverage`
- ❌ `run-parallel-tests.sh` → Use `run-tests.sh [mode]`

## Quick Usage

```bash
# Run standard tests (default)
./scripts/run-tests.sh

# Run quick unit tests (30 seconds)
./scripts/run-tests.sh quick

# Run with full coverage report
./scripts/run-tests.sh coverage

# See all options
./scripts/run-tests.sh --help
```

## Why the Change?

Previous scripts caused confusion:
- `simple-coverage-gate.sh` only ran ONE test file (showing 0.4% coverage instead of ~25%)
- Different scripts had different configurations
- No parallel execution for coverage tests
- Import errors weren't handled consistently

The unified `run-tests.sh`:
- Always uses parallel execution (6-8x faster)
- Consistent configuration
- Accurate coverage reporting
- Single point of maintenance

See [TEST_EXECUTION.md](../TEST_EXECUTION.md) for complete documentation.