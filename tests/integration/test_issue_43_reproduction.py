#!/usr/bin/env python3
"""
Comprehensive test for Issue #43 reproduction and fix validation.

This script tests the complete fix including:
1. Query expansion
2. Q&A relationship detection during storage
3. Enhanced retrieval with Q&A awareness
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.query_expansion import get_query_expander
from core.qa_detector import get_qa_detector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_qa_detection():
    """Test Q&A relationship detection."""
    logger.info("🔍 Testing Q&A Relationship Detection")
    
    qa_detector = get_qa_detector()
    
    # Simulate the exact conversation from Issue #43
    messages = [
        {"role": "user", "content": "What is my name?"},
        {"role": "assistant", "content": "I don't have your name saved yet! Could you please tell me?"},
        {"role": "user", "content": "My name is Matt"}
    ]
    
    logger.info(f"📥 Test conversation: {len(messages)} messages")
    for i, msg in enumerate(messages):
        logger.info(f"   {i+1}. {msg['role']}: {msg['content']}")
    
    # Detect Q&A relationships
    qa_relationships = qa_detector.detect_qa_relationship(messages)
    logger.info(f"\n🔗 Detected {len(qa_relationships)} Q&A relationships:")
    
    for i, rel in enumerate(qa_relationships):
        logger.info(f"   {i+1}. Q: '{rel['question_content']}'")
        logger.info(f"       A: '{rel['answer_content']}'")
        logger.info(f"       Confidence: {rel['confidence']:.2f}")
    
    # Extract factual statements
    facts = qa_detector.extract_factual_statements(messages)
    logger.info(f"\n📊 Extracted {len(facts)} factual statements:")
    
    for i, fact in enumerate(facts):
        logger.info(f"   {i+1}. {fact['content']}")
        logger.info(f"       Types: {fact['fact_types']}")
        logger.info(f"       Entities: {fact['entities']}")
    
    return len(qa_relationships) > 0 and len(facts) > 0


def test_combined_fix():
    """Test the combined query expansion + Q&A detection fix."""
    logger.info("\n🎯 Testing Combined Fix for Issue #43")
    
    # Simulate storing conversation with Q&A detection
    expander = get_query_expander()
    qa_detector = get_qa_detector()
    
    # Test conversation from Issue #43
    conversation_content = {
        "messages": [
            {"role": "user", "content": "What is my name?"},
            {"role": "assistant", "content": "I don't have your name saved yet! Could you please tell me?"},
            {"role": "user", "content": "My name is Matt"}
        ]
    }
    
    logger.info("📥 Simulating storage of conversation...")
    
    # Detect Q&A relationships (what would happen during storage)
    qa_relationships = qa_detector.detect_qa_relationship(conversation_content["messages"])
    factual_statements = qa_detector.extract_factual_statements(conversation_content["messages"])
    
    # Create storage metadata
    storage_metadata = {
        "qa_metadata": {
            "qa_pairs": len(qa_relationships),
            "relationships": qa_relationships
        },
        "fact_metadata": {
            "factual_statements": factual_statements
        }
    }
    
    logger.info(f"✅ Storage would create: {len(qa_relationships)} Q&A pairs, {len(factual_statements)} facts")
    
    # Test retrieval with query expansion
    query = "What's my name?"
    logger.info(f"\n❓ Simulating query: '{query}'")
    
    # Expand query
    expanded_queries = expander.expand_query(query)
    logger.info(f"🔍 Query expansion: {expanded_queries}")
    
    # Simulate search in stored content
    conversation_text = json.dumps(conversation_content).lower()
    qa_text = json.dumps(storage_metadata).lower()
    
    matches = []
    for expanded_query in expanded_queries:
        if expanded_query.lower() in conversation_text or expanded_query.lower() in qa_text:
            matches.append(expanded_query)
    
    if matches:
        logger.info(f"✅ SUCCESS: Would find matches via expanded queries: {matches}")
        return True
    else:
        logger.error(f"❌ FAILURE: No matches found in stored content")
        return False


def test_before_after_comparison():
    """Compare behavior before and after the fix."""
    logger.info("\n📊 Before/After Comparison")
    
    # Original query from Issue #43
    query = "What's my name?"
    stored_answer = "My name is Matt"
    
    logger.info(f"Query: '{query}'")
    logger.info(f"Stored answer: '{stored_answer}'")
    
    # Before fix: Direct string matching only
    before_match = query.lower() in stored_answer.lower()
    logger.info(f"\n❌ BEFORE (direct matching): {before_match}")
    
    # After fix: Query expansion
    expander = get_query_expander()
    expanded_queries = expander.expand_query(query)
    
    after_matches = []
    for expanded_query in expanded_queries:
        if expanded_query.lower() in stored_answer.lower():
            after_matches.append(expanded_query)
    
    after_match = len(after_matches) > 0
    logger.info(f"✅ AFTER (with expansion): {after_match}")
    if after_matches:
        logger.info(f"   Matching patterns: {after_matches}")
    
    return after_match and not before_match


def test_edge_cases():
    """Test various edge cases and question types."""
    logger.info("\n🧪 Testing Edge Cases")
    
    expander = get_query_expander()
    qa_detector = get_qa_detector()
    
    test_cases = [
        {
            "query": "What do I do for work?",
            "stored": "I work as a software engineer",
            "description": "Profession query"
        },
        {
            "query": "Where do I live?",
            "stored": "I live in San Francisco",
            "description": "Location query"
        },
        {
            "query": "What's my email?",
            "stored": "My email is matt@example.com",
            "description": "Contact query"
        },
        {
            "query": "How old am I?",
            "stored": "I am 30 years old",
            "description": "Age query"
        }
    ]
    
    all_passed = True
    
    for i, case in enumerate(test_cases, 1):
        query = case["query"]
        stored = case["stored"]
        desc = case["description"]
        
        logger.info(f"\n📝 Test {i} ({desc}):")
        logger.info(f"   Query: '{query}'")
        logger.info(f"   Stored: '{stored}'")
        
        # Test query expansion
        expanded = expander.expand_query(query)
        matches = [eq for eq in expanded if any(word in stored.lower() for word in eq.lower().split())]
        
        if matches:
            logger.info(f"   ✅ Would match via: {matches[:2]}...")  # Show first 2 matches
        else:
            logger.info(f"   ❌ No matches found")
            all_passed = False
    
    return all_passed


async def main():
    """Run all tests."""
    logger.info("🚀 Comprehensive Test for Issue #43 Fix")
    logger.info("="*60)
    
    # Test individual components
    qa_detection_passed = test_qa_detection()
    combined_fix_passed = test_combined_fix()
    comparison_passed = test_before_after_comparison()
    edge_cases_passed = test_edge_cases()
    
    # Final assessment
    print("\n" + "="*60)
    logger.info("📋 Test Results Summary:")
    logger.info(f"   Q&A Detection: {'✅ PASS' if qa_detection_passed else '❌ FAIL'}")
    logger.info(f"   Combined Fix: {'✅ PASS' if combined_fix_passed else '❌ FAIL'}")
    logger.info(f"   Before/After: {'✅ PASS' if comparison_passed else '❌ FAIL'}")
    logger.info(f"   Edge Cases: {'✅ PASS' if edge_cases_passed else '❌ FAIL'}")
    
    all_passed = all([ 
        qa_detection_passed,
        combined_fix_passed, 
        comparison_passed,
        edge_cases_passed
    ])
    
    print("\n" + "="*60)
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("   Issue #43 should be resolved with this fix.")
        logger.info("   Query expansion + Q&A detection will enable semantic retrieval.")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED!")
        logger.error("   The fix needs additional improvements.")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))