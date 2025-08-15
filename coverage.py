#!/usr/bin/env python3
"""
SIMPLE COVERAGE RUNNER FOR AGENTS

This file makes it TRIVIAL to get code coverage.
Just run: python coverage.py

That's it. No flags, no confusion, no searching.
Results always go to coverage.json
"""

import subprocess
import sys
import json
import os

def main():
    """Run tests with coverage and output to coverage.json"""
    
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("🔍 Running code coverage...")
    print("-" * 50)
    
    # Simple pytest command that ALWAYS works
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--cov=src",
        "--cov-report=json:coverage.json",
        "--cov-report=term",
        "-q",
        "--tb=no"
    ]
    
    # Run the command
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    # Read and display coverage percentage
    if os.path.exists("coverage.json"):
        with open("coverage.json", "r") as f:
            data = json.load(f)
            percent = data.get("totals", {}).get("percent_covered", 0)
            print(f"\n📊 Total Coverage: {percent:.1f}%")
            print(f"✅ Coverage report saved to: coverage.json")
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())