# Sentinel Optimization Migration Guide

## Overview

This guide helps you migrate monitoring dashboards and alerting after PR #327 (Sentinel query optimization).

**Changes Summary**:
- **S3**: Reduced from 25 to 6 queries (still active, just optimized)
- **S9**: Deprecated (consolidated into S2)
- **S10**: Deprecated (consolidated into S2)
- **S2**: Enhanced with graph relationship validation

**Query Count Evolution**:
- **Original**: 48 queries/cycle (2,880/hour)
- **After Phase 1 & 2**: 18 queries/cycle (commit 75ce17c)
- **After Code Review Enhancement**: 22 queries/cycle (commits 8a92bc9 + 86ebcbb)
  - S2 enhanced from 8 to 12 queries (added 2 more graph test cases)
  - Final total: 22 queries/cycle = 1,320 queries/hour
  - **Net reduction**: 54% from original 48 queries

**Timeline**:
- **Deprecated since**: 2025-11-17
- **Removal planned**: 2025-12-17 (30 days)
- **Action required**: Update dashboards before removal date

---

## Dashboard Migration

### Grafana Dashboards

#### 1. S9 Graph Intent (DEPRECATED)

**Current panels to update**:
```
Panel: "S9 Graph Intent Status"
Query: sentinel_check_status{check_id="S9-graph-intent"}
```

**Migration options**:

**Option A**: Hide the panel (recommended for first 2 weeks)
```
1. Edit panel → Display → Transparent background
2. Add note: "DEPRECATED - Consolidated into S2 (see S2 Graph Relationships)"
3. Keep visible to track deprecation rollout
```

**Option B**: Remove the panel (after 2 weeks)
```
1. Delete "S9 Graph Intent Status" panel
2. Ensure S2 panels cover graph relationship monitoring
```

**Option C**: Repurpose for S2 Graph Relationships
```
Panel: "S2 Graph Relationship Validation"
Query: sentinel_check_status{check_id="S2-golden-fact-recall",test_type="graph_relationship"}
```

---

#### 2. S10 Content Pipeline (DEPRECATED)

**Current panels to update**:
```
Panel: "S10 Content Pipeline Status"
Query: sentinel_check_status{check_id="S10-content-pipeline"}
```

**Migration**:

**Replace with**: S2 Pipeline Health (implicit validation)
```
Panel: "S2 Semantic Search & Pipeline"
Query: sentinel_check_status{check_id="S2-golden-fact-recall"}
Note: "S2's store→retrieve cycle validates pipeline health"
```

**Why this works**:
- S2 tests store facts → retrieve facts
- This validates: ingestion → storage → indexing → retrieval
- Full pipeline is exercised by S2's test cycle

---

#### 3. S3 Paraphrase Robustness (OPTIMIZED)

**Current panels** (NO CHANGES NEEDED):
```
Panel: "S3 Paraphrase Status"
Query: sentinel_check_status{check_id="S3-paraphrase-robustness"}
```

**Status**: Still active, just optimized (25 → 6 queries)

**Optional enhancement**:
```
Panel note: "Runtime: 2 topics × 3 variations (6 queries)
Full matrix: 5 topics × 5 variations (25 tests) in CI/CD"
```

---

#### 4. S2 Golden Fact Recall (ENHANCED)

**Add new panels**:

**Panel 1**: S2 Overall Status (already exists, no changes)
```
Panel: "S2 Semantic Search Status"
Query: sentinel_check_status{check_id="S2-golden-fact-recall"}
```

**Panel 2**: S2 Test Type Breakdown (NEW - recommended)
```
Panel: "S2 Test Coverage"
Query A: count(sentinel_check_details{check_id="S2-golden-fact-recall",test_type="semantic_search"})
Query B: count(sentinel_check_details{check_id="S2-golden-fact-recall",test_type="graph_relationship"})

Visualization: Pie chart or stat panel
- Semantic Search: 3 facts (6 queries)
- Graph Relationships: 3 relationships (6 queries)
```

**Panel 3**: S2 Success Rate (NEW - recommended)
```
Panel: "S2 Query Success Rate"
Query: rate(sentinel_check_passed_tests{check_id="S2-golden-fact-recall"}[5m]) /
       rate(sentinel_check_total_tests{check_id="S2-golden-fact-recall"}[5m])

Threshold: Green >90%, Yellow 70-90%, Red <70%
```

