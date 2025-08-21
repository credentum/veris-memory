#!/bin/bash
# API Debug Wrapper - Captures ALL startup errors with maximum verbosity

echo "=========================================="
echo "🔍 API DEBUG WRAPPER STARTING"
echo "=========================================="
echo "Time: $(date)"
echo "Working Directory: $(pwd)"
echo "Python Version: $(python3 --version)"
echo "User: $(whoami)"
echo ""

# Check environment variables
echo "🔍 ENVIRONMENT VARIABLES:"
echo "----------------------------------------"
env | grep -E "(API|NEO4J|QDRANT|REDIS|PYTHON|LOG)" | sort
echo ""

# Check if config file exists
echo "🔍 CONFIG FILE CHECK:"
echo "----------------------------------------"
if [ -f ".ctxrc.yaml" ]; then
    echo "✅ .ctxrc.yaml exists"
    echo "File size: $(stat -c%s .ctxrc.yaml) bytes"
    echo "First 5 lines:"
    head -5 .ctxrc.yaml
else
    echo "❌ ERROR: .ctxrc.yaml NOT FOUND!"
    echo "Current directory contents:"
    ls -la
fi
echo ""

# Check Python imports
echo "🔍 TESTING PYTHON IMPORTS:"
echo "----------------------------------------"
python3 -c "
import sys
print(f'Python path: {sys.path}')
try:
    from src.api import main
    print('✅ src.api.main import successful')
except Exception as e:
    print(f'❌ ERROR importing src.api.main: {e}')
    import traceback
    traceback.print_exc()
"
echo ""

# Check for syntax errors
echo "🔍 CHECKING FOR SYNTAX ERRORS:"
echo "----------------------------------------"
python3 -m py_compile src/api/main.py 2>&1
if [ $? -eq 0 ]; then
    echo "✅ No syntax errors in src/api/main.py"
else
    echo "❌ SYNTAX ERROR DETECTED!"
fi
echo ""

# Try to start the API with maximum verbosity
echo "🔍 STARTING API WITH MAXIMUM DEBUG OUTPUT:"
echo "=========================================="
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export LOG_LEVEL=DEBUG

# Capture both stdout and stderr
exec 2>&1

# Start with Python verbose mode to see all imports
echo "Starting uvicorn with full traceback..."
python3 -v -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --log-level debug 2>&1 | while IFS= read -r line; do
    echo "[$(date +%H:%M:%S)] $line"
    
    # Detect and highlight errors
    if echo "$line" | grep -iE "(error|exception|failed|traceback|critical)" > /dev/null; then
        echo "🚨🚨🚨 ERROR DETECTED 🚨🚨🚨"
        echo "$line"
        echo "🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨"
    fi
done

# If we get here, the process exited
EXIT_CODE=$?
echo ""
echo "=========================================="
echo "🔴 API PROCESS EXITED WITH CODE: $EXIT_CODE"
echo "=========================================="

# Final diagnostic
if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ API FAILED TO START!"
    echo "Common causes:"
    echo "1. Missing dependencies"
    echo "2. Import errors"
    echo "3. Configuration issues"
    echo "4. Port already in use"
    echo "5. Syntax errors"
fi

exit $EXIT_CODE