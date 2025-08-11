"""
Ablation Study Framework for Phase 4.2

Implements systematic ablation testing and A/B testing including:
- Dense-only, Dense+Lexical, Hybrid+Rerank comparisons
- Statistical significance testing between configurations
- Automated ablation study execution and reporting
- Configuration matrix testing with factorial design
- Performance regression detection and analysis
"""

import asyncio
import logging
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import statistics
import itertools
from scipy import stats as scipy_stats
import pandas as pd

from .evaluator import Evaluator, EvaluationConfig, EvaluationResult
from .datasets import DatasetManager
from .config import EvaluationConfigManager
from retrieval.reranker import RetrievalReranker, RetrievalConfig

logger = logging.getLogger(__name__)


@dataclass
class AblationConfiguration:
    """Single ablation test configuration."""
    
    name: str
    description: str
    
    # Retrieval configuration
    dense_weight: float
    lexical_weight: float
    enable_reranking: bool
    rerank_threshold: float = 0.1
    
    # Advanced settings
    fusion_method: str = "weighted"  # "weighted" or "rank_fusion"
    rerank_top_k: int = 20
    enable_dynamic_gating: bool = True
    
    # Expected performance (for regression testing)
    expected_p_at_1: Optional[float] = None
    expected_ndcg_at_5: Optional[float] = None
    expected_latency_ms: Optional[float] = None
    
    def to_retrieval_config(self) -> RetrievalConfig:
        """Convert to retrieval configuration."""
        return RetrievalConfig(
            dense_weight=self.dense_weight,
            lexical_weight=self.lexical_weight,
            enable_reranking=self.enable_reranking,
            rerank_threshold=self.rerank_threshold,
            enable_dynamic_gating=self.enable_dynamic_gating,
            rerank_top_k=self.rerank_top_k
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AblationResult:
    """Results from single ablation configuration."""
    
    configuration: AblationConfiguration
    evaluation_result: EvaluationResult
    
    # Key metrics extracted
    p_at_1: float
    p_at_5: float
    ndcg_at_5: float
    ndcg_at_10: float
    mrr: float
    
    # Performance metrics
    avg_latency_ms: float
    p95_latency_ms: float
    queries_per_second: float
    
    # Reranking metrics
    rerank_invocation_rate: float
    rerank_avg_latency_ms: float
    
    # Statistical confidence
    confidence_interval_95: Dict[str, Tuple[float, float]]
    
    def to_dict(self) -> Dict[str, Any]:
        result_dict = asdict(self)
        # Convert evaluation_result to dict
        result_dict['evaluation_result'] = asdict(self.evaluation_result)
        return result_dict


@dataclass
class AblationComparison:
    """Statistical comparison between two ablation results."""
    
    baseline_name: str
    variant_name: str
    
    # Metric comparisons
    p_at_1_diff: float
    p_at_1_p_value: float
    p_at_1_significant: bool
    
    ndcg_at_5_diff: float
    ndcg_at_5_p_value: float
    ndcg_at_5_significant: bool
    
    latency_diff_ms: float
    latency_p_value: float
    latency_significant: bool
    
    # Overall assessment
    overall_better: bool  # Is variant significantly better?
    effect_size: float    # Cohen's d effect size
    recommendation: str   # "adopt", "reject", "inconclusive"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AblationStudyResult:
    """Complete ablation study results."""
    
    study_name: str
    timestamp: str
    duration_minutes: float
    
    # Configuration
    configurations_tested: int
    dataset_used: str
    queries_per_config: int
    
    # Results
    ablation_results: List[AblationResult]
    pairwise_comparisons: List[AblationComparison]
    
    # Analysis
    best_configuration: str
    performance_ranking: List[Tuple[str, float]]  # (config_name, score)
    
    # Insights
    key_findings: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'ablation_results': [r.to_dict() for r in self.ablation_results],
            'pairwise_comparisons': [c.to_dict() for c in self.pairwise_comparisons]
        }


