#!/usr/bin/env python3
"""
S2: Golden Fact Recall Check

Tests the ability to store and recall specific facts through natural language queries.
This validates that the core store/retrieve functionality works correctly.
"""

import asyncio
import json
import time
import uuid
import aiohttp
from datetime import datetime
from typing import Dict, Any, List

from ..base_check import BaseCheck, APITestMixin
from ..models import CheckResult, SentinelConfig


class GoldenFactRecall(BaseCheck, APITestMixin):
    """S2: Golden fact recall testing with natural questions."""
    
    def __init__(self, config: SentinelConfig) -> None:
        super().__init__(config, "S2-golden-fact-recall", "Golden fact recall with natural questions")
        self.test_dataset = [
            {
                "kv": {"name": "Matt"},
                "questions": ["What's my name?", "Who am I?"],
                "expect_contains": "Matt"
            },
            {
                "kv": {"food": "spicy"},
                "questions": ["What kind of food do I like?", "What food preference do I have?"],
                "expect_contains": "spicy"
            },
            {
                "kv": {"location": "San Francisco"},
                "questions": ["Where do I live?", "What's my location?"],
                "expect_contains": "San Francisco"
            }
        ]
        
    async def run_check(self) -> CheckResult:
        """Execute golden fact recall check."""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                test_results = []
                total_tests = 0
                passed_tests = 0
                
                for i, test_case in enumerate(self.test_dataset):
                    test_result = await self._run_single_test(session, test_case, i)
                    test_results.append(test_result)
                    
                    total_tests += test_result["total_questions"]
                    passed_tests += test_result["passed_questions"]
                
                # Determine overall status
                success_rate = passed_tests / total_tests if total_tests > 0 else 0.0
                
                if success_rate >= 0.8:
                    status = "pass"
                    message = f"Golden fact recall successful: {passed_tests}/{total_tests} tests passed"
                elif success_rate >= 0.6:
                    status = "warn"
                    message = f"Golden fact recall degraded: {passed_tests}/{total_tests} tests passed"
                else:
                    status = "fail"
                    message = f"Golden fact recall failed: {passed_tests}/{total_tests} tests passed"
                
                latency_ms = (time.time() - start_time) * 1000
                return CheckResult(
                    check_id=self.check_id,
                    timestamp=datetime.utcnow(),
                    status=status,
                    latency_ms=latency_ms,
                    message=message,
                    details={
                        "total_tests": total_tests,
                        "passed_tests": passed_tests,
                        "success_rate": success_rate,
                        "test_results": test_results,
                        "latency_ms": latency_ms
                    }
                )
                
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return CheckResult(
                check_id=self.check_id,
                timestamp=datetime.utcnow(),
                status="fail",
                latency_ms=latency_ms,
                message=f"Golden fact recall exception: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _run_single_test(self, session: aiohttp.ClientSession, test_case: Dict[str, Any], test_index: int) -> Dict[str, Any]:
        """Run a single golden fact test case."""
        user_id = f"sentinel_test_{uuid.uuid4().hex[:8]}"
        
        # Store the fact
        store_result = await self._store_fact(session, test_case["kv"], user_id)
        if not store_result["success"]:
            return {
                "test_index": test_index,
                "test_case": test_case,
                "store_success": False,
                "store_error": store_result["message"],
                "total_questions": len(test_case["questions"]),
                "passed_questions": 0,
                "question_results": []
            }
        
        # Test each question
        question_results = []
        passed_questions = 0
        
        for question in test_case["questions"]:
            question_result = await self._test_recall(session, question, test_case["expect_contains"], user_id)
            question_results.append(question_result)
            
            if question_result["success"]:
                passed_questions += 1
        
        return {
            "test_index": test_index,
            "test_case": test_case,
            "store_success": True,
            "store_result": store_result,
            "total_questions": len(test_case["questions"]),
            "passed_questions": passed_questions,
            "question_results": question_results
        }
    
    async def _store_fact(self, session: aiohttp.ClientSession, fact_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Store a fact in the system."""
        # Fixed: Use correct MCP API format (PR #240 + #241)
        # - content: Dict, not JSON string
        # - type: must be one of: design, decision, trace, sprint, log
        # - author: not user_id
        # Note: Using "log" type since "fact" is not in allowed values
        store_payload = {
            "content": fact_data,
            "type": "log",
            "author": user_id,
            "metadata": {"test_type": "golden_recall", "sentinel": True, "content_type": "fact"}
        }
        
        success, message, latency, response_data = await self.test_api_call(
            session,
            "POST",
            f"{self.config.target_base_url}/tools/store_context",
            data=store_payload,
            expected_status=200,
            timeout=10.0
        )
        
        return {
            "success": success,
            "message": message,
            "latency_ms": latency,
            "response": response_data,
            "payload": store_payload
        }
    
    async def _test_recall(self, session: aiohttp.ClientSession, question: str, expected_content: str, user_id: str) -> Dict[str, Any]:
        """Test recalling a fact through a natural language question."""
        # Fixed: Use correct MCP API format (PR #240)
        # - filters: {"author": user_id} instead of user_id field
        query_payload = {
            "query": question,
            "limit": 5,
            "filters": {"author": user_id}
        }
        
        success, message, latency, response_data = await self.test_api_call(
            session,
            "POST",
            f"{self.config.target_base_url}/tools/retrieve_context",
            data=query_payload,
            expected_status=200,
            timeout=15.0
        )
        
        if not success:
            return {
                "question": question,
                "expected_content": expected_content,
                "success": False,
                "message": f"API call failed: {message}",
                "latency_ms": latency
            }
        
        # Check if the expected content is in the response
        # Fixed: API returns "results" not "contexts" (PR #240)
        if not response_data or "results" not in response_data:
            return {
                "question": question,
                "expected_content": expected_content,
                "success": False,
                "message": "No results returned",
                "latency_ms": latency,
                "response": response_data
            }

        contexts = response_data["results"]
        found_expected = False

        for context in contexts:
            # Fixed: content is a dict, need to convert to string for searching (PR #240)
            content = context.get("content", {})
            # Convert content dict to string for searching
            content_str = json.dumps(content) if isinstance(content, dict) else str(content)
            if expected_content.lower() in content_str.lower():
                found_expected = True
                break
        
        return {
            "question": question,
            "expected_content": expected_content,
            "success": found_expected,
            "message": "Expected content found" if found_expected else f"Expected '{expected_content}' not found in response",
            "latency_ms": latency,
            "response": response_data,
            "contexts_count": len(contexts)
        }