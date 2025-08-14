#!/usr/bin/env python3
"""
BUGFIX_IMPLEMENTATION.py - Direct code fixes for Veris Memory critical bugs

This file contains the exact code changes needed to fix the identified issues.
Apply these changes to the corresponding files in the codebase.
"""

# ============================================================================
# FIX 1: Qdrant Client Usage (src/mcp_server/main.py)
# ============================================================================

"""
FILE: src/mcp_server/main.py
LINE: ~317

CURRENT (BROKEN):
    qdrant_client = qdrant_initializer.client

REPLACE WITH:
    qdrant_client = qdrant_initializer
"""

# ============================================================================
# FIX 2: Store Vector Method Call (src/mcp_server/main.py)
# ============================================================================

"""
FILE: src/mcp_server/main.py
LINES: 762-771

CURRENT (BROKEN):
    vector_id = qdrant_client.store_vector(
        collection="context_store",
        id=context_id,
        vector=embedding,
        payload={
            "content": request.content,
            "type": request.type,
            "metadata": request.metadata,
        },
    )

REPLACE WITH:
    vector_id = qdrant_client.store_vector(
        vector_id=context_id,
        embedding=embedding,
        metadata={
            "content": request.content,
            "type": request.type,
            "metadata": request.metadata,
        }
    )
"""

# ============================================================================
# FIX 3: Neo4j Query Timeout (src/mcp_server/main.py)
# ============================================================================

"""
FILE: src/mcp_server/main.py
LINES: 902-906

CURRENT (BROKEN):
    results = neo4j_client.query(
        request.query,
        parameters=request.parameters,
        timeout=request.timeout / 1000,  # Convert to seconds
    )

REPLACE WITH:
    results = neo4j_client.query(
        request.query,
        parameters=request.parameters
    )
    # Note: timeout handling can be added to Neo4jInitializer.query() method later
"""

# ============================================================================
# FIX 4: Add Missing Endpoints (src/mcp_server/main.py)
# ============================================================================

"""
FILE: src/mcp_server/main.py
LOCATION: Add after line ~917 (after query_graph endpoint)

ADD THESE NEW ENDPOINTS:
"""

from typing import Optional
from pydantic import BaseModel, Field


class UpdateScratchpadRequest(BaseModel):
    """Request model for update_scratchpad tool."""
    agent_id: str = Field(..., description="Agent identifier")
    key: str = Field(..., description="Scratchpad key")
    value: Any = Field(..., description="Value to store")
    ttl: int = Field(3600, ge=1, le=86400, description="Time to live in seconds")


class GetAgentStateRequest(BaseModel):
    """Request model for get_agent_state tool."""
    agent_id: str = Field(..., description="Agent identifier")
    key: Optional[str] = Field(None, description="Specific state key")
    prefix: str = Field("state", description="State type prefix")


# Add these endpoints to main.py:

@app.post("/tools/update_scratchpad")
async def update_scratchpad_endpoint(request: UpdateScratchpadRequest) -> Dict[str, Any]:
    """
    Update agent scratchpad with transient storage.
    
    Provides temporary storage for agent working memory with TTL support.
    """
    try:
        if not kv_store:
            raise HTTPException(status_code=503, detail="KV store not available")
        
        # Create namespaced key
        redis_key = f"scratchpad:{request.agent_id}:{request.key}"
        
        # Store value with TTL
        import json
        value_str = json.dumps(request.value) if not isinstance(request.value, str) else request.value
        success = kv_store.set(redis_key, value_str, ex=request.ttl)
        
        if success:
            return {
                "success": True,
                "agent_id": request.agent_id,
                "key": request.key,
                "ttl": request.ttl,
                "message": "Scratchpad updated successfully"
            }
        else:
            return {
                "success": False,
                "message": "Failed to update scratchpad"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scratchpad update error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Internal error updating scratchpad"
        }


