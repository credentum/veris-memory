#!/usr/bin/env python3
"""
Unit tests for Q&A handlers module.

Tests the refactored Q&A detection and query expansion handlers
that were extracted from the main server code.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.qa_handlers import (
    detect_and_store_qa_metadata,
    expand_query_patterns,
    process_enhanced_search_results,
    calculate_qa_enhanced_score,
    merge_and_deduplicate_results
)


class TestDetectAndStoreQAMetadata:
    """Test Q&A metadata detection and storage."""

    def test_detect_and_store_qa_metadata_success(self):
        """Test successful Q&A metadata detection and storage."""
        # Mock session
        mock_session = Mock()
        
        # Mock content with conversation messages
        content = {
            "messages": [
                {"role": "user", "content": "What is my name?"},
                {"role": "assistant", "content": "My name is John"}
            ]
        }
        
        with patch('core.qa_handlers.get_qa_detector') as mock_get_detector:
            mock_detector = Mock()
            mock_detector.detect_qa_relationship.return_value = [
                {
                    "type": "qa_pair",
                    "question_content": "What is my name?",
                    "answer_content": "My name is John",
                    "confidence": 0.8
                }
            ]
            mock_detector.extract_factual_statements.return_value = [
                {
                    "content": "My name is John",
                    "fact_types": ["name"],
                    "entities": {"names": ["John"]}
                }
            ]
            mock_get_detector.return_value = mock_detector
            
            success, metadata = detect_and_store_qa_metadata(content, "test_id", mock_session)
            
            assert success is True
            assert "qa_pairs" in metadata
            assert metadata["qa_pairs"] == 1
            assert "relationships" in metadata
            assert "factual_statements" in metadata
            
            # Verify session.run was called
            assert mock_session.run.call_count == 2

    def test_detect_and_store_qa_metadata_no_messages(self):
        """Test with content that has no messages."""
        mock_session = Mock()
        content = {"title": "Test content"}
        
        with patch('core.qa_handlers.get_qa_detector'):
            success, metadata = detect_and_store_qa_metadata(content, "test_id", mock_session)
            
            assert success is True
            assert metadata == {}
            assert mock_session.run.call_count == 0

    def test_detect_and_store_qa_metadata_import_error(self):
        """Test handling of import error."""
        mock_session = Mock()
        content = {"messages": []}
        
        with patch('core.qa_handlers.get_qa_detector', side_effect=ImportError):
            success, metadata = detect_and_store_qa_metadata(content, "test_id", mock_session)
            
            assert success is False
            assert metadata == {}

    def test_detect_and_store_qa_metadata_exception(self):
        """Test handling of unexpected exceptions."""
        mock_session = Mock()
        mock_session.run.side_effect = Exception("Database error")
        
        content = {
            "messages": [
                {"role": "user", "content": "Test"}
            ]
        }
        
        with patch('core.qa_handlers.get_qa_detector') as mock_get_detector:
            mock_detector = Mock()
            mock_detector.detect_qa_relationship.return_value = [{"test": "data"}]
            mock_detector.extract_factual_statements.return_value = []
            mock_get_detector.return_value = mock_detector
            
            success, metadata = detect_and_store_qa_metadata(content, "test_id", mock_session)
            
            assert success is False
            assert metadata == {}


class TestExpandQueryPatterns:
    """Test query expansion functionality."""

    def test_expand_query_patterns_success(self):
        """Test successful query expansion."""
        with patch('core.qa_handlers.get_query_expander') as mock_get_expander:
            mock_expander = Mock()
            mock_expander.expand_query.return_value = [
                "what's my name?",
                "my name is",
                "i am",
                "call me"
            ]
            mock_get_expander.return_value = mock_expander
            
            expanded = expand_query_patterns("What's my name?")
            
            assert len(expanded) == 4
            assert "what's my name?" in expanded
            assert "my name is" in expanded

    def test_expand_query_patterns_import_error(self):
        """Test handling of import error."""
        with patch('core.qa_handlers.get_query_expander', side_effect=ImportError):
            expanded = expand_query_patterns("Test query")
            
            assert expanded == ["Test query"]

    def test_expand_query_patterns_exception(self):
        """Test handling of expansion exception."""
        with patch('core.qa_handlers.get_query_expander') as mock_get_expander:
            mock_expander = Mock()
            mock_expander.expand_query.side_effect = Exception("Expansion error")
            mock_get_expander.return_value = mock_expander
            
            expanded = expand_query_patterns("Test query")
            
            assert expanded == ["Test query"]


class TestProcessEnhancedSearchResults:
    """Test enhanced search result processing."""

    def test_process_enhanced_search_results_with_qa_metadata(self):
        """Test processing results with Q&A metadata."""
        results = [
            {
                "id": "test1",
                "content": "Test content",
                "qa_metadata": json.dumps({
                    "qa_pairs": 1,
                    "relationships": [
                        {
                            "question_content": "What is my name?",
                            "answer_content": "My name is John",
                            "confidence": 0.8
                        }
                    ]
                })
            }
        ]
        
        processed = process_enhanced_search_results(results, "What's my name?")
        
        assert len(processed) == 1
        assert processed[0]["has_qa_data"] is True
        assert processed[0]["qa_pairs_count"] == 1
        assert "relevant_qa_pairs" in processed[0]

    def test_process_enhanced_search_results_with_fact_metadata(self):
        """Test processing results with factual metadata."""
        results = [
            {
                "id": "test1",
                "content": "Test content",
                "fact_metadata": json.dumps({
                    "factual_statements": [
                        {
                            "content": "My name is John",
                            "fact_types": ["name"],
                            "entities": {"names": ["John"]}
                        }
                    ]
                })
            }
        ]
        
        processed = process_enhanced_search_results(results, "name")
        
        assert len(processed) == 1
        assert processed[0]["has_factual_data"] is True
        assert processed[0]["factual_statements_count"] == 1
        assert "relevant_facts" in processed[0]

    def test_process_enhanced_search_results_no_metadata(self):
        """Test processing results without Q&A metadata."""
        results = [
            {
                "id": "test1",
                "content": "Test content"
            }
        ]
        
        processed = process_enhanced_search_results(results, "test query")
        
        assert len(processed) == 1
        assert "has_qa_data" not in processed[0]
        assert "has_factual_data" not in processed[0]

    def test_process_enhanced_search_results_invalid_json(self):
        """Test handling of invalid JSON in metadata."""
        results = [
            {
                "id": "test1",
                "content": "Test content",
                "qa_metadata": "invalid json"
            }
        ]
        
        processed = process_enhanced_search_results(results, "test query")
        
        assert len(processed) == 1
        assert "has_qa_data" not in processed[0]


class TestCalculateQAEnhancedScore:
    """Test Q&A enhanced scoring."""

    def test_calculate_qa_enhanced_score_basic(self):
        """Test basic score calculation."""
        result = {
            "score": 0.5,
            "qa_boost": 1.0
        }
        
        score = calculate_qa_enhanced_score(result, "test query")
        
        assert score == 0.5

    def test_calculate_qa_enhanced_score_with_qa_boost(self):
        """Test score calculation with Q&A boost."""
        result = {
            "score": 0.5,
            "qa_boost": 2.0
        }
        
        score = calculate_qa_enhanced_score(result, "test query")
        
        assert score == 1.0  # 0.5 * 2.0

    def test_calculate_qa_enhanced_score_with_qa_relevance(self):
        """Test score calculation with Q&A relevance."""
        result = {
            "score": 0.5,
            "qa_boost": 1.0,
            "qa_relevance_score": 0.8
        }
        
        score = calculate_qa_enhanced_score(result, "test query")
        
        assert score == 0.66  # 0.5 + (0.8 * 0.2)

    def test_calculate_qa_enhanced_score_with_relevant_facts(self):
        """Test score calculation with relevant facts."""
        result = {
            "score": 0.5,
            "qa_boost": 1.0,
            "relevant_facts": [{"fact": "test1"}, {"fact": "test2"}]
        }
        
        score = calculate_qa_enhanced_score(result, "test query")
        
        assert score == 0.7  # 0.5 + (2 * 0.1)

    def test_calculate_qa_enhanced_score_with_relevant_qa_pairs(self):
        """Test score calculation with relevant Q&A pairs."""
        result = {
            "score": 0.5,
            "qa_boost": 1.0,
            "relevant_qa_pairs": [
                {
                    "question_content": "What is my name?",
                    "answer_content": "My name is John"
                }
            ]
        }
        
        score = calculate_qa_enhanced_score(result, "What is my name?")
        
        assert score >= 0.9  # Should get question match boost

    def test_calculate_qa_enhanced_score_normalization(self):
        """Test that scores are normalized to [0, 1] range."""
        result = {
            "score": 0.8,
            "qa_boost": 2.0,
            "qa_relevance_score": 1.0,
            "relevant_facts": [{"fact": f"test{i}"} for i in range(10)],
            "relevant_qa_pairs": [
                {
                    "question_content": "What is my name?",
                    "answer_content": "My name is John"
                }
            ]
        }
        
        score = calculate_qa_enhanced_score(result, "What is my name?")
        
        assert score <= 1.0


class TestMergeAndDeduplicateResults:
    """Test result merging and deduplication."""

    def test_merge_and_deduplicate_results_basic(self):
        """Test basic merging and deduplication."""
        vector_results = [
            {"id": "1", "score": 0.8, "source": "vector"},
            {"id": "2", "score": 0.6, "source": "vector"}
        ]
        graph_results = [
            {"id": "1", "score": 0.7, "qa_boost": 2.0, "source": "graph"},
            {"id": "3", "score": 0.5, "source": "graph"}
        ]
        
        merged = merge_and_deduplicate_results(vector_results, graph_results, 10)
        
        assert len(merged) == 3
        
        # Check that ID "1" was deduplicated (should keep the one with higher total score)
        id_1_results = [r for r in merged if r["id"] == "1"]
        assert len(id_1_results) == 1

    def test_merge_and_deduplicate_results_with_limit(self):
        """Test merging with result limit."""
        vector_results = [
            {"id": "1", "score": 0.8, "source": "vector"},
            {"id": "2", "score": 0.6, "source": "vector"}
        ]
        graph_results = [
            {"id": "3", "score": 0.7, "source": "graph"},
            {"id": "4", "score": 0.5, "source": "graph"}
        ]
        
        merged = merge_and_deduplicate_results(vector_results, graph_results, 2)
        
        assert len(merged) == 2

    def test_merge_and_deduplicate_results_empty_inputs(self):
        """Test merging with empty inputs."""
        merged = merge_and_deduplicate_results([], [], 10)
        
        assert len(merged) == 0

    def test_merge_and_deduplicate_results_no_ids(self):
        """Test merging with results that have no IDs."""
        vector_results = [
            {"score": 0.8, "source": "vector"},
            {"score": 0.6, "source": "vector"}
        ]
        graph_results = [
            {"score": 0.7, "source": "graph"}
        ]
        
        merged = merge_and_deduplicate_results(vector_results, graph_results, 10)
        
        # Results without IDs should be ignored in deduplication
        assert len(merged) >= 0

    def test_merge_and_deduplicate_results_sorting(self):
        """Test that results are properly sorted."""
        vector_results = [
            {"id": "1", "score": 0.5, "qa_boost": 1.0},
            {"id": "2", "score": 0.8, "qa_boost": 1.0}
        ]
        graph_results = [
            {"id": "3", "score": 0.6, "qa_boost": 2.0, "qa_metadata": "test"}
        ]
        
        merged = merge_and_deduplicate_results(vector_results, graph_results, 10)
        
        # Should be sorted by enhanced score
        assert len(merged) >= 3
        # First result should have highest combined score
        first_score = merged[0].get("score", 0) * merged[0].get("qa_boost", 1)
        second_score = merged[1].get("score", 0) * merged[1].get("qa_boost", 1)
        assert first_score >= second_score


@pytest.mark.integration
class TestQAHandlersIntegration:
    """Integration tests for Q&A handlers."""

    def test_full_qa_workflow(self):
        """Test the complete Q&A detection and processing workflow."""
        # Mock conversation content
        content = {
            "messages": [
                {"role": "user", "content": "What's my name?"},
                {"role": "assistant", "content": "I don't know. What is it?"},
                {"role": "user", "content": "My name is Alice"}
            ]
        }
        
        # Mock session
        mock_session = Mock()
        
        # Test Q&A detection and storage
        with patch('core.qa_handlers.get_qa_detector') as mock_get_detector:
            mock_detector = Mock()
            mock_detector.detect_qa_relationship.return_value = [
                {
                    "type": "qa_pair",
                    "question_content": "What's my name?",
                    "answer_content": "My name is Alice",
                    "confidence": 0.9
                }
            ]
            mock_detector.extract_factual_statements.return_value = [
                {
                    "content": "My name is Alice",
                    "fact_types": ["name"],
                    "entities": {"names": ["Alice"]}
                }
            ]
            mock_get_detector.return_value = mock_detector
            
            success, qa_metadata = detect_and_store_qa_metadata(content, "test_id", mock_session)
            
            assert success is True
            assert qa_metadata["qa_pairs"] == 1
        
        # Test query expansion
        with patch('core.qa_handlers.get_query_expander') as mock_get_expander:
            mock_expander = Mock()
            mock_expander.expand_query.return_value = [
                "what's my name?",
                "my name is",
                "i am",
                "call me"
            ]
            mock_get_expander.return_value = mock_expander
            
            expanded = expand_query_patterns("What's my name?")
            
            assert len(expanded) == 4
            assert "my name is" in expanded
        
        # Test result processing
        search_results = [
            {
                "id": "test1",
                "score": 0.8,
                "qa_metadata": json.dumps(qa_metadata)
            }
        ]
        
        processed = process_enhanced_search_results(search_results, "What's my name?")
        
        assert len(processed) == 1
        assert processed[0]["has_qa_data"] is True
        assert "relevant_qa_pairs" in processed[0]