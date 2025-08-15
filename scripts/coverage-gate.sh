#!/bin/bash
# Local Coverage Gate Script
# Ensures code coverage meets minimum thresholds before commits

set -e

# Configuration
MIN_COVERAGE=0.5  # Start with current baseline (0.3%)
COVERAGE_FILE=".coverage"
REPORT_DIR="coverage_html"
REPORT_FILE="coverage.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Running Coverage Gate Check..."

# Clean previous coverage data
rm -f $COVERAGE_FILE
rm -f coverage.xml $REPORT_FILE

# Run tests with coverage
echo "📊 Running tests with coverage analysis..."
python3 -m pytest tests/ \
    --cov=src \
    --cov-report=term-missing:skip-covered \
    --cov-report=json:$REPORT_FILE \
    --cov-fail-under=$MIN_COVERAGE \
    --tb=short \
    -v

# Check if coverage file was generated
if [ ! -f "$REPORT_FILE" ]; then
    echo -e "${RED}❌ Coverage report not generated!${NC}"
    exit 1
fi

# Extract coverage percentage
CURRENT_COVERAGE=$(python3 -c "
import json
try:
    with open('$REPORT_FILE', 'r') as f:
        data = json.load(f)
    total_statements = data['totals']['num_statements']
    covered_lines = data['totals']['covered_lines']
    coverage_pct = (covered_lines / total_statements) * 100 if total_statements > 0 else 0
    print(f'{coverage_pct:.1f}')
except Exception as e:
    print('0.0')
")

# Coverage gate logic
echo "📈 Coverage Analysis:"
echo "   Current: ${CURRENT_COVERAGE}%"
echo "   Required: ${MIN_COVERAGE}%"

if (( $(echo "$CURRENT_COVERAGE >= $MIN_COVERAGE" | bc -l) )); then
    echo -e "${GREEN}✅ Coverage gate PASSED! (${CURRENT_COVERAGE}% >= ${MIN_COVERAGE}%)${NC}"
    echo "📄 Coverage data: $REPORT_FILE"
else
    echo -e "${RED}❌ Coverage gate FAILED! (${CURRENT_COVERAGE}% < ${MIN_COVERAGE}%)${NC}"
    echo -e "${YELLOW}💡 Add more tests to increase coverage before committing${NC}"
    echo "📄 Coverage data: $REPORT_FILE"
    exit 1
fi

# Additional checks
echo ""
echo "🔍 Additional Quality Checks:"

# Check for files with 0% coverage
ZERO_COVERAGE_FILES=$(python3 -c "
import json
try:
    with open('$REPORT_FILE', 'r') as f:
        data = json.load(f)
    zero_files = []
    for filename, info in data['files'].items():
        if info['summary']['percent_covered'] == 0:
            zero_files.append(filename)
    if zero_files:
        print('\\n'.join(zero_files[:10]))  # Show first 10
except:
    pass
")

if [ ! -z "$ZERO_COVERAGE_FILES" ]; then
    echo -e "${YELLOW}⚠️  Files with 0% coverage:${NC}"
    echo "$ZERO_COVERAGE_FILES" | head -5
    if [ $(echo "$ZERO_COVERAGE_FILES" | wc -l) -gt 5 ]; then
        echo "   ... and $(( $(echo "$ZERO_COVERAGE_FILES" | wc -l) - 5 )) more"
    fi
    echo ""
fi

# Generate coverage summary
python3 -c "
import json
try:
    with open('$REPORT_FILE', 'r') as f:
        data = json.load(f)
    
    print('📊 Coverage Summary by Module:')
    modules = {}
    for filename, info in data['files'].items():
        if filename.startswith('src/'):
            module = filename.split('/')[1] if '/' in filename else 'root'
            if module not in modules:
                modules[module] = {'statements': 0, 'covered': 0, 'files': 0}
            modules[module]['statements'] += info['summary']['num_statements']
            modules[module]['covered'] += info['summary']['covered_lines']
            modules[module]['files'] += 1
    
    for module, stats in sorted(modules.items()):
        if stats['statements'] > 0:
            pct = (stats['covered'] / stats['statements']) * 100
            print(f'   {module:15s}: {pct:5.1f}% ({stats[\"covered\"]:3d}/{stats[\"statements\"]:3d} lines, {stats[\"files\"]} files)')
        else:
            print(f'   {module:15s}: No code')
            
except Exception as e:
    print(f'Error generating summary: {e}')
"

echo ""
echo -e "${GREEN}🎯 Coverage gate check completed successfully!${NC}"