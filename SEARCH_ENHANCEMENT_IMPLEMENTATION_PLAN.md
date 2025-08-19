# Search Enhancement Implementation Plan

## Current State Analysis

Based on workspace 001's findings and code review:

1. **Current Implementation**:
   - Search results are sorted by either timestamp or relevance
   - No exact match boosting for filenames or keywords
   - No context type weighting in scoring
   - Recent content dominates search results
   - Technical searches return conversational contexts

2. **Key Issues**:
   - Semantic dominance over exact matches
   - Recent content bias (newer content overshadows older)
   - Content type mixing (technical queries return logs instead of code)
   - Workspace 001's own plan couldn't be found after storage

## Implementation Strategy

### Phase 1: Immediate Fixes (HIGH PRIORITY)

#### 1.1 Exact Match Boosting
**Location**: `src/mcp_server/server.py` in `retrieve_context_tool` function
**Implementation**:
```python
# Add exact match detection before hybrid scoring
def calculate_exact_match_boost(query, content, metadata):
    boost = 1.0
    query_lower = query.lower()
    
    # Check for exact filename match
    if 'file_path' in metadata:
        filename = os.path.basename(metadata['file_path']).lower()
        if filename in query_lower or query_lower in filename:
            boost *= 3.0  # 3x boost for filename match
    
    # Check for exact keyword matches
    keywords = query_lower.split()
    content_lower = str(content).lower()
    for keyword in keywords:
        if keyword in content_lower:
            boost *= 1.2  # 20% boost per keyword match
    
    return boost
```

#### 1.2 Context Type Filtering and Weighting
**Location**: `src/mcp_server/server.py` in `retrieve_context_tool` function
**Implementation**:
```python
# Context type weights for technical searches
CONTEXT_TYPE_WEIGHTS = {
    'log': 1.5,           # Code and technical logs
    'code': 2.0,          # Actual code files
    'documentation': 1.3,  # Technical documentation
    'infrastructure_improvement': 1.0,
    'accomplishment': 0.8,
    'conversation': 0.5   # Lower weight for conversations
}

def apply_context_type_weight(result, context_type):
    type_value = result.get('payload', {}).get('type', 'unknown')
    category = result.get('payload', {}).get('category', 'unknown')
    
    # Determine effective type
    if category == 'code' or category == 'python_code':
        effective_type = 'code'
    elif category == 'documentation':
        effective_type = 'documentation'
    else:
        effective_type = type_value
    
    weight = CONTEXT_TYPE_WEIGHTS.get(effective_type, 1.0)
    return weight
```

### Phase 2: Algorithm Improvements

#### 2.1 Recency Balancing
**Implementation**:
```python
import math
from datetime import datetime, timedelta

def calculate_recency_decay(created_at, base_score):
    """Apply exponential decay based on age"""
    if not created_at:
        return base_score
    
    try:
        # Parse timestamp
        if isinstance(created_at, str):
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created_dt = created_at
        
        # Calculate age in days
        age_days = (datetime.now() - created_dt).days
        
        # Apply exponential decay: score * exp(-age_days / 7)
        # This gives 50% weight after 1 week, 25% after 2 weeks
        decay_factor = math.exp(-age_days / 7)
        
        # Don't let decay go below 0.1 (10% minimum)
        decay_factor = max(decay_factor, 0.1)
        
        return base_score * decay_factor
    except:
        return base_score
```

#### 2.2 Technical Term Recognition
**Implementation**:
```python
# Technical vocabulary for boosting
TECHNICAL_TERMS = {
    'python', 'javascript', 'typescript', 'function', 'class', 'method',
    'api', 'endpoint', 'database', 'query', 'schema', 'model',
    'docker', 'kubernetes', 'deployment', 'server', 'client',
    'vector', 'embedding', 'graph', 'neo4j', 'qdrant', 'redis',
    'mcp', 'context', 'storage', 'retrieval', 'search'
}

def calculate_technical_boost(query, content):
    """Boost results containing technical terms"""
    boost = 1.0
    query_terms = set(query.lower().split())
    content_lower = str(content).lower()
    
    # Check for technical terms in query
    technical_query = bool(query_terms & TECHNICAL_TERMS)
    
    if technical_query:
        # Count technical terms in content
        tech_count = sum(1 for term in TECHNICAL_TERMS if term in content_lower)
        if tech_count > 0:
            # Logarithmic boost to avoid over-weighting
            boost *= (1 + math.log(1 + tech_count) * 0.3)
    
    return boost
```

### Phase 3: Advanced Features

#### 3.1 Multi-Modal Search
- Separate search paths for code vs conversational content
- Different scoring algorithms based on intent

#### 3.2 Search Result Clustering
- Group results by type (code, conversations, documentation)
- Present grouped results for better organization

## Testing Strategy

### Test Cases from Workspace 001:
1. Search "server.py MCP Python SDK" should return actual server.py file
2. Search "hybrid memory vector embeddings" should find README.md
3. Search for exact filenames should prioritize those files
4. Technical searches should return code/documentation, not conversations

### Performance Metrics:
- Measure search latency with new scoring
- Track relevance improvements
- Monitor exact match success rate

## Implementation Order:

1. **First PR**: Phase 1 fixes (exact match + context type)
   - Most critical for immediate improvement
   - Relatively simple to implement
   - Can be tested quickly

2. **Second PR**: Phase 2 improvements (recency + technical terms)
   - More complex scoring changes
   - Requires careful testing
   - Builds on Phase 1

3. **Third PR**: Phase 3 advanced features
   - Major architectural changes
   - Requires extensive testing
   - Optional based on Phase 1&2 success

## Files to Modify:

1. `src/mcp_server/server.py` - Main search implementation
2. `src/mcp_server/search_enhancements.py` - New file for enhancement functions
3. `tests/mcp_server/test_search_enhancements.py` - Comprehensive test suite
4. `docs/SEARCH_IMPROVEMENTS.md` - Documentation of changes

## Success Criteria:

1. Exact filename searches return the file as top result
2. Technical queries prioritize code/documentation over conversations  
3. Recent content doesn't completely overshadow older relevant content
4. Workspace 001's test cases all pass
5. No performance regression (search latency < 200ms)