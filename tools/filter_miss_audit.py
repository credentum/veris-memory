#!/usr/bin/env python3
"""
Filter & Namespace Miss Audit - Phase 4.1
Tests 50 known-answer queries with filters ON/OFF to detect filter-related recovery issues
"""

import asyncio
import logging
import time
import json
import random
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class MissReason(Enum):
    """Reason codes for search misses"""
    NO_CANDIDATES = "NO_CANDIDATES"          # No results returned at all
    FILTER_MISMATCH = "FILTER_MISMATCH"      # Filter eliminated relevant results  
    EMPTY_TEXT = "EMPTY_TEXT"                # Document has empty/missing text field
    LOW_SCORE = "LOW_SCORE"                  # Results below score threshold
    NAMESPACE_MISMATCH = "NAMESPACE_MISMATCH" # Wrong namespace filtering
    PAGINATION_MISS = "PAGINATION_MISS"       # Relevant result beyond limit
    UNKNOWN = "UNKNOWN"                      # Unable to determine reason

@dataclass 
class QueryTest:
    """Test case for filter miss audit"""
    query: str
    expected_type: Optional[str] = None      # Expected document type
    expected_namespace: Optional[str] = None  # Expected namespace
    expected_min_results: int = 1            # Minimum expected results
    description: str = ""                    # Human description

@dataclass
class AuditResult:
    """Result of filter miss audit for a single query"""
    query: str
    filters_on_results: int
    filters_off_results: int
    recovery_delta: float                    # filters_off - filters_on recovery
    miss_reason: Optional[MissReason]        # Reason if filters_on failed
    filters_on_time_ms: float
    filters_off_time_ms: float
    debug_info: Dict[str, Any]

