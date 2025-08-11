"""
Advanced Evaluation Scenarios for Phase 4.2

Implements specialized evaluation scenarios including:
- Chunk drift testing (±100 token shift evaluation)
- Paraphrase hardness evaluation with adversarial variants
- Narrative retrieval with multi-chunk context assembly
- Edge case testing and robustness evaluation
- Cross-domain evaluation and transfer testing
"""

import asyncio
import logging
import time
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import statistics

from .datasets import DatasetManager, QueryData, DocumentData, EvaluationDataset
from .evaluator import Evaluator, EvaluationConfig
from .metrics import EvaluationMetrics, AdvancedMetrics

logger = logging.getLogger(__name__)


@dataclass
class ChunkVariant:
    """Document chunk with boundary variations."""
    
    original_id: str
    variant_id: str
    original_content: str
    variant_content: str
    
    # Shift information
    token_shift: int  # Positive = shift right, negative = shift left
    overlap_preserved: bool
    boundary_type: str  # "word", "sentence", "paragraph"
    
    # Quality metrics
    content_similarity: float
    semantic_preservation: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParaphraseVariant:
    """Paraphrased query variant with difficulty scoring."""
    
    original_query: str
    paraphrased_query: str
    paraphrase_type: str  # "synonym", "tense", "voice", "structure"
    
    # Difficulty metrics
    difficulty_score: float  # 0-1, higher = more difficult
    semantic_similarity: float
    lexical_overlap: float
    syntactic_complexity: float
    
    # Performance impact
    performance_drop: Optional[float] = None  # Difference in retrieval quality
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NarrativeQuery:
    """Multi-chunk narrative query requiring context assembly."""
    
    query_id: str
    query_text: str
    narrative_id: str
    
    # Expected chunks
    expected_chunks: List[str]  # Document IDs that should be retrieved
    min_chunks_required: int
    temporal_order_important: bool
    
    # Context requirements
    requires_causal_links: bool
    requires_temporal_sequence: bool
    requires_thematic_coherence: bool
    
    # Metadata
    narrative_domain: str  # "story", "process", "explanation", "timeline"
    complexity_level: str  # "simple", "medium", "complex"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdvancedScenarioResult:
    """Results from advanced scenario testing."""
    
    scenario_name: str
    timestamp: str
    
    # Test configuration
    test_count: int
    success_count: int
    failure_count: int
    
    # Performance metrics
    avg_performance_score: float
    performance_std_dev: float
    robustness_score: float  # Overall robustness metric
    
    # Detailed results
    individual_results: List[Dict[str, Any]]
    
    # Analysis
    failure_modes: Dict[str, int]  # Failure type -> count
    edge_cases_found: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ParaphraseGenerator:
    """Generates adversarial paraphrase variants."""
    
    def __init__(self):
        self.synonym_map = self._build_synonym_map()
        self.paraphrase_templates = self._build_paraphrase_templates()
    
    def _build_synonym_map(self) -> Dict[str, List[str]]:
        """Build simple synonym mappings."""
        return {
            'find': ['locate', 'discover', 'identify', 'search for'],
            'show': ['display', 'present', 'demonstrate', 'exhibit'],
            'get': ['obtain', 'acquire', 'retrieve', 'fetch'],
            'how': ['what method', 'what way', 'by what means'],
            'what': ['which', 'what kind of'],
            'where': ['in what location', 'at what place'],
            'when': ['at what time', 'during which period'],
            'good': ['effective', 'excellent', 'superior', 'optimal'],
            'bad': ['poor', 'inferior', 'suboptimal', 'ineffective'],
            'fast': ['quick', 'rapid', 'speedy', 'swift'],
            'slow': ['sluggish', 'gradual', 'delayed']
        }
    
    def _build_paraphrase_templates(self) -> Dict[str, List[Tuple[str, str]]]:
        """Build paraphrase transformation templates."""
        return {
            'voice': [
                (r'(.+) can (.+)', r'\2 can be done by \1'),
                (r'I need (.+)', r'\1 is needed'),
                (r'(.+) shows (.+)', r'\2 is shown by \1'),
            ],
            'tense': [
                (r'(.+) will (.+)', r'\1 is going to \2'),
                (r'(.+) has (.+)', r'\1 had \2'),
                (r'(.+) is (.+)', r'\1 was \2'),
            ],
            'structure': [
                (r'How to (.+)', r'What is the method for \1'),
                (r'What is (.+)', r'Can you explain \1'),
                (r'Where can I find (.+)', r'What is the location of \1'),
            ]
        }
    
    def generate_synonym_paraphrase(self, query: str) -> ParaphraseVariant:
        """Generate paraphrase using synonym substitution."""
        
        words = query.split()
        paraphrased_words = []
        changes_made = 0
        
        for word in words:
            word_lower = word.lower().strip('.,!?')
            if word_lower in self.synonym_map and random.random() < 0.3:  # 30% chance to substitute
                synonym = random.choice(self.synonym_map[word_lower])
                paraphrased_words.append(synonym)
                changes_made += 1
            else:
                paraphrased_words.append(word)
        
        paraphrased_query = ' '.join(paraphrased_words)
        
        # Calculate metrics
        original_words = set(query.lower().split())
        paraphrased_words_set = set(paraphrased_query.lower().split())
        lexical_overlap = len(original_words.intersection(paraphrased_words_set)) / len(original_words.union(paraphrased_words_set))
        
        return ParaphraseVariant(
            original_query=query,
            paraphrased_query=paraphrased_query,
            paraphrase_type="synonym",
            difficulty_score=min(1.0, changes_made / len(words)),
            semantic_similarity=0.9 - (changes_made / len(words)) * 0.2,
            lexical_overlap=lexical_overlap,
            syntactic_complexity=1.0
        )
    
    def generate_voice_paraphrase(self, query: str) -> Optional[ParaphraseVariant]:
        """Generate paraphrase using voice transformation."""
        
        for pattern, replacement in self.paraphrase_templates['voice']:
            if re.search(pattern, query, re.IGNORECASE):
                paraphrased = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
                
                if paraphrased != query:
                    return ParaphraseVariant(
                        original_query=query,
                        paraphrased_query=paraphrased,
                        paraphrase_type="voice",
                        difficulty_score=0.7,
                        semantic_similarity=0.85,
                        lexical_overlap=0.6,
                        syntactic_complexity=0.8
                    )
        
        return None
    
    def generate_structure_paraphrase(self, query: str) -> Optional[ParaphraseVariant]:
        """Generate paraphrase using structural transformation."""
        
        for pattern, replacement in self.paraphrase_templates['structure']:
            if re.search(pattern, query, re.IGNORECASE):
                paraphrased = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
                
                if paraphrased != query:
                    return ParaphraseVariant(
                        original_query=query,
                        paraphrased_query=paraphrased,
                        paraphrase_type="structure",
                        difficulty_score=0.8,
                        semantic_similarity=0.8,
                        lexical_overlap=0.5,
                        syntactic_complexity=0.9
                    )
        
        return None
    
    def generate_all_paraphrases(self, query: str) -> List[ParaphraseVariant]:
        """Generate all types of paraphrases for a query."""
        
        paraphrases = []
        
        # Synonym paraphrase
        synonym_variant = self.generate_synonym_paraphrase(query)
        paraphrases.append(synonym_variant)
        
        # Voice paraphrase
        voice_variant = self.generate_voice_paraphrase(query)
        if voice_variant:
            paraphrases.append(voice_variant)
        
        # Structure paraphrase
        structure_variant = self.generate_structure_paraphrase(query)
        if structure_variant:
            paraphrases.append(structure_variant)
        
        return paraphrases


