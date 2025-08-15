#!/usr/bin/env python3
"""
Test script to reproduce and verify fix for Issue #43:
Memory search retrieval ineffective for semantically related questions.

This script tests the query expansion functionality to ensure questions
like "What's my name?" can find answers like "My name is Matt".
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.query_expansion import QueryExpander

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_query_expansion():
    """Test the query expansion functionality."""
    logger.info("🧪 Testing Query Expansion for Issue #43")
    
    expander = QueryExpander()
    
    # Test cases from the GitHub issue
    test_cases = [
        {
            "query": "What's my name?",
            "expected_expansions": ["my name is", "i am", "call me"]
        },
        {
            "query": "What is my name?",
            "expected_expansions": ["my name is", "i am", "call me"]
        },
        {
            "query": "Who am I?",
            "expected_expansions": ["my name is", "i am", "call me"]
        },
        {
            "query": "What do I do?",
            "expected_expansions": ["i work", "my job is", "i am a"]
        },
        {
            "query": "My name is Matt",
            "expected_expansions": ["what's my name", "who am i"]
        }
    ]
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        query = test_case["query"]
        expected = test_case["expected_expansions"]
        
        logger.info(f"\n📝 Test {i}: '{query}'")
        
        # Get expanded queries
        expanded = expander.expand_query(query)
        
        logger.info(f"   Original: {query}")
        logger.info(f"   Expanded: {expanded}")
        
        # Check if expected expansions are present
        expanded_lower = [q.lower() for q in expanded]
        found_expected = []
        
        for exp in expected:
            if any(exp in eq for eq in expanded_lower):
                found_expected.append(exp)
        
        if found_expected:
            logger.info(f"   ✅ Found expected patterns: {found_expected}")
        else:
            logger.error(f"   ❌ Missing expected patterns: {expected}")
            all_passed = False
    
    return all_passed


def test_entity_extraction():
    """Test entity extraction functionality."""
    logger.info("\n🔍 Testing Entity Extraction")
    
    expander = QueryExpander()
    
    test_texts = [
        "My name is Matt",
        "I work as a software engineer",
        "My email is matt@example.com",
        "Call me at 555-123-4567",
        "I live in San Francisco"
    ]
    
    for text in test_texts:
        entities = expander.extract_entities(text)
        logger.info(f"Text: '{text}'")
        logger.info(f"Entities: {entities}")
        print()


async def simulate_issue_43_scenario():
    """Simulate the exact scenario from Issue #43."""
    logger.info("\n🎯 Simulating Issue #43 Scenario")
    
    expander = QueryExpander()
    
    # Simulate storing "My name is Matt"
    stored_content = "My name is Matt"
    logger.info(f"📥 Stored: '{stored_content}'")
    
    # Simulate querying "What's my name?"
    query = "What's my name?"
    logger.info(f"❓ Query: '{query}'")
    
    # Show how query expansion would help
    expanded_queries = expander.expand_query(query)
    logger.info(f"🔍 Expanded queries: {expanded_queries}")
    
    # Check if any expanded query would match the stored content
    matches = []
    stored_lower = stored_content.lower()
    
    for expanded_query in expanded_queries:
        if expanded_query.lower() in stored_lower or any(word in stored_lower for word in expanded_query.lower().split()):
            matches.append(expanded_query)
    
    if matches:
        logger.info(f"✅ SUCCESS: Query expansion would find matches via: {matches}")
        return True
    else:
        logger.error(f"❌ FAILURE: No expanded queries would match stored content")
        return False


def main():
    """Run all tests."""
    logger.info("🚀 Testing Issue #43 Fix - Query Expansion")
    
    # Test query expansion
    expansion_passed = test_query_expansion()
    
    # Test entity extraction
    test_entity_extraction()
    
    # Test the specific Issue #43 scenario
    scenario_passed = asyncio.run(simulate_issue_43_scenario())
    
    # Final result
    print("\n" + "="*50)
    if expansion_passed and scenario_passed:
        logger.info("🎉 ALL TESTS PASSED! Query expansion should fix Issue #43")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED! Query expansion needs improvement")
        return 1


if __name__ == "__main__":
    exit(main())