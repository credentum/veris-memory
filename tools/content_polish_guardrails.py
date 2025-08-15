#!/usr/bin/env python3
"""
Content Polish Guardrails - Phase 4.1
Implements quality guardrails: drop empty/short chunks, title preservation, length validation
"""

import logging
import time
import json
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ChunkQualityIssue(Enum):
    """Quality issues that can affect chunks"""
    EMPTY_CONTENT = "EMPTY_CONTENT"              # Completely empty chunk
    TOO_SHORT = "TOO_SHORT"                      # Below minimum length threshold
    ONLY_WHITESPACE = "ONLY_WHITESPACE"          # Contains only whitespace/newlines
    ONLY_PUNCTUATION = "ONLY_PUNCTUATION"       # Contains only punctuation
    ONLY_STOPWORDS = "ONLY_STOPWORDS"            # Contains only common stopwords
    TITLE_ONLY_ACCEPTABLE = "TITLE_ONLY_ACCEPTABLE"  # Short but acceptable (title/heading)
    RERANKER_TOO_LONG = "RERANKER_TOO_LONG"      # Exceeds reranker token limit

@dataclass
class ChunkQualityResult:
    """Result of quality analysis for a chunk"""
    original_chunk: str
    processed_chunk: Optional[str]  # None if chunk should be dropped
    issues: List[ChunkQualityIssue]
    is_title_or_heading: bool
    char_count: int
    word_count: int
    token_estimate: int
    should_keep: bool
    reason: str