@app.post("/tools/get_agent_state")
async def get_agent_state_endpoint(request: GetAgentStateRequest) -> Dict[str, Any]:
    """
    Retrieve agent state from storage.
    
    Returns agent-specific state data with namespace isolation.
    """
    try:
        if not kv_store:
            raise HTTPException(status_code=503, detail="KV store not available")
        
        # Build key pattern
        if request.key:
            redis_key = f"{request.prefix}:{request.agent_id}:{request.key}"
            value = kv_store.get(redis_key)
            
            if value is None:
                return {
                    "success": False,
                    "data": {},
                    "message": f"No state found for key: {request.key}"
                }
            
            # Parse JSON if possible
            try:
                import json
                data = json.loads(value) if isinstance(value, bytes) else value
            except:
                data = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return {
                "success": True,
                "data": {request.key: data},
                "agent_id": request.agent_id,
                "message": "State retrieved successfully"
            }
        else:
            # Get all keys for agent
            pattern = f"{request.prefix}:{request.agent_id}:*"
            keys = kv_store.keys(pattern)
            
            if not keys:
                return {
                    "success": True,
                    "data": {},
                    "keys": [],
                    "agent_id": request.agent_id,
                    "message": "No state found for agent"
                }
            
            # Retrieve all values
            data = {}
            for key in keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                key_name = key_str.split(':', 2)[-1]  # Extract key name
                value = kv_store.get(key)
                
                try:
                    import json
                    data[key_name] = json.loads(value) if isinstance(value, bytes) else value
                except:
                    data[key_name] = value.decode('utf-8') if isinstance(value, bytes) else value
            
            return {
                "success": True,
                "data": data,
                "keys": list(data.keys()),
                "agent_id": request.agent_id,
                "message": f"Retrieved {len(data)} state entries"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent state retrieval error: {e}")
        return {
            "success": False,
            "data": {},
            "error": str(e),
            "message": "Internal error retrieving agent state"
        }


# ============================================================================
# FIX 5: Update Tool List (src/mcp_server/main.py)
# ============================================================================

"""
FILE: src/mcp_server/main.py
LINE: ~640-644

CURRENT:
    "tools": [
        "store_context",
        "retrieve_context",
        "query_graph",
        "update_scratchpad",
        "get_agent_state",
    ],

This is actually correct - just make sure the endpoints exist!
"""

# ============================================================================
# OPTIONAL FIX: Add Timeout to Neo4j Query (src/storage/neo4j_client.py)
# ============================================================================

"""
FILE: src/storage/neo4j_client.py
LINE: ~447

CURRENT:
    def query(self, cypher: str, parameters: Optional[JSON] = None) -> QueryResult:

REPLACE WITH:
    def query(self, cypher: str, parameters: Optional[JSON] = None, timeout: Optional[float] = None) -> QueryResult:

AND UPDATE THE IMPLEMENTATION:
    with self.driver.session(database=self.database) as session:
        # Use timeout if provided
        if timeout:
            result = session.run(cypher, parameters or {}, timeout=timeout)
        else:
            result = session.run(cypher, parameters or {})
        
        # Convert to list of dictionaries
        return [dict(record) for record in result]
"""

# ============================================================================
# TEST SCRIPT
# ============================================================================

def test_all_endpoints():
    """Test script to verify all fixes are working."""
    import requests
    import json
    
    base_url = "http://172.17.0.1:8000"
    
    print("Testing Veris Memory Endpoints...")
    print("=" * 50)
    
    # Test 1: Store Context
    print("\n1. Testing store_context...")
    response = requests.post(
        f"{base_url}/tools/store_context",
        json={
            "type": "design",
            "content": {
                "title": "Bug Fix Test",
                "description": "Testing after bug fixes",
                "timestamp": "2025-01-14T12:00:00Z"
            },
            "metadata": {
                "author": "test-script",
                "version": "1.0.0"
            }
        }
    )
    print(f"   Status: {response.status_code}")
    print(f"   Result: {response.json()}")
    
    # Test 2: Retrieve Context
    print("\n2. Testing retrieve_context...")
    response = requests.post(
        f"{base_url}/tools/retrieve_context",
        json={
            "query": "bug fix",
            "limit": 5,
            "include_metadata": True
        }
    )
    print(f"   Status: {response.status_code}")
    result = response.json()
    print(f"   Found: {result.get('total_count', 0)} contexts")
    
    # Test 3: Query Graph
    print("\n3. Testing query_graph...")
    response = requests.post(
        f"{base_url}/tools/query_graph",
        json={
            "query": "MATCH (n) RETURN count(n) as total",
            "parameters": {}
        }
    )
    print(f"   Status: {response.status_code}")
    print(f"   Result: {response.json()}")
    
    # Test 4: Update Scratchpad
    print("\n4. Testing update_scratchpad...")
    response = requests.post(
        f"{base_url}/tools/update_scratchpad",
        json={
            "agent_id": "test-agent",
            "key": "working_memory",
            "value": {"test": "data", "timestamp": "2025-01-14"},
            "ttl": 3600
        }
    )
    print(f"   Status: {response.status_code}")
    print(f"   Result: {response.json()}")
    
    # Test 5: Get Agent State
    print("\n5. Testing get_agent_state...")
    response = requests.post(
        f"{base_url}/tools/get_agent_state",
        json={
            "agent_id": "test-agent",
            "prefix": "scratchpad"
        }
    )
    print(f"   Status: {response.status_code}")
    print(f"   Result: {response.json()}")
    
    print("\n" + "=" * 50)
    print("Testing complete!")


if __name__ == "__main__":
    print("This file contains code fixes to be applied to Veris Memory")
    print("Run test_all_endpoints() after applying fixes to verify")
    # Uncomment to run tests:
    # test_all_endpoints()