#!/usr/bin/env python3
"""
S9: Graph Intent Validation Check

Validates that graph queries and relationships are correctly
interpreted and produce expected semantic intent and graph traversal results.

This check validates:
- Graph relationship accuracy and consistency
- Semantic intent preservation in graph queries
- Context connectivity validation
- Graph traversal result quality
- Relationship inference correctness
- Graph query optimization effectiveness
- Knowledge graph coherence testing
"""

import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import aiohttp
import logging

from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig

logger = logging.getLogger(__name__)


class GraphIntentValidation(BaseCheck):
    """S9: Graph intent validation for query correctness and relationship accuracy."""
    
    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S9-graph-intent", "Graph intent validation")
        self.veris_memory_url = config.get("veris_memory_url", "http://localhost:8000")
        self.timeout_seconds = config.get("s9_graph_timeout_sec", 45)
        self.max_traversal_depth = config.get("s9_max_traversal_depth", 3)
        self.graph_sample_size = config.get("s9_graph_sample_size", 15)
        
        # Graph intent test scenarios
        self.intent_scenarios = config.get("s9_intent_scenarios", self._get_default_intent_scenarios())
        
    def _get_default_intent_scenarios(self) -> List[Dict[str, Any]]:
        """Default graph intent test scenarios."""
        return [
            {
                "name": "context_relationship_accuracy",
                "description": "Test relationship accuracy between related contexts",
                "contexts": [
                    "Database configuration for PostgreSQL connection",
                    "Setting up PostgreSQL for production environment",
                    "PostgreSQL performance tuning and optimization"
                ],
                "expected_relationships": ["configuration", "database", "postgresql", "performance"]
            },
            {
                "name": "semantic_clustering_validation",
                "description": "Validate semantic clustering in graph relationships",
                "contexts": [
                    "User authentication implementation",
                    "JWT token validation process",
                    "Session management and security",
                    "OAuth2 integration setup"
                ],
                "expected_relationships": ["authentication", "security", "token", "session"]
            },
            {
                "name": "technical_concept_connectivity",
                "description": "Test connectivity between technical concepts",
                "contexts": [
                    "API rate limiting implementation",
                    "Redis caching for performance",
                    "Load balancing configuration",
                    "Performance monitoring setup"
                ],
                "expected_relationships": ["performance", "api", "caching", "monitoring"]
            },
            {
                "name": "workflow_sequence_validation",
                "description": "Validate workflow and process sequences",
                "contexts": [
                    "Initial project setup and configuration",
                    "Development environment setup",
                    "Testing framework implementation",
                    "Production deployment process"
                ],
                "expected_relationships": ["setup", "development", "testing", "deployment"]
            },
            {
                "name": "error_troubleshooting_connections",
                "description": "Test error handling and troubleshooting relationships",
                "contexts": [
                    "Database connection timeout errors",
                    "Network connectivity troubleshooting",
                    "Application error logging setup",
                    "System monitoring and alerting"
                ],
                "expected_relationships": ["error", "troubleshooting", "monitoring", "logging"]
            }
        ]
        
    async def run_check(self) -> CheckResult:
        """Execute comprehensive graph intent validation."""
        start_time = time.time()
        
        try:
            # Run all graph intent validation tests
            test_results = await asyncio.gather(
                self._test_relationship_accuracy(),
                self._validate_semantic_connectivity(),
                self._test_graph_traversal_quality(),
                self._validate_context_clustering(),
                self._test_relationship_inference(),
                self._validate_graph_coherence(),
                self._test_intent_preservation(),
                return_exceptions=True
            )
            
            # Analyze results
            graph_issues = []
            passed_tests = []
            failed_tests = []
            
            test_names = [
                "relationship_accuracy",
                "semantic_connectivity", 
                "graph_traversal_quality",
                "context_clustering",
                "relationship_inference",
                "graph_coherence",
                "intent_preservation"
            ]
            
            for i, result in enumerate(test_results):
                test_name = test_names[i]
                
                if isinstance(result, Exception):
                    failed_tests.append(test_name)
                    graph_issues.append(f"{test_name}: {str(result)}")
                elif result.get("passed", False):
                    passed_tests.append(test_name)
                else:
                    failed_tests.append(test_name)
                    graph_issues.append(f"{test_name}: {result.get('message', 'Unknown failure')}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine overall status
            if graph_issues:
                status = "fail"
                message = f"Graph intent validation issues detected: {len(graph_issues)} problems found"
            else:
                status = "pass"
                message = f"All graph intent validation checks passed: {len(passed_tests)} tests successful"
            
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
                    "graph_issues": graph_issues,
                    "passed_test_names": passed_tests,
                    "failed_test_names": failed_tests,
                    "test_results": test_results,
                    "graph_configuration": {
                        "max_traversal_depth": self.max_traversal_depth,
                        "graph_sample_size": self.graph_sample_size,
                        "intent_scenarios_count": len(self.intent_scenarios)
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
                message=f"Graph intent validation failed with error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _test_relationship_accuracy(self) -> Dict[str, Any]:
        """Test accuracy of relationships between contexts."""
        try:
            relationship_tests = []
            total_accuracy_score = 0.0
            
            for scenario in self.intent_scenarios:
                scenario_name = scenario["name"]
                contexts = scenario["contexts"]
                expected_relationships = scenario["expected_relationships"]
                
                # Store test contexts and get relationship analysis
                context_ids = []
                
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                ) as session:
                    
                    # Store contexts for relationship testing
                    for i, context_text in enumerate(contexts):
                        store_data = {
                            "context_type": "graph_intent_test",
                            "content": {
                                "text": context_text,
                                "scenario": scenario_name,
                                "index": i
                            },
                            "title": f"Graph Intent Test - {scenario_name} #{i+1}",
                            "metadata": {
                                "test_scenario": scenario_name,
                                "expected_relationships": expected_relationships,
                                "test_timestamp": datetime.utcnow().isoformat()
                            }
                        }
                        
                        try:
                            store_url = f"{self.veris_memory_url}/api/v1/contexts"
                            async with session.post(store_url, json=store_data) as response:
                                if response.status == 201:
                                    result_data = await response.json()
                                    context_ids.append(result_data.get("context_id"))
                                else:
                                    logger.warning(f"Failed to store context for scenario {scenario_name}")
                        except Exception as store_error:
                            logger.warning(f"Context storage error: {store_error}")
                    
                    # Allow time for graph processing
                    await asyncio.sleep(1)
                    
                    # Test relationship discovery between stored contexts
                    if len(context_ids) >= 2:
                        relationship_accuracy = await self._analyze_context_relationships(
                            session, context_ids, expected_relationships
                        )
                        
                        relationship_tests.append({
                            "scenario": scenario_name,
                            "context_count": len(context_ids),
                            "relationship_accuracy": relationship_accuracy,
                            "expected_relationships_found": relationship_accuracy > 0.6
                        })
                        
                        total_accuracy_score += relationship_accuracy
            
            avg_accuracy = total_accuracy_score / len(self.intent_scenarios) if self.intent_scenarios else 0.0
            accuracy_threshold = 0.7
            
            return {
                "passed": avg_accuracy >= accuracy_threshold,
                "message": f"Relationship accuracy: {avg_accuracy:.2f} (threshold: {accuracy_threshold})",
                "accuracy_score": avg_accuracy,
                "accuracy_threshold": accuracy_threshold,
                "scenario_results": relationship_tests,
                "scenarios_tested": len(relationship_tests)
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Relationship accuracy test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _analyze_context_relationships(
        self, 
        session: aiohttp.ClientSession, 
        context_ids: List[str], 
        expected_relationships: List[str]
    ) -> float:
        """Analyze relationships between contexts and calculate accuracy."""
        try:
            # Search for each context and analyze related contexts
            relationship_matches = 0
            total_relationships = 0
            
            for context_id in context_ids:
                # Get context details to use as search query
                get_url = f"{self.veris_memory_url}/api/v1/contexts/{context_id}"
                try:
                    async with session.get(get_url) as response:
                        if response.status == 200:
                            context_data = await response.json()
                            context_text = context_data.get("content", {}).get("text", "")
                            
                            # Search for related contexts
                            search_data = {
                                "query": context_text[:100],  # Use first 100 chars as query
                                "limit": 5
                            }
                            
                            search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                            async with session.post(search_url, json=search_data) as search_response:
                                if search_response.status == 200:
                                    search_results = await search_response.json()
                                    related_contexts = search_results.get("contexts", [])
                                    
                                    # Analyze if related contexts share expected relationship concepts
                                    for related_context in related_contexts:
                                        if related_context.get("context_id") != context_id:
                                            related_text = related_context.get("content", {}).get("text", "")
                                            
                                            # Check for expected relationship keywords
                                            for expected_rel in expected_relationships:
                                                if expected_rel.lower() in related_text.lower():
                                                    relationship_matches += 1
                                                total_relationships += 1
                except Exception as context_error:
                    logger.warning(f"Context relationship analysis error: {context_error}")
            
            return relationship_matches / total_relationships if total_relationships > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Relationship analysis failed: {e}")
            return 0.0
    
    async def _validate_semantic_connectivity(self) -> Dict[str, Any]:
        """Validate semantic connectivity in graph relationships."""
        try:
            connectivity_tests = []
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                # Test semantic connectivity with sample queries
                test_queries = [
                    "database configuration",
                    "user authentication", 
                    "error handling",
                    "performance optimization",
                    "security implementation"
                ]
                
                for query in test_queries:
                    search_data = {
                        "query": query,
                        "limit": 10
                    }
                    
                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    try:
                        async with session.post(search_url, json=search_data) as response:
                            if response.status == 200:
                                results = await response.json()
                                contexts = results.get("contexts", [])
                                
                                # Analyze semantic clustering in results
                                semantic_coherence = self._calculate_semantic_coherence(contexts, query)
                                
                                connectivity_tests.append({
                                    "query": query,
                                    "results_count": len(contexts),
                                    "semantic_coherence": semantic_coherence,
                                    "well_connected": semantic_coherence > 0.5
                                })
                    except Exception as query_error:
                        connectivity_tests.append({
                            "query": query,
                            "error": str(query_error),
                            "well_connected": False
                        })
            
            well_connected_queries = sum(1 for test in connectivity_tests if test.get("well_connected", False))
            connectivity_ratio = well_connected_queries / len(test_queries) if test_queries else 0.0
            connectivity_threshold = 0.6
            
            return {
                "passed": connectivity_ratio >= connectivity_threshold,
                "message": f"Semantic connectivity: {connectivity_ratio:.2f} (threshold: {connectivity_threshold})",
                "connectivity_ratio": connectivity_ratio,
                "connectivity_threshold": connectivity_threshold,
                "query_tests": connectivity_tests,
                "well_connected_queries": well_connected_queries
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Semantic connectivity validation failed: {str(e)}",
                "error": str(e)
            }
    
    def _calculate_semantic_coherence(self, contexts: List[Dict], query: str) -> float:
        """Calculate semantic coherence score for search results."""
        if not contexts:
            return 0.0
        
        query_terms = set(query.lower().split())
        coherence_scores = []
        
        for context in contexts:
            content_text = context.get("content", {}).get("text", "")
            content_terms = set(content_text.lower().split())
            
            # Calculate term overlap as a simple coherence metric
            overlap = len(query_terms.intersection(content_terms))
            coherence = overlap / len(query_terms) if query_terms else 0.0
            coherence_scores.append(coherence)
        
        return sum(coherence_scores) / len(coherence_scores)
    
    async def _test_graph_traversal_quality(self) -> Dict[str, Any]:
        """Test quality of graph traversal and path finding."""
        try:
            traversal_tests = []
            
            # Test traversal quality with different starting points
            test_concepts = [
                "database",
                "authentication", 
                "performance",
                "security",
                "monitoring"
            ]
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for concept in test_concepts:
                    traversal_quality = await self._analyze_traversal_paths(
                        session, concept, self.max_traversal_depth
                    )
                    
                    traversal_tests.append({
                        "concept": concept,
                        "traversal_quality": traversal_quality,
                        "paths_found": traversal_quality > 0.3
                    })
            
            successful_traversals = sum(1 for test in traversal_tests if test.get("paths_found", False))
            traversal_ratio = successful_traversals / len(test_concepts) if test_concepts else 0.0
            traversal_threshold = 0.6
            
            return {
                "passed": traversal_ratio >= traversal_threshold,
                "message": f"Graph traversal quality: {traversal_ratio:.2f} (threshold: {traversal_threshold})",
                "traversal_ratio": traversal_ratio,
                "traversal_threshold": traversal_threshold,
                "concept_tests": traversal_tests,
                "successful_traversals": successful_traversals
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Graph traversal quality test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _analyze_traversal_paths(
        self, 
        session: aiohttp.ClientSession, 
        start_concept: str, 
        max_depth: int
    ) -> float:
        """Analyze traversal paths from a starting concept."""
        try:
            # Search for contexts related to the starting concept
            search_data = {
                "query": start_concept,
                "limit": 5
            }
            
            search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
            async with session.post(search_url, json=search_data) as response:
                if response.status == 200:
                    results = await response.json()
                    initial_contexts = results.get("contexts", [])
                    
                    if not initial_contexts:
                        return 0.0
                    
                    # Use first context as starting point for traversal simulation
                    start_context = initial_contexts[0]
                    start_text = start_context.get("content", {}).get("text", "")
                    
                    # Simulate traversal by searching with related terms
                    path_quality_scores = []
                    
                    # Extract key terms for traversal
                    start_terms = [term for term in start_text.split() 
                                 if len(term) > 3 and term.lower() not in ['the', 'and', 'for', 'with']]
                    
                    for term in start_terms[:3]:  # Test traversal with first 3 key terms
                        term_search_data = {
                            "query": term,
                            "limit": 3
                        }
                        
                        async with session.post(search_url, json=term_search_data) as term_response:
                            if term_response.status == 200:
                                term_results = await term_response.json()
                                related_contexts = term_results.get("contexts", [])
                                
                                # Calculate path quality based on result relevance
                                relevance_scores = []
                                for context in related_contexts:
                                    context_text = context.get("content", {}).get("text", "")
                                    relevance = self._calculate_path_relevance(start_text, context_text)
                                    relevance_scores.append(relevance)
                                
                                if relevance_scores:
                                    path_quality_scores.append(sum(relevance_scores) / len(relevance_scores))
                    
                    return sum(path_quality_scores) / len(path_quality_scores) if path_quality_scores else 0.0
                else:
                    return 0.0
                    
        except Exception as e:
            logger.error(f"Traversal path analysis failed: {e}")
            return 0.0
    
    def _calculate_path_relevance(self, source_text: str, target_text: str) -> float:
        """Calculate relevance between two contexts for path quality."""
        source_terms = set(source_text.lower().split())
        target_terms = set(target_text.lower().split())
        
        if not source_terms or not target_terms:
            return 0.0
        
        intersection = source_terms.intersection(target_terms)
        union = source_terms.union(target_terms)
        
        return len(intersection) / len(union) if union else 0.0
    
    async def _validate_context_clustering(self) -> Dict[str, Any]:
        """Validate context clustering and grouping quality."""
        try:
            # Test clustering with diverse queries
            clustering_tests = []
            
            test_clusters = [
                {"theme": "database_operations", "query": "database setup configuration"},
                {"theme": "user_management", "query": "user authentication authorization"},
                {"theme": "system_monitoring", "query": "monitoring logging alerts"},
                {"theme": "api_development", "query": "REST API endpoints development"},
                {"theme": "deployment_processes", "query": "deployment production environment"}
            ]
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for cluster in test_clusters:
                    theme = cluster["theme"]
                    query = cluster["query"]
                    
                    search_data = {
                        "query": query,
                        "limit": 8
                    }
                    
                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    try:
                        async with session.post(search_url, json=search_data) as response:
                            if response.status == 200:
                                results = await response.json()
                                contexts = results.get("contexts", [])
                                
                                # Analyze clustering quality
                                cluster_coherence = self._analyze_cluster_coherence(contexts, query)
                                
                                clustering_tests.append({
                                    "theme": theme,
                                    "query": query,
                                    "results_count": len(contexts),
                                    "cluster_coherence": cluster_coherence,
                                    "well_clustered": cluster_coherence > 0.4
                                })
                    except Exception as cluster_error:
                        clustering_tests.append({
                            "theme": theme,
                            "query": query,
                            "error": str(cluster_error),
                            "well_clustered": False
                        })
            
            well_clustered_themes = sum(1 for test in clustering_tests if test.get("well_clustered", False))
            clustering_ratio = well_clustered_themes / len(test_clusters) if test_clusters else 0.0
            clustering_threshold = 0.6
            
            return {
                "passed": clustering_ratio >= clustering_threshold,
                "message": f"Context clustering quality: {clustering_ratio:.2f} (threshold: {clustering_threshold})",
                "clustering_ratio": clustering_ratio,
                "clustering_threshold": clustering_threshold,
                "cluster_tests": clustering_tests,
                "well_clustered_themes": well_clustered_themes
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Context clustering validation failed: {str(e)}",
                "error": str(e)
            }
    
    def _analyze_cluster_coherence(self, contexts: List[Dict], query: str) -> float:
        """Analyze coherence of contexts in a cluster."""
        if len(contexts) < 2:
            return 0.0
        
        query_terms = set(query.lower().split())
        coherence_scores = []
        
        # Calculate pairwise coherence between contexts
        for i in range(len(contexts)):
            for j in range(i + 1, len(contexts)):
                context_i_text = contexts[i].get("content", {}).get("text", "")
                context_j_text = contexts[j].get("content", {}).get("text", "")
                
                terms_i = set(context_i_text.lower().split())
                terms_j = set(context_j_text.lower().split())
                
                # Calculate similarity
                intersection = terms_i.intersection(terms_j)
                union = terms_i.union(terms_j)
                
                if union:
                    similarity = len(intersection) / len(union)
                    coherence_scores.append(similarity)
        
        return sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0
    
    async def _test_relationship_inference(self) -> Dict[str, Any]:
        """Test relationship inference capabilities."""
        try:
            # Test inference with implicit relationships
            inference_tests = []
            
            test_cases = [
                {
                    "primary_concept": "error handling",
                    "related_concepts": ["logging", "monitoring", "debugging"],
                    "expected_inference": "troubleshooting"
                },
                {
                    "primary_concept": "user authentication",
                    "related_concepts": ["password", "session", "security"],
                    "expected_inference": "authorization"
                },
                {
                    "primary_concept": "database optimization",
                    "related_concepts": ["indexing", "query", "performance"],
                    "expected_inference": "tuning"
                }
            ]
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for test_case in test_cases:
                    primary = test_case["primary_concept"]
                    related = test_case["related_concepts"]
                    expected = test_case["expected_inference"]
                    
                    # Search for primary concept
                    search_data = {
                        "query": primary,
                        "limit": 5
                    }
                    
                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    try:
                        async with session.post(search_url, json=search_data) as response:
                            if response.status == 200:
                                results = await response.json()
                                contexts = results.get("contexts", [])
                                
                                # Check if related concepts appear in results
                                inference_quality = self._evaluate_inference_quality(
                                    contexts, related, expected
                                )
                                
                                inference_tests.append({
                                    "primary_concept": primary,
                                    "related_concepts": related,
                                    "expected_inference": expected,
                                    "inference_quality": inference_quality,
                                    "inference_successful": inference_quality > 0.4
                                })
                    except Exception as inference_error:
                        inference_tests.append({
                            "primary_concept": primary,
                            "error": str(inference_error),
                            "inference_successful": False
                        })
            
            successful_inferences = sum(1 for test in inference_tests if test.get("inference_successful", False))
            inference_ratio = successful_inferences / len(test_cases) if test_cases else 0.0
            inference_threshold = 0.5
            
            return {
                "passed": inference_ratio >= inference_threshold,
                "message": f"Relationship inference: {inference_ratio:.2f} (threshold: {inference_threshold})",
                "inference_ratio": inference_ratio,
                "inference_threshold": inference_threshold,
                "inference_tests": inference_tests,
                "successful_inferences": successful_inferences
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Relationship inference test failed: {str(e)}",
                "error": str(e)
            }
    
    def _evaluate_inference_quality(
        self, 
        contexts: List[Dict], 
        related_concepts: List[str], 
        expected_inference: str
    ) -> float:
        """Evaluate quality of relationship inference."""
        if not contexts:
            return 0.0
        
        # Check if related concepts and expected inference appear in context texts
        all_text = " ".join([
            context.get("content", {}).get("text", "")
            for context in contexts
        ]).lower()
        
        related_found = sum(1 for concept in related_concepts if concept.lower() in all_text)
        inference_found = 1 if expected_inference.lower() in all_text else 0
        
        related_score = related_found / len(related_concepts) if related_concepts else 0.0
        inference_score = inference_found
        
        return (related_score + inference_score) / 2.0
    
    async def _validate_graph_coherence(self) -> Dict[str, Any]:
        """Validate overall graph coherence and consistency."""
        try:
            # Test graph coherence with cross-domain queries
            coherence_tests = []
            
            cross_domain_queries = [
                "database performance monitoring",
                "user authentication security logging",
                "API error handling troubleshooting",
                "deployment automation testing",
                "system configuration management"
            ]
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for query in cross_domain_queries:
                    search_data = {
                        "query": query,
                        "limit": 6
                    }
                    
                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    try:
                        async with session.post(search_url, json=search_data) as response:
                            if response.status == 200:
                                results = await response.json()
                                contexts = results.get("contexts", [])
                                
                                # Analyze cross-domain coherence
                                coherence_score = self._calculate_cross_domain_coherence(contexts, query)
                                
                                coherence_tests.append({
                                    "query": query,
                                    "results_count": len(contexts),
                                    "coherence_score": coherence_score,
                                    "coherent": coherence_score > 0.3
                                })
                    except Exception as coherence_error:
                        coherence_tests.append({
                            "query": query,
                            "error": str(coherence_error),
                            "coherent": False
                        })
            
            coherent_queries = sum(1 for test in coherence_tests if test.get("coherent", False))
            coherence_ratio = coherent_queries / len(cross_domain_queries) if cross_domain_queries else 0.0
            coherence_threshold = 0.6
            
            return {
                "passed": coherence_ratio >= coherence_threshold,
                "message": f"Graph coherence: {coherence_ratio:.2f} (threshold: {coherence_threshold})",
                "coherence_ratio": coherence_ratio,
                "coherence_threshold": coherence_threshold,
                "coherence_tests": coherence_tests,
                "coherent_queries": coherent_queries
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Graph coherence validation failed: {str(e)}",
                "error": str(e)
            }
    
    def _calculate_cross_domain_coherence(self, contexts: List[Dict], query: str) -> float:
        """Calculate coherence score for cross-domain query results."""
        if not contexts:
            return 0.0
        
        query_domains = query.lower().split()
        domain_coverage = []
        
        for context in contexts:
            context_text = context.get("content", {}).get("text", "").lower()
            
            # Check how many query domains are covered in this context
            covered_domains = sum(1 for domain in query_domains if domain in context_text)
            coverage_ratio = covered_domains / len(query_domains) if query_domains else 0.0
            domain_coverage.append(coverage_ratio)
        
        return sum(domain_coverage) / len(domain_coverage) if domain_coverage else 0.0
    
    async def _test_intent_preservation(self) -> Dict[str, Any]:
        """Test preservation of semantic intent in graph operations."""
        try:
            intent_tests = []
            
            # Test intent preservation with complex queries
            intent_scenarios = [
                {
                    "original_intent": "How to troubleshoot database connection issues",
                    "key_concepts": ["database", "connection", "troubleshoot"],
                    "expected_coverage": 0.7
                },
                {
                    "original_intent": "Best practices for secure user authentication",
                    "key_concepts": ["authentication", "security", "practices"],
                    "expected_coverage": 0.7
                },
                {
                    "original_intent": "Performance optimization strategies for web applications",
                    "key_concepts": ["performance", "optimization", "web"],
                    "expected_coverage": 0.7
                }
            ]
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for scenario in intent_scenarios:
                    intent = scenario["original_intent"]
                    key_concepts = scenario["key_concepts"]
                    expected_coverage = scenario["expected_coverage"]
                    
                    search_data = {
                        "query": intent,
                        "limit": 5
                    }
                    
                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    try:
                        async with session.post(search_url, json=search_data) as response:
                            if response.status == 200:
                                results = await response.json()
                                contexts = results.get("contexts", [])
                                
                                # Calculate intent preservation score
                                preservation_score = self._calculate_intent_preservation(
                                    contexts, key_concepts
                                )
                                
                                intent_tests.append({
                                    "original_intent": intent,
                                    "key_concepts": key_concepts,
                                    "preservation_score": preservation_score,
                                    "expected_coverage": expected_coverage,
                                    "intent_preserved": preservation_score >= expected_coverage
                                })
                    except Exception as intent_error:
                        intent_tests.append({
                            "original_intent": intent,
                            "error": str(intent_error),
                            "intent_preserved": False
                        })
            
            preserved_intents = sum(1 for test in intent_tests if test.get("intent_preserved", False))
            preservation_ratio = preserved_intents / len(intent_scenarios) if intent_scenarios else 0.0
            preservation_threshold = 0.6
            
            return {
                "passed": preservation_ratio >= preservation_threshold,
                "message": f"Intent preservation: {preservation_ratio:.2f} (threshold: {preservation_threshold})",
                "preservation_ratio": preservation_ratio,
                "preservation_threshold": preservation_threshold,
                "intent_tests": intent_tests,
                "preserved_intents": preserved_intents
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Intent preservation test failed: {str(e)}",
                "error": str(e)
            }
    
    def _calculate_intent_preservation(self, contexts: List[Dict], key_concepts: List[str]) -> float:
        """Calculate intent preservation score based on key concept coverage."""
        if not contexts or not key_concepts:
            return 0.0
        
        all_text = " ".join([
            context.get("content", {}).get("text", "")
            for context in contexts
        ]).lower()
        
        concepts_found = sum(1 for concept in key_concepts if concept.lower() in all_text)
        return concepts_found / len(key_concepts)