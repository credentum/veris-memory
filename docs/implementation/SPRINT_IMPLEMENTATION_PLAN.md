# Veris-Memory Sprint Implementation Plan
## Cleanup and Interface Tightening

### Executive Summary
This document outlines a phased implementation approach for the Veris-Memory cleanup and interface tightening sprint. Based on analysis of the current codebase, the plan addresses architectural issues through 5 progressive phases that minimize risk while delivering incremental value.

### Current State Analysis

#### Problems Identified:
1. **Tight Coupling**: Direct client instances (`neo4j_client`, `qdrant_client`, `kv_store`) used globally
2. **Inconsistent Results**: Different backends return different data structures
   - Vector: `{id, content, score, source}`
   - Graph: Requires normalization from `{'n': {...}}` wrapper
3. **Hardcoded Ranking**: Simple sort operations in `retrieve_context` (lines 1330-1337)
4. **Poor Observability**: Basic logging without trace_id or per-backend timings
5. **Limited API Surface**: No OpenAPI spec, limited filtering capabilities

#### Current Architecture:
```
src/
├── mcp_server/
│   ├── main.py (1500+ lines, monolithic)
│   └── server.py (global client instances)
├── storage/
│   ├── qdrant_client.py (direct implementation)
│   ├── neo4j_client.py (direct implementation)
│   ├── kv_store.py (Redis wrapper)
│   ├── hybrid_scorer.py (scoring logic)
│   └── reranker.py (ranking logic)
└── core/
    └── config.py (configuration management)
```

---

## Phase 1: Foundation (Days 1-2)
**Goal**: Establish interfaces and infrastructure without breaking existing functionality

### Tasks:

#### 1.1 Define Backend Interface (vm-core-iface)
**File**: `src/interfaces/backend_interface.py`
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class SearchOptions(BaseModel):
    limit: int = 10
    filters: Dict[str, Any] = {}
    score_threshold: float = 0.0
    include_metadata: bool = True

class BackendSearchInterface(ABC):
    @abstractmethod
    async def search(
        self, 
        query: str, 
        options: SearchOptions
    ) -> List[Dict[str, Any]]:
        """Search backend and return normalized results"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check backend health status"""
        pass
```

#### 1.2 Define Normalized Result Schema (vm-schema-define)
**File**: `src/interfaces/memory_result.py`
```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class MemoryResult(BaseModel):
    id: str = Field(..., description="Unique identifier")
    text: str = Field(..., description="Primary content text")
    type: str = Field(default="general", description="Content type")
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(..., description="Backend source (vector/graph/kv)")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        schema_extra = {
            "example": {
                "id": "uuid-123",
                "text": "User's name is Matt",
                "type": "personal_info",
                "score": 0.95,
                "source": "vector",
                "tags": ["user_fact", "name"]
            }
        }
```

#### 1.3 Structured Logging Infrastructure (vm-log-struct)
**File**: `src/utils/logging_middleware.py`
```python
import json
import time
import uuid
from contextvars import ContextVar
from typing import Dict, Any

# Context variable for trace_id
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')

class StructuredLogger:
    def __init__(self, name: str):
        self.name = name
        
    def log(self, level: str, message: str, **kwargs):
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "trace_id": trace_id_var.get() or str(uuid.uuid4()),
            "logger": self.name,
            **kwargs
        }
        print(json.dumps(log_entry))
```

### Deliverables:
- [x] Backend interface definition
- [x] Normalized result schema
- [x] Structured logging setup
- [ ] Unit tests for schemas

---

## Phase 2: Backend Modularization (Days 2-4)
**Goal**: Extract backends behind common interface

### Tasks:

#### 2.1 Extract VectorBackend (vm-core-vector)
**File**: `src/backends/vector_backend.py`
```python
from ..interfaces.backend_interface import BackendSearchInterface, SearchOptions
from ..interfaces.memory_result import MemoryResult
from ..storage.qdrant_client import VectorDBInitializer

