#!/usr/bin/env python3
"""
Namespace Discipline Enforcement - Single Namespace Tag System
Ensures consistent tagging on both store & retrieve operations
"""

import logging
from typing import Dict, Any, Optional
import uuid
import hashlib

logger = logging.getLogger(__name__)

class NamespaceEnforcer:
    """Enforces single namespace discipline across store/retrieve operations"""
    
    DEFAULT_NAMESPACE = "default"
    NAMESPACE_KEY = "namespace"
    
    def __init__(self, enforce_mode: bool = True):
        self.enforce_mode = enforce_mode
        logger.info(f"NamespaceEnforcer initialized (enforce_mode={enforce_mode})")
    
    def enforce_store_namespace(self, context: Dict[str, Any], 
                              provided_namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Enforce namespace discipline on store operations
        
        Args:
            context: Context data to store
            provided_namespace: Optional explicit namespace
            
        Returns:
            Enhanced context with namespace tag
        """
        # Determine namespace
        namespace = self._resolve_namespace(context, provided_namespace)
        
        # Clone context to avoid mutation
        enhanced_context = context.copy()
        
        # Ensure metadata exists
        if "metadata" not in enhanced_context:
            enhanced_context["metadata"] = {}
        
        # Force namespace tag
        enhanced_context["metadata"][self.NAMESPACE_KEY] = namespace
        
        logger.info(f"Store namespace enforced: {namespace}")
        return enhanced_context
    
    def enforce_retrieve_namespace(self, query: str, 
                                 filters: Optional[Dict[str, Any]] = None,
                                 provided_namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Enforce namespace discipline on retrieve operations
        
        Args:
            query: Search query
            filters: Optional existing filters
            provided_namespace: Optional explicit namespace
            
        Returns:
            Enhanced filters with namespace constraint
        """
        # Start with existing filters or empty dict
        enhanced_filters = filters.copy() if filters else {}
        
        # Determine namespace
        namespace = provided_namespace or self._infer_namespace_from_query(query)
        
        # Force namespace filter (even if no other filters)
        enhanced_filters[self.NAMESPACE_KEY] = namespace
        
        logger.info(f"Retrieve namespace enforced: {namespace} (query: '{query[:50]}...')")
        return enhanced_filters
    
    def _resolve_namespace(self, context: Dict[str, Any], 
                          provided_namespace: Optional[str]) -> str:
        """Resolve namespace using precedence rules"""
        
        # 1. Explicit namespace (highest priority)
        if provided_namespace:
            return self._sanitize_namespace(provided_namespace)
        
        # 2. Context metadata namespace
        if "metadata" in context and self.NAMESPACE_KEY in context["metadata"]:
            return self._sanitize_namespace(context["metadata"][self.NAMESPACE_KEY])
        
        # 3. Context type-based namespace
        if "type" in context:
            return self._sanitize_namespace(f"type_{context['type']}")
        
        # 4. Content-based namespace (hash of content keys)
        if "content" in context and isinstance(context["content"], dict):
            content_sig = "_".join(sorted(context["content"].keys()))
            content_hash = hashlib.md5(content_sig.encode()).hexdigest()[:8]
            return f"content_{content_hash}"
        
        # 5. Default fallback
        return self.DEFAULT_NAMESPACE
    
    def _infer_namespace_from_query(self, query: str) -> str:
        """Infer namespace from query characteristics"""
        
        query_lower = query.lower()
        
        # Query pattern matching
        if any(word in query_lower for word in ["design", "architecture", "spec"]):
            return "type_design"
        elif any(word in query_lower for word in ["decision", "choice", "option"]):
            return "type_decision"
        elif any(word in query_lower for word in ["trace", "debug", "log"]):
            return "type_trace"
        elif any(word in query_lower for word in ["sprint", "planning", "milestone"]):
            return "type_sprint"
        
        # Default namespace for general queries
        return self.DEFAULT_NAMESPACE
    
    def _sanitize_namespace(self, namespace: str) -> str:
        """Sanitize namespace to ensure consistency"""
        # Convert to lowercase, replace spaces/special chars with underscores
        sanitized = namespace.lower().strip()
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in sanitized)
        
        # Remove multiple underscores and trim
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        
        sanitized = sanitized.strip("_")
        
        # Ensure non-empty
        return sanitized if sanitized else self.DEFAULT_NAMESPACE
    
    def validate_consistency(self, stored_contexts: list, 
                           query_filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate namespace consistency across operations"""
        
        # Count namespace distribution in stored contexts
        namespace_counts = {}
        for context in stored_contexts:
            ns = context.get("metadata", {}).get(self.NAMESPACE_KEY, "MISSING")
            namespace_counts[ns] = namespace_counts.get(ns, 0) + 1
        
        # Check query filter namespace
        query_namespace = query_filters.get(self.NAMESPACE_KEY, "MISSING")
        
        return {
            "stored_namespaces": namespace_counts,
            "query_namespace": query_namespace,
            "consistency_check": "PASS" if "MISSING" not in namespace_counts else "FAIL",
            "total_contexts": len(stored_contexts)
        }


# Production integration helper
def enforce_namespace_discipline():
    """Factory function for production integration"""
    return NamespaceEnforcer(enforce_mode=True)


# Example usage
if __name__ == "__main__":
    enforcer = NamespaceEnforcer()
    
    # Test store enforcement
    test_context = {
        "type": "design",
        "content": {"title": "API Design", "description": "REST endpoints"},
        "metadata": {"author": "developer"}
    }
    
    enhanced = enforcer.enforce_store_namespace(test_context)
    print("Enhanced context:", enhanced)
    
    # Test retrieve enforcement  
    filters = enforcer.enforce_retrieve_namespace("API design patterns")
    print("Enhanced filters:", filters)