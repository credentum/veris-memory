#!/bin/bash
# DEPRECATED: This script is replaced by run-tests.sh
# Redirecting to the new unified test runner

echo "⚠️  DEPRECATED: simple-coverage-gate.sh is deprecated"
echo "   Please use: ./scripts/run-tests.sh coverage"
echo "   Redirecting to new command..."
echo ""

# Delegate to the unified test runner
exec "$(dirname "$0")/run-tests.sh" coverage "$@"