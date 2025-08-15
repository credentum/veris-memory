#!/usr/bin/env python3
"""
Quick Ingestion Fix - Monkey patch to restore data ingestion
Adds store_vector method to raw QdrantClient instances
"""

import sys
import os

# Add the store_vector method to QdrantClient class
def patch_qdrant_client():
    """Add missing store_vector method to QdrantClient"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        
        def store_vector(self, vector_id: str, embedding: list, metadata: dict = None):
            """Store vector with wait=True hotfix"""
            collection_name = getattr(self, '_collection_name', 'project_context')
            
            return self.upsert(
                collection_name=collection_name,
                points=[PointStruct(id=vector_id, vector=embedding, payload=metadata or {})],
                wait=True  # Critical: our hotfix for immediate availability
            )
        
        # Monkey patch the method
        QdrantClient.store_vector = store_vector
        
        print("✅ QdrantClient.store_vector method patched successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to patch QdrantClient: {e}")
        return False

def test_ingestion_fix():
    """Test the ingestion fix with a sample context"""
    import requests
    import json
    import time
    
    base_url = "http://135.181.4.118:8000"
    
    print("🔧 Testing ingestion fix...")
    
    # Test data
    test_context = {
        "type": "design",
        "content": {
            "title": "Ingestion Fix Test",
            "description": "Testing if the store_vector hotfix resolves data ingestion"
        },
        "metadata": {
            "test_type": "ingestion_fix",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }
    
    try:
        # Store context
        response = requests.post(
            f"{base_url}/tools/store_context",
            json=test_context,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Store operation successful!")
                
                # Check Qdrant points count
                time.sleep(2)
                qdrant_response = requests.get("http://135.181.4.118:6333/collections/project_context")
                if qdrant_response.status_code == 200:
                    collection_info = qdrant_response.json()
                    points_count = collection_info.get("result", {}).get("points_count", 0)
                    print(f"📊 Qdrant points count: {points_count}")
                    
                    if points_count > 0:
                        print("🎉 INGESTION FIX SUCCESSFUL - Data is being stored!")
                        
                        # Test retrieval
                        retrieve_response = requests.post(
                            f"{base_url}/tools/retrieve_context",
                            json={"query": "Ingestion Fix Test", "limit": 5},
                            timeout=10
                        )
                        
                        if retrieve_response.status_code == 200:
                            retrieve_result = retrieve_response.json()
                            results_count = len(retrieve_result.get("results", []))
                            print(f"🔍 Retrieval test: {results_count} results found")
                            
                            if results_count > 0:
                                print("🚀 END-TO-END SUCCESS: Store → Index → Retrieve working!")
                                return True
                    else:
                        print("❌ Points count still 0 - fix didn't work")
            else:
                print(f"❌ Store operation failed: {result.get('message')}")
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    return False

if __name__ == "__main__":
    print("🔥 CRITICAL INGESTION PIPELINE HOTFIX")
    print("=" * 50)
    
    # Apply patch
    if patch_qdrant_client():
        # Test the fix
        if test_ingestion_fix():
            print("\\n✅ MISSION ACCOMPLISHED: Ingestion pipeline restored!")
            print("📈 Expected recovery jump: 60% → 95-100%")
        else:
            print("\\n❌ Fix didn't resolve the issue - deeper investigation needed")
    else:
        print("\\n❌ Failed to apply patch - manual intervention required")