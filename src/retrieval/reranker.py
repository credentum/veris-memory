"""
Reranking Pipeline with Dynamic Gating for Phase 4.2

Implements intelligent reranking system with:
- Dense + Lexical score fusion with configurable weights
- Dynamic rerank gating to skip reranking when not needed
- Cross-encoder style reranking simulation
- Performance monitoring and rerank invocation rate tracking
- Configurable fusion strategies and threshold management
"""

import asyncio
import logging
import time
import random
import math
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import statistics

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Individual search result with scores and metadata."""
    
    id: str
    content: str
    title: Optional[str] = None
    
    # Scoring information
    dense_score: float = 0.0
    lexical_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: Optional[float] = None
    final_score: float = 0.0
    
    # Source information
    dense_retrieval: bool = False
    lexical_retrieval: bool = False
    sources: List[str] = None
    
    # Reranking information
    was_reranked: bool = False
    rerank_latency_ms: Optional[float] = None
    
    # Metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []
        if self.metadata is None:
            self.metadata = {}


@dataclass 
class RetrievalConfig:
    """Configuration for retrieval and reranking."""
    
    # Score fusion weights
    dense_weight: float = 0.7
    lexical_weight: float = 0.3
    
    # Dynamic gating parameters
    enable_dynamic_gating: bool = True
    rerank_threshold: float = 0.1  # Skip rerank if score gap > threshold
    lexical_agreement_bonus: float = 0.05  # Bonus for lexical+dense agreement
    
    # Reranking parameters
    enable_reranking: bool = True
    rerank_top_k: int = 20  # Rerank top K results
    rerank_model: str = "cross_encoder"
    
    # Performance parameters
    max_rerank_latency_ms: float = 100.0  # Skip rerank if expected to be slow
    enable_rerank_caching: bool = True
    
    # Quality parameters
    min_fusion_confidence: float = 0.1  # Minimum confidence to return results


@dataclass
class RetrievalStats:
    """Statistics from retrieval and reranking process."""
    
    timestamp: str
    query: str
    
    # Result counts
    dense_results: int = 0
    lexical_results: int = 0
    fused_results: int = 0
    final_results: int = 0
    
    # Timing
    dense_latency_ms: float = 0.0
    lexical_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    # Gating decisions
    rerank_invoked: bool = False
    rerank_skip_reason: Optional[str] = None
    
    # Quality metrics
    score_gap: float = 0.0  # Gap between top 2 results
    lexical_agreement: bool = False
    fusion_confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScoreFusion(ABC):
    """Abstract base class for score fusion strategies."""
    
    @abstractmethod
    def fuse(self, dense_results: List[SearchResult], lexical_results: List[SearchResult]) -> List[SearchResult]:
        """Fuse dense and lexical results."""
        pass


class WeightedFusion(ScoreFusion):
    """Weighted linear combination of dense and lexical scores."""
    
    def __init__(self, dense_weight: float = 0.7, lexical_weight: float = 0.3):
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight
        
        # Normalize weights
        total_weight = dense_weight + lexical_weight
        self.dense_weight = dense_weight / total_weight
        self.lexical_weight = lexical_weight / total_weight
    
    def fuse(self, dense_results: List[SearchResult], lexical_results: List[SearchResult]) -> List[SearchResult]:
        """Fuse using weighted linear combination."""
        
        # Create document ID -> result mapping
        all_results = {}
        
        # Add dense results
        for result in dense_results:
            result.dense_retrieval = True
            result.sources.append("dense")
            all_results[result.id] = result
        
        # Add or merge lexical results
        for result in lexical_results:
            if result.id in all_results:
                # Merge with existing dense result
                existing = all_results[result.id]
                existing.lexical_retrieval = True
                existing.lexical_score = result.lexical_score
                existing.sources.append("lexical")
            else:
                # New lexical-only result
                result.lexical_retrieval = True
                result.sources.append("lexical")
                all_results[result.id] = result
        
        # Calculate fused scores
        fused_results = []
        for result in all_results.values():
            # Weighted combination
            fused_score = (
                self.dense_weight * result.dense_score + 
                self.lexical_weight * result.lexical_score
            )
            
            result.fused_score = fused_score
            result.final_score = fused_score  # Will be updated by reranking if applied
            fused_results.append(result)
        
        # Sort by fused score
        fused_results.sort(key=lambda x: x.fused_score, reverse=True)
        
        return fused_results


class RankFusion(ScoreFusion):
    """Rank-based fusion (Reciprocal Rank Fusion)."""
    
    def __init__(self, k: float = 60.0):
        self.k = k  # RRF parameter
    
    def fuse(self, dense_results: List[SearchResult], lexical_results: List[SearchResult]) -> List[SearchResult]:
        """Fuse using reciprocal rank fusion."""
        
        all_results = {}
        
        # Add dense results with RRF scores
        for rank, result in enumerate(dense_results):
            result.dense_retrieval = True
            result.sources.append("dense")
            dense_rrf = 1.0 / (self.k + rank + 1)
            result.dense_score = dense_rrf
            all_results[result.id] = result
        
        # Add lexical results with RRF scores
        for rank, result in enumerate(lexical_results):
            lexical_rrf = 1.0 / (self.k + rank + 1)
            
            if result.id in all_results:
                # Merge with existing result
                existing = all_results[result.id]
                existing.lexical_retrieval = True
                existing.lexical_score = lexical_rrf
                existing.sources.append("lexical")
            else:
                # New lexical result
                result.lexical_retrieval = True
                result.lexical_score = lexical_rrf
                result.sources.append("lexical")
                all_results[result.id] = result
        
        # Calculate combined RRF scores
        for result in all_results.values():
            result.fused_score = result.dense_score + result.lexical_score
            result.final_score = result.fused_score
        
        # Sort by combined RRF score
        fused_results = list(all_results.values())
        fused_results.sort(key=lambda x: x.fused_score, reverse=True)
        
        return fused_results


class DynamicGate:
    """Dynamic gating to decide whether to invoke reranking."""
    
    def __init__(self, config: RetrievalConfig):
        self.config = config
    
    def should_rerank(
        self, 
        results: List[SearchResult], 
        query: str,
        retrieval_stats: RetrievalStats
    ) -> Tuple[bool, Optional[str]]:
        """
        Decide whether to invoke reranking.
        
        Args:
            results: Fused search results
            query: Original query
            retrieval_stats: Current retrieval statistics
            
        Returns:
            Tuple of (should_rerank, skip_reason)
        """
        
        if not self.config.enable_dynamic_gating:
            return True, None
        
        if not self.config.enable_reranking:
            return False, "reranking_disabled"
        
        if len(results) < 2:
            return False, "insufficient_results"
        
        # Check score gap between top results
        score_gap = results[0].fused_score - results[1].fused_score
        retrieval_stats.score_gap = score_gap
        
        if score_gap > self.config.rerank_threshold:
            # Large score gap - top result is clearly better
            
            # Check for lexical agreement (bonus condition)
            top_result = results[0]
            has_lexical_agreement = ("dense" in top_result.sources and 
                                   "lexical" in top_result.sources)
            retrieval_stats.lexical_agreement = has_lexical_agreement
            
            if has_lexical_agreement:
                # Both dense and lexical agree on top result - safe to skip
                return False, "score_gap_with_lexical_agreement"
            elif score_gap > self.config.rerank_threshold * 2:
                # Very large score gap - skip even without lexical agreement
                return False, "large_score_gap"
        
        # Check if reranking would be too slow
        expected_rerank_time = self._estimate_rerank_latency(len(results), query)
        if expected_rerank_time > self.config.max_rerank_latency_ms:
            return False, "expected_latency_too_high"
        
        # Check fusion confidence
        fusion_confidence = self._calculate_fusion_confidence(results)
        retrieval_stats.fusion_confidence = fusion_confidence
        
        if fusion_confidence < self.config.min_fusion_confidence:
            # Low confidence in fusion - reranking might help
            return True, None
        
        # Default: proceed with reranking
        return True, None
    
    def _estimate_rerank_latency(self, result_count: int, query: str) -> float:
        """Estimate reranking latency based on result count and query complexity."""
        
        # Base latency per result
        base_latency_per_result = 2.0  # 2ms per result
        
        # Query complexity factor
        query_words = len(query.split())
        complexity_factor = 1.0 + (query_words - 5) * 0.1  # Longer queries take more time
        
        # Estimated latency
        estimated_ms = result_count * base_latency_per_result * complexity_factor
        
        # Add some randomness for realism
        return estimated_ms * random.uniform(0.8, 1.2)
    
    def _calculate_fusion_confidence(self, results: List[SearchResult]) -> float:
        """Calculate confidence in fusion results."""
        
        if not results:
            return 0.0
        
        scores = [r.fused_score for r in results]
        
        # Confidence based on score distribution
        if len(scores) == 1:
            return scores[0]  # Single result - confidence = score
        
        # Calculate coefficient of variation (lower = more confident)
        mean_score = statistics.mean(scores)
        if mean_score == 0:
            return 0.0
        
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
        cv = std_dev / mean_score
        
        # Convert to confidence (lower CV = higher confidence)
        confidence = max(0.0, 1.0 - cv)
        
        return confidence


class CrossEncoderReranker:
    """Simulated cross-encoder reranker."""
    
    def __init__(self, model_name: str = "cross_encoder"):
        self.model_name = model_name
        self.cache = {}  # Simple cache for rerank scores
    
    async def rerank(
        self, 
        query: str, 
        results: List[SearchResult],
        top_k: Optional[int] = None
    ) -> Tuple[List[SearchResult], float]:
        """
        Rerank results using cross-encoder.
        
        Args:
            query: Query text
            results: Results to rerank
            top_k: Number of top results to rerank
            
        Returns:
            Tuple of (reranked_results, latency_ms)
        """
        
        start_time = time.time()
        
        # Limit to top_k results for efficiency
        if top_k:
            results_to_rerank = results[:top_k]
            remaining_results = results[top_k:]
        else:
            results_to_rerank = results
            remaining_results = []
        
        # Simulate reranking for each result
        reranked_results = []
        
        for result in results_to_rerank:
            # Check cache first
            cache_key = f"{query}|{result.id}"
            if cache_key in self.cache:
                rerank_score = self.cache[cache_key]
            else:
                # Simulate cross-encoder scoring
                rerank_score = await self._simulate_cross_encoder_score(query, result)
                self.cache[cache_key] = rerank_score
            
            # Update result with rerank score
            result.rerank_score = rerank_score
            result.final_score = rerank_score  # Use rerank score as final score
            result.was_reranked = True
            
            reranked_results.append(result)
        
        # Sort by rerank scores
        reranked_results.sort(key=lambda x: x.final_score, reverse=True)
        
        # Add remaining results (not reranked)
        final_results = reranked_results + remaining_results
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Update rerank latency for all reranked results
        for result in reranked_results:
            result.rerank_latency_ms = latency_ms / len(reranked_results)
        
        return final_results, latency_ms
    
    async def _simulate_cross_encoder_score(self, query: str, result: SearchResult) -> float:
        """Simulate cross-encoder scoring."""
        
        # Simulate processing time
        await asyncio.sleep(0.001)  # 1ms per result
        
        # Simulate cross-encoder logic
        # Real implementation would use transformer model
        
        query_words = set(query.lower().split())
        content_words = set(result.content.lower().split())
        
        # Word overlap score
        overlap = len(query_words.intersection(content_words))
        overlap_score = overlap / max(len(query_words), 1)
        
        # Length penalty for very long content
        content_length = len(result.content.split())
        length_penalty = 1.0 if content_length < 200 else 0.9
        
        # Base score from fusion (prior information)
        base_score = result.fused_score
        
        # Combine factors
        cross_encoder_score = (
            0.4 * overlap_score +
            0.1 * length_penalty +
            0.5 * base_score +
            random.uniform(-0.05, 0.05)  # Add some noise
        )
        
        return max(0.0, min(1.0, cross_encoder_score))


class RetrievalReranker:
    """Main retrieval and reranking pipeline."""
    
    def __init__(self, config: Optional[RetrievalConfig] = None):
        """Initialize retrieval reranker."""
        
        self.config = config or RetrievalConfig()
        
        # Initialize components
        if self.config.dense_weight > 0 and self.config.lexical_weight > 0:
            self.fusion = WeightedFusion(self.config.dense_weight, self.config.lexical_weight)
        else:
            # Use rank fusion if one weight is zero
            self.fusion = RankFusion()
        
        self.gate = DynamicGate(self.config)
        self.reranker = CrossEncoderReranker(self.config.rerank_model)
        
        # Statistics tracking
        self.stats_history = []
        
        self.logger = logging.getLogger(__name__)
    
    async def retrieve_and_rerank(
        self, 
        query: str, 
        top_k: int = 10
    ) -> Tuple[List[SearchResult], RetrievalStats]:
        """
        Main retrieval and reranking pipeline.
        
        Args:
            query: Search query
            top_k: Number of final results to return
            
        Returns:
            Tuple of (final_results, retrieval_stats)
        """
        
        start_time = time.time()
        
        # Initialize stats
        stats = RetrievalStats(
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
            query=query
        )
        
        try:
            # Step 1: Dense retrieval
            dense_start = time.time()
            dense_results = await self._dense_retrieval(query, top_k * 2)
            stats.dense_latency_ms = (time.time() - dense_start) * 1000
            stats.dense_results = len(dense_results)
            
            # Step 2: Lexical retrieval
            lexical_start = time.time()
            lexical_results = await self._lexical_retrieval(query, top_k * 2)
            stats.lexical_latency_ms = (time.time() - lexical_start) * 1000
            stats.lexical_results = len(lexical_results)
            
            # Step 3: Score fusion
            fusion_start = time.time()
            fused_results = self.fusion.fuse(dense_results, lexical_results)
            stats.fusion_latency_ms = (time.time() - fusion_start) * 1000
            stats.fused_results = len(fused_results)
            
            # Step 4: Dynamic gating decision
            should_rerank, skip_reason = self.gate.should_rerank(fused_results, query, stats)
            stats.rerank_invoked = should_rerank
            stats.rerank_skip_reason = skip_reason
            
            # Step 5: Reranking (if needed)
            final_results = fused_results
            
            if should_rerank:
                rerank_start = time.time()
                reranked_results, rerank_latency = await self.reranker.rerank(
                    query, fused_results, self.config.rerank_top_k
                )
                stats.rerank_latency_ms = rerank_latency
                final_results = reranked_results
            else:
                stats.rerank_latency_ms = 0.0
                self.logger.info(f"Skipped reranking: {skip_reason}")
            
            # Step 6: Final result selection
            final_results = final_results[:top_k]
            stats.final_results = len(final_results)
            
            # Calculate total time
            stats.total_latency_ms = (time.time() - start_time) * 1000
            
            # Track stats
            self.stats_history.append(stats)
            if len(self.stats_history) > 1000:  # Keep last 1000 queries
                self.stats_history.pop(0)
            
            self.logger.info(
                f"Query processed: {len(final_results)} results, "
                f"{stats.total_latency_ms:.1f}ms total, "
                f"reranked: {should_rerank}"
            )
            
            return final_results, stats
            
        except Exception as e:
            self.logger.error(f"Retrieval error: {str(e)}")
            raise
    
    async def _dense_retrieval(self, query: str, limit: int) -> List[SearchResult]:
        """Simulate dense vector retrieval."""
        
        # Simulate dense retrieval latency
        await asyncio.sleep(0.01)  # 10ms
        
        # Generate mock dense results
        results = []
        for i in range(min(limit, 10)):  # Max 10 dense results
            score = 0.9 - (i * 0.08)  # Decreasing scores
            result = SearchResult(
                id=f"dense_{i}",
                content=f"Dense retrieval result {i} for query: {query}",
                title=f"Dense Result {i}",
                dense_score=score,
                metadata={"retrieval_type": "dense", "rank": i}
            )
            results.append(result)
        
        return results
    
    async def _lexical_retrieval(self, query: str, limit: int) -> List[SearchResult]:
        """Simulate lexical/BM25 retrieval."""
        
        # Simulate lexical retrieval latency
        await asyncio.sleep(0.005)  # 5ms
        
        # Generate mock lexical results (some overlap with dense)
        results = []
        for i in range(min(limit, 8)):  # Max 8 lexical results
            # Sometimes overlap with dense results
            if i < 3 and random.random() < 0.3:  # 30% chance of overlap for top 3
                doc_id = f"dense_{i}"  # Same as dense result
            else:
                doc_id = f"lexical_{i}"
            
            score = 0.8 - (i * 0.09)  # Decreasing scores
            result = SearchResult(
                id=doc_id,
                content=f"Lexical retrieval result {i} for query: {query}",
                title=f"Lexical Result {i}",
                lexical_score=score,
                metadata={"retrieval_type": "lexical", "rank": i}
            )
            results.append(result)
        
        return results
    
    def get_rerank_invocation_rate(self, window_size: int = 100) -> float:
        """Calculate rerank invocation rate over recent queries."""
        
        if not self.stats_history:
            return 0.0
        
        recent_stats = self.stats_history[-window_size:]
        invoked_count = sum(1 for s in recent_stats if s.rerank_invoked)
        
        return invoked_count / len(recent_stats)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        
        if not self.stats_history:
            return {}
        
        recent_stats = self.stats_history[-100:]  # Last 100 queries
        
        total_latencies = [s.total_latency_ms for s in recent_stats]
        rerank_latencies = [s.rerank_latency_ms for s in recent_stats if s.rerank_invoked]
        
        summary = {
            'query_count': len(recent_stats),
            'avg_total_latency_ms': statistics.mean(total_latencies),
            'p95_total_latency_ms': statistics.quantiles(sorted(total_latencies), n=20)[18] if len(total_latencies) >= 20 else max(total_latencies),
            'rerank_invocation_rate': self.get_rerank_invocation_rate(),
            'avg_rerank_latency_ms': statistics.mean(rerank_latencies) if rerank_latencies else 0.0,
            'score_gap_avg': statistics.mean([s.score_gap for s in recent_stats]),
            'lexical_agreement_rate': sum(1 for s in recent_stats if s.lexical_agreement) / len(recent_stats)
        }
        
        return summary


# Convenience functions for easy usage

async def create_standard_reranker(
    dense_weight: float = 0.7,
    lexical_weight: float = 0.3,
    enable_dynamic_gating: bool = True
) -> RetrievalReranker:
    """Create standard reranker configuration."""
    
    config = RetrievalConfig(
        dense_weight=dense_weight,
        lexical_weight=lexical_weight,
        enable_dynamic_gating=enable_dynamic_gating,
        rerank_threshold=0.1,
        enable_reranking=True
    )
    
    return RetrievalReranker(config)


async def create_ablation_rerankers() -> Dict[str, RetrievalReranker]:
    """Create rerankers for ablation testing."""
    
    rerankers = {}
    
    # Dense only
    config_dense = RetrievalConfig(dense_weight=1.0, lexical_weight=0.0, enable_reranking=False)
    rerankers['dense_only'] = RetrievalReranker(config_dense)
    
    # Lexical only
    config_lexical = RetrievalConfig(dense_weight=0.0, lexical_weight=1.0, enable_reranking=False)
    rerankers['lexical_only'] = RetrievalReranker(config_lexical)
    
    # Hybrid without rerank
    config_hybrid = RetrievalConfig(dense_weight=0.7, lexical_weight=0.3, enable_reranking=False)
    rerankers['hybrid_no_rerank'] = RetrievalReranker(config_hybrid)
    
    # Full pipeline
    config_full = RetrievalConfig(dense_weight=0.7, lexical_weight=0.3, enable_reranking=True)
    rerankers['hybrid_with_rerank'] = RetrievalReranker(config_full)
    
    return rerankers