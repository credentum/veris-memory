#!/usr/bin/env python3
"""
Unit tests for Query Expansion module.

Tests all functionality of query expansion patterns, bidirectional search,
and entity extraction for improved semantic retrieval.
"""

import pytest
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.query_expansion import QueryExpander, get_query_expander


class TestQueryExpander:
    """Test class for QueryExpander functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.expander = QueryExpander()

    def test_init(self):
        """Test QueryExpander initialization."""
        assert self.expander is not None
        assert len(self.expander.question_answer_patterns) > 0
        assert len(self.expander.answer_question_patterns) > 0

    def test_expand_query_basic(self):
        """Test basic query expansion."""
        expanded = self.expander.expand_query("Hello")
        
        assert isinstance(expanded, list)
        assert len(expanded) >= 1
        assert "hello" in expanded  # Original query should be included

    def test_expand_query_name_questions(self):
        """Test expansion of name-related questions."""
        test_queries = [
            "What's my name?",
            "What is my name?", 
            "Who am I?"
        ]
        
        for query in test_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include original and expansions
            assert len(expanded) > 1
            
            # Should include name answer patterns
            expected_patterns = ["my name is", "i am", "call me"]
            found_patterns = [p for p in expected_patterns if any(p in exp for exp in expanded)]
            assert len(found_patterns) > 0

    def test_expand_query_profession_questions(self):
        """Test expansion of profession-related questions."""
        test_queries = [
            "What do I do?",
            "What's my job?",
            "What is my profession?"
        ]
        
        for query in test_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include profession answer patterns
            expected_patterns = ["i work", "my job is", "i am a"]
            found_patterns = [p for p in expected_patterns if any(p in exp for exp in expanded)]
            assert len(found_patterns) > 0

    def test_expand_query_location_questions(self):
        """Test expansion of location-related questions."""
        test_queries = [
            "Where do I live?",
            "Where am I from?",
            "What's my location?"
        ]
        
        for query in test_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include location answer patterns
            expected_patterns = ["i live", "from", "located"]
            found_patterns = [p for p in expected_patterns if any(p in exp for exp in expanded)]
            assert len(found_patterns) > 0

    def test_expand_query_age_questions(self):
        """Test expansion of age-related questions."""
        test_queries = [
            "How old am I?",
            "What's my age?",
            "What is my age?"
        ]
        
        for query in test_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include age answer patterns
            expected_patterns = ["i am", "years old", "age:", "born"]
            found_patterns = [p for p in expected_patterns if any(p in exp for exp in expanded)]
            assert len(found_patterns) > 0

    def test_expand_query_preference_questions(self):
        """Test expansion of preference-related questions."""
        test_queries = [
            "What do I like?",
            "What are my preferences?",
            "What's my favorite?"
        ]
        
        for query in test_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include preference answer patterns
            expected_patterns = ["i like", "i love", "favorite", "prefer"]
            found_patterns = [p for p in expected_patterns if any(p in exp for exp in expanded)]
            assert len(found_patterns) > 0

    def test_expand_query_contact_questions(self):
        """Test expansion of contact-related questions."""
        test_queries = [
            "What's my phone?",
            "What's my email?",
            "How to contact me?"
        ]
        
        for query in test_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include contact answer patterns
            expected_patterns = ["phone:", "email:", "contact:", "@"]
            found_patterns = [p for p in expected_patterns if any(p in exp for exp in expanded)]
            assert len(found_patterns) > 0

    def test_expand_query_bidirectional_name(self):
        """Test bidirectional expansion for name answers."""
        answer_queries = [
            "My name is John",
            "I am called Alice",
            "Call me Bob"
        ]
        
        for query in answer_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include related questions
            expected_questions = ["what's my name", "who am i", "what is my name"]
            found_questions = [q for q in expected_questions if any(q in exp for exp in expanded)]
            assert len(found_questions) > 0

    def test_expand_query_bidirectional_profession(self):
        """Test bidirectional expansion for profession answers."""
        answer_queries = [
            "I work as an engineer",
            "My job is teaching",
            "I am a doctor"
        ]
        
        for query in answer_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include related questions
            expected_questions = ["what do i do", "what's my job", "what is my work"]
            found_questions = [q for q in expected_questions if any(q in exp for exp in expanded)]
            assert len(found_questions) > 0

    def test_expand_query_bidirectional_location(self):
        """Test bidirectional expansion for location answers."""
        answer_queries = [
            "I live in California",
            "I'm from New York",
            "Located in Seattle"
        ]
        
        for query in answer_queries:
            expanded = self.expander.expand_query(query)
            
            # Should include related questions
            expected_questions = ["where do i live", "where am i from", "what's my location"]
            found_questions = [q for q in expected_questions if any(q in exp for exp in expanded)]
            assert len(found_questions) > 0

    def test_generate_variations(self):
        """Test generation of query variations."""
        query = "What is my full name?"
        variations = self.expander._generate_variations(query)
        
        assert isinstance(variations, list)
        # Should remove question words and generate key terms
        assert any("name" in var for var in variations)

    def test_generate_variations_question_word_removal(self):
        """Test removal of question words in variations."""
        query = "What do you think about this?"
        variations = self.expander._generate_variations(query)
        
        # Should have variations without question words
        filtered_var = [var for var in variations if "what" not in var.lower()]
        assert len(filtered_var) > 0

    def test_generate_variations_key_terms(self):
        """Test extraction of key terms."""
        query = "How does machine learning work?"
        variations = self.expander._generate_variations(query)
        
        # Should extract meaningful terms
        key_terms = " ".join(variations).lower()
        assert "machine" in key_terms
        assert "learning" in key_terms

    def test_extract_entities_names(self):
        """Test entity extraction for names."""
        text = "My name is John Smith and I work here"
        entities = self.expander.extract_entities(text)
        
        assert "names" in entities
        assert len(entities["names"]) > 0

    def test_extract_entities_emails(self):
        """Test entity extraction for emails."""
        text = "Contact me at john.smith@company.com for questions"
        entities = self.expander.extract_entities(text)
        
        assert "emails" in entities
        assert "john.smith@company.com" in entities["emails"]

    def test_extract_entities_phones(self):
        """Test entity extraction for phone numbers."""
        text = "Call me at 555-123-4567 or 555.987.6543"
        entities = self.expander.extract_entities(text)
        
        assert "phones" in entities
        assert len(entities["phones"]) >= 1

    def test_extract_entities_professions(self):
        """Test entity extraction for professions."""
        text = "I work as a software engineer at the company"
        entities = self.expander.extract_entities(text)
        
        assert "professions" in entities
        assert len(entities["professions"]) > 0

    def test_extract_entities_multiple_types(self):
        """Test entity extraction with multiple entity types."""
        text = "I'm John Smith, work as an engineer, email john@test.com, phone 555-123-4567"
        entities = self.expander.extract_entities(text)
        
        assert len(entities["names"]) > 0
        assert len(entities["emails"]) > 0
        assert len(entities["phones"]) > 0
        assert len(entities["professions"]) > 0

    def test_extract_entities_empty_text(self):
        """Test entity extraction with empty text."""
        entities = self.expander.extract_entities("")
        
        assert all(len(entities[key]) == 0 for key in entities.keys())

    def test_extract_entities_no_entities(self):
        """Test entity extraction with text containing no entities."""
        text = "Hello world this is a test"
        entities = self.expander.extract_entities(text)
        
        assert all(len(entities[key]) == 0 for key in entities.keys())

    def test_deduplication(self):
        """Test that expanded queries are deduplicated."""
        query = "What's my name? What's my name?"  # Intentional duplication
        expanded = self.expander.expand_query(query)
        
        # Should not have duplicates
        assert len(expanded) == len(set(expanded))

    def test_case_insensitive_processing(self):
        """Test that processing is case insensitive."""
        queries = [
            "What's my name?",
            "WHAT'S MY NAME?",
            "what's my name?"
        ]
        
        expansions = [self.expander.expand_query(q) for q in queries]
        
        # Should produce similar results (normalized to lowercase)
        normalized_expansions = [set(exp) for exp in expansions]
        
        # Should have significant overlap
        common = normalized_expansions[0].intersection(*normalized_expansions[1:])
        assert len(common) > 0

    def test_edge_case_empty_query(self):
        """Test handling of empty query."""
        expanded = self.expander.expand_query("")
        
        assert isinstance(expanded, list)
        assert len(expanded) >= 1  # Should at least contain the empty string

    def test_edge_case_whitespace_query(self):
        """Test handling of whitespace-only query."""
        expanded = self.expander.expand_query("   ")
        
        assert isinstance(expanded, list)

    def test_edge_case_very_long_query(self):
        """Test handling of very long query."""
        long_query = "What is " + "very " * 1000 + "long query?"
        expanded = self.expander.expand_query(long_query)
        
        assert isinstance(expanded, list)
        assert len(expanded) >= 1

    def test_edge_case_special_characters(self):
        """Test handling of special characters and unicode."""
        special_query = "What's my naïve résumé? 🤔"
        expanded = self.expander.expand_query(special_query)
        
        assert isinstance(expanded, list)
        assert len(expanded) >= 1

    def test_edge_case_numbers_and_symbols(self):
        """Test handling of queries with numbers and symbols."""
        symbol_query = "What's my phone #? Is it 555-123-4567?"
        expanded = self.expander.expand_query(symbol_query)
        
        assert isinstance(expanded, list)
        # Should handle phone patterns
        phone_patterns = [exp for exp in expanded if "phone" in exp or "@" in exp]
        assert len(phone_patterns) > 0

    def test_pattern_coverage(self):
        """Test that all major question patterns are covered."""
        test_questions = [
            "What's my name?",
            "What do I do?", 
            "Where do I live?",
            "How old am I?",
            "What do I like?",
            "What's my email?",
            "Tell me about myself"
        ]
        
        for question in test_questions:
            expanded = self.expander.expand_query(question)
            
            # Each question should generate multiple expansions
            assert len(expanded) > 2
            
            # Should include the original (normalized)
            assert question.lower().strip() in expanded

    def test_answer_pattern_coverage(self):
        """Test that answer patterns trigger question expansions."""
        test_answers = [
            "My name is John",
            "I work as an engineer",
            "I live in California"
        ]
        
        for answer in test_answers:
            expanded = self.expander.expand_query(answer)
            
            # Should generate related questions
            question_words = ["what", "where", "who", "how"]
            has_question_expansion = any(
                any(qw in exp for qw in question_words) 
                for exp in expanded
            )
            assert has_question_expansion


class TestQueryExpanderGlobalInstance:
    """Test the global instance functionality."""

    def test_get_query_expander_singleton(self):
        """Test that get_query_expander returns the same instance."""
        expander1 = get_query_expander()
        expander2 = get_query_expander()
        
        assert expander1 is expander2

    def test_get_query_expander_type(self):
        """Test that get_query_expander returns correct type."""
        expander = get_query_expander()
        
        assert isinstance(expander, QueryExpander)


@pytest.mark.integration
class TestQueryExpanderIntegration:
    """Integration tests for Query Expander with real-world scenarios."""

    def setup_method(self):
        """Setup test environment."""
        self.expander = QueryExpander()

    def test_real_world_name_scenario(self):
        """Test the exact Issue #43 scenario."""
        query = "What's my name?"
        stored_content = "My name is Matt"
        
        expanded = self.expander.expand_query(query)
        
        # Should find a match with the stored content
        matches = []
        for expansion in expanded:
            if expansion.lower() in stored_content.lower():
                matches.append(expansion)
        
        assert len(matches) > 0, f"No matches found. Expanded: {expanded}"
        assert "my name is" in matches

    def test_profession_scenarios(self):
        """Test various profession-related scenarios."""
        scenarios = [
            ("What do I do for work?", "I work as a software engineer"),
            ("What's my profession?", "My job is teaching"),
            ("What is my occupation?", "I am a doctor")
        ]
        
        for question, answer in scenarios:
            expanded = self.expander.expand_query(question)
            
            # Should find matches
            matches = [exp for exp in expanded if any(word in answer.lower() for word in exp.lower().split())]
            assert len(matches) > 0

    def test_contact_information_scenarios(self):
        """Test contact information retrieval scenarios."""
        scenarios = [
            ("What's my email?", "My email is john@example.com"),
            ("How can someone contact me?", "Contact me at 555-123-4567"),
            ("What's my phone number?", "Phone: (555) 987-6543")
        ]
        
        for question, answer in scenarios:
            expanded = self.expander.expand_query(question)
            
            # Should find contact patterns
            contact_patterns = [exp for exp in expanded if any(pat in exp for pat in ["email", "phone", "contact", "@"])]
            assert len(contact_patterns) > 0

    def test_multilingual_names(self):
        """Test with international names and characters."""
        scenarios = [
            ("What's my name?", "My name is José García"),
            ("Who am I?", "I'm François Müller"),
            ("What's my name?", "Call me Александр")
        ]
        
        for question, answer in scenarios:
            expanded = self.expander.expand_query(question)
            entities = self.expander.extract_entities(answer)
            
            # Should extract name entities
            assert len(entities["names"]) > 0

    def test_complex_professional_titles(self):
        """Test with complex professional information."""
        question = "What do I do?"
        complex_answers = [
            "I work as a Senior Software Engineer at Google",
            "My job is Principal Data Scientist specializing in AI/ML",
            "I am the Chief Technology Officer and co-founder"
        ]
        
        expanded = self.expander.expand_query(question)
        
        for answer in complex_answers:
            # Should find profession patterns
            prof_patterns = [exp for exp in expanded if any(word in answer.lower() for word in exp.lower().split())]
            assert len(prof_patterns) > 0

    def test_performance_with_many_expansions(self):
        """Test performance with complex queries that generate many expansions."""
        complex_query = "What do you know about my personal and professional background including my name, job, location, and contact information?"
        
        # Should not timeout or crash
        expanded = self.expander.expand_query(complex_query)
        
        assert isinstance(expanded, list)
        assert len(expanded) > 0
        
        # Should generate expansions for multiple categories
        categories_found = []
        if any("name" in exp for exp in expanded):
            categories_found.append("name")
        if any("work" in exp or "job" in exp for exp in expanded):
            categories_found.append("profession")
        if any("live" in exp or "location" in exp for exp in expanded):
            categories_found.append("location")
        if any("contact" in exp or "@" in exp for exp in expanded):
            categories_found.append("contact")
        
        assert len(categories_found) >= 2  # Should cover multiple categories