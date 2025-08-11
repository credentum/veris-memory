# Gold Evaluation Dataset

## Overview
This directory contains the frozen gold standard evaluation dataset for semantic search quality measurement.

## Files
- `eval_dataset.json` - The gold standard dataset with queries and documents
- `manifest.json` - File hashes and metadata for reproducibility

## Hashing Rules
1. SHA256 hashes are computed on the raw JSON file content
2. Hashes are verified before each evaluation run
3. Any modification invalidates the gold standard status

## Selection Criteria
- **Query Diversity**: Covers microservices, databases, APIs, Kubernetes, and event-driven architecture
- **Relevance Scores**: Hand-labeled relevance from 0.5 (somewhat relevant) to 1.0 (perfect match)
- **Document Types**: Balanced across design, implementation, operations, infrastructure, and deployment
- **Size**: 5 queries, 12 documents (small but representative)

## Usage
```bash
# Verify dataset integrity
sha256sum eval_dataset.json

# Run evaluation
make eval-clean

# Reproduce scores
python ops/eval/run_eval.py --dataset clean --seed 42
```

## Metrics
- **P@1** (Precision at 1): Is the top result relevant?
- **NDCG@5** (Normalized Discounted Cumulative Gain at 5): Quality of top 5 results
- **MRR** (Mean Reciprocal Rank): Position of first relevant result

## Freezing Policy
This dataset is frozen as of commit 875b100. Changes require:
1. New version number
2. Updated manifest with new hashes
3. Justification in PR description
4. Review by 2+ team members