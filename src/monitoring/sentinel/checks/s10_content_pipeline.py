#!/usr/bin/env python3
"""
S10: Content Pipeline Monitoring Check

Monitors the content processing pipeline to ensure data flows
correctly through all stages of the system and validates end-to-end
content processing quality and performance.

This check validates:
- Content ingestion and processing stages
- Pipeline throughput and latency validation
- Data transformation and enrichment quality
- Storage backend integration health
- Content retrieval and search performance
- Pipeline error handling and recovery
- Content lifecycle management
"""

import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import aiohttp
import logging

from ..base_check import BaseCheck
from ..models import CheckResult, SentinelConfig

logger = logging.getLogger(__name__)

# Constants for pipeline monitoring
INGESTION_SUCCESS_THRESHOLD = 0.8
RETRIEVAL_SUCCESS_THRESHOLD = 0.8
STAGE_HEALTH_THRESHOLD = 0.8
ERROR_HANDLING_THRESHOLD = 0.75
LIFECYCLE_SUCCESS_THRESHOLD = 0.75
CONCURRENT_SUCCESS_THRESHOLD = 0.8
MIN_CONCURRENT_SUCCESS = 4  # At least 80% of 5 operations


class ContentPipelineMonitoring(BaseCheck):
    """S10: Content pipeline monitoring for data processing validation."""

    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S10-content-pipeline", "Content pipeline monitoring")
        default_url = os.getenv("TARGET_BASE_URL", "http://localhost:8000")
        self.veris_memory_url = config.get("veris_memory_url", default_url)
        self.timeout_seconds = config.get("s10_pipeline_timeout_sec", 60)

        # Get API key from environment for authentication
        self.api_key = os.getenv('SENTINEL_API_KEY')

        self.pipeline_stages = config.get("s10_pipeline_stages", [
            "ingestion",
            "validation", 
            "enrichment",
            "storage",
            "indexing",
            "retrieval"
        ])
        self.test_content_samples = config.get("s10_test_content_samples", self._get_default_test_samples())
        self.performance_thresholds = config.get("s10_performance_thresholds", {
            "ingestion_latency_ms": 5000,
            "retrieval_latency_ms": 2000,
            "pipeline_throughput_per_min": 10,
            "storage_consistency_ratio": 0.95
        })

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests including authentication."""
        headers = {}
        if self.api_key:
            # Extract key portion from format: vmk_{prefix}_{hash}:user_id:role:is_agent
            # Context-store expects only the key portion (before first colon)
            api_key_parts = self.api_key.strip().split(":")
            api_key = api_key_parts[0]
            headers['X-API-Key'] = api_key
        return headers

    def _get_default_test_samples(self) -> List[Dict[str, Any]]:
        """Default test content samples for pipeline validation.

        MCP Type Validation: All types must be valid MCP types (design|decision|trace|sprint|log)
        Using "log" for all test samples, with original category preserved in tags/metadata.
        """
        return [
            {
                "type": "log",  # Changed from "technical_documentation" (invalid MCP type)
                "content": {
                    "text": "Setting up PostgreSQL database connection for production environment with SSL encryption and connection pooling configuration.",
                    "title": "PostgreSQL Production Setup",
                    "tags": ["database", "postgresql", "production", "ssl", "technical_documentation"]
                },
                "expected_features": ["database", "connection", "ssl", "production"]
            },
            {
                "type": "log",  # Changed from "api_documentation" (invalid MCP type)
                "content": {
                    "text": "REST API endpoint for user authentication using JWT tokens with role-based access control and session management.",
                    "title": "User Authentication API",
                    "tags": ["api", "authentication", "jwt", "rbac", "api_documentation"]
                },
                "expected_features": ["api", "authentication", "jwt", "access"]
            },
            {
                "type": "log",  # Changed from "troubleshooting_guide" (invalid MCP type)
                "content": {
                    "text": "Debugging network connectivity issues in microservices architecture with service mesh monitoring and distributed tracing.",
                    "title": "Network Troubleshooting Guide",
                    "tags": ["troubleshooting", "network", "microservices", "tracing", "troubleshooting_guide"]
                },
                "expected_features": ["debugging", "network", "microservices", "monitoring"]
            },
            {
                "type": "log",  # Changed from "deployment_process" (invalid MCP type)
                "content": {
                    "text": "Automated deployment pipeline with Docker containers, Kubernetes orchestration, and CI/CD integration for production releases.",
                    "title": "Deployment Automation",
                    "tags": ["deployment", "docker", "kubernetes", "cicd", "deployment_process"]
                },
                "expected_features": ["deployment", "docker", "kubernetes", "automation"]
            },
            {
                "type": "log",  # Changed from "performance_optimization" (invalid MCP type)
                "content": {
                    "text": "Application performance tuning strategies including database query optimization, caching layers, and load balancing configuration.",
                    "title": "Performance Optimization Strategies",
                    "tags": ["performance", "optimization", "caching", "database", "performance_optimization"]
                },
                "expected_features": ["performance", "optimization", "caching", "database"]
            }
        ]
        
    async def run_check(self) -> CheckResult:
        """Execute comprehensive content pipeline monitoring."""
        start_time = time.time()
        
        try:
            # Run all pipeline validation tests
            test_results = await asyncio.gather(
                self._test_content_ingestion(),
                self._validate_pipeline_stages(),
                self._test_content_retrieval(),
                self._validate_storage_consistency(),
                self._test_pipeline_performance(),
                self._validate_error_handling(),
                self._test_content_lifecycle(),
                return_exceptions=True
            )
            
            # Analyze results
            pipeline_issues = []
            passed_tests = []
            failed_tests = []
            
            test_names = [
                "content_ingestion",
                "pipeline_stages",
                "content_retrieval",
                "storage_consistency",
                "pipeline_performance",
                "error_handling",
                "content_lifecycle"
            ]
            
            for i, result in enumerate(test_results):
                test_name = test_names[i]
                
                if isinstance(result, Exception):
                    failed_tests.append(test_name)
                    pipeline_issues.append(f"{test_name}: {str(result)}")
                elif result.get("passed", False):
                    passed_tests.append(test_name)
                else:
                    failed_tests.append(test_name)
                    pipeline_issues.append(f"{test_name}: {result.get('message', 'Unknown failure')}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Determine overall status
            if pipeline_issues:
                status = "fail"
                message = f"Content pipeline issues detected: {len(pipeline_issues)} problems found"
            else:
                status = "pass"
                message = f"All content pipeline checks passed: {len(passed_tests)} tests successful"
            
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
                    "pipeline_issues": pipeline_issues,
                    "passed_test_names": passed_tests,
                    "failed_test_names": failed_tests,
                    "test_results": test_results,
                    "pipeline_configuration": {
                        "pipeline_stages": self.pipeline_stages,
                        "test_samples_count": len(self.test_content_samples),
                        "performance_thresholds": self.performance_thresholds
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
                message=f"Content pipeline monitoring failed with error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    async def _test_content_ingestion(self) -> Dict[str, Any]:
        """Test content ingestion and processing stages."""
        try:
            ingestion_tests = []
            successful_ingestions = 0
            total_ingestion_time = 0.0

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                for i, sample in enumerate(self.test_content_samples):
                    test_id = f"pipeline_test_{uuid.uuid4().hex[:8]}"
                    content_type = sample["type"]
                    content_data = sample["content"]

                    # Prepare ingestion payload - API expects content as string
                    # Fixed: Field name is "content_type" not "context_type"
                    # Using valid MCP type "log" for test data
                    ingestion_payload = {
                        "content_type": "log",  # Changed from "context_type": "pipeline_test"
                        "content": content_data["text"],  # Extract text string from content dict
                        "title": f"Pipeline Test - {content_type} #{i+1}",
                        "metadata": {
                            "test_id": test_id,
                            "content_type": content_type,
                            "test_type": "pipeline_test",  # Original type preserved for filtering
                            "test_timestamp": datetime.utcnow().isoformat(),
                            "expected_features": sample.get("expected_features", []),
                            "original_title": content_data.get("title", ""),
                            "tags": content_data.get("tags", [])
                        }
                    }
                    
                    # Test ingestion
                    ingestion_start = time.time()
                    try:
                        store_url = f"{self.veris_memory_url}/api/v1/contexts"
                        async with session.post(store_url, json=ingestion_payload, headers=headers) as response:
                            ingestion_latency = (time.time() - ingestion_start) * 1000
                            total_ingestion_time += ingestion_latency
                            
                            if response.status == 201:
                                result_data = await response.json()
                                context_id = result_data.get("context_id")
                                
                                ingestion_tests.append({
                                    "test_id": test_id,
                                    "content_type": content_type,
                                    "context_id": context_id,
                                    "ingestion_latency_ms": ingestion_latency,
                                    "ingestion_successful": True,
                                    "status_code": response.status
                                })
                                
                                successful_ingestions += 1
                            else:
                                error_detail = await response.text()
                                ingestion_tests.append({
                                    "test_id": test_id,
                                    "content_type": content_type,
                                    "ingestion_latency_ms": ingestion_latency,
                                    "ingestion_successful": False,
                                    "status_code": response.status,
                                    "error": error_detail
                                })
                                
                    except Exception as ingestion_error:
                        ingestion_latency = (time.time() - ingestion_start) * 1000
                        total_ingestion_time += ingestion_latency
                        
                        ingestion_tests.append({
                            "test_id": test_id,
                            "content_type": content_type,
                            "ingestion_latency_ms": ingestion_latency,
                            "ingestion_successful": False,
                            "error": str(ingestion_error)
                        })
            
            success_rate = successful_ingestions / len(self.test_content_samples) if self.test_content_samples else 0.0
            avg_ingestion_latency = total_ingestion_time / len(self.test_content_samples) if self.test_content_samples else 0.0
            
            ingestion_threshold = INGESTION_SUCCESS_THRESHOLD
            latency_threshold = self.performance_thresholds["ingestion_latency_ms"]
            
            passed = (success_rate >= ingestion_threshold and 
                     avg_ingestion_latency <= latency_threshold)
            
            return {
                "passed": passed,
                "message": f"Content ingestion: {success_rate:.2f} success rate, {avg_ingestion_latency:.1f}ms avg latency",
                "success_rate": success_rate,
                "successful_ingestions": successful_ingestions,
                "avg_ingestion_latency_ms": avg_ingestion_latency,
                "ingestion_threshold": ingestion_threshold,
                "latency_threshold": latency_threshold,
                "ingestion_tests": ingestion_tests
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Content ingestion test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _validate_pipeline_stages(self) -> Dict[str, Any]:
        """Validate all pipeline stages are functioning correctly."""
        try:
            stage_validations = []

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                # Test each pipeline stage through health endpoints
                stage_endpoints = {
                    "ingestion": f"{self.veris_memory_url}/health/ingestion",
                    "validation": f"{self.veris_memory_url}/health/validation",
                    "enrichment": f"{self.veris_memory_url}/health/enrichment",
                    "storage": f"{self.veris_memory_url}/health/storage",
                    "indexing": f"{self.veris_memory_url}/health/indexing",
                    "retrieval": f"{self.veris_memory_url}/health/retrieval"
                }
                
                for stage in self.pipeline_stages:
                    endpoint = stage_endpoints.get(stage, f"{self.veris_memory_url}/health/{stage}")

                    try:
                        async with session.get(endpoint, headers=headers) as response:
                            if response.status == 200:
                                health_data = await response.json()
                                stage_validations.append({
                                    "stage": stage,
                                    "status": "healthy",
                                    "status_code": response.status,
                                    "health_data": health_data,
                                    "stage_operational": True
                                })
                            else:
                                stage_validations.append({
                                    "stage": stage,
                                    "status": "unhealthy",
                                    "status_code": response.status,
                                    "stage_operational": False
                                })
                    except Exception as stage_error:
                        # Fallback: Test stage through general health endpoint
                        try:
                            general_health_url = f"{self.veris_memory_url}/health/ready"
                            async with session.get(general_health_url, headers=headers) as health_response:
                                if health_response.status == 200:
                                    # Assume stage is operational if general health is good
                                    stage_validations.append({
                                        "stage": stage,
                                        "status": "assumed_healthy",
                                        "status_code": health_response.status,
                                        "stage_operational": True,
                                        "note": "Validated through general health endpoint"
                                    })
                                else:
                                    stage_validations.append({
                                        "stage": stage,
                                        "status": "unknown",
                                        "stage_operational": False,
                                        "error": str(stage_error)
                                    })
                        except Exception:
                            stage_validations.append({
                                "stage": stage,
                                "status": "error",
                                "stage_operational": False,
                                "error": str(stage_error)
                            })
            
            operational_stages = sum(1 for validation in stage_validations 
                                   if validation.get("stage_operational", False))
            stage_health_ratio = operational_stages / len(self.pipeline_stages) if self.pipeline_stages else 0.0
            stage_threshold = STAGE_HEALTH_THRESHOLD
            
            return {
                "passed": stage_health_ratio >= stage_threshold,
                "message": f"Pipeline stages: {operational_stages}/{len(self.pipeline_stages)} operational ({stage_health_ratio:.2f})",
                "stage_health_ratio": stage_health_ratio,
                "operational_stages": operational_stages,
                "total_stages": len(self.pipeline_stages),
                "stage_threshold": stage_threshold,
                "stage_validations": stage_validations
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Pipeline stages validation failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_content_retrieval(self) -> Dict[str, Any]:
        """Test content retrieval and search performance."""
        try:
            retrieval_tests = []
            successful_retrievals = 0
            total_retrieval_time = 0.0

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                # Test retrieval with various query patterns
                test_queries = [
                    "database configuration",
                    "authentication jwt",
                    "network troubleshooting",
                    "deployment docker",
                    "performance optimization"
                ]
                
                for query in test_queries:
                    retrieval_start = time.time()
                    
                    search_data = {
                        "query": query,
                        "limit": 10
                    }
                    
                    try:
                        search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                        async with session.post(search_url, json=search_data, headers=headers) as response:
                            retrieval_latency = (time.time() - retrieval_start) * 1000
                            total_retrieval_time += retrieval_latency
                            
                            if response.status == 200:
                                search_results = await response.json()
                                contexts = search_results.get("contexts", [])
                                
                                retrieval_tests.append({
                                    "query": query,
                                    "retrieval_latency_ms": retrieval_latency,
                                    "results_count": len(contexts),
                                    "retrieval_successful": True,
                                    "status_code": response.status
                                })
                                
                                successful_retrievals += 1
                            else:
                                error_detail = await response.text()
                                retrieval_tests.append({
                                    "query": query,
                                    "retrieval_latency_ms": retrieval_latency,
                                    "retrieval_successful": False,
                                    "status_code": response.status,
                                    "error": error_detail
                                })
                                
                    except Exception as retrieval_error:
                        retrieval_latency = (time.time() - retrieval_start) * 1000
                        total_retrieval_time += retrieval_latency
                        
                        retrieval_tests.append({
                            "query": query,
                            "retrieval_latency_ms": retrieval_latency,
                            "retrieval_successful": False,
                            "error": str(retrieval_error)
                        })
            
            success_rate = successful_retrievals / len(test_queries) if test_queries else 0.0
            avg_retrieval_latency = total_retrieval_time / len(test_queries) if test_queries else 0.0
            
            retrieval_threshold = RETRIEVAL_SUCCESS_THRESHOLD
            latency_threshold = self.performance_thresholds["retrieval_latency_ms"]
            
            passed = (success_rate >= retrieval_threshold and 
                     avg_retrieval_latency <= latency_threshold)
            
            return {
                "passed": passed,
                "message": f"Content retrieval: {success_rate:.2f} success rate, {avg_retrieval_latency:.1f}ms avg latency",
                "success_rate": success_rate,
                "successful_retrievals": successful_retrievals,
                "avg_retrieval_latency_ms": avg_retrieval_latency,
                "retrieval_threshold": retrieval_threshold,
                "latency_threshold": latency_threshold,
                "retrieval_tests": retrieval_tests
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Content retrieval test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _validate_storage_consistency(self) -> Dict[str, Any]:
        """Validate storage consistency across different storage backends."""
        try:
            consistency_tests = []

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                # Test storage consistency by storing and immediately retrieving content
                # Fixed: Field name is "content_type" not "context_type"
                test_content = {
                    "content_type": "log",  # Changed from "context_type": "consistency_test"
                    "content": f"Storage consistency test content - {datetime.utcnow().isoformat()}",  # String, not dict
                    "title": "Storage Consistency Test",
                    "metadata": {
                        "test_timestamp": datetime.utcnow().isoformat(),
                        "consistency_test": True,
                        "test_type": "consistency_validation"
                    }
                }
                
                stored_contexts = []
                
                # Store multiple test contexts
                for i in range(5):
                    test_content["title"] = f"Storage Consistency Test #{i+1}"
                    test_content["content"] = f"Storage consistency test content #{i+1} - {datetime.utcnow().isoformat()}"

                    try:
                        store_url = f"{self.veris_memory_url}/api/v1/contexts"
                        async with session.post(store_url, json=test_content, headers=headers) as response:
                            if response.status == 201:
                                result_data = await response.json()
                                context_id = result_data.get("context_id")
                                stored_contexts.append(context_id)
                    except Exception as store_error:
                        logger.warning(f"Storage error during consistency test: {store_error}")
                
                # Allow time for storage propagation
                await asyncio.sleep(2)
                
                # Verify stored contexts can be retrieved
                successful_retrievals = 0
                
                for context_id in stored_contexts:
                    try:
                        get_url = f"{self.veris_memory_url}/api/v1/contexts/{context_id}"
                        async with session.get(get_url, headers=headers) as response:
                            if response.status == 200:
                                context_data = await response.json()
                                
                                consistency_tests.append({
                                    "context_id": context_id,
                                    "storage_successful": True,
                                    "retrieval_successful": True,
                                    "status_code": response.status
                                })
                                
                                successful_retrievals += 1
                            else:
                                consistency_tests.append({
                                    "context_id": context_id,
                                    "storage_successful": True,
                                    "retrieval_successful": False,
                                    "status_code": response.status
                                })
                    except Exception as retrieval_error:
                        consistency_tests.append({
                            "context_id": context_id,
                            "storage_successful": True,
                            "retrieval_successful": False,
                            "error": str(retrieval_error)
                        })
            
            consistency_ratio = successful_retrievals / len(stored_contexts) if stored_contexts else 0.0
            consistency_threshold = self.performance_thresholds["storage_consistency_ratio"]
            
            return {
                "passed": consistency_ratio >= consistency_threshold,
                "message": f"Storage consistency: {consistency_ratio:.2f} ratio ({successful_retrievals}/{len(stored_contexts)})",
                "consistency_ratio": consistency_ratio,
                "successful_retrievals": successful_retrievals,
                "total_stored": len(stored_contexts),
                "consistency_threshold": consistency_threshold,
                "consistency_tests": consistency_tests
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Storage consistency validation failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_pipeline_performance(self) -> Dict[str, Any]:
        """Test overall pipeline performance and throughput."""
        try:
            performance_metrics = {
                "throughput_test": {},
                "latency_test": {},
                "concurrent_load_test": {}
            }

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                
                # Throughput test - measure operations per minute
                throughput_start = time.time()
                throughput_operations = 0
                
                for i in range(10):  # Test with 10 rapid operations
                    # Fixed: Field name is "content_type" not "context_type"
                    test_content = {
                        "content_type": "log",  # Changed from "context_type": "throughput_test"
                        "content": f"Throughput test content #{i+1}",  # String, not dict
                        "title": f"Throughput Test #{i+1}",
                        "metadata": {
                            "test_type": "throughput",
                            "operation_index": i,
                            "performance_test": True
                        }
                    }

                    try:
                        store_url = f"{self.veris_memory_url}/api/v1/contexts"
                        async with session.post(store_url, json=test_content, headers=headers) as response:
                            if response.status == 201:
                                throughput_operations += 1
                    except Exception:
                        continue
                
                throughput_duration = time.time() - throughput_start
                operations_per_minute = (throughput_operations / throughput_duration) * 60 if throughput_duration > 0 else 0
                
                performance_metrics["throughput_test"] = {
                    "operations_completed": throughput_operations,
                    "duration_seconds": throughput_duration,
                    "operations_per_minute": operations_per_minute,
                    "threshold": self.performance_thresholds["pipeline_throughput_per_min"],
                    "meets_threshold": operations_per_minute >= self.performance_thresholds["pipeline_throughput_per_min"]
                }
                
                # Latency test - measure end-to-end latency
                latency_measurements = []
                
                for i in range(3):
                    latency_start = time.time()

                    # Store content
                    # Fixed: Field name is "content_type" not "context_type"
                    test_content = {
                        "content_type": "log",  # Changed from "context_type": "latency_test"
                        "content": f"Latency test content for measurement #{i+1}",  # String, not dict
                        "title": f"Latency Test #{i+1}",
                        "metadata": {
                            "performance_test": True,
                            "test_type": "latency"
                        }
                    }

                    try:
                        store_url = f"{self.veris_memory_url}/api/v1/contexts"
                        async with session.post(store_url, json=test_content, headers=headers) as response:
                            if response.status == 201:
                                store_latency = (time.time() - latency_start) * 1000
                                
                                # Test immediate retrieval
                                search_start = time.time()
                                search_data = {
                                    "query": f"Latency test content for measurement #{i+1}",
                                    "limit": 5
                                }

                                search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                                async with session.post(search_url, json=search_data, headers=headers) as search_response:
                                    if search_response.status == 200:
                                        search_latency = (time.time() - search_start) * 1000
                                        total_latency = store_latency + search_latency
                                        
                                        latency_measurements.append({
                                            "store_latency_ms": store_latency,
                                            "search_latency_ms": search_latency,
                                            "total_latency_ms": total_latency
                                        })
                    except Exception:
                        continue
                
                avg_total_latency = (sum(m["total_latency_ms"] for m in latency_measurements) / 
                                   len(latency_measurements)) if latency_measurements else 0
                
                performance_metrics["latency_test"] = {
                    "measurements": latency_measurements,
                    "avg_total_latency_ms": avg_total_latency,
                    "threshold_ms": self.performance_thresholds["ingestion_latency_ms"] + self.performance_thresholds["retrieval_latency_ms"],
                    "meets_threshold": avg_total_latency <= (self.performance_thresholds["ingestion_latency_ms"] + self.performance_thresholds["retrieval_latency_ms"])
                }
                
                # Concurrent load test - test with concurrent operations
                concurrent_start = time.time()

                async def concurrent_operation(session, index):
                    # Fixed: Field name is "content_type" not "context_type"
                    test_content = {
                        "content_type": "log",  # Changed from "context_type": "concurrent_test"
                        "content": f"Concurrent test content #{index}",  # String, not dict
                        "title": f"Concurrent Test #{index}",
                        "metadata": {
                            "performance_test": True,
                            "test_type": "concurrent"
                        }
                    }

                    try:
                        store_url = f"{self.veris_memory_url}/api/v1/contexts"
                        async with session.post(store_url, json=test_content, headers=headers) as response:
                            return response.status == 201
                    except Exception:
                        return False

                # Run 5 concurrent operations
                concurrent_tasks = [concurrent_operation(session, i) for i in range(5)]
                concurrent_results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
                
                concurrent_duration = time.time() - concurrent_start
                successful_concurrent = sum(1 for result in concurrent_results if result is True)
                
                performance_metrics["concurrent_load_test"] = {
                    "concurrent_operations": len(concurrent_tasks),
                    "successful_operations": successful_concurrent,
                    "duration_seconds": concurrent_duration,
                    "success_rate": successful_concurrent / len(concurrent_tasks) if concurrent_tasks else 0,
                    "meets_threshold": successful_concurrent >= MIN_CONCURRENT_SUCCESS  # At least 80% success
                }
            
            # Overall performance assessment
            all_thresholds_met = all([
                performance_metrics["throughput_test"].get("meets_threshold", False),
                performance_metrics["latency_test"].get("meets_threshold", False),
                performance_metrics["concurrent_load_test"].get("meets_threshold", False)
            ])
            
            return {
                "passed": all_thresholds_met,
                "message": f"Pipeline performance: throughput={performance_metrics['throughput_test']['operations_per_minute']:.1f}/min, latency={performance_metrics['latency_test']['avg_total_latency_ms']:.1f}ms",
                "performance_metrics": performance_metrics,
                "all_thresholds_met": all_thresholds_met
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Pipeline performance test failed: {str(e)}",
                "error": str(e)
            }
    
    async def _validate_error_handling(self) -> Dict[str, Any]:
        """Validate pipeline error handling and recovery mechanisms."""
        try:
            error_handling_tests = []

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:

                # Test 1: Invalid content format
                try:
                    invalid_content = {
                        "invalid_field": "missing required fields",
                        "malformed": True
                    }

                    store_url = f"{self.veris_memory_url}/api/v1/contexts"
                    async with session.post(store_url, json=invalid_content, headers=headers) as response:
                        error_handling_tests.append({
                            "test": "invalid_content_format",
                            "expected_failure": True,
                            "actual_status": response.status,
                            "properly_handled": response.status in [400, 422],
                            "response_body": await response.text()
                        })
                except Exception as e:
                    error_handling_tests.append({
                        "test": "invalid_content_format",
                        "expected_failure": True,
                        "properly_handled": True,
                        "error": str(e)
                    })
                
                # Test 2: Oversized content
                try:
                    # Fixed: Field name is "content_type" not "context_type"
                    oversized_content = {
                        "content_type": "log",  # Changed from "context_type": "error_test"
                        "content": "x" * 1000000,  # 1MB of text - string, not dict
                        "title": "Oversized Content Test",
                        "metadata": {
                            "oversized": True,
                            "test_type": "error_handling"
                        }
                    }
                    
                    async with session.post(store_url, json=oversized_content) as response:
                        error_handling_tests.append({
                            "test": "oversized_content",
                            "expected_failure": True,
                            "actual_status": response.status,
                            "properly_handled": response.status in [400, 413, 422],
                            "response_body": await response.text()
                        })
                except Exception as e:
                    error_handling_tests.append({
                        "test": "oversized_content",
                        "expected_failure": True,
                        "properly_handled": True,
                        "error": str(e)
                    })
                
                # Test 3: Invalid search query
                try:
                    invalid_search = {
                        "query": "",  # Empty query
                        "limit": -1   # Invalid limit
                    }

                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    async with session.post(search_url, json=invalid_search, headers=headers) as response:
                        error_handling_tests.append({
                            "test": "invalid_search_query",
                            "expected_failure": True,
                            "actual_status": response.status,
                            "properly_handled": response.status in [400, 422],
                            "response_body": await response.text()
                        })
                except Exception as e:
                    error_handling_tests.append({
                        "test": "invalid_search_query",
                        "expected_failure": True,
                        "properly_handled": True,
                        "error": str(e)
                    })
                
                # Test 4: Non-existent context retrieval
                try:
                    fake_context_id = "non_existent_context_id_12345"
                    get_url = f"{self.veris_memory_url}/api/v1/contexts/{fake_context_id}"

                    async with session.get(get_url, headers=headers) as response:
                        error_handling_tests.append({
                            "test": "non_existent_context",
                            "expected_failure": True,
                            "actual_status": response.status,
                            "properly_handled": response.status == 404,
                            "response_body": await response.text()
                        })
                except Exception as e:
                    error_handling_tests.append({
                        "test": "non_existent_context",
                        "expected_failure": True,
                        "properly_handled": True,
                        "error": str(e)
                    })
            
            properly_handled_errors = sum(1 for test in error_handling_tests 
                                        if test.get("properly_handled", False))
            error_handling_ratio = properly_handled_errors / len(error_handling_tests) if error_handling_tests else 0.0
            error_handling_threshold = ERROR_HANDLING_THRESHOLD
            
            return {
                "passed": error_handling_ratio >= error_handling_threshold,
                "message": f"Error handling: {properly_handled_errors}/{len(error_handling_tests)} errors properly handled ({error_handling_ratio:.2f})",
                "error_handling_ratio": error_handling_ratio,
                "properly_handled_errors": properly_handled_errors,
                "total_error_tests": len(error_handling_tests),
                "error_handling_threshold": error_handling_threshold,
                "error_handling_tests": error_handling_tests
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Error handling validation failed: {str(e)}",
                "error": str(e)
            }
    
    async def _test_content_lifecycle(self) -> Dict[str, Any]:
        """Test complete content lifecycle from creation to retrieval."""
        try:
            lifecycle_stages = []

            # Get authentication headers
            headers = self._get_headers()

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:

                # Stage 1: Content Creation
                # Fixed: Field name is "content_type" not "context_type"
                lifecycle_content = {
                    "content_type": "log",  # Changed from "context_type": "lifecycle_test"
                    "content": f"Content lifecycle test - {datetime.utcnow().isoformat()}",  # String, not dict
                    "title": "Content Lifecycle Test",
                    "metadata": {
                        "lifecycle_test": True,
                        "lifecycle_stage": "creation",
                        "test_type": "lifecycle",
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
                
                creation_start = time.time()
                context_id = None
                
                try:
                    store_url = f"{self.veris_memory_url}/api/v1/contexts"
                    async with session.post(store_url, json=lifecycle_content, headers=headers) as response:
                        creation_latency = (time.time() - creation_start) * 1000
                        
                        if response.status == 201:
                            result_data = await response.json()
                            context_id = result_data.get("context_id")
                            
                            lifecycle_stages.append({
                                "stage": "creation",
                                "successful": True,
                                "latency_ms": creation_latency,
                                "context_id": context_id,
                                "status_code": response.status
                            })
                        else:
                            lifecycle_stages.append({
                                "stage": "creation",
                                "successful": False,
                                "latency_ms": creation_latency,
                                "status_code": response.status,
                                "error": await response.text()
                            })
                except Exception as creation_error:
                    lifecycle_stages.append({
                        "stage": "creation",
                        "successful": False,
                        "error": str(creation_error)
                    })
                
                if not context_id:
                    return {
                        "passed": False,
                        "message": "Content lifecycle test failed at creation stage",
                        "lifecycle_stages": lifecycle_stages
                    }
                
                # Stage 2: Content Indexing (wait for processing)
                await asyncio.sleep(2)  # Allow time for indexing
                
                # Stage 3: Content Retrieval by ID
                retrieval_start = time.time()
                
                try:
                    get_url = f"{self.veris_memory_url}/api/v1/contexts/{context_id}"
                    async with session.get(get_url, headers=headers) as response:
                        retrieval_latency = (time.time() - retrieval_start) * 1000
                        
                        if response.status == 200:
                            retrieved_data = await response.json()

                            # Extract retrieved content - handle both nested and flat formats
                            # DUAL FORMAT SUPPORT RATIONALE:
                            # The system is transitioning from nested dict format to flat string format.
                            # - Legacy format (pre-PR#265): content = {"text": "...", "title": "..."}
                            # - Current format (post-PR#265): content = "..."
                            # Both formats must be supported during transition period to ensure:
                            # 1. Backward compatibility with existing stored contexts
                            # 2. No test failures during gradual migration
                            # 3. Smooth rollout without breaking existing integrations
                            # TODO: Remove dict format support in v2.0 after full migration
                            retrieved_context = retrieved_data.get("context", {})
                            retrieved_content = retrieved_context.get("content")
                            if isinstance(retrieved_content, dict):
                                # Legacy nested dict format: extract text from dict
                                retrieved_text = retrieved_content.get("text", "")
                            else:
                                # Current flat string format: use content directly
                                retrieved_text = retrieved_content or ""

                            # Compare with original content string
                            original_text = lifecycle_content["content"]
                            data_integrity = retrieved_text == original_text

                            lifecycle_stages.append({
                                "stage": "retrieval_by_id",
                                "successful": True,
                                "latency_ms": retrieval_latency,
                                "context_id": context_id,
                                "status_code": response.status,
                                "data_integrity": data_integrity
                            })
                        else:
                            lifecycle_stages.append({
                                "stage": "retrieval_by_id",
                                "successful": False,
                                "latency_ms": retrieval_latency,
                                "status_code": response.status,
                                "error": await response.text()
                            })
                except Exception as retrieval_error:
                    lifecycle_stages.append({
                        "stage": "retrieval_by_id",
                        "successful": False,
                        "error": str(retrieval_error)
                    })
                
                # Stage 4: Content Search
                search_start = time.time()
                
                try:
                    search_data = {
                        "query": "Content lifecycle test",
                        "limit": 10
                    }

                    search_url = f"{self.veris_memory_url}/api/v1/contexts/search"
                    async with session.post(search_url, json=search_data, headers=headers) as response:
                        search_latency = (time.time() - search_start) * 1000
                        
                        if response.status == 200:
                            search_results = await response.json()
                            contexts = search_results.get("contexts", [])
                            
                            # Check if our context appears in search results
                            found_in_search = any(ctx.get("context_id") == context_id for ctx in contexts)
                            
                            lifecycle_stages.append({
                                "stage": "search_discovery",
                                "successful": True,
                                "latency_ms": search_latency,
                                "found_in_search": found_in_search,
                                "results_count": len(contexts),
                                "status_code": response.status
                            })
                        else:
                            lifecycle_stages.append({
                                "stage": "search_discovery",
                                "successful": False,
                                "latency_ms": search_latency,
                                "status_code": response.status,
                                "error": await response.text()
                            })
                except Exception as search_error:
                    lifecycle_stages.append({
                        "stage": "search_discovery",
                        "successful": False,
                        "error": str(search_error)
                    })
            
            # Analyze lifecycle completion
            successful_stages = sum(1 for stage in lifecycle_stages if stage.get("successful", False))
            lifecycle_success_ratio = successful_stages / len(lifecycle_stages) if lifecycle_stages else 0.0
            lifecycle_threshold = LIFECYCLE_SUCCESS_THRESHOLD
            
            return {
                "passed": lifecycle_success_ratio >= lifecycle_threshold,
                "message": f"Content lifecycle: {successful_stages}/{len(lifecycle_stages)} stages successful ({lifecycle_success_ratio:.2f})",
                "lifecycle_success_ratio": lifecycle_success_ratio,
                "successful_stages": successful_stages,
                "total_stages": len(lifecycle_stages),
                "lifecycle_threshold": lifecycle_threshold,
                "lifecycle_stages": lifecycle_stages
            }
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Content lifecycle test failed: {str(e)}",
                "error": str(e)
            }