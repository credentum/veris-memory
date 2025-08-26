#!/usr/bin/env python3
"""
Data migration and backfill system for Veris Memory Phase 3.

This module provides comprehensive data migration capabilities including:
- Backfilling existing data to new text search backend
- Migrating data between storage backends
- Validation and verification of migrated data
- Progress tracking and error recovery
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple, Iterator
from dataclasses import dataclass
from enum import Enum

from ..backends.text_backend import TextSearchBackend, get_text_backend, initialize_text_backend
from ..storage.qdrant_client import VectorDBInitializer
from ..storage.neo4j_client import Neo4jInitializer  
from ..storage.kv_store import KVStore
from ..interfaces.memory_result import MemoryResult


logger = logging.getLogger(__name__)


class MigrationStatus(str, Enum):
    """Status values for migration operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class MigrationSource(str, Enum):
    """Source systems for migration."""
    QDRANT = "qdrant"
    NEO4J = "neo4j"
    REDIS = "redis"
    ALL = "all"


@dataclass
class MigrationJob:
    """Configuration for a migration job."""
    job_id: str
    source: MigrationSource
    target_backend: str  # "text", "vector", "graph", etc.
    batch_size: int = 100
    max_concurrent: int = 5
    filters: Optional[Dict[str, Any]] = None
    dry_run: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: MigrationStatus = MigrationStatus.PENDING
    processed_count: int = 0
    success_count: int = 0
    error_count: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    source_id: str
    target_id: Optional[str]
    success: bool
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DataMigrationEngine:
    """
    Core engine for data migration and backfill operations.
    
    Handles migration of data between different storage backends with
    support for batching, concurrency control, error recovery, and progress tracking.
    """
    
    def __init__(
        self,
        qdrant_client: Optional[VectorDBInitializer] = None,
        neo4j_client: Optional[Neo4jInitializer] = None,
        kv_store: Optional[KVStore] = None,
        text_backend: Optional[TextSearchBackend] = None
    ):
        """
        Initialize the migration engine.
        
        Args:
            qdrant_client: Vector database client
            neo4j_client: Graph database client
            kv_store: Key-value store client
            text_backend: Text search backend
        """
        self.qdrant_client = qdrant_client
        self.neo4j_client = neo4j_client
        self.kv_store = kv_store
        self.text_backend = text_backend or get_text_backend()
        
        self.active_jobs: Dict[str, MigrationJob] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
    
    async def migrate_data(self, job: MigrationJob) -> MigrationJob:
        """
        Execute a data migration job.
        
        Args:
            job: Migration job configuration
            
        Returns:
            Updated job with results
        """
        logger.info(f"Starting migration job {job.job_id}: {job.source} -> {job.target_backend}")
        
        # Register job
        self.active_jobs[job.job_id] = job
        job.status = MigrationStatus.RUNNING
        job.started_at = datetime.now()
        
        try:
            # Create concurrency semaphore
            self._semaphores[job.job_id] = asyncio.Semaphore(job.max_concurrent)
            
            # Execute migration based on source
            if job.source == MigrationSource.QDRANT:
                await self._migrate_from_qdrant(job)
            elif job.source == MigrationSource.NEO4J:
                await self._migrate_from_neo4j(job)
            elif job.source == MigrationSource.REDIS:
                await self._migrate_from_redis(job)
            elif job.source == MigrationSource.ALL:
                await self._migrate_from_all_sources(job)
            else:
                raise ValueError(f"Unsupported source: {job.source}")
            
            # Mark as completed
            job.status = MigrationStatus.COMPLETED if job.error_count == 0 else MigrationStatus.PARTIAL
            job.completed_at = datetime.now()
            
            logger.info(
                f"Migration job {job.job_id} completed: "
                f"{job.success_count}/{job.processed_count} successful, "
                f"{job.error_count} errors"
            )
            
        except Exception as e:
            job.status = MigrationStatus.FAILED
            job.errors.append(f"Job failed: {str(e)}")
            logger.error(f"Migration job {job.job_id} failed: {e}")
            
        finally:
            # Cleanup
            if job.job_id in self._semaphores:
                del self._semaphores[job.job_id]
        
        return job
    
    async def _migrate_from_qdrant(self, job: MigrationJob) -> None:
        """Migrate data from Qdrant vector database."""
        if not self.qdrant_client:
            raise ValueError("Qdrant client not available")
        
        if job.target_backend != "text":
            raise ValueError(f"Migration from Qdrant to {job.target_backend} not supported")
        
        if not self.text_backend:
            raise ValueError("Text backend not available")
        
        logger.info("Starting Qdrant to text backend migration")
        
        # Get all vectors from Qdrant
        try:
            # Use scroll to get all points in batches
            collection_name = getattr(job, 'collection_name', "context_embeddings")  # Configurable collection name
            # Add memory usage monitoring for large batches
            if job.batch_size > 1000:
                logger.warning(f"Large batch size {job.batch_size} may cause memory issues")
            
            scroll_result = self.qdrant_client.client.scroll(
                collection_name=collection_name,
                limit=min(job.batch_size, 1000),  # Cap batch size to prevent memory issues
                with_payload=True,
                with_vectors=False  # We don't need vectors for text indexing
            )
            
            points = scroll_result[0]  # First element is the list of points
            next_page_offset = scroll_result[1]  # Second element is next page offset
            
            # Process first batch
            if points:
                await self._process_qdrant_batch(job, points)
            
            # Continue with remaining batches
            while next_page_offset:
                scroll_result = self.qdrant_client.client.scroll(
                    collection_name=collection_name,
                    limit=job.batch_size,
                    offset=next_page_offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                points = scroll_result[0]
                next_page_offset = scroll_result[1]
                
                if points:
                    await self._process_qdrant_batch(job, points)
                else:
                    break
                    
        except Exception as e:
            logger.error(f"Error migrating from Qdrant: {e}")
            job.errors.append(f"Qdrant migration error: {str(e)}")
    
    async def _process_qdrant_batch(self, job: MigrationJob, points: List[Any]) -> None:
        """Process a batch of points from Qdrant."""
        tasks = []
        
        for point in points:
            task = self._migrate_qdrant_point(job, point)
            tasks.append(task)
        
        # Execute batch concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                job.error_count += 1
                job.errors.append(f"Point migration error: {str(result)}")
            elif isinstance(result, MigrationResult):
                if result.success:
                    job.success_count += 1
                else:
                    job.error_count += 1
                    if result.error_message:
                        job.errors.append(result.error_message)
            
            job.processed_count += 1
    
    async def _migrate_qdrant_point(self, job: MigrationJob, point: Any) -> MigrationResult:
        """Migrate a single point from Qdrant to text backend."""
        async with self._semaphores[job.job_id]:
            start_time = time.time()
            
            try:
                point_id = str(point.id)
                payload = point.payload or {}
                
                # Extract text content from payload
                text_content = self._extract_text_from_payload(payload)
                if not text_content:
                    return MigrationResult(
                        source_id=point_id,
                        target_id=None,
                        success=False,
                        error_message="No text content found in payload"
                    )
                
                # Extract metadata
                metadata = {
                    "source": "qdrant_migration",
                    "original_id": point_id,
                    "migrated_at": datetime.now().isoformat(),
                    "content_type": payload.get("type", "unknown"),
                    **payload.get("metadata", {})
                }
                
                # Index in text backend (skip in dry run mode)
                if not job.dry_run:
                    await self.text_backend.index_document(
                        doc_id=point_id,
                        text=text_content,
                        content_type=metadata.get("content_type", "text"),
                        metadata=metadata
                    )
                
                processing_time = (time.time() - start_time) * 1000
                
                return MigrationResult(
                    source_id=point_id,
                    target_id=point_id,
                    success=True,
                    processing_time_ms=processing_time,
                    metadata={"text_length": len(text_content)}
                )
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                return MigrationResult(
                    source_id=str(point.id) if hasattr(point, 'id') else "unknown",
                    target_id=None,
                    success=False,
                    error_message=f"Migration failed: {str(e)}",
                    processing_time_ms=processing_time
                )
    
    def _extract_text_from_payload(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract text content from Qdrant payload."""
        # Try different common fields for text content
        text_fields = ["content", "text", "title", "description", "body"]
        
        for field in text_fields:
            if field in payload:
                value = payload[field]
                if isinstance(value, str) and value.strip():
                    return value
                elif isinstance(value, dict):
                    # Handle nested content
                    if "text" in value:
                        return str(value["text"])
                    elif "title" in value and "description" in value:
                        return f"{value['title']} {value['description']}"
        
        # Fallback: concatenate all string values (with limits to prevent memory issues)
        text_parts = []
        max_parts = 50  # Limit number of parts to prevent excessive concatenation
        max_part_length = 1000  # Limit each part length
        
        for key, value in payload.items():
            if len(text_parts) >= max_parts:
                break
            if isinstance(value, str) and value.strip() and key not in ["id", "type", "source"]:
                # Truncate individual parts to prevent memory issues
                truncated_value = value[:max_part_length] if len(value) > max_part_length else value
                text_parts.append(truncated_value)
        
        return " ".join(text_parts) if text_parts else None
    
    async def _migrate_from_neo4j(self, job: MigrationJob) -> None:
        """Migrate data from Neo4j graph database."""
        if not self.neo4j_client:
            raise ValueError("Neo4j client not available")
        
        if job.target_backend != "text":
            raise ValueError(f"Migration from Neo4j to {job.target_backend} not supported")
        
        if not self.text_backend:
            raise ValueError("Text backend not available")
        
        logger.info("Starting Neo4j to text backend migration")
        
        try:
            # Query all Context nodes in batches
            offset = 0
            
            while True:
                # Get batch of nodes
                cypher_query = """
                MATCH (n:Context)
                RETURN n
                SKIP $offset
                LIMIT $limit
                """
                
                results = self.neo4j_client.query(
                    cypher_query,
                    {"offset": offset, "limit": job.batch_size}
                )
                
                if not results:
                    break
                
                # Process batch
                await self._process_neo4j_batch(job, results)
                
                # Check if we got fewer results than batch size (last batch)
                if len(results) < job.batch_size:
                    break
                
                offset += job.batch_size
                
        except Exception as e:
            logger.error(f"Error migrating from Neo4j: {e}")
            job.errors.append(f"Neo4j migration error: {str(e)}")
    
    async def _process_neo4j_batch(self, job: MigrationJob, nodes: List[Dict[str, Any]]) -> None:
        """Process a batch of nodes from Neo4j."""
        tasks = []
        
        for node_data in nodes:
            task = self._migrate_neo4j_node(job, node_data)
            tasks.append(task)
        
        # Execute batch concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                job.error_count += 1
                job.errors.append(f"Node migration error: {str(result)}")
            elif isinstance(result, MigrationResult):
                if result.success:
                    job.success_count += 1
                else:
                    job.error_count += 1
                    if result.error_message:
                        job.errors.append(result.error_message)
            
            job.processed_count += 1
    
    async def _migrate_neo4j_node(self, job: MigrationJob, node_data: Dict[str, Any]) -> MigrationResult:
        """Migrate a single node from Neo4j to text backend."""
        async with self._semaphores[job.job_id]:
            start_time = time.time()
            
            try:
                node = node_data.get("n", {})
                if not node:
                    return MigrationResult(
                        source_id="unknown",
                        target_id=None,
                        success=False,
                        error_message="No node data found"
                    )
                
                node_id = node.get("id", str(hash(str(node))))
                
                # Extract text content from node properties
                text_content = self._extract_text_from_node(node)
                if not text_content:
                    return MigrationResult(
                        source_id=node_id,
                        target_id=None,
                        success=False,
                        error_message="No text content found in node"
                    )
                
                # Extract metadata
                metadata = {
                    "source": "neo4j_migration",
                    "original_id": node_id,
                    "migrated_at": datetime.now().isoformat(),
                    "content_type": node.get("type", "unknown"),
                    **{k: v for k, v in node.items() if k not in ["id", "text", "content"]}
                }
                
                # Index in text backend (skip in dry run mode)
                if not job.dry_run:
                    await self.text_backend.index_document(
                        doc_id=node_id,
                        text=text_content,
                        content_type=metadata.get("content_type", "text"),
                        metadata=metadata
                    )
                
                processing_time = (time.time() - start_time) * 1000
                
                return MigrationResult(
                    source_id=node_id,
                    target_id=node_id,
                    success=True,
                    processing_time_ms=processing_time,
                    metadata={"text_length": len(text_content)}
                )
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                return MigrationResult(
                    source_id="unknown",
                    target_id=None,
                    success=False,
                    error_message=f"Migration failed: {str(e)}",
                    processing_time_ms=processing_time
                )
    
    def _extract_text_from_node(self, node: Dict[str, Any]) -> Optional[str]:
        """Extract text content from Neo4j node properties."""
        # Try different common fields for text content
        text_fields = ["content", "text", "title", "description", "body"]
        
        for field in text_fields:
            if field in node:
                value = node[field]
                if isinstance(value, str) and value.strip():
                    return value
        
        # Handle JSON fields (from flattened storage) with size limits
        json_fields = [k for k in node.keys() if k.endswith("_json")]
        for field in json_fields:
            try:
                json_str = node[field]
                # Security: Validate JSON size before parsing to prevent DoS
                max_json_size = 1024 * 1024  # 1MB limit
                if isinstance(json_str, str) and len(json_str.encode('utf-8')) > max_json_size:
                    logger.warning(f"Skipping large JSON field {field}: {len(json_str.encode('utf-8'))} bytes")
                    continue
                    
                json_data = json.loads(json_str)
                if isinstance(json_data, dict):
                    text = self._extract_text_from_payload(json_data)
                    if text:
                        return text
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Fallback: concatenate all string values
        text_parts = []
        for key, value in node.items():
            if isinstance(value, str) and value.strip() and key not in ["id", "type", "source"]:
                text_parts.append(value)
        
        return " ".join(text_parts) if text_parts else None
    
    async def _migrate_from_redis(self, job: MigrationJob) -> None:
        """Migrate data from Redis key-value store."""
        if not self.kv_store:
            raise ValueError("KV store client not available")
        
        if job.target_backend != "text":
            raise ValueError(f"Migration from Redis to {job.target_backend} not supported")
        
        # Redis migration is typically not needed for text search
        # as KV data is usually non-textual (IDs, state, cache)
        logger.warning("Redis to text migration requested - typically not needed")
        job.status = MigrationStatus.COMPLETED
    
    async def _migrate_from_all_sources(self, job: MigrationJob) -> None:
        """Migrate data from all available sources."""
        # Create separate jobs for each source
        sub_jobs = []
        
        if self.qdrant_client:
            qdrant_job = MigrationJob(
                job_id=f"{job.job_id}_qdrant",
                source=MigrationSource.QDRANT,
                target_backend=job.target_backend,
                batch_size=job.batch_size,
                max_concurrent=job.max_concurrent,
                dry_run=job.dry_run
            )
            sub_jobs.append(self._migrate_from_qdrant(qdrant_job))
        
        if self.neo4j_client:
            neo4j_job = MigrationJob(
                job_id=f"{job.job_id}_neo4j",
                source=MigrationSource.NEO4J,
                target_backend=job.target_backend,
                batch_size=job.batch_size,
                max_concurrent=job.max_concurrent,
                dry_run=job.dry_run
            )
            sub_jobs.append(self._migrate_from_neo4j(neo4j_job))
        
        # Execute all sub-jobs
        await asyncio.gather(*sub_jobs, return_exceptions=True)
    
    async def validate_migration(self, job_id: str) -> Dict[str, Any]:
        """
        Validate the results of a migration job.
        
        Args:
            job_id: ID of the migration job to validate
            
        Returns:
            Validation results
        """
        if job_id not in self.active_jobs:
            return {"error": "Job not found"}
        
        job = self.active_jobs[job_id]
        
        # Basic validation
        validation_results = {
            "job_id": job_id,
            "status": job.status,
            "total_processed": job.processed_count,
            "successful": job.success_count,
            "failed": job.error_count,
            "success_rate": (job.success_count / job.processed_count * 100) if job.processed_count > 0 else 0,
            "errors": job.errors[-10:],  # Last 10 errors
            "validation_checks": {}
        }
        
        # Text backend validation
        if job.target_backend == "text" and self.text_backend:
            try:
                stats = self.text_backend.get_index_statistics()
                validation_results["validation_checks"]["text_backend"] = {
                    "indexed_documents": stats["document_count"],
                    "vocabulary_size": stats["vocabulary_size"],
                    "average_doc_length": stats.get("average_document_length", 0)
                }
            except Exception as e:
                validation_results["validation_checks"]["text_backend"] = {
                    "error": str(e)
                }
        
        return validation_results
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a migration job."""
        if job_id not in self.active_jobs:
            return None
        
        job = self.active_jobs[job_id]
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "source": job.source,
            "target_backend": job.target_backend,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "processed_count": job.processed_count,
            "success_count": job.success_count,
            "error_count": job.error_count,
            "progress_percentage": (job.processed_count / max(job.processed_count, 1)) * 100,
            "recent_errors": job.errors[-5:] if job.errors else []
        }
    
    def list_active_jobs(self) -> List[Dict[str, Any]]:
        """List all active migration jobs."""
        return [self.get_job_status(job_id) for job_id in self.active_jobs.keys()]


# Global migration engine instance
_migration_engine: Optional[DataMigrationEngine] = None


def get_migration_engine() -> Optional[DataMigrationEngine]:
    """Get the global migration engine instance."""
    return _migration_engine


def initialize_migration_engine(
    qdrant_client: Optional[VectorDBInitializer] = None,
    neo4j_client: Optional[Neo4jInitializer] = None,
    kv_store: Optional[KVStore] = None,
    text_backend: Optional[TextSearchBackend] = None
) -> DataMigrationEngine:
    """Initialize the global migration engine."""
    global _migration_engine
    _migration_engine = DataMigrationEngine(
        qdrant_client=qdrant_client,
        neo4j_client=neo4j_client,
        kv_store=kv_store,
        text_backend=text_backend
    )
    logger.info("Migration engine initialized")
    return _migration_engine