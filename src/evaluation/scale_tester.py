"""
Scale Testing Infrastructure for Phase 4.2

Implements comprehensive scale curve measurement from 1x → 10x corpus size including:
- Synthetic corpus expansion with domain-specific content
- P@1 and p95 latency tracking vs document count
- Performance degradation analysis and slope measurement
- Memory and resource usage monitoring
"""

import asyncio
import logging
import time
import psutil
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from .datasets import DatasetManager, EvaluationDataset
from .evaluator import Evaluator, EvaluationConfig
from .metrics import EvaluationMetrics

logger = logging.getLogger(__name__)


@dataclass
class ScalePoint:
    """Single data point in scale curve measurement."""
    
    scale_factor: int
    corpus_size: int
    query_count: int
    
    # Performance metrics
    p_at_1: float
    p_at_5: float
    ndcg_at_5: float
    ndcg_at_10: float
    mrr: float
    
    # Latency metrics
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_latency_ms: float
    
    # Throughput metrics
    queries_per_second: float
    
    # Resource usage
    memory_usage_mb: float
    cpu_usage_percent: float
    
    # Ingestion metrics
    ingest_time_seconds: float
    ingest_rate_docs_per_second: float
    
    # Quality metrics
    quality_score: float  # Combined metric
    degradation_from_baseline_percent: float
    
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScaleCurve:
    """Complete scale curve analysis results."""
    
    name: str
    description: str
    timestamp: str
    
    # Test parameters
    base_corpus_size: int
    scale_factors: List[int]
    topics: List[str]
    
    # Scale points
    points: List[ScalePoint]
    
    # Analysis results
    performance_slope: float  # P@1 degradation per 10x scale
    latency_slope: float     # P95 latency increase per 10x scale
    
    # Tolerance checks
    within_tolerance: bool
    tolerance_violations: List[str]
    
    # Recommendations
    recommended_max_scale: int
    scaling_bottlenecks: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'points': [point.to_dict() for point in self.points]
        }


