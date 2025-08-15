#!/bin/bash
# Parallel Test Execution Script for Veris Memory
# Optimized for speed while maintaining test isolation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEFAULT_WORKERS="auto"
COVERAGE_THRESHOLD=15
MAX_FAILURES=10

# Function to print colored output
print_status() {
    echo -e "${BLUE}[PARALLEL-TESTS]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to detect optimal worker count
detect_workers() {
    local cpu_count=$(nproc)
    local optimal_workers=$((cpu_count - 2))
    
    # Minimum 2 workers, maximum 12 workers
    if [ $optimal_workers -lt 2 ]; then
        optimal_workers=2
    elif [ $optimal_workers -gt 12 ]; then
        optimal_workers=12
    fi
    
    echo $optimal_workers
}

# Function to run tests with parallel execution
run_parallel_tests() {
    local test_pattern="${1:-tests/}"
    local workers="${2:-$(detect_workers)}"
    local extra_args="${3:-}"
    
    print_status "Running parallel tests with $workers workers"
    print_status "Test pattern: $test_pattern"
    
    # Run tests with pytest-xdist
    python3 -m pytest \
        "$test_pattern" \
        -n "$workers" \
        --maxfail="$MAX_FAILURES" \
        --tb=short \
        --durations=20 \
        -v \
        --cov=src \
        --cov-report=term-missing:skip-covered \
        --cov-report=json:coverage.json \
        --cov-branch \
        --cov-fail-under="$COVERAGE_THRESHOLD" \
        --timeout=300 \
        $extra_args
}

# Function to run fast unit tests only
run_fast_tests() {
    print_status "Running fast unit tests in parallel"
    run_parallel_tests "tests/" "auto" "-m 'unit or not slow'"
}

# Function to run security tests in parallel
run_security_tests() {
    print_status "Running security tests in parallel"
    run_parallel_tests "tests/security/" "6" ""
}

# Function to run all tests with smart parallelization
run_all_tests() {
    print_status "Running comprehensive test suite with parallel execution"
    
    # Run fast tests first with high parallelization
    print_status "Phase 1: Fast unit tests (high parallelization)"
    run_parallel_tests "tests/" "auto" "-m 'unit or not (slow or integration)'"
    
    # Run integration tests with moderate parallelization
    print_status "Phase 2: Integration tests (moderate parallelization)"
    run_parallel_tests "tests/" "4" "-m 'integration and not slow'"
    
    # Run slow tests with low parallelization
    print_status "Phase 3: Slow tests (limited parallelization)"
    run_parallel_tests "tests/" "2" "-m 'slow'"
}

# Function to benchmark parallel vs sequential
benchmark_parallel() {
    local test_subset="tests/core/test_utils.py tests/validators/test_config_validator.py"
    
    print_status "Benchmarking parallel vs sequential execution"
    
    print_status "Running sequential baseline..."
    time python3 -m pytest $test_subset -v --tb=no -q > /tmp/sequential.log 2>&1
    
    print_status "Running parallel with 2 workers..."
    time python3 -m pytest $test_subset -n 2 -v --tb=no -q > /tmp/parallel_2.log 2>&1
    
    print_status "Running parallel with 4 workers..."
    time python3 -m pytest $test_subset -n 4 -v --tb=no -q > /tmp/parallel_4.log 2>&1
    
    print_status "Running parallel with auto workers..."
    time python3 -m pytest $test_subset -n auto -v --tb=no -q > /tmp/parallel_auto.log 2>&1
    
    print_success "Benchmark complete. Check timing results above."
}

# Function to validate parallel execution works correctly
validate_parallel() {
    print_status "Validating parallel test execution..."
    
    # Test basic enum tests that should always pass
    local validation_tests="tests/security/test_compliance_reporter_comprehensive.py::TestEnumsAndDataClasses::test_compliance_framework_enum tests/security/test_security_scanner_comprehensive.py::TestEnumsAndDataClasses::test_scan_type_enum"
    
    if python3 -m pytest $validation_tests -n 2 -v --tb=short; then
        print_success "Parallel execution validation passed"
        return 0
    else
        print_error "Parallel execution validation failed"
        return 1
    fi
}

# Main execution logic
main() {
    local command="${1:-help}"
    
    # Check if pytest-xdist is installed
    if ! python3 -c "import xdist" 2>/dev/null; then
        print_error "pytest-xdist not installed. Installing..."
        pip install pytest-xdist pytest-forked
    fi
    
    case "$command" in
        "fast")
            run_fast_tests
            ;;
        "security")
            run_security_tests
            ;;
        "all")
            run_all_tests
            ;;
        "benchmark")
            benchmark_parallel
            ;;
        "validate")
            validate_parallel
            ;;
        "custom")
            local pattern="${2:-tests/}"
            local workers="${3:-auto}"
            run_parallel_tests "$pattern" "$workers"
            ;;
        "help"|*)
            echo "Parallel Test Execution Script"
            echo "Usage: $0 [command] [options]"
            echo ""
            echo "Commands:"
            echo "  fast      - Run fast unit tests with high parallelization"
            echo "  security  - Run security tests with moderate parallelization"
            echo "  all       - Run all tests with smart parallel strategy"
            echo "  benchmark - Compare parallel vs sequential performance"
            echo "  validate  - Validate parallel execution works correctly"
            echo "  custom    - Custom test run: $0 custom [pattern] [workers]"
            echo "  help      - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 fast                           # Fast tests only"
            echo "  $0 security                       # Security module tests"
            echo "  $0 all                            # Complete test suite"
            echo "  $0 custom tests/core/ 4           # Core tests with 4 workers"
            echo "  $0 benchmark                      # Performance comparison"
            echo ""
            echo "Detected optimal workers: $(detect_workers)"
            ;;
    esac
}

# Execute main function with all arguments
main "$@"