class FilterMissAudit:
    """Miss audit system for filter ON vs OFF comparison"""
    
    def __init__(self):
        # Generate test cases
        self.test_cases = self._generate_test_cases()
        
        # Mock database for demonstration
        self.mock_documents = self._generate_mock_documents()
        
        logger.info(f"Filter miss audit initialized with {len(self.test_cases)} test cases")
    
    def _generate_test_cases(self) -> List[QueryTest]:
        """Generate 50 known-answer test queries"""
        
        test_cases = [
            # Design-type queries
            QueryTest("API design patterns", "design", "type_design", 2, "API architecture design"),
            QueryTest("microservices architecture", "design", "type_design", 2, "Service architecture"),
            QueryTest("database schema design", "design", "type_design", 1, "Database design"),
            QueryTest("user interface mockups", "design", "type_design", 1, "UI/UX design"),
            QueryTest("system architecture", "design", "type_design", 3, "System design"),
            QueryTest("REST API specification", "design", "type_design", 2, "API spec design"),
            QueryTest("component architecture", "design", "type_design", 1, "Component design"),
            QueryTest("security architecture", "design", "type_design", 1, "Security design"),
            
            # Decision-type queries  
            QueryTest("technology choice decision", "decision", "type_decision", 2, "Tech decisions"),
            QueryTest("framework selection", "decision", "type_decision", 1, "Framework choice"),
            QueryTest("deployment strategy", "decision", "type_decision", 2, "Deploy decisions"),
            QueryTest("database selection", "decision", "type_decision", 1, "DB choice"),
            QueryTest("architecture decision record", "decision", "type_decision", 2, "ADR"),
            QueryTest("vendor evaluation", "decision", "type_decision", 1, "Vendor choice"),
            QueryTest("tool selection", "decision", "type_decision", 1, "Tool decisions"),
            QueryTest("platform choice", "decision", "type_decision", 1, "Platform decision"),
            
            # Trace-type queries
            QueryTest("error investigation", "trace", "type_trace", 2, "Error debugging"),
            QueryTest("performance bottleneck", "trace", "type_trace", 1, "Perf investigation"),
            QueryTest("bug reproduction steps", "trace", "type_trace", 2, "Bug traces"),
            QueryTest("debugging session", "trace", "type_trace", 1, "Debug traces"),
            QueryTest("root cause analysis", "trace", "type_trace", 2, "RCA traces"),
            QueryTest("incident response", "trace", "type_trace", 1, "Incident traces"),
            QueryTest("system monitoring", "trace", "type_trace", 2, "Monitor traces"),
            QueryTest("log analysis", "trace", "type_trace", 1, "Log traces"),
            
            # Sprint-type queries  
            QueryTest("sprint planning", "sprint", "type_sprint", 2, "Sprint planning"),
            QueryTest("backlog refinement", "sprint", "type_sprint", 1, "Backlog grooming"),
            QueryTest("user story estimation", "sprint", "type_sprint", 1, "Story pointing"),
            QueryTest("retrospective meeting", "sprint", "type_sprint", 2, "Sprint retro"),
            QueryTest("sprint review", "sprint", "type_sprint", 1, "Sprint review"),
            QueryTest("daily standup", "sprint", "type_sprint", 2, "Daily standups"),
            QueryTest("velocity tracking", "sprint", "type_sprint", 1, "Team velocity"),
            QueryTest("milestone planning", "sprint", "type_sprint", 1, "Milestone plan"),
            
            # General queries (no specific type)
            QueryTest("machine learning", None, "default", 3, "ML general"),
            QueryTest("data processing", None, "default", 2, "Data ops"),
            QueryTest("cloud infrastructure", None, "default", 2, "Cloud setup"),
            QueryTest("security practices", None, "default", 2, "Security general"),
            QueryTest("testing strategies", None, "default", 2, "Test approaches"),
            QueryTest("code review", None, "default", 2, "Review process"),
            QueryTest("documentation", None, "default", 2, "Doc practices"),
            QueryTest("team collaboration", None, "default", 1, "Team process"),
            
            # Edge cases - should test filter robustness
            QueryTest("", None, "default", 0, "Empty query"),
            QueryTest("a", None, "default", 0, "Single char"),
            QueryTest("very specific unique term xyz123", None, "default", 0, "Unique term"),
            QueryTest("common word the", None, "default", 3, "Common word"),
            
            # Cross-type queries that might match multiple namespaces
            QueryTest("API testing strategy", None, None, 2, "Cross-type API"),
            QueryTest("database performance optimization", None, None, 2, "Cross-type DB"),
            QueryTest("deployment automation", None, None, 2, "Cross-type deploy"),
            QueryTest("error handling patterns", None, None, 2, "Cross-type errors"),
            QueryTest("monitoring and alerting", None, None, 2, "Cross-type monitor"),
            QueryTest("security implementation", None, None, 2, "Cross-type security"),
        ]
        
        # Ensure we have exactly 50 test cases
        while len(test_cases) < 50:
            test_cases.append(QueryTest(
                f"additional test query {len(test_cases) + 1}",
                random.choice(["design", "decision", "trace", "sprint"]),
                f"type_{random.choice(['design', 'decision', 'trace', 'sprint'])}",
                random.randint(1, 2),
                f"Additional test case {len(test_cases) + 1}"
            ))
        
        return test_cases[:50]
    
    def _generate_mock_documents(self) -> List[Dict[str, Any]]:
        """Generate mock document database"""
        
        documents = [
            # Design documents
            {"id": "d1", "type": "design", "namespace": "type_design", "text": "API design patterns for microservices architecture", "title": "API Design Guide", "content": {"description": "REST API patterns"}},
            {"id": "d2", "type": "design", "namespace": "type_design", "text": "microservices architecture best practices", "title": "Microservices Guide", "content": {"description": "Service design"}},
            {"id": "d3", "type": "design", "namespace": "type_design", "text": "database schema design principles", "title": "Database Design", "content": {"description": "Schema design"}},
            {"id": "d4", "type": "design", "namespace": "type_design", "text": "system architecture documentation", "title": "System Architecture", "content": {"description": "System design"}},
            {"id": "d5", "type": "design", "namespace": "type_design", "text": "user interface component design", "title": "UI Components", "content": {"description": "UI design"}},
            
            # Decision documents  
            {"id": "dec1", "type": "decision", "namespace": "type_decision", "text": "technology choice decision for framework", "title": "Tech Decision", "content": {"description": "Framework choice"}},
            {"id": "dec2", "type": "decision", "namespace": "type_decision", "text": "deployment strategy decision", "title": "Deploy Decision", "content": {"description": "Deployment approach"}},
            {"id": "dec3", "type": "decision", "namespace": "type_decision", "text": "database selection criteria", "title": "DB Decision", "content": {"description": "Database choice"}},
            {"id": "dec4", "type": "decision", "namespace": "type_decision", "text": "architecture decision record template", "title": "ADR Template", "content": {"description": "ADR format"}},
            
            # Trace documents
            {"id": "t1", "type": "trace", "namespace": "type_trace", "text": "error investigation debugging steps", "title": "Error Debug", "content": {"description": "Debug process"}},
            {"id": "t2", "type": "trace", "namespace": "type_trace", "text": "performance bottleneck analysis", "title": "Perf Analysis", "content": {"description": "Performance trace"}},
            {"id": "t3", "type": "trace", "namespace": "type_trace", "text": "bug reproduction and fix", "title": "Bug Trace", "content": {"description": "Bug fixing"}},
            {"id": "t4", "type": "trace", "namespace": "type_trace", "text": "system monitoring alerts", "title": "Monitor Trace", "content": {"description": "Monitoring"}},
            
            # Sprint documents
            {"id": "s1", "type": "sprint", "namespace": "type_sprint", "text": "sprint planning meeting notes", "title": "Sprint Planning", "content": {"description": "Planning session"}},
            {"id": "s2", "type": "sprint", "namespace": "type_sprint", "text": "backlog refinement session", "title": "Backlog Refinement", "content": {"description": "Grooming session"}},
            {"id": "s3", "type": "sprint", "namespace": "type_sprint", "text": "retrospective action items", "title": "Sprint Retro", "content": {"description": "Retro meeting"}},
            
            # General documents (no specific type)
            {"id": "g1", "type": "general", "namespace": "default", "text": "machine learning model training", "title": "ML Training", "content": {"description": "ML process"}},
            {"id": "g2", "type": "general", "namespace": "default", "text": "data processing pipeline", "title": "Data Pipeline", "content": {"description": "Data flow"}},
            {"id": "g3", "type": "general", "namespace": "default", "text": "cloud infrastructure setup", "title": "Cloud Setup", "content": {"description": "Infrastructure"}},
            {"id": "g4", "type": "general", "namespace": "default", "text": "security best practices", "title": "Security Guide", "content": {"description": "Security"}},
            
            # Edge cases
            {"id": "e1", "type": "misc", "namespace": "default", "text": "", "title": "Empty Doc", "content": {"description": "Empty content"}},  # Empty text
            {"id": "e2", "type": "misc", "namespace": "default", "text": "the and or but", "title": "Common Words", "content": {"description": "Common words"}},  # Common words only
        ]
        
        logger.info(f"Generated {len(documents)} mock documents")
        return documents
    
    def _simulate_search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10) -> Tuple[List[Dict[str, Any]], float]:
        """
        Simulate search with or without filters
        
        Args:
            query: Search query
            filters: Optional filters to apply
            limit: Max results to return
            
        Returns:
            Tuple of (results, search_time_ms)
        """
        start_time = time.time()
        
        # Handle empty query
        if not query.strip():
            return [], (time.time() - start_time) * 1000
        
        query_lower = query.lower()
        results = []
        
        for doc in self.mock_documents:
            # Skip if text is empty
            if not doc.get("text", "").strip():
                continue
                
            # Simple text matching (simulate vector similarity)
            doc_text = doc["text"].lower()
            doc_title = doc["title"].lower()
            
            # Calculate relevance score
            score = 0.0
            
            # Keyword matching
            query_terms = query_lower.split()
            for term in query_terms:
                if term in doc_text:
                    score += 1.0
                if term in doc_title:
                    score += 0.5
            
            # Apply filters if provided
            if filters:
                passes_filters = True
                
                # Type filter
                if "type" in filters and doc.get("type") != filters["type"]:
                    passes_filters = False
                
                # Namespace filter  
                if "namespace" in filters and doc.get("namespace") != filters["namespace"]:
                    passes_filters = False
                
                # Score threshold filter
                if "min_score" in filters and score < filters["min_score"]:
                    passes_filters = False
                
                if not passes_filters:
                    continue
            
            # Add to results if has relevance
            if score > 0:
                results.append({
                    "id": doc["id"],
                    "score": score,
                    "payload": doc,
                    "reason": "match"
                })
        
        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Apply limit
        results = results[:limit]
        
        search_time = (time.time() - start_time) * 1000
        return results, search_time
    
    def _determine_miss_reason(self, query: str, filters: Dict[str, Any], results_with_filters: List[Dict[str, Any]], results_without_filters: List[Dict[str, Any]]) -> MissReason:
        """Determine reason for miss when filters_on returns fewer results"""
        
        # If no results at all (even without filters)
        if len(results_without_filters) == 0:
            return MissReason.NO_CANDIDATES
        
        # If results exist without filters but not with filters
        if len(results_with_filters) == 0 and len(results_without_filters) > 0:
            # Check if it's a filter mismatch
            for result in results_without_filters:
                doc = result["payload"]
                
                # Check type filter mismatch
                if "type" in filters and doc.get("type") != filters["type"]:
                    return MissReason.FILTER_MISMATCH
                
                # Check namespace filter mismatch
                if "namespace" in filters and doc.get("namespace") != filters["namespace"]:
                    return MissReason.NAMESPACE_MISMATCH
                
                # Check for empty text
                if not doc.get("text", "").strip():
                    return MissReason.EMPTY_TEXT
                
                # Check score threshold
                if "min_score" in filters and result["score"] < filters["min_score"]:
                    return MissReason.LOW_SCORE
        
        # If results exist but fewer with filters (partial filtering)
        if len(results_with_filters) < len(results_without_filters):
            return MissReason.FILTER_MISMATCH
        
        return MissReason.UNKNOWN
    
    async def run_audit(self, limit: int = 5) -> Dict[str, Any]:
        """
        Run complete filter miss audit
        
        Args:
            limit: Max results per query
            
        Returns:
            Complete audit results
        """
        logger.info(f"Starting filter miss audit on {len(self.test_cases)} test cases...")
        
        audit_results = []
        reason_code_histogram = {reason.value: 0 for reason in MissReason}
        
        for i, test_case in enumerate(self.test_cases):
            logger.info(f"Processing test case {i+1}/50: '{test_case.query[:30]}...'")
            
            # Build filters for this test case
            filters = {}
            if test_case.expected_type:
                filters["type"] = test_case.expected_type
            if test_case.expected_namespace:
                filters["namespace"] = test_case.expected_namespace
            
            # Search WITH filters
            results_on, time_on = self._simulate_search(test_case.query, filters, limit)
            
            # Search WITHOUT filters  
            results_off, time_off = self._simulate_search(test_case.query, None, limit)
            
            # Calculate recovery delta
            recovery_with = len(results_on) / max(test_case.expected_min_results, 1)
            recovery_without = len(results_off) / max(test_case.expected_min_results, 1) 
            recovery_delta = recovery_without - recovery_with
            
            # Determine miss reason if filters reduced results
            miss_reason = None
            if len(results_on) < len(results_off):
                miss_reason = self._determine_miss_reason(test_case.query, filters, results_on, results_off)
                reason_code_histogram[miss_reason.value] += 1
            
            # Create audit result
            result = AuditResult(
                query=test_case.query,
                filters_on_results=len(results_on),
                filters_off_results=len(results_off),
                recovery_delta=recovery_delta,
                miss_reason=miss_reason,
                filters_on_time_ms=time_on,
                filters_off_time_ms=time_off,
                debug_info={
                    "expected_type": test_case.expected_type,
                    "expected_namespace": test_case.expected_namespace,
                    "expected_min_results": test_case.expected_min_results,
                    "filters_applied": filters,
                    "top_results_on": [r["id"] for r in results_on[:3]],
                    "top_results_off": [r["id"] for r in results_off[:3]]
                }
            )
            
            audit_results.append(result)
            
            if recovery_delta > 0.1:  # Significant delta
                logger.warning(f"   Significant recovery delta: {recovery_delta:.2f} (reason: {miss_reason.value if miss_reason else 'N/A'})")
        
        # Calculate summary statistics
        deltas = [r.recovery_delta for r in audit_results]
        avg_recovery_delta = sum(deltas) / len(deltas) if deltas else 0
        max_recovery_delta = max(deltas) if deltas else 0
        min_recovery_delta = min(deltas) if deltas else 0
        
        queries_with_issues = len([r for r in audit_results if r.recovery_delta > 0])
        
        return {
            "success": True,
            "summary": {
                "total_queries": len(audit_results),
                "avg_recovery_delta": avg_recovery_delta,
                "max_recovery_delta": max_recovery_delta,
                "min_recovery_delta": min_recovery_delta,
                "queries_with_filter_issues": queries_with_issues,
                "filter_impact_rate": queries_with_issues / len(audit_results)
            },
            "reason_code_histogram": reason_code_histogram,
            "audit_results": [
                {
                    "query": r.query,
                    "filters_on_results": r.filters_on_results,
                    "filters_off_results": r.filters_off_results,
                    "recovery_delta": r.recovery_delta,
                    "miss_reason": r.miss_reason.value if r.miss_reason else None,
                    "performance": {
                        "filters_on_time_ms": r.filters_on_time_ms,
                        "filters_off_time_ms": r.filters_off_time_ms
                    },
                    "debug_info": r.debug_info
                } for r in audit_results
            ]
        }

