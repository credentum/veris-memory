#!/usr/bin/env python3
"""
S3: Paraphrase Robustness Check

Tests semantic consistency across paraphrased queries to ensure
the system returns similar results for semantically equivalent questions.

This check validates:
- Semantic similarity across paraphrased queries
- Result consistency for equivalent questions
- Ranking stability for related queries
- Context retrieval robustness
- Query expansion effectiveness
- Embedding similarity validation
- Response quality consistency
"""

import asyncio
import math
import random
import statistics
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import aiohttp
import logging

from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig

logger = logging.getLogger(__name__)

# Constants for semantic analysis
JACCARD_WEIGHT = 0.7
PEARSON_WEIGHT = 0.3
RANDOM_RANGE_MIN = 0.1
RANDOM_RANGE_MAX = 0.9
MIN_CORRELATION_THRESHOLD = 0.6
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_VARIANCE_THRESHOLD = 0.3
SIMULATION_SAMPLE_SIZE = 20
EMBEDDING_SIMILARITY_THRESHOLD = 0.8


class ParaphraseRobustness(BaseCheck):
    """S3: Paraphrase robustness testing for semantic consistency."""
    
    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S3-paraphrase-robustness", "Paraphrase robustness for semantic consistency")
        self.service_url = config.get("veris_memory_url", "http://localhost:8000")
        self.timeout_seconds = config.get("s3_paraphrase_timeout_sec", 60)
        self.min_similarity_threshold = config.get("s3_min_similarity_threshold", 0.7)
        self.max_result_variance = config.get("s3_max_result_variance", 0.3)
        self.test_paraphrase_sets = config.get("s3_test_paraphrase_sets", self._get_default_paraphrase_sets())
        
    def _get_default_paraphrase_sets(self) -> List[Dict[str, Any]]:
        """Get default paraphrase test sets for semantic consistency testing."""
        return [
            {
                "topic": "system_configuration",
                "variations": [
                    "How do I configure the system?",
                    "What are the configuration steps?",
                    "How to set up the system configuration?",
                    "What is the process for configuring the system?",
                    "How can I configure this system?"
                ],
                "expected_similarity": EMBEDDING_SIMILARITY_THRESHOLD
            },
            {
                "topic": "database_connection",
                "variations": [
                    "How do I connect to the database?",
                    "What are the database connection steps?",
                    "How to establish a database connection?",
                    "What is the process for connecting to the database?",
                    "How can I connect to the DB?"
                ],
                "expected_similarity": 0.75
            },
            {
                "topic": "error_troubleshooting",
                "variations": [
                    "How do I fix this error?",
                    "What's the solution to this problem?",
                    "How to resolve this issue?",
                    "What steps should I take to fix this?",
                    "How can I troubleshoot this error?"
                ],
                "expected_similarity": 0.7
            },
            {
                "topic": "performance_optimization",
                "variations": [
                    "How can I improve performance?",
                    "What are ways to optimize speed?",
                    "How to make the system faster?",
                    "What performance improvements are available?",
                    "How do I optimize system performance?"
                ],
                "expected_similarity": 0.75
            },
            {
                "topic": "user_authentication",
                "variations": [
                    "How do users log in?",
                    "What is the authentication process?",
                    "How to authenticate users?",
                    "What are the login steps?",
                    "How does user authentication work?"
                ],
                "expected_similarity": EMBEDDING_SIMILARITY_THRESHOLD
            }
        ]
        
    async def run_check(self) -> CheckResult:
        """Execute comprehensive paraphrase robustness validation."""
        start_time = time.time()
        
        try:
            # Run all paraphrase robustness tests
            test_results = await asyncio.gather(
                self._test_semantic_similarity(),
                self._test_result_consistency(),
                self._test_ranking_stability(),
                self._test_context_retrieval_robustness(),
                self._test_query_expansion(),
                self._validate_embedding_similarity(),
                self._test_response_quality_consistency(),
                return_exceptions=True
            )
            
            # Analyze results
            semantic_issues = []
            passed_tests = []
            failed_tests = []
            
            test_names = [
                "semantic_similarity",
                "result_consistency",
                "ranking_stability",
                "context_retrieval_robustness",
                "query_expansion",
                "embedding_similarity",
                "response_quality_consistency"
            ]
            
            for i, result in enumerate(test_results):
                test_name = test_names[i]
                
                if isinstance(result, Exception):
                    failed_tests.append(test_name)
                    semantic_issues.append(f"{test_name}: {str(result)}")
                elif result.get("passed", False):
                    passed_tests.append(test_name)
                else:
                    failed_tests.append(test_name)
                    semantic_issues.append(f"{test_name}: {result.get('message', 'Unknown failure')}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine overall status
            if semantic_issues:
                status = "fail"
                message = f"Semantic consistency issues detected: {len(semantic_issues)} problems found"
            else:
                status = "pass"
                message = f"All paraphrase robustness checks passed: {len(passed_tests)} tests successful"
            
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status=status,
                latency_ms=latency_ms,
                message=message,
                details={
                    "total_tests": len(test_names),
                    "passed_tests": len(passed_tests),
                    "failed_tests": len(failed_tests),
                    "semantic_issues": semantic_issues,
                    "passed_test_names": passed_tests,
                    "failed_test_names": failed_tests,
                    "test_results": test_results,
                    "paraphrase_configuration": {
                        "min_similarity_threshold": self.min_similarity_threshold,
                        "max_result_variance": self.max_result_variance,
                        "test_sets_count": len(self.test_paraphrase_sets)
                    }
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status="fail",
                latency_ms=latency_ms,
                message=f"Paraphrase robustness check failed with error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _test_semantic_similarity(self) -> Dict[str, Any]:
        """Test semantic similarity across paraphrase sets."""
        try:
            similarity_results = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for paraphrase_set in self.test_paraphrase_sets:
                    topic = paraphrase_set["topic"]
                    variations = paraphrase_set["variations"]
                    expected_similarity = paraphrase_set.get("expected_similarity", self.min_similarity_threshold)
                    
                    # Get search results for each variation
                    search_results = []
                    for variation in variations:
                        try:
                            result = await self._search_contexts(session, variation)
                            search_results.append({
                                "query": variation,
                                "results": result.get("contexts", []),
                                "count": len(result.get("contexts", [])),
                                "error": result.get("error")
                            })
                        except Exception as e:
                            search_results.append({
                                "query": variation,
                                "results": [],
                                "count": 0,
                                "error": str(e)
                            })
                    
                    # Calculate similarity between result sets
                    similarity_scores = []
                    result_overlaps = []
                    
                    for i in range(len(search_results)):
                        for j in range(i + 1, len(search_results)):
                            result1 = search_results[i]
                            result2 = search_results[j]
                            
                            if result1["error"] or result2["error"]:
                                continue
                            
                            # Calculate result overlap (Jaccard similarity)
                            if result1["results"] and result2["results"]:
                                overlap = self._calculate_result_overlap(result1["results"], result2["results"])
                                similarity_scores.append(overlap)
                                result_overlaps.append({
                                    "query1": result1["query"],
                                    "query2": result2["query"],
                                    "overlap": overlap,
                                    "count1": result1["count"],
                                    "count2": result2["count"]
                                })
                    
                    avg_similarity = statistics.mean(similarity_scores) if similarity_scores else 0
                    min_similarity = min(similarity_scores) if similarity_scores else 0
                    
                    similarity_results.append({
                        "topic": topic,
                        "variations_tested": len(variations),
                        "successful_searches": len([r for r in search_results if not r["error"]]),
                        "average_similarity": avg_similarity,
                        "minimum_similarity": min_similarity,
                        "expected_similarity": expected_similarity,
                        "meets_threshold": avg_similarity >= expected_similarity,
                        "result_overlaps": result_overlaps[:3],  # Sample overlaps
                        "search_results_summary": [
                            {"query": r["query"], "count": r["count"], "has_error": bool(r["error"])}
                            for r in search_results
                        ]
                    })
            
            # Analyze overall similarity performance
            topics_tested = len(similarity_results)
            topics_passed = len([r for r in similarity_results if r["meets_threshold"]])
            overall_avg_similarity = statistics.mean([r["average_similarity"] for r in similarity_results]) if similarity_results else 0
            
            issues = []
            for result in similarity_results:
                if not result["meets_threshold"]:
                    issues.append(f"Topic '{result['topic']}': similarity {result['average_similarity']:.3f} below threshold {result['expected_similarity']}")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Semantic similarity test: {topics_passed}/{topics_tested} topics passed, avg similarity {overall_avg_similarity:.3f}" + (f", issues: {len(issues)}" if issues else ""),
                "topics_tested": topics_tested,
                "topics_passed": topics_passed,
                "overall_avg_similarity": overall_avg_similarity,
                "similarity_results": similarity_results,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Semantic similarity test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_result_consistency(self) -> Dict[str, Any]:
        """Test consistency of results across paraphrased queries."""
        try:
            consistency_results = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for paraphrase_set in self.test_paraphrase_sets[:3]:  # Test subset for performance
                    topic = paraphrase_set["topic"]
                    variations = paraphrase_set["variations"]
                    
                    # Get results for each variation
                    all_results = []
                    for variation in variations:
                        try:
                            result = await self._search_contexts(session, variation, limit=10)
                            if not result.get("error"):
                                all_results.append({
                                    "query": variation,
                                    "contexts": result.get("contexts", []),
                                    "scores": [ctx.get("score", 0) for ctx in result.get("contexts", [])]
                                })
                        except Exception as e:
                            logger.warning(f"Error searching for '{variation}': {e}")
                    
                    if len(all_results) < 2:
                        consistency_results.append({
                            "topic": topic,
                            "variations_tested": len(variations),
                            "successful_searches": len(all_results),
                            "consistency_score": 0,
                            "error": "Insufficient successful searches for consistency analysis"
                        })
                        continue
                    
                    # Calculate result consistency
                    consistency_scores = []
                    top_results_overlap = []
                    
                    for i in range(len(all_results)):
                        for j in range(i + 1, len(all_results)):
                            result1 = all_results[i]
                            result2 = all_results[j]
                            
                            # Compare top 5 results
                            top1 = result1["contexts"][:5]
                            top2 = result2["contexts"][:5]
                            
                            overlap = self._calculate_result_overlap(top1, top2)
                            consistency_scores.append(overlap)
                            
                            # Compare score distributions
                            scores1 = result1["scores"][:5]
                            scores2 = result2["scores"][:5]
                            
                            if scores1 and scores2:
                                score_correlation = self._calculate_score_correlation(scores1, scores2)
                                top_results_overlap.append({
                                    "query1": result1["query"],
                                    "query2": result2["query"],
                                    "overlap": overlap,
                                    "score_correlation": score_correlation
                                })
                    
                    avg_consistency = statistics.mean(consistency_scores) if consistency_scores else 0
                    min_consistency = min(consistency_scores) if consistency_scores else 0
                    
                    consistency_results.append({
                        "topic": topic,
                        "variations_tested": len(variations),
                        "successful_searches": len(all_results),
                        "average_consistency": avg_consistency,
                        "minimum_consistency": min_consistency,
                        "meets_threshold": avg_consistency >= self.min_similarity_threshold,
                        "top_results_analysis": top_results_overlap[:2]  # Sample
                    })
            
            # Overall consistency analysis
            topics_tested = len([r for r in consistency_results if "error" not in r])
            topics_passed = len([r for r in consistency_results if r.get("meets_threshold", False)])
            
            issues = []
            for result in consistency_results:
                if "error" in result:
                    issues.append(f"Topic '{result['topic']}': {result['error']}")
                elif not result.get("meets_threshold", False):
                    issues.append(f"Topic '{result['topic']}': consistency {result.get('average_consistency', 0):.3f} below threshold")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Result consistency test: {topics_passed}/{topics_tested} topics passed" + (f", issues: {len(issues)}" if issues else ""),
                "topics_tested": topics_tested,
                "topics_passed": topics_passed,
                "consistency_results": consistency_results,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Result consistency test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_ranking_stability(self) -> Dict[str, Any]:
        """Test ranking stability across similar queries."""
        try:
            ranking_results = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                # Test ranking stability by running the same query multiple times
                for paraphrase_set in self.test_paraphrase_sets[:2]:  # Test subset
                    topic = paraphrase_set["topic"]
                    base_query = paraphrase_set["variations"][0]
                    
                    # Run the same query multiple times to test ranking stability
                    multiple_runs = []
                    for run in range(3):
                        try:
                            result = await self._search_contexts(session, base_query, limit=10)
                            if not result.get("error"):
                                multiple_runs.append({
                                    "run": run + 1,
                                    "contexts": result.get("contexts", []),
                                    "context_ids": [ctx.get("id", f"ctx_{i}") for i, ctx in enumerate(result.get("contexts", []))]
                                })
                        except Exception as e:
                            logger.warning(f"Error in ranking stability run {run + 1}: {e}")
                    
                    if len(multiple_runs) < 2:
                        ranking_results.append({
                            "topic": topic,
                            "query": base_query,
                            "runs_completed": len(multiple_runs),
                            "ranking_stability": 0,
                            "error": "Insufficient runs for stability analysis"
                        })
                        continue
                    
                    # Calculate ranking stability
                    stability_scores = []
                    for i in range(len(multiple_runs)):
                        for j in range(i + 1, len(multiple_runs)):
                            run1 = multiple_runs[i]
                            run2 = multiple_runs[j]
                            
                            # Calculate rank correlation (Spearman-like)
                            stability = self._calculate_ranking_stability(run1["context_ids"], run2["context_ids"])
                            stability_scores.append(stability)
                    
                    avg_stability = statistics.mean(stability_scores) if stability_scores else 0
                    
                    ranking_results.append({
                        "topic": topic,
                        "query": base_query,
                        "runs_completed": len(multiple_runs),
                        "average_stability": avg_stability,
                        "meets_threshold": avg_stability >= self.min_similarity_threshold,
                        "stability_scores": stability_scores
                    })
            
            # Overall ranking stability analysis
            topics_tested = len([r for r in ranking_results if "error" not in r])
            topics_passed = len([r for r in ranking_results if r.get("meets_threshold", False)])
            
            issues = []
            for result in ranking_results:
                if "error" in result:
                    issues.append(f"Topic '{result['topic']}': {result['error']}")
                elif not result.get("meets_threshold", False):
                    issues.append(f"Topic '{result['topic']}': stability {result.get('average_stability', 0):.3f} below threshold")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Ranking stability test: {topics_passed}/{topics_tested} topics passed" + (f", issues: {len(issues)}" if issues else ""),
                "topics_tested": topics_tested,
                "topics_passed": topics_passed,
                "ranking_results": ranking_results,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Ranking stability test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_context_retrieval_robustness(self) -> Dict[str, Any]:
        """Test robustness of context retrieval across query variations."""
        try:
            retrieval_results = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for paraphrase_set in self.test_paraphrase_sets:
                    topic = paraphrase_set["topic"]
                    variations = paraphrase_set["variations"]
                    
                    retrieval_stats = []
                    for variation in variations:
                        try:
                            result = await self._search_contexts(session, variation)
                            if not result.get("error"):
                                contexts = result.get("contexts", [])
                                retrieval_stats.append({
                                    "query": variation,
                                    "count": len(contexts),
                                    "avg_score": statistics.mean([ctx.get("score", 0) for ctx in contexts]) if contexts else 0,
                                    "score_variance": statistics.variance([ctx.get("score", 0) for ctx in contexts]) if len(contexts) > 1 else 0
                                })
                        except Exception as e:
                            retrieval_stats.append({
                                "query": variation,
                                "count": 0,
                                "error": str(e)
                            })
                    
                    # Analyze retrieval robustness
                    successful_retrievals = [r for r in retrieval_stats if "error" not in r]
                    
                    if len(successful_retrievals) < 2:
                        retrieval_results.append({
                            "topic": topic,
                            "variations_tested": len(variations),
                            "successful_retrievals": len(successful_retrievals),
                            "robustness_score": 0,
                            "error": "Insufficient successful retrievals for analysis"
                        })
                        continue
                    
                    # Calculate retrieval consistency metrics
                    counts = [r["count"] for r in successful_retrievals]
                    scores = [r["avg_score"] for r in successful_retrievals]
                    
                    count_variance = statistics.variance(counts) if len(counts) > 1 else 0
                    score_variance = statistics.variance(scores) if len(scores) > 1 else 0
                    
                    # Robustness score based on low variance
                    max_acceptable_count_variance = (statistics.mean(counts) * self.max_result_variance) ** 2
                    max_acceptable_score_variance = (statistics.mean(scores) * self.max_result_variance) ** 2
                    
                    count_robustness = 1.0 - min(1.0, count_variance / max_acceptable_count_variance) if max_acceptable_count_variance > 0 else 1.0
                    score_robustness = 1.0 - min(1.0, score_variance / max_acceptable_score_variance) if max_acceptable_score_variance > 0 else 1.0
                    
                    overall_robustness = (count_robustness + score_robustness) / 2
                    
                    retrieval_results.append({
                        "topic": topic,
                        "variations_tested": len(variations),
                        "successful_retrievals": len(successful_retrievals),
                        "count_variance": count_variance,
                        "score_variance": score_variance,
                        "count_robustness": count_robustness,
                        "score_robustness": score_robustness,
                        "overall_robustness": overall_robustness,
                        "meets_threshold": overall_robustness >= self.min_similarity_threshold,
                        "retrieval_stats": successful_retrievals[:3]  # Sample
                    })
            
            # Overall robustness analysis
            topics_tested = len([r for r in retrieval_results if "error" not in r])
            topics_passed = len([r for r in retrieval_results if r.get("meets_threshold", False)])
            
            issues = []
            for result in retrieval_results:
                if "error" in result:
                    issues.append(f"Topic '{result['topic']}': {result['error']}")
                elif not result.get("meets_threshold", False):
                    issues.append(f"Topic '{result['topic']}': robustness {result.get('overall_robustness', 0):.3f} below threshold")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Context retrieval robustness test: {topics_passed}/{topics_tested} topics passed" + (f", issues: {len(issues)}" if issues else ""),
                "topics_tested": topics_tested,
                "topics_passed": topics_passed,
                "retrieval_results": retrieval_results,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Context retrieval robustness test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_query_expansion(self) -> Dict[str, Any]:
        """Test query expansion effectiveness."""
        try:
            # Test with simple vs expanded queries
            expansion_results = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                test_cases = [
                    {"simple": "config", "expanded": "configuration setup process"},
                    {"simple": "error", "expanded": "error troubleshooting resolution"},
                    {"simple": "database", "expanded": "database connection setup"}
                ]
                
                for test_case in test_cases:
                    simple_query = test_case["simple"]
                    expanded_query = test_case["expanded"]
                    
                    try:
                        # Get results for both queries
                        simple_result = await self._search_contexts(session, simple_query)
                        expanded_result = await self._search_contexts(session, expanded_query)
                        
                        if simple_result.get("error") or expanded_result.get("error"):
                            expansion_results.append({
                                "simple_query": simple_query,
                                "expanded_query": expanded_query,
                                "expansion_effective": False,
                                "error": "One or both queries failed"
                            })
                            continue
                        
                        simple_contexts = simple_result.get("contexts", [])
                        expanded_contexts = expanded_result.get("contexts", [])
                        
                        # Analyze expansion effectiveness
                        simple_count = len(simple_contexts)
                        expanded_count = len(expanded_contexts)
                        
                        # Check if expanded query provides more relevant results
                        expansion_effective = expanded_count > simple_count or (
                            expanded_count >= simple_count * EMBEDDING_SIMILARITY_THRESHOLD and
                            len(expanded_contexts) > 0 and
                            expanded_contexts[0].get("score", 0) >= simple_contexts[0].get("score", 0) if simple_contexts else True
                        )
                        
                        expansion_results.append({
                            "simple_query": simple_query,
                            "expanded_query": expanded_query,
                            "simple_count": simple_count,
                            "expanded_count": expanded_count,
                            "expansion_effective": expansion_effective,
                            "improvement_ratio": expanded_count / simple_count if simple_count > 0 else float('inf')
                        })
                        
                    except Exception as e:
                        expansion_results.append({
                            "simple_query": simple_query,
                            "expanded_query": expanded_query,
                            "expansion_effective": False,
                            "error": str(e)
                        })
            
            # Analyze overall expansion effectiveness
            total_tests = len(expansion_results)
            effective_expansions = len([r for r in expansion_results if r.get("expansion_effective", False)])
            
            issues = []
            for result in expansion_results:
                if "error" in result:
                    issues.append(f"Query '{result['simple_query']}': {result['error']}")
                elif not result.get("expansion_effective", False):
                    issues.append(f"Query '{result['simple_query']}': expansion not effective")
            
            return {
                "passed": effective_expansions >= total_tests * 0.7,  # 70% threshold
                "message": f"Query expansion test: {effective_expansions}/{total_tests} expansions effective" + (f", issues: {len(issues)}" if issues else ""),
                "total_tests": total_tests,
                "effective_expansions": effective_expansions,
                "effectiveness_rate": effective_expansions / total_tests if total_tests > 0 else 0,
                "expansion_results": expansion_results,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Query expansion test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _validate_embedding_similarity(self) -> Dict[str, Any]:
        """Validate embedding similarity for semantically related queries."""
        try:
            # This test simulates embedding similarity validation
            # In a real implementation, this would use the actual embedding service
            
            similarity_tests = []
            
            for paraphrase_set in self.test_paraphrase_sets[:3]:  # Test subset
                topic = paraphrase_set["topic"]
                variations = paraphrase_set["variations"]
                
                # Simulate embedding similarity calculation
                # In practice, this would call the embedding service
                simulated_similarities = []
                
                for i in range(len(variations)):
                    for j in range(i + 1, len(variations)):
                        # Simulate similarity based on string similarity and topic
                        sim_score = self._simulate_embedding_similarity(variations[i], variations[j])
                        simulated_similarities.append({
                            "query1": variations[i],
                            "query2": variations[j],
                            "similarity": sim_score
                        })
                
                avg_similarity = statistics.mean([s["similarity"] for s in simulated_similarities]) if simulated_similarities else 0
                min_similarity = min([s["similarity"] for s in simulated_similarities]) if simulated_similarities else 0
                
                similarity_tests.append({
                    "topic": topic,
                    "variations_count": len(variations),
                    "similarity_pairs": len(simulated_similarities),
                    "average_similarity": avg_similarity,
                    "minimum_similarity": min_similarity,
                    "meets_threshold": avg_similarity >= self.min_similarity_threshold,
                    "similarity_samples": simulated_similarities[:3]  # Sample
                })
            
            # Overall analysis
            topics_tested = len(similarity_tests)
            topics_passed = len([t for t in similarity_tests if t["meets_threshold"]])
            
            issues = []
            for test in similarity_tests:
                if not test["meets_threshold"]:
                    issues.append(f"Topic '{test['topic']}': avg similarity {test['average_similarity']:.3f} below threshold")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Embedding similarity validation: {topics_passed}/{topics_tested} topics passed" + (f", issues: {len(issues)}" if issues else ""),
                "topics_tested": topics_tested,
                "topics_passed": topics_passed,
                "similarity_tests": similarity_tests,
                "simulation_mode": True,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Embedding similarity validation failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_response_quality_consistency(self) -> Dict[str, Any]:
        """Test consistency of response quality across paraphrased queries."""
        try:
            quality_results = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for paraphrase_set in self.test_paraphrase_sets[:3]:  # Test subset
                    topic = paraphrase_set["topic"]
                    variations = paraphrase_set["variations"]
                    
                    quality_metrics = []
                    for variation in variations:
                        try:
                            result = await self._search_contexts(session, variation, limit=5)
                            if not result.get("error"):
                                contexts = result.get("contexts", [])
                                
                                # Calculate quality metrics
                                avg_score = statistics.mean([ctx.get("score", 0) for ctx in contexts]) if contexts else 0
                                score_variance = statistics.variance([ctx.get("score", 0) for ctx in contexts]) if len(contexts) > 1 else 0
                                
                                quality_metrics.append({
                                    "query": variation,
                                    "result_count": len(contexts),
                                    "average_score": avg_score,
                                    "score_variance": score_variance,
                                    "quality_score": avg_score * (1 - min(score_variance, 1.0))  # Penalize high variance
                                })
                        except Exception as e:
                            quality_metrics.append({
                                "query": variation,
                                "result_count": 0,
                                "error": str(e)
                            })
                    
                    # Analyze quality consistency
                    successful_queries = [m for m in quality_metrics if "error" not in m]
                    
                    if len(successful_queries) < 2:
                        quality_results.append({
                            "topic": topic,
                            "variations_tested": len(variations),
                            "successful_queries": len(successful_queries),
                            "quality_consistency": 0,
                            "error": "Insufficient successful queries for quality analysis"
                        })
                        continue
                    
                    quality_scores = [m["quality_score"] for m in successful_queries]
                    avg_quality = statistics.mean(quality_scores)
                    quality_variance = statistics.variance(quality_scores) if len(quality_scores) > 1 else 0
                    
                    # Quality consistency based on low variance
                    max_acceptable_variance = (avg_quality * self.max_result_variance) ** 2
                    consistency_score = 1.0 - min(1.0, quality_variance / max_acceptable_variance) if max_acceptable_variance > 0 else 1.0
                    
                    quality_results.append({
                        "topic": topic,
                        "variations_tested": len(variations),
                        "successful_queries": len(successful_queries),
                        "average_quality": avg_quality,
                        "quality_variance": quality_variance,
                        "quality_consistency": consistency_score,
                        "meets_threshold": consistency_score >= self.min_similarity_threshold,
                        "quality_samples": successful_queries[:3]  # Sample
                    })
            
            # Overall quality consistency analysis
            topics_tested = len([r for r in quality_results if "error" not in r])
            topics_passed = len([r for r in quality_results if r.get("meets_threshold", False)])
            
            issues = []
            for result in quality_results:
                if "error" in result:
                    issues.append(f"Topic '{result['topic']}': {result['error']}")
                elif not result.get("meets_threshold", False):
                    issues.append(f"Topic '{result['topic']}': quality consistency {result.get('quality_consistency', 0):.3f} below threshold")
            
            return {
                "passed": len(issues) == 0,
                "message": f"Response quality consistency test: {topics_passed}/{topics_tested} topics passed" + (f", issues: {len(issues)}" if issues else ""),
                "topics_tested": topics_tested,
                "topics_passed": topics_passed,
                "quality_results": quality_results,
                "issues": issues
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Response quality consistency test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _search_contexts(self, session: aiohttp.ClientSession, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for contexts using the service API."""
        try:
            search_url = f"{self.service_url}/api/v1/contexts/search"
            payload = {
                "query": query,
                "limit": limit,
                "include_metadata": True
            }

            async with session.post(search_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    # Fixed: REST API returns "results" not "contexts" (PR #240)
                    # Normalize response to always have "contexts" key for backward compatibility
                    if "results" in data and "contexts" not in data:
                        data["contexts"] = data["results"]
                    return data
                else:
                    return {"error": f"HTTP {response.status}", "contexts": []}

        except Exception as e:
            return {"error": str(e), "contexts": []}
    
    def _calculate_result_overlap(self, results1: List[Dict], results2: List[Dict]) -> float:
        """Calculate overlap between two result sets using Jaccard similarity."""
        if not results1 or not results2:
            return 0.0
        
        # Extract identifiers or content for comparison
        set1 = set()
        set2 = set()
        
        for result in results1:
            # Use content hash or ID for comparison
            identifier = result.get("id", hash(str(result.get("content", ""))))
            set1.add(identifier)
        
        for result in results2:
            identifier = result.get("id", hash(str(result.get("content", ""))))
            set2.add(identifier)
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_score_correlation(self, scores1: List[float], scores2: List[float]) -> float:
        """Calculate correlation between two score lists."""
        if len(scores1) != len(scores2) or len(scores1) < 2:
            return 0.0
        
        # Simple Pearson correlation coefficient
        mean1 = statistics.mean(scores1)
        mean2 = statistics.mean(scores2)
        
        numerator = sum((x - mean1) * (y - mean2) for x, y in zip(scores1, scores2))
        
        sum_sq1 = sum((x - mean1) ** 2 for x in scores1)
        sum_sq2 = sum((y - mean2) ** 2 for y in scores2)
        
        denominator = math.sqrt(sum_sq1 * sum_sq2)
        
        return numerator / denominator if denominator > 0 else 0.0
    
    def _calculate_ranking_stability(self, ranking1: List[str], ranking2: List[str]) -> float:
        """Calculate ranking stability between two rankings."""
        if not ranking1 or not ranking2:
            return 0.0
        
        # Calculate normalized rank correlation
        common_items = set(ranking1).intersection(set(ranking2))
        if len(common_items) < 2:
            return 0.0
        
        # Create rank mappings for common items
        rank_map1 = {item: i for i, item in enumerate(ranking1) if item in common_items}
        rank_map2 = {item: i for i, item in enumerate(ranking2) if item in common_items}
        
        if len(rank_map1) < 2:
            return 0.0
        
        # Calculate Spearman rank correlation
        ranks1 = [rank_map1[item] for item in common_items]
        ranks2 = [rank_map2[item] for item in common_items]
        
        return self._calculate_score_correlation(ranks1, ranks2)
    
    def _simulate_embedding_similarity(self, text1: str, text2: str) -> float:
        """Simulate embedding similarity between two texts."""
        # Simple similarity based on word overlap and length
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        jaccard_sim = intersection / union if union > 0 else 0.0
        
        # Add some randomness to simulate real embedding similarity
        base_similarity = jaccard_sim * JACCARD_WEIGHT + random.uniform(RANDOM_RANGE_MIN, PEARSON_WEIGHT)
        
        return min(1.0, max(0.0, base_similarity))