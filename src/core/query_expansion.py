#!/usr/bin/env python3
"""
Query expansion for improving semantic search recall.

This module implements query expansion strategies to transform user questions
into multiple search patterns that can find semantically related answers.
"""

import logging
import re
from typing import List, Set, Dict, Any, Optional

logger = logging.getLogger(__name__)


class QueryExpander:
    """Expands queries to improve retrieval of semantically related content."""
    
    def __init__(self) -> None:
        """Initialize the query expander with predefined patterns."""
        # Question patterns and their corresponding answer patterns
        self.question_answer_patterns = {
            # Name-related queries
            r"what.?s my name|what is my name|who am i": [
                "my name is", "i am", "i'm called", "call me", "name:"
            ],
            # Identity/profession queries
            r"what do i do|what.?s my job|what is my work|what.?s my profession": [
                "i work", "my job is", "i am a", "profession:", "work as"
            ],
            # Location queries
            r"where do i live|where am i from|what.?s my location": [
                "i live", "from", "located", "address:", "city:"
            ],
            # Age queries
            r"how old am i|what.?s my age|what is my age": [
                "i am", "years old", "age:", "born"
            ],
            # Preference queries
            r"what do i like|what are my preferences|what.?s my favorite": [
                "i like", "i love", "favorite", "prefer", "enjoy"
            ],
            # Contact queries
            r"what.?s my phone|what.?s my email|how to contact": [
                "phone:", "email:", "contact:", "@", "number:"
            ],
            # General information queries
            r"what do you know about me|tell me about myself": [
                "my", "i am", "i have", "i work", "i live", "i like"
            ]
        }
        
        # Bidirectional patterns - find questions when given answers
        self.answer_question_patterns = {
            r"my name is|i am called|call me": [
                "what's my name", "who am i", "what is my name"
            ],
            r"i work|my job is|i am a": [
                "what do i do", "what's my job", "what is my work"
            ],
            r"i live|from|located": [
                "where do i live", "where am i from", "what's my location"
            ]
        }
    
    def expand_query(self, query: str) -> List[str]:
        """Expand a query into multiple search patterns.
        
        Args:
            query: Original search query
            
        Returns:
            List of expanded query patterns including the original
        """
        expanded_queries = [query.lower().strip()]
        query_lower = query.lower().strip()
        
        # Check for question patterns
        for pattern, expansions in self.question_answer_patterns.items():
            if re.search(pattern, query_lower):
                expanded_queries.extend(expansions)
                logger.debug(f"Expanded question '{query}' with patterns: {expansions}")
                break
        
        # Check for answer patterns (bidirectional search)
        for pattern, questions in self.answer_question_patterns.items():
            if re.search(pattern, query_lower):
                expanded_queries.extend(questions)
                logger.debug(f"Found answer pattern in '{query}', adding related questions: {questions}")
                break
        
        # Add common variations
        expanded_queries.extend(self._generate_variations(query_lower))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in expanded_queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)
        
        logger.info(f"Expanded query '{query}' into {len(unique_queries)} patterns")
        return unique_queries
    
    def _generate_variations(self, query: str) -> List[str]:
        """Generate common variations of the query.
        
        Args:
            query: Original query
            
        Returns:
            List of query variations
        """
        variations = []
        
        # Remove question words for broader matching
        question_words = ["what", "where", "when", "who", "how", "why", "is", "are", "do", "does"]
        words = query.split()
        filtered_words = [w for w in words if w.lower() not in question_words]
        if len(filtered_words) > 0 and len(filtered_words) < len(words):
            variations.append(" ".join(filtered_words))
        
        # Extract key terms (longer than 2 characters)
        key_terms = [w for w in words if len(w) > 2]
        if key_terms:
            variations.append(" ".join(key_terms))
        
        return variations
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract potential entities from text for better matching.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary of entity types and their values
        """
        entities = {
            "names": [],
            "emails": [],
            "phones": [],
            "locations": [],
            "professions": []
        }
        
        text_lower = text.lower()
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, text)
        
        # Extract phone numbers (simple patterns)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        entities["phones"] = re.findall(phone_pattern, text)
        
        # Extract potential names (capitalized words after "my name is", "i am", etc.)
        name_patterns = [
            r"my name is (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"i'm (\w+)"
        ]
        for pattern in name_patterns:
            matches = re.findall(pattern, text_lower)
            entities["names"].extend(matches)
        
        # Extract potential professions
        profession_patterns = [
            r"i work as (?:a |an )?(\w+)",
            r"i am (?:a |an )?(\w+)",
            r"my job is (\w+)",
            r"profession: (\w+)"
        ]
        for pattern in profession_patterns:
            matches = re.findall(pattern, text_lower)
            entities["professions"].extend(matches)
        
        return entities


# Global instance for reuse
_global_expander = None


def get_query_expander() -> QueryExpander:
    """Get or create global query expander instance."""
    global _global_expander
    if _global_expander is None:
        _global_expander = QueryExpander()
    return _global_expander