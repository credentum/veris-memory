#!/usr/bin/env python3
"""Analyze test failures to identify patterns and root causes."""

import json
import re
import subprocess
from collections import defaultdict
from typing import Dict, List, Tuple


def run_tests_and_collect_failures(test_path: str) -> Tuple[List[str], str]:
    """Run tests and collect failure information."""
    cmd = ["python", "-m", "pytest", "--tb=short", "--no-header", "-q", "--maxfail=30", test_path]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr

    # Extract failed test names
    failed_tests = re.findall(r"FAILED ([\w/\.]+::\S+)", output)

    return failed_tests, output


def analyze_failure_patterns(output: str) -> Dict[str, List[str]]:
    """Analyze output to categorize failure patterns."""
    patterns = defaultdict(list)

    # Common error patterns
    error_patterns = {
        "TypeError: ConfigValidator.__init__": "ConfigValidator constructor mismatch",
        "TypeError: .* takes .* positional argument": "Function signature mismatch",
        "ImportError": "Import error",
        "ModuleNotFoundError": "Module not found",
        "FileNotFoundError": "File not found",
        "AttributeError": "Attribute error",
        "KeyError": "Key error",
        "ValueError: Duplicated timeseries": "Prometheus metrics duplication",
        "AssertionError": "Assertion failure",
        "patch.*does not exist": "Mock patch target doesn't exist",
        "fixture.*not found": "Pytest fixture not found",
    }

    lines = output.split("\n")
    for i, line in enumerate(lines):
        for pattern, category in error_patterns.items():
            if re.search(pattern, line):
                # Get context (line before and after)
                context = []
                if i > 0:
                    context.append(lines[i - 1])
                context.append(line)
                if i < len(lines) - 1:
                    context.append(lines[i + 1])
                patterns[category].append("\n".join(context))
                break

    return dict(patterns)


def analyze_test_structure():
    """Analyze test file structure and imports."""
    test_dirs = [
        "src/core/tests",
        "src/storage/tests",
        "src/validators/tests",
        "src/mcp_server/tests",
        "tests",
    ]

    results = {}

    for test_dir in test_dirs:
        print(f"\nAnalyzing {test_dir}...")
        failed_tests, output = run_tests_and_collect_failures(test_dir)
        patterns = analyze_failure_patterns(output)

        # Count pass/fail
        total_match = re.search(r"(\d+) failed, (\d+) passed", output)
        if total_match:
            failed_count = int(total_match.group(1))
            passed_count = int(total_match.group(2))
        else:
            failed_count = len(failed_tests)
            passed_count = 0

        results[test_dir] = {
            "failed": failed_count,
            "passed": passed_count,
            "failure_patterns": patterns,
            "sample_failures": failed_tests[:5],  # First 5 failures
        }

    return results


def generate_fix_plan(results: Dict) -> List[str]:
    """Generate a prioritized fix plan based on analysis."""
    fix_plan = []

    # Count failure patterns across all test suites
    pattern_counts = defaultdict(int)
    for test_dir, data in results.items():
        for pattern in data.get("failure_patterns", {}):
            pattern_counts[pattern] += len(data["failure_patterns"][pattern])

    # Sort by frequency
    sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)

    # Generate fix recommendations
    fix_recommendations = {
        "ConfigValidator constructor mismatch": "Update ConfigValidator tests to not pass config_path to __init__()",
        "Function signature mismatch": "Review and update test function calls to match actual signatures",
        "Import error": "Fix import paths and ensure all modules are properly installed",
        "Mock patch target doesn't exist": "Update patch decorators to use correct module paths",
        "Prometheus metrics duplication": "Add proper cleanup/isolation for Prometheus metrics",
        "File not found": "Ensure test files create necessary fixtures or use proper paths",
        "Assertion failure": "Review test assertions and expected values",
    }

    for pattern, count in sorted_patterns:
        if pattern in fix_recommendations:
            fix_plan.append(
                {"issue": pattern, "count": count, "recommendation": fix_recommendations[pattern]}
            )

    return fix_plan


def main():
    print("=" * 60)
    print("TEST FAILURE ANALYSIS")
    print("=" * 60)

    # Analyze test structure and failures
    results = analyze_test_structure()

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY BY TEST SUITE")
    print("=" * 60)

    total_failed = 0
    total_passed = 0

    for test_dir, data in results.items():
        print(f"\n{test_dir}:")
        print(f"  Failed: {data['failed']}")
        print(f"  Passed: {data['passed']}")
        print(
            f"  Success rate: {data['passed'] / max(1, data['failed'] + data['passed']) * 100:.1f}%"
        )

        if data["failure_patterns"]:
            print("  Common issues:")
            for pattern, examples in list(data["failure_patterns"].items())[:3]:
                print(f"    - {pattern} ({len(examples)} occurrences)")

        total_failed += data["failed"]
        total_passed += data["passed"]

    print("\n" + "=" * 60)
    print("OVERALL STATISTICS")
    print("=" * 60)
    print(f"Total Failed: {total_failed}")
    print(f"Total Passed: {total_passed}")
    print(f"Overall Success Rate: {total_passed / max(1, total_failed + total_passed) * 100:.1f}%")

    # Generate fix plan
    fix_plan = generate_fix_plan(results)

    print("\n" + "=" * 60)
    print("PRIORITIZED FIX PLAN")
    print("=" * 60)

    for i, fix in enumerate(fix_plan, 1):
        print(f"\n{i}. {fix['issue']} ({fix['count']} failures)")
        print(f"   Recommendation: {fix['recommendation']}")

    # Save detailed results to JSON
    with open("test_failure_analysis.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\nDetailed results saved to test_failure_analysis.json")


if __name__ == "__main__":
    main()
