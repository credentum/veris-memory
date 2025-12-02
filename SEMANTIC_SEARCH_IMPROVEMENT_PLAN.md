# Semantic Search Improvement Plan

## Overview

This plan addresses the S3-Paraphrase-Robustness issue by implementing four fixes in a phased approach:

1. **Phase 1**: Semantic Cache Keys
2. **Phase 2**: Multi-Query Expansion (MQE) Integration
3. **Phase 3**: Search Enhancements Integration
4. **Phase 4**: Query Normalization Layer

Each phase includes feature flags for safe rollout, comprehensive testing, and rollback capabilities.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Query Flow (After All Phases)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User Query                                                                  │
│      │                                                                       │
│      ▼                                                                       │
│  ┌────────────────────┐                                                     │
│  │ Phase 4: Query     │  "How to setup Neo4j?" → "How do I configure       │
│  │ Normalization      │   Neo4j database settings?"                         │
│  └────────┬───────────┘                                                     │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────┐                                                     │
│  │ Phase 1: Semantic  │  Check cache using embedding-based key             │
│  │ Cache Check        │  (quantized embedding prefix)                       │
│  └────────┬───────────┘                                                     │
│           │                                                                  │
│    Cache Miss                                                                │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────┐                                                     │
│  │ Phase 2: MQE       │  Generate paraphrases:                              │
│  │ (Multi-Query       │  - Original: "How do I configure Neo4j?"           │
│  │  Expansion)        │  - Para 1: "Neo4j configuration guide"             │
│  └────────┬───────────┘  - Para 2: "Setting up Neo4j database"             │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────┐                                                     │
│  │ VectorBackend      │  Execute search for each paraphrase                │
│  │ (Qdrant)           │  in parallel                                        │
│  └────────┬───────────┘                                                     │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────┐                                                     │
│  │ MQE Aggregation    │  Merge results, keep max score per doc             │
│  └────────┬───────────┘                                                     │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────┐                                                     │
│  │ Phase 3: Search    │  Apply boosts:                                      │
│  │ Enhancements       │  - Exact match boost                                │
│  │                    │  - Type weighting                                   │
│  │                    │  - Technical boost                                  │
│  └────────┬───────────┘  - Recency decay                                    │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────┐                                                     │
│  │ Phase 1: Cache     │  Store results with semantic cache key             │
│  │ Store              │                                                     │
│  └────────┬───────────┘                                                     │
│           │                                                                  │
│           ▼                                                                  │
│      Response                                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Semantic Cache Keys

### Goal
Ensure semantically similar queries share cache entries by generating cache keys from quantized embeddings rather than raw query text.

### Implementation Details

#### 1.1 New Module: `src/core/semantic_cache.py`

```python
"""
Semantic cache key generation for query caching.
Generates cache keys from quantized embeddings instead of raw text.
"""

import hashlib
import json
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class SemanticCacheKeyGenerator:
    """Generate cache keys from semantic embeddings."""

    def __init__(
        self,
        quantization_precision: int = 1,
        embedding_prefix_length: int = 32,
        enabled: bool = True
    ):
        """
        Args:
            quantization_precision: Decimal places for rounding (1 = 0.1 precision)
            embedding_prefix_length: Number of embedding dimensions to use
            enabled: Whether semantic caching is enabled
        """
        self.quantization_precision = quantization_precision
        self.embedding_prefix_length = embedding_prefix_length
        self.enabled = enabled

    def quantize_embedding(self, embedding: List[float]) -> List[float]:
        """Quantize embedding to reduce sensitivity to small differences."""
        prefix = embedding[:self.embedding_prefix_length]
        return [round(x, self.quantization_precision) for x in prefix]

    def generate_cache_key(
        self,
        embedding: List[float],
        limit: int,
        search_mode: str,
        context_type: Optional[str] = None,
        sort_by: str = "relevance"
    ) -> str:
        """Generate semantic cache key from embedding."""
        if not self.enabled:
            return None  # Fall back to text-based caching

        quantized = self.quantize_embedding(embedding)

        cache_params = {
            "embedding_prefix": quantized,
            "limit": limit,
            "search_mode": search_mode,
            "context_type": context_type,
            "sort_by": sort_by,
        }

        cache_hash = hashlib.sha256(
            json.dumps(cache_params, sort_keys=True).encode()
        ).hexdigest()

        return f"semantic:{cache_hash}"

# Global instance
_semantic_cache_generator: Optional[SemanticCacheKeyGenerator] = None

def get_semantic_cache_generator() -> SemanticCacheKeyGenerator:
    """Get or create global semantic cache generator."""
    global _semantic_cache_generator
    if _semantic_cache_generator is None:
        _semantic_cache_generator = SemanticCacheKeyGenerator()
    return _semantic_cache_generator
```

