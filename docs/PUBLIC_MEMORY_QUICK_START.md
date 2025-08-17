# Quick Start: Minimum Viable Public Memory Implementation

## Immediate Implementation (1-2 Days)

### Step 1: Add Visibility Field to StoreContextRequest

**File: `src/mcp_server/main.py`**

```python
# Add to existing StoreContextRequest (line ~300)
class StoreContextRequest(BaseModel):
    content: Dict[str, Any]
    type: str = Field(..., pattern="^(design|decision|trace|sprint|log|public_knowledge|shared_doc)$")
    metadata: Optional[Dict[str, Any]] = None
    relationships: Optional[List[Dict[str, str]]] = None
    # NEW FIELDS
    visibility: str = Field(default="private", pattern="^(private|public|team)$")
    agent_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
```

### Step 2: Modify Neo4j Storage to Include Visibility

**File: `src/storage/neo4j_client.py`**

```python
# Modify create_context method (around line 200)
def create_context(self, properties: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new context node with visibility"""
    
    # Extract visibility (default to private)
    visibility = properties.get('visibility', 'private')
    agent_id = properties.get('agent_id')
    
    # Add visibility label
    labels = ["Context", visibility.capitalize()]
    
    query = f"""
        CREATE (n:{':'.join(labels)})
        SET n = $properties
        SET n.id = randomUUID()
        SET n.created_at = timestamp()
        SET n.visibility = $visibility
        {'SET n.agent_id = $agent_id' if agent_id else ''}
        RETURN n
    """
    
    result = self.execute_query(
        query, 
        properties=properties,
        visibility=visibility,
        agent_id=agent_id
    )
    return result[0]["n"] if result else None
```

### Step 3: Add Visibility Filtering to Retrieval

**File: `src/mcp_server/main.py`**

```python
# Modify retrieve_context endpoint (around line 800)
@app.post("/tools/retrieve_context")
async def retrieve_context(request: RetrieveContextRequest):
    """Retrieve context data with visibility filtering"""
    
    # Extract agent_id from request or headers
    agent_id = request.filters.get('agent_id') if request.filters else None
    
    # Build visibility filter
    visibility_filter = build_visibility_filter(agent_id)
    
    # Add to existing filters
    enhanced_filters = {
        **(request.filters or {}),
        'visibility_filter': visibility_filter
    }
    
    # Continue with existing logic...

def build_visibility_filter(agent_id: Optional[str]) -> str:
    """Build Cypher WHERE clause for visibility"""
    if not agent_id:
        # Anonymous users only see public
        return "n.visibility = 'public'"
    
    # Authenticated users see their private + all public
    return f"""(
        n.visibility = 'public' OR 
        (n.visibility = 'private' AND n.agent_id = '{agent_id}')
    )"""
```

### Step 4: Modify Graph Queries to Respect Visibility

**File: `src/storage/neo4j_client.py`**

```python
# Modify search_similar method (around line 400)
def search_similar(self, embedding: List[float], type_filter: str = "all", 
                   limit: int = 10, agent_id: Optional[str] = None) -> List[Dict]:
    """Search for similar contexts with visibility filtering"""
    
    # Build visibility WHERE clause
    visibility_clause = self._build_visibility_clause(agent_id)
    
    query = f"""
        MATCH (n:Context)
        WHERE ({type_filter == 'all' or 'n.type = $type'})
        AND {visibility_clause}
        RETURN n, 
               gds.similarity.cosine(n.embedding, $embedding) AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
    """
    
    # Execute with parameters...

def _build_visibility_clause(self, agent_id: Optional[str]) -> str:
    """Build WHERE clause for visibility filtering"""
    if not agent_id:
        return "n.visibility = 'public'"
    
    return f"""(
        n.visibility = 'public' OR
        (n.visibility = 'private' AND n.agent_id = '{agent_id}')
    )"""
```

### Step 5: Quick Test Script

**File: `scripts/test_public_memory.py`**

