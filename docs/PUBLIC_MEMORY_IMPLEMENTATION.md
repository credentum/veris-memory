# Public/Shareable Memory Implementation Plan for Veris Memory

## Executive Summary
Extend Veris Memory to support both private (agent-scoped) and public (shareable) memory contexts while maintaining backward compatibility and security.

## Phase 1: Foundation & Schema Extension (Week 1-2)

### 1.1 Extend Type System
**File: `src/mcp_server/main.py`**

```python
class VisibilityScope(str, Enum):
    PRIVATE = "private"      # Agent-only access (default)
    TEAM = "team"           # Team/organization access
    PUBLIC = "public"       # Global access across all agents
    SHARED = "shared"       # Explicitly shared with specific agents

class StoreContextRequest(BaseModel):
    content: Dict[str, Any]
    type: str = Field(..., pattern="^(design|decision|trace|sprint|log|knowledge|documentation)$")
    visibility: VisibilityScope = Field(default=VisibilityScope.PRIVATE)
    agent_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    team_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    metadata: Optional[Dict[str, Any]] = None
    relationships: Optional[List[Dict[str, str]]] = None
    shared_with: Optional[List[str]] = None  # For SHARED visibility
```

### 1.2 Database Schema Updates

**Neo4j Labels:**
```cypher
// Add visibility labels
CREATE INDEX visibility_idx FOR (n:Context) ON (n.visibility);
CREATE INDEX agent_idx FOR (n:Context) ON (n.agent_id);
CREATE INDEX team_idx FOR (n:Context) ON (n.team_id);

// Example node structure
(:Context:Public {
    id: "uuid",
    type: "documentation",
    visibility: "public",
    agent_id: "creator_agent_id",
    team_id: "team_uuid",
    created_at: timestamp()
})
```

**Qdrant Metadata:**
```python
# Enhanced metadata structure
metadata = {
    "content": request.content,
    "type": request.type,
    "visibility": request.visibility,
    "agent_id": request.agent_id,
    "team_id": request.team_id,
    "created_at": datetime.utcnow().isoformat(),
    "metadata": request.metadata
}
```

### 1.3 Configuration Updates
**File: `src/core/config.py`**

```python
class VisibilityConfig(BaseModel):
    enable_public_memory: bool = Field(default=False, env="ENABLE_PUBLIC_MEMORY")
    default_visibility: str = Field(default="private", env="DEFAULT_VISIBILITY")
    require_agent_id: bool = Field(default=True, env="REQUIRE_AGENT_ID")
    allow_anonymous_read: bool = Field(default=False, env="ALLOW_ANONYMOUS_READ")
    max_public_contexts_per_agent: int = Field(default=1000, env="MAX_PUBLIC_CONTEXTS")
```

## Phase 2: Storage Layer Implementation (Week 2-3)

### 2.1 Extend Storage Clients

**File: `src/storage/neo4j_client.py`**
```python
def create_context_with_visibility(self, properties: Dict, visibility: str, agent_id: str = None):
    """Create context node with visibility scoping"""
    labels = ["Context", visibility.capitalize()]
    
    if visibility == "private" and agent_id:
        properties["agent_id"] = agent_id
    
    query = """
        CREATE (n:Context:%s $props)
        SET n.created_at = timestamp()
        RETURN n
    """ % ":".join(labels)
    
    return self.execute_query(query, props=properties)

def retrieve_with_visibility(self, agent_id: str, include_public: bool = True):
    """Retrieve contexts respecting visibility rules"""
    query = """
        MATCH (n:Context)
        WHERE (
            n.visibility = 'public' OR
            (n.visibility = 'private' AND n.agent_id = $agent_id) OR
            (n.visibility = 'team' AND n.team_id IN $team_ids) OR
            (n.visibility = 'shared' AND $agent_id IN n.shared_with)
        )
        RETURN n
        LIMIT $limit
    """
    # Implementation details...
```

**File: `src/storage/qdrant_client.py`**
```python
def search_with_visibility(self, query_vector: List[float], agent_id: str, visibility_filter: List[str]):
    """Search vectors with visibility filtering"""
    must_conditions = []
    should_conditions = []
    
    # Public contexts always included
    should_conditions.append(
        models.FieldCondition(
            key="visibility",
            match=models.MatchValue(value="public")
        )
    )
    
    # Private contexts for this agent
    if agent_id:
        should_conditions.append(
            models.Filter(
                must=[
                    models.FieldCondition(
                        key="visibility",
                        match=models.MatchValue(value="private")
                    ),
                    models.FieldCondition(
                        key="agent_id",
                        match=models.MatchValue(value=agent_id)
                    )
                ]
            )
        )
    
    # Apply filters...
```

