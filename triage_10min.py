#!/usr/bin/env python3
"""
10-minute triage checklist for production issues
Focus: Qdrant sanity, namespace/filter, Neo4j auth, reranker latency
"""

import asyncio
import aiohttp
import json
import time

class ProductionTriage:
    def __init__(self):
        self.base_url = "http://135.181.4.118:8000"
        self.issues = []
        self.fixes = []
    
    async def run_triage(self):
        print("🔍 10-Minute Production Triage")
        print("=" * 50)
        
        async with aiohttp.ClientSession() as session:
            await self.qdrant_sanity_check(session)
            await self.namespace_filter_check(session)
            await self.neo4j_auth_check(session)
            await self.reranker_timing_check(session)
        
        self.print_summary()
    
    async def qdrant_sanity_check(self, session):
        """1. Qdrant sanity - collections, vectors, indexing"""
        print("\n🔎 1. QDRANT SANITY CHECK")
        print("-" * 30)
        
        # Try direct Qdrant API (might not be exposed)
        try:
            async with session.get(f"{self.base_url}/debug/qdrant") as response:
                if response.status == 404:
                    print("❌ No Qdrant debug endpoint - need SSH access")
                    self.issues.append("No Qdrant API access - need server debug endpoint")
                else:
                    result = await response.json()
                    print(f"✅ Qdrant debug: {result}")
        except:
            print("❌ No direct Qdrant access")
            self.issues.append("Need Qdrant direct access for collection inspection")
        
        # Test indexing with known ID
        print("Testing store→retrieve with known ID...")
        test_id = f"triage_test_{int(time.time())}"
        
        # Store with unique content
        store_success = False
        try:
            async with session.post(
                f"{self.base_url}/tools/store_context",
                json={
                    "type": "trace",
                    "content": {
                        "title": f"Triage Test {test_id}",
                        "unique_marker": test_id,
                        "description": "Testing immediate retrieval"
                    },
                    "metadata": {"test_id": test_id}
                }
            ) as response:
                store_success = response.status == 200
                print(f"Store result: {response.status}")
        except Exception as e:
            print(f"Store error: {e}")
        
        if store_success:
            # Wait for indexing
            await asyncio.sleep(3)
            
            # Try to retrieve immediately
            async with session.post(
                f"{self.base_url}/tools/retrieve_context",
                json={
                    "query": f"Triage Test {test_id}",
                    "limit": 5
                }
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    found = any(test_id in str(r) for r in results)
                    if found:
                        print("✅ Store→retrieve working!")
                    else:
                        print("❌ Stored but not retrieved - indexing issue")
                        self.issues.append("Qdrant indexing: stored contexts not immediately retrievable")
                        self.fixes.append("Add wait=True to Qdrant upsert calls")
                else:
                    print(f"❌ Retrieve failed: {response.status}")
                    self.issues.append(f"Retrieve API failing: {response.status}")
    
    async def namespace_filter_check(self, session):
        """2. Namespace/filter consistency"""
        print("\n🏷️  2. NAMESPACE/FILTER CHECK")  
        print("-" * 30)
        
        # Store contexts with different types to test filtering
        test_types = ["design", "decision", "trace"]
        stored_ids = []
        
        for ctx_type in test_types:
            test_id = f"filter_test_{ctx_type}_{int(time.time())}"
            try:
                async with session.post(
                    f"{self.base_url}/tools/store_context",
                    json={
                        "type": ctx_type,
                        "content": {
                            "title": f"Filter Test {ctx_type}",
                            "marker": test_id
                        },
                        "metadata": {"filter_test": True}
                    }
                ) as response:
                    if response.status == 200:
                        stored_ids.append((ctx_type, test_id))
                        print(f"✅ Stored {ctx_type}")
                    else:
                        print(f"❌ Failed to store {ctx_type}: {response.status}")
            except Exception as e:
                print(f"❌ Store error for {ctx_type}: {e}")
        
        await asyncio.sleep(2)
        
        # Try broad retrieval to see if any contexts come back
        try:
            async with session.post(
                f"{self.base_url}/tools/retrieve_context",
                json={
                    "query": "Filter Test",
                    "limit": 10
                }
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    retrieved_count = len(results)
                    print(f"📊 Retrieved {retrieved_count} contexts")
                    
                    if retrieved_count == 0:
                        print("❌ No contexts retrieved despite successful storage")
                        self.issues.append("Namespace/filter mismatch or indexing failure")
                        self.fixes.append("Check collection namespace consistency")
                        self.fixes.append("Temporarily disable all filters for testing")
                    else:
                        print("✅ Some contexts retrievable")
                else:
                    print(f"❌ Retrieve failed: {response.status}")
        except Exception as e:
            print(f"❌ Retrieval test error: {e}")
    
    async def neo4j_auth_check(self, session):
        """3. Neo4j authentication diagnosis"""
        print("\n🔐 3. NEO4J AUTH CHECK")
        print("-" * 30)
        
        # Check server status for Neo4j
        try:
            async with session.get(f"{self.base_url}/status") as response:
                if response.status == 200:
                    status = await response.json()
                    neo4j_status = status.get("deps", {}).get("neo4j", "unknown")
                    print(f"Neo4j status: {neo4j_status}")
                    
                    if neo4j_status == "error":
                        print("❌ Neo4j authentication confirmed failed")
                        self.issues.append("Neo4j authentication failure")
                        self.fixes.append("Fix NEO4J_AUTH env var or create RO user")
                        self.fixes.append("Use either NEO4J_AUTH=neo4j/<pw> OR NEO4J_USER/PASSWORD, not both")
                    else:
                        print("✅ Neo4j status looks ok")
        except:
            print("❌ Could not check Neo4j status")
        
        # Try graph query to see specific error
        try:
            async with session.post(
                f"{self.base_url}/tools/query_graph",
                json={
                    "query": "test relationships",
                    "limit": 1
                }
            ) as response:
                if response.status == 200:
                    print("✅ Graph query successful")
                else:
                    print(f"❌ Graph query failed: {response.status}")
                    error_text = await response.text()
                    if "unauthorized" in error_text.lower() or "authentication" in error_text.lower():
                        print("🎯 Confirmed: Neo4j authentication issue")
                        self.fixes.append("SSH to server and fix Neo4j credentials")
        except Exception as e:
            print(f"❌ Graph query error: {e}")
    
    async def reranker_timing_check(self, session):
        """4. Reranker latency analysis"""
        print("\n⚡ 4. RERANKER TIMING CHECK")
        print("-" * 30)
        
        # Test query with timing
        timings = []
        for i in range(3):
            start_time = time.time()
            try:
                async with session.post(
                    f"{self.base_url}/tools/retrieve_context",
                    json={
                        "query": f"timing test query {i}",
                        "limit": 10  # Moderate limit
                    }
                ) as response:
                    latency = (time.time() - start_time) * 1000
                    timings.append(latency)
                    print(f"Query {i+1}: {latency:.1f}ms")
                    
                    if latency > 500:
                        print(f"⚠️  High latency: {latency:.1f}ms")
            except Exception as e:
                print(f"❌ Timing test {i+1} failed: {e}")
                timings.append(9999)
        
        if timings:
            avg_latency = sum(timings) / len(timings)
            print(f"📊 Average latency: {avg_latency:.1f}ms")
            
            if avg_latency > 800:
                print("❌ Excessive latency detected")
                self.issues.append(f"High latency: {avg_latency:.1f}ms avg")
                self.fixes.append("Add reranker gating: only rerank when score_gap < 0.05")
                self.fixes.append("Reduce RERANK_TOP_K to 10")
                self.fixes.append("Add stage timing logs: embed_ms, dense_ms, rerank_ms")
                self.fixes.append("Batch reranker calls and clamp text ≤512 tokens")
            else:
                print("✅ Latency acceptable")
    
    def print_summary(self):
        """Print triage summary"""
        print("\n" + "=" * 50)
        print("🏥 TRIAGE SUMMARY")
        print("=" * 50)
        
        print(f"\n❌ ISSUES FOUND ({len(self.issues)}):")
        for i, issue in enumerate(self.issues, 1):
            print(f"{i}. {issue}")
        
        print(f"\n🔧 RECOMMENDED FIXES ({len(self.fixes)}):")
        for i, fix in enumerate(self.fixes, 1):
            print(f"{i}. {fix}")
        
        print("\n🚀 IMMEDIATE ACTIONS:")
        print("1. SSH to hetzner-server and check Qdrant collections directly")
        print("2. Add wait=True to all Qdrant upsert operations")
        print("3. Fix Neo4j authentication environment variables")
        print("4. Add reranker performance gating and reduce top_k")
        
        print(f"\n📋 PRIORITY: {'HIGH' if len(self.issues) > 2 else 'MEDIUM'}")
        print("Focus on search pipeline first (biggest impact)")

async def main():
    triage = ProductionTriage()
    await triage.run_triage()

if __name__ == "__main__":
    asyncio.run(main())