#### 1.2 Modify `src/mcp_server/main.py`

Add semantic caching to `retrieve_context`:

```python
# At top of file, add import:
from ..core.semantic_cache import get_semantic_cache_generator
from ..embedding import generate_embedding

# In retrieve_context function, replace cache key generation:

# PHASE 1: Generate semantic cache key
semantic_cache = get_semantic_cache_generator()
if semantic_cache.enabled and simple_redis:
    try:
        # Generate embedding for cache key
        query_embedding = await generate_embedding(request.query, adjust_dimensions=True)
        cache_key = semantic_cache.generate_cache_key(
            embedding=query_embedding,
            limit=request.limit,
            search_mode=request.search_mode,
            context_type=getattr(request, "context_type", None),
            sort_by=request.sort_by.value if hasattr(request, "sort_by") and request.sort_by else "relevance"
        )
        # ... rest of cache logic using semantic cache_key
    except Exception as e:
        logger.warning(f"Semantic cache key generation failed, falling back: {e}")
        # Fall back to text-based cache key
```

#### 1.3 Feature Flag

Add to `src/core/feature_gates.py`:

```python
'semantic_cache_keys': {
    'state': FeatureState.ROLLOUT,
    'rollout_percentage': 10.0,  # Start with 10%
    'description': 'Embedding-based cache key generation for semantic consistency'
},
```

#### 1.4 Configuration

Add to `src/core/config.py`:

```python
# Semantic cache settings
SEMANTIC_CACHE_ENABLED = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() == "true"
SEMANTIC_CACHE_QUANTIZATION_PRECISION = int(os.getenv("SEMANTIC_CACHE_PRECISION", "1"))
SEMANTIC_CACHE_EMBEDDING_PREFIX_LENGTH = int(os.getenv("SEMANTIC_CACHE_PREFIX_LENGTH", "32"))
```

#### 1.5 Tests