### 2.2 Unified Agent Context Manager
**New File: `src/core/context_manager.py`**

```python
class ContextManager:
    """Unified context management with visibility scoping"""
    
    def __init__(self, neo4j_client, qdrant_client, redis_client):
        self.neo4j = neo4j_client
        self.qdrant = qdrant_client
        self.redis = redis_client
        self.agent_namespace = AgentNamespace()
    
    async def store_context(self, request: StoreContextRequest) -> Dict:
        """Store context with appropriate visibility"""
        # Validate agent permissions for public storage
        if request.visibility == VisibilityScope.PUBLIC:
            await self._validate_public_storage_permission(request.agent_id)
        
        # Add visibility metadata
        enhanced_metadata = {
            **request.metadata,
            "visibility": request.visibility,
            "agent_id": request.agent_id,
            "team_id": request.team_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store with appropriate scoping...
    
    async def retrieve_context(self, agent_id: str, query: str, include_public: bool = True):
        """Retrieve contexts respecting visibility rules"""
        # Build visibility filter based on agent context
        visibility_filter = self._build_visibility_filter(agent_id, include_public)
        
        # Search with filtering...
```

## Phase 3: API & Endpoint Updates (Week 3-4)

### 3.1 Enhanced Retrieve Endpoint
**File: `src/mcp_server/main.py`**

```python
class RetrieveContextRequest(BaseModel):
    query: str
    type: Optional[str] = "all"
    search_mode: str = "hybrid"
    limit: int = Field(10, ge=1, le=100)
    filters: Optional[Dict[str, Any]] = None
    include_relationships: bool = False
    # New fields for visibility
    agent_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    visibility_scope: List[VisibilityScope] = Field(
        default=[VisibilityScope.PRIVATE, VisibilityScope.PUBLIC]
    )
    include_team: bool = Field(default=True)
    include_shared: bool = Field(default=True)

@app.post("/tools/retrieve_context")
async def retrieve_context(request: RetrieveContextRequest):
    """Enhanced retrieval with visibility filtering"""
    # Extract agent context
    agent_context = await get_agent_context(request.agent_id)
    
    # Build visibility filters
    visibility_filters = build_visibility_filters(
        agent_id=request.agent_id,
        team_id=agent_context.team_id,
        scopes=request.visibility_scope
    )
    
    # Search with visibility awareness...
```

### 3.2 Public Context Discovery Endpoints
**New Endpoints:**

```python
@app.get("/tools/discover_public")
async def discover_public_contexts(
    category: Optional[str] = None,
    limit: int = 20
):
    """Discover public knowledge and documentation"""
    # Query public contexts only
    
@app.get("/tools/trending_public")
async def get_trending_public_contexts():
    """Get most accessed public contexts"""
    # Analytics on public context usage
    
@app.post("/tools/share_context")
async def share_context(
    context_id: str,
    share_with: List[str],
    agent_id: str
):
    """Share private context with specific agents"""
    # Update context visibility and shared_with list
```

## Phase 4: Security & Access Control (Week 4-5)

### 4.1 Permission System
**New File: `src/core/permissions.py`**

```python
class PermissionManager:
    """Manage context visibility permissions"""
    
    PERMISSION_RULES = {
        VisibilityScope.PRIVATE: {
            "read": ["owner"],
            "write": ["owner"],
            "delete": ["owner"]
        },
        VisibilityScope.TEAM: {
            "read": ["owner", "team_member"],
            "write": ["owner", "team_member"],
            "delete": ["owner", "team_admin"]
        },
        VisibilityScope.PUBLIC: {
            "read": ["*"],
            "write": ["owner"],
            "delete": ["owner", "admin"]
        },
        VisibilityScope.SHARED: {
            "read": ["owner", "shared_with"],
            "write": ["owner"],
            "delete": ["owner"]
        }
    }
    
    async def check_permission(
        self,
        agent_id: str,
        context_id: str,
        action: str
    ) -> bool:
        """Check if agent has permission for action on context"""
        context = await self.get_context_metadata(context_id)
        visibility = context.get("visibility", VisibilityScope.PRIVATE)
        
        # Apply permission rules...
```

### 4.2 Rate Limiting for Public Operations
**File: `src/core/rate_limiter.py` (Enhanced)**

```python
class PublicMemoryRateLimiter(RateLimiter):
    """Special rate limits for public memory operations"""
    
    PUBLIC_WRITE_LIMITS = {
        "requests_per_minute": 10,
        "contexts_per_day": 100,
        "max_content_size": 50000  # 50KB for public
    }
    
    async def check_public_write_limit(self, agent_id: str) -> bool:
        """Check if agent can write to public memory"""
        # Track public writes per agent
        key = f"public_write:{agent_id}:{datetime.utcnow().date()}"
        count = await self.redis.incr(key)
        
        if count > self.PUBLIC_WRITE_LIMITS["contexts_per_day"]:
            raise RateLimitExceeded("Daily public context limit exceeded")
```

## Phase 5: Migration & Backward Compatibility (Week 5-6)

### 5.1 Data Migration Script
**New File: `scripts/migrate_to_visibility.py`**

```python
async def migrate_existing_contexts():
    """Migrate existing contexts to new visibility model"""
    
    # 1. Add visibility field to all existing contexts
    query = """
        MATCH (n:Context)
        WHERE NOT EXISTS(n.visibility)
        SET n.visibility = 'private'
        RETURN count(n) as migrated
    """
    
    # 2. Infer agent_id from existing patterns
    # 3. Update Qdrant metadata
    # 4. Create migration report
```

### 5.2 Backward Compatibility Layer
```python
class BackwardCompatibilityMiddleware:
    """Ensure old clients continue to work"""
    
    async def process_request(self, request):
        # Add default visibility if missing
        if not hasattr(request, 'visibility'):
            request.visibility = VisibilityScope.PRIVATE
        
        # Infer agent_id from headers/context if missing
        if not request.agent_id:
            request.agent_id = await self.infer_agent_id(request)
```

## Phase 6: Testing & Documentation (Week 6-7)

### 6.1 Test Coverage
**New Test Files:**
- `tests/test_visibility_scoping.py`
- `tests/test_public_memory.py`
- `tests/test_permission_system.py`
- `tests/integration/test_multi_agent_sharing.py`

### 6.2 Documentation Updates
- Update API documentation with visibility parameters
- Add public memory usage guide
- Create migration guide for existing deployments
- Add security best practices for public content

## Phase 7: Monitoring & Analytics (Week 7-8)

### 7.1 Public Memory Metrics
```python
class PublicMemoryMetrics:
    """Track public memory usage and patterns"""
    
    metrics = {
        "public_contexts_created": Counter(),
        "public_searches": Counter(),
        "shared_contexts": Counter(),
        "visibility_distribution": Histogram()
    }
```

### 7.2 Audit Logging
```python
class VisibilityAuditLog:
    """Audit trail for visibility changes"""
    
    async def log_visibility_change(
        self,
        context_id: str,
        old_visibility: str,
        new_visibility: str,
        changed_by: str
    ):
        # Log to security audit trail
```

## Implementation Priority & Risk Assessment

### High Priority (Must Have):
1. Basic public/private distinction
2. Agent ID tracking
3. Visibility filtering in retrieval
4. Backward compatibility

### Medium Priority (Should Have):
1. Team-based sharing
2. Explicit sharing with specific agents
3. Rate limiting for public writes
4. Discovery endpoints

### Low Priority (Nice to Have):
1. Advanced permissions
2. Visibility change tracking
3. Public content moderation
4. Usage analytics

### Risk Mitigation:
1. **Data Leakage**: Implement strict visibility filtering at storage layer
2. **Performance**: Add caching for public content
3. **Abuse**: Rate limiting and content size limits
4. **Migration**: Comprehensive testing and rollback plan

## Success Metrics
- Zero private data leakage incidents
- < 50ms additional latency for visibility filtering
- 90% of queries use appropriate visibility scope
- Successful migration of 100% existing contexts

## Timeline Summary
- **Weeks 1-2**: Foundation & Schema
- **Weeks 2-3**: Storage Layer
- **Weeks 3-4**: API Updates
- **Weeks 4-5**: Security
- **Weeks 5-6**: Migration
- **Weeks 6-7**: Testing
- **Weeks 7-8**: Monitoring

Total Implementation Time: 8 weeks