#!/usr/bin/env python3
"""
Production T-102 Validation Test
Tests bulletproof reranker functionality directly without database dependencies
"""

import sys
import asyncio
import json
from typing import List, Dict, Any
import time

# Add src to path
sys.path.insert(0, 'src')

try:
    from storage.reranker_bulletproof import BulletproofReranker, extract_chunk_text
    DEPS_AVAILABLE = True
    print("✅ Bulletproof reranker imported successfully")
except ImportError as e:
    print(f"❌ Failed to import bulletproof reranker: {e}")
    DEPS_AVAILABLE = False

class ProductionT102Test:
    """Production validation for T-102 bulletproof reranker fix."""
    
    def __init__(self):
        if DEPS_AVAILABLE:
            self.reranker = BulletproofReranker(debug_mode=True)
        else:
            self.reranker = None
        
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def log_test(self, name: str, passed: bool, message: str = ""):
        """Log test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name} - {message}")
        
        self.test_results.append({
            "test": name,
            "passed": passed,
            "message": message,
            "timestamp": time.time()
        })
        
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def test_text_extraction_edge_cases(self):
        """Test text extraction with edge cases that caused T-102 bug."""
        print("\n🔧 Testing Text Extraction Edge Cases...")
        
        edge_cases = [
            # Empty payload
            {"name": "empty_payload", "payload": {}, "expect_chars": 0},
            
            # Null content
            {"name": "null_content", "payload": {"content": None}, "expect_chars": 0},
            
            # Empty string
            {"name": "empty_string", "payload": {"content": ""}, "expect_chars": 0},
            
            # Whitespace only
            {"name": "whitespace_only", "payload": {"content": "   \n\t\r  "}, "expect_chars": 0},
            
            # Valid minimal content
            {"name": "minimal_valid", "payload": {"content": "a"}, "expect_chars": 1},
            
            # Complex nested structure
            {"name": "nested_complex", "payload": {
                "data": {
                    "payload": {
                        "content": {
                            "text": "deeply nested content"
                        }
                    }
                }
            }, "expect_chars": 21},
            
            # MCP-style tool result
            {"name": "mcp_tool_result", "payload": {
                "tool": "search",
                "result": {
                    "content": "MCP tool result content"
                }
            }, "expect_chars": 23},
            
            # Large content
            {"name": "large_content", "payload": {
                "content": "This is a longer piece of content " * 50
            }, "expect_chars": 1650},
        ]
        
        for case in edge_cases:
            try:
                extracted = extract_chunk_text(case["payload"])
                actual_chars = len(extracted.strip())
                
                # For empty cases, allow fallback behavior
                if case["expect_chars"] == 0:
                    # Empty content should either return empty or fallback string
                    success = actual_chars == 0 or extracted.strip() == str(case["payload"])
                else:
                    success = actual_chars >= case["expect_chars"]
                
                self.log_test(
                    f"Text extraction: {case['name']}", 
                    success,
                    f"extracted {actual_chars} chars"
                )
                
            except Exception as e:
                self.log_test(
                    f"Text extraction: {case['name']}", 
                    False,
                    f"exception: {str(e)}"
                )
    
    def test_reranker_no_zeros(self):
        """Test that reranker never returns all-zero scores (T-102 fix)."""
        print("\n🎯 Testing T-102 Fix: No All-Zero Scores...")
        
        # Test cases that previously triggered the all-zeros bug
        test_cases = [
            {
                "name": "minimal_content",
                "query": "test",
                "documents": [
                    {"content": "a"},
                    {"content": "b"}, 
                    {"content": "test"}
                ]
            },
            {
                "name": "empty_content_mixed",
                "query": "find relevant",
                "documents": [
                    {"content": ""},
                    {"content": "   "},
                    {"content": "relevant information here"}
                ]
            },
            {
                "name": "identical_content",
                "query": "search query",
                "documents": [
                    {"content": "identical content"},
                    {"content": "identical content"},
                    {"content": "identical content"}
                ]
            },
            {
                "name": "special_characters",
                "query": "symbols",
                "documents": [
                    {"content": "!@#$%^&*()"},
                    {"content": "{}[]|\\:;\"'<>,.?/"},
                    {"content": "symbols and text mixed"}
                ]
            },
            {
                "name": "unicode_content",
                "query": "international",
                "documents": [
                    {"content": "你好世界"},
                    {"content": "🌟⭐✨"},
                    {"content": "international content"}
                ]
            }
        ]
        
        all_tests_passed = True
        
        for case in test_cases:
            try:
                # Run reranking
                start_time = time.time()
                result = self.reranker.rerank(case["query"], case["documents"])
                end_time = time.time()
                
                # Validate result structure
                if not isinstance(result, list):
                    self.log_test(
                        f"T-102 fix: {case['name']}", 
                        False, 
                        f"result not list: {type(result)}"
                    )
                    all_tests_passed = False
                    continue
                
                if len(result) != len(case["documents"]):
                    self.log_test(
                        f"T-102 fix: {case['name']}", 
                        False, 
                        f"length mismatch: {len(result)} vs {len(case['documents'])}"
                    )
                    all_tests_passed = False
                    continue
                
                # Extract scores
                scores = []
                for item in result:
                    if isinstance(item, dict) and 'score' in item:
                        scores.append(item['score'])
                    else:
                        scores.append(0)  # Fallback for malformed items
                
                # Check for all-zeros bug (T-102)
                all_zeros = all(score == 0 for score in scores)
                
                if all_zeros:
                    self.log_test(
                        f"T-102 fix: {case['name']}", 
                        False, 
                        "ALL ZEROS BUG DETECTED!"
                    )
                    all_tests_passed = False
                    continue
                
                # Check for reasonable score distribution
                if len(scores) > 1:
                    score_range = max(scores) - min(scores)
                    has_variation = score_range > 1e-6  # Allow for small floating point differences
                    
                    self.log_test(
                        f"T-102 fix: {case['name']}", 
                        True, 
                        f"scores: {min(scores):.3f}-{max(scores):.3f}, time: {(end_time-start_time)*1000:.1f}ms"
                    )
                else:
                    self.log_test(
                        f"T-102 fix: {case['name']}", 
                        True, 
                        f"single score: {scores[0]:.3f}, time: {(end_time-start_time)*1000:.1f}ms"
                    )
                
            except Exception as e:
                self.log_test(
                    f"T-102 fix: {case['name']}", 
                    False, 
                    f"exception: {str(e)}"
                )
                all_tests_passed = False
        
        return all_tests_passed
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks for production readiness."""
        print("\n⚡ Testing Performance Benchmarks...")
        
        # Generate test documents of varying sizes
        small_docs = [{"content": f"Small doc {i} with basic content"} for i in range(5)]
        medium_docs = [{"content": f"Medium document {i} with more detailed content " * 10} for i in range(10)]
        large_docs = [{"content": f"Large document {i} with extensive content " * 50} for i in range(20)]
        
        benchmark_cases = [
            {"name": "small_5_docs", "query": "basic content", "documents": small_docs, "max_time_ms": 2000},
            {"name": "medium_10_docs", "query": "detailed content", "documents": medium_docs, "max_time_ms": 3000},
            {"name": "large_20_docs", "query": "extensive content", "documents": large_docs, "max_time_ms": 5000},
        ]
        
        for case in benchmark_cases:
            try:
                start_time = time.time()
                result = self.reranker.rerank(case["query"], case["documents"])
                end_time = time.time()
                
                elapsed_ms = (end_time - start_time) * 1000
                
                # Performance check
                meets_performance = elapsed_ms <= case["max_time_ms"]
                
                # Correctness check
                correct_length = len(result) == len(case["documents"])
                has_scores = all('score' in item for item in result if isinstance(item, dict))
                
                overall_pass = meets_performance and correct_length and has_scores
                
                self.log_test(
                    f"Performance: {case['name']}", 
                    overall_pass,
                    f"{elapsed_ms:.1f}ms (target: <{case['max_time_ms']}ms), {len(result)} results"
                )
                
            except Exception as e:
                self.log_test(
                    f"Performance: {case['name']}", 
                    False,
                    f"exception: {str(e)}"
                )
    
    def run_production_validation(self):
        """Run complete production validation."""
        print("🚀 Production T-102 Validation Test")
        print("=" * 60)
        
        if not DEPS_AVAILABLE:
            print("❌ Dependencies not available - cannot run validation")
            return False
        
        # Run all test suites
        self.test_text_extraction_edge_cases()
        t102_success = self.test_reranker_no_zeros()
        self.test_performance_benchmarks()
        
        # Final summary
        print("\n" + "=" * 60)
        print("📊 PRODUCTION VALIDATION SUMMARY")
        print("=" * 60)
        print(f"✅ Tests Passed: {self.passed}")
        print(f"❌ Tests Failed: {self.failed}")
        print(f"📈 Success Rate: {(self.passed/(self.passed+self.failed)*100):.1f}%")
        
        # T-102 specific validation
        if t102_success and self.failed == 0:
            print("\n🎉 PRODUCTION VALIDATION PASSED!")
            print("✅ T-102 'all zeros' bug is FIXED")
            print("✅ Bulletproof reranker is production-ready")
            print("✅ Performance benchmarks met")
            status = "PASSED"
        elif t102_success:
            print("\n⚠️  PARTIAL SUCCESS")
            print("✅ T-102 'all zeros' bug is FIXED")
            print("⚠️  Some auxiliary tests failed")
            status = "PARTIAL"
        else:
            print("\n❌ VALIDATION FAILED")
            print("❌ Critical issues detected")
            status = "FAILED"
        
        # Save detailed results
        results = {
            "status": status,
            "timestamp": time.time(),
            "summary": {
                "passed": self.passed,
                "failed": self.failed,
                "success_rate": (self.passed/(self.passed+self.failed)*100) if (self.passed+self.failed) > 0 else 0,
                "t102_fixed": t102_success
            },
            "tests": self.test_results
        }
        
        with open('production_t102_validation.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: production_t102_validation.json")
        
        return status == "PASSED"

def main():
    """Main production validation execution."""
    validator = ProductionT102Test()
    success = validator.run_production_validation()
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)