class ScaleTester:
    """Implements scale curve testing from 1x to 10x corpus size."""
    
    def __init__(
        self, 
        dataset_manager: DatasetManager,
        evaluator: Evaluator,
        base_corpus_size: int = 1000,
        results_dir: str = "./scale_test_results"
    ):
        """
        Initialize scale tester.
        
        Args:
            dataset_manager: Dataset manager for corpus generation
            evaluator: Evaluator for running tests
            base_corpus_size: Base corpus size for 1x scale
            results_dir: Directory for storing results
        """
        self.dataset_manager = dataset_manager
        self.evaluator = evaluator
        self.base_corpus_size = base_corpus_size
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Performance tolerances
        self.max_p1_degradation_per_10x = 0.05  # 5% max degradation per 10x scale
        self.max_latency_increase_per_10x = 2.0   # 2x max latency increase per 10x scale
        
    async def run_scale_curve_test(
        self,
        scale_factors: List[int] = None,
        topics: List[str] = None,
        test_name: str = "scale_curve"
    ) -> ScaleCurve:
        """
        Run complete scale curve test across multiple scale factors.
        
        Args:
            scale_factors: List of scale factors to test (default: [1, 2, 5, 10])
            topics: List of topics for content generation
            test_name: Name for this test run
            
        Returns:
            Complete scale curve analysis
        """
        if scale_factors is None:
            scale_factors = [1, 2, 5, 10]
        
        if topics is None:
            topics = ['technology', 'science', 'business', 'health', 'education']
        
        self.logger.info(f"🚀 Starting scale curve test: {test_name}")
        self.logger.info(f"Scale factors: {scale_factors}")
        self.logger.info(f"Base corpus size: {self.base_corpus_size}")
        
        points = []
        baseline_point = None
        
        # Test each scale factor
        for i, factor in enumerate(scale_factors):
            self.logger.info(f"📊 Testing scale factor {factor}x ({i+1}/{len(scale_factors)})")
            
            point = await self.test_scale_point(factor, topics, test_name)
            points.append(point)
            
            if factor == 1:
                baseline_point = point
            
            self.logger.info(
                f"✅ Scale {factor}x: P@1={point.p_at_1:.3f}, "
                f"P95 latency={point.p95_latency_ms:.1f}ms, "
                f"QPS={point.queries_per_second:.1f}"
            )
            
            # Brief pause between tests
            await asyncio.sleep(2)
        
        # Analyze results
        curve = self.analyze_scale_curve(
            points=points,
            baseline_point=baseline_point,
            scale_factors=scale_factors,
            topics=topics,
            test_name=test_name
        )
        
        # Save results
        await self.save_scale_curve(curve)
        
        self.logger.info(f"📈 Scale curve test completed: {test_name}")
        self.logger.info(f"Performance slope: {curve.performance_slope:.4f} P@1 per 10x scale")
        self.logger.info(f"Latency slope: {curve.latency_slope:.2f}x per 10x scale")
        self.logger.info(f"Within tolerance: {curve.within_tolerance}")
        
        if curve.tolerance_violations:
            self.logger.warning("⚠️  Tolerance violations:")
            for violation in curve.tolerance_violations:
                self.logger.warning(f"   - {violation}")
        
        return curve
    
    async def test_scale_point(
        self,
        scale_factor: int,
        topics: List[str],
        test_name: str
    ) -> ScalePoint:
        """
        Test single scale point.
        
        Args:
            scale_factor: Scale multiplier (1x, 2x, 5x, 10x)
            topics: Content topics for generation
            test_name: Name of overall test
            
        Returns:
            Scale point results
        """
        corpus_size = self.base_corpus_size * scale_factor
        
        self.logger.info(f"Generating {corpus_size} documents ({scale_factor}x scale)")
        
        # Generate synthetic dataset
        generation_start = time.time()
        dataset = self.dataset_manager.generate_synthetic_corpus(
            base_corpus_size=self.base_corpus_size,
            scale_factor=scale_factor,
            topic_domains=topics
        )
        generation_time = time.time() - generation_start
        
        self.logger.info(f"Generated corpus in {generation_time:.1f}s")
        
        # Measure resource usage before test
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Configure evaluation
        config = EvaluationConfig(
            name=f"{test_name}_scale_{scale_factor}x",
            description=f"Scale test at {scale_factor}x corpus size",
            output_dir=str(self.results_dir / "evaluations"),
            k_values=[1, 5, 10],
            max_queries=min(100, len(dataset.queries))  # Limit queries for faster testing
        )
        
        # Run evaluation with timing
        eval_start = time.time()
        result = await self.evaluator.run_evaluation(
            config=config,
            dataset={
                "queries": [asdict(q) for q in dataset.queries],
                "documents": [asdict(d) for d in dataset.documents]
            }
        )
        eval_time = time.time() - eval_start
        
        # Measure resource usage after test
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        cpu_percent = process.cpu_percent()
        
        # Calculate metrics
        metrics = result.metrics
        perf_stats = result.performance_stats
        
        # Calculate latency percentiles from query times
        query_times = []
        for query_result in result.query_results.values():
            query_time_ms = query_result.get('query_time', 0) * 1000
            if query_time_ms > 0:
                query_times.append(query_time_ms)
        
        if query_times:
            query_times.sort()
            n = len(query_times)
            p50_latency = query_times[n // 2]
            p95_latency = query_times[int(n * 0.95)] if n >= 20 else query_times[-1]
            p99_latency = query_times[int(n * 0.99)] if n >= 100 else query_times[-1]
            avg_latency = sum(query_times) / len(query_times)
        else:
            p50_latency = p95_latency = p99_latency = avg_latency = 0.0
        
        # Calculate QPS
        queries_per_second = result.performance_stats.get('queries_processed', 0) / max(eval_time, 0.001)
        
        # Calculate quality score (weighted combination of metrics)
        quality_score = (
            0.4 * metrics.get('p_at_1', 0) +
            0.3 * metrics.get('ndcg_at_5', 0) +
            0.3 * metrics.get('mrr', 0)
        )
        
        # Calculate ingestion rate
        ingest_rate = corpus_size / max(generation_time, 0.001)
        
        return ScalePoint(
            scale_factor=scale_factor,
            corpus_size=corpus_size,
            query_count=len(dataset.queries),
            p_at_1=metrics.get('p_at_1', 0.0),
            p_at_5=metrics.get('p_at_5', 0.0),
            ndcg_at_5=metrics.get('ndcg_at_5', 0.0),
            ndcg_at_10=metrics.get('ndcg_at_10', 0.0),
            mrr=metrics.get('mrr', 0.0),
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            avg_latency_ms=avg_latency,
            queries_per_second=queries_per_second,
            memory_usage_mb=memory_after,
            cpu_usage_percent=cpu_percent,
            ingest_time_seconds=generation_time,
            ingest_rate_docs_per_second=ingest_rate,
            quality_score=quality_score,
            degradation_from_baseline_percent=0.0,  # Will be calculated later
            timestamp=datetime.now().isoformat()
        )
    
    def analyze_scale_curve(
        self,
        points: List[ScalePoint],
        baseline_point: Optional[ScalePoint],
        scale_factors: List[int],
        topics: List[str],
        test_name: str
    ) -> ScaleCurve:
        """
        Analyze scale curve results and calculate slopes and tolerances.
        
        Args:
            points: List of scale test points
            baseline_point: Baseline (1x) scale point
            scale_factors: Scale factors tested
            topics: Topics used for generation
            test_name: Name of test
            
        Returns:
            Complete scale curve analysis
        """
        if not points:
            raise ValueError("No scale points to analyze")
        
        # Calculate degradation from baseline
        if baseline_point:
            for point in points:
                if point.scale_factor != 1:
                    p1_degradation = (baseline_point.p_at_1 - point.p_at_1) / baseline_point.p_at_1 * 100
                    point.degradation_from_baseline_percent = p1_degradation
        
        # Calculate performance slope (P@1 change per 10x scale)
        performance_slope = self.calculate_performance_slope(points)
        
        # Calculate latency slope (latency multiplier per 10x scale)
        latency_slope = self.calculate_latency_slope(points)
        
        # Check tolerances
        tolerance_violations = []
        within_tolerance = True
        
        # Check performance degradation tolerance
        if abs(performance_slope) > self.max_p1_degradation_per_10x:
            violation = f"P@1 degradation {performance_slope:.4f} exceeds limit {self.max_p1_degradation_per_10x}"
            tolerance_violations.append(violation)
            within_tolerance = False
        
        # Check latency increase tolerance
        if latency_slope > self.max_latency_increase_per_10x:
            violation = f"Latency increase {latency_slope:.2f}x exceeds limit {self.max_latency_increase_per_10x}x"
            tolerance_violations.append(violation)
            within_tolerance = False
        
        # Check individual point tolerances
        for point in points:
            if point.scale_factor > 1 and point.degradation_from_baseline_percent > 20:  # 20% max degradation
                violation = f"Scale {point.scale_factor}x: {point.degradation_from_baseline_percent:.1f}% performance degradation"
                tolerance_violations.append(violation)
                within_tolerance = False
        
        # Determine recommended max scale
        recommended_max_scale = self.determine_max_scale(points)
        
        # Identify scaling bottlenecks
        scaling_bottlenecks = self.identify_bottlenecks(points)
        
        return ScaleCurve(
            name=test_name,
            description=f"Scale curve analysis from 1x to {max(scale_factors)}x corpus size",
            timestamp=datetime.now().isoformat(),
            base_corpus_size=self.base_corpus_size,
            scale_factors=scale_factors,
            topics=topics,
            points=points,
            performance_slope=performance_slope,
            latency_slope=latency_slope,
            within_tolerance=within_tolerance,
            tolerance_violations=tolerance_violations,
            recommended_max_scale=recommended_max_scale,
            scaling_bottlenecks=scaling_bottlenecks
        )
    
    def calculate_performance_slope(self, points: List[ScalePoint]) -> float:
        """Calculate P@1 degradation slope per 10x scale increase."""
        if len(points) < 2:
            return 0.0
        
        # Use linear regression on log scale
        import math
        
        x_values = [math.log10(point.scale_factor) for point in points]
        y_values = [point.p_at_1 for point in points]
        
        if len(set(x_values)) < 2:  # No variation in scale
            return 0.0
        
        # Simple linear regression
        n = len(points)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n
        
        numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator  # P@1 change per log10(scale) unit
        return slope  # This is per 10x scale change
    
    def calculate_latency_slope(self, points: List[ScalePoint]) -> float:
        """Calculate latency multiplier per 10x scale increase."""
        if len(points) < 2:
            return 1.0
        
        baseline_latency = points[0].p95_latency_ms
        if baseline_latency == 0:
            return 1.0
        
        # Find latency at maximum scale
        max_scale_point = max(points, key=lambda p: p.scale_factor)
        max_latency = max_scale_point.p95_latency_ms
        
        if max_latency == 0:
            return 1.0
        
        # Calculate multiplier per 10x scale
        import math
        scale_ratio = max_scale_point.scale_factor
        latency_ratio = max_latency / baseline_latency
        
        if scale_ratio <= 1:
            return 1.0
        
        # Convert to per-10x multiplier
        log_scale = math.log10(scale_ratio)
        multiplier_per_10x = latency_ratio ** (1.0 / log_scale) if log_scale > 0 else 1.0
        
        return multiplier_per_10x
    
    def determine_max_scale(self, points: List[ScalePoint]) -> int:
        """Determine recommended maximum scale based on performance."""
        max_acceptable_degradation = 15.0  # 15% max degradation
        max_acceptable_latency_ms = 1000.0   # 1 second max latency
        
        for point in sorted(points, key=lambda p: p.scale_factor, reverse=True):
            if (point.degradation_from_baseline_percent <= max_acceptable_degradation and
                point.p95_latency_ms <= max_acceptable_latency_ms):
                return point.scale_factor
        
        return 1  # Fallback to 1x if no scale meets criteria
    
    def identify_bottlenecks(self, points: List[ScalePoint]) -> List[str]:
        """Identify potential scaling bottlenecks."""
        bottlenecks = []
        
        if len(points) < 2:
            return bottlenecks
        
        # Check for memory usage growth
        memory_growth = (points[-1].memory_usage_mb - points[0].memory_usage_mb) / points[0].memory_usage_mb
        if memory_growth > 5.0:  # 500% memory increase
            bottlenecks.append("Memory usage scaling poorly")
        
        # Check for QPS degradation
        qps_degradation = (points[0].queries_per_second - points[-1].queries_per_second) / points[0].queries_per_second
        if qps_degradation > 0.5:  # 50% QPS decrease
            bottlenecks.append("Query throughput degradation")
        
        # Check for excessive latency growth
        latency_growth = points[-1].p95_latency_ms / points[0].p95_latency_ms
        if latency_growth > 3.0:  # 3x latency increase
            bottlenecks.append("Excessive latency growth")
        
        # Check for quality degradation
        quality_degradation = (points[0].quality_score - points[-1].quality_score) / points[0].quality_score
        if quality_degradation > 0.1:  # 10% quality decrease
            bottlenecks.append("Retrieval quality degradation")
        
        return bottlenecks
    
    async def save_scale_curve(self, curve: ScaleCurve):
        """Save scale curve results to file."""
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"scale_curve_{curve.name}_{timestamp_str}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(curve.to_dict(), f, indent=2)
        
        self.logger.info(f"Scale curve results saved: {filepath}")
        
        # Also save CSV for easy analysis
        csv_filename = f"scale_curve_{curve.name}_{timestamp_str}.csv"
        csv_filepath = self.results_dir / csv_filename
        
        await self.save_scale_curve_csv(curve, csv_filepath)
    
    async def save_scale_curve_csv(self, curve: ScaleCurve, filepath: Path):
        """Save scale curve as CSV for analysis."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'scale_factor', 'corpus_size', 'p_at_1', 'p_at_5', 'ndcg_at_5', 'ndcg_at_10', 'mrr',
                'p50_latency_ms', 'p95_latency_ms', 'p99_latency_ms', 'queries_per_second',
                'memory_usage_mb', 'quality_score', 'degradation_percent'
            ])
            
            # Data rows
            for point in curve.points:
                writer.writerow([
                    point.scale_factor, point.corpus_size, point.p_at_1, point.p_at_5,
                    point.ndcg_at_5, point.ndcg_at_10, point.mrr, point.p50_latency_ms,
                    point.p95_latency_ms, point.p99_latency_ms, point.queries_per_second,
                    point.memory_usage_mb, point.quality_score, point.degradation_from_baseline_percent
                ])
        
        self.logger.info(f"Scale curve CSV saved: {filepath}")


# Convenience functions for common scale testing scenarios

async def run_standard_scale_test(
    base_corpus_size: int = 1000,
    results_dir: str = "./scale_test_results"
) -> ScaleCurve:
    """Run standard 1x → 10x scale test."""
    dataset_manager = DatasetManager()
    evaluator = Evaluator()
    
    tester = ScaleTester(dataset_manager, evaluator, base_corpus_size, results_dir)
    
    return await tester.run_scale_curve_test(
        scale_factors=[1, 2, 5, 10],
        test_name="standard_scale_test"
    )


async def run_extended_scale_test(
    base_corpus_size: int = 1000,
    max_scale: int = 20,
    results_dir: str = "./scale_test_results"
) -> ScaleCurve:
    """Run extended scale test up to specified maximum."""
    dataset_manager = DatasetManager()
    evaluator = Evaluator()
    
    # Generate scale factors up to max_scale
    scale_factors = [1, 2, 5, 10]
    if max_scale > 10:
        scale_factors.extend([15, 20])
    
    tester = ScaleTester(dataset_manager, evaluator, base_corpus_size, results_dir)
    
    return await tester.run_scale_curve_test(
        scale_factors=scale_factors[:max_scale//5 + 1],
        test_name="extended_scale_test"
    )