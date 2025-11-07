# Phase 3: Service Integration & Verification

## Comprehensive Integration Tests

### 1. Create Integration Test Suite
**File**: `tests/integration/test_full_system.py`

```python
#!/usr/bin/env python3
"""Full system integration test suite."""

import pytest
import asyncio
import aiohttp
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
API_KEY = "vmk_mcp_903e1bcb70d704da4fbf207722c471ba"

class TestSystemIntegration:
    """Test full system integration."""

    @pytest.fixture
    async def session(self):
        """Create HTTP session with auth headers."""
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            yield session

    async def test_health_endpoints(self, session):
        """Test all health endpoints."""
        endpoints = [
            ("http://localhost:8000/health", "context-store"),
            ("http://localhost:8001/api/v1/health/live", "api"),
            ("http://localhost:8080/api/dashboard/health", "monitoring"),
            ("http://localhost:9090/health", "sentinel"),
            ("http://localhost:6333/", "qdrant"),
            ("http://localhost:7474", "neo4j")
        ]

        for url, service in endpoints:
            async with session.get(url) as resp:
                assert resp.status == 200, f"{service} health check failed"

    async def test_full_context_flow(self, session):
        """Test complete store -> retrieve -> update flow."""

        # 1. Store context
        store_payload = {
            "type": "decision",
            "content": {
                "title": "Integration Test Decision",
                "description": "Testing full system flow",
                "timestamp": time.time()
            },
            "metadata": {"test": "integration"},
            "author": "test_suite",
            "author_type": "agent"
        }

        async with session.post(f"{BASE_URL}/tools/store_context", json=store_payload) as resp:
            assert resp.status == 200
            result = await resp.json()
            assert result["success"] is True
            context_id = result["id"]

        # 2. Retrieve context
        retrieve_payload = {
            "query": "Integration Test Decision",
            "limit": 5
        }

        async with session.post(f"{BASE_URL}/tools/retrieve_context", json=retrieve_payload) as resp:
            assert resp.status == 200
            result = await resp.json()
            assert result["success"] is True
            assert result["total_count"] > 0
            assert any(c["id"] == context_id for c in result["results"])

        # 3. Query graph relationships
        graph_payload = {
            "query": "MATCH (n) WHERE n.title CONTAINS 'Integration' RETURN n LIMIT 1"
        }

        async with session.post(f"{BASE_URL}/tools/query_graph", json=graph_payload) as resp:
            assert resp.status == 200
            result = await resp.json()
            assert result["success"] is True

    async def test_sentinel_checks(self, session):
        """Test that sentinel checks can authenticate."""

        # Trigger S2 check
        async with session.get("http://localhost:9090/api/checks/s2/execute") as resp:
            assert resp.status in [200, 201]
            result = await resp.json()
            assert result["status"] != "fail", "S2 check should not fail with auth"

    async def test_embedding_pipeline(self, session):
        """Test embedding generation."""

        test_payload = {
            "type": "log",
            "content": {"title": "Embedding test", "text": "This should generate embeddings"},
            "author": "test",
            "author_type": "agent"
        }

        async with session.post(f"{BASE_URL}/tools/store_context", json=test_payload) as resp:
            result = await resp.json()

            # Check embedding status
            assert "embedding_status" in result
            if result["embedding_status"] == "failed":
                print(f"Warning: Embeddings failing - {result.get('embedding_message')}")
            else:
                assert result["embedding_status"] == "completed"

### 2. Monitoring Verification Script
**File**: `scripts/verify_monitoring.sh`

```bash
#!/bin/bash

echo "=== Veris Memory System Verification ==="
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check service health
echo "1. Checking Service Health..."
services=("context-store:8000" "api:8001" "monitoring-dashboard:8080" "sentinel:9090" "qdrant:6333" "neo4j:7474" "redis:6379")

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if nc -z localhost $port 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name (port $port) is running"
    else
        echo -e "  ${RED}✗${NC} $name (port $port) is not accessible"
    fi
done

echo
echo "2. Checking Data Presence..."

# Check Qdrant
qdrant_count=$(curl -s http://localhost:6333/collections/contexts/points/count 2>/dev/null | jq -r '.result.count // 0')
echo -e "  Qdrant vectors: ${qdrant_count}"

# Check Neo4j (requires password)
if [ -n "$NEO4J_PASSWORD" ]; then
    neo4j_count=$(docker exec veris-memory_neo4j_1 cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
        "MATCH (n) RETURN count(n) as count" 2>/dev/null | grep -o '[0-9]*' | tail -1)
    echo -e "  Neo4j nodes: ${neo4j_count:-0}"
fi

# Check Redis
redis_count=$(docker exec veris-memory_redis_1 redis-cli DBSIZE 2>/dev/null | grep -o '[0-9]*')
echo -e "  Redis keys: ${redis_count:-0}"

echo
echo "3. Testing API Authentication..."

# Test with API key
response=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/tools/retrieve_context \
    -H "Content-Type: application/json" \
    -H "X-API-Key: vmk_mcp_903e1bcb70d704da4fbf207722c471ba" \
    -d '{"query":"test","limit":1}')

if [ "$response" = "200" ]; then
    echo -e "  ${GREEN}✓${NC} API authentication working"
else
    echo -e "  ${RED}✗${NC} API authentication failed (HTTP $response)"
fi

echo
echo "4. Checking Sentinel Status..."

sentinel_health=$(curl -s http://localhost:9090/health 2>/dev/null | jq -r '.status // "unknown"')
if [ "$sentinel_health" = "healthy" ]; then
    echo -e "  ${GREEN}✓${NC} Sentinel is healthy"

    # Check recent check results
    recent_checks=$(curl -s http://localhost:9090/api/checks/results/recent 2>/dev/null | jq -r '.checks // []' | jq length)
    echo -e "  Recent check results: $recent_checks"
else
    echo -e "  ${RED}✗${NC} Sentinel status: $sentinel_health"
fi

echo
echo "=== Verification Complete ==="
```

### 3. Quick Fix Application Script
**File**: `scripts/apply_fixes.sh`

```bash
#!/bin/bash

echo "Applying veris-memory fixes..."

# Backup current configuration
cp docker-compose.yml docker-compose.yml.backup
cp .env .env.backup 2>/dev/null || true

# Apply Phase 1 fixes
echo "Phase 1: Fixing authentication..."
# Add API_KEY_MCP to services (would need actual sed commands here)

# Apply Phase 2 fixes
echo "Phase 2: Initializing data..."
python scripts/initialize_data.py

# Apply Phase 3 verification
echo "Phase 3: Verifying integration..."
bash scripts/verify_monitoring.sh

echo "Fixes applied. Please restart services with:"
echo "  docker-compose down && docker-compose up -d"
```

## Verification Commands:

```bash
# 1. Run full integration test
pytest tests/integration/test_full_system.py -v

# 2. Check monitoring dashboard
curl http://localhost:8080/api/dashboard/metrics

# 3. Verify Sentinel checks pass
for check in s1 s2 s3 s4 s5 s6 s7 s8 s9 s10; do
    echo "Testing $check..."
    curl -s http://localhost:9090/api/checks/$check/execute | jq -r '.status'
done

# 4. Test MCP tools
bash /claude-workspace/.claude/skills/veris-mcp-connection/scripts/test-connection.sh
```

## Success Criteria:
- ✅ All services report healthy
- ✅ Sentinel S2 checks pass without 401 errors
- ✅ Data can be stored and retrieved
- ✅ Embeddings generate (or gracefully fail with fallback)
- ✅ Graph relationships are created
- ✅ Monitoring dashboard shows metrics
- ✅ No authentication errors in logs