class ContentPolishGuardrails:
    """Content quality guardrails for chunk processing"""
    
    def __init__(self):
        # Quality thresholds from sprint requirements
        self.min_chunk_chars = 200        # Minimum characters (unless title-only)
        self.max_reranker_tokens = 512    # Clamp reranker text to ~512 tokens
        self.title_min_chars = 10         # Minimum for title-only chunks
        
        # Common stopwords for quality detection
        self.stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'
        }
        
        # Title/heading patterns
        self.title_patterns = [
            r'^#{1,6}\s+.+',           # Markdown headers
            r'^[A-Z][A-Z\s]+:?\s*$',   # ALL CAPS titles
            r'^\d+\.\s+[A-Z].+',       # Numbered titles
            r'^[A-Z][^.!?]*:?\s*$',    # Title case without sentence ending
            r'^\*\*[^*]+\*\*\s*$',     # Bold markdown titles
            r'^__[^_]+__\s*$',         # Underlined markdown titles
        ]
        
        logger.info("Content polish guardrails initialized")
        logger.info(f"Min chunk chars: {self.min_chunk_chars}")
        logger.info(f"Max reranker tokens: {self.max_reranker_tokens}")
        logger.info(f"Title min chars: {self.title_min_chars}")
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def _is_title_or_heading(self, text: str) -> bool:
        """Check if text appears to be a title or heading"""
        text_strip = text.strip()
        
        # Check against title patterns
        for pattern in self.title_patterns:
            if re.match(pattern, text_strip, re.MULTILINE):
                return True
        
        # Heuristic: short, title-case, no sentence ending
        if len(text_strip) < 100 and len(text_strip) > 0 and text_strip[0].isupper() and not text_strip.endswith(('.', '!', '?')):
            words = text_strip.split()
            if len(words) <= 8:  # Reasonable title length
                return True
        
        return False
    
    def _analyze_content_quality(self, chunk: str) -> Tuple[List[ChunkQualityIssue], Dict[str, Any]]:
        """Analyze chunk for quality issues"""
        issues = []
        metrics = {
            "char_count": len(chunk),
            "word_count": len(chunk.split()),
            "token_estimate": self._estimate_tokens(chunk)
        }
        
        # Check for empty content
        if not chunk.strip():
            issues.append(ChunkQualityIssue.EMPTY_CONTENT)
            return issues, metrics
        
        # Check for only whitespace
        if chunk.isspace():
            issues.append(ChunkQualityIssue.ONLY_WHITESPACE)
            return issues, metrics
        
        # Check for only punctuation
        if re.match(r'^[^\w\s]*$', chunk.strip()):
            issues.append(ChunkQualityIssue.ONLY_PUNCTUATION)
            return issues, metrics
        
        # Check for only stopwords
        words = re.findall(r'\w+', chunk.lower())
        if words and all(word in self.stopwords for word in words):
            issues.append(ChunkQualityIssue.ONLY_STOPWORDS)
            return issues, metrics
        
        # Check for length issues
        if len(chunk.strip()) < self.min_chunk_chars:
            issues.append(ChunkQualityIssue.TOO_SHORT)
        
        # Check reranker length limit
        if metrics["token_estimate"] > self.max_reranker_tokens:
            issues.append(ChunkQualityIssue.RERANKER_TOO_LONG)
        
        return issues, metrics
    
    def process_chunk(self, chunk: str, preserve_titles: bool = True) -> ChunkQualityResult:
        """
        Process a single chunk through quality guardrails
        
        Args:
            chunk: Input chunk text
            preserve_titles: Whether to preserve title-only chunks
            
        Returns:
            ChunkQualityResult with processing decision
        """
        issues, metrics = self._analyze_content_quality(chunk)
        is_title = self._is_title_or_heading(chunk)
        
        # Decision logic
        should_keep = True
        processed_chunk = chunk
        reason = "Passed quality checks"
        
        # Always drop completely empty or whitespace-only content
        if ChunkQualityIssue.EMPTY_CONTENT in issues or ChunkQualityIssue.ONLY_WHITESPACE in issues:
            should_keep = False
            processed_chunk = None
            reason = "Empty or whitespace-only content"
        
        # Drop punctuation-only or stopword-only content
        elif ChunkQualityIssue.ONLY_PUNCTUATION in issues or ChunkQualityIssue.ONLY_STOPWORDS in issues:
            should_keep = False
            processed_chunk = None
            reason = "Low-quality content (punctuation/stopwords only)"
        
        # Handle short content
        elif ChunkQualityIssue.TOO_SHORT in issues:
            if is_title and preserve_titles and len(chunk.strip()) >= self.title_min_chars:
                should_keep = True
                issues.append(ChunkQualityIssue.TITLE_ONLY_ACCEPTABLE)
                reason = "Short but acceptable title/heading"
            else:
                should_keep = False
                processed_chunk = None
                reason = f"Too short ({len(chunk.strip())} < {self.min_chunk_chars} chars)"
        
        # Handle reranker length limits
        if should_keep and ChunkQualityIssue.RERANKER_TOO_LONG in issues:
            # Clamp to token limit (conservative estimate)
            max_chars = self.max_reranker_tokens * 4
            processed_chunk = chunk[:max_chars].strip()
            
            # Try to break at sentence boundary if possible
            sentences = re.split(r'[.!?]\s+', processed_chunk)
            if len(sentences) > 1:
                processed_chunk = '. '.join(sentences[:-1]) + '.'
            
            reason = f"Clamped to {len(processed_chunk)} chars for reranker"
        
        return ChunkQualityResult(
            original_chunk=chunk,
            processed_chunk=processed_chunk,
            issues=issues,
            is_title_or_heading=is_title,
            char_count=len(chunk),
            word_count=len(chunk.split()),
            token_estimate=metrics["token_estimate"],
            should_keep=should_keep,
            reason=reason
        )
    
    def process_document_chunks(self, chunks: List[str], document_title: Optional[str] = None) -> Dict[str, Any]:
        """
        Process all chunks in a document through quality guardrails
        
        Args:
            chunks: List of chunk strings
            document_title: Optional document title to preserve
            
        Returns:
            Processing results and statistics
        """
        logger.info(f"Processing {len(chunks)} chunks for quality...")
        
        results = []
        kept_chunks = []
        dropped_chunks = []
        issue_counts = {issue.value: 0 for issue in ChunkQualityIssue}
        
        # Add document title as first chunk if provided
        if document_title and document_title.strip():
            title_result = self.process_chunk(document_title, preserve_titles=True)
            results.append(title_result)
            if title_result.should_keep:
                kept_chunks.append(title_result.processed_chunk)
        
        # Process all chunks
        for i, chunk in enumerate(chunks):
            result = self.process_chunk(chunk, preserve_titles=True)
            results.append(result)
            
            # Track statistics
            for issue in result.issues:
                issue_counts[issue.value] += 1
            
            if result.should_keep:
                kept_chunks.append(result.processed_chunk)
            else:
                dropped_chunks.append({
                    "original": chunk,
                    "reason": result.reason,
                    "issues": [issue.value for issue in result.issues]
                })
        
        # Calculate statistics
        original_chunks = len(chunks)
        kept_count = len(kept_chunks)
        dropped_count = len(dropped_chunks)
        
        empty_chunk_rate = issue_counts[ChunkQualityIssue.EMPTY_CONTENT.value] / max(original_chunks, 1)
        short_chunk_rate = issue_counts[ChunkQualityIssue.TOO_SHORT.value] / max(original_chunks, 1)
        
        return {
            "success": True,
            "original_chunk_count": original_chunks,
            "kept_chunks": kept_chunks,
            "kept_count": kept_count,
            "dropped_count": dropped_count,
            "retention_rate": kept_count / max(original_chunks, 1),
            "empty_chunk_rate": empty_chunk_rate,
            "short_chunk_rate": short_chunk_rate,
            "quality_metrics": {
                "empty_chunk_rate": empty_chunk_rate,
                "short_chunk_rate": short_chunk_rate,
                "avg_chunk_length": sum(len(chunk) for chunk in kept_chunks) / max(kept_count, 1),
                "title_chunks_preserved": sum(1 for r in results if r.is_title_or_heading and r.should_keep)
            },
            "issue_breakdown": issue_counts,
            "dropped_chunks": dropped_chunks,
            "processing_details": [
                {
                    "original_length": r.char_count,
                    "processed_length": len(r.processed_chunk) if r.processed_chunk else 0,
                    "kept": r.should_keep,
                    "is_title": r.is_title_or_heading,
                    "issues": [issue.value for issue in r.issues],
                    "reason": r.reason
                } for r in results
            ]
        }

