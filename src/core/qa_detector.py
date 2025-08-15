#!/usr/bin/env python3
"""
Question-Answer relationship detector for enhanced memory storage.

This module detects Q&A patterns in conversation contexts and creates
explicit relationships between questions and their answers.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class QADetector:
    """Detects question-answer patterns in conversation contexts."""
    
    def __init__(self) -> None:
        """Initialize the Q&A detector with pattern definitions."""
        # Question patterns that indicate a user is asking for information
        self.question_patterns = [
            # Name questions
            r"what.?s my name|what is my name|who am i",
            # Identity/profession questions
            r"what do i do|what.?s my job|what is my work|what.?s my profession",
            # Location questions  
            r"where do i live|where am i from|what.?s my location",
            # Age questions
            r"how old am i|what.?s my age|what is my age",
            # Preference questions
            r"what do i like|what are my preferences|what.?s my favorite",
            # Contact questions
            r"what.?s my phone|what.?s my email|how to contact",
            # General questions
            r"what do you know about me|tell me about myself",
            # Generic question patterns
            r"what.?s|what is|who|where|when|how|why|can you tell me"
        ]
        
        # Answer patterns that provide factual information
        self.answer_patterns = [
            # Name answers
            r"my name is|i am|i'm called|call me",
            # Identity/profession answers
            r"i work|my job is|i am a|profession:|work as",
            # Location answers
            r"i live|from|located|address:",
            # Contact answers
            r"phone:|email:|contact:|@|\d{3}[-.]?\d{3}[-.]?\d{4}",
            # Preference answers
            r"i like|i love|favorite|prefer|enjoy",
            # Generic factual statements
            r"my .+ is|i have|i own|i use"
        ]
        
        # Question words that indicate information seeking
        self.question_words: Set[str] = {"what", "who", "where", "when", "how", "why", "which", "whose"}
    
    def detect_qa_relationship(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect Q&A relationships in a conversation thread.
        
        Args:
            messages: List of conversation messages with 'role' and 'content'
            
        Returns:
            List of detected Q&A relationships with metadata
        """
        relationships = []
        
        if len(messages) < 2:
            return relationships
        
        # Look for question-answer pairs in consecutive messages
        for i in range(len(messages) - 1):
            current_msg = messages[i]
            next_msg = messages[i + 1]
            
            # Check if current message is a question and next is an answer
            if self._is_question(current_msg.get("content", "")):
                if self._is_answer(next_msg.get("content", "")):
                    # Found a Q&A pair
                    relationship = {
                        "type": "qa_pair",
                        "question_index": i,
                        "answer_index": i + 1,
                        "question_content": current_msg.get("content", ""),
                        "answer_content": next_msg.get("content", ""),
                        "question_role": current_msg.get("role", ""),
                        "answer_role": next_msg.get("role", ""),
                        "confidence": self._calculate_qa_confidence(
                            current_msg.get("content", ""),
                            next_msg.get("content", "")
                        )
                    }
                    relationships.append(relationship)
                    logger.debug(f"Detected Q&A pair: '{current_msg.get('content', '')[:50]}...' -> '{next_msg.get('content', '')[:50]}...'")
        
        return relationships
    
    def _is_question(self, text: str) -> bool:
        """Check if text appears to be a question.
        
        Args:
            text: Text to analyze
            
        Returns:
            True if text appears to be a question
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Check for question mark
        if text_lower.endswith("?"):
            return True
        
        # Check for question patterns
        for pattern in self.question_patterns:
            if re.search(pattern, text_lower):
                return True
        
        # Check for question words at start of sentence
        words = text_lower.split()
        if words and words[0] in self.question_words:
            return True
        
        return False
    
    def _is_answer(self, text: str) -> bool:
        """Check if text appears to be an informative answer.
        
        Args:
            text: Text to analyze
            
        Returns:
            True if text appears to provide factual information
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Check for answer patterns
        for pattern in self.answer_patterns:
            if re.search(pattern, text_lower):
                return True
        
        # Check for factual statements (contains specific information)
        # Simple heuristic: contains proper nouns, numbers, or specific details
        if re.search(r'\b[A-Z][a-z]+\b|\b\d+\b|@|\w+\.\w+', text):
            return True
        
        return False
    
    def _calculate_qa_confidence(self, question: str, answer: str) -> float:
        """Calculate confidence score for a Q&A pair.
        
        Args:
            question: Question text
            answer: Answer text
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.0
        
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        # Base confidence for being detected as Q&A
        confidence += 0.3
        
        # Boost for explicit question markers
        if question_lower.endswith("?"):
            confidence += 0.2
        
        # Boost for strong question patterns
        strong_question_patterns = [
            r"what.?s my|what is my|who am i",
            r"what do i|where do i",
            r"tell me about|what do you know"
        ]
        for pattern in strong_question_patterns:
            if re.search(pattern, question_lower):
                confidence += 0.2
                break
        
        # Boost for strong answer patterns
        strong_answer_patterns = [
            r"my name is|i am|i'm called",
            r"i work|my job is",
            r"i live|i'm from"
        ]
        for pattern in strong_answer_patterns:
            if re.search(pattern, answer_lower):
                confidence += 0.2
                break
        
        # Boost for semantic relevance (simple keyword matching)
        question_keywords = self._extract_keywords(question_lower)
        answer_keywords = self._extract_keywords(answer_lower)
        
        common_keywords = question_keywords & answer_keywords
        if common_keywords:
            confidence += min(0.1 * len(common_keywords), 0.3)
        
        return min(confidence, 1.0)
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract relevant keywords from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Set of relevant keywords
        """
        # Remove common stop words and extract meaningful terms
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "what", "who", "where", "when", "how", "why"}
        
        # Extract words longer than 2 characters
        words = re.findall(r'\b\w{3,}\b', text.lower())
        keywords = {word for word in words if word not in stop_words}
        
        return keywords
    
    def extract_factual_statements(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract factual statements that could answer future questions.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            List of factual statements with metadata
        """
        facts = []
        
        for i, message in enumerate(messages):
            content = message.get("content", "")
            if self._is_answer(content):
                # Extract specific fact types
                fact_info = {
                    "message_index": i,
                    "content": content,
                    "role": message.get("role", ""),
                    "fact_types": self._classify_fact_type(content),
                    "entities": self._extract_entities(content)
                }
                facts.append(fact_info)
        
        return facts
    
    def _classify_fact_type(self, text: str) -> List[str]:
        """Classify the type of factual information in text.
        
        Args:
            text: Text to classify
            
        Returns:
            List of fact types detected
        """
        text_lower = text.lower()
        fact_types = []
        
        type_patterns = {
            "name": [r"my name is|i am|i'm called|call me"],
            "profession": [r"i work|my job is|i am a|profession:"],
            "location": [r"i live|from|located|address:"],
            "contact": [r"phone:|email:|contact:|@"],
            "preference": [r"i like|i love|favorite|prefer"],
            "personal": [r"my .+ is|i have|i own"]
        }
        
        for fact_type, patterns in type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    fact_types.append(fact_type)
                    break
        
        return fact_types
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from factual text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary of entity types and values
        """
        entities = {
            "names": [],
            "emails": [],
            "phones": [],
            "locations": [],
            "organizations": []
        }
        
        # Extract email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        entities["emails"] = emails
        
        # Extract phone numbers
        phones = re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', text)
        entities["phones"] = phones
        
        # Extract potential names (simple heuristic)
        name_patterns = [
            r"my name is (\w+(?:\s+\w+)?)",
            r"i am (\w+(?:\s+\w+)?)",
            r"call me (\w+)"
        ]
        for pattern in name_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["names"].extend(matches)
        
        return entities


# Global instance for reuse
_global_qa_detector = None


def get_qa_detector() -> QADetector:
    """Get or create global Q&A detector instance."""
    global _global_qa_detector
    if _global_qa_detector is None:
        _global_qa_detector = QADetector()
    return _global_qa_detector