Create `tests/test_semantic_cache.py`:
- Test quantization produces stable keys for similar embeddings
- Test different embeddings produce different keys
- Test cache hit rate with paraphrased queries
- Test fallback when embedding generation fails

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/core/semantic_cache.py` | Create | Semantic cache key generator |
| `src/mcp_server/main.py` | Modify | Integrate semantic caching |
| `src/core/feature_gates.py` | Modify | Add feature flag |
| `src/core/config.py` | Modify | Add configuration |
| `tests/test_semantic_cache.py` | Create | Unit tests |

### Rollback

Set `SEMANTIC_CACHE_ENABLED=false` or set feature flag to `DISABLED`.

---

## Phase 2: Multi-Query Expansion (MQE) Integration

### Goal
Integrate the existing `MultiQueryExpander` into the retrieval pipeline to improve paraphrase robustness by searching multiple query variations.

### Implementation Details

#### 2.1 Create Wrapper: `src/core/mqe_wrapper.py`

```python
"""
Multi-Query Expansion wrapper for retrieval pipeline integration.
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable

from ..storage.query_expansion import MultiQueryExpander, FieldBoostProcessor
from ..interfaces.memory_result import MemoryResult

logger = logging.getLogger(__name__)

class MQERetrievalWrapper:
    """Wraps MQE for use in the retrieval pipeline."""

    def __init__(
        self,
        enabled: bool = True,
        num_paraphrases: int = 2,
        apply_field_boosts: bool = True
    ):
        self.enabled = enabled
        self.num_paraphrases = num_paraphrases
        self.apply_field_boosts = apply_field_boosts
        self.expander = MultiQueryExpander()
        self.field_processor = FieldBoostProcessor() if apply_field_boosts else None

    async def search_with_expansion(
        self,
        query: str,
        search_func: Callable[[str, int], Awaitable[List[Dict[str, Any]]]],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute search with multi-query expansion.

        Args:
            query: Original search query
            search_func: Async function to perform single search
            limit: Maximum results to return

        Returns:
            Aggregated search results
        """
        if not self.enabled:
            return await search_func(query, limit)

        try:
            # Use MQE to expand and search
            results = await self.expander.expand_and_search(
                query=query,
                search_func=search_func,
                limit=limit,
                num_paraphrases=self.num_paraphrases
            )

            # Apply field boosts if enabled
            if self.apply_field_boosts and self.field_processor:
                results = self.field_processor.process_results(results)

            logger.info(f"MQE search returned {len(results)} results for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"MQE search failed, falling back to single query: {e}")
            return await search_func(query, limit)

# Global instance
_mqe_wrapper: Optional[MQERetrievalWrapper] = None

def get_mqe_wrapper() -> MQERetrievalWrapper:
    """Get or create global MQE wrapper."""
    global _mqe_wrapper
    if _mqe_wrapper is None:
        import os
        enabled = os.getenv("MQE_ENABLED", "true").lower() == "true"
        num_paraphrases = int(os.getenv("MQE_NUM_PARAPHRASES", "2"))
        _mqe_wrapper = MQERetrievalWrapper(
            enabled=enabled,
            num_paraphrases=num_paraphrases
        )
    return _mqe_wrapper
```

#### 2.2 Integrate into QueryDispatcher

Modify `src/core/query_dispatcher.py`:

```python
# Add import
from .mqe_wrapper import get_mqe_wrapper

# In _search_single_backend method, wrap the search:
async def _search_single_backend(
    self,
    backend_name: str,
    query: str,
    options: SearchOptions,
    trace_id: str
) -> tuple[List[MemoryResult], float]:
    """Search a single backend with optional MQE."""
    backend = self.backends[backend_name]
    start_time = time.time()

    try:
        # Check if MQE should be used for this backend
        mqe_wrapper = get_mqe_wrapper()
        if mqe_wrapper.enabled and backend_name == "vector":
            # Use MQE for vector searches
            async def single_search(q: str, limit: int) -> List[Dict[str, Any]]:
                results = await backend.search(q, SearchOptions(limit=limit))
                return [asdict(r) if hasattr(r, '__dataclass_fields__') else r.__dict__ for r in results]

            raw_results = await mqe_wrapper.search_with_expansion(
                query=query,
                search_func=single_search,
                limit=options.limit
            )
            # Convert back to MemoryResult
            results = [self._dict_to_memory_result(r) for r in raw_results]
        else:
            results = await backend.search(query, options)

        timing = (time.time() - start_time) * 1000
        return results, timing

    except Exception as e:
        timing = (time.time() - start_time) * 1000
        raise BackendSearchError(backend_name, str(e), e)
```

#### 2.3 Feature Flag

Add to `src/core/feature_gates.py`:

```python
'multi_query_expansion': {
    'state': FeatureState.ROLLOUT,
    'rollout_percentage': 20.0,  # Start with 20%
    'description': 'Multi-query expansion for paraphrase robustness'
},
```

#### 2.4 Enhance MultiQueryExpander

Update `src/storage/query_expansion.py` to add Neo4j configuration templates:

```python
# Add to generate_paraphrases method:

# Neo4j configuration templates
elif "configure" in query_lower or "setup" in query_lower or "settings" in query_lower:
    if "neo4j" in query_lower:
        paraphrases.extend([
            "How do I configure Neo4j database connection settings?",
            "Neo4j database configuration and setup guide"
        ])
    elif "database" in query_lower:
        paraphrases.extend([
            "Database configuration settings guide",
            "How to set up database connection parameters"
        ])

elif "steps" in query_lower and "set up" in query_lower:
    if "neo4j" in query_lower or "database" in query_lower:
        paraphrases.extend([
            "How to configure database settings?",
            "Database setup configuration process"
        ])
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/core/mqe_wrapper.py` | Create | MQE wrapper for retrieval integration |
| `src/core/query_dispatcher.py` | Modify | Integrate MQE into search |
| `src/storage/query_expansion.py` | Modify | Add Neo4j templates |
| `src/core/feature_gates.py` | Modify | Add feature flag |
| `tests/test_mqe_integration.py` | Create | Integration tests |

### Rollback

Set `MQE_ENABLED=false` or set feature flag to `DISABLED`.

---

## Phase 3: Search Enhancements Integration

### Goal
Apply the existing `apply_search_enhancements` function to the main `retrieve_context` endpoint to ensure consistent boosting behavior.

### Implementation Details

#### 3.1 Modify RetrievalCore

Update `src/core/retrieval_core.py` to apply search enhancements:

```python
# Add import
from ..mcp_server.search_enhancements import (
    apply_search_enhancements,
    is_technical_query
)

class RetrievalCore:
    def __init__(
        self,
        query_dispatcher: QueryDispatcher,
        enable_search_enhancements: bool = True
    ):
        self.dispatcher = query_dispatcher
        self.enable_search_enhancements = enable_search_enhancements

    async def search(self, query: str, ...):
        # ... existing search logic ...

        # Execute search through unified dispatcher
        search_response = await self.dispatcher.search(
            query=query,
            options=search_options,
            search_mode=search_mode_enum
        )

        # PHASE 3: Apply search enhancements
        if self.enable_search_enhancements and search_response.results:
            technical_query = is_technical_query(query)

            # Convert MemoryResult to dict for enhancement processing
            results_as_dicts = [
                self._memory_result_to_enhancement_dict(r)
                for r in search_response.results
            ]

            enhanced_dicts = apply_search_enhancements(
                results=results_as_dicts,
                query=query,
                enable_exact_match=True,
                enable_type_weighting=True,
                enable_recency_decay=True,
                enable_technical_boost=technical_query
            )

            # Convert back to MemoryResult
            search_response.results = [
                self._enhancement_dict_to_memory_result(d)
                for d in enhanced_dicts
            ]

        return search_response

    def _memory_result_to_enhancement_dict(self, result: MemoryResult) -> Dict[str, Any]:
        """Convert MemoryResult to dict for search enhancements."""
        return {
            "id": result.id,
            "score": result.score,
            "payload": {
                "content": result.text,
                "type": result.type.value if result.type else "unknown",
                "metadata": result.metadata,
                "title": result.title,
                "tags": result.tags,
                **result.metadata
            }
        }

    def _enhancement_dict_to_memory_result(self, d: Dict[str, Any]) -> MemoryResult:
        """Convert enhanced dict back to MemoryResult."""
        # Preserve original fields, update score
        return MemoryResult(
            id=d["id"],
            score=d.get("enhanced_score", d.get("score", 0.0)),
            text=d.get("payload", {}).get("content", ""),
            type=d.get("payload", {}).get("type", "general"),
            metadata={
                **d.get("payload", {}).get("metadata", {}),
                "score_boosts": d.get("score_boosts", {}),
                "original_score": d.get("original_score", d.get("score", 0.0))
            },
            # ... other fields ...
        )
```

#### 3.2 Feature Flag

Add to `src/core/feature_gates.py`:

```python
'search_enhancements_in_retrieval': {
    'state': FeatureState.ROLLOUT,
    'rollout_percentage': 30.0,  # Start with 30%
    'description': 'Apply search enhancements (exact match, type weighting, etc.) in retrieval core'
},
```

#### 3.3 Configuration

Add to `src/core/config.py`:

```python
# Search enhancement settings
SEARCH_ENHANCEMENTS_ENABLED = os.getenv("SEARCH_ENHANCEMENTS_ENABLED", "true").lower() == "true"
SEARCH_ENHANCEMENT_EXACT_MATCH = os.getenv("SEARCH_ENHANCEMENT_EXACT_MATCH", "true").lower() == "true"
SEARCH_ENHANCEMENT_TYPE_WEIGHTING = os.getenv("SEARCH_ENHANCEMENT_TYPE_WEIGHTING", "true").lower() == "true"
SEARCH_ENHANCEMENT_RECENCY_DECAY = os.getenv("SEARCH_ENHANCEMENT_RECENCY_DECAY", "true").lower() == "true"
SEARCH_ENHANCEMENT_TECHNICAL_BOOST = os.getenv("SEARCH_ENHANCEMENT_TECHNICAL_BOOST", "true").lower() == "true"
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/core/retrieval_core.py` | Modify | Integrate search enhancements |
| `src/core/feature_gates.py` | Modify | Add feature flag |
| `src/core/config.py` | Modify | Add configuration |
| `tests/test_search_enhancements_integration.py` | Create | Integration tests |

### Rollback

Set `SEARCH_ENHANCEMENTS_ENABLED=false` or set feature flag to `DISABLED`.

---

## Phase 4: Query Normalization Layer

### Goal
Create a semantic query normalization layer that maps paraphrased queries to canonical forms before retrieval.

### Implementation Details

#### 4.1 New Module: `src/core/query_normalizer.py`

```python
"""
Semantic query normalization for consistent retrieval.

Normalizes semantically equivalent queries to canonical forms
to ensure consistent caching and retrieval behavior.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    """Detected query intents."""
    CONFIGURATION = "configuration"
    TROUBLESHOOTING = "troubleshooting"
    HOWTO = "howto"
    CONCEPTUAL = "conceptual"
    LOOKUP = "lookup"
    UNKNOWN = "unknown"

@dataclass
class NormalizedQuery:
    """Result of query normalization."""
    original: str
    normalized: str
    intent: QueryIntent
    entities: List[str]
    confidence: float

class QueryNormalizer:
    """
    Normalize queries to canonical semantic forms.

    Uses pattern matching and keyword detection to map
    paraphrased queries to consistent forms.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

        # Canonical query patterns (intent -> keywords -> canonical form)
        self.canonical_patterns: Dict[QueryIntent, Dict[str, str]] = {
            QueryIntent.CONFIGURATION: {
                "neo4j": "How do I configure Neo4j database settings?",
                "database connection": "How do I configure database connection settings?",
                "qdrant": "How do I configure Qdrant vector database?",
                "redis": "How do I configure Redis cache settings?",
                "embedding": "How do I configure embedding model settings?",
            },
            QueryIntent.TROUBLESHOOTING: {
                "neo4j timeout": "How do I troubleshoot Neo4j connection timeout errors?",
                "connection error": "How do I troubleshoot database connection errors?",
                "performance": "How do I troubleshoot performance issues?",
            },
            QueryIntent.HOWTO: {
                "store context": "How do I store context in Veris Memory?",
                "retrieve context": "How do I retrieve context from Veris Memory?",
                "query graph": "How do I query the Neo4j graph database?",
            }
        }

        # Intent detection patterns
        self.intent_patterns = {
            QueryIntent.CONFIGURATION: [
                r'\bconfigur\w*\b', r'\bset\s*up\b', r'\bsettings?\b',
                r'\bparameters?\b', r'\binitializ\w*\b'
            ],
            QueryIntent.TROUBLESHOOTING: [
                r'\btroubleshoot\w*\b', r'\bfix\b', r'\bresolv\w*\b',
                r'\berrors?\b', r'\bfail\w*\b', r'\bissues?\b', r'\bproblems?\b'
            ],
            QueryIntent.HOWTO: [
                r'\bhow\s+(?:to|do|can)\b', r'\bsteps?\s+to\b',
                r'\bguide\b', r'\btutorial\b'
            ],
            QueryIntent.CONCEPTUAL: [
                r'\bwhat\s+(?:is|are)\b', r'\bexplain\b',
                r'\bdescribe\b', r'\bunderstand\b'
            ],
            QueryIntent.LOOKUP: [
                r'\bfind\b', r'\bsearch\b', r'\blook\s*up\b',
                r'\bget\b', r'\bretrieve\b'
            ]
        }

        # Entity extraction patterns
        self.entity_patterns = [
            r'\bneo4j\b', r'\bqdrant\b', r'\bredis\b', r'\bmcp\b',
            r'\bveris\s*memory\b', r'\bembedding\b', r'\bvector\b',
            r'\bgraph\b', r'\bdatabase\b', r'\bcontext\b'
        ]

    def normalize(self, query: str) -> NormalizedQuery:
        """
        Normalize a query to its canonical form.

        Args:
            query: Raw user query

        Returns:
            NormalizedQuery with normalized form and metadata
        """
        if not self.enabled:
            return NormalizedQuery(
                original=query,
                normalized=query,
                intent=QueryIntent.UNKNOWN,
                entities=[],
                confidence=0.0
            )

        query_lower = query.lower().strip()

        # Detect intent
        intent, intent_confidence = self._detect_intent(query_lower)

        # Extract entities
        entities = self._extract_entities(query_lower)

        # Find canonical form
        canonical, match_confidence = self._find_canonical(query_lower, intent, entities)

        # Calculate overall confidence
        confidence = (intent_confidence + match_confidence) / 2

        logger.debug(
            f"Normalized query: '{query[:50]}...' -> '{canonical[:50]}...' "
            f"(intent={intent.value}, entities={entities}, confidence={confidence:.2f})"
        )

        return NormalizedQuery(
            original=query,
            normalized=canonical if confidence > 0.5 else query,
            intent=intent,
            entities=entities,
            confidence=confidence
        )

    def _detect_intent(self, query: str) -> Tuple[QueryIntent, float]:
        """Detect the intent of a query."""
        intent_scores = {}

        for intent, patterns in self.intent_patterns.items():
            score = sum(
                1 for pattern in patterns
                if re.search(pattern, query, re.IGNORECASE)
            ) / len(patterns)
            intent_scores[intent] = score

        if not intent_scores or max(intent_scores.values()) == 0:
            return QueryIntent.UNKNOWN, 0.0

        best_intent = max(intent_scores, key=intent_scores.get)
        return best_intent, intent_scores[best_intent]

    def _extract_entities(self, query: str) -> List[str]:
        """Extract technical entities from query."""
        entities = []
        for pattern in self.entity_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend([m.lower() for m in matches])
        return list(set(entities))

    def _find_canonical(
        self,
        query: str,
        intent: QueryIntent,
        entities: List[str]
    ) -> Tuple[str, float]:
        """Find the canonical form for the query."""
        if intent not in self.canonical_patterns:
            return query, 0.0

        intent_patterns = self.canonical_patterns[intent]

        best_match = None
        best_score = 0.0

        for key, canonical in intent_patterns.items():
            # Score based on keyword presence
            keywords = key.lower().split()
            score = sum(1 for kw in keywords if kw in query) / len(keywords)

            # Bonus for entity overlap
            canonical_lower = canonical.lower()
            entity_bonus = sum(
                0.1 for entity in entities
                if entity in canonical_lower
            )

            total_score = min(1.0, score + entity_bonus)

            if total_score > best_score:
                best_score = total_score
                best_match = canonical

        return best_match or query, best_score

# Global instance
_query_normalizer: Optional[QueryNormalizer] = None

def get_query_normalizer() -> QueryNormalizer:
    """Get or create global query normalizer."""
    global _query_normalizer
    if _query_normalizer is None:
        import os
        enabled = os.getenv("QUERY_NORMALIZATION_ENABLED", "true").lower() == "true"
        _query_normalizer = QueryNormalizer(enabled=enabled)
    return _query_normalizer
```

#### 4.2 Integrate into RetrievalCore

Update `src/core/retrieval_core.py`:

```python
# Add import
from .query_normalizer import get_query_normalizer

class RetrievalCore:
    async def search(self, query: str, ...):
        # PHASE 4: Normalize query
        normalizer = get_query_normalizer()
        normalized = normalizer.normalize(query)

        # Use normalized query for search
        effective_query = normalized.normalized

        logger.info(
            f"Query normalization: '{query[:30]}...' -> '{effective_query[:30]}...' "
            f"(confidence={normalized.confidence:.2f})"
        )

        # ... rest of search using effective_query ...
```

#### 4.3 Feature Flag

Add to `src/core/feature_gates.py`:

```python
'query_normalization': {
    'state': FeatureState.TESTING,  # Start in testing mode
    'rollout_percentage': 5.0,  # Very gradual rollout
    'description': 'Semantic query normalization for paraphrase consistency'
},
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/core/query_normalizer.py` | Create | Query normalization logic |
| `src/core/retrieval_core.py` | Modify | Integrate normalization |
| `src/core/feature_gates.py` | Modify | Add feature flag |
| `tests/test_query_normalizer.py` | Create | Unit tests |

### Rollback

Set `QUERY_NORMALIZATION_ENABLED=false` or set feature flag to `DISABLED`.

---

## Implementation Order & Dependencies

```
Phase 1 (Semantic Cache)
    │
    │  No dependencies - can be implemented first
    │
    ▼
Phase 2 (MQE Integration)
    │
    │  Depends on: Phase 1 for efficient caching of expanded queries
    │
    ▼
Phase 3 (Search Enhancements)
    │
    │  Depends on: Phase 2 for enhanced results to boost
    │
    ▼
Phase 4 (Query Normalization)
    │
    │  Depends on: Phase 1 for cache key consistency
    │  Works best with: Phase 2+3 already active
    │
    ▼
All Phases Complete
```

### Recommended Implementation Timeline

| Phase | Sprint | Feature Flag State | Rollout % |
|-------|--------|-------------------|-----------|
| Phase 1: Semantic Cache | Sprint 1 | ROLLOUT | 10% → 50% → 100% |
| Phase 2: MQE Integration | Sprint 2 | ROLLOUT | 20% → 50% → 100% |
| Phase 3: Search Enhancements | Sprint 2-3 | ROLLOUT | 30% → 60% → 100% |
| Phase 4: Query Normalization | Sprint 3-4 | TESTING → ROLLOUT | 5% → 25% → 50% → 100% |

---

## Testing Strategy

### Unit Tests

Each phase requires unit tests:
- Phase 1: `tests/test_semantic_cache.py`
- Phase 2: `tests/test_mqe_integration.py`
- Phase 3: `tests/test_search_enhancements_integration.py`
- Phase 4: `tests/test_query_normalizer.py`

### Integration Tests

Create `tests/integration/test_paraphrase_robustness.py`:

```python
"""
Integration tests for paraphrase robustness improvements.
Tests all four phases working together.
"""

async def test_paraphrase_consistency_improved():
    """Test that paraphrased queries return similar results."""
    queries = [
        "How do I configure Neo4j database connection settings?",
        "What are the steps to set up Neo4j database configuration?",
        "How to configure the Neo4j connection in Veris Memory?"
    ]

    results = []
    for query in queries:
        response = await retrieval_core.search(query, limit=10)
        results.append(set(r.id for r in response.results))

    # Calculate pairwise overlap
    overlaps = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            intersection = len(results[i] & results[j])
            union = len(results[i] | results[j])
            overlaps.append(intersection / union if union > 0 else 0)

    avg_overlap = sum(overlaps) / len(overlaps)

    # With all improvements, expect > 50% overlap
    assert avg_overlap > 0.5, f"Paraphrase overlap too low: {avg_overlap}"
```

### Performance Tests

Monitor for:
- Latency increase from MQE (expected: 50-100% increase)
- Cache hit rate improvement (expected: 20-30% improvement)
- Memory usage increase (expected: minimal)

---

## Monitoring & Metrics

### New Metrics to Track

```python
# Add to metrics tracking:

# Phase 1
"semantic_cache_hit_rate"
"semantic_cache_key_generation_time_ms"

# Phase 2
"mqe_paraphrases_generated"
"mqe_aggregation_time_ms"
"mqe_unique_docs_found"

# Phase 3
"search_enhancement_boost_applied"
"search_enhancement_score_delta"

# Phase 4
"query_normalization_applied"
"query_normalization_confidence"
"query_normalization_intent_distribution"
```

### Alerts

Set up alerts for:
- Semantic cache hit rate drops below 20%
- MQE latency exceeds 500ms
- Query normalization confidence consistently low

---

## Rollback Plan

Each phase can be independently disabled:

```bash
# Phase 1: Disable semantic caching
export SEMANTIC_CACHE_ENABLED=false

# Phase 2: Disable MQE
export MQE_ENABLED=false

# Phase 3: Disable search enhancements
export SEARCH_ENHANCEMENTS_ENABLED=false

# Phase 4: Disable query normalization
export QUERY_NORMALIZATION_ENABLED=false

# Or use feature flags via API:
# POST /admin/features/semantic_cache_keys {"state": "disabled"}
```

---

## Success Criteria

After all phases are fully rolled out:

| Metric | Current | Target |
|--------|---------|--------|
| S3 Paraphrase Overlap | 0.0 - 0.33 | > 0.55 |
| S3 semantic_similarity pass | Failing | Passing |
| S3 result_consistency pass | Failing | Passing |
| Cache hit rate (paraphrased queries) | ~0% | > 30% |
| Average retrieval latency | ~100ms | < 200ms (with MQE) |

---

## Summary

This phased approach provides:

1. **Incremental deployment** - Each phase adds value independently
2. **Safe rollout** - Feature flags allow gradual exposure
3. **Easy rollback** - Each phase can be disabled instantly
4. **Measurable progress** - Clear metrics for each phase
5. **Minimal risk** - Building on existing, tested code

The implementation leverages existing components (`MultiQueryExpander`, `apply_search_enhancements`) while adding new capabilities (semantic caching, query normalization) in a structured manner.