class VectorBackend(BackendSearchInterface):
    def __init__(self, client: VectorDBInitializer):
        self.client = client
        
    async def search(self, query: str, options: SearchOptions) -> List[MemoryResult]:
        # Generate embedding
        query_vector = await generate_embedding(query)
        
        # Search Qdrant
        results = self.client.search(
            query_vector=query_vector,
            limit=options.limit
        )
        
        # Convert to normalized format
        return [
            MemoryResult(
                id=r.id,
                text=r.payload.get("text", ""),
                score=r.score,
                source="vector",
                metadata=r.payload
            )
            for r in results
        ]
```

#### 2.2 Extract GraphBackend (vm-core-graph)
**File**: `src/backends/graph_backend.py`
```python
class GraphBackend(BackendSearchInterface):
    def __init__(self, client):
        self.client = client
        
    async def search(self, query: str, options: SearchOptions) -> List[MemoryResult]:
        cypher = """
        MATCH (n:Context)
        WHERE n.text CONTAINS $query
        RETURN n LIMIT $limit
        """
        
        results = self.client.query(cypher, {"query": query, "limit": options.limit})
        
        # Normalize graph results
        normalized = []
        for r in results:
            node = r.get('n', r)  # Handle wrapper
            normalized.append(MemoryResult(
                id=node.get("id"),
                text=node.get("text", ""),
                source="graph",
                metadata=node
            ))
        return normalized
```

#### 2.3 Implement QueryDispatcher (vm-core-router)
**File**: `src/core/query_dispatcher.py`
```python
from typing import List, Optional
from ..interfaces.memory_result import MemoryResult

class QueryDispatcher:
    def __init__(self):
        self.backends = {}
        
    def register_backend(self, name: str, backend: BackendSearchInterface):
        self.backends[name] = backend
        
    async def dispatch_query(
        self, 
        query: str,
        search_mode: str = "hybrid",
        options: Optional[SearchOptions] = None
    ) -> List[MemoryResult]:
        results = []
        
        if search_mode in ["vector", "hybrid"] and "vector" in self.backends:
            vector_results = await self.backends["vector"].search(query, options)
            results.extend(vector_results)
            
        if search_mode in ["graph", "hybrid"] and "graph" in self.backends:
            graph_results = await self.backends["graph"].search(query, options)
            results.extend(graph_results)
            
        return results
```

### Migration Strategy:
1. Keep existing global clients initially
2. Wrap them in backend adapters
3. Route through dispatcher
4. Gradually refactor calling code

---

## Phase 3: Ranking and Filtering (Days 4-5)
**Goal**: Implement flexible ranking system

### Tasks:

#### 3.1 Define RankingPolicy Interface (vm-policy-api)
**File**: `src/ranking/policy_engine.py`
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..interfaces.memory_result import MemoryResult

class RankingPolicy(ABC):
    @abstractmethod
    def rank(
        self,
        results: List[MemoryResult],
        context: Dict[str, Any]
    ) -> List[MemoryResult]:
        """Apply ranking policy to results"""
        pass

class DefaultRankingPolicy(RankingPolicy):
    def rank(self, results: List[MemoryResult], context: Dict[str, Any]) -> List[MemoryResult]:
        # Current behavior: sort by score
        return sorted(results, key=lambda x: x.score, reverse=True)

class CodeBoostPolicy(RankingPolicy):
    def rank(self, results: List[MemoryResult], context: Dict[str, Any]) -> List[MemoryResult]:
        # Boost code results
        for r in results:
            if r.type == "code":
                r.score *= 2.0
        return sorted(results, key=lambda x: x.score, reverse=True)
```

#### 3.2 Pre-filter Implementation (vm-pre_filter_hooks)
**File**: `src/filters/pre_filter.py`
```python
from typing import List, Optional
from datetime import datetime, timedelta

class PreFilterEngine:
    @staticmethod
    def apply_tag_filter(results: List[MemoryResult], tags: List[str]) -> List[MemoryResult]:
        if not tags:
            return results
        return [r for r in results if any(tag in r.tags for tag in tags)]
    
    @staticmethod
    def apply_time_window(
        results: List[MemoryResult], 
        window_hours: int
    ) -> List[MemoryResult]:
        cutoff = datetime.now() - timedelta(hours=window_hours)
        return [r for r in results if r.timestamp >= cutoff]
```

