#!/bin/bash
# DEPRECATED: This script is replaced by run-tests.sh
# Redirecting to the new unified test runner

echo "⚠️  DEPRECATED: run-parallel-tests.sh is deprecated"
echo "   Please use: ./scripts/run-tests.sh [mode]"
echo ""

# Map old commands to new ones
case "${1:-}" in
    fast)
        echo "   Mapping 'fast' → 'quick'"
        exec "$(dirname "$0")/run-tests.sh" quick "${@:2}"
        ;;
    security)
        echo "   Running security tests..."
        exec "$(dirname "$0")/run-tests.sh" standard --path tests/security/ "${@:2}"
        ;;
    all)
        echo "   Mapping 'all' → 'standard'"
        exec "$(dirname "$0")/run-tests.sh" standard "${@:2}"
        ;;
    custom)
        echo "   Mapping 'custom' → 'parallel'"
        shift
        exec "$(dirname "$0")/run-tests.sh" parallel --path "$1" --workers "${2:-auto}" "${@:3}"
        ;;
    benchmark)
        echo "   Running benchmark..."
        exec "$(dirname "$0")/run-tests.sh" stats "${@:2}"
        ;;
    validate)
        echo "   Running validation..."
        exec "$(dirname "$0")/run-tests.sh" quick "${@:2}"
        ;;
    *)
        echo "   Redirecting to standard mode..."
        exec "$(dirname "$0")/run-tests.sh" standard "$@"
        ;;
esac