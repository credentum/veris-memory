# Sort By Parameter Documentation

## Overview

The `sort_by` parameter in the `retrieve_context` tool allows you to control the ordering of search results. This parameter was introduced to fix a critical issue where messages were getting lost due to lack of chronological ordering.

## Parameter Details

- **Parameter Name**: `sort_by`
- **Type**: `string`
- **Values**: `"timestamp"` | `"relevance"`
- **Default**: `"timestamp"`
- **Added in Version**: 1.1.0

## Values

### `timestamp` (Default)
Orders results by creation timestamp, with the most recent contexts appearing first. This is the default behavior to ensure recent messages and contexts are easily discoverable.

**Use Cases:**
- Chat/conversation contexts where recency matters
- Finding the latest updates or changes
- Chronological browsing of context history
- Default behavior for most use cases

**Example:**
```json
{
  "query": "workspace updates",
  "sort_by": "timestamp",
  "limit": 10
}
```

### `relevance`
Orders results by relevance score, with the highest scoring contexts appearing first. The score is calculated differently for vector and graph results:
- **Vector results**: Cosine similarity score (0-1)
- **Graph results**: Distance-based score using formula `1.0 / (hop_distance + 0.5)`

**Use Cases:**
- Semantic search where best match matters most
- Finding the most relevant technical documentation
- Research queries where accuracy trumps recency

**Example:**
```json
{
  "query": "authentication implementation",
  "sort_by": "relevance",
  "limit": 10
}
```

## Migration Guide

### Breaking Change Notice
Prior to version 1.1.0, the system had broken relevance sorting where graph results appeared with no scores. The default behavior was unpredictable and messages could get lost.

### Migration Steps

1. **Review Current Integrations**: Check if your code expects relevance-based sorting by default
2. **Update API Calls**: Explicitly specify `sort_by: "relevance"` if you need score-based ordering
3. **Test Behavior**: The new default (`timestamp`) ensures recent contexts appear first

### Before (Broken Behavior)
```python
# Results appeared in random order, graph results had no scores
result = await retrieve_context_tool(query="test")
# Messages could be lost, hard to find recent contexts
```

### After (Fixed Behavior)
```python
# Default: Recent contexts first
result = await retrieve_context_tool(query="test")  # Uses timestamp ordering

# Explicit relevance sorting
result = await retrieve_context_tool(
    query="test",
    sort_by="relevance"  # High-score contexts first
)
```

## Implementation Details

### Sorting Logic

The sorting is applied after combining results from all search sources (vector, graph, key-value):

```python
if sort_by == "timestamp":
    results.sort(key=lambda x: x.get("created_at", "") or "", reverse=True)
elif sort_by == "relevance":
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
```

### Score Calculation

#### Vector Search Scores
- Calculated by Qdrant using cosine similarity
- Range: 0.0 to 1.0
- Higher scores indicate better semantic match

#### Graph Search Scores
- Calculated using hop distance: `score = 1.0 / (hop_distance + 0.5)`
- Examples:
  - Direct connection (1 hop): 0.667
  - Two hops: 0.400
  - Three hops: 0.286

### Performance Considerations

When using `sort_by="timestamp"` with graph queries:
- The Cypher query still orders by hop_distance internally for efficiency
- Final sorting by timestamp happens in application code
- For large result sets, consider using smaller `limit` values

## Error Handling

Invalid `sort_by` values return an error response:

```json
{
  "success": false,
  "results": [],
  "message": "Invalid sort_by value: 'invalid'. Must be 'timestamp' or 'relevance'",
  "error_type": "invalid_parameter"
}
```

## Examples

### Finding Recent Workspace Messages
```python
# Get the 5 most recent messages for workspace 001
result = await retrieve_context_tool(
    query="workspace 001",
    sort_by="timestamp",  # Explicit, though it's the default
    limit=5
)
```

### Finding Best Technical Matches
```python
# Get the most relevant authentication docs
result = await retrieve_context_tool(
    query="OAuth2 JWT implementation",
    sort_by="relevance",
    search_mode="hybrid",
    limit=10
)
```

### Combined with Filters
```python
# Recent design decisions from last week
result = await retrieve_context_tool(
    query="architecture decision",
    sort_by="timestamp",
    type="decision",
    filters={
        "date_from": "2025-01-10"
    },
    limit=20
)
```

## Troubleshooting

### Q: Why was the default changed to timestamp?
**A:** The previous relevance-based sorting was broken (graph results had no scores), causing messages to appear randomly and get lost. Timestamp ordering ensures predictable, chronological results.

### Q: When should I use relevance sorting?
**A:** Use relevance sorting when:
- Doing semantic search for documentation
- The best match matters more than recency
- Searching through historical data where dates don't matter

### Q: How do I maintain backward compatibility?
**A:** If your application expects relevance-based sorting, explicitly add `sort_by="relevance"` to your API calls. Note that relevance sorting now works correctly with proper scoring for all result types.

### Q: What happens to results without timestamps?
**A:** Results missing timestamps are sorted to the end when using timestamp sorting. They receive an empty string as their sort key.

## Related Documentation

- [Retrieve Context Tool Reference](./tools/retrieve_context.md)
- [Search Modes Documentation](./search_modes.md)
- [Graph Scoring Implementation](./internals/graph_scoring.md)
- [Performance Tuning Guide](./performance.md)