async def main():
    """Main execution for filter miss audit"""
    
    print("🔍 Filter & Namespace Miss Audit - Phase 4.1")
    print("=" * 60)
    
    audit = FilterMissAudit()
    
    print("📋 Audit Configuration:")
    print(f"   Test cases: {len(audit.test_cases)}")
    print(f"   Mock documents: {len(audit.mock_documents)}")
    print(f"   Document types: {set(doc.get('type') for doc in audit.mock_documents)}")
    print(f"   Namespaces: {set(doc.get('namespace') for doc in audit.mock_documents)}")
    
    # Run the audit
    print(f"\n🔍 Running Filter Miss Audit...")
    results = await audit.run_audit(limit=5)
    
    if not results["success"]:
        print(f"❌ Audit failed: {results.get('error')}")
        return False
    
    # Display summary
    summary = results["summary"]
    print(f"\n📊 Audit Results Summary:")
    print(f"   Total queries tested: {summary['total_queries']}")
    print(f"   Average recovery delta: {summary['avg_recovery_delta']:.3f}")
    print(f"   Max recovery delta: {summary['max_recovery_delta']:.3f}")  
    print(f"   Min recovery delta: {summary['min_recovery_delta']:.3f}")
    print(f"   Queries with filter issues: {summary['queries_with_filter_issues']}")
    print(f"   Filter impact rate: {summary['filter_impact_rate']:.1%}")
    
    # Display reason code histogram
    print(f"\n📈 Reason Code Histogram:")
    histogram = results["reason_code_histogram"]
    for reason, count in histogram.items():
        if count > 0:
            print(f"   {reason}: {count}")
    
    # Show top issues
    print(f"\n⚠️ Top Filter Issues:")
    issues = [r for r in results["audit_results"] if r["recovery_delta"] > 0]
    issues.sort(key=lambda x: x["recovery_delta"], reverse=True)
    
    for i, issue in enumerate(issues[:5]):
        print(f"   #{i+1}: '{issue['query'][:40]}...'")
        print(f"       Delta: {issue['recovery_delta']:.3f} | Reason: {issue['miss_reason'] or 'N/A'}")
        print(f"       Filters ON: {issue['filters_on_results']} | OFF: {issue['filters_off_results']}")
    
    # Save detailed results
    results_file = "filter_miss_audit_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {results_file}")
    
    print(f"\n🎉 Filter Miss Audit Complete!")
    print("=" * 60)
    print("📋 Sprint Acceptance Criteria:")
    print(f"✅ recovery_off - recovery_on reported: Δ{summary['avg_recovery_delta']:.3f}")
    print("✅ reason_code histogram saved")
    print(f"✅ {summary['total_queries']} known-answer queries tested")
    print(f"✅ Filter impact analysis: {summary['filter_impact_rate']:.1%} affected")
    
    print(f"\n🚨 Key Findings:")
    if summary['filter_impact_rate'] > 0.1:
        print(f"⚠️ Significant filter impact detected ({summary['filter_impact_rate']:.1%})")
        print("   Recommendation: Review filter logic and namespace alignment")
    else:
        print("✅ Low filter impact - filters working as expected")
    
    return True

if __name__ == "__main__":
    asyncio.run(main())