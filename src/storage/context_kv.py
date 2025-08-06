#!/usr/bin/env python3
"""
context_kv.py: Context-aware key-value storage implementation

This module provides a context-aware wrapper around the base KV store
with additional features for context management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .kv_store import CacheEntry
from .kv_store import ContextKV as BaseContextKV
from .kv_store import MetricEvent


class ContextKV(BaseContextKV):
    """Enhanced context-aware KV store with additional context management features."""

    def __init__(
        self,
        config_path: str = ".ctxrc.yaml",
        verbose: bool = False,
        config: Optional[Dict[str, Any]] = None,
        test_mode: bool = False,
    ):
        """Initialize enhanced ContextKV."""
        super().__init__(config_path, verbose, config, test_mode)
        self.context_cache: Dict[str, Any] = {}

    def store_context(
        self, context_id: str, context_data: Dict[str, Any], ttl_seconds: Optional[int] = None
    ) -> bool:
        """Store context data with optional TTL.

        Args:
            context_id: Unique identifier for the context
            context_data: Context data to store
            ttl_seconds: Optional TTL in seconds

        Returns:
            bool: True if stored successfully, False otherwise
        """
        if not context_id or not context_data:
            return False

        # Add metadata
        context_data["_stored_at"] = datetime.utcnow().isoformat()
        context_data["_context_id"] = context_id

        # Store in cache
        success = self.redis.set_cache(f"context:{context_id}", context_data, ttl_seconds)

        # Record metric
        if success:
            metric = MetricEvent(
                timestamp=datetime.utcnow(),
                metric_name="context.store",
                value=1.0,
                tags={"context_id": context_id},
                document_id=context_data.get("document_id"),
                agent_id=context_data.get("agent_id"),
            )
            self.redis.record_metric(metric)

        return success

    def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve context data by ID.

        Args:
            context_id: Context identifier

        Returns:
            Context data if found, None otherwise
        """
        if not context_id:
            return None

        # Try cache first
        cached = self.redis.get_cache(f"context:{context_id}")
        if cached:
            # Record hit metric
            metric = MetricEvent(
                timestamp=datetime.utcnow(),
                metric_name="context.get",
                value=1.0,
                tags={"context_id": context_id, "cache_hit": "true"},
                document_id=None,
                agent_id=None,
            )
            self.redis.record_metric(metric)
            return cached

        return None

    def delete_context(self, context_id: str) -> bool:
        """Delete context data.

        Args:
            context_id: Context identifier

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not context_id:
            return False

        count = self.redis.delete_cache(f"context:{context_id}")

        if count > 0:
            # Record deletion metric
            metric = MetricEvent(
                timestamp=datetime.utcnow(),
                metric_name="context.delete",
                value=float(count),
                tags={"context_id": context_id},
                document_id=None,
                agent_id=None,
            )
            self.redis.record_metric(metric)

        return count > 0

    def list_contexts(self, pattern: str = "*") -> List[str]:
        """List all context IDs matching pattern.

        Args:
            pattern: Pattern to match context IDs

        Returns:
            List of matching context IDs
        """
        # This would need to be implemented in the base redis connector
        # For now, return empty list
        return []

    def update_context(self, context_id: str, updates: Dict[str, Any], merge: bool = True) -> bool:
        """Update existing context data.

        Args:
            context_id: Context identifier
            updates: Updates to apply
            merge: If True, merge with existing data; if False, replace

        Returns:
            bool: True if updated successfully, False otherwise
        """
        if not context_id or not updates:
            return False

        existing = self.get_context(context_id)
        if not existing:
            return False

        if merge:
            # Merge updates with existing data
            existing.update(updates)
            new_data = existing
        else:
            # Replace with updates
            new_data = updates

        # Preserve metadata
        new_data["_updated_at"] = datetime.utcnow().isoformat()
        new_data["_context_id"] = context_id

        return self.store_context(context_id, new_data)

    def get_context_metrics(self, context_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get metrics for a specific context.

        Args:
            context_id: Context identifier
            hours: Hours to look back

        Returns:
            Metrics summary for the context
        """
        end_time = datetime.utcnow()
        from datetime import timedelta

        start_time = end_time - timedelta(hours=hours)

        # Get metrics from Redis
        metrics = self.redis.get_metrics(f"context.{context_id}", start_time, end_time)

        return {
            "context_id": context_id,
            "period_hours": hours,
            "metrics_count": len(metrics),
            "metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "tags": m.tags,
                }
                for m in metrics
            ],
        }


# Export the enhanced class
__all__ = ["ContextKV", "MetricEvent", "CacheEntry"]
