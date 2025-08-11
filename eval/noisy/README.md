# Noisy Evaluation Datasets

## Overview
This directory contains evaluation datasets with various types of noise to test system robustness.

## Datasets

### noisy/eval_dataset_noisy.json
Contains the following noise types:
- **Exact Duplicates**: Same document appears multiple times (d001_dup)
- **Near Duplicates**: Paraphrased versions of documents (d003_near)
- **Typos**: Documents and queries with spelling errors (d002_typo, q002_typo)
- **Weak Labels**: Marginally relevant documents with low scores (d013_weak)

### long/eval_dataset_long.json
Contains documents with 180-220 words to test:
- Performance with verbose content
- Relevance detection in longer text
- Chunking and summarization capabilities

## Metrics

### Primary Metrics
- **P@1** (Precision at 1): Measures if the top result is relevant
- **NDCG@5** (Normalized Discounted Cumulative Gain): Quality of top 5 results ranking
- **MRR** (Mean Reciprocal Rank): Average position of first relevant result

### Noise-Specific Metrics
- **Duplicate Detection Rate**: % of duplicates correctly identified
- **Typo Tolerance**: Score degradation with typos vs clean queries
- **Long Document Performance**: Latency and accuracy on verbose content

## Expected Performance

| Dataset | Expected P@1 | Expected NDCG@5 | Notes |
|---------|--------------|-----------------|-------|
| Clean   | 0.80-0.90    | 0.75-0.85      | Baseline |
| Noisy   | 0.65-0.75    | 0.60-0.70      | Degradation due to noise |
| Long    | 0.70-0.80    | 0.65-0.75      | Slight degradation from length |

## Usage

```bash
# Run evaluation on noisy dataset
python ops/eval/run_eval.py --dataset noisy --output reports/eval-noisy.json

# Run evaluation on long documents
python ops/eval/run_eval.py --dataset long --output reports/eval-long.json

# Compare all datasets
python ops/eval/run_eval.py --dataset all --compare
```

## Noise Generation Process

1. **Duplicates**: Exact copy of high-relevance documents
2. **Near-duplicates**: Paraphrased using synonyms and restructuring
3. **Typos**: Common misspellings (missing letters, transpositions)
4. **Weak labels**: Generic documents with tangential relevance