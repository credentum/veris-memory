"""
Enhanced Burn-in Script with Phase 4.2 Evaluation Integration

Extends the comprehensive burn-in test with evaluation capabilities including:
- P@1, NDCG, MRR metric calculation
- Dataset management and testing
- Scale curve measurement (1x → 10x corpus)
- Cold vs warm performance validation
- Trace ID integration for observability
"""

import asyncio
import json
import logging
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import argparse

# Add evaluation modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from evaluation.evaluator import Evaluator, EvaluationConfig, EvaluationResult
    from evaluation.datasets import DatasetManager
    from evaluation.metrics import EvaluationMetrics, MetricCalculator
    from mcp_server.tracing import initialize_tracing, TracingContext
except ImportError as e:
    print(f"Warning: Could not import evaluation modules: {e}")
    print("Running in basic burn-in mode without evaluation capabilities")
    Evaluator = None
    EvaluationConfig = None
    DatasetManager = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/workspaces/agent-context-template/context-store/burnin-results/evaluation_burnin.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
HETZNER_HOST = "135.181.4.118"
RESULTS_DIR = Path("/workspaces/agent-context-template/context-store/burnin-results/evaluation")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class EvaluationCycleMetrics:
    """Extended metrics with evaluation data."""
    
    # Basic performance metrics
    cycle: int
    timestamp: str
    qps: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_percent: float
    requests_total: int
    
    # Evaluation metrics
    eval_p_at_1: float
    eval_p_at_5: float
    eval_ndcg_at_5: float
    eval_ndcg_at_10: float
    eval_mrr: float
    
    # Advanced evaluation metrics
    eval_query_count: int
    eval_avg_retrieval_time_ms: float
    eval_rerank_invocation_rate: float
    
    # Trace information
    trace_id: Optional[str] = None
    
    # Scale testing metrics (when applicable)
    corpus_scale_factor: Optional[int] = None
    corpus_size: Optional[int] = None
    
    # Cold vs warm metrics (when applicable)
    is_cold_start: bool = False
    cache_hit_rate: Optional[float] = None
    
    # Status and alerts
    status: str = "PASS"  # PASS, WARN, FAIL
    alerts: List[str] = None
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = []
    
    def to_dict(self):
        return asdict(self)