---

### Example Dashboard Layout (Recommended)

**Before** (old layout):
```
┌─────────────┬─────────────┬─────────────┐
│ S2 Golden   │ S3 Para-    │ S9 Graph    │
│ Fact Recall │ phrase      │ Intent      │
├─────────────┼─────────────┼─────────────┤
│ S10 Content │ Other       │ Other       │
│ Pipeline    │ Checks      │ Checks      │
└─────────────┴─────────────┴─────────────┘
```

**After** (optimized layout):
```
┌─────────────────────┬─────────────┬─────────────┐
│ S2 Comprehensive    │ S3 Para-    │ Other       │
│ (Semantic + Graph + │ phrase      │ Checks      │
│  Pipeline)          │             │             │
│ - Overall Status    │ (Optimized) │             │
│ - Test Breakdown    │             │             │
│ - Success Rate      │             │             │
├─────────────────────┼─────────────┼─────────────┤
│ Deprecated Checks   │ Query Load  │ Latency     │
│ S9: DEPRECATED →S2  │ Metrics     │ Metrics     │
│ S10: DEPRECATED →S2 │             │             │
└─────────────────────┴─────────────┴─────────────┘
```

---

## Alerting Rules

### Update Alert Definitions

#### 1. S9 Graph Intent Alerts (DEPRECATED)

**Current alert**:
```yaml
alert: S9GraphIntentFailing
expr: sentinel_check_status{check_id="S9-graph-intent"} == 0
for: 5m
labels:
  severity: warning
annotations:
  summary: "Graph intent validation failing"
```

**Action**: Delete this alert (S9 will always return "pass")

**Replace with**: S2 Graph Relationship Alert
```yaml
alert: S2GraphRelationshipFailing
expr: |
  sentinel_check_passed_tests{check_id="S2-golden-fact-recall",test_type="graph_relationship"}
  / sentinel_check_total_tests{check_id="S2-golden-fact-recall",test_type="graph_relationship"}
  < 0.7
for: 5m
labels:
  severity: warning
annotations:
  summary: "S2 graph relationship tests failing"
  description: "Less than 70% of graph relationship tests passing"
```

---

#### 2. S10 Pipeline Alerts (DEPRECATED)

**Current alert**:
```yaml
alert: S10PipelineFailing
expr: sentinel_check_status{check_id="S10-content-pipeline"} == 0
for: 5m
labels:
  severity: critical
annotations:
  summary: "Content pipeline failing"
```

**Action**: Delete this alert (S10 will always return "pass")

**Replace with**: S2 Overall Alert (catches pipeline issues)
```yaml
alert: S2SemanticSearchFailing
expr: sentinel_check_status{check_id="S2-golden-fact-recall"} == 0
for: 5m
labels:
  severity: critical
annotations:
  summary: "S2 semantic search failing (includes pipeline validation)"
  description: "S2 store→retrieve cycle failing, indicates pipeline or search issues"
```

**Rationale**: S2's store/retrieve cycle exercises the full pipeline, so S2 failures indicate pipeline problems.

---

#### 3. S3 Alerts (NO CHANGES NEEDED)

**Current alert** (still valid):
```yaml
alert: S3ParaphraseFailing
expr: sentinel_check_status{check_id="S3-paraphrase-robustness"} == 0
for: 5m
labels:
  severity: warning
annotations:
  summary: "Paraphrase robustness failing"
```

**Status**: Keep as-is. Still active, just optimized.

---

## Metrics to Track

### New Metrics (S2 Enhanced)

```promql
# S2 test type breakdown
sentinel_check_test_type_count{check_id="S2-golden-fact-recall",test_type="semantic_search"}
sentinel_check_test_type_count{check_id="S2-golden-fact-recall",test_type="graph_relationship"}

# S2 success rate by type
rate(sentinel_check_passed_tests{check_id="S2-golden-fact-recall",test_type="semantic_search"}[5m])
rate(sentinel_check_passed_tests{check_id="S2-golden-fact-recall",test_type="graph_relationship"}[5m])

# Overall query load reduction
sum(rate(sentinel_total_queries[5m]))  # Should drop from 2880/hr to 1080/hr
```

### Deprecated Metrics (S9, S10)

These metrics will show "deprecated=True":
```promql
sentinel_check_details{check_id="S9-graph-intent",deprecated="true"}
sentinel_check_details{check_id="S10-content-pipeline",deprecated="true"}
```

