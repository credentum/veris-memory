"""
Main Evaluation Orchestrator for Phase 4.2

Coordinates evaluation workflows including:
- Dataset loading and management
- Metric calculation across different test scenarios
- Integration with MCP server for retrieval testing
- Performance and scale testing coordination
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os

from .metrics import EvaluationMetrics, AdvancedMetrics, MetricCalculator

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """Configuration for evaluation runs."""
    
    # Basic settings
    name: str
    description: str
    output_dir: str
    
    # Metric settings
    k_values: List[int] = None
    calculate_ndcg: bool = True
    calculate_mrr: bool = True
    
    # Test settings
    max_queries: Optional[int] = None
    timeout_seconds: int = 30
    
    # Advanced evaluation settings
    test_paraphrase_robustness: bool = False
    test_narrative_coherence: bool = False
    test_chunk_drift: bool = False
    
    def __post_init__(self):
        if self.k_values is None:
            self.k_values = [1, 3, 5, 10]


@dataclass
class EvaluationResult:
    """Results from an evaluation run."""
    
    config: EvaluationConfig
    timestamp: str
    duration_seconds: float
    
    # Core metrics
    metrics: Dict[str, float]
    
    # Per-query results
    query_results: Dict[str, Dict[str, Any]]
    
    # Performance metrics
    performance_stats: Dict[str, Any]
    
    # Advanced evaluation results
    advanced_results: Optional[Dict[str, Any]] = None
    
    # Error tracking
    errors: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class Evaluator:
    """Main evaluation orchestrator."""
    
    def __init__(self, mcp_client=None):
        """
        Initialize evaluator.
        
        Args:
            mcp_client: Optional MCP client for retrieval testing
        """
        self.mcp_client = mcp_client
        self.metric_calculator = MetricCalculator()
        self.logger = logging.getLogger(__name__)
        
    async def run_evaluation(
        self,
        config: EvaluationConfig,
        dataset: Dict[str, Any],
        retrieval_func: Optional[Callable] = None
    ) -> EvaluationResult:
        """
        Run complete evaluation workflow.
        
        Args:
            config: Evaluation configuration
            dataset: Evaluation dataset with queries and ground truth
            retrieval_func: Optional custom retrieval function
            
        Returns:
            Complete evaluation results
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        self.logger.info(f"Starting evaluation: {config.name}")
        self.logger.info(f"Dataset contains {len(dataset.get('queries', []))} queries")
        
        # Initialize results structure
        query_results = {}
        errors = []
        performance_stats = {
            'queries_processed': 0,
            'queries_failed': 0,
            'avg_query_time': 0.0,
            'total_retrieval_time': 0.0
        }
        
        # Use provided retrieval function or default MCP client
        if retrieval_func is None:
            retrieval_func = self._default_retrieval_func
        
        # Process queries
        queries = dataset.get('queries', [])
        if config.max_queries:
            queries = queries[:config.max_queries]
        
        query_times = []
        
        for i, query_data in enumerate(queries):
            query_id = query_data.get('id', f"query_{i}")
            query_text = query_data.get('query')
            ground_truth = query_data.get('relevant', [])
            relevance_scores = query_data.get('relevance_scores', {})
            
            if not query_text:
                self.logger.warning(f"Skipping query {query_id}: no query text")
                continue
            
            try:
                # Time the retrieval
                query_start = time.time()
                retrieved_results = await self._safe_retrieval(
                    retrieval_func, 
                    query_text, 
                    config.timeout_seconds
                )
                query_time = time.time() - query_start
                query_times.append(query_time)
                
                # Store results
                query_results[query_id] = {
                    'query': query_text,
                    'relevant': ground_truth,
                    'retrieved': retrieved_results,
                    'relevance_scores': relevance_scores,
                    'query_time': query_time
                }
                
                performance_stats['queries_processed'] += 1
                
            except Exception as e:
                self.logger.error(f"Error processing query {query_id}: {str(e)}")
                errors.append({
                    'query_id': query_id,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                performance_stats['queries_failed'] += 1
        
        # Calculate performance statistics
        if query_times:
            performance_stats['avg_query_time'] = sum(query_times) / len(query_times)
            performance_stats['total_retrieval_time'] = sum(query_times)
            performance_stats['min_query_time'] = min(query_times)
            performance_stats['max_query_time'] = max(query_times)
        
        # Calculate standard metrics
        metrics = {}
        if query_results:
            metrics = self.metric_calculator.calculate_standard_metrics(
                query_results, 
                config.k_values
            )
        
        # Run advanced evaluations if requested
        advanced_results = {}
        if config.test_paraphrase_robustness:
            advanced_results['paraphrase_robustness'] = await self._evaluate_paraphrase_robustness(
                dataset, retrieval_func
            )
        
        if config.test_narrative_coherence:
            advanced_results['narrative_coherence'] = await self._evaluate_narrative_coherence(
                dataset, retrieval_func
            )
        
        if config.test_chunk_drift:
            advanced_results['chunk_drift'] = await self._evaluate_chunk_drift(
                dataset, retrieval_func
            )
        
        # Create final result
        duration = time.time() - start_time
        result = EvaluationResult(
            config=config,
            timestamp=timestamp,
            duration_seconds=duration,
            metrics=metrics,
            query_results=query_results,
            performance_stats=performance_stats,
            advanced_results=advanced_results if advanced_results else None,
            errors=errors
        )
        
        # Save results
        await self._save_evaluation_result(result)
        
        self.logger.info(f"Evaluation completed in {duration:.2f} seconds")
        self.logger.info(f"Processed {performance_stats['queries_processed']} queries successfully")
        self.logger.info(f"Failed {performance_stats['queries_failed']} queries")
        
        if metrics:
            self.logger.info(f"P@1: {metrics.get('p_at_1', 0.0):.3f}")
            self.logger.info(f"NDCG@10: {metrics.get('ndcg_at_10', 0.0):.3f}")
            self.logger.info(f"MRR: {metrics.get('mrr', 0.0):.3f}")
        
        return result
    
    async def _safe_retrieval(
        self, 
        retrieval_func: Callable, 
        query: str, 
        timeout_seconds: int
    ) -> List[str]:
        """Safely execute retrieval with timeout."""
        try:
            # Wrap in timeout
            result = await asyncio.wait_for(
                retrieval_func(query), 
                timeout=timeout_seconds
            )
            
            # Ensure result is a list of document IDs
            if isinstance(result, dict):
                return result.get('documents', [])
            elif isinstance(result, list):
                return result
            else:
                return []
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Query timed out after {timeout_seconds}s: {query[:50]}...")
            return []
        except Exception as e:
            self.logger.error(f"Retrieval error: {str(e)}")
            raise
    
    async def _default_retrieval_func(self, query: str) -> List[str]:
        """Default retrieval function using MCP client."""
        if not self.mcp_client:
            raise ValueError("No MCP client provided and no custom retrieval function")
        
        # Call MCP server for retrieval
        response = await self.mcp_client.call_tool("retrieve_context", {
            "query": query,
            "limit": 10
        })
        
        # Extract document IDs from response
        if isinstance(response, dict) and 'results' in response:
            return [result.get('id') for result in response['results'] if result.get('id')]
        
        return []
    
    async def _evaluate_paraphrase_robustness(
        self, 
        dataset: Dict[str, Any], 
        retrieval_func: Callable
    ) -> Dict[str, Any]:
        """Evaluate robustness to paraphrased queries."""
        paraphrase_data = dataset.get('paraphrase_tests', [])
        if not paraphrase_data:
            return {}
        
        results = []
        for test_case in paraphrase_data:
            original_query = test_case.get('original_query')
            paraphrases = test_case.get('paraphrases', [])
            ground_truth = test_case.get('relevant', [])
            
            if original_query and paraphrases:
                para_result = AdvancedMetrics.para_at_1_hard(
                    original_query=original_query,
                    paraphrased_queries=paraphrases,
                    ground_truth=ground_truth,
                    retrieval_func=lambda q: asyncio.run(retrieval_func(q))
                )
                results.append(para_result)
        
        # Aggregate results
        if results:
            avg_para_score = sum(r['para_at_1_hard'] for r in results) / len(results)
            total_hard_cases = sum(r['hard_case_count'] for r in results)
            
            return {
                'avg_para_at_1_hard': avg_para_score,
                'total_hard_cases': total_hard_cases,
                'test_cases': len(results),
                'detailed_results': results
            }
        
        return {}
    
    async def _evaluate_narrative_coherence(
        self, 
        dataset: Dict[str, Any], 
        retrieval_func: Callable
    ) -> Dict[str, Any]:
        """Evaluate narrative retrieval coherence."""
        narrative_data = dataset.get('narrative_tests', [])
        if not narrative_data:
            return {}
        
        results = []
        for test_case in narrative_data:
            query = test_case.get('query')
            expected_narrative_id = test_case.get('narrative_id')
            
            if query and expected_narrative_id:
                # Retrieve with metadata
                retrieved = await retrieval_func(query)
                # TODO: Enhance retrieval to return chunk metadata
                
                coherence_result = AdvancedMetrics.narrative_coherence_score(
                    query=query,
                    retrieved_chunks=retrieved if isinstance(retrieved, list) else [],
                    expected_narrative_id=expected_narrative_id
                )
                results.append(coherence_result)
        
        # Aggregate results
        if results:
            avg_coherence = sum(r['narrative_coherence'] for r in results) / len(results)
            correct_narrative_rate = sum(r['correct_narrative_id'] for r in results) / len(results)
            
            return {
                'avg_narrative_coherence': avg_coherence,
                'correct_narrative_rate': correct_narrative_rate,
                'test_cases': len(results),
                'detailed_results': results
            }
        
        return {}
    
    async def _evaluate_chunk_drift(
        self, 
        dataset: Dict[str, Any], 
        retrieval_func: Callable
    ) -> Dict[str, Any]:
        """Evaluate robustness to chunk boundary variations."""
        # Implementation for ±100 token shift testing
        # This would require specialized test data with chunk variations
        return {
            'chunk_drift_tolerance': 0.0,  # Placeholder
            'test_cases': 0,
            'note': 'Chunk drift evaluation requires specialized test data'
        }
    
    async def _save_evaluation_result(self, result: EvaluationResult):
        """Save evaluation result to configured output directory."""
        output_dir = result.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp_str = result.timestamp.replace(':', '-').replace('.', '-')
        filename = f"evaluation_{result.config.name}_{timestamp_str}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Convert to serializable format
        result_dict = asdict(result)
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(result_dict, f, indent=2, default=str)
        
        self.logger.info(f"Evaluation results saved to {filepath}")
    
    def create_config(
        self, 
        name: str, 
        description: str = "", 
        **kwargs
    ) -> EvaluationConfig:
        """Create evaluation config with defaults."""
        return EvaluationConfig(
            name=name,
            description=description,
            output_dir=kwargs.get('output_dir', './eval_results'),
            **kwargs
        )


class BatchEvaluator:
    """Run multiple evaluations with different configurations."""
    
    def __init__(self, evaluator: Evaluator):
        self.evaluator = evaluator
        self.results = []
    
    async def run_ablation_study(
        self,
        base_config: EvaluationConfig,
        dataset: Dict[str, Any],
        retrieval_configs: List[Dict[str, Any]]
    ) -> List[EvaluationResult]:
        """
        Run ablation study with different retrieval configurations.
        
        Args:
            base_config: Base evaluation configuration
            dataset: Evaluation dataset
            retrieval_configs: List of retrieval configuration variants
            
        Returns:
            List of evaluation results for each configuration
        """
        results = []
        
        for i, retrieval_config in enumerate(retrieval_configs):
            # Create variant config
            config = EvaluationConfig(
                name=f"{base_config.name}_variant_{i}",
                description=f"{base_config.description} - {retrieval_config.get('name', f'Variant {i}')}",
                output_dir=base_config.output_dir,
                k_values=base_config.k_values,
                calculate_ndcg=base_config.calculate_ndcg,
                calculate_mrr=base_config.calculate_mrr
            )
            
            # Create custom retrieval function for this variant
            retrieval_func = self._create_retrieval_func(retrieval_config)
            
            # Run evaluation
            result = await self.evaluator.run_evaluation(config, dataset, retrieval_func)
            results.append(result)
        
        self.results.extend(results)
        return results
    
    def _create_retrieval_func(self, config: Dict[str, Any]) -> Callable:
        """Create retrieval function based on configuration."""
        # This would create different retrieval functions based on config
        # e.g., dense-only, lexical-only, hybrid, etc.
        async def retrieval_func(query: str) -> List[str]:
            # Placeholder implementation
            return []
        
        return retrieval_func
    
    def compare_results(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Compare multiple evaluation results."""
        if not results:
            return {}
        
        comparison = {
            'configurations': [r.config.name for r in results],
            'metric_comparison': {},
            'performance_comparison': {}
        }
        
        # Compare metrics across configurations
        for metric in results[0].metrics.keys():
            comparison['metric_comparison'][metric] = [
                r.metrics.get(metric, 0.0) for r in results
            ]
        
        # Find best performing configuration for each metric
        for metric, values in comparison['metric_comparison'].items():
            best_idx = values.index(max(values))
            comparison['metric_comparison'][f'{metric}_best'] = results[best_idx].config.name
        
        return comparison