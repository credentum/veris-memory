#!/usr/bin/env python3
"""
Unit tests for QA Detector module.

Tests all functionality of question-answer relationship detection,
factual statement extraction, and entity recognition.
"""

import pytest
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.qa_detector import QADetector, get_qa_detector


class TestQADetector:
    """Test class for QADetector functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.detector = QADetector()

    def test_init(self):
        """Test QADetector initialization."""
        assert self.detector is not None
        assert len(self.detector.question_patterns) > 0
        assert len(self.detector.answer_patterns) > 0
        assert len(self.detector.question_words) > 0

    def test_is_question_with_question_mark(self):
        """Test question detection with question marks."""
        assert self.detector._is_question("What is your name?")
        assert self.detector._is_question("How are you?")
        assert self.detector._is_question("Where do you live?")

    def test_is_question_with_question_words(self):
        """Test question detection with question words."""
        assert self.detector._is_question("What is happening")
        assert self.detector._is_question("Who are you")
        assert self.detector._is_question("Where is the store")
        assert self.detector._is_question("How does this work")
        assert self.detector._is_question("Why did this happen")

    def test_is_question_with_patterns(self):
        """Test question detection with specific patterns."""
        assert self.detector._is_question("What's my name")
        assert self.detector._is_question("What do I do")
        assert self.detector._is_question("Tell me about myself")

    def test_is_question_negative_cases(self):
        """Test question detection negative cases."""
        assert not self.detector._is_question("My name is John")
        assert not self.detector._is_question("I work as an engineer")
        assert not self.detector._is_question("Hello there")
        assert not self.detector._is_question("")

    def test_is_answer_with_patterns(self):
        """Test answer detection with specific patterns."""
        assert self.detector._is_answer("My name is John")
        assert self.detector._is_answer("I work as an engineer")
        assert self.detector._is_answer("I live in San Francisco")
        assert self.detector._is_answer("My email is test@example.com")

    def test_is_answer_with_factual_info(self):
        """Test answer detection with factual information."""
        assert self.detector._is_answer("John Smith")  # Proper noun
        assert self.detector._is_answer("I am 25 years old")  # Contains number
        assert self.detector._is_answer("Contact me at john@test.com")  # Email

    def test_is_answer_negative_cases(self):
        """Test answer detection negative cases."""
        assert not self.detector._is_answer("What is your name?")
        assert not self.detector._is_answer("Hello there")
        assert not self.detector._is_answer("")
        assert not self.detector._is_answer("Maybe")

    def test_detect_qa_relationship_basic(self):
        """Test basic Q&A relationship detection."""
        messages = [
            {"role": "user", "content": "What is my name?"},
            {"role": "assistant", "content": "My name is John"}
        ]
        
        relationships = self.detector.detect_qa_relationship(messages)
        
        assert len(relationships) == 1
        assert relationships[0]["type"] == "qa_pair"
        assert relationships[0]["question_index"] == 0
        assert relationships[0]["answer_index"] == 1
        assert relationships[0]["confidence"] > 0.0

    def test_detect_qa_relationship_multiple_pairs(self):
        """Test detection of multiple Q&A pairs."""
        messages = [
            {"role": "user", "content": "What is my name?"},
            {"role": "assistant", "content": "My name is John"},
            {"role": "user", "content": "Where do I work?"},
            {"role": "assistant", "content": "I work at Google"}
        ]
        
        relationships = self.detector.detect_qa_relationship(messages)
        
        assert len(relationships) == 2
        assert all(rel["type"] == "qa_pair" for rel in relationships)

    def test_detect_qa_relationship_no_pairs(self):
        """Test when no Q&A pairs are detected."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        relationships = self.detector.detect_qa_relationship(messages)
        
        assert len(relationships) == 0

    def test_detect_qa_relationship_empty_input(self):
        """Test with empty or insufficient input."""
        assert self.detector.detect_qa_relationship([]) == []
        assert self.detector.detect_qa_relationship([{"role": "user", "content": "Hi"}]) == []

    def test_calculate_qa_confidence_high(self):
        """Test confidence calculation for strong Q&A pairs."""
        question = "What's my name?"
        answer = "My name is John"
        
        confidence = self.detector._calculate_qa_confidence(question, answer)
        
        assert confidence > 0.7  # Should be high confidence

    def test_calculate_qa_confidence_low(self):
        """Test confidence calculation for weak Q&A pairs."""
        question = "Hello"
        answer = "Hi"
        
        confidence = self.detector._calculate_qa_confidence(question, answer)
        
        assert confidence < 0.5  # Should be low confidence

    def test_extract_keywords(self):
        """Test keyword extraction."""
        text = "What is my name and email address?"
        keywords = self.detector._extract_keywords(text)
        
        assert "name" in keywords
        assert "email" in keywords
        assert "address" in keywords
        assert "what" not in keywords  # Stop word should be removed

    def test_extract_factual_statements(self):
        """Test factual statement extraction."""
        messages = [
            {"role": "user", "content": "What is my name?"},
            {"role": "user", "content": "My name is John"},
            {"role": "user", "content": "I work as an engineer"}
        ]
        
        facts = self.detector.extract_factual_statements(messages)
        
        assert len(facts) == 2  # Should find 2 factual statements
        assert any("My name is John" in fact["content"] for fact in facts)
        assert any("engineer" in fact["content"] for fact in facts)

    def test_classify_fact_type_name(self):
        """Test fact type classification for names."""
        fact_types = self.detector._classify_fact_type("My name is John")
        
        assert "name" in fact_types
        assert "personal" in fact_types

    def test_classify_fact_type_profession(self):
        """Test fact type classification for professions."""
        fact_types = self.detector._classify_fact_type("I work as an engineer")
        
        assert "profession" in fact_types

    def test_classify_fact_type_location(self):
        """Test fact type classification for locations."""
        fact_types = self.detector._classify_fact_type("I live in San Francisco")
        
        assert "location" in fact_types

    def test_classify_fact_type_contact(self):
        """Test fact type classification for contact info."""
        fact_types = self.detector._classify_fact_type("My email is test@example.com")
        
        assert "contact" in fact_types

    def test_classify_fact_type_preference(self):
        """Test fact type classification for preferences."""
        fact_types = self.detector._classify_fact_type("I like pizza")
        
        assert "preference" in fact_types

    def test_extract_entities_names(self):
        """Test entity extraction for names."""
        entities = self.detector._extract_entities("My name is John Smith")
        
        assert len(entities["names"]) > 0
        assert any("John" in name or "Smith" in name for name in entities["names"])

    def test_extract_entities_emails(self):
        """Test entity extraction for emails."""
        entities = self.detector._extract_entities("Contact me at john@example.com")
        
        assert "john@example.com" in entities["emails"]

    def test_extract_entities_phones(self):
        """Test entity extraction for phone numbers."""
        entities = self.detector._extract_entities("Call me at 555-123-4567")
        
        assert "555-123-4567" in entities["phones"]

    def test_extract_entities_multiple(self):
        """Test entity extraction with multiple types."""
        text = "I'm John Smith, email john@test.com, phone 555-123-4567"
        entities = self.detector._extract_entities(text)
        
        assert len(entities["names"]) > 0
        assert "john@test.com" in entities["emails"]
        assert "555-123-4567" in entities["phones"]

    def test_extract_entities_empty(self):
        """Test entity extraction with no entities."""
        entities = self.detector._extract_entities("Hello world")
        
        assert len(entities["names"]) == 0
        assert len(entities["emails"]) == 0
        assert len(entities["phones"]) == 0

    def test_edge_case_malformed_messages(self):
        """Test handling of malformed message structures."""
        malformed_messages = [
            {"content": "What is my name?"},  # Missing role
            {"role": "user"},  # Missing content
            {},  # Empty message
        ]
        
        # Should not crash
        relationships = self.detector.detect_qa_relationship(malformed_messages)
        facts = self.detector.extract_factual_statements(malformed_messages)
        
        assert isinstance(relationships, list)
        assert isinstance(facts, list)

    def test_edge_case_very_long_text(self):
        """Test handling of very long text."""
        long_text = "word " * 10000  # Very long text
        
        # Should not crash
        assert isinstance(self.detector._is_question(long_text), bool)
        assert isinstance(self.detector._is_answer(long_text), bool)
        assert isinstance(self.detector._extract_entities(long_text), dict)

    def test_edge_case_special_characters(self):
        """Test handling of special characters and unicode."""
        special_text = "What's my naïve résumé? 🤔"
        
        # Should not crash
        assert isinstance(self.detector._is_question(special_text), bool)
        keywords = self.detector._extract_keywords(special_text)
        assert isinstance(keywords, set)

    def test_confidence_bounds(self):
        """Test that confidence scores are always within bounds."""
        test_cases = [
            ("What's my name?", "My name is John"),
            ("", ""),
            ("Hello", "World"),
            ("What do I do?", "I work as an engineer")
        ]
        
        for question, answer in test_cases:
            confidence = self.detector._calculate_qa_confidence(question, answer)
            assert 0.0 <= confidence <= 1.0


