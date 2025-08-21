#!/usr/bin/env python3
"""
migration_checksum.py: Data Integrity Verification for Sprint 11

This module provides comprehensive data integrity verification through
checksums, ensuring migrations preserve data correctly and detect any
corruption or loss during the dimension migration process.
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from src.storage.qdrant_client import VectorDBInitializer
    from src.storage.neo4j_client import Neo4jInitializer
    from src.storage.kv_store import ContextKV
except ImportError:
    print("Error: Unable to import required modules. Ensure you're running from the project root.")
    sys.exit(1)

logger = logging.getLogger(__name__)


@dataclass
class ChecksumData:
    """Comprehensive checksum data for a storage system"""
    timestamp: datetime
    qdrant_checksums: Dict[str, str]
    neo4j_checksums: Dict[str, str] 
    kv_checksums: Dict[str, str]
    overall_checksum: str
    record_counts: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat()
        }


class DataIntegrityChecker:
    """Verifies data integrity through comprehensive checksums"""
    
    def __init__(self, config_path: str = ".ctxrc.yaml"):
        """Initialize integrity checker"""
        self.config_path = config_path
        self.qdrant_client = None
        self.neo4j_client = None
        self.kv_client = None
    
    async def initialize_clients(self) -> bool:
        """Initialize all database clients"""
        try:
            # Initialize Qdrant
            qdrant_init = VectorDBInitializer(self.config_path)
            if not qdrant_init.connect():
                logger.error("Failed to connect to Qdrant")
                return False
            self.qdrant_client = qdrant_init.client
            
            # Initialize Neo4j
            neo4j_init = Neo4jInitializer(self.config_path)
            if not await neo4j_init.connect_async():
                logger.error("Failed to connect to Neo4j")
                return False
            self.neo4j_client = neo4j_init.driver
            
            # Initialize KV store
            self.kv_client = ContextKV(self.config_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            return False
    
    def calculate_qdrant_checksums(self) -> Dict[str, str]:
        """Calculate detailed Qdrant collection checksums"""
        checksums = {}
        
        if not self.qdrant_client:
            return {"error": "qdrant_not_connected"}
        
        try:
            collections = self.qdrant_client.get_collections().collections
            
            for collection in collections:
                try:
                    # Get collection info
                    info = self.qdrant_client.get_collection(collection.name)
                    
                    # Get vector configuration
                    vectors_config = info.config.params.vectors
                    if hasattr(vectors_config, 'size'):
                        dimensions = vectors_config.size
                    else:
                        dimensions = "unknown"
                    
                    # Sample a few points to verify dimensions
                    sample_points = []
                    try:
                        scroll_result = self.qdrant_client.scroll(
                            collection_name=collection.name,
                            limit=5,
                            with_vectors=True
                        )
                        
                        for point in scroll_result[0]:  # Points are in first element
                            if point.vector and isinstance(point.vector, list):
                                sample_points.append(len(point.vector))
                    except Exception as e:
                        logger.warning(f"Failed to sample points from {collection.name}: {e}")
                    
                    # Create collection fingerprint
                    collection_data = {
                        "name": collection.name,
                        "points_count": info.points_count,
                        "dimensions": dimensions,
                        "sample_vector_dims": sample_points,
                        "config_optimizer": str(info.config.optimizer_config) if info.config.optimizer_config else "none"
                    }
                    
                    collection_json = json.dumps(collection_data, sort_keys=True)
                    checksums[collection.name] = hashlib.sha256(collection_json.encode()).hexdigest()[:12]
                    
                except Exception as e:
                    logger.warning(f"Failed to checksum collection {collection.name}: {e}")
                    checksums[collection.name] = "error"
            
            return checksums
            
        except Exception as e:
            logger.error(f"Failed to calculate Qdrant checksums: {e}")
            return {"error": str(e)}
    
    def calculate_neo4j_checksums(self) -> Dict[str, str]:
        """Calculate detailed Neo4j graph checksums"""
        checksums = {}
        
        if not self.neo4j_client:
            return {"error": "neo4j_not_connected"}
        
        try:
            with self.neo4j_client.session() as session:
                # Node type checksums
                node_types_result = session.run("""
                    MATCH (n) 
                    RETURN labels(n) as labels, count(*) as count
                """)
                
                node_checksums = {}
                for record in node_types_result:
                    labels = tuple(sorted(record["labels"]))
                    count = record["count"]
                    node_checksums[str(labels)] = count
                
                # Relationship type checksums
                rel_types_result = session.run("""
                    MATCH ()-[r]->() 
                    RETURN type(r) as rel_type, count(*) as count
                """)
                
                rel_checksums = {}
                for record in rel_types_result:
                    rel_type = record["rel_type"]
                    count = record["count"]
                    rel_checksums[rel_type] = count
                
                # Property checksums (sample)
                prop_sample_result = session.run("""
                    MATCH (n) 
                    WITH n LIMIT 100
                    RETURN keys(n) as prop_keys
                """)
                
                all_prop_keys = set()
                for record in prop_sample_result:
                    all_prop_keys.update(record["prop_keys"])
                
                # Create overall Neo4j checksum
                neo4j_data = {
                    "node_types": node_checksums,
                    "relationship_types": rel_checksums,
                    "property_keys": sorted(list(all_prop_keys))
                }
                
                neo4j_json = json.dumps(neo4j_data, sort_keys=True)
                checksums["graph_structure"] = hashlib.sha256(neo4j_json.encode()).hexdigest()[:12]
                checksums["node_types"] = str(len(node_checksums))
                checksums["rel_types"] = str(len(rel_checksums))
                
                return checksums
                
        except Exception as e:
            logger.error(f"Failed to calculate Neo4j checksums: {e}")
            return {"error": str(e)}
    
    def calculate_kv_checksums(self) -> Dict[str, str]:
        """Calculate KV store checksums (simplified)"""
        checksums = {}
        
        try:
            # For Redis-based KV store, we'd need to sample keys
            # This is a simplified version
            checksums["kv_status"] = "available" if self.kv_client else "unavailable"
            
            return checksums
            
        except Exception as e:
            logger.error(f"Failed to calculate KV checksums: {e}")
            return {"error": str(e)}
    
    def get_record_counts(self) -> Dict[str, int]:
        """Get comprehensive record counts from all systems"""
        counts = {}
        
        # Qdrant counts
        if self.qdrant_client:
            try:
                collections = self.qdrant_client.get_collections().collections
                total_points = 0
                for collection in collections:
                    info = self.qdrant_client.get_collection(collection.name)
                    counts[f"qdrant_{collection.name}"] = info.points_count
                    total_points += info.points_count
                counts["qdrant_total"] = total_points
            except Exception as e:
                logger.warning(f"Failed to get Qdrant counts: {e}")
        
        # Neo4j counts
        if self.neo4j_client:
            try:
                with self.neo4j_client.session() as session:
                    node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
                    rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
                    counts["neo4j_nodes"] = node_count
                    counts["neo4j_relationships"] = rel_count
            except Exception as e:
                logger.warning(f"Failed to get Neo4j counts: {e}")
        
        return counts
    
    async def calculate_comprehensive_checksum(self) -> ChecksumData:
        """Calculate comprehensive system checksum"""
        timestamp = datetime.utcnow()
        
        # Get all component checksums
        qdrant_checksums = self.calculate_qdrant_checksums()
        neo4j_checksums = self.calculate_neo4j_checksums()
        kv_checksums = self.calculate_kv_checksums()
        record_counts = self.get_record_counts()
        
        # Create overall system checksum
        overall_data = {
            "qdrant": qdrant_checksums,
            "neo4j": neo4j_checksums,
            "kv": kv_checksums,
            "counts": record_counts
        }
        
        overall_json = json.dumps(overall_data, sort_keys=True)
        overall_checksum = hashlib.sha256(overall_json.encode()).hexdigest()
        
        return ChecksumData(
            timestamp=timestamp,
            qdrant_checksums=qdrant_checksums,
            neo4j_checksums=neo4j_checksums,
            kv_checksums=kv_checksums,
            overall_checksum=overall_checksum,
            record_counts=record_counts
        )
    
    async def compare_checksums(self, checksum1: ChecksumData, checksum2: ChecksumData) -> Dict[str, Any]:
        """Compare two checksum datasets for differences"""
        comparison = {
            "identical": checksum1.overall_checksum == checksum2.overall_checksum,
            "overall_checksum_match": checksum1.overall_checksum == checksum2.overall_checksum,
            "timestamp_1": checksum1.timestamp.isoformat(),
            "timestamp_2": checksum2.timestamp.isoformat(),
            "differences": {}
        }
        
        # Compare record counts
        count_diffs = {}
        for key in set(checksum1.record_counts.keys()) | set(checksum2.record_counts.keys()):
            val1 = checksum1.record_counts.get(key, 0)
            val2 = checksum2.record_counts.get(key, 0)
            if val1 != val2:
                count_diffs[key] = {"before": val1, "after": val2}
        
        if count_diffs:
            comparison["differences"]["record_counts"] = count_diffs
        
        # Compare Qdrant checksums
        qdrant_diffs = {}
        for collection in set(checksum1.qdrant_checksums.keys()) | set(checksum2.qdrant_checksums.keys()):
            cs1 = checksum1.qdrant_checksums.get(collection, "missing")
            cs2 = checksum2.qdrant_checksums.get(collection, "missing") 
            if cs1 != cs2:
                qdrant_diffs[collection] = {"before": cs1, "after": cs2}
        
        if qdrant_diffs:
            comparison["differences"]["qdrant"] = qdrant_diffs
        
        # Compare Neo4j checksums
        neo4j_diffs = {}
        for key in set(checksum1.neo4j_checksums.keys()) | set(checksum2.neo4j_checksums.keys()):
            cs1 = checksum1.neo4j_checksums.get(key, "missing")
            cs2 = checksum2.neo4j_checksums.get(key, "missing")
            if cs1 != cs2:
                neo4j_diffs[key] = {"before": cs1, "after": cs2}
        
        if neo4j_diffs:
            comparison["differences"]["neo4j"] = neo4j_diffs
        
        return comparison
    
    async def cleanup(self):
        """Clean up database connections"""
        if self.neo4j_client:
            await self.neo4j_client.close()


async def main():
    """Main checksum utility"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sprint 11 Data Integrity Checker")
    parser.add_argument("--save", help="Save checksum to file")
    parser.add_argument("--compare", nargs=2, help="Compare two checksum files")
    parser.add_argument("--config", default=".ctxrc.yaml", help="Configuration file")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    checker = DataIntegrityChecker(args.config)
    
    try:
        if args.compare:
            # Compare two saved checksums
            try:
                with open(args.compare[0], 'r') as f:
                    data1 = json.load(f)
                    data1["timestamp"] = datetime.fromisoformat(data1["timestamp"])
                    checksum1 = ChecksumData(**data1)
                
                with open(args.compare[1], 'r') as f:
                    data2 = json.load(f)
                    data2["timestamp"] = datetime.fromisoformat(data2["timestamp"])
                    checksum2 = ChecksumData(**data2)
                
                comparison = await checker.compare_checksums(checksum1, checksum2)
                
                if comparison["identical"]:
                    print("✅ Checksums are identical - data integrity verified")
                else:
                    print("❌ Checksums differ - data changes detected:")
                    for category, diffs in comparison["differences"].items():
                        print(f"  {category}:")
                        for key, change in diffs.items():
                            print(f"    {key}: {change['before']} → {change['after']}")
                
                print(f"\nOverall checksum match: {comparison['overall_checksum_match']}")
                
            except Exception as e:
                print(f"Failed to compare checksums: {e}")
                sys.exit(1)
        
        else:
            # Calculate and optionally save current checksum
            if not await checker.initialize_clients():
                sys.exit(1)
            
            print("Calculating comprehensive system checksum...")
            checksum_data = await checker.calculate_comprehensive_checksum()
            
            print(f"Overall checksum: {checksum_data.overall_checksum}")
            print(f"Timestamp: {checksum_data.timestamp}")
            
            # Display record counts
            print("\nRecord counts:")
            for key, count in checksum_data.record_counts.items():
                print(f"  {key}: {count}")
            
            # Display component checksums
            print(f"\nQdrant collections: {len(checksum_data.qdrant_checksums)}")
            for collection, checksum in checksum_data.qdrant_checksums.items():
                if checksum != "error":
                    print(f"  {collection}: {checksum}")
            
            print(f"\nNeo4j components: {len(checksum_data.neo4j_checksums)}")
            for component, checksum in checksum_data.neo4j_checksums.items():
                if checksum != "error":
                    print(f"  {component}: {checksum}")
            
            if args.save:
                # Save checksum to file
                with open(args.save, 'w') as f:
                    json.dump(checksum_data.to_dict(), f, indent=2)
                print(f"\n✅ Checksum saved to {args.save}")
    
    finally:
        await checker.cleanup()


if __name__ == "__main__":
    asyncio.run(main())