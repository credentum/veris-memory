#!/usr/bin/env python3
"""
Phase 1.5 Validation Test - Enhanced T-101 with Reranker
Test script to validate Phase 1.5 improvements after deployment
"""

import json
import time
import requests
from typing import Dict, List, Any

class Phase15Tester:
    """Test Phase 1.5 improvements on deployed server."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp/call_tool"
        
    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call MCP tool via HTTP."""
        payload = {
            "method": "call_tool", 
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            response = requests.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def store_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Store multiple documents and return their IDs."""
        doc_ids = []
        
        for i, doc in enumerate(documents):
            result = self.call_mcp_tool("store_context", {
                "type": "document",
                "content": doc,
                "metadata": {"doc_id": f"doc-{i+1}.txt", "test": "t101_enhanced"}
            })
            
            if result.get("success"):
                doc_ids.append(f"doc-{i+1}")
            else:
                print(f"Failed to store document {i+1}: {result}")
        
        return doc_ids
    
    def run_enhanced_t101(self) -> Dict[str, Any]:
        """Run enhanced T-101 test with reranker improvements."""
        print("🧪 Running Enhanced T-101: Needle Retrieval with Phase 1.5 Improvements")
        print("=" * 70)
        
        # Create 20 documents with one containing the answer (doc-17)
        documents = []
        
        # Create 16 regular documents (1-16)
        for i in range(1, 17):
            doc = {
                "title": f"Document {i}",
                "text": f"This is document {i} containing general information about various topics including science, technology, history, and literature. The document covers basic concepts and background information that may be relevant for research purposes."
            }
            documents.append(doc)
        
        # Create the NEEDLE document (doc-17) with the specific answer
        needle_doc = {
            "title": "Mars Surface Composition Analysis",
            "text": """Document 17: Detailed Mars Surface Composition Analysis
            
            Mars, the fourth planet from the Sun, has a distinctive reddish appearance that has fascinated astronomers for centuries. Recent scientific analysis of Martian surface samples and spectroscopic data reveals crucial insights about the planet's composition.
            
            The primary component responsible for Mars' red color is iron oxide, commonly known as rust. This mineral makes up the majority of Mars' surface material, giving the planet its characteristic appearance when viewed from space. Iron oxide forms when iron-bearing minerals are exposed to oxygen over extended periods, creating the rusty, reddish compounds that dominate the Martian landscape.
            
            Through various Mars missions including rovers and orbital surveys, scientists have confirmed that iron oxide concentrations are particularly high in the surface regolith. This oxidized iron represents the predominant mineral composition across most of the planet's surface terrain.
            """
        }
        documents.append(needle_doc)
        
        # Create 3 more regular documents (18-20)
        for i in range(18, 21):
            doc = {
                "title": f"Document {i}",
                "text": f"This is document {i} with additional content about research topics, scientific methods, and academic studies. The information presented here provides context for various research areas and methodological approaches."
            }
            documents.append(doc)
        
        # Store all documents
        start_time = time.time()
        doc_ids = self.store_documents(documents)
        storage_time = time.time() - start_time
        
        print(f"📝 Stored {len(doc_ids)} documents in {storage_time:.2f}s")
        
        # Wait a moment for indexing
        time.sleep(2)
        
        # Query for the needle with the exact question from the test spec
        query = "What mineral makes up the majority of Mars' surface?"
        print(f"🔍 Query: '{query}'")
        
        query_start = time.time()
        result = self.call_mcp_tool("retrieve_context", {
            "query": query,
            "limit": 5,
            "search_mode": "hybrid",
            "retrieval_mode": "hybrid"
        })
        query_time = time.time() - query_start
        
        print(f"⏱️  Query completed in {query_time*1000:.2f}ms")
        
        if not result.get("success"):
            return {
                "test_passed": False,
                "error": result.get("error", "Unknown error"),
                "query_time_ms": query_time * 1000
            }
        
        results = result.get("results", [])
        metadata = result.get("graphrag_metadata", {})
        reranker_info = metadata.get("reranker", {})
        
        print(f"\n📊 Results ({len(results)} returned):")
        print("-" * 50)
        
        needle_found_rank = None
        top_hit_id = None
        
        for i, res in enumerate(results):
            rank = i + 1
            
            # Extract document info from payload
            payload = res.get("payload", {})
            content = payload.get("content", {})
            doc_title = content.get("title", "Unknown")
            metadata_info = payload.get("metadata", {})
            doc_id = metadata_info.get("doc_id", f"unknown-{i}")
            
            # Check scores
            original_score = res.get("original_score", res.get("score", 0))
            rerank_score = res.get("rerank_score", None)
            source = res.get("source", "unknown")
            
            print(f"  Rank {rank}: {doc_id} - {doc_title}")
            print(f"           Source: {source}")
            print(f"           Original Score: {original_score:.4f}")
            if rerank_score is not None:
                print(f"           Rerank Score: {rerank_score:.4f}")
            print()
            
            if i == 0:
                top_hit_id = doc_id
            
            if "17" in doc_id or "Mars" in doc_title:
                needle_found_rank = rank
        
        # Calculate metrics
        precision_at_1 = 1.0 if needle_found_rank == 1 else 0.0
        needle_in_top_5 = needle_found_rank is not None and needle_found_rank <= 5
        
        metrics = {
            "query_time_ms": round(query_time * 1000, 2),
            "precision_at_1": precision_at_1,
            "needle_found_rank": needle_found_rank,
            "needle_in_top_5": needle_in_top_5,
            "top_hit_id": top_hit_id,
            "total_results": len(results),
            "reranker_enabled": reranker_info.get("enabled", False),
            "reranker_model": reranker_info.get("model", "N/A"),
            "original_count": reranker_info.get("original_count", len(results)),
            "reranked_count": reranker_info.get("reranked_count", len(results))
        }
        
        # Success criteria
        success = (
            precision_at_1 >= 0.9 and
            query_time * 1000 <= 300 and  # P95 latency target
            needle_found_rank is not None
        )
        
        metrics["test_passed"] = success
        
        print("🎯 Test Analysis:")
        print("-" * 30)
        print(f"Precision@1: {precision_at_1:.3f} (target: ≥0.9)")
        print(f"Needle found at rank: {needle_found_rank if needle_found_rank else 'Not found'}")
        print(f"Query latency: {query_time*1000:.2f}ms (target: ≤300ms)")
        print(f"Top hit: {top_hit_id}")
        
        print(f"\n🔧 Reranker Status:")
        print(f"Enabled: {metrics['reranker_enabled']}")
        if metrics['reranker_enabled']:
            print(f"Model: {metrics['reranker_model']}")
            print(f"Processed: {metrics['original_count']} → {metrics['reranked_count']}")
        
        status = "✅ PASSED" if success else "❌ FAILED"
        improvement = ""
        if precision_at_1 > 0.67:
            improvement = f" (improvement from 0.67 baseline!)"
        
        print(f"\n{status}{improvement}")
        
        return metrics
    
    def run_comparison_test(self) -> Dict[str, Any]:
        """Run A/B comparison between reranker on vs off (if possible)."""
        print("\n" + "="*70)
        print("🔀 A/B Comparison Test: Reranker ON vs OFF")
        print("="*70)
        
        # This would require the ability to toggle reranker via API
        # For now, just report the current test results
        print("Note: Full A/B testing requires reranker toggle capability")
        return {}

def main():
    """Main test execution."""
    tester = Phase15Tester()
    
    print("🚀 Phase 1.5 Validation Test Suite")
    print("="*50)
    print("Testing retrieval improvements:")
    print("• Cross-encoder reranker")
    print("• Hybrid scoring")
    print("• Advanced chunking")
    print("• Optimized Qdrant HNSW")
    print()
    
    # Run enhanced T-101 test
    results = tester.run_enhanced_t101()
    
    # Print final summary
    print("\n" + "="*70)
    print("📋 PHASE 1.5 VALIDATION SUMMARY")
    print("="*70)
    
    print("Test Results:")
    print(f"• Precision@1: {results['precision_at_1']:.3f}")
    print(f"• Query Latency: {results['query_time_ms']:.2f}ms") 
    print(f"• Needle Rank: {results['needle_found_rank'] if results['needle_found_rank'] else 'Not found'}")
    print(f"• Reranker: {'Enabled' if results['reranker_enabled'] else 'Disabled'}")
    
    if results['test_passed']:
        print("\n🎉 SUCCESS: Phase 1.5 improvements validated!")
        print("Ready to proceed to Phase 2 advanced testing.")
    else:
        print("\n⚠️ NEEDS ATTENTION: Phase 1.5 targets not met.")
        if results['precision_at_1'] < 0.9:
            print(f"• Precision@1 ({results['precision_at_1']:.3f}) below target (0.9)")
        if results['query_time_ms'] > 300:
            print(f"• Query latency ({results['query_time_ms']:.2f}ms) above target (300ms)")
    
    # Output JSON for automated processing
    print(f"\n📄 JSON Results:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()