class TestQADetectorGlobalInstance:
    """Test the global instance functionality."""

    def test_get_qa_detector_singleton(self):
        """Test that get_qa_detector returns the same instance."""
        detector1 = get_qa_detector()
        detector2 = get_qa_detector()
        
        assert detector1 is detector2

    def test_get_qa_detector_type(self):
        """Test that get_qa_detector returns correct type."""
        detector = get_qa_detector()
        
        assert isinstance(detector, QADetector)


@pytest.mark.integration
class TestQADetectorIntegration:
    """Integration tests for QA Detector with real-world scenarios."""

    def setup_method(self):
        """Setup test environment."""
        self.detector = QADetector()

    def test_real_conversation_scenario(self):
        """Test with a realistic conversation scenario."""
        messages = [
            {"role": "user", "content": "Hi there!"},
            {"role": "assistant", "content": "Hello! How can I help you?"},
            {"role": "user", "content": "What's my name?"},
            {"role": "assistant", "content": "I don't have your name saved yet. Could you tell me?"},
            {"role": "user", "content": "My name is Alice Johnson"},
            {"role": "assistant", "content": "Nice to meet you, Alice! I'll remember that."},
            {"role": "user", "content": "What do I do for work?"},
            {"role": "user", "content": "I work as a data scientist at Google"}
        ]
        
        relationships = self.detector.detect_qa_relationship(messages)
        facts = self.detector.extract_factual_statements(messages)
        
        # Should detect multiple relationships
        assert len(relationships) >= 2
        
        # Should extract factual statements
        assert len(facts) >= 2
        
        # Should find name information
        name_facts = [f for f in facts if "name" in f["fact_types"]]
        assert len(name_facts) > 0
        
        # Should find profession information
        prof_facts = [f for f in facts if "profession" in f["fact_types"]]
        assert len(prof_facts) > 0

    def test_multilingual_entities(self):
        """Test entity extraction with international names."""
        text = "My name is José García-López, email josé@empresa.es"
        entities = self.detector._extract_entities(text)
        
        # Should handle international characters
        assert "josé@empresa.es" in entities["emails"]

    def test_complex_professional_info(self):
        """Test with complex professional information."""
        messages = [
            {"role": "user", "content": "What's my job?"},
            {"role": "user", "content": "I work as a Senior Software Engineer at Microsoft, specializing in AI/ML"}
        ]
        
        facts = self.detector.extract_factual_statements(messages)
        prof_facts = [f for f in facts if "profession" in f["fact_types"]]
        
        assert len(prof_facts) > 0