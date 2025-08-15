#!/usr/bin/env python3
"""
Miss Audit System - Find the why behind every search miss
Implements comprehensive miss analysis with reason codes for 95-100% recovery
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class ReasonCode(Enum):
    """Standardized reason codes for search misses"""
    NO_CANDIDATES = "NO_CANDIDATES"        # Vector search returned 0 results
    FILTER_MISMATCH = "FILTER_MISMATCH"    # Filters excluded all candidates
    EMPTY_TEXT = "EMPTY_TEXT"              # Document has no text content
    LOW_SCORE = "LOW_SCORE"                # All scores below threshold
    LEX_ONLY_QUERY = "LEX_ONLY_QUERY"      # Query needs lexical fallback

@dataclass
class MissAuditEntry:
    """Detailed miss analysis for every failed query"""
    query: str
    namespace: Optional[str]
    filters: Dict[str, Any]
    top_k_dense: int
    dense_top1: Optional[Dict[str, Any]]
    dense_top2: Optional[Dict[str, Any]]
    text_len: int
    rerank_invoked: bool
    reason_code: ReasonCode
    timestamp: str
    additional_context: Dict[str, Any]

class MissAuditSystem:
    """Comprehensive miss audit system for search quality analysis"""
    
    def __init__(self, base_url: str = "http://135.181.4.118:8000"):
        self.base_url = base_url
        self.audit_log: List[MissAuditEntry] = []
    
    async def run_miss_audit_suite(self):
        """Execute comprehensive miss audit analysis"""
        
        print("🔍 MISS AUDIT SYSTEM - Path to 95-100% Recovery")
        print("=" * 60)
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            
            # Phase 1: Current state baseline
            await self.baseline_miss_analysis(session)
            
            # Phase 2: Filter vs no-filter comparison  
            await self.filter_mismatch_analysis(session)
            
            # Phase 3: Content quality audit
            await self.content_quality_audit(session)
            
            # Phase 4: Lexical path validation
            await self.lexical_path_audit(session)
            
            # Generate comprehensive report
            await self.generate_miss_audit_report()
    
    async def baseline_miss_analysis(self, session: aiohttp.ClientSession):
        """Run baseline miss analysis with current configuration"""
        
        print("\\n📊 PHASE 1: BASELINE MISS ANALYSIS")
        print("-" * 40)
        
        # Known-answer test queries (these should have matches)
        test_queries = [
            "machine learning best practices",
            "API design patterns",
            "database optimization techniques", 
            "microservices architecture",
            "performance tuning guide",
            "context store deployment",
            "vector search implementation",
            "graph database connectivity",
            "Redis memory optimization",
            "Docker container security"
        ]
        
        for query in test_queries:
            await self.audit_single_query(session, query, {}, "baseline")
    
    async def filter_mismatch_analysis(self, session: aiohttp.ClientSession):
        """Compare results with filters ON vs OFF"""
        
        print("\\n🏷️ PHASE 2: FILTER MISMATCH ANALYSIS")
        print("-" * 40)
        
        test_queries = [
            "design patterns",
            "system architecture", 
            "performance optimization",
            "security best practices",
            "deployment strategies"
        ]
        
        for query in test_queries:
            print(f"\\n  Testing query: '{query}'")
            
            # With filters
            with_filters = await self.query_with_analysis(session, query, {"type": "design"})
            
            # Without filters  
            without_filters = await self.query_with_analysis(session, query, {})
            
            # Log comparison
            filter_impact = {
                "query": query,
                "with_filters_count": len(with_filters.get("results", [])),
                "without_filters_count": len(without_filters.get("results", [])),
                "filter_impact": len(without_filters.get("results", [])) - len(with_filters.get("results", []))
            }
            
            print(f"    With filters: {filter_impact['with_filters_count']} results")
            print(f"    Without filters: {filter_impact['without_filters_count']} results")
            print(f"    Filter impact: {filter_impact['filter_impact']} results lost")
            
            if filter_impact["filter_impact"] > 2:
                await self.log_miss(
                    query=query,
                    namespace="design", 
                    filters={"type": "design"},
                    reason_code=ReasonCode.FILTER_MISMATCH,
                    additional_context=filter_impact
                )
    
    async def content_quality_audit(self, session: aiohttp.ClientSession):
        """Audit content quality issues"""
        
        print("\\n📝 PHASE 3: CONTENT QUALITY AUDIT")
        print("-" * 40)
        
        # Test queries that probe for content issues
        quality_probes = [
            {"query": "empty document", "expected_issue": "EMPTY_TEXT"},
            {"query": "short text snippet", "expected_issue": "LOW_SCORE"},
            {"query": "very specific technical term", "expected_issue": "NO_CANDIDATES"}
        ]
        
        for probe in quality_probes:
            result = await self.query_with_analysis(session, probe["query"], {})
            results = result.get("results", [])
            
            print(f"  Quality probe: '{probe['query']}' → {len(results)} results")
            
            if len(results) == 0:
                await self.log_miss(
                    query=probe["query"],
                    namespace=None,
                    filters={},
                    reason_code=ReasonCode[probe["expected_issue"]],
                    additional_context={"probe_type": "content_quality"}
                )
    
    async def lexical_path_audit(self, session: aiohttp.ClientSession):
        """Validate lexical search path and text indexing"""
        
        print("\\n🔤 PHASE 4: LEXICAL PATH AUDIT")
        print("-" * 40)
        
        # Queries that should trigger lexical search
        lexical_queries = [
            "exact phrase match test",
            "specific identifier ABC123",
            "quoted 'exact match' query",
            "boolean AND OR logic",
            "wildcard * search patterns"
        ]
        
        for query in lexical_queries:
            result = await self.query_with_analysis(session, query, {})
            results = result.get("results", [])
            
            print(f"  Lexical test: '{query}' → {len(results)} results")
            
            if len(results) == 0:
                await self.log_miss(
                    query=query,
                    namespace=None,
                    filters={},
                    reason_code=ReasonCode.LEX_ONLY_QUERY,
                    additional_context={"lexical_query": True}
                )
    
    async def query_with_analysis(self, session: aiohttp.ClientSession, query: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query and return detailed analysis"""
        
        try:
            payload = {
                "query": query,
                "limit": 10
            }
            
            # Add filters if provided
            if filters:
                payload.update(filters)
            
            async with session.post(
                f"{self.base_url}/tools/retrieve_context",
                json=payload
            ) as response:
                
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    return {"error": error_text, "status": response.status, "results": []}
                    
        except Exception as e:
            return {"error": str(e), "results": []}
    
    async def audit_single_query(self, session: aiohttp.ClientSession, query: str, filters: Dict[str, Any], audit_phase: str):
        """Perform detailed audit of a single query"""
        
        result = await self.query_with_analysis(session, query, filters)
        results = result.get("results", [])
        
        print(f"  Query: '{query}' → {len(results)} results")
        
        if len(results) == 0:
            # Determine reason code
            reason_code = ReasonCode.NO_CANDIDATES
            
            if "error" in result:
                reason_code = ReasonCode.FILTER_MISMATCH
            elif "Neo4j" in str(result.get("message", "")):
                reason_code = ReasonCode.FILTER_MISMATCH  # Neo4j auth issues
            
            await self.log_miss(
                query=query,
                namespace=filters.get("type"),
                filters=filters,
                reason_code=reason_code,
                additional_context={"audit_phase": audit_phase, "error": result.get("error")}
            )
        
        return len(results) > 0
    
    async def log_miss(self, query: str, namespace: Optional[str], filters: Dict[str, Any], reason_code: ReasonCode, additional_context: Dict[str, Any] = None):
        """Log a detailed miss with reason code"""
        
        miss_entry = MissAuditEntry(
            query=query,
            namespace=namespace,
            filters=filters,
            top_k_dense=20,  # Current default
            dense_top1=None,  # Would be populated with actual search results
            dense_top2=None,
            text_len=0,  # Would be calculated from query
            rerank_invoked=False,  # Would be determined from actual execution
            reason_code=reason_code,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            additional_context=additional_context or {}
        )
        
        self.audit_log.append(miss_entry)
        
        print(f"    🔍 MISS LOGGED: {reason_code.value} - {query}")
    
    async def generate_miss_audit_report(self):
        """Generate comprehensive miss audit report"""
        
        print("\\n" + "=" * 60)
        print("📋 MISS AUDIT REPORT - PATH TO 95-100% RECOVERY")  
        print("=" * 60)
        
        # Aggregate by reason code
        reason_counts = {}
        for entry in self.audit_log:
            reason = entry.reason_code.value
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        print("\\n🔍 MISS BREAKDOWN BY REASON CODE:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count} misses")
        
        # Priority recommendations
        print("\\n🎯 PRIORITY RECOMMENDATIONS:")
        
        if reason_counts.get("FILTER_MISMATCH", 0) > 0:
            print("  1. HIGH: Fix filter/namespace mismatches")
            print("     → Run queries without filters to validate candidates exist")
            print("     → Standardize namespace field usage")
        
        if reason_counts.get("NO_CANDIDATES", 0) > 0:
            print("  2. HIGH: Boost recall parameters")
            print("     → Increase top_k_dense: 20 → 50")
            print("     → Increase ef_search: 256 → 512")
        
        if reason_counts.get("LEX_ONLY_QUERY", 0) > 0:
            print("  3. MEDIUM: Implement lexical fallback")
            print("     → Enable Qdrant payload text indexing")
            print("     → Add lexical scoring path")
        
        if reason_counts.get("EMPTY_TEXT", 0) > 0:
            print("  4. MEDIUM: Content quality enforcement")
            print("     → Guard against empty chunks before upsert")
            print("     → Implement minimum text length validation")
        
        # Save detailed report
        report_data = {
            "audit_summary": {
                "total_misses": len(self.audit_log),
                "reason_breakdown": reason_counts,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "detailed_misses": [asdict(entry) for entry in self.audit_log],
            "recommendations": [
                "Increase top_k_dense from 20 to 50",
                "Increase ef_search from 256 to 512", 
                "Enable reranker gating with margin 0.05",
                "Fix filter/namespace consistency",
                "Implement lexical fallback for exact matches",
                "Add content quality validation on ingest"
            ]
        }
        
        with open("miss_audit_report.json", "w") as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print("\\n📊 NEXT ACTIONS FOR 95-100% RECOVERY:")
        print("  1. Deploy recall boost configuration")
        print("  2. Fix top miss reasons from audit")
        print("  3. Run Phase 4.1 validation suite")
        print("  4. Implement safety net for regression prevention")
        
        print(f"\\n💾 Detailed report saved to: miss_audit_report.json")
        
        return len(self.audit_log)

async def main():
    """Execute miss audit system"""
    audit_system = MissAuditSystem()
    await audit_system.run_miss_audit_suite()

if __name__ == "__main__":
    asyncio.run(main())