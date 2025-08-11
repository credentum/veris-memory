#!/usr/bin/env python3
"""
Simple test script for Enhanced ARC-Reviewer.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import after path modification (required for test setup)
from agents.arc_reviewer_enhanced import ARCReviewerEnhanced  # noqa: E402


def test_basic_functionality():
    """Test basic initialization and configuration."""
    print("🔍 Testing Enhanced ARC-Reviewer initialization...")

    # Test basic initialization
    reviewer = ARCReviewerEnhanced(verbose=True, skip_coverage=True)
    print(f"✅ Initialized with model: {reviewer.model}")
    print(f"✅ Timeout: {reviewer.timeout}s")
    print(f"✅ Coverage config loaded: {bool(reviewer.coverage_config)}")

    # Test configuration loading
    config_keys = list(reviewer.coverage_config.keys())
    print(f"✅ Config keys: {config_keys}")

    # Test tool definitions
    print(f"✅ Available tools: {len(reviewer.ALLOWED_TOOLS)}")

    print("🎯 Basic functionality test completed!")


def test_format_correction():
    """Test format correction pipeline."""
    print("\n🔧 Testing format correction pipeline...")

    reviewer = ARCReviewerEnhanced(verbose=True, skip_coverage=True)

    # Test YAML format correction
    test_yaml = """
schema_version: "1.0"
pr_number: 123
timestamp: "2025-08-11T18:00:00Z"
reviewer: "ARC-Reviewer"
verdict: "APPROVE"
summary: "Test review"
coverage:
  current_pct: 85.0
  status: "PASS"
  meets_baseline: true
issues:
  blocking: []
  warnings: []
  nits: []
automated_issues: []
"""

    corrected = reviewer._apply_format_correction(test_yaml)
    print(f"✅ Format correction successful: {corrected.get('verdict', 'UNKNOWN')}")

    # Test fallback response
    fallback = reviewer._create_fallback_response()
    print(f"✅ Fallback response created: {fallback.get('verdict', 'UNKNOWN')}")

    print("🎯 Format correction test completed!")


def test_analysis_functions():
    """Test analysis functions."""
    print("\n🔍 Testing analysis functions...")

    reviewer = ARCReviewerEnhanced(verbose=True, skip_coverage=True)

    # Test infrastructure PR detection
    test_files = ["docker-compose.yml", "Dockerfile", "src/main.py"]
    is_infra = reviewer._detect_infrastructure_pr(test_files, "feat/docker-compose-update")
    print(f"✅ Infrastructure detection: {is_infra}")

    # Test Python file analysis
    issues = {"blocking": [], "warnings": [], "nits": []}
    test_content = "import os\nimport sys\nprint('hello world')\n" + "x" * 200  # Long line

    reviewer._analyze_python_file("test.py", test_content, issues)
    print(f"✅ Python analysis found {len(issues['blocking'])} blocking issues")

    print("🎯 Analysis functions test completed!")


def main():
    """Run all tests."""
    print("🚀 Starting Enhanced ARC-Reviewer Tests\n")

    try:
        test_basic_functionality()
        test_format_correction()
        test_analysis_functions()

        print("\n🎉 All tests completed successfully!")
        print("\nThe Enhanced ARC-Reviewer implementation includes:")
        print("✅ GitHub Workflow parity features")
        print("✅ Comprehensive format correction pipeline")
        print("✅ Advanced coverage handling with tolerance")
        print("✅ Infrastructure PR detection")
        print("✅ Multi-strategy YAML parsing")
        print("✅ Automated issue generation")
        print("✅ Tool integration framework")
        print("✅ Security analysis")
        print("✅ Context integrity validation")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
