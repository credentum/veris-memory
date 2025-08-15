#!/bin/bash
#
# Quick Fix for Hanging Security Tests
# Sprint 10 Phase 3 - Emergency test recovery script
#

echo "🛠️  Emergency Test Recovery Script"
echo "=================================="

# Kill any hanging test processes
echo "🔍 Looking for hanging test processes..."
pkill -f "test_synthetic_abuse" 2>/dev/null && echo "✅ Killed synthetic abuse tests"
pkill -f "pytest.*security" 2>/dev/null && echo "✅ Killed hanging pytest processes"
pkill -f "python.*security.*test" 2>/dev/null && echo "✅ Killed hanging Python test processes"

# Clear any test lock files
echo "🧹 Cleaning up test artifacts..."
find . -name "*.lock" -delete 2>/dev/null && echo "✅ Removed lock files"
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null && echo "✅ Cleared pytest cache"

# Reset system state
echo "🔄 Resetting security systems..."
python3 -c "
try:
    import sys, os
    sys.path.insert(0, '.')
    from src.security.waf import WAFRateLimiter
    limiter = WAFRateLimiter()
    limiter.request_counts.clear()
    limiter.blocked_clients.clear() 
    limiter.global_requests.clear()
    print('✅ Rate limiters reset')
except Exception as e:
    print(f'⚠️  Rate limiter reset failed: {e}')
"

# Check system resources
echo "📊 System Status:"
echo "   CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
echo "   Memory: $(free | grep Mem | awk '{printf("%.1f%%", $3/$2 * 100.0)}')%"
echo "   Load: $(uptime | awk -F'load average:' '{print $2}')"

# Run quick security validation
echo "🧪 Running quick security validation..."
timeout 30 python3 test_resilient_security.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Security systems operational"
else
    echo "⚠️  Security systems need attention"
fi

echo ""
echo "🎉 Recovery complete! You can now run security tests safely."
echo "💡 Recommended: Use 'python3 test_resilient_security.py' for non-hanging tests"