class ChunkDriftTester:
    """Tests robustness to chunk boundary variations."""
    
    def __init__(self):
        self.token_shifts = [-100, -50, -25, 25, 50, 100]  # Token shift amounts
    
    def generate_chunk_variants(self, document: DocumentData) -> List[ChunkVariant]:
        """Generate chunk variants with different boundary shifts."""
        
        variants = []
        tokens = document.content.split()
        
        if len(tokens) < 200:  # Skip very short documents
            return variants
        
        for shift in self.token_shifts:
            variant = self._create_shifted_variant(document, tokens, shift)
            if variant:
                variants.append(variant)
        
        return variants
    
    def _create_shifted_variant(self, document: DocumentData, tokens: List[str], shift: int) -> Optional[ChunkVariant]:
        """Create single shifted variant."""
        
        total_tokens = len(tokens)
        
        # Calculate new boundaries
        if shift > 0:  # Shift right (start later)
            start_idx = min(shift, total_tokens // 4)  # Don't shift too much
            end_idx = min(total_tokens, total_tokens - shift // 2)
        else:  # Shift left (start earlier)
            start_idx = max(0, abs(shift) // 2)
            end_idx = min(total_tokens, total_tokens + abs(shift))
        
        if start_idx >= end_idx or end_idx - start_idx < 50:  # Ensure minimum chunk size
            return None
        
        # Extract variant content
        variant_tokens = tokens[start_idx:end_idx]
        variant_content = ' '.join(variant_tokens)
        
        # Calculate overlap preservation
        original_tokens_set = set(tokens)
        variant_tokens_set = set(variant_tokens)
        overlap_ratio = len(original_tokens_set.intersection(variant_tokens_set)) / len(original_tokens_set)
        
        # Calculate content similarity
        content_similarity = len(variant_tokens) / len(tokens)
        
        return ChunkVariant(
            original_id=document.id,
            variant_id=f"{document.id}_shift_{shift}",
            original_content=document.content,
            variant_content=variant_content,
            token_shift=shift,
            overlap_preserved=overlap_ratio > 0.7,
            boundary_type="word",
            content_similarity=content_similarity,
            semantic_preservation=0.9 if overlap_ratio > 0.8 else 0.7
        )


class NarrativeQueryGenerator:
    """Generates multi-chunk narrative queries."""
    
    def __init__(self):
        self.narrative_templates = self._build_narrative_templates()
    
    def _build_narrative_templates(self) -> Dict[str, Dict[str, Any]]:
        """Build narrative query templates."""
        return {
            'process_explanation': {
                'template': "How does {process} work from start to finish?",
                'min_chunks': 3,
                'temporal_order': True,
                'causal_links': True,
                'domains': ['technology', 'science', 'business']
            },
            'story_sequence': {
                'template': "What happened in the story of {subject}?",
                'min_chunks': 4,
                'temporal_order': True,
                'causal_links': False,
                'domains': ['history', 'literature', 'biography']
            },
            'cause_effect_chain': {
                'template': "What are the causes and effects of {phenomenon}?",
                'min_chunks': 3,
                'temporal_order': False,
                'causal_links': True,
                'domains': ['science', 'economics', 'health']
            },
            'comparative_analysis': {
                'template': "Compare {subject_a} and {subject_b} across different aspects",
                'min_chunks': 4,
                'temporal_order': False,
                'causal_links': False,
                'domains': ['technology', 'business', 'science']
            }
        }
    
    def generate_narrative_queries(self, dataset: EvaluationDataset, count: int = 10) -> List[NarrativeQuery]:
        """Generate narrative queries from dataset."""
        
        narrative_queries = []
        
        # Group documents by potential narrative themes
        thematic_groups = self._group_documents_by_theme(dataset.documents)
        
        for i in range(count):
            template_name = random.choice(list(self.narrative_templates.keys()))
            template_info = self.narrative_templates[template_name]
            
            # Select appropriate document group
            suitable_groups = [group for group in thematic_groups.values() 
                             if len(group) >= template_info['min_chunks']]
            
            if not suitable_groups:
                continue
            
            selected_group = random.choice(suitable_groups)
            narrative_id = f"narrative_{i}"
            
            # Generate query text
            if template_name == 'process_explanation':
                process_name = self._extract_process_name(selected_group[0].content)
                query_text = template_info['template'].format(process=process_name)
            elif template_name == 'story_sequence':
                subject = self._extract_subject_name(selected_group[0].content)
                query_text = template_info['template'].format(subject=subject)
            elif template_name == 'cause_effect_chain':
                phenomenon = self._extract_phenomenon_name(selected_group[0].content)
                query_text = template_info['template'].format(phenomenon=phenomenon)
            else:  # comparative_analysis
                subjects = self._extract_comparative_subjects(selected_group[:2])
                query_text = template_info['template'].format(
                    subject_a=subjects[0], subject_b=subjects[1]
                )
            
            narrative_query = NarrativeQuery(
                query_id=f"narrative_query_{i}",
                query_text=query_text,
                narrative_id=narrative_id,
                expected_chunks=[doc.id for doc in selected_group[:template_info['min_chunks']]],
                min_chunks_required=template_info['min_chunks'],
                temporal_order_important=template_info['temporal_order'],
                requires_causal_links=template_info['causal_links'],
                requires_temporal_sequence=template_info['temporal_order'],
                requires_thematic_coherence=True,
                narrative_domain=template_name,
                complexity_level="medium"
            )
            
            narrative_queries.append(narrative_query)
        
        return narrative_queries
    
    def _group_documents_by_theme(self, documents: List[DocumentData]) -> Dict[str, List[DocumentData]]:
        """Group documents by thematic similarity."""
        
        # Simple thematic grouping based on content keywords
        themes = {
            'technology': ['software', 'computer', 'algorithm', 'system', 'network'],
            'science': ['research', 'study', 'experiment', 'analysis', 'theory'],
            'business': ['company', 'market', 'customer', 'product', 'strategy'],
            'health': ['medical', 'treatment', 'patient', 'health', 'disease']
        }
        
        thematic_groups = {theme: [] for theme in themes}
        
        for document in documents:
            content_words = set(document.content.lower().split())
            
            for theme, keywords in themes.items():
                keyword_matches = sum(1 for kw in keywords if kw in content_words)
                if keyword_matches >= 2:  # At least 2 keyword matches
                    thematic_groups[theme].append(document)
                    break
            else:
                # Default group
                if 'general' not in thematic_groups:
                    thematic_groups['general'] = []
                thematic_groups['general'].append(document)
        
        return thematic_groups
    
    def _extract_process_name(self, content: str) -> str:
        """Extract process name from content."""
        # Simple extraction - would be more sophisticated in real implementation
        words = content.split()[:20]  # First 20 words
        
        process_indicators = ['process', 'method', 'procedure', 'approach', 'technique']
        for i, word in enumerate(words):
            if word.lower() in process_indicators and i > 0:
                return ' '.join(words[max(0, i-2):i])
        
        return "the process"
    
    def _extract_subject_name(self, content: str) -> str:
        """Extract subject name from content."""
        words = content.split()[:10]
        return ' '.join(words[:3])  # First 3 words as subject
    
    def _extract_phenomenon_name(self, content: str) -> str:
        """Extract phenomenon name from content."""
        return "the phenomenon"  # Simplified
    
    def _extract_comparative_subjects(self, documents: List[DocumentData]) -> List[str]:
        """Extract subjects for comparison from documents."""
        subjects = []
        for doc in documents:
            words = doc.title.split()[:2] if doc.title else doc.content.split()[:2]
            subjects.append(' '.join(words))
        
        return subjects[:2]


class AdvancedScenarioRunner:
    """Runs advanced evaluation scenarios."""
    
    def __init__(
        self,
        evaluator: Evaluator,
        dataset_manager: DatasetManager,
        results_dir: str = "./advanced_scenarios"
    ):
        """Initialize advanced scenario runner."""
        
        self.evaluator = evaluator
        self.dataset_manager = dataset_manager
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize specialized components
        self.paraphrase_generator = ParaphraseGenerator()
        self.chunk_drift_tester = ChunkDriftTester()
        self.narrative_generator = NarrativeQueryGenerator()
        
        self.logger = logging.getLogger(__name__)
    
    async def run_chunk_drift_evaluation(
        self,
        dataset_name: str = "clean_medium",
        scenario_name: str = "chunk_drift_robustness"
    ) -> AdvancedScenarioResult:
        """Run chunk drift robustness evaluation."""
        
        self.logger.info(f"🧩 Starting chunk drift evaluation: {scenario_name}")
        
        # Load dataset
        dataset = self.dataset_manager.load_dataset(dataset_name, "clean")
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        # Generate chunk variants for subset of documents
        test_documents = dataset.documents[:20]  # Test subset for efficiency
        all_variants = []
        
        for document in test_documents:
            variants = self.chunk_drift_tester.generate_chunk_variants(document)
            all_variants.extend(variants)
        
        self.logger.info(f"Generated {len(all_variants)} chunk variants for testing")
        
        # Create test datasets with variants
        individual_results = []
        performance_scores = []
        
        for variant in all_variants[:10]:  # Test subset
            # Create modified dataset
            modified_docs = [doc if doc.id != variant.original_id else 
                           DocumentData(
                               id=variant.variant_id,
                               content=variant.variant_content,
                               title=f"Variant of {doc.title}" if doc.title else None,
                               metadata={'is_variant': True, 'original_id': variant.original_id}
                           )
                           for doc in dataset.documents]
            
            # Run evaluation
            config = EvaluationConfig(
                name=f"chunk_drift_{variant.variant_id}",
                description=f"Chunk drift test with {variant.token_shift} token shift",
                output_dir=str(self.results_dir / "chunk_drift"),
                max_queries=20
            )
            
            result = await self.evaluator.run_evaluation(
                config=config,
                dataset={
                    "queries": [asdict(q) for q in dataset.queries[:20]],
                    "documents": [asdict(d) for d in modified_docs]
                }
            )
            
            # Calculate performance impact
            p_at_1 = result.metrics.get('p_at_1', 0.0)
            performance_scores.append(p_at_1)
            
            individual_results.append({
                'variant_id': variant.variant_id,
                'token_shift': variant.token_shift,
                'p_at_1': p_at_1,
                'content_similarity': variant.content_similarity,
                'semantic_preservation': variant.semantic_preservation
            })
        
        # Analyze results
        avg_performance = statistics.mean(performance_scores) if performance_scores else 0.0
        std_dev = statistics.stdev(performance_scores) if len(performance_scores) > 1 else 0.0
        robustness_score = 1.0 - (std_dev / max(avg_performance, 0.001))  # Higher = more robust
        
        # Identify failure modes
        failure_modes = {}
        for result in individual_results:
            if result['p_at_1'] < avg_performance * 0.9:  # 10% performance drop
                shift = result['token_shift']
                if shift > 0:
                    failure_modes['positive_shift'] = failure_modes.get('positive_shift', 0) + 1
                else:
                    failure_modes['negative_shift'] = failure_modes.get('negative_shift', 0) + 1
        
        return AdvancedScenarioResult(
            scenario_name=scenario_name,
            timestamp=datetime.now().isoformat(),
            test_count=len(all_variants),
            success_count=len([r for r in individual_results if r['p_at_1'] >= avg_performance * 0.9]),
            failure_count=len([r for r in individual_results if r['p_at_1'] < avg_performance * 0.9]),
            avg_performance_score=avg_performance,
            performance_std_dev=std_dev,
            robustness_score=robustness_score,
            individual_results=individual_results,
            failure_modes=failure_modes,
            edge_cases_found=[f"Token shift {r['token_shift']}" for r in individual_results 
                             if r['p_at_1'] < avg_performance * 0.8],
            recommendations=self._generate_chunk_drift_recommendations(individual_results)
        )
    
    async def run_paraphrase_hardness_evaluation(
        self,
        dataset_name: str = "clean_medium",
        scenario_name: str = "paraphrase_hardness"
    ) -> AdvancedScenarioResult:
        """Run paraphrase hardness evaluation."""
        
        self.logger.info(f"🔄 Starting paraphrase hardness evaluation: {scenario_name}")
        
        # Load dataset
        dataset = self.dataset_manager.load_dataset(dataset_name, "clean")
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        # Generate paraphrases for subset of queries
        test_queries = dataset.queries[:15]  # Test subset
        all_paraphrases = []
        
        for query in test_queries:
            paraphrases = self.paraphrase_generator.generate_all_paraphrases(query.query)
            for paraphrase in paraphrases:
                paraphrase.original_query = query.query
            all_paraphrases.extend(paraphrases)
        
        self.logger.info(f"Generated {len(all_paraphrases)} paraphrases for testing")
        
        # Test each paraphrase
        individual_results = []
        performance_scores = []
        
        # First, get baseline performance with original queries
        config_baseline = EvaluationConfig(
            name="baseline_original",
            description="Baseline with original queries",
            output_dir=str(self.results_dir / "paraphrase"),
            max_queries=len(test_queries)
        )
        
        baseline_result = await self.evaluator.run_evaluation(
            config=config_baseline,
            dataset={
                "queries": [asdict(q) for q in test_queries],
                "documents": [asdict(d) for d in dataset.documents]
            }
        )
        baseline_p_at_1 = baseline_result.metrics.get('p_at_1', 0.0)
        
        # Test paraphrases
        for paraphrase in all_paraphrases[:10]:  # Test subset
            # Create paraphrased query dataset
            paraphrased_queries = []
            for query in test_queries:
                if query.query == paraphrase.original_query:
                    modified_query = QueryData(
                        id=query.id,
                        query=paraphrase.paraphrased_query,
                        relevant=query.relevant,
                        relevance_scores=query.relevance_scores,
                        metadata={**query.metadata, 'is_paraphrase': True}
                    )
                    paraphrased_queries.append(modified_query)
                else:
                    paraphrased_queries.append(query)
            
            # Run evaluation
            config = EvaluationConfig(
                name=f"paraphrase_{paraphrase.paraphrase_type}",
                description=f"Paraphrase test: {paraphrase.paraphrase_type}",
                output_dir=str(self.results_dir / "paraphrase"),
                max_queries=len(paraphrased_queries)
            )
            
            result = await self.evaluator.run_evaluation(
                config=config,
                dataset={
                    "queries": [asdict(q) for q in paraphrased_queries],
                    "documents": [asdict(d) for d in dataset.documents]
                }
            )
            
            # Calculate performance impact
            p_at_1 = result.metrics.get('p_at_1', 0.0)
            performance_drop = baseline_p_at_1 - p_at_1
            paraphrase.performance_drop = performance_drop
            
            performance_scores.append(p_at_1)
            
            individual_results.append({
                'paraphrase_type': paraphrase.paraphrase_type,
                'difficulty_score': paraphrase.difficulty_score,
                'p_at_1': p_at_1,
                'performance_drop': performance_drop,
                'semantic_similarity': paraphrase.semantic_similarity,
                'lexical_overlap': paraphrase.lexical_overlap
            })
        
        # Calculate para@1_hard metric
        para_at_1_hard = AdvancedMetrics.para_at_1_hard(
            original_query="test",  # Placeholder
            paraphrased_queries=[p.paraphrased_query for p in all_paraphrases[:5]],
            ground_truth=["doc1", "doc2"],  # Placeholder
            retrieval_func=lambda q: ["doc1", "doc2", "doc3"],  # Placeholder
            similarity_threshold=0.8
        )
        
        # Analyze results
        avg_performance = statistics.mean(performance_scores) if performance_scores else 0.0
        std_dev = statistics.stdev(performance_scores) if len(performance_scores) > 1 else 0.0
        robustness_score = 1.0 - (std_dev / max(avg_performance, 0.001))
        
        # Identify failure modes
        failure_modes = {}
        for result in individual_results:
            if result['performance_drop'] > 0.1:  # 10% performance drop
                para_type = result['paraphrase_type']
                failure_modes[para_type] = failure_modes.get(para_type, 0) + 1
        
        return AdvancedScenarioResult(
            scenario_name=scenario_name,
            timestamp=datetime.now().isoformat(),
            test_count=len(all_paraphrases),
            success_count=len([r for r in individual_results if r['performance_drop'] <= 0.05]),
            failure_count=len([r for r in individual_results if r['performance_drop'] > 0.1]),
            avg_performance_score=avg_performance,
            performance_std_dev=std_dev,
            robustness_score=robustness_score,
            individual_results=individual_results,
            failure_modes=failure_modes,
            edge_cases_found=[f"High difficulty {r['paraphrase_type']}" for r in individual_results 
                             if r['difficulty_score'] > 0.8 and r['performance_drop'] > 0.15],
            recommendations=self._generate_paraphrase_recommendations(individual_results)
        )
    
    async def run_narrative_retrieval_evaluation(
        self,
        dataset_name: str = "clean_medium",
        scenario_name: str = "narrative_retrieval"
    ) -> AdvancedScenarioResult:
        """Run narrative/lineage retrieval evaluation."""
        
        self.logger.info(f"📖 Starting narrative retrieval evaluation: {scenario_name}")
        
        # Load dataset
        dataset = self.dataset_manager.load_dataset(dataset_name, "clean")
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        # Generate narrative queries
        narrative_queries = self.narrative_generator.generate_narrative_queries(dataset, count=10)
        
        self.logger.info(f"Generated {len(narrative_queries)} narrative queries")
        
        # Test each narrative query
        individual_results = []
        performance_scores = []
        
        for narrative_query in narrative_queries:
            # Run evaluation with this narrative query
            eval_queries = [QueryData(
                id=narrative_query.query_id,
                query=narrative_query.query_text,
                relevant=narrative_query.expected_chunks,
                metadata={'is_narrative': True, 'narrative_domain': narrative_query.narrative_domain}
            )]
            
            config = EvaluationConfig(
                name=f"narrative_{narrative_query.narrative_domain}",
                description=f"Narrative query: {narrative_query.narrative_domain}",
                output_dir=str(self.results_dir / "narrative"),
                max_queries=1,
                test_narrative_coherence=True
            )
            
            result = await self.evaluator.run_evaluation(
                config=config,
                dataset={
                    "queries": [asdict(q) for q in eval_queries],
                    "documents": [asdict(d) for d in dataset.documents]
                }
            )
            
            # Calculate narrative coherence
            retrieved_docs = result.query_results.get(narrative_query.query_id, {}).get('retrieved', [])
            
            # Simulate retrieved chunks with metadata
            retrieved_chunks = []
            for doc_id in retrieved_docs[:narrative_query.min_chunks_required]:
                retrieved_chunks.append({
                    'document_id': doc_id,
                    'narrative_id': narrative_query.narrative_id,
                    'timestamp': time.time(),
                    'retrieval_rank': len(retrieved_chunks)
                })
            
            coherence_result = AdvancedMetrics.narrative_coherence_score(
                query=narrative_query.query_text,
                retrieved_chunks=retrieved_chunks,
                expected_narrative_id=narrative_query.narrative_id
            )
            
            coherence_score = coherence_result['narrative_coherence']
            performance_scores.append(coherence_score)
            
            individual_results.append({
                'query_id': narrative_query.query_id,
                'narrative_domain': narrative_query.narrative_domain,
                'min_chunks_required': narrative_query.min_chunks_required,
                'chunks_retrieved': len(retrieved_chunks),
                'coherence_score': coherence_score,
                'correct_narrative_id': coherence_result['correct_narrative_id'],
                'chunk_coverage': coherence_result['chunk_coverage']
            })
        
        # Analyze results
        avg_performance = statistics.mean(performance_scores) if performance_scores else 0.0
        std_dev = statistics.stdev(performance_scores) if len(performance_scores) > 1 else 0.0
        robustness_score = avg_performance  # For narrative, coherence is robustness
        
        # Identify failure modes
        failure_modes = {}
        for result in individual_results:
            if result['coherence_score'] < 0.5:
                domain = result['narrative_domain']
                failure_modes[domain] = failure_modes.get(domain, 0) + 1
        
        return AdvancedScenarioResult(
            scenario_name=scenario_name,
            timestamp=datetime.now().isoformat(),
            test_count=len(narrative_queries),
            success_count=len([r for r in individual_results if r['coherence_score'] >= 0.7]),
            failure_count=len([r for r in individual_results if r['coherence_score'] < 0.5]),
            avg_performance_score=avg_performance,
            performance_std_dev=std_dev,
            robustness_score=robustness_score,
            individual_results=individual_results,
            failure_modes=failure_modes,
            edge_cases_found=[f"Low coherence {r['narrative_domain']}" for r in individual_results 
                             if r['coherence_score'] < 0.3],
            recommendations=self._generate_narrative_recommendations(individual_results)
        )
    
    def _generate_chunk_drift_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on chunk drift results."""
        
        recommendations = []
        
        # Check for shift direction bias
        positive_shift_issues = len([r for r in results if r['token_shift'] > 0 and r['p_at_1'] < 0.7])
        negative_shift_issues = len([r for r in results if r['token_shift'] < 0 and r['p_at_1'] < 0.7])
        
        if positive_shift_issues > negative_shift_issues * 1.5:
            recommendations.append("Right-shifted chunks perform poorly - consider left-padding or overlap adjustment")
        elif negative_shift_issues > positive_shift_issues * 1.5:
            recommendations.append("Left-shifted chunks perform poorly - consider right-padding or anchor words")
        
        # Check for large shift vulnerability
        large_shift_issues = len([r for r in results if abs(r['token_shift']) > 75 and r['p_at_1'] < 0.6])
        if large_shift_issues > len(results) * 0.3:
            recommendations.append("System vulnerable to large boundary shifts - implement adaptive chunking")
        
        # Check semantic preservation correlation
        low_preservation_issues = len([r for r in results if r['semantic_preservation'] < 0.8 and r['p_at_1'] < 0.6])
        if low_preservation_issues > 0:
            recommendations.append("Low semantic preservation correlates with poor performance - improve boundary detection")
        
        return recommendations
    
    def _generate_paraphrase_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on paraphrase results."""
        
        recommendations = []
        
        # Check which paraphrase types cause most issues
        type_performance = {}
        for result in results:
            para_type = result['paraphrase_type']
            if para_type not in type_performance:
                type_performance[para_type] = []
            type_performance[para_type].append(result['performance_drop'])
        
        for para_type, drops in type_performance.items():
            avg_drop = statistics.mean(drops)
            if avg_drop > 0.1:
                recommendations.append(f"High vulnerability to {para_type} paraphrases - consider augmented training")
        
        # Check difficulty correlation
        high_difficulty_issues = len([r for r in results if r['difficulty_score'] > 0.8 and r['performance_drop'] > 0.15])
        if high_difficulty_issues > 0:
            recommendations.append("Difficulty score predicts performance drops - implement query complexity analysis")
        
        return recommendations
    
    def _generate_narrative_recommendations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on narrative results."""
        
        recommendations = []
        
        # Check domain-specific performance
        domain_performance = {}
        for result in results:
            domain = result['narrative_domain']
            if domain not in domain_performance:
                domain_performance[domain] = []
            domain_performance[domain].append(result['coherence_score'])
        
        for domain, scores in domain_performance.items():
            avg_score = statistics.mean(scores)
            if avg_score < 0.6:
                recommendations.append(f"Poor performance on {domain} narratives - consider domain-specific training")
        
        # Check chunk coverage issues
        low_coverage_issues = len([r for r in results if r['chunk_coverage'] < 0.5])
        if low_coverage_issues > len(results) * 0.3:
            recommendations.append("Low chunk coverage - improve multi-document retrieval strategy")
        
        return recommendations
    
    async def save_scenario_results(self, result: AdvancedScenarioResult):
        """Save advanced scenario results."""
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"advanced_scenario_{result.scenario_name}_{timestamp_str}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        self.logger.info(f"Advanced scenario results saved: {filepath}")


# Convenience functions for running advanced scenarios

async def run_all_advanced_scenarios(dataset_name: str = "clean_medium") -> Dict[str, AdvancedScenarioResult]:
    """Run all advanced evaluation scenarios."""
    
    from .evaluator import Evaluator
    from .datasets import DatasetManager
    
    evaluator = Evaluator()
    dataset_manager = DatasetManager()
    runner = AdvancedScenarioRunner(evaluator, dataset_manager)
    
    results = {}
    
    # Run all scenarios
    results['chunk_drift'] = await runner.run_chunk_drift_evaluation(dataset_name)
    results['paraphrase_hardness'] = await runner.run_paraphrase_hardness_evaluation(dataset_name)
    results['narrative_retrieval'] = await runner.run_narrative_retrieval_evaluation(dataset_name)
    
    return results