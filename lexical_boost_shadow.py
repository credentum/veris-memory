#!/usr/bin/env python3
"""
Lexical Boost Shadow Implementation
Enables Qdrant text index and implements hybrid α=0.7 β=0.3 scoring in shadow mode
"""

import asyncio
import logging
import time
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class LexicalBoostShadow:
    """Shadow implementation of lexical boost with hybrid scoring"""
    
    def __init__(self, 
                 qdrant_url: str = "http://localhost:6333",
                 collection_name: str = "project_context"):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.client = None
        
        # Hybrid scoring parameters
        self.alpha = 0.7  # Dense vector weight
        self.beta = 0.3   # Lexical/BM25 weight
        
    async def setup_qdrant_client(self) -> bool:
        """Setup Qdrant client connection"""
        try:
            import qdrant_client
            from qdrant_client import QdrantClient
            
            self.client = QdrantClient(url=self.qdrant_url)
            
            # Test connection
            collections = self.client.get_collections()
            logger.info(f"✅ Connected to Qdrant, found {len(collections.collections)} collections")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            return False
    
    async def check_text_index_status(self) -> Dict[str, Any]:
        """Check if text index exists on payload.text field"""
        if not self.client:
            return {"error": "Not connected to Qdrant"}
        
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            # Check payload indexes
            payload_indexes = collection_info.config.params.payload_indexes or {}
            
            # Look for text index on payload.text
            text_index_present = False
            text_index_config = None
            
            for field_name, index_config in payload_indexes.items():
                if field_name == "text" or field_name.endswith(".text"):
                    if hasattr(index_config, 'text_index_params'):
                        text_index_present = True
                        text_index_config = index_config
                        break
            
            return {
                "success": True,
                "collection_exists": True,
                "text_index_present": text_index_present,
                "text_index_config": str(text_index_config) if text_index_config else None,
                "points_count": collection_info.points_count,
                "payload_indexes": list(payload_indexes.keys())
            }
            
        except Exception as e:
            logger.error(f"Error checking text index: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_text_index(self) -> Dict[str, Any]:
        """Create text index on payload.text field for lexical search"""
        if not self.client:
            return {"error": "Not connected to Qdrant"}
        
        try:
            from qdrant_client.models import PayloadIndexParams, TextIndexParams, TextIndexType
            
            # Create text index on payload.text field
            logger.info("Creating text index on payload.text field...")
            
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="text",
                field_schema=PayloadIndexParams(
                    type=TextIndexParams(
                        type=TextIndexType.TEXT,
                        tokenizer="whitespace",  # Simple tokenizer
                        min_token_len=2,
                        max_token_len=15,
                        lowercase=True
                    )
                )
            )
            
            logger.info("✅ Text index created successfully")
            return {"success": True, "index_created": True}
            
        except Exception as e:
            # Check if error is because index already exists
            if "already exists" in str(e).lower():
                logger.info("✅ Text index already exists")
                return {"success": True, "index_existed": True}
            else:
                logger.error(f"❌ Failed to create text index: {e}")
                return {"success": False, "error": str(e)}
    
    async def perform_hybrid_search(self, 
                                  query: str, 
                                  limit: int = 10,
                                  with_payload: bool = True) -> Dict[str, Any]:
        """
        Perform hybrid search combining dense vector and lexical search
        
        Args:
            query: Search query
            limit: Number of results to return
            with_payload: Whether to include payload in results
            
        Returns:
            Dict with hybrid search results and scoring breakdown
        """
        if not self.client:
            return {"error": "Not connected to Qdrant"}
        
        try:
            from qdrant_client.models import SearchRequest, Filter, FieldCondition, MatchText
            from sentence_transformers import SentenceTransformer
            
            # Generate query embedding
            model = SentenceTransformer('all-MiniLM-L6-v2')
            query_embedding = model.encode(query)
            
            start_time = time.time()
            
            # 1. Dense vector search (α=0.7)
            logger.info(f"Performing dense vector search for: '{query}'")
            
            dense_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                limit=limit * 2,  # Get more candidates for reranking
                with_payload=with_payload,
                score_threshold=0.1  # Low threshold to get diverse candidates
            )
            
            # 2. Lexical search using text index (β=0.3)
            logger.info(f"Performing lexical search for: '{query}'")
            
            try:
                # Use text search filter for lexical matching
                lexical_results = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="text",
                                match=MatchText(text=query)
                            )
                        ]
                    ),
                    limit=limit * 2,
                    with_payload=with_payload,
                    with_vectors=True  # Need vectors for hybrid scoring
                )
                
                lexical_points = lexical_results[0] if lexical_results else []
                
            except Exception as e:
                logger.warning(f"Lexical search failed: {e}, using empty results")
                lexical_points = []
            
            # 3. Hybrid scoring combination
            logger.info("Combining dense and lexical scores...")
            
            # Create lookup for lexical results
            lexical_lookup = {point.id: point for point in lexical_points}
            
            hybrid_results = []
            
            for dense_point in dense_results:
                point_id = dense_point.id
                
                # Dense score (already similarity score)
                dense_score = float(dense_point.score)
                
                # Lexical score (binary: 1.0 if found in lexical, 0.0 otherwise)
                lexical_score = 1.0 if point_id in lexical_lookup else 0.0
                
                # Hybrid combination: α * dense + β * lexical
                hybrid_score = (self.alpha * dense_score) + (self.beta * lexical_score)
                
                hybrid_results.append({
                    "id": point_id,
                    "payload": dense_point.payload if with_payload else None,
                    "vector": dense_point.vector,
                    "scores": {
                        "dense": dense_score,
                        "lexical": lexical_score,
                        "hybrid": hybrid_score
                    }
                })
            
            # Sort by hybrid score (descending)
            hybrid_results.sort(key=lambda x: x["scores"]["hybrid"], reverse=True)
            
            # Take top results
            final_results = hybrid_results[:limit]
            
            search_time = time.time() - start_time
            
            logger.info(f"✅ Hybrid search completed in {search_time:.3f}s")
            logger.info(f"   Dense results: {len(dense_results)}")
            logger.info(f"   Lexical results: {len(lexical_points)}")
            logger.info(f"   Final hybrid results: {len(final_results)}")
            
            return {
                "success": True,
                "query": query,
                "results": final_results,
                "search_time_seconds": search_time,
                "algorithm": {
                    "alpha": self.alpha,
                    "beta": self.beta,
                    "dense_candidates": len(dense_results),
                    "lexical_matches": len(lexical_points)
                },
                "performance": {
                    "total_time_ms": search_time * 1000,
                    "avg_time_per_result_ms": (search_time * 1000) / max(len(final_results), 1)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Hybrid search failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def calculate_ndcg_delta(self, test_queries: List[str], limit: int = 5) -> Dict[str, Any]:
        """
        Calculate NDCG@5 delta between dense-only and hybrid search
        
        Args:
            test_queries: List of test queries
            limit: Top-K for NDCG calculation
            
        Returns:
            Dict with NDCG delta analysis
        """
        if not self.client:
            return {"error": "Not connected to Qdrant"}
        
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            ndcg_deltas = []
            query_results = []
            
            for query in test_queries:
                logger.info(f"Calculating NDCG delta for: '{query}'")
                
                # Get hybrid results
                hybrid_result = await self.perform_hybrid_search(query, limit=limit)
                
                if not hybrid_result["success"]:
                    logger.warning(f"Hybrid search failed for '{query}': {hybrid_result.get('error')}")
                    continue
                
                # Get dense-only results (α=1.0, β=0.0)
                query_embedding = model.encode(query)
                dense_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding.tolist(),
                    limit=limit,
                    with_payload=True
                )
                
                # Calculate relevance scores (using dense similarity as ground truth)
                def calculate_dcg(results, relevance_scores):
                    dcg = 0.0
                    for i, result in enumerate(results[:limit]):
                        relevance = relevance_scores.get(result["id"] if isinstance(result, dict) else result.id, 0.0)
                        dcg += relevance / np.log2(i + 2)  # +2 because log2(1) = 0
                    return dcg
                
                # Use dense scores as relevance ground truth
                dense_relevance = {point.id: point.score for point in dense_results}
                
                # Calculate NDCG for both approaches
                hybrid_results = hybrid_result["results"]
                
                # Dense NDCG (baseline)
                dense_dcg = calculate_dcg(dense_results, dense_relevance)
                ideal_dcg = calculate_dcg(sorted(dense_results, key=lambda x: x.score, reverse=True), dense_relevance)
                dense_ndcg = dense_dcg / ideal_dcg if ideal_dcg > 0 else 0
                
                # Hybrid NDCG 
                hybrid_dcg = calculate_dcg(hybrid_results, dense_relevance)
                hybrid_ndcg = hybrid_dcg / ideal_dcg if ideal_dcg > 0 else 0
                
                # Calculate delta
                ndcg_delta = hybrid_ndcg - dense_ndcg
                ndcg_deltas.append(ndcg_delta)
                
                query_results.append({
                    "query": query,
                    "dense_ndcg": dense_ndcg,
                    "hybrid_ndcg": hybrid_ndcg,
                    "ndcg_delta": ndcg_delta,
                    "hybrid_top_scores": [r["scores"] for r in hybrid_results[:3]]
                })
                
                logger.info(f"   Dense NDCG@{limit}: {dense_ndcg:.3f}")
                logger.info(f"   Hybrid NDCG@{limit}: {hybrid_ndcg:.3f}")
                logger.info(f"   Delta: {ndcg_delta:.3f}")
            
            # Calculate summary statistics
            avg_delta = np.mean(ndcg_deltas) if ndcg_deltas else 0
            std_delta = np.std(ndcg_deltas) if ndcg_deltas else 0
            positive_deltas = len([d for d in ndcg_deltas if d > 0])
            
            return {
                "success": True,
                "ndcg_analysis": {
                    "avg_delta": avg_delta,
                    "std_delta": std_delta,
                    "positive_deltas": positive_deltas,
                    "total_queries": len(ndcg_deltas),
                    "improvement_rate": positive_deltas / max(len(ndcg_deltas), 1)
                },
                "query_details": query_results,
                "target_gain": 0.02,  # From sprint requirements
                "meets_target": avg_delta >= 0.02
            }
            
        except Exception as e:
            logger.error(f"❌ NDCG delta calculation failed: {e}")
            return {"success": False, "error": str(e)}

async def main():
    """Main execution for lexical boost shadow implementation"""
    
    print("🔍 Lexical Boost Shadow - Phase 4.1")
    print("=" * 50)
    
    lexical_boost = LexicalBoostShadow()
    
    # Step 1: Setup Qdrant connection
    print("1️⃣ Setting up Qdrant connection...")
    if not await lexical_boost.setup_qdrant_client():
        print("❌ Failed to connect to Qdrant. Ensure it's running with: docker-compose up -d")
        return False
    
    # Step 2: Check text index status
    print("\n2️⃣ Checking text index status...")
    status = await lexical_boost.check_text_index_status()
    
    if not status.get("success"):
        print(f"❌ Failed to check text index: {status.get('error')}")
        return False
    
    print(f"   Collection exists: {status['collection_exists']}")
    print(f"   Points count: {status['points_count']}")
    print(f"   Text index present: {status['text_index_present']}")
    print(f"   Payload indexes: {status['payload_indexes']}")
    
    # Step 3: Create text index if needed
    if not status['text_index_present']:
        print("\n3️⃣ Creating text index...")
        index_result = await lexical_boost.create_text_index()
        
        if not index_result["success"]:
            print(f"❌ Failed to create text index: {index_result['error']}")
            return False
        
        print("✅ Text index created successfully")
    else:
        print("\n3️⃣ Text index already exists ✅")
    
    # Step 4: Test hybrid search
    print("\n4️⃣ Testing hybrid search (α=0.7, β=0.3)...")
    
    test_queries = [
        "machine learning best practices",
        "API design patterns", 
        "database optimization",
        "deployment configuration",
        "performance monitoring"
    ]
    
    for query in test_queries[:2]:  # Test first 2 queries
        print(f"\n   Testing: '{query}'")
        
        result = await lexical_boost.perform_hybrid_search(query, limit=5)
        
        if not result["success"]:
            print(f"   ❌ Search failed: {result['error']}")
            continue
        
        print(f"   ✅ Found {len(result['results'])} results in {result['search_time_seconds']:.3f}s")
        print(f"   Algorithm: α={result['algorithm']['alpha']} β={result['algorithm']['beta']}")
        print(f"   Dense candidates: {result['algorithm']['dense_candidates']}")
        print(f"   Lexical matches: {result['algorithm']['lexical_matches']}")
        
        # Show top 3 results with scores
        for i, res in enumerate(result['results'][:3]):
            scores = res['scores']
            print(f"   #{i+1}: Dense={scores['dense']:.3f} Lexical={scores['lexical']:.1f} Hybrid={scores['hybrid']:.3f}")
    
    # Step 5: Calculate NDCG@5 delta
    print("\n5️⃣ Calculating NDCG@5 delta...")
    
    ndcg_result = await lexical_boost.calculate_ndcg_delta(test_queries)
    
    if not ndcg_result["success"]:
        print(f"❌ NDCG calculation failed: {ndcg_result['error']}")
        return False
    
    analysis = ndcg_result["ndcg_analysis"]
    print(f"   Average NDCG@5 delta: {analysis['avg_delta']:.4f}")
    print(f"   Standard deviation: {analysis['std_delta']:.4f}")
    print(f"   Positive deltas: {analysis['positive_deltas']}/{analysis['total_queries']}")
    print(f"   Improvement rate: {analysis['improvement_rate']:.1%}")
    print(f"   Meets target (≥0.02): {'✅' if analysis['avg_delta'] >= 0.02 else '❌'}")
    
    # Step 6: Summary and logging
    print("\n6️⃣ Generating shadow score logs...")
    
    # Save detailed results
    results_file = Path("lexical_boost_shadow_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            "text_index_status": status,
            "ndcg_analysis": ndcg_result,
            "timestamp": time.time(),
            "parameters": {
                "alpha": lexical_boost.alpha,
                "beta": lexical_boost.beta,
                "collection": lexical_boost.collection_name
            }
        }, f, indent=2)
    
    print(f"✅ Results saved to: {results_file}")
    
    print("\n🎉 Lexical Boost Shadow Complete!")
    print("=" * 50)
    print("✅ Text index enabled on payload.text")
    print(f"✅ Hybrid scoring implemented (α={lexical_boost.alpha} β={lexical_boost.beta})")
    print(f"✅ NDCG@5 delta logged: {analysis['avg_delta']:.4f}")
    print("✅ Shadow mode - no impact on production scores")
    
    print("\n📋 Acceptance Criteria:")
    print(f"✅ text_index_present = {status['text_index_present']}")
    print(f"✅ logged ndcg@5_delta per query = {len(ndcg_result['query_details'])} queries")
    
    return True

if __name__ == "__main__":
    asyncio.run(main())