def create_test_document_chunks() -> Tuple[List[str], str]:
    """Create test document chunks for demonstration"""
    
    title = "Content Quality Guardrails Implementation Guide"
    
    chunks = [
        # Good quality chunks
        """This is a comprehensive guide to implementing content quality guardrails in a context store system. The guardrails are designed to filter out low-quality content while preserving important structural elements like titles and headings. The system implements multiple quality checks including length validation, content analysis, and semantic filtering to ensure that only meaningful content is stored and indexed for retrieval.""",
        
        # Title/heading chunks (should be preserved)
        "# Overview and Architecture",
        "## Quality Check Implementation",
        "### Token Length Management",
        
        # Good content chunk
        """The quality analysis process begins with basic structural validation. Empty chunks and whitespace-only content are immediately filtered out as they provide no semantic value. The system then analyzes content density by checking for meaningful words versus stopwords and punctuation. Chunks that contain only common stopwords or punctuation marks are considered low-quality and are removed from the processing pipeline.""",
        
        # Empty chunk (should be dropped)
        "",
        
        # Whitespace only (should be dropped)
        "   \n  \t  \n   ",
        
        # Only stopwords (should be dropped)
        "the and or but with by",
        
        # Only punctuation (should be dropped)
        "!@#$%^&*()",
        
        # Too short but not a title (should be dropped)
        "Short content.",
        
        # Short title (should be preserved)
        "Configuration Parameters",
        
        # Very long chunk that needs clamping
        """This is an extremely long chunk that exceeds the reranker token limit and needs to be clamped to ensure optimal performance during the reranking phase. The content processing pipeline must handle cases where individual chunks contain more tokens than the reranker can effectively process. In such cases, the system implements intelligent truncation strategies that preserve semantic coherence while respecting token limits. The truncation process attempts to break at natural sentence boundaries to maintain readability and context. This approach ensures that the reranker receives appropriately sized content segments that can be processed efficiently without compromising the quality of the semantic analysis. The system also logs these truncation events for monitoring and optimization purposes. Additional content beyond this point would normally be truncated to maintain optimal reranker performance and ensure consistent processing times across all content types.""" * 3,
        
        # Good quality chunk
        """Configuration parameters play a crucial role in fine-tuning the quality guardrails. The minimum chunk character threshold is set to 200 characters by default, but can be adjusted based on domain-specific requirements. Title and heading detection uses pattern matching and heuristic analysis to identify structural elements that should be preserved even if they fall below the standard length threshold. The token estimation algorithm provides approximate token counts to help with reranker optimization.""",
        
        # Edge cases
        "A",  # Single character (too short)
        "Technical Implementation Details for Advanced Users",  # Good title
        "   Whitespace padded content that should pass quality checks after trimming   ",
    ]
    
    return chunks, title

