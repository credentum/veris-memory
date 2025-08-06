#!/usr/bin/env python3
"""
Quick test to verify the extracted components can be imported
"""

try:
    print("Testing imports...")

    # Test storage imports
    from storage.hash_diff_embedder import (  # noqa: F401
        DocumentHash,
        EmbeddingTask,
        HashDiffEmbedder,
    )

    print("✓ hash_diff_embedder imports successful")

    from storage.neo4j_client import Neo4jInitializer  # noqa: F401

    print("✓ neo4j_client imports successful")

    from storage.qdrant_client import VectorDBInitializer  # noqa: F401

    print("✓ qdrant_client imports successful")

    from storage.kv_store import ContextKV  # noqa: F401

    print("✓ kv_store imports successful")

    # Test core imports
    from core.base_component import DatabaseComponent  # noqa: F401

    print("✓ base_component imports successful")

    from core.utils import get_secure_connection_config  # noqa: F401

    print("✓ utils imports successful")

    # Test validator imports
    from validators.kv_validators import validate_redis_key  # noqa: F401

    print("✓ validators imports successful")

    print("\n✅ All imports successful!")

except ImportError as e:
    print(f"\n❌ Import error: {e}")
    exit(1)
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    exit(1)