```python
import asyncio
import aiohttp
import json

async def test_public_memory():
    base_url = "http://localhost:8000"
    
    # Test 1: Store public knowledge
    public_context = {
        "content": {
            "text": "Veris Memory is a context storage system",
            "type": "public_knowledge",
            "title": "About Veris Memory"
        },
        "type": "public_knowledge",
        "visibility": "public",
        "agent_id": "test_agent_1",
        "metadata": {"category": "documentation"}
    }
    
    async with aiohttp.ClientSession() as session:
        # Store public context
        async with session.post(
            f"{base_url}/tools/store_context",
            json=public_context
        ) as resp:
            result = await resp.json()
            print(f"Stored public: {result}")
        
        # Test 2: Store private context
        private_context = {
            **public_context,
            "content": {
                **public_context["content"],
                "text": "My private notes",
                "title": "Private Notes"
            },
            "visibility": "private"
        }
        
        async with session.post(
            f"{base_url}/tools/store_context",
            json=private_context
        ) as resp:
            result = await resp.json()
            print(f"Stored private: {result}")
        
        # Test 3: Retrieve as different agent
        retrieve_request = {
            "query": "Veris Memory",
            "filters": {"agent_id": "different_agent"}
        }
        
        async with session.post(
            f"{base_url}/tools/retrieve_context",
            json=retrieve_request
        ) as resp:
            result = await resp.json()
            print(f"Different agent sees: {len(result['results'])} results")
            # Should only see public context
        
        # Test 4: Retrieve as original agent
        retrieve_request["filters"]["agent_id"] = "test_agent_1"
        
        async with session.post(
            f"{base_url}/tools/retrieve_context",
            json=retrieve_request
        ) as resp:
            result = await resp.json()
            print(f"Original agent sees: {len(result['results'])} results")
            # Should see both public and private

asyncio.run(test_public_memory())
```

## Next Steps (Week 1)

### 1. Add Qdrant Visibility Filtering

```python
# In qdrant_client.py
def search_with_visibility(self, query_vector, agent_id=None):
    should_conditions = [
        models.FieldCondition(
            key="metadata.visibility",
            match=models.MatchValue(value="public")
        )
    ]
    
    if agent_id:
        should_conditions.append(
            models.Filter(must=[
                models.FieldCondition(
                    key="metadata.visibility",
                    match=models.MatchValue(value="private")
                ),
                models.FieldCondition(
                    key="metadata.agent_id",
                    match=models.MatchValue(value=agent_id)
                )
            ])
        )
```

### 2. Add Database Indexes

```sql
-- Neo4j indexes for performance
CREATE INDEX visibility_idx FOR (n:Context) ON (n.visibility);
CREATE INDEX agent_idx FOR (n:Context) ON (n.agent_id);
CREATE INDEX composite_idx FOR (n:Context) ON (n.visibility, n.agent_id);
```

### 3. Add Configuration Toggle

```python
# In config.py
class PublicMemoryConfig(BaseModel):
    enabled: bool = Field(default=False, env="ENABLE_PUBLIC_MEMORY")
    allow_anonymous: bool = Field(default=True, env="ALLOW_ANONYMOUS_PUBLIC_READ")
    require_agent_auth: bool = Field(default=False, env="REQUIRE_AGENT_AUTH")
```

## Benefits of This Approach

✅ **Minimal Changes**: Only modifies critical paths
✅ **Backward Compatible**: Old requests default to private
✅ **Immediately Useful**: Public docs/knowledge shareable
✅ **Safe Default**: Everything private unless specified
✅ **Easy Testing**: Simple test script to verify

## Migration for Existing Data

```python
# One-time migration script
async def migrate_existing():
    query = """
        MATCH (n:Context)
        WHERE NOT EXISTS(n.visibility)
        SET n.visibility = 'private'
        RETURN count(n) as migrated
    """
    # Run on Neo4j
    
    # Update Qdrant metadata
    for doc in qdrant_client.scroll():
        if 'visibility' not in doc.metadata:
            doc.metadata['visibility'] = 'private'
            qdrant_client.update(doc.id, metadata=doc.metadata)
```

This minimal implementation gives you public/private memory separation in 1-2 days!