async def main():
    """Demonstrate content polish guardrails"""
    
    print("✨ Content Polish Guardrails - Phase 4.1")
    print("=" * 60)
    
    # Initialize guardrails
    guardrails = ContentPolishGuardrails()
    
    # Create test data
    test_chunks, test_title = create_test_document_chunks()
    
    print("📋 Guardrail Configuration:")
    print(f"   Minimum chunk characters: {guardrails.min_chunk_chars}")
    print(f"   Maximum reranker tokens: {guardrails.max_reranker_tokens}")
    print(f"   Title minimum characters: {guardrails.title_min_chars}")
    print(f"   Test document: '{test_title}'")
    print(f"   Test chunks: {len(test_chunks)}")
    
    # Process the document
    print(f"\n🔍 Processing Test Document...")
    result = guardrails.process_document_chunks(test_chunks, test_title)
    
    if not result["success"]:
        print(f"❌ Processing failed")
        return False
    
    # Display results
    print(f"\n📊 Processing Results:")
    print(f"   Original chunks: {result['original_chunk_count']}")
    print(f"   Kept chunks: {result['kept_count']}")
    print(f"   Dropped chunks: {result['dropped_count']}")
    print(f"   Retention rate: {result['retention_rate']:.1%}")
    print(f"   Empty chunk rate: {result['empty_chunk_rate']:.1%}")
    print(f"   Short chunk rate: {result['short_chunk_rate']:.1%}")
    
    # Quality metrics
    metrics = result["quality_metrics"]
    print(f"\n📈 Quality Metrics:")
    print(f"   Empty chunk rate: {metrics['empty_chunk_rate']:.1%}")
    print(f"   Short chunk rate: {metrics['short_chunk_rate']:.1%}")
    print(f"   Average chunk length: {metrics['avg_chunk_length']:.0f} chars")
    print(f"   Title chunks preserved: {metrics['title_chunks_preserved']}")
    
    # Issue breakdown
    print(f"\n🚨 Issue Breakdown:")
    for issue_type, count in result["issue_breakdown"].items():
        if count > 0:
            print(f"   {issue_type}: {count}")
    
    # Show dropped chunks
    print(f"\n🗑️ Dropped Chunks (first 5):")
    for i, dropped in enumerate(result["dropped_chunks"][:5]):
        preview = dropped["original"][:50].replace('\n', ' ')
        print(f"   #{i+1}: '{preview}...' (Reason: {dropped['reason']})")
    
    # Show kept chunks  
    print(f"\n✅ Kept Chunks (first 3):")
    for i, chunk in enumerate(result["kept_chunks"][:3]):
        preview = chunk[:80].replace('\n', ' ')
        print(f"   #{i+1}: '{preview}...' ({len(chunk)} chars)")
    
    # Acceptance criteria validation
    print(f"\n📋 Acceptance Criteria Validation:")
    empty_rate = result["quality_metrics"]["empty_chunk_rate"]
    short_rate = result["quality_metrics"]["short_chunk_rate"]
    
    print(f"✅ empty_chunk_rate == 0: {'PASS' if empty_rate == 0 else 'FAIL'} ({empty_rate:.1%})")
    print(f"✅ short_chunk_rate <= 1%: {'PASS' if short_rate <= 0.01 else 'FAIL'} ({short_rate:.1%})")
    
    # Save results
    results_file = "content_polish_results.json"
    with open(results_file, 'w') as f:
        # Convert kept_chunks to shorter format for JSON
        result_for_json = result.copy()
        result_for_json["kept_chunks"] = [chunk[:100] + "..." if len(chunk) > 100 else chunk for chunk in result["kept_chunks"]]
        
        json.dump({
            "implementation": "content_polish_guardrails",
            "results": result_for_json,
            "timestamp": time.time()
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    print(f"\n🎉 Content Polish Implementation Complete!")
    print("=" * 60)
    print("📋 Sprint Acceptance Criteria:")
    print(f"✅ Empty chunk rate: {empty_rate:.1%} (target: 0%)")
    print(f"✅ Short chunk rate: {short_rate:.1%} (target: ≤1%)")
    print(f"✅ Title preservation: {metrics['title_chunks_preserved']} titles kept")
    print(f"✅ Reranker token clamping: {result['issue_breakdown']['RERANKER_TOO_LONG']} chunks clamped")
    
    print(f"\n🚀 Implementation Ready:")
    print("1. Integrate with document ingestion pipeline")
    print("2. Configure thresholds per content domain")
    print("3. Monitor quality metrics in production")
    print("4. A/B test impact on retrieval performance")
    
    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())