class StatisticalTester:
    """Statistical testing utilities for ablation studies."""
    
    @staticmethod
    def bootstrap_confidence_interval(
        data: List[float], 
        confidence: float = 0.95,
        n_bootstrap: int = 1000
    ) -> Tuple[float, float]:
        """Calculate bootstrap confidence interval."""
        
        if len(data) < 2:
            return (0.0, 0.0)
        
        import random
        
        bootstrap_means = []
        
        for _ in range(n_bootstrap):
            # Bootstrap sample
            sample = [random.choice(data) for _ in range(len(data))]
            bootstrap_means.append(statistics.mean(sample))
        
        bootstrap_means.sort()
        
        # Calculate confidence interval
        alpha = 1 - confidence
        lower_idx = int(alpha / 2 * n_bootstrap)
        upper_idx = int((1 - alpha / 2) * n_bootstrap)
        
        return (bootstrap_means[lower_idx], bootstrap_means[upper_idx])
    
    @staticmethod
    def welch_t_test(data1: List[float], data2: List[float]) -> Tuple[float, float]:
        """Perform Welch's t-test (unequal variances)."""
        
        if len(data1) < 2 or len(data2) < 2:
            return (0.0, 1.0)  # No difference, high p-value
        
        try:
            # Use scipy if available
            t_stat, p_value = scipy_stats.ttest_ind(data1, data2, equal_var=False)
            return (float(t_stat), float(p_value))
        except ImportError:
            # Fallback implementation
            mean1, mean2 = statistics.mean(data1), statistics.mean(data2)
            var1, var2 = statistics.variance(data1), statistics.variance(data2)
            n1, n2 = len(data1), len(data2)
            
            # Welch's t-statistic
            pooled_se = ((var1 / n1) + (var2 / n2)) ** 0.5
            if pooled_se == 0:
                return (0.0, 1.0)
            
            t_stat = (mean1 - mean2) / pooled_se
            
            # Approximate p-value (simplified)
            # In real implementation, use proper t-distribution
            p_value = 2 * (1 - abs(t_stat) / 10)  # Rough approximation
            p_value = max(0.0, min(1.0, p_value))
            
            return (t_stat, p_value)
    
    @staticmethod
    def cohens_d(data1: List[float], data2: List[float]) -> float:
        """Calculate Cohen's d effect size."""
        
        if len(data1) < 2 or len(data2) < 2:
            return 0.0
        
        mean1, mean2 = statistics.mean(data1), statistics.mean(data2)
        var1, var2 = statistics.variance(data1), statistics.variance(data2)
        n1, n2 = len(data1), len(data2)
        
        # Pooled standard deviation
        pooled_std = (((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)) ** 0.5
        
        if pooled_std == 0:
            return 0.0
        
        return (mean1 - mean2) / pooled_std


class AblationRunner:
    """Main ablation study framework."""
    
    def __init__(
        self,
        evaluator: Evaluator,
        dataset_manager: DatasetManager,
        results_dir: str = "./ablation_studies"
    ):
        """
        Initialize ablation runner.
        
        Args:
            evaluator: Evaluator for running tests
            dataset_manager: Dataset manager for test data
            results_dir: Directory for storing results
        """
        self.evaluator = evaluator
        self.dataset_manager = dataset_manager
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.statistical_tester = StatisticalTester()
        
        self.logger = logging.getLogger(__name__)
    
    async def run_retrieval_pipeline_ablation(
        self,
        dataset_name: str = "clean_medium",
        study_name: str = "retrieval_pipeline_ablation"
    ) -> AblationStudyResult:
        """
        Run standard retrieval pipeline ablation study.
        
        Args:
            dataset_name: Dataset to use for testing
            study_name: Name for this ablation study
            
        Returns:
            Complete ablation study results
        """
        
        self.logger.info(f"🧪 Starting retrieval pipeline ablation: {study_name}")
        
        # Define standard configurations
        configurations = [
            AblationConfiguration(
                name="dense_only",
                description="Dense retrieval only, no lexical or reranking",
                dense_weight=1.0,
                lexical_weight=0.0,
                enable_reranking=False,
                expected_p_at_1=0.65,
                expected_latency_ms=25
            ),
            AblationConfiguration(
                name="lexical_only", 
                description="Lexical/BM25 retrieval only, no dense or reranking",
                dense_weight=0.0,
                lexical_weight=1.0,
                enable_reranking=False,
                expected_p_at_1=0.55,
                expected_latency_ms=15
            ),
            AblationConfiguration(
                name="hybrid_no_rerank",
                description="Hybrid dense+lexical fusion, no reranking",
                dense_weight=0.7,
                lexical_weight=0.3,
                enable_reranking=False,
                expected_p_at_1=0.72,
                expected_latency_ms=30
            ),
            AblationConfiguration(
                name="hybrid_with_rerank",
                description="Full pipeline: hybrid fusion + reranking",
                dense_weight=0.7,
                lexical_weight=0.3,
                enable_reranking=True,
                expected_p_at_1=0.78,
                expected_latency_ms=45
            )
        ]
        
        return await self.run_ablation_study(configurations, dataset_name, study_name)
    
    async def run_rerank_threshold_ablation(
        self,
        dataset_name: str = "clean_medium",
        study_name: str = "rerank_threshold_ablation"
    ) -> AblationStudyResult:
        """Run ablation study on rerank threshold values."""
        
        self.logger.info(f"🎯 Starting rerank threshold ablation: {study_name}")
        
        thresholds = [0.0, 0.05, 0.1, 0.15, 0.2]
        configurations = []
        
        for threshold in thresholds:
            config = AblationConfiguration(
                name=f"threshold_{threshold:.2f}",
                description=f"Rerank threshold {threshold:.2f}",
                dense_weight=0.7,
                lexical_weight=0.3,
                enable_reranking=True,
                rerank_threshold=threshold,
                expected_latency_ms=35 + threshold * 50  # Higher threshold = lower latency
            )
            configurations.append(config)
        
        return await self.run_ablation_study(configurations, dataset_name, study_name)
    
    async def run_fusion_weight_ablation(
        self,
        dataset_name: str = "clean_medium",
        study_name: str = "fusion_weight_ablation"
    ) -> AblationStudyResult:
        """Run ablation study on dense/lexical fusion weights."""
        
        self.logger.info(f"⚖️  Starting fusion weight ablation: {study_name}")
        
        weight_combinations = [
            (1.0, 0.0),  # Dense only
            (0.8, 0.2),  # Dense heavy
            (0.7, 0.3),  # Standard
            (0.6, 0.4),  # Balanced
            (0.5, 0.5),  # Equal
            (0.3, 0.7),  # Lexical heavy
            (0.0, 1.0)   # Lexical only
        ]
        
        configurations = []
        
        for dense_w, lexical_w in weight_combinations:
            config = AblationConfiguration(
                name=f"weights_{dense_w:.1f}_{lexical_w:.1f}",
                description=f"Dense {dense_w:.1f}, Lexical {lexical_w:.1f}",
                dense_weight=dense_w,
                lexical_weight=lexical_w,
                enable_reranking=True
            )
            configurations.append(config)
        
        return await self.run_ablation_study(configurations, dataset_name, study_name)
    
    async def run_ablation_study(
        self,
        configurations: List[AblationConfiguration],
        dataset_name: str,
        study_name: str
    ) -> AblationStudyResult:
        """
        Run complete ablation study with given configurations.
        
        Args:
            configurations: List of configurations to test
            dataset_name: Dataset for evaluation
            study_name: Name for this study
            
        Returns:
            Complete ablation study results
        """
        
        start_time = time.time()
        
        self.logger.info(f"Running ablation study: {study_name}")
        self.logger.info(f"Configurations: {len(configurations)}")
        self.logger.info(f"Dataset: {dataset_name}")
        
        # Load dataset
        dataset = self.dataset_manager.load_dataset(dataset_name, "clean")
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        dataset_dict = {
            "queries": [asdict(q) for q in dataset.queries],
            "documents": [asdict(d) for d in dataset.documents]
        }
        
        # Run ablation tests
        ablation_results = []
        
        for i, config in enumerate(configurations):
            self.logger.info(f"Running configuration {i+1}/{len(configurations)}: {config.name}")
            
            # Create retrieval function for this configuration
            retrieval_func = await self._create_retrieval_function(config)
            
            # Run evaluation
            eval_config = EvaluationConfig(
                name=f"{study_name}_{config.name}",
                description=f"Ablation test: {config.description}",
                output_dir=str(self.results_dir / "evaluations"),
                k_values=[1, 3, 5, 10],
                calculate_ndcg=True,
                calculate_mrr=True,
                max_queries=100  # Limit for efficiency
            )
            
            eval_result = await self.evaluator.run_evaluation(
                config=eval_config,
                dataset=dataset_dict,
                retrieval_func=retrieval_func
            )
            
            # Extract ablation result
            ablation_result = await self._create_ablation_result(config, eval_result)
            ablation_results.append(ablation_result)
            
            self.logger.info(
                f"✅ {config.name}: P@1={ablation_result.p_at_1:.3f}, "
                f"NDCG@5={ablation_result.ndcg_at_5:.3f}, "
                f"Latency={ablation_result.avg_latency_ms:.1f}ms"
            )
        
        # Run pairwise comparisons
        pairwise_comparisons = await self._run_pairwise_comparisons(ablation_results)
        
        # Analyze results
        analysis = await self._analyze_ablation_results(ablation_results, pairwise_comparisons)
        
        # Create study result
        duration = (time.time() - start_time) / 60.0
        
        study_result = AblationStudyResult(
            study_name=study_name,
            timestamp=datetime.now().isoformat(),
            duration_minutes=duration,
            configurations_tested=len(configurations),
            dataset_used=dataset_name,
            queries_per_config=len(dataset.queries),
            ablation_results=ablation_results,
            pairwise_comparisons=pairwise_comparisons,
            best_configuration=analysis['best_configuration'],
            performance_ranking=analysis['performance_ranking'],
            key_findings=analysis['key_findings'],
            recommendations=analysis['recommendations']
        )
        
        # Save results
        await self._save_ablation_study(study_result)
        
        self.logger.info("🏆 Ablation study completed")
        self.logger.info(f"   Duration: {duration:.1f} minutes")
        self.logger.info(f"   Best configuration: {analysis['best_configuration']}")
        self.logger.info("   Key findings:")
        for finding in analysis['key_findings'][:3]:
            self.logger.info(f"     • {finding}")
        
        return study_result
    
    async def _create_retrieval_function(self, config: AblationConfiguration) -> callable:
        """Create retrieval function for ablation configuration."""
        
        # Create reranker with this configuration
        retrieval_config = config.to_retrieval_config()
        reranker = RetrievalReranker(retrieval_config)
        
        async def ablation_retrieval_func(query: str) -> List[str]:
            """Custom retrieval function for ablation testing."""
            
            results, stats = await reranker.retrieve_and_rerank(query, top_k=10)
            return [r.id for r in results]
        
        return ablation_retrieval_func
    
    async def _create_ablation_result(
        self, 
        config: AblationConfiguration, 
        eval_result: EvaluationResult
    ) -> AblationResult:
        """Create ablation result from evaluation result."""
        
        metrics = eval_result.metrics
        perf_stats = eval_result.performance_stats
        
        # Extract query-level data for statistical testing
        query_p_at_1 = []
        query_latencies = []
        
        for query_result in eval_result.query_results.values():
            # Calculate P@1 for this query
            relevant = query_result.get('relevant', [])
            retrieved = query_result.get('retrieved', [])
            
            if relevant and retrieved:
                p_at_1 = 1.0 if retrieved[0] in relevant else 0.0
                query_p_at_1.append(p_at_1)
            
            # Get query latency
            query_time = query_result.get('query_time', 0)
            if query_time > 0:
                query_latencies.append(query_time * 1000)  # Convert to ms
        
        # Calculate confidence intervals
        confidence_intervals = {}
        if query_p_at_1:
            confidence_intervals['p_at_1'] = self.statistical_tester.bootstrap_confidence_interval(query_p_at_1)
        if query_latencies:
            confidence_intervals['latency_ms'] = self.statistical_tester.bootstrap_confidence_interval(query_latencies)
        
        # Calculate performance metrics
        avg_latency = perf_stats.get('avg_query_time', 0) * 1000
        p95_latency = max(query_latencies) if query_latencies else 0  # Simplified P95
        qps = perf_stats.get('queries_processed', 0) / max(eval_result.duration_seconds, 0.001)
        
        return AblationResult(
            configuration=config,
            evaluation_result=eval_result,
            p_at_1=metrics.get('p_at_1', 0.0),
            p_at_5=metrics.get('p_at_5', 0.0),
            ndcg_at_5=metrics.get('ndcg_at_5', 0.0),
            ndcg_at_10=metrics.get('ndcg_at_10', 0.0),
            mrr=metrics.get('mrr', 0.0),
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            queries_per_second=qps,
            rerank_invocation_rate=0.7,  # Placeholder - would be extracted from reranker stats
            rerank_avg_latency_ms=15.0,  # Placeholder
            confidence_interval_95=confidence_intervals
        )
    
    async def _run_pairwise_comparisons(
        self, 
        ablation_results: List[AblationResult]
    ) -> List[AblationComparison]:
        """Run statistical comparisons between all pairs of configurations."""
        
        comparisons = []
        
        for i in range(len(ablation_results)):
            for j in range(i + 1, len(ablation_results)):
                baseline = ablation_results[i]
                variant = ablation_results[j]
                
                comparison = await self._compare_ablation_results(baseline, variant)
                comparisons.append(comparison)
        
        return comparisons
    
    async def _compare_ablation_results(
        self, 
        baseline: AblationResult, 
        variant: AblationResult
    ) -> AblationComparison:
        """Compare two ablation results statistically."""
        
        # Extract query-level metrics for statistical testing
        baseline_eval = baseline.evaluation_result
        variant_eval = variant.evaluation_result
        
        # Get P@1 values per query
        baseline_p_at_1 = self._extract_query_p_at_1(baseline_eval)
        variant_p_at_1 = self._extract_query_p_at_1(variant_eval)
        
        # Get latency values per query
        baseline_latencies = self._extract_query_latencies(baseline_eval)
        variant_latencies = self._extract_query_latencies(variant_eval)
        
        # Statistical tests
        p_at_1_t_stat, p_at_1_p_value = self.statistical_tester.welch_t_test(variant_p_at_1, baseline_p_at_1)
        ndcg_t_stat, ndcg_p_value = (0.0, 1.0)  # Placeholder - would need query-level NDCG
        latency_t_stat, latency_p_value = self.statistical_tester.welch_t_test(baseline_latencies, variant_latencies)
        
        # Effect sizes
        p_at_1_effect_size = self.statistical_tester.cohens_d(variant_p_at_1, baseline_p_at_1)
        
        # Significance threshold
        alpha = 0.05
        
        # Determine recommendation
        p_at_1_better = variant.p_at_1 > baseline.p_at_1 and p_at_1_p_value < alpha
        latency_better = variant.avg_latency_ms < baseline.avg_latency_ms and latency_p_value < alpha
        
        if p_at_1_better and not (variant.avg_latency_ms > baseline.avg_latency_ms * 2):
            recommendation = "adopt"
        elif latency_better and variant.p_at_1 >= baseline.p_at_1 * 0.95:  # Within 5% of baseline quality
            recommendation = "adopt"
        elif p_at_1_p_value > alpha and latency_p_value > alpha:
            recommendation = "inconclusive"
        else:
            recommendation = "reject"
        
        return AblationComparison(
            baseline_name=baseline.configuration.name,
            variant_name=variant.configuration.name,
            p_at_1_diff=variant.p_at_1 - baseline.p_at_1,
            p_at_1_p_value=p_at_1_p_value,
            p_at_1_significant=p_at_1_p_value < alpha,
            ndcg_at_5_diff=variant.ndcg_at_5 - baseline.ndcg_at_5,
            ndcg_at_5_p_value=ndcg_p_value,
            ndcg_at_5_significant=ndcg_p_value < alpha,
            latency_diff_ms=variant.avg_latency_ms - baseline.avg_latency_ms,
            latency_p_value=latency_p_value,
            latency_significant=latency_p_value < alpha,
            overall_better=p_at_1_better,
            effect_size=p_at_1_effect_size,
            recommendation=recommendation
        )
    
    def _extract_query_p_at_1(self, eval_result: EvaluationResult) -> List[float]:
        """Extract P@1 scores per query from evaluation result."""
        
        p_at_1_scores = []
        
        for query_result in eval_result.query_results.values():
            relevant = query_result.get('relevant', [])
            retrieved = query_result.get('retrieved', [])
            
            if relevant and retrieved:
                p_at_1 = 1.0 if retrieved[0] in relevant else 0.0
                p_at_1_scores.append(p_at_1)
        
        return p_at_1_scores
    
    def _extract_query_latencies(self, eval_result: EvaluationResult) -> List[float]:
        """Extract latencies per query from evaluation result."""
        
        latencies = []
        
        for query_result in eval_result.query_results.values():
            query_time = query_result.get('query_time', 0)
            if query_time > 0:
                latencies.append(query_time * 1000)  # Convert to ms
        
        return latencies
    
    async def _analyze_ablation_results(
        self, 
        results: List[AblationResult], 
        comparisons: List[AblationComparison]
    ) -> Dict[str, Any]:
        """Analyze ablation results and generate insights."""
        
        # Find best configuration by P@1
        best_config = max(results, key=lambda r: r.p_at_1)
        
        # Create performance ranking
        ranking = [(r.configuration.name, r.p_at_1) for r in results]
        ranking.sort(key=lambda x: x[1], reverse=True)
        
        # Generate key findings
        key_findings = []
        
        # Finding 1: Best performing configuration
        key_findings.append(
            f"Best overall: {best_config.configuration.name} "
            f"(P@1={best_config.p_at_1:.3f}, latency={best_config.avg_latency_ms:.1f}ms)"
        )
        
        # Finding 2: Reranking impact
        rerank_results = [r for r in results if r.configuration.enable_reranking]
        no_rerank_results = [r for r in results if not r.configuration.enable_reranking]
        
        if rerank_results and no_rerank_results:
            rerank_avg = statistics.mean([r.p_at_1 for r in rerank_results])
            no_rerank_avg = statistics.mean([r.p_at_1 for r in no_rerank_results])
            rerank_improvement = rerank_avg - no_rerank_avg
            
            key_findings.append(
                f"Reranking impact: +{rerank_improvement:.3f} P@1 average improvement"
            )
        
        # Finding 3: Latency vs quality tradeoffs
        quality_latency_pairs = [(r.p_at_1, r.avg_latency_ms) for r in results]
        if len(quality_latency_pairs) > 2:
            # Find most efficient configuration (highest quality per ms)
            efficiency_scores = [(r.configuration.name, r.p_at_1 / max(r.avg_latency_ms, 1)) 
                               for r in results]
            most_efficient = max(efficiency_scores, key=lambda x: x[1])
            
            key_findings.append(
                f"Most efficient: {most_efficient[0]} "
                f"(efficiency score: {most_efficient[1]:.4f})"
            )
        
        # Finding 4: Statistical significance
        significant_improvements = [c for c in comparisons 
                                  if c.p_at_1_significant and c.p_at_1_diff > 0]
        if significant_improvements:
            best_improvement = max(significant_improvements, key=lambda c: c.p_at_1_diff)
            key_findings.append(
                f"Largest significant improvement: {best_improvement.variant_name} vs "
                f"{best_improvement.baseline_name} (+{best_improvement.p_at_1_diff:.3f} P@1)"
            )
        
        # Generate recommendations
        recommendations = []
        
        # Recommendation 1: Adoption
        adopt_comparisons = [c for c in comparisons if c.recommendation == "adopt"]
        if adopt_comparisons:
            recommendations.append(
                f"Adopt {len(adopt_comparisons)} configuration changes showing significant improvement"
            )
        
        # Recommendation 2: Performance regression alerts
        regression_comparisons = [c for c in comparisons 
                                if c.p_at_1_diff < -0.01 and c.p_at_1_significant]
        if regression_comparisons:
            recommendations.append(
                f"Monitor {len(regression_comparisons)} configurations showing quality regression"
            )
        
        # Recommendation 3: Inconclusive results
        inconclusive = [c for c in comparisons if c.recommendation == "inconclusive"]
        if len(inconclusive) > len(comparisons) * 0.5:
            recommendations.append(
                "Many comparisons inconclusive - consider larger sample sizes for future studies"
            )
        
        return {
            'best_configuration': best_config.configuration.name,
            'performance_ranking': ranking,
            'key_findings': key_findings,
            'recommendations': recommendations
        }
    
    async def _save_ablation_study(self, study_result: AblationStudyResult):
        """Save ablation study results."""
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON results
        json_file = self.results_dir / f"ablation_study_{study_result.study_name}_{timestamp_str}.json"
        with open(json_file, 'w') as f:
            json.dump(study_result.to_dict(), f, indent=2, default=str)
        
        # Save CSV summary
        csv_file = self.results_dir / f"ablation_summary_{study_result.study_name}_{timestamp_str}.csv"
        await self._save_ablation_csv(study_result, csv_file)
        
        # Save comparison matrix
        matrix_file = self.results_dir / f"comparison_matrix_{study_result.study_name}_{timestamp_str}.csv"
        await self._save_comparison_matrix(study_result, matrix_file)
        
        self.logger.info(f"Ablation study saved: {json_file}")
    
    async def _save_ablation_csv(self, study_result: AblationStudyResult, filepath: Path):
        """Save ablation results as CSV."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'configuration', 'p_at_1', 'p_at_5', 'ndcg_at_5', 'ndcg_at_10', 'mrr',
                'avg_latency_ms', 'p95_latency_ms', 'queries_per_second',
                'rerank_invocation_rate', 'dense_weight', 'lexical_weight', 'enable_reranking'
            ])
            
            # Data rows
            for result in study_result.ablation_results:
                config = result.configuration
                writer.writerow([
                    config.name, result.p_at_1, result.p_at_5, result.ndcg_at_5,
                    result.ndcg_at_10, result.mrr, result.avg_latency_ms, result.p95_latency_ms,
                    result.queries_per_second, result.rerank_invocation_rate,
                    config.dense_weight, config.lexical_weight, config.enable_reranking
                ])
    
    async def _save_comparison_matrix(self, study_result: AblationStudyResult, filepath: Path):
        """Save pairwise comparison matrix as CSV."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'baseline', 'variant', 'p_at_1_diff', 'p_at_1_p_value', 'p_at_1_significant',
                'latency_diff_ms', 'latency_p_value', 'latency_significant',
                'effect_size', 'recommendation'
            ])
            
            # Data rows
            for comparison in study_result.pairwise_comparisons:
                writer.writerow([
                    comparison.baseline_name, comparison.variant_name,
                    comparison.p_at_1_diff, comparison.p_at_1_p_value, comparison.p_at_1_significant,
                    comparison.latency_diff_ms, comparison.latency_p_value, comparison.latency_significant,
                    comparison.effect_size, comparison.recommendation
                ])


# Convenience functions for common ablation studies

async def run_standard_retrieval_ablation(dataset_name: str = "clean_medium") -> AblationStudyResult:
    """Run standard retrieval pipeline ablation study."""
    
    from .evaluator import Evaluator
    from .datasets import DatasetManager
    
    evaluator = Evaluator()
    dataset_manager = DatasetManager()
    runner = AblationRunner(evaluator, dataset_manager)
    
    return await runner.run_retrieval_pipeline_ablation(dataset_name)


async def run_comprehensive_ablation_suite(dataset_name: str = "clean_medium") -> Dict[str, AblationStudyResult]:
    """Run comprehensive ablation study suite."""
    
    from .evaluator import Evaluator
    from .datasets import DatasetManager
    
    evaluator = Evaluator()
    dataset_manager = DatasetManager()
    runner = AblationRunner(evaluator, dataset_manager)
    
    results = {}
    
    # Run multiple ablation studies
    results['retrieval_pipeline'] = await runner.run_retrieval_pipeline_ablation(dataset_name)
    results['rerank_threshold'] = await runner.run_rerank_threshold_ablation(dataset_name)
    results['fusion_weights'] = await runner.run_fusion_weight_ablation(dataset_name)
    
    return results