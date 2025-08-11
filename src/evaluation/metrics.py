"""
Evaluation Metrics for Phase 4.2 - Lockdown & Eval Integrity

Implements core retrieval evaluation metrics including:
- Precision@k (P@1, P@5, P@10)
- Normalized Discounted Cumulative Gain (NDCG@k)
- Mean Reciprocal Rank (MRR)
- Custom metrics for narrative retrieval and hard negative evaluation
"""

import math
from typing import Dict, List, Optional, Set, Union, Any
import logging

logger = logging.getLogger(__name__)


class EvaluationMetrics:
    """Core evaluation metrics for retrieval systems."""
    
    @staticmethod
    def precision_at_k(
        relevant_items: Union[List[str], Set[str]], 
        retrieved_items: List[str], 
        k: int
    ) -> float:
        """
        Calculate Precision@k metric.
        
        Args:
            relevant_items: Ground truth relevant document IDs
            retrieved_items: Retrieved document IDs in ranked order
            k: Number of top results to consider
            
        Returns:
            Precision@k score (0.0 to 1.0)
        """
        if k <= 0 or not retrieved_items:
            return 0.0
        
        relevant_set = set(relevant_items) if isinstance(relevant_items, list) else relevant_items
        retrieved_k = retrieved_items[:k]
        
        relevant_count = sum(1 for item in retrieved_k if item in relevant_set)
        return relevant_count / min(k, len(retrieved_k))
    
    @staticmethod
    def ndcg_at_k(
        relevance_scores: Dict[str, float], 
        retrieved_items: List[str], 
        k: int
    ) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain@k.
        
        Args:
            relevance_scores: Document ID -> relevance score mapping
            retrieved_items: Retrieved document IDs in ranked order
            k: Number of top results to consider
            
        Returns:
            NDCG@k score (0.0 to 1.0)
        """
        if k <= 0 or not retrieved_items or not relevance_scores:
            return 0.0
        
        # Calculate DCG@k
        dcg = 0.0
        for i, item_id in enumerate(retrieved_items[:k]):
            if item_id in relevance_scores:
                relevance = relevance_scores[item_id]
                # Use log2(i + 2) for position discount (i is 0-indexed)
                dcg += relevance / math.log2(i + 2)
        
        # Calculate IDCG@k (ideal DCG)
        sorted_scores = sorted(relevance_scores.values(), reverse=True)
        idcg = 0.0
        for i, score in enumerate(sorted_scores[:k]):
            idcg += score / math.log2(i + 2)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    @staticmethod
    def mean_reciprocal_rank(
        relevant_items: Union[List[str], Set[str]], 
        retrieved_items: List[str]
    ) -> float:
        """
        Calculate Mean Reciprocal Rank for a single query.
        
        Args:
            relevant_items: Ground truth relevant document IDs
            retrieved_items: Retrieved document IDs in ranked order
            
        Returns:
            Reciprocal rank (0.0 to 1.0)
        """
        if not retrieved_items:
            return 0.0
        
        relevant_set = set(relevant_items) if isinstance(relevant_items, list) else relevant_items
        
        for i, item_id in enumerate(retrieved_items):
            if item_id in relevant_set:
                return 1.0 / (i + 1)  # i is 0-indexed, rank is 1-indexed
        
        return 0.0
    
    @staticmethod
    def recall_at_k(
        relevant_items: Union[List[str], Set[str]], 
        retrieved_items: List[str], 
        k: int
    ) -> float:
        """
        Calculate Recall@k metric.
        
        Args:
            relevant_items: Ground truth relevant document IDs
            retrieved_items: Retrieved document IDs in ranked order
            k: Number of top results to consider
            
        Returns:
            Recall@k score (0.0 to 1.0)
        """
        if k <= 0 or not retrieved_items:
            return 0.0
        
        relevant_set = set(relevant_items) if isinstance(relevant_items, list) else relevant_items
        if not relevant_set:
            return 0.0
        
        retrieved_k = set(retrieved_items[:k])
        found_relevant = len(relevant_set.intersection(retrieved_k))
        
        return found_relevant / len(relevant_set)
    
    @staticmethod
    def f1_at_k(
        relevant_items: Union[List[str], Set[str]], 
        retrieved_items: List[str], 
        k: int
    ) -> float:
        """
        Calculate F1@k metric (harmonic mean of precision and recall).
        
        Args:
            relevant_items: Ground truth relevant document IDs
            retrieved_items: Retrieved document IDs in ranked order
            k: Number of top results to consider
            
        Returns:
            F1@k score (0.0 to 1.0)
        """
        precision = EvaluationMetrics.precision_at_k(relevant_items, retrieved_items, k)
        recall = EvaluationMetrics.recall_at_k(relevant_items, retrieved_items, k)
        
        if precision + recall == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)


class AdvancedMetrics:
    """Advanced metrics for specialized evaluation scenarios."""
    
    @staticmethod
    def para_at_1_hard(
        original_query: str,
        paraphrased_queries: List[str],
        ground_truth: List[str],
        retrieval_func: callable,
        similarity_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Calculate paraphrase robustness metric for hard adversarial cases.
        
        Args:
            original_query: Base query
            paraphrased_queries: List of paraphrased variations
            ground_truth: Expected relevant documents
            retrieval_func: Function to call for retrieval
            similarity_threshold: Minimum similarity for "hard" classification
            
        Returns:
            Dict with para@1_hard score and detailed results
        """
        results = {}
        original_results = retrieval_func(original_query)
        original_p1 = EvaluationMetrics.precision_at_k(ground_truth, original_results, 1)
        
        hard_cases = []
        para_scores = []
        
        for para_query in paraphrased_queries:
            para_results = retrieval_func(para_query)
            para_p1 = EvaluationMetrics.precision_at_k(ground_truth, para_results, 1)
            para_scores.append(para_p1)
            
            # Classify as "hard" if performance drops significantly
            performance_drop = original_p1 - para_p1
            if performance_drop > (1 - similarity_threshold):
                hard_cases.append({
                    'query': para_query,
                    'original_p1': original_p1,
                    'para_p1': para_p1,
                    'performance_drop': performance_drop
                })
        
        return {
            'para_at_1_hard': sum(para_scores) / len(para_scores) if para_scores else 0.0,
            'hard_case_count': len(hard_cases),
            'hard_case_ratio': len(hard_cases) / len(paraphrased_queries) if paraphrased_queries else 0.0,
            'hard_cases': hard_cases,
            'original_p1': original_p1,
            'average_para_p1': sum(para_scores) / len(para_scores) if para_scores else 0.0
        }
    
    @staticmethod
    def narrative_coherence_score(
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        expected_narrative_id: str
    ) -> Dict[str, Any]:
        """
        Evaluate narrative retrieval for multi-chunk queries requiring context assembly.
        
        Args:
            query: Multi-chunk narrative query
            retrieved_chunks: List of retrieved chunks with metadata
            expected_narrative_id: Expected story/event ID
            
        Returns:
            Dict with coherence score and supporting metrics
        """
        if not retrieved_chunks:
            return {
                'narrative_coherence': 0.0,
                'correct_narrative_id': False,
                'chunk_coverage': 0.0,
                'temporal_order_score': 0.0
            }
        
        # Check if correct narrative ID is present
        narrative_ids = [chunk.get('narrative_id') for chunk in retrieved_chunks]
        correct_narrative_present = expected_narrative_id in narrative_ids
        
        # Calculate chunk coverage for the correct narrative
        if correct_narrative_present:
            correct_chunks = [c for c in retrieved_chunks if c.get('narrative_id') == expected_narrative_id]
            chunk_coverage = len(correct_chunks) / len(retrieved_chunks)
            
            # Evaluate temporal ordering if timestamps are available
            temporal_order_score = AdvancedMetrics._calculate_temporal_order_score(correct_chunks)
        else:
            chunk_coverage = 0.0
            temporal_order_score = 0.0
        
        # Overall coherence score (weighted combination)
        narrative_coherence = (
            0.4 * (1.0 if correct_narrative_present else 0.0) +
            0.4 * chunk_coverage +
            0.2 * temporal_order_score
        )
        
        return {
            'narrative_coherence': narrative_coherence,
            'correct_narrative_id': correct_narrative_present,
            'chunk_coverage': chunk_coverage,
            'temporal_order_score': temporal_order_score,
            'retrieved_narrative_ids': list(set(narrative_ids))
        }
    
    @staticmethod
    def _calculate_temporal_order_score(chunks: List[Dict[str, Any]]) -> float:
        """Calculate temporal ordering score for narrative chunks."""
        if len(chunks) < 2:
            return 1.0
        
        # Sort by position in retrieved list and check timestamp order
        sorted_by_retrieval = sorted(chunks, key=lambda x: x.get('retrieval_rank', 0))
        
        correct_order_count = 0
        total_pairs = 0
        
        for i in range(len(sorted_by_retrieval) - 1):
            chunk1 = sorted_by_retrieval[i]
            chunk2 = sorted_by_retrieval[i + 1]
            
            timestamp1 = chunk1.get('timestamp')
            timestamp2 = chunk2.get('timestamp')
            
            if timestamp1 is not None and timestamp2 is not None:
                total_pairs += 1
                if timestamp1 <= timestamp2:  # Correct chronological order
                    correct_order_count += 1
        
        return correct_order_count / total_pairs if total_pairs > 0 else 1.0


