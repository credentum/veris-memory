# 🤖 FOR AI AGENTS: HOW TO RUN TESTS

## THE ONE COMMAND YOU NEED:

```bash
make coverage
```

That's it. This will:
- ✅ Run all tests with parallel execution
- ✅ Show you the coverage percentage (~25% expected)
- ✅ Save results to `coverage.json`
- ✅ Automatically fix common issues

## IF THAT DOESN'T WORK:

```bash
make fix-coverage   # Fixes common issues
make coverage       # Try again
```

## OTHER USEFUL COMMANDS:

```bash
make test          # Run all tests (faster, no coverage)
make quick         # Super fast test subset
make help          # See all available commands
```

## EXPECTED RESULTS:

- **Current Coverage: ~25%** (not 0.4% - that was a bug)
- **Test Count: 4000+** tests
- **Execution Time: 2-3 minutes** with parallel execution

## WHY THIS EXISTS:

Every new agent was struggling to find the right way to run tests. This file makes it impossible to miss. The Makefile is the industry standard that every agent should try first.

## TROUBLESHOOTING:

If you see `ModuleNotFoundError: No module named 'coverage.exceptions'`:
- This means a file named `coverage.py` exists and conflicts with the Python coverage package
- Run: `make fix-coverage` to automatically fix this

If tests hang or timeout:
- The Makefile now uses parallel execution by default
- This should prevent hanging issues

## TECHNICAL DETAILS:

- Uses `pytest-xdist` for parallel execution (`-n auto`)
- Automatically detects optimal worker count
- Falls back to `./scripts/run-tests.sh` if available
- Saves coverage to `coverage.json` for easy parsing

---
Remember: `make coverage` is all you need!