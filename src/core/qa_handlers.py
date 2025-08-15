#!/usr/bin/env python3
"""
Q&A handling utilities for storage and retrieval operations.

This module provides helper functions to extract Q&A detection and query
expansion logic from the main server code for better maintainability.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def detect_and_store_qa_metadata(
    content: Dict[str, Any], 
    context_id: str, 
    session
) -> Tuple[bool, Dict[str, Any]]:
    """Detect Q&A relationships and store metadata in Neo4j.
    
    Args:
        content: The context content containing conversation messages
        context_id: Unique identifier for the context
        session: Neo4j session for database operations
        
    Returns:
        Tuple of (success, metadata) where metadata contains Q&A information
    """
    try:
        from src.core.qa_detector import get_qa_detector
        
        qa_detector = get_qa_detector()
        qa_metadata = {}
        
        # Check if content contains conversation messages
        if isinstance(content, dict) and "messages" in content:
            messages = content["messages"]
            if isinstance(messages, list):
                qa_relationships = qa_detector.detect_qa_relationship(messages)
                
                # Store Q&A metadata in the context
                if qa_relationships:
                    qa_metadata = {
                        "qa_pairs": len(qa_relationships),
                        "relationships": qa_relationships
                    }
                    
                    # Update node with Q&A metadata
                    update_query = """
                    MATCH (c:Context {id: $id})
                    SET c.qa_metadata = $qa_metadata
                    RETURN c
                    """
                    session.run(update_query, id=context_id, qa_metadata=json.dumps(qa_metadata))
                    logger.info(f"Added Q&A metadata: {len(qa_relationships)} relationships detected")
                    
                    # Extract and index factual statements for better retrieval
                    factual_statements = qa_detector.extract_factual_statements(messages)
                    if factual_statements:
                        fact_metadata = {
                            "factual_statements": factual_statements
                        }
                        update_query = """
                        MATCH (c:Context {id: $id})
                        SET c.fact_metadata = $fact_metadata
                        RETURN c
                        """
                        session.run(update_query, id=context_id, fact_metadata=json.dumps(fact_metadata))
                        logger.info(f"Indexed {len(factual_statements)} factual statements")
                        
                        # Merge factual metadata into main metadata
                        qa_metadata.update(fact_metadata)
        
        return True, qa_metadata
        
    except ImportError:
        logger.debug("Q&A detector not available, skipping relationship detection")
        return False, {}
    except Exception as e:
        logger.error(f"Failed to detect and store Q&A metadata: {e}")
        return False, {}


def expand_query_patterns(query: str) -> List[str]:
    """Expand query into multiple search patterns for better recall.
    
    Args:
        query: Original search query
        
    Returns:
        List of expanded query patterns including the original
    """
    try:
        from src.core.query_expansion import get_query_expander
        
        query_expander = get_query_expander()
        expanded_queries = query_expander.expand_query(query)
        logger.info(f"Query expansion: '{query}' → {len(expanded_queries)} patterns")
        return expanded_queries
        
    except ImportError:
        # Fallback if query expansion is not available
        logger.warning("Query expansion not available, using original query only")
        return [query]
    except Exception as e:
        logger.error(f"Query expansion failed: {e}")
        return [query]


def process_enhanced_search_results(
    results: List[Dict[str, Any]], 
    original_query: str
) -> List[Dict[str, Any]]:
    """Process search results with Q&A awareness and enhanced metadata.
    
    Args:
        results: Raw search results from vector/graph search
        original_query: The original search query for context
        
    Returns:
        Processed results with enhanced Q&A metadata
    """
    processed_results = []
    
    for result in results:
        # Add Q&A context information if available
        enhanced_result = result.copy()
        
        # Check if result has Q&A metadata
        if "qa_metadata" in result:
            try:
                qa_data = result["qa_metadata"]
                if isinstance(qa_data, str):
                    qa_data = json.loads(qa_data)
                
                enhanced_result["has_qa_data"] = True
                enhanced_result["qa_pairs_count"] = qa_data.get("qa_pairs", 0)
                
                # Extract relevant Q&A relationships for this query
                relationships = qa_data.get("relationships", [])
                relevant_qa = []
                
                for rel in relationships:
                    question = rel.get("question_content", "").lower()
                    answer = rel.get("answer_content", "").lower()
                    query_lower = original_query.lower()
                    
                    # Check if this Q&A pair is relevant to the query
                    if (any(word in question for word in query_lower.split()) or
                        any(word in answer for word in query_lower.split())):
                        relevant_qa.append(rel)
                
                if relevant_qa:
                    enhanced_result["relevant_qa_pairs"] = relevant_qa
                    enhanced_result["qa_relevance_score"] = len(relevant_qa) / len(relationships)
                
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse Q&A metadata: {e}")
        
        # Check if result has factual metadata
        if "fact_metadata" in result:
            try:
                fact_data = result["fact_metadata"]
                if isinstance(fact_data, str):
                    fact_data = json.loads(fact_data)
                
                enhanced_result["has_factual_data"] = True
                factual_statements = fact_data.get("factual_statements", [])
                enhanced_result["factual_statements_count"] = len(factual_statements)
                
                # Find factual statements relevant to query
                relevant_facts = []
                query_lower = original_query.lower()
                
                for fact in factual_statements:
                    fact_content = fact.get("content", "").lower()
                    fact_types = fact.get("fact_types", [])
                    
                    if (any(word in fact_content for word in query_lower.split()) or
                        any(ftype in query_lower for ftype in fact_types)):
                        relevant_facts.append(fact)
                
                if relevant_facts:
                    enhanced_result["relevant_facts"] = relevant_facts
                
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse factual metadata: {e}")
        
        processed_results.append(enhanced_result)
    
    return processed_results


def calculate_qa_enhanced_score(result: Dict[str, Any], original_query: str) -> float:
    """Calculate enhanced relevance score incorporating Q&A metadata.
    
    Args:
        result: Search result with potential Q&A metadata
        original_query: Original search query
        
    Returns:
        Enhanced relevance score (0.0 to 1.0)
    """
    base_score = result.get("score", 0.0)
    qa_boost = result.get("qa_boost", 1.0)
    
    # Start with base score
    enhanced_score = base_score
    
    # Apply Q&A boost
    enhanced_score *= qa_boost
    
    # Additional boost for Q&A relevance
    if "qa_relevance_score" in result:
        qa_relevance = result["qa_relevance_score"]
        enhanced_score += qa_relevance * 0.2  # Up to 20% boost
    
    # Additional boost for factual statements
    if "relevant_facts" in result:
        fact_count = len(result["relevant_facts"])
        enhanced_score += min(fact_count * 0.1, 0.3)  # Up to 30% boost
    
    # Boost for exact query matches in Q&A pairs
    if "relevant_qa_pairs" in result:
        for qa_pair in result["relevant_qa_pairs"]:
            question = qa_pair.get("question_content", "").lower()
            answer = qa_pair.get("answer_content", "").lower()
            query_lower = original_query.lower()
            
            # High boost for exact question matches
            if query_lower in question or question in query_lower:
                enhanced_score += 0.4
            
            # Medium boost for answer pattern matches
            if any(word in answer for word in query_lower.split() if len(word) > 3):
                enhanced_score += 0.2
    
    # Normalize to [0, 1] range while preserving relative ordering
    return min(enhanced_score, 1.0)


def merge_and_deduplicate_results(
    vector_results: List[Dict[str, Any]], 
    graph_results: List[Dict[str, Any]], 
    limit: int
) -> List[Dict[str, Any]]:
    """Merge vector and graph results with intelligent deduplication.
    
    Args:
        vector_results: Results from vector search
        graph_results: Results from graph search  
        limit: Maximum number of results to return
        
    Returns:
        Merged and deduplicated results, limited to specified count
    """
    # Combine all results
    all_results = []
    all_results.extend(vector_results)
    all_results.extend(graph_results)
    
    # Deduplicate by ID while preserving best scores
    seen_ids = {}
    for result in all_results:
        result_id = result.get("id")
        if result_id:
            current_score = result.get("score", 0.0)
            qa_boost = result.get("qa_boost", 1.0)
            total_score = current_score * qa_boost
            
            if (result_id not in seen_ids or 
                total_score > seen_ids[result_id].get("score", 0.0) * seen_ids[result_id].get("qa_boost", 1.0)):
                seen_ids[result_id] = result
    
    # Convert back to list and sort by enhanced score
    deduplicated_results = list(seen_ids.values())
    
    # Sort by multiple criteria for best ranking
    def sort_key(result):
        score = result.get("score", 0.0)
        qa_boost = result.get("qa_boost", 1.0)
        has_qa = 1.0 if result.get("qa_metadata") else 0.0
        has_facts = 1.0 if result.get("fact_metadata") else 0.0
        
        return (score * qa_boost, has_qa, has_facts, score)
    
    deduplicated_results.sort(key=sort_key, reverse=True)
    
    return deduplicated_results[:limit]