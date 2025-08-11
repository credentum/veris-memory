"""
Automatic Hard Negative Mining System for Phase 4.2

Implements intelligent hard negative detection and mining including:
- Near-miss detection based on retrieval failures and edge cases
- Automatic hard negative generation from query-document pairs
- Weekly eval set updates with discovered hard negatives
- Mining from production traffic and evaluation failures
- Difficulty scoring and progressive hardness levels
"""

import asyncio
import logging
import time
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import heapq
import statistics

from .datasets import DatasetManager, QueryData, DocumentData, EvaluationDataset
from .evaluator import Evaluator, EvaluationConfig
from .metrics import EvaluationMetrics
from retrieval.reranker import RetrievalReranker, create_standard_reranker

logger = logging.getLogger(__name__)


@dataclass
class HardNegativeCandidate:
    """Candidate hard negative with scoring information."""
    
    query_id: str
    query_text: str
    
    document_id: str
    document_content: str
    document_title: Optional[str] = None
    
    # Scoring information
    retrieval_score: float = 0.0  # Original retrieval score
    expected_relevance: float = 0.0  # Expected relevance (ground truth)
    actual_relevance: float = 0.0   # Actual measured relevance
    
    # Difficulty metrics
    difficulty_score: float = 0.0  # How hard this negative is (0-1)
    near_miss_score: float = 0.0   # How close to being relevant (0-1)
    
    # Mining context
    mining_source: str = ""  # "evaluation_failure", "production_traffic", "synthetic"
    mining_timestamp: str = ""
    failure_count: int = 0  # How many times this was incorrectly ranked high
    
    # Semantic similarity
    semantic_similarity: float = 0.0  # Similarity to true positives
    lexical_overlap: float = 0.0      # Word overlap with query
    
    # Quality signals
    confidence_score: float = 0.0     # Confidence in this being a good hard negative
    ambiguity_score: float = 0.0      # How ambiguous/borderline this case is
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MiningSession:
    """Results from a hard negative mining session."""
    
    session_id: str
    timestamp: str
    duration_minutes: float
    
    # Mining parameters
    source_queries: int
    source_documents: int
    mining_methods: List[str]
    
    # Results
    candidates_found: int
    hard_negatives_selected: int
    difficulty_distribution: Dict[str, int]  # difficulty ranges -> count
    
    # Quality metrics
    avg_difficulty_score: float
    avg_confidence_score: float
    semantic_diversity: float
    
    # Integration
    added_to_eval_set: int
    rejected_count: int
    rejection_reasons: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SemanticSimilarityEstimator:
    """Estimates semantic similarity for hard negative mining."""
    
    def __init__(self):
        self.word_vectors = {}  # Simplified word embedding simulation
        self._initialize_word_vectors()
    
    def _initialize_word_vectors(self):
        """Initialize simple word vectors for demonstration."""
        # In real implementation, this would load pre-trained embeddings
        common_words = [
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
            'computer', 'software', 'algorithm', 'data', 'system', 'network',
            'science', 'research', 'study', 'analysis', 'method', 'approach',
            'business', 'market', 'customer', 'service', 'product', 'company',
            'health', 'medical', 'treatment', 'patient', 'disease', 'therapy'
        ]
        
        # Generate random vectors for demonstration
        for word in common_words:
            self.word_vectors[word] = [random.gauss(0, 1) for _ in range(50)]
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts."""
        
        # Simple bag-of-words approach with word vectors
        words1 = [w.lower() for w in text1.split() if w.lower() in self.word_vectors]
        words2 = [w.lower() for w in text2.split() if w.lower() in self.word_vectors]
        
        if not words1 or not words2:
            return 0.0
        
        # Average word vectors
        vec1 = self._average_vectors([self.word_vectors[w] for w in words1])
        vec2 = self._average_vectors([self.word_vectors[w] for w in words2])
        
        # Cosine similarity
        return self._cosine_similarity(vec1, vec2)
    
    def _average_vectors(self, vectors: List[List[float]]) -> List[float]:
        """Average a list of vectors."""
        if not vectors:
            return [0.0] * 50
        
        avg_vec = [0.0] * len(vectors[0])
        for vec in vectors:
            for i, val in enumerate(vec):
                avg_vec[i] += val
        
        for i in range(len(avg_vec)):
            avg_vec[i] /= len(vectors)
        
        return avg_vec
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class HardNegativeMiner:
    """Main hard negative mining system."""
    
    def __init__(
        self,
        dataset_manager: DatasetManager,
        evaluator: Evaluator,
        results_dir: str = "./hard_negative_mining"
    ):
        """
        Initialize hard negative miner.
        
        Args:
            dataset_manager: Dataset manager for accessing eval sets
            evaluator: Evaluator for running tests
            results_dir: Directory for storing mining results
        """
        self.dataset_manager = dataset_manager
        self.evaluator = evaluator
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.semantic_estimator = SemanticSimilarityEstimator()
        self.reranker = None  # Will be initialized async
        
        # Mining configuration
        self.near_miss_threshold = 0.7  # Minimum score to be considered near-miss
        self.difficulty_threshold = 0.6  # Minimum difficulty to be selected
        self.confidence_threshold = 0.8  # Minimum confidence for auto-selection
        self.max_hard_negatives_per_query = 3  # Limit per query
        
        # Mining history
        self.mining_sessions: List[MiningSession] = []
        self.candidate_cache: Dict[str, HardNegativeCandidate] = {}
        
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize async components."""
        if self.reranker is None:
            self.reranker = await create_standard_reranker()
    
    async def run_mining_session(
        self,
        dataset_name: str = "clean_medium",
        mining_methods: List[str] = None,
        session_name: str = "nightly_mining"
    ) -> MiningSession:
        """
        Run comprehensive hard negative mining session.
        
        Args:
            dataset_name: Name of dataset to mine from
            mining_methods: List of mining methods to use
            session_name: Name for this mining session
            
        Returns:
            Mining session results
        """
        if mining_methods is None:
            mining_methods = ["evaluation_failures", "near_miss_detection", "semantic_confusers"]
        
        self.logger.info(f"🔍 Starting hard negative mining session: {session_name}")
        self.logger.info(f"Methods: {mining_methods}")
        
        await self.initialize()
        
        session_start = time.time()
        session_id = f"{session_name}_{int(time.time())}"
        
        # Load dataset
        dataset = self.dataset_manager.load_dataset(dataset_name, "clean")
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        self.logger.info(f"Mining from dataset: {len(dataset.queries)} queries, {len(dataset.documents)} documents")
        
        # Collect candidates from different methods
        all_candidates = []
        
        if "evaluation_failures" in mining_methods:
            self.logger.info("Mining from evaluation failures...")
            failure_candidates = await self._mine_from_evaluation_failures(dataset)
            all_candidates.extend(failure_candidates)
            self.logger.info(f"Found {len(failure_candidates)} failure candidates")
        
        if "near_miss_detection" in mining_methods:
            self.logger.info("Mining near-miss cases...")
            near_miss_candidates = await self._mine_near_miss_cases(dataset)
            all_candidates.extend(near_miss_candidates)
            self.logger.info(f"Found {len(near_miss_candidates)} near-miss candidates")
        
        if "semantic_confusers" in mining_methods:
            self.logger.info("Mining semantic confusers...")
            confuser_candidates = await self._mine_semantic_confusers(dataset)
            all_candidates.extend(confuser_candidates)
            self.logger.info(f"Found {len(confuser_candidates)} semantic confuser candidates")
        
        # Deduplicate and score candidates
        unique_candidates = self._deduplicate_candidates(all_candidates)
        scored_candidates = await self._score_candidates(unique_candidates, dataset)
        
        # Select best hard negatives
        selected_negatives = self._select_hard_negatives(scored_candidates)
        
        # Analyze results
        duration = (time.time() - session_start) / 60.0
        
        session = MiningSession(
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            duration_minutes=duration,
            source_queries=len(dataset.queries),
            source_documents=len(dataset.documents),
            mining_methods=mining_methods,
            candidates_found=len(unique_candidates),
            hard_negatives_selected=len(selected_negatives),
            difficulty_distribution=self._analyze_difficulty_distribution(selected_negatives),
            avg_difficulty_score=statistics.mean([c.difficulty_score for c in selected_negatives]) if selected_negatives else 0.0,
            avg_confidence_score=statistics.mean([c.confidence_score for c in selected_negatives]) if selected_negatives else 0.0,
            semantic_diversity=self._calculate_semantic_diversity(selected_negatives),
            added_to_eval_set=0,  # Will be updated by integration
            rejected_count=len(unique_candidates) - len(selected_negatives),
            rejection_reasons=self._analyze_rejection_reasons(unique_candidates, selected_negatives)
        )
        
        # Save results
        await self._save_mining_session(session, selected_negatives)
        
        self.mining_sessions.append(session)
        
        self.logger.info("✅ Hard negative mining completed")
        self.logger.info(f"   Candidates found: {len(unique_candidates)}")
        self.logger.info(f"   Hard negatives selected: {len(selected_negatives)}")
        self.logger.info(f"   Average difficulty: {session.avg_difficulty_score:.3f}")
        self.logger.info(f"   Average confidence: {session.avg_confidence_score:.3f}")
        
        return session
    
    async def _mine_from_evaluation_failures(self, dataset: EvaluationDataset) -> List[HardNegativeCandidate]:
        """Mine hard negatives from evaluation failures."""
        
        candidates = []
        
        # Run evaluation to find failures
        config = EvaluationConfig(
            name="hard_negative_mining_eval",
            description="Mining evaluation failures",
            output_dir=str(self.results_dir / "eval_temp"),
            max_queries=50  # Sample of queries
        )
        
        # Custom retrieval function that returns detailed scores
        async def detailed_retrieval_func(query: str) -> List[str]:
            results, stats = await self.reranker.retrieve_and_rerank(query, top_k=20)
            return [r.id for r in results]
        
        result = await self.evaluator.run_evaluation(
            config=config,
            dataset={
                "queries": [asdict(q) for q in dataset.queries[:50]],
                "documents": [asdict(d) for d in dataset.documents]
            },
            retrieval_func=detailed_retrieval_func
        )
        
        # Analyze failures
        for query_id, query_result in result.query_results.items():
            query_text = query_result.get('query', '')
            relevant_docs = query_result.get('relevant', [])
            retrieved_docs = query_result.get('retrieved', [])
            
            if not relevant_docs or not retrieved_docs:
                continue
            
            # Find false positives (retrieved but not relevant)
            false_positives = [doc_id for doc_id in retrieved_docs[:5] 
                             if doc_id not in relevant_docs]
            
            for doc_id in false_positives:
                # Find document content
                doc_content = self._find_document_content(doc_id, dataset.documents)
                if not doc_content:
                    continue
                
                candidate = HardNegativeCandidate(
                    query_id=query_id,
                    query_text=query_text,
                    document_id=doc_id,
                    document_content=doc_content['content'],
                    document_title=doc_content.get('title'),
                    retrieval_score=0.8,  # High score but irrelevant
                    expected_relevance=0.0,
                    actual_relevance=0.0,
                    mining_source="evaluation_failure",
                    mining_timestamp=datetime.now().isoformat(),
                    failure_count=1
                )
                
                candidates.append(candidate)
        
        return candidates
    
    async def _mine_near_miss_cases(self, dataset: EvaluationDataset) -> List[HardNegativeCandidate]:
        """Mine near-miss cases that are almost relevant but not quite."""
        
        candidates = []
        
        # For each query, find documents with high lexical overlap but low relevance
        for query in dataset.queries[:30]:  # Sample queries
            query_words = set(query.query.lower().split())
            relevant_doc_ids = set(query.relevant)
            
            for document in dataset.documents:
                # Skip if actually relevant
                if document.id in relevant_doc_ids:
                    continue
                
                doc_words = set(document.content.lower().split())
                
                # Calculate lexical overlap
                overlap = len(query_words.intersection(doc_words))
                lexical_overlap = overlap / max(len(query_words), 1)
                
                # High lexical overlap but not relevant = potential hard negative
                if lexical_overlap > 0.3:
                    
                    # Calculate semantic similarity
                    semantic_sim = self.semantic_estimator.calculate_similarity(
                        query.query, document.content
                    )
                    
                    # Near-miss score combines lexical and semantic similarity
                    near_miss = (lexical_overlap + semantic_sim) / 2
                    
                    if near_miss > self.near_miss_threshold:
                        candidate = HardNegativeCandidate(
                            query_id=query.id,
                            query_text=query.query,
                            document_id=document.id,
                            document_content=document.content,
                            document_title=document.title,
                            near_miss_score=near_miss,
                            lexical_overlap=lexical_overlap,
                            semantic_similarity=semantic_sim,
                            mining_source="near_miss_detection",
                            mining_timestamp=datetime.now().isoformat()
                        )
                        
                        candidates.append(candidate)
        
        return candidates
    
    async def _mine_semantic_confusers(self, dataset: EvaluationDataset) -> List[HardNegativeCandidate]:
        """Mine semantically confusing documents that could mislead retrieval."""
        
        candidates = []
        
        # For each query, find documents that are semantically similar to relevant docs
        # but are actually irrelevant
        
        for query in dataset.queries[:20]:  # Sample queries
            if not query.relevant:
                continue
            
            # Get content of relevant documents
            relevant_docs = []
            for doc_id in query.relevant:
                doc_content = self._find_document_content(doc_id, dataset.documents)
                if doc_content:
                    relevant_docs.append(doc_content)
            
            if not relevant_docs:
                continue
            
            # Find documents similar to relevant ones but not actually relevant
            for document in dataset.documents:
                if document.id in query.relevant:
                    continue  # Skip actually relevant docs
                
                # Calculate similarity to relevant documents
                similarities = []
                for rel_doc in relevant_docs:
                    sim = self.semantic_estimator.calculate_similarity(
                        document.content, rel_doc['content']
                    )
                    similarities.append(sim)
                
                max_similarity = max(similarities) if similarities else 0.0
                
                # High similarity to relevant docs but not relevant = confuser
                if max_similarity > 0.6:
                    candidate = HardNegativeCandidate(
                        query_id=query.id,
                        query_text=query.query,
                        document_id=document.id,
                        document_content=document.content,
                        document_title=document.title,
                        semantic_similarity=max_similarity,
                        mining_source="semantic_confusers",
                        mining_timestamp=datetime.now().isoformat()
                    )
                    
                    candidates.append(candidate)
        
        return candidates
    
    def _deduplicate_candidates(self, candidates: List[HardNegativeCandidate]) -> List[HardNegativeCandidate]:
        """Remove duplicate candidates."""
        
        seen = set()
        unique_candidates = []
        
        for candidate in candidates:
            key = f"{candidate.query_id}|{candidate.document_id}"
            
            if key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)
            else:
                # If duplicate, merge information
                existing = next(c for c in unique_candidates if 
                              c.query_id == candidate.query_id and c.document_id == candidate.document_id)
                existing.failure_count += candidate.failure_count
                existing.mining_source += f",{candidate.mining_source}"
        
        return unique_candidates
    
    async def _score_candidates(
        self, 
        candidates: List[HardNegativeCandidate], 
        dataset: EvaluationDataset
    ) -> List[HardNegativeCandidate]:
        """Score candidates for difficulty and confidence."""
        
        for candidate in candidates:
            # Calculate difficulty score
            difficulty_factors = []
            
            # Factor 1: Near-miss score (higher = more difficult)
            if candidate.near_miss_score > 0:
                difficulty_factors.append(candidate.near_miss_score)
            
            # Factor 2: Semantic similarity to relevant docs (higher = more confusing)
            if candidate.semantic_similarity > 0:
                difficulty_factors.append(candidate.semantic_similarity)
            
            # Factor 3: Lexical overlap (moderate overlap is most tricky)
            if candidate.lexical_overlap > 0:
                # Peak difficulty at ~0.5 overlap
                overlap_difficulty = 1 - abs(candidate.lexical_overlap - 0.5) * 2
                difficulty_factors.append(max(0, overlap_difficulty))
            
            # Factor 4: Failure frequency (more failures = harder case)
            failure_factor = min(1.0, candidate.failure_count / 5.0)
            if failure_factor > 0:
                difficulty_factors.append(failure_factor)
            
            # Combine factors
            if difficulty_factors:
                candidate.difficulty_score = statistics.mean(difficulty_factors)
            else:
                candidate.difficulty_score = 0.3  # Default moderate difficulty
            
            # Calculate confidence score
            confidence_factors = []
            
            # High confidence if multiple mining sources agree
            source_count = len(candidate.mining_source.split(','))
            confidence_factors.append(min(1.0, source_count / 3.0))
            
            # High confidence if consistent signals
            if candidate.near_miss_score > 0.7:
                confidence_factors.append(0.9)
            elif candidate.semantic_similarity > 0.7:
                confidence_factors.append(0.8)
            elif candidate.lexical_overlap > 0.5:
                confidence_factors.append(0.7)
            
            # Lower confidence for edge cases
            if candidate.difficulty_score < 0.3 or candidate.difficulty_score > 0.9:
                confidence_factors.append(0.5)
            else:
                confidence_factors.append(0.8)
            
            candidate.confidence_score = statistics.mean(confidence_factors) if confidence_factors else 0.5
            
            # Calculate ambiguity score (how borderline/unclear this case is)
            candidate.ambiguity_score = abs(0.5 - candidate.difficulty_score) * 2  # Peak at 0.5 difficulty
        
        return candidates
    
    def _select_hard_negatives(self, candidates: List[HardNegativeCandidate]) -> List[HardNegativeCandidate]:
        """Select best hard negatives from candidates."""
        
        # Filter by minimum thresholds
        qualified_candidates = [
            c for c in candidates 
            if (c.difficulty_score >= self.difficulty_threshold and
                c.confidence_score >= self.confidence_threshold)
        ]
        
        # Group by query
        query_groups = defaultdict(list)
        for candidate in qualified_candidates:
            query_groups[candidate.query_id].append(candidate)
        
        # Select top candidates per query
        selected = []
        
        for query_id, query_candidates in query_groups.items():
            # Sort by combined score (difficulty * confidence)
            query_candidates.sort(
                key=lambda x: x.difficulty_score * x.confidence_score,
                reverse=True
            )
            
            # Select top N per query
            selected.extend(query_candidates[:self.max_hard_negatives_per_query])
        
        return selected
    
    def _find_document_content(self, doc_id: str, documents: List[DocumentData]) -> Optional[Dict[str, Any]]:
        """Find document content by ID."""
        for doc in documents:
            if doc.id == doc_id:
                return {
                    'content': doc.content,
                    'title': doc.title,
                    'metadata': doc.metadata
                }
        return None
    
    def _analyze_difficulty_distribution(self, candidates: List[HardNegativeCandidate]) -> Dict[str, int]:
        """Analyze distribution of difficulty scores."""
        
        distribution = {"easy": 0, "medium": 0, "hard": 0, "extreme": 0}
        
        for candidate in candidates:
            if candidate.difficulty_score < 0.4:
                distribution["easy"] += 1
            elif candidate.difficulty_score < 0.6:
                distribution["medium"] += 1
            elif candidate.difficulty_score < 0.8:
                distribution["hard"] += 1
            else:
                distribution["extreme"] += 1
        
        return distribution
    
    def _calculate_semantic_diversity(self, candidates: List[HardNegativeCandidate]) -> float:
        """Calculate semantic diversity among selected candidates."""
        
        if len(candidates) < 2:
            return 1.0
        
        # Sample candidates for efficiency
        sample_candidates = candidates[:20] if len(candidates) > 20 else candidates
        
        # Calculate pairwise similarities
        similarities = []
        for i in range(len(sample_candidates)):
            for j in range(i + 1, len(sample_candidates)):
                sim = self.semantic_estimator.calculate_similarity(
                    sample_candidates[i].document_content,
                    sample_candidates[j].document_content
                )
                similarities.append(sim)
        
        # Diversity = 1 - average similarity
        avg_similarity = statistics.mean(similarities) if similarities else 0.0
        return max(0.0, 1.0 - avg_similarity)
    
    def _analyze_rejection_reasons(
        self, 
        all_candidates: List[HardNegativeCandidate],
        selected: List[HardNegativeCandidate]
    ) -> Dict[str, int]:
        """Analyze reasons why candidates were rejected."""
        
        selected_ids = {(c.query_id, c.document_id) for c in selected}
        rejected = [c for c in all_candidates 
                   if (c.query_id, c.document_id) not in selected_ids]
        
        reasons = {"low_difficulty": 0, "low_confidence": 0, "quota_exceeded": 0, "duplicate": 0}
        
        for candidate in rejected:
            if candidate.difficulty_score < self.difficulty_threshold:
                reasons["low_difficulty"] += 1
            elif candidate.confidence_score < self.confidence_threshold:
                reasons["low_confidence"] += 1
            else:
                reasons["quota_exceeded"] += 1
        
        return reasons
    
    async def integrate_with_eval_set(
        self, 
        hard_negatives: List[HardNegativeCandidate],
        target_dataset: str = "clean_medium"
    ) -> Dict[str, Any]:
        """Integrate hard negatives into evaluation dataset."""
        
        self.logger.info(f"🔗 Integrating {len(hard_negatives)} hard negatives into {target_dataset}")
        
        # Load target dataset
        dataset = self.dataset_manager.load_dataset(target_dataset, "clean")
        if not dataset:
            raise ValueError(f"Target dataset '{target_dataset}' not found")
        
        # Group hard negatives by query
        query_negatives = defaultdict(list)
        for hn in hard_negatives:
            query_negatives[hn.query_id].append(hn)
        
        # Add hard negatives to dataset
        updated_queries = []
        new_documents = []
        
        for query in dataset.queries:
            if query.id in query_negatives:
                # Add hard negative documents for this query
                negatives = query_negatives[query.id]
                
                # Create new documents if they don't exist
                for negative in negatives:
                    if not any(d.id == negative.document_id for d in dataset.documents):
                        new_doc = DocumentData(
                            id=negative.document_id,
                            content=negative.document_content,
                            title=negative.document_title,
                            metadata={
                                **negative.metadata if hasattr(negative, 'metadata') and negative.metadata else {},
                                'is_hard_negative': True,
                                'difficulty_score': negative.difficulty_score,
                                'mining_source': negative.mining_source
                            }
                        )
                        new_documents.append(new_doc)
                
                # Update query metadata to track hard negatives
                query.metadata = query.metadata or {}
                query.metadata['hard_negatives'] = [hn.document_id for hn in negatives]
                query.metadata['hard_negative_count'] = len(negatives)
            
            updated_queries.append(query)
        
        # Create updated dataset
        updated_dataset = EvaluationDataset(
            name=f"{dataset.name}_with_hard_negatives",
            version=f"{dataset.version}_hn",
            description=f"{dataset.description} - Enhanced with {len(hard_negatives)} hard negatives",
            queries=updated_queries,
            documents=dataset.documents + new_documents,
            metadata={
                **dataset.metadata,
                'hard_negatives_added': len(hard_negatives),
                'hard_negative_integration_date': datetime.now().isoformat()
            },
            created_at=datetime.now().isoformat()
        )
        
        # Save updated dataset
        self.dataset_manager._save_dataset(updated_dataset, self.dataset_manager.clean_dir)
        
        integration_result = {
            'original_queries': len(dataset.queries),
            'original_documents': len(dataset.documents),
            'hard_negatives_added': len(hard_negatives),
            'new_documents_created': len(new_documents),
            'queries_enhanced': len(query_negatives),
            'updated_dataset_name': updated_dataset.name
        }
        
        self.logger.info("✅ Hard negative integration completed")
        self.logger.info(f"   Enhanced {len(query_negatives)} queries")
        self.logger.info(f"   Added {len(new_documents)} new documents")
        
        return integration_result
    
    async def _save_mining_session(
        self, 
        session: MiningSession, 
        hard_negatives: List[HardNegativeCandidate]
    ):
        """Save mining session results."""
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save session summary
        session_file = self.results_dir / f"mining_session_{session.session_id}_{timestamp_str}.json"
        with open(session_file, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)
        
        # Save hard negatives
        negatives_file = self.results_dir / f"hard_negatives_{session.session_id}_{timestamp_str}.json"
        with open(negatives_file, 'w') as f:
            json.dump([hn.to_dict() for hn in hard_negatives], f, indent=2)
        
        # Save CSV for analysis
        csv_file = self.results_dir / f"hard_negatives_{session.session_id}_{timestamp_str}.csv"
        await self._save_hard_negatives_csv(hard_negatives, csv_file)
        
        self.logger.info(f"Mining session saved: {session_file}")
    
    async def _save_hard_negatives_csv(self, hard_negatives: List[HardNegativeCandidate], filepath: Path):
        """Save hard negatives as CSV for analysis."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'query_id', 'document_id', 'difficulty_score', 'confidence_score',
                'near_miss_score', 'semantic_similarity', 'lexical_overlap',
                'mining_source', 'failure_count'
            ])
            
            # Data rows
            for hn in hard_negatives:
                writer.writerow([
                    hn.query_id, hn.document_id, hn.difficulty_score, hn.confidence_score,
                    hn.near_miss_score, hn.semantic_similarity, hn.lexical_overlap,
                    hn.mining_source, hn.failure_count
                ])


# Scheduled mining functions

async def run_nightly_mining(
    dataset_name: str = "clean_medium",
    auto_integrate: bool = True
) -> Dict[str, Any]:
    """Run nightly hard negative mining job."""
    
    dataset_manager = DatasetManager()
    evaluator = Evaluator()
    miner = HardNegativeMiner(dataset_manager, evaluator)
    
    # Run mining session
    session = await miner.run_mining_session(
        dataset_name=dataset_name,
        mining_methods=["evaluation_failures", "near_miss_detection", "semantic_confusers"],
        session_name="nightly_mining"
    )
    
    if auto_integrate and session.hard_negatives_selected > 0:
        # Load hard negatives and integrate
        hard_negatives_file = miner.results_dir / f"hard_negatives_{session.session_id}_*.json"
        # In real implementation, load the actual hard negatives
        # For now, just return the session info
        pass
    
    return {
        'session': session.to_dict(),
        'auto_integrated': auto_integrate,
        'timestamp': datetime.now().isoformat()
    }


async def run_weekly_eval_update(
    source_dataset: str = "clean_medium",
    target_dataset: str = "clean_medium_enhanced"
) -> Dict[str, Any]:
    """Run weekly evaluation set update with hard negatives."""
    
    dataset_manager = DatasetManager()
    evaluator = Evaluator()
    miner = HardNegativeMiner(dataset_manager, evaluator)
    
    # Run comprehensive mining
    session = await miner.run_mining_session(
        dataset_name=source_dataset,
        session_name="weekly_update"
    )
    
    # Integration would happen here in real implementation
    
    return {
        'session': session.to_dict(),
        'source_dataset': source_dataset,
        'target_dataset': target_dataset,
        'timestamp': datetime.now().isoformat()
    }