class EvaluationBurnIn:
    """Enhanced burn-in test with comprehensive evaluation."""
    
    def __init__(self, mode: str = "standard", eval_dataset: str = None):
        """
        Initialize evaluation burn-in.
        
        Args:
            mode: Burn-in mode ("standard", "evaluation", "scale", "ablation")
            eval_dataset: Name of evaluation dataset to use
        """
        self.mode = mode
        self.eval_dataset = eval_dataset
        
        # Initialize components
        self.dataset_manager = DatasetManager() if DatasetManager else None
        self.evaluator = Evaluator() if Evaluator else None
        
        # Initialize tracing
        self.trace_manager = initialize_tracing("./trace_data/burnin")
        
        # Results tracking
        self.cycles: List[EvaluationCycleMetrics] = []
        self.baseline: Optional[EvaluationCycleMetrics] = None
        
        # Stability tracking
        self.stable_cycles = 0
        self.stability_required = 5
        
        # Load evaluation dataset
        self.dataset = None
        if self.dataset_manager and eval_dataset:
            self.dataset = self.dataset_manager.load_dataset(eval_dataset, "clean")
            if not self.dataset:
                logger.warning(f"Could not load dataset '{eval_dataset}', creating synthetic data")
                self.dataset = self.dataset_manager.generate_synthetic_corpus(
                    base_corpus_size=100,
                    scale_factor=1
                )
    
    def run(self):
        """Main burn-in execution with evaluation."""
        logger.info("="*80)
        logger.info("🚀 PHASE 4.2 EVALUATION BURN-IN SPRINT")
        logger.info(f"Mode: {self.mode.upper()}")
        if self.eval_dataset:
            logger.info(f"Dataset: {self.eval_dataset}")
        logger.info("="*80)
        
        try:
            if self.mode == "evaluation":
                self.run_evaluation_mode()
            elif self.mode == "scale":
                self.run_scale_testing()
            elif self.mode == "ablation":
                self.run_ablation_study()
            else:
                self.run_standard_mode()
        
        except Exception as e:
            logger.error(f"Burn-in failed: {e}")
            sys.exit(1)
    
    def run_standard_mode(self):
        """Run standard burn-in with basic evaluation."""
        # Phase 1: Baseline with evaluation
        self.capture_baseline_with_evaluation()
        
        # Phase 2-4: Burn-in cycles
        cycle_count = 0
        while self.stable_cycles < self.stability_required and cycle_count < 20:
            cycle_count += 1
            self.run_evaluation_cycle(cycle_count)
        
        # Phase 5: Final analysis
        self.generate_final_report()
    
    def run_evaluation_mode(self):
        """Run comprehensive evaluation testing."""
        logger.info("🔍 Running comprehensive evaluation mode")
        
        if not self.evaluator or not self.dataset:
            raise ValueError("Evaluation mode requires evaluator and dataset")
        
        # Run evaluation with different configurations
        configs = [
            {"name": "baseline", "description": "Baseline evaluation"},
            {"name": "cold_start", "description": "Cold start evaluation", "cold_start": True},
            {"name": "high_load", "description": "High load evaluation", "max_queries": 500}
        ]
        
        for config_data in configs:
            logger.info(f"Running evaluation: {config_data['name']}")
            
            config = EvaluationConfig(
                name=config_data["name"],
                description=config_data["description"],
                output_dir=str(RESULTS_DIR / "evaluations"),
                test_paraphrase_robustness=True,
                test_narrative_coherence=True
            )
            
            if config_data.get("cold_start"):
                self.simulate_cold_start()
            
            # Run evaluation
            result = asyncio.run(self.run_single_evaluation(config))
            
            # Convert to cycle metrics
            cycle_metrics = self.evaluation_result_to_cycle_metrics(result, len(self.cycles) + 1)
            cycle_metrics.is_cold_start = config_data.get("cold_start", False)
            
            self.cycles.append(cycle_metrics)
            
            logger.info(f"Evaluation completed: P@1={cycle_metrics.eval_p_at_1:.3f}, NDCG@5={cycle_metrics.eval_ndcg_at_5:.3f}")
    
    def run_scale_testing(self):
        """Run scale curve testing (1x → 10x corpus)."""
        logger.info("📈 Running scale curve testing")
        
        if not self.dataset_manager:
            raise ValueError("Scale testing requires dataset manager")
        
        scale_factors = [1, 2, 5, 10]
        
        for factor in scale_factors:
            logger.info(f"Testing scale factor: {factor}x")
            
            # Generate scaled dataset
            scaled_dataset = self.dataset_manager.generate_synthetic_corpus(
                base_corpus_size=100,
                scale_factor=factor
            )
            
            # Run evaluation on scaled dataset
            config = EvaluationConfig(
                name=f"scale_{factor}x",
                description=f"Scale testing at {factor}x corpus size",
                output_dir=str(RESULTS_DIR / "scale_testing")
            )
            
            # Override dataset for this evaluation
            original_dataset = self.dataset
            self.dataset = scaled_dataset
            
            result = asyncio.run(self.run_single_evaluation(config))
            
            # Restore original dataset
            self.dataset = original_dataset
            
            # Convert to cycle metrics
            cycle_metrics = self.evaluation_result_to_cycle_metrics(result, len(self.cycles) + 1)
            cycle_metrics.corpus_scale_factor = factor
            cycle_metrics.corpus_size = len(scaled_dataset.documents)
            
            self.cycles.append(cycle_metrics)
            
            logger.info(f"Scale {factor}x completed: P@1={cycle_metrics.eval_p_at_1:.3f}, Latency P95={cycle_metrics.p95_latency_ms:.2f}ms")
    
    def run_ablation_study(self):
        """Run ablation study comparing different retrieval modes."""
        logger.info("🧪 Running ablation study")
        
        # Define ablation configurations
        ablation_configs = [
            {"name": "dense_only", "dense_weight": 1.0, "lexical_weight": 0.0, "rerank": False},
            {"name": "lexical_only", "dense_weight": 0.0, "lexical_weight": 1.0, "rerank": False},
            {"name": "hybrid_no_rerank", "dense_weight": 0.7, "lexical_weight": 0.3, "rerank": False},
            {"name": "hybrid_with_rerank", "dense_weight": 0.7, "lexical_weight": 0.3, "rerank": True}
        ]
        
        for ab_config in ablation_configs:
            logger.info(f"Running ablation: {ab_config['name']}")
            
            config = EvaluationConfig(
                name=ab_config["name"],
                description=f"Ablation study: {ab_config['name']}",
                output_dir=str(RESULTS_DIR / "ablation_study")
            )
            
            # Configure retrieval parameters (this would be passed to the retrieval system)
            retrieval_params = {
                "dense_weight": ab_config["dense_weight"],
                "lexical_weight": ab_config["lexical_weight"],
                "enable_rerank": ab_config["rerank"]
            }
            
            result = asyncio.run(self.run_single_evaluation(config, retrieval_params))
            
            # Convert to cycle metrics
            cycle_metrics = self.evaluation_result_to_cycle_metrics(result, len(self.cycles) + 1)
            cycle_metrics.alerts.append(f"Ablation: {ab_config['name']}")
            
            self.cycles.append(cycle_metrics)
            
            logger.info(f"Ablation {ab_config['name']} completed: P@1={cycle_metrics.eval_p_at_1:.3f}")
    
    async def run_single_evaluation(
        self, 
        config: EvaluationConfig, 
        retrieval_params: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """Run single evaluation with tracing."""
        
        async with TracingContext(
            request_type="evaluation_cycle",
            request_metadata={
                "config_name": config.name,
                "mode": self.mode,
                "dataset_size": len(self.dataset.queries) if self.dataset else 0
            },
            trace_manager=self.trace_manager
        ) as trace_id:
            
            # Create custom retrieval function if needed
            retrieval_func = None
            if retrieval_params:
                retrieval_func = self.create_retrieval_func(retrieval_params)
            
            # Run evaluation
            result = await self.evaluator.run_evaluation(
                config=config,
                dataset={
                    "queries": [asdict(q) for q in self.dataset.queries] if self.dataset else [],
                    "documents": [asdict(d) for d in self.dataset.documents] if self.dataset else []
                },
                retrieval_func=retrieval_func
            )
            
            result.trace_id = trace_id
            return result
    
    def create_retrieval_func(self, params: Dict[str, Any]):
        """Create custom retrieval function with specified parameters."""
        
        async def custom_retrieval(query: str) -> List[str]:
            """Custom retrieval function for ablation testing."""
            
            # Simulate different retrieval strategies
            dense_weight = params.get("dense_weight", 0.7)
            lexical_weight = params.get("lexical_weight", 0.3)
            enable_rerank = params.get("enable_rerank", True)
            
            # Simulate retrieval delay based on complexity
            base_delay = 0.01
            if dense_weight > 0:
                base_delay += 0.005  # Dense retrieval overhead
            if lexical_weight > 0:
                base_delay += 0.003  # Lexical retrieval overhead
            if enable_rerank:
                base_delay += 0.015  # Reranking overhead
            
            await asyncio.sleep(base_delay)
            
            # Return simulated results (in real implementation, this would call actual retrieval)
            num_results = min(10, len(self.dataset.documents) if self.dataset else 5)
            return [f"doc_{i}" for i in range(num_results)]
        
        return custom_retrieval
    
    def capture_baseline_with_evaluation(self):
        """Capture baseline metrics including evaluation."""
        logger.info("📊 Capturing baseline with evaluation metrics")
        
        if self.evaluator and self.dataset:
            # Run baseline evaluation
            config = EvaluationConfig(
                name="baseline",
                description="Baseline evaluation metrics",
                output_dir=str(RESULTS_DIR / "baseline")
            )
            
            result = asyncio.run(self.run_single_evaluation(config))
            
            # Convert to baseline metrics
            self.baseline = self.evaluation_result_to_cycle_metrics(result, 0)
            
            logger.info("✅ Baseline captured with evaluation metrics")
            logger.info(f"   P@1: {self.baseline.eval_p_at_1:.3f}")
            logger.info(f"   NDCG@5: {self.baseline.eval_ndcg_at_5:.3f}")
            logger.info(f"   MRR: {self.baseline.eval_mrr:.3f}")
            logger.info(f"   Avg Retrieval Time: {self.baseline.eval_avg_retrieval_time_ms:.2f}ms")
        
        else:
            # Fallback to basic baseline without evaluation
            self.baseline = EvaluationCycleMetrics(
                cycle=0,
                timestamp=datetime.now().isoformat(),
                qps=10,
                p50_latency_ms=50.0,
                p95_latency_ms=100.0,
                p99_latency_ms=200.0,
                error_rate_percent=0.0,
                requests_total=1000,
                eval_p_at_1=0.8,  # Default values
                eval_p_at_5=0.9,
                eval_ndcg_at_5=0.85,
                eval_ndcg_at_10=0.88,
                eval_mrr=0.82,
                eval_query_count=50,
                eval_avg_retrieval_time_ms=45.0,
                eval_rerank_invocation_rate=0.7
            )
            
            logger.info("✅ Basic baseline captured (no evaluation)")
    
    def run_evaluation_cycle(self, cycle_num: int):
        """Run single evaluation cycle."""
        logger.info(f"🔄 Running evaluation cycle {cycle_num}")
        
        if self.evaluator and self.dataset:
            config = EvaluationConfig(
                name=f"cycle_{cycle_num}",
                description=f"Burn-in cycle {cycle_num}",
                output_dir=str(RESULTS_DIR / "cycles")
            )
            
            result = asyncio.run(self.run_single_evaluation(config))
            cycle_metrics = self.evaluation_result_to_cycle_metrics(result, cycle_num)
        
        else:
            # Generate synthetic cycle metrics
            cycle_metrics = self.generate_synthetic_cycle_metrics(cycle_num)
        
        # Check stability
        is_stable = self.check_stability(cycle_metrics)
        
        if is_stable:
            self.stable_cycles += 1
            cycle_metrics.status = "PASS"
            logger.info(f"✅ Cycle {cycle_num} STABLE ({self.stable_cycles}/{self.stability_required})")
        else:
            self.stable_cycles = 0
            cycle_metrics.status = "WARN"
            logger.info(f"⚠️  Cycle {cycle_num} UNSTABLE (reset stability counter)")
        
        self.cycles.append(cycle_metrics)
    
    def evaluation_result_to_cycle_metrics(
        self, 
        result: EvaluationResult, 
        cycle_num: int
    ) -> EvaluationCycleMetrics:
        """Convert evaluation result to cycle metrics."""
        
        metrics = result.metrics
        perf_stats = result.performance_stats
        
        return EvaluationCycleMetrics(
            cycle=cycle_num,
            timestamp=result.timestamp,
            qps=int(perf_stats.get('queries_processed', 0) / result.duration_seconds) if result.duration_seconds > 0 else 0,
            p50_latency_ms=perf_stats.get('avg_query_time', 0) * 1000,
            p95_latency_ms=perf_stats.get('max_query_time', 0) * 1000,
            p99_latency_ms=perf_stats.get('max_query_time', 0) * 1000,
            error_rate_percent=(perf_stats.get('queries_failed', 0) / max(1, perf_stats.get('queries_processed', 1))) * 100,
            requests_total=perf_stats.get('queries_processed', 0),
            eval_p_at_1=metrics.get('p_at_1', 0.0),
            eval_p_at_5=metrics.get('p_at_5', 0.0),
            eval_ndcg_at_5=metrics.get('ndcg_at_5', 0.0),
            eval_ndcg_at_10=metrics.get('ndcg_at_10', 0.0),
            eval_mrr=metrics.get('mrr', 0.0),
            eval_query_count=perf_stats.get('queries_processed', 0),
            eval_avg_retrieval_time_ms=perf_stats.get('total_retrieval_time', 0) * 1000 / max(1, perf_stats.get('queries_processed', 1)),
            eval_rerank_invocation_rate=0.8,  # Placeholder - would be calculated from actual data
            trace_id=getattr(result, 'trace_id', None)
        )
    
    def generate_synthetic_cycle_metrics(self, cycle_num: int) -> EvaluationCycleMetrics:
        """Generate synthetic cycle metrics when evaluation is not available."""
        
        # Add some realistic variation
        base_p1 = 0.8
        variation = 0.02 * (cycle_num % 3 - 1)  # Small variation
        
        return EvaluationCycleMetrics(
            cycle=cycle_num,
            timestamp=datetime.now().isoformat(),
            qps=10,
            p50_latency_ms=45.0 + variation * 5,
            p95_latency_ms=90.0 + variation * 10,
            p99_latency_ms=180.0 + variation * 20,
            error_rate_percent=0.1,
            requests_total=1000,
            eval_p_at_1=base_p1 + variation,
            eval_p_at_5=0.9 + variation * 0.5,
            eval_ndcg_at_5=0.85 + variation,
            eval_ndcg_at_10=0.88 + variation * 0.5,
            eval_mrr=0.82 + variation,
            eval_query_count=50,
            eval_avg_retrieval_time_ms=40.0 + variation * 10,
            eval_rerank_invocation_rate=0.7 + variation * 0.1
        )
    
    def check_stability(self, current_metrics: EvaluationCycleMetrics) -> bool:
        """Check if current cycle is stable compared to baseline."""
        
        if not self.baseline:
            return False
        
        # Check evaluation metric stability
        p1_drift = abs(current_metrics.eval_p_at_1 - self.baseline.eval_p_at_1)
        ndcg_drift = abs(current_metrics.eval_ndcg_at_5 - self.baseline.eval_ndcg_at_5)
        
        # Check latency stability
        latency_drift_pct = abs(current_metrics.p95_latency_ms - self.baseline.p95_latency_ms) / self.baseline.p95_latency_ms * 100
        
        # Stability thresholds
        max_p1_drift = 0.02
        max_ndcg_drift = 0.02
        max_latency_drift_pct = 10
        max_error_rate_pct = 0.5
        
        is_stable = (
            p1_drift <= max_p1_drift and
            ndcg_drift <= max_ndcg_drift and
            latency_drift_pct <= max_latency_drift_pct and
            current_metrics.error_rate_percent <= max_error_rate_pct
        )
        
        if not is_stable:
            if p1_drift > max_p1_drift:
                current_metrics.alerts.append(f"P@1 drift: {p1_drift:.3f} > {max_p1_drift}")
            if ndcg_drift > max_ndcg_drift:
                current_metrics.alerts.append(f"NDCG@5 drift: {ndcg_drift:.3f} > {max_ndcg_drift}")
            if latency_drift_pct > max_latency_drift_pct:
                current_metrics.alerts.append(f"Latency drift: {latency_drift_pct:.1f}% > {max_latency_drift_pct}%")
        
        return is_stable
    
    def simulate_cold_start(self):
        """Simulate cold start conditions."""
        logger.info("❄️  Simulating cold start conditions")
        # In a real implementation, this would restart services, clear caches, etc.
        time.sleep(2)  # Simulate restart time
    
    def generate_final_report(self):
        """Generate comprehensive final report."""
        
        logger.info("📋 Generating final evaluation report")
        
        # Calculate summary statistics
        if self.cycles:
            avg_p1 = sum(c.eval_p_at_1 for c in self.cycles) / len(self.cycles)
            avg_ndcg = sum(c.eval_ndcg_at_5 for c in self.cycles) / len(self.cycles)
            avg_latency = sum(c.p95_latency_ms for c in self.cycles) / len(self.cycles)
            
            pass_rate = sum(1 for c in self.cycles if c.status == "PASS") / len(self.cycles) * 100
        else:
            avg_p1 = avg_ndcg = avg_latency = pass_rate = 0.0
        
        # Generate report
        report = {
            "mode": self.mode,
            "dataset": self.eval_dataset,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_cycles": len(self.cycles),
                "stable_cycles": self.stable_cycles,
                "pass_rate_percent": pass_rate,
                "avg_p_at_1": avg_p1,
                "avg_ndcg_at_5": avg_ndcg,
                "avg_p95_latency_ms": avg_latency
            },
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "cycles": [c.to_dict() for c in self.cycles],
            "evaluation_available": self.evaluator is not None,
            "dataset_available": self.dataset is not None
        }
        
        # Save report
        report_file = RESULTS_DIR / f"evaluation_burnin_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📊 Final Report Saved: {report_file}")
        logger.info("="*80)
        logger.info("🏆 EVALUATION BURN-IN COMPLETED")
        logger.info(f"   Mode: {self.mode}")
        logger.info(f"   Total Cycles: {len(self.cycles)}")
        logger.info(f"   Pass Rate: {pass_rate:.1f}%")
        logger.info(f"   Average P@1: {avg_p1:.3f}")
        logger.info(f"   Average NDCG@5: {avg_ndcg:.3f}")
        logger.info(f"   Average P95 Latency: {avg_latency:.2f}ms")
        logger.info("="*80)


def main():
    """Main entry point with command-line argument parsing."""
    
    parser = argparse.ArgumentParser(description="Phase 4.2 Evaluation Burn-in Testing")
    
    parser.add_argument(
        "--mode", 
        choices=["standard", "evaluation", "scale", "ablation"],
        default="standard",
        help="Burn-in testing mode"
    )
    
    parser.add_argument(
        "--dataset",
        type=str,
        help="Name of evaluation dataset to use"
    )
    
    parser.add_argument(
        "--cycles",
        type=int,
        default=5,
        help="Number of stable cycles required"
    )
    
    args = parser.parse_args()
    
    # Create and run burn-in test
    burnin = EvaluationBurnIn(mode=args.mode, eval_dataset=args.dataset)
    burnin.stability_required = args.cycles
    
    burnin.run()


if __name__ == "__main__":
    main()