**Timeline**:
- **Week 1-2**: Metrics show deprecated=true, status=pass
- **Week 3-4**: Plan removal from monitoring
- **After 2025-12-17**: S9/S10 will be removed entirely

---

## Recommended Dashboard Queries

### Query Load Monitoring

**Before/After Comparison**:
```promql
# Total queries per hour (should drop 62%)
sum(rate(sentinel_queries_total[1h])) by (check_id)

# By check:
S1: 120/hr (unchanged)
S2: 720/hr (was 360/hr - enhanced with graph tests)
S3: 360/hr (was 1500/hr - optimized)
S4-S8, S11: unchanged
S9: 0/hr (was 480/hr - deprecated)
S10: 0/hr (was 300/hr - deprecated)
```

### Success Rate Dashboard

```promql
# Overall Sentinel health
(sum(rate(sentinel_check_passed_tests[5m])) /
 sum(rate(sentinel_check_total_tests[5m]))) * 100

# Per-check success rates
rate(sentinel_check_passed_tests{check_id="S2-golden-fact-recall"}[5m]) /
rate(sentinel_check_total_tests{check_id="S2-golden-fact-recall"}[5m])

# S2 breakdown by test type
rate(sentinel_check_passed_tests{check_id="S2-golden-fact-recall",test_type="semantic_search"}[5m])
rate(sentinel_check_passed_tests{check_id="S2-golden-fact-recall",test_type="graph_relationship"}[5m])
```

---

## Migration Checklist

### Week 1 (Immediately after PR merge)
- [ ] Update Grafana dashboards to show deprecation notices on S9/S10 panels
- [ ] Add S2 test type breakdown panels
- [ ] Verify S3 optimization doesn't break existing alerts
- [ ] Monitor query load reduction (should see 62% drop)

### Week 2
- [ ] Delete S9 graph intent alert rules
- [ ] Delete S10 pipeline alert rules
- [ ] Add S2 graph relationship alerts
- [ ] Verify no false positives from deprecated checks

### Week 3
- [ ] Remove S9 panels from main dashboards (move to "deprecated" section)
- [ ] Remove S10 panels from main dashboards
- [ ] Update team documentation with new S2 coverage
- [ ] Verify CI/CD comprehensive tests are running

### Week 4 (Before 2025-12-17)
- [ ] Complete removal of S9/S10 from all dashboards
- [ ] Complete removal of S9/S10 alert rules
- [ ] Update runbooks to reference S2 for graph/pipeline issues
- [ ] Final verification before code removal

---

## Troubleshooting

### "S9/S10 always showing as passing, is this normal?"

**Yes**. S9 and S10 now return early with status="pass" and deprecation details.

Check the `details` field:
```json
{
  "deprecated": true,
  "deprecated_since": "2025-11-17",
  "removal_planned": "2025-12-17",
  "consolidated_into": "S2-golden-fact-recall"
}
```

### "How do I know if graph relationships are working?"

Check **S2** status and details:
```promql
sentinel_check_status{check_id="S2-golden-fact-recall"}
sentinel_check_details{check_id="S2-golden-fact-recall",test_type="graph_relationship"}
```

S2 now includes 3 graph relationship test cases (6 queries).

### "How do I know if pipeline is working?"

Check **S2** status. S2's store→retrieve cycle validates:
- Ingestion (store facts)
- Storage (persist to Neo4j)
- Indexing (add to Qdrant)
- Retrieval (search and find)

If S2 passes, pipeline is healthy.

### "Where are the comprehensive tests?"

Comprehensive tests strategy:
- **S3**: Comprehensive tests in `.github/workflows/sentinel-comprehensive-tests.yml`
  - Runs on PR + pre-deployment
  - Full paraphrase robustness testing
- **S9 & S10**: Deprecated - no longer have comprehensive tests
  - S9 graph validation consolidated into S2 (runtime monitoring)
  - S10 pipeline validation implicit in S2's store→retrieve cycle
  - S2 unit tests cover this functionality (test_s2_golden_fact_recall.py)

---

## Support

**Questions?** Contact the platform team or open an issue referencing PR #327.

**Related Documentation**:
- PR #327: Sentinel query optimization
- PR #326: Rate limit exemption
- Sentinel architecture: `docs/SENTINEL_ARCHITECTURE.md`