class MetricCalculator:
    """Batch metric calculation and reporting."""
    
    def __init__(self):
        self.results = {}
        
    def calculate_standard_metrics(
        self, 
        query_results: Dict[str, Dict],
        k_values: List[int] = [1, 3, 5, 10]
    ) -> Dict[str, Any]:
        """
        Calculate standard retrieval metrics for a set of query results.
        
        Args:
            query_results: Dict mapping query_id to result dict with 'relevant' and 'retrieved'
            k_values: List of k values for @k metrics
            
        Returns:
            Aggregated metric results
        """
        all_metrics = {}
        
        for k in k_values:
            p_at_k_scores = []
            r_at_k_scores = []
            f1_at_k_scores = []
            ndcg_at_k_scores = []
            
            for query_id, result in query_results.items():
                relevant = result.get('relevant', [])
                retrieved = result.get('retrieved', [])
                relevance_scores = result.get('relevance_scores', {})
                
                # Calculate metrics
                p_at_k = EvaluationMetrics.precision_at_k(relevant, retrieved, k)
                r_at_k = EvaluationMetrics.recall_at_k(relevant, retrieved, k)
                f1_at_k = EvaluationMetrics.f1_at_k(relevant, retrieved, k)
                
                p_at_k_scores.append(p_at_k)
                r_at_k_scores.append(r_at_k)
                f1_at_k_scores.append(f1_at_k)
                
                if relevance_scores:
                    ndcg_at_k = EvaluationMetrics.ndcg_at_k(relevance_scores, retrieved, k)
                    ndcg_at_k_scores.append(ndcg_at_k)
            
            # Aggregate results
            all_metrics[f'p_at_{k}'] = sum(p_at_k_scores) / len(p_at_k_scores) if p_at_k_scores else 0.0
            all_metrics[f'r_at_{k}'] = sum(r_at_k_scores) / len(r_at_k_scores) if r_at_k_scores else 0.0
            all_metrics[f'f1_at_{k}'] = sum(f1_at_k_scores) / len(f1_at_k_scores) if f1_at_k_scores else 0.0
            
            if ndcg_at_k_scores:
                all_metrics[f'ndcg_at_{k}'] = sum(ndcg_at_k_scores) / len(ndcg_at_k_scores)
        
        # Calculate MRR
        mrr_scores = []
        for query_id, result in query_results.items():
            relevant = result.get('relevant', [])
            retrieved = result.get('retrieved', [])
            mrr = EvaluationMetrics.mean_reciprocal_rank(relevant, retrieved)
            mrr_scores.append(mrr)
        
        all_metrics['mrr'] = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0.0
        
        # Add summary statistics
        all_metrics['query_count'] = len(query_results)
        all_metrics['avg_retrieved_per_query'] = sum(
            len(result.get('retrieved', [])) for result in query_results.values()
        ) / len(query_results) if query_results else 0.0
        
        logger.info(f"Calculated metrics for {len(query_results)} queries")
        return all_metrics
    
    def save_results(self, results: Dict[str, Any], output_path: str):
        """Save evaluation results to file."""
        import json
        import os
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {output_path}")