#!/bin/bash
#
# Deployment Validation Script
# 
# Validates that deployed API uses real backends and prevents the >95% failure
# rate caused by mock backends in production.
#
# Usage: ./scripts/validate-deployment.sh [API_URL]
#

set -euo pipefail

API_URL="${1:-http://173.17.0.2:8000}"
VALIDATION_FAILED=0

echo "🔍 Validating Veris Memory deployment at $API_URL..."
echo "📋 Checking for mock backend deployment issues..."
echo ""

# Function to perform API health check
check_health_endpoint() {
    local endpoint="$1"
    local description="$2"
    
    echo "🔍 Checking $description..."
    
    local response
    if ! response=$(curl -s --max-time 10 "$API_URL$endpoint" 2>/dev/null); then
        echo "❌ FAILED: Cannot reach $endpoint"
        return 1
    fi
    
    echo "✅ SUCCESS: $endpoint responded"
    echo "   Response: $response"
    return 0
}

# Function to check for mock backend indicators
check_for_mock_backends() {
    echo ""
    echo "🚨 CRITICAL: Checking for mock backend deployment..."
    
    local health_response
    if ! health_response=$(curl -s --max-time 10 "$API_URL/api/v1/health/detailed" 2>/dev/null); then
        echo "⚠️  WARNING: Cannot check detailed health endpoint"
        echo "   This could indicate the API is not fully deployed"
        return 1
    fi
    
    # Check for any mention of "mock" in the response
    if echo "$health_response" | grep -qi "mock"; then
        echo "❌ DEPLOYMENT FAILURE: API is using mock backends!"
        echo "🚨 This will cause >95% failure rate in production!"
        echo ""
        echo "📄 Health Response:"
        echo "$health_response"
        echo ""
        echo "🔧 FIX REQUIRED:"
        echo "   1. Check docker-compose.yml for USE_MOCK_BACKENDS=true"
        echo "   2. Check Dockerfile.api for USE_MOCK_BACKENDS=true"
        echo "   3. Ensure API connects to real Neo4j/Qdrant/Redis"
        echo "   4. Redeploy with real backend configuration"
        return 1
    fi
    
    echo "✅ SUCCESS: No mock backend indicators found"
    return 0
}

# Function to check backend connectivity
check_backend_connectivity() {
    echo ""
    echo "🔗 Checking real backend connectivity..."
    
    local health_response
    if ! health_response=$(curl -s --max-time 10 "$API_URL/api/v1/health/detailed" 2>/dev/null); then
        echo "⚠️  Cannot get detailed health status"
        return 1
    fi
    
    local backends_connected=0
    
    # Check Neo4j connectivity
    if echo "$health_response" | grep -qi "neo4j.*connected\|graph.*connected"; then
        echo "✅ Neo4j backend connected"
        ((backends_connected++))
    else
        echo "⚠️  Neo4j backend not connected"
    fi
    
    # Check Qdrant connectivity  
    if echo "$health_response" | grep -qi "qdrant.*connected\|vector.*connected"; then
        echo "✅ Qdrant backend connected"
        ((backends_connected++))
    else
        echo "⚠️  Qdrant backend not connected"
    fi
    
    # Check Redis connectivity
    if echo "$health_response" | grep -qi "redis.*connected\|kv.*connected"; then
        echo "✅ Redis backend connected"
        ((backends_connected++))
    else
        echo "⚠️  Redis backend not connected"
    fi
    
    if [ $backends_connected -eq 0 ]; then
        echo "❌ DEPLOYMENT ISSUE: No backends connected"
        echo "   API will have severely limited functionality"
        return 1
    elif [ $backends_connected -lt 3 ]; then
        echo "⚠️  WARNING: Only $backends_connected/3 backends connected"
        echo "   Some functionality may be limited"
        return 0
    else
        echo "✅ SUCCESS: All backends connected ($backends_connected/3)"
        return 0
    fi
}

# Function to test basic API functionality
test_api_functionality() {
    echo ""
    echo "🧪 Testing basic API functionality..."
    
    # Test root endpoint
    if ! check_health_endpoint "/" "API root endpoint"; then
        return 1
    fi
    
    # Test health endpoints
    if ! check_health_endpoint "/api/v1/health" "Basic health check"; then
        return 1
    fi
    
    if ! check_health_endpoint "/api/v1/health/live" "Liveness probe"; then
        return 1
    fi
    
    if ! check_health_endpoint "/api/v1/health/ready" "Readiness probe"; then
        return 1
    fi
    
    # Test API documentation
    if ! check_health_endpoint "/docs" "API documentation"; then
        return 1
    fi
    
    echo "✅ SUCCESS: Basic API functionality working"
    return 0
}

# Main validation sequence
echo "🚀 Starting deployment validation..."
echo "   Target: $API_URL"
echo "   Time: $(date)"
echo ""

# 1. Test basic API functionality
if ! test_api_functionality; then
    echo "❌ VALIDATION FAILED: Basic API functionality issues"
    VALIDATION_FAILED=1
fi

# 2. Critical check for mock backends
if ! check_for_mock_backends; then
    echo "❌ VALIDATION FAILED: Mock backend deployment detected"
    VALIDATION_FAILED=1
fi

# 3. Check backend connectivity
if ! check_backend_connectivity; then
    echo "❌ VALIDATION FAILED: Backend connectivity issues"
    VALIDATION_FAILED=1
fi

# Final result
echo ""
echo "===================="
if [ $VALIDATION_FAILED -eq 0 ]; then
    echo "✅ DEPLOYMENT VALIDATION PASSED"
    echo "   The API is properly deployed with real backends"
    echo "   No mock backend deployment issues detected"
    echo "   Production deployment is safe to use"
else
    echo "❌ DEPLOYMENT VALIDATION FAILED"
    echo "   Critical issues found that will cause production failures"
    echo "   DO NOT USE THIS DEPLOYMENT IN PRODUCTION"
    echo "   Fix the issues above and redeploy"
fi
echo "===================="

exit $VALIDATION_FAILED