---

## Phase 4: API Hardening (Days 5-6)
**Goal**: Stabilize API surface

### Tasks:

#### 4.1 OpenAPI Contract (vm-api-contract)
**File**: `src/api/openapi.yaml`
```yaml
openapi: 3.0.0
info:
  title: Veris Memory API
  version: 1.0.0
paths:
  /tools/retrieve_context:
    post:
      summary: Retrieve context with hybrid search
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RetrieveContextRequest'
      responses:
        200:
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RetrieveContextResponse'
```

#### 4.2 Enhanced Logging (vm-log-timings)
**File**: `src/utils/timing_logger.py`
```python
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def log_backend_timing(backend_name: str, logger):
    start = time.time()
    try:
        yield
    finally:
        duration = (time.time() - start) * 1000
        logger.log("info", f"Backend timing", 
                  backend=backend_name,
                  duration_ms=duration)
```

---

## Phase 5: Testing and Tools (Days 6-7)
**Goal**: Comprehensive testing and developer tools

### Tasks:

#### 5.1 CLI Query Simulator (vm-test-query-simulator)
**File**: `tools/query_simulator.py`
```python
#!/usr/bin/env python3
import click
import asyncio
from src.core.query_dispatcher import QueryDispatcher

@click.command()
@click.option('--query', required=True, help='Search query')
@click.option('--policy', default='default', help='Ranking policy')
@click.option('--limit', default=10, help='Result limit')
def simulate(query, policy, limit):
    """Simulate query with different policies"""
    dispatcher = QueryDispatcher()
    # ... implementation
```

#### 5.2 Developer Documentation (vm-docs-dev-usage)
**File**: `docs/USAGE_SMART_CONTEXT.md`
```markdown
# Smart Context Integration Guide

## Quick Start
```python
from veris_memory import MemoryClient

client = MemoryClient(base_url="http://localhost:8000")
results = await client.search("user preferences", filters={"type": "preference"})
```

## Filtering Examples
...
```

---

## Implementation Timeline

### Week Overview:
```
Day 1-2: Foundation (Interfaces, Schemas, Logging)
Day 2-4: Backend Modularization (Adapters, Dispatcher)
Day 4-5: Ranking System (Policies, Filters)
Day 5-6: API Hardening (OpenAPI, Error Handling)
Day 6-7: Testing & Documentation
```

### Critical Path:
1. Backend Interface → Backend Adapters → Dispatcher
2. Result Schema → Ranking Policy → API Response
3. Structured Logging → Timing Logs → Observability

### Risk Mitigation:
- **Schema Drift**: Use Pydantic for validation
- **Performance Regression**: Add timing logs early
- **Breaking Changes**: Keep backward compatibility layer

---

## Success Metrics

### Technical Metrics:
- [ ] 100% unit test coverage on new modules
- [ ] All backends return normalized schema
- [ ] Structured logs with trace_id implemented
- [ ] OpenAPI spec validates against implementation
- [ ] Query simulator reproduces production scenarios

### Business Metrics:
- [ ] Smart Context integration successful
- [ ] Response time < 100ms for typical queries
- [ ] Zero breaking changes for existing clients
- [ ] Documentation reviewed and approved

---

## Next Steps

1. **Immediate Actions**:
   - Create feature branch: `feature/vm-cleanup-sprint`
   - Set up test infrastructure
   - Begin Phase 1 implementation

2. **Dependencies**:
   - Coordinate with Smart Context team on API requirements
   - Review with DevOps on logging infrastructure
   - Align with Product on ranking priorities

3. **Follow-up Sprint**:
   - Smart Context Microservice implementation
   - Advanced caching layer
   - Performance optimization