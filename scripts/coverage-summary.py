#!/usr/bin/env python3
"""
Coverage Summary Tool - Agent-friendly JSON coverage analysis
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any


def load_coverage_data(file_path: str = "coverage.json") -> Dict[str, Any]:
    """Load coverage data from JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found. Run tests with coverage first.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {file_path}")
        sys.exit(1)


def analyze_coverage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze coverage data and return summary."""
    totals = data.get('totals', {})
    files = data.get('files', {})
    
    # Overall metrics
    total_coverage = totals.get('percent_covered', 0)
    total_statements = totals.get('num_statements', 0)
    covered_lines = totals.get('covered_lines', 0)
    
    # Module breakdown
    modules = {}
    zero_coverage_files = []
    high_coverage_files = []
    
    for filename, info in files.items():
        if filename.startswith('src/'):
            # Extract module name
            parts = filename.split('/')
            module = parts[1] if len(parts) > 1 else 'root'
            
            # Initialize module stats
            if module not in modules:
                modules[module] = {
                    'statements': 0,
                    'covered': 0,
                    'files': 0,
                    'percent': 0
                }
            
            # Aggregate stats
            file_stats = info.get('summary', {})
            modules[module]['statements'] += file_stats.get('num_statements', 0)
            modules[module]['covered'] += file_stats.get('covered_lines', 0)
            modules[module]['files'] += 1
            
            # Track zero/high coverage files
            file_coverage = file_stats.get('percent_covered', 0)
            if file_coverage == 0 and file_stats.get('num_statements', 0) > 0:
                zero_coverage_files.append(filename)
            elif file_coverage >= 80:
                high_coverage_files.append({
                    'file': filename,
                    'coverage': file_coverage
                })
    
    # Calculate module percentages
    for module in modules:
        if modules[module]['statements'] > 0:
            modules[module]['percent'] = (
                modules[module]['covered'] / modules[module]['statements'] * 100
            )
    
    return {
        'overall': {
            'coverage': total_coverage,
            'statements': total_statements,
            'covered': covered_lines,
            'missing': total_statements - covered_lines
        },
        'modules': modules,
        'zero_coverage_files': zero_coverage_files,
        'high_coverage_files': high_coverage_files
    }


def print_summary(analysis: Dict[str, Any], format_type: str = "human"):
    """Print coverage summary in specified format."""
    if format_type == "json":
        print(json.dumps(analysis, indent=2))
        return
    
    overall = analysis['overall']
    modules = analysis['modules']
    zero_files = analysis['zero_coverage_files']
    
    print("📊 Coverage Summary")
    print("=" * 50)
    print(f"Overall Coverage: {overall['coverage']:.1f}%")
    print(f"Total Statements: {overall['statements']}")
    print(f"Covered Lines: {overall['covered']}")
    print(f"Missing Lines: {overall['missing']}")
    print()
    
    print("📁 Module Breakdown:")
    for module, stats in sorted(modules.items(), key=lambda x: x[1]['percent'], reverse=True):
        print(f"  {module:15s}: {stats['percent']:5.1f}% "
              f"({stats['covered']:3d}/{stats['statements']:3d} lines, "
              f"{stats['files']} files)")
    print()
    
    if zero_files:
        print(f"⚠️  Files with 0% coverage ({len(zero_files)}):")
        for file in zero_files[:10]:  # Show first 10
            print(f"  - {file}")
        if len(zero_files) > 10:
            print(f"  ... and {len(zero_files) - 10} more")
        print()
    
    # Coverage status
    coverage = overall['coverage']
    if coverage >= 80:
        print("✅ Excellent coverage!")
    elif coverage >= 60:
        print("🟡 Good coverage, room for improvement")
    elif coverage >= 40:
        print("🟠 Moderate coverage, needs attention")
    elif coverage >= 20:
        print("🔴 Low coverage, significant work needed")
    else:
        print("💀 Critical: Very low coverage")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze test coverage data")
    parser.add_argument(
        '--file', '-f', 
        default='coverage.json',
        help='Coverage JSON file path'
    )
    parser.add_argument(
        '--format', 
        choices=['human', 'json'],
        default='human',
        help='Output format'
    )
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=15.0,
        help='Coverage threshold for pass/fail'
    )
    
    args = parser.parse_args()
    
    # Load and analyze data
    data = load_coverage_data(args.file)
    analysis = analyze_coverage(data)
    
    # Print summary
    print_summary(analysis, args.format)
    
    # Exit with appropriate code
    coverage = analysis['overall']['coverage']
    if coverage < args.threshold:
        sys.exit(1)


if __name__ == '__main__':
    main()