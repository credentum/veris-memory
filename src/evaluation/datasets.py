"""
Dataset Management System for Phase 4.2 Evaluation

Handles loading, versioning, and management of evaluation datasets including:
- Clean evaluation sets with ground truth
- Noisy variant generation (dupes, near-dupes, long docs, weak labels)
- Dataset versioning and snapshots
- Synthetic corpus generation for scale testing
"""

import json
import os
import hashlib
import random
import uuid
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class QueryData:
    """Single evaluation query with ground truth."""
    
    id: str
    query: str
    relevant: List[str]  # Document IDs
    relevance_scores: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DocumentData:
    """Document in evaluation corpus."""
    
    id: str
    content: str
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class EvaluationDataset:
    """Complete evaluation dataset."""
    
    name: str
    version: str
    description: str
    queries: List[QueryData]
    documents: List[DocumentData]
    metadata: Dict[str, Any]
    created_at: str
    checksum: Optional[str] = None
    
    def __post_init__(self):
        if self.checksum is None:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate dataset checksum for integrity verification."""
        content = json.dumps(asdict(self), sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()


class DatasetManager:
    """Manages evaluation datasets with versioning and variant generation."""
    
    def __init__(self, data_dir: str = "./eval_data"):
        """
        Initialize dataset manager.
        
        Args:
            data_dir: Directory for storing evaluation datasets
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Dataset storage directories
        self.clean_dir = self.data_dir / "clean"
        self.noisy_dir = self.data_dir / "noisy" 
        self.synthetic_dir = self.data_dir / "synthetic"
        self.snapshots_dir = self.data_dir / "snapshots"
        
        for dir_path in [self.clean_dir, self.noisy_dir, self.synthetic_dir, self.snapshots_dir]:
            dir_path.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    def create_clean_dataset(
        self,
        name: str,
        queries: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        description: str = "",
        version: str = "1.0"
    ) -> EvaluationDataset:
        """
        Create a clean evaluation dataset.
        
        Args:
            name: Dataset name
            queries: List of query dictionaries
            documents: List of document dictionaries  
            description: Dataset description
            version: Dataset version
            
        Returns:
            Created evaluation dataset
        """
        # Convert to dataclass objects
        query_objects = []
        for q in queries:
            query_objects.append(QueryData(
                id=q.get('id', str(uuid.uuid4())),
                query=q['query'],
                relevant=q.get('relevant', []),
                relevance_scores=q.get('relevance_scores'),
                metadata=q.get('metadata', {})
            ))
        
        document_objects = []
        for d in documents:
            document_objects.append(DocumentData(
                id=d.get('id', str(uuid.uuid4())),
                content=d['content'],
                title=d.get('title'),
                metadata=d.get('metadata', {})
            ))
        
        # Create dataset
        dataset = EvaluationDataset(
            name=name,
            version=version,
            description=description,
            queries=query_objects,
            documents=document_objects,
            metadata={
                'query_count': len(query_objects),
                'document_count': len(document_objects),
                'avg_query_length': sum(len(q.query.split()) for q in query_objects) / len(query_objects),
                'avg_doc_length': sum(len(d.content.split()) for d in document_objects) / len(document_objects)
            },
            created_at=datetime.now().isoformat()
        )
        
        # Save dataset
        self._save_dataset(dataset, self.clean_dir)
        
        self.logger.info(f"Created clean dataset '{name}' v{version} with {len(queries)} queries")
        return dataset
    
    def create_noisy_variants(
        self,
        clean_dataset: EvaluationDataset,
        noise_types: List[str] = None
    ) -> Dict[str, EvaluationDataset]:
        """
        Create noisy variants of a clean dataset.
        
        Args:
            clean_dataset: Base clean dataset
            noise_types: Types of noise to add ['dupes', 'near_dupes', 'long_docs', 'weak_labels']
            
        Returns:
            Dictionary mapping noise type to noisy dataset
        """
        if noise_types is None:
            noise_types = ['dupes', 'near_dupes', 'long_docs', 'weak_labels']
        
        noisy_datasets = {}
        
        for noise_type in noise_types:
            self.logger.info(f"Creating {noise_type} variant of {clean_dataset.name}")
            
            if noise_type == 'dupes':
                noisy_dataset = self._add_duplicates(clean_dataset)
            elif noise_type == 'near_dupes':
                noisy_dataset = self._add_near_duplicates(clean_dataset)
            elif noise_type == 'long_docs':
                noisy_dataset = self._add_long_documents(clean_dataset)
            elif noise_type == 'weak_labels':
                noisy_dataset = self._add_weak_labels(clean_dataset)
            else:
                self.logger.warning(f"Unknown noise type: {noise_type}")
                continue
            
            # Save noisy dataset
            self._save_dataset(noisy_dataset, self.noisy_dir)
            noisy_datasets[noise_type] = noisy_dataset
        
        return noisy_datasets
    
    def _add_duplicates(self, dataset: EvaluationDataset) -> EvaluationDataset:
        """Add exact duplicates to document corpus."""
        documents = dataset.documents.copy()
        
        # Add 10% duplicates
        num_dupes = max(1, len(documents) // 10)
        
        for _ in range(num_dupes):
            original_doc = random.choice(documents)
            duplicate_doc = DocumentData(
                id=f"{original_doc.id}_dup_{uuid.uuid4().hex[:8]}",
                content=original_doc.content,
                title=f"{original_doc.title} (Duplicate)" if original_doc.title else None,
                metadata={**original_doc.metadata, 'is_duplicate': True, 'original_id': original_doc.id}
            )
            documents.append(duplicate_doc)
        
        return EvaluationDataset(
            name=f"{dataset.name}_dupes",
            version=dataset.version,
            description=f"{dataset.description} - With duplicates",
            queries=dataset.queries,
            documents=documents,
            metadata={**dataset.metadata, 'noise_type': 'duplicates'},
            created_at=datetime.now().isoformat()
        )
    
    def _add_near_duplicates(self, dataset: EvaluationDataset) -> EvaluationDataset:
        """Add near-duplicates with minor variations."""
        documents = dataset.documents.copy()
        
        # Add 5% near-duplicates
        num_near_dupes = max(1, len(documents) // 20)
        
        for _ in range(num_near_dupes):
            original_doc = random.choice(documents)
            
            # Create variations (simple word substitutions/additions)
            varied_content = self._create_content_variation(original_doc.content)
            
            near_dup_doc = DocumentData(
                id=f"{original_doc.id}_neardup_{uuid.uuid4().hex[:8]}",
                content=varied_content,
                title=f"{original_doc.title} (Variation)" if original_doc.title else None,
                metadata={**original_doc.metadata, 'is_near_duplicate': True, 'original_id': original_doc.id}
            )
            documents.append(near_dup_doc)
        
        return EvaluationDataset(
            name=f"{dataset.name}_near_dupes",
            version=dataset.version,
            description=f"{dataset.description} - With near-duplicates",
            queries=dataset.queries,
            documents=documents,
            metadata={**dataset.metadata, 'noise_type': 'near_duplicates'},
            created_at=datetime.now().isoformat()
        )
    
    def _add_long_documents(self, dataset: EvaluationDataset) -> EvaluationDataset:
        """Add very long documents to test performance."""
        documents = dataset.documents.copy()
        
        # Add 5% long documents (5000+ words)
        num_long_docs = max(1, len(documents) // 20)
        
        for _ in range(num_long_docs):
            original_doc = random.choice(documents)
            
            # Create long document by repeating and varying content
            long_content = self._create_long_document(original_doc.content)
            
            long_doc = DocumentData(
                id=f"long_{uuid.uuid4().hex[:8]}",
                content=long_content,
                title=f"Extended Document - {original_doc.title or 'Untitled'}",
                metadata={**original_doc.metadata, 'is_long_document': True, 'word_count': len(long_content.split())}
            )
            documents.append(long_doc)
        
        return EvaluationDataset(
            name=f"{dataset.name}_long_docs",
            version=dataset.version,
            description=f"{dataset.description} - With long documents",
            queries=dataset.queries,
            documents=documents,
            metadata={**dataset.metadata, 'noise_type': 'long_documents'},
            created_at=datetime.now().isoformat()
        )
    
    def _add_weak_labels(self, dataset: EvaluationDataset) -> EvaluationDataset:
        """Add queries with weak/noisy relevance labels."""
        queries = []
        
        for query in dataset.queries:
            # Randomly add/remove relevant documents for 20% of queries
            if random.random() < 0.2:
                noisy_relevant = query.relevant.copy()
                
                # Remove some correct labels
                if len(noisy_relevant) > 1 and random.random() < 0.5:
                    noisy_relevant.pop(random.randint(0, len(noisy_relevant) - 1))
                
                # Add some incorrect labels
                if random.random() < 0.3:
                    all_doc_ids = [d.id for d in dataset.documents]
                    incorrect_docs = [doc_id for doc_id in all_doc_ids if doc_id not in query.relevant]
                    if incorrect_docs:
                        noisy_relevant.append(random.choice(incorrect_docs))
                
                noisy_query = QueryData(
                    id=query.id,
                    query=query.query,
                    relevant=noisy_relevant,
                    relevance_scores=query.relevance_scores,
                    metadata={**query.metadata, 'has_weak_labels': True}
                )
                queries.append(noisy_query)
            else:
                queries.append(query)
        
        return EvaluationDataset(
            name=f"{dataset.name}_weak_labels",
            version=dataset.version,
            description=f"{dataset.description} - With weak labels",
            queries=queries,
            documents=dataset.documents,
            metadata={**dataset.metadata, 'noise_type': 'weak_labels'},
            created_at=datetime.now().isoformat()
        )
    
    def _create_content_variation(self, content: str) -> str:
        """Create content variation for near-duplicates."""
        words = content.split()
        
        # Simple variations
        variations = [
            lambda w: w.replace('the', 'a') if w == 'the' else w,
            lambda w: w + 's' if w.endswith('ion') else w,
            lambda w: w.replace('ing', 'ed') if w.endswith('ing') else w,
        ]
        
        varied_words = []
        for word in words:
            if random.random() < 0.1:  # 10% chance to vary each word
                variation = random.choice(variations)
                varied_words.append(variation(word))
            else:
                varied_words.append(word)
        
        # Add some extra words
        if random.random() < 0.3:
            extra_words = ['additionally', 'furthermore', 'moreover', 'also']
            insert_pos = random.randint(0, len(varied_words))
            varied_words.insert(insert_pos, random.choice(extra_words))
        
        return ' '.join(varied_words)
    
    def _create_long_document(self, base_content: str) -> str:
        """Create very long document from base content."""
        # Repeat base content with variations
        sections = []
        
        for i in range(10):  # Create 10 sections
            if i == 0:
                sections.append(base_content)
            else:
                # Add section headers and varied content
                section_header = f"\n\nSection {i + 1}: Extended Discussion\n"
                varied_content = self._create_content_variation(base_content)
                sections.append(section_header + varied_content)
        
        return '\n'.join(sections)
    
    def generate_synthetic_corpus(
        self,
        base_corpus_size: int,
        scale_factor: int = 10,
        topic_domains: List[str] = None
    ) -> EvaluationDataset:
        """
        Generate synthetic corpus for scale testing (1x → 10x).
        
        Args:
            base_corpus_size: Base number of documents
            scale_factor: Multiplication factor for corpus expansion
            topic_domains: List of topic domains for content generation
            
        Returns:
            Synthetic evaluation dataset
        """
        if topic_domains is None:
            topic_domains = ['technology', 'science', 'business', 'health', 'education']
        
        target_size = base_corpus_size * scale_factor
        
        self.logger.info(f"Generating synthetic corpus: {base_corpus_size} → {target_size} documents")
        
        documents = []
        queries = []
        
        # Generate documents
        for i in range(target_size):
            domain = random.choice(topic_domains)
            doc_id = f"synthetic_{domain}_{i:06d}"
            
            # Generate synthetic content
            content = self._generate_synthetic_content(domain, 100 + random.randint(50, 200))
            title = self._generate_synthetic_title(domain)
            
            documents.append(DocumentData(
                id=doc_id,
                content=content,
                title=title,
                metadata={
                    'domain': domain,
                    'is_synthetic': True,
                    'word_count': len(content.split())
                }
            ))
        
        # Generate queries (1% of document count)
        num_queries = max(10, target_size // 100)
        
        for i in range(num_queries):
            domain = random.choice(topic_domains)
            query_text = self._generate_synthetic_query(domain)
            
            # Select relevant documents (randomly from same domain)
            domain_docs = [d for d in documents if d.metadata.get('domain') == domain]
            relevant_docs = random.sample(
                domain_docs, 
                min(3, len(domain_docs))
            )
            
            queries.append(QueryData(
                id=f"synthetic_query_{i:06d}",
                query=query_text,
                relevant=[d.id for d in relevant_docs],
                metadata={'domain': domain, 'is_synthetic': True}
            ))
        
        # Create dataset
        dataset = EvaluationDataset(
            name=f"synthetic_{scale_factor}x",
            version="1.0",
            description=f"Synthetic corpus for scale testing ({scale_factor}x expansion)",
            queries=queries,
            documents=documents,
            metadata={
                'scale_factor': scale_factor,
                'base_size': base_corpus_size,
                'target_size': target_size,
                'domains': topic_domains
            },
            created_at=datetime.now().isoformat()
        )
        
        # Save dataset
        self._save_dataset(dataset, self.synthetic_dir)
        
        self.logger.info(f"Generated synthetic corpus with {len(documents)} docs and {len(queries)} queries")
        return dataset
    
    def _generate_synthetic_content(self, domain: str, word_count: int) -> str:
        """Generate synthetic document content for a domain."""
        # Domain-specific word lists
        domain_vocab = {
            'technology': [
                'algorithm', 'software', 'development', 'programming', 'database', 'system',
                'application', 'framework', 'architecture', 'deployment', 'server', 'cloud',
                'security', 'encryption', 'authentication', 'optimization', 'performance'
            ],
            'science': [
                'research', 'experiment', 'hypothesis', 'analysis', 'data', 'methodology',
                'observation', 'theory', 'discovery', 'investigation', 'evidence', 'study',
                'laboratory', 'measurement', 'validation', 'conclusion', 'scientific'
            ],
            'business': [
                'strategy', 'management', 'organization', 'leadership', 'planning', 'execution',
                'revenue', 'profit', 'market', 'customer', 'service', 'product', 'growth',
                'innovation', 'competition', 'investment', 'stakeholder'
            ],
            'health': [
                'medical', 'treatment', 'diagnosis', 'patient', 'therapy', 'prevention',
                'healthcare', 'clinical', 'medicine', 'hospital', 'wellness', 'disease',
                'symptoms', 'recovery', 'pharmaceutical', 'research', 'practice'
            ],
            'education': [
                'learning', 'teaching', 'student', 'curriculum', 'instruction', 'assessment',
                'knowledge', 'skill', 'academic', 'pedagogy', 'classroom', 'educational',
                'training', 'development', 'scholarship', 'institution', 'program'
            ]
        }
        
        vocab = domain_vocab.get(domain, ['general', 'content', 'information', 'topic'])
        
        # Generate content with domain-specific vocabulary
        words = []
        for _ in range(word_count):
            if random.random() < 0.3:  # 30% domain-specific words
                words.append(random.choice(vocab))
            else:  # General words
                words.append(random.choice([
                    'the', 'and', 'of', 'to', 'in', 'a', 'is', 'that', 'for', 'with',
                    'as', 'it', 'on', 'be', 'at', 'by', 'this', 'have', 'from', 'not',
                    'process', 'important', 'effective', 'approach', 'method', 'result',
                    'example', 'specific', 'particular', 'various', 'different', 'complex'
                ]))
        
        return ' '.join(words)
    
    def _generate_synthetic_title(self, domain: str) -> str:
        """Generate synthetic document title."""
        domain_titles = {
            'technology': ['Advanced', 'Modern', 'Innovative', 'Scalable', 'Distributed'],
            'science': ['Experimental', 'Theoretical', 'Empirical', 'Quantitative', 'Analytical'],
            'business': ['Strategic', 'Operational', 'Competitive', 'Market-driven', 'Growth-oriented'],
            'health': ['Clinical', 'Therapeutic', 'Preventive', 'Diagnostic', 'Medical'],
            'education': ['Pedagogical', 'Instructional', 'Academic', 'Curriculum-based', 'Learning-focused']
        }
        
        prefix = random.choice(domain_titles.get(domain, ['General']))
        suffix = domain.title()
        
        return f"{prefix} {suffix} Research and Applications"
    
    def _generate_synthetic_query(self, domain: str) -> str:
        """Generate synthetic query for a domain."""
        query_templates = [
            f"What are the best practices for {domain}?",
            f"How to implement {domain} solutions?",
            f"Recent advances in {domain} research",
            f"Challenges in modern {domain}",
            f"Future trends in {domain} development"
        ]
        
        return random.choice(query_templates)
    
    def freeze_dataset(self, dataset: EvaluationDataset) -> str:
        """
        Create frozen snapshot of dataset for eval integrity.
        
        Args:
            dataset: Dataset to freeze
            
        Returns:
            Snapshot ID
        """
        snapshot_id = f"{dataset.name}_v{dataset.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create snapshot with integrity metadata
        snapshot_data = {
            'snapshot_id': snapshot_id,
            'original_dataset': asdict(dataset),
            'frozen_at': datetime.now().isoformat(),
            'integrity_checksum': dataset.checksum,
            'frozen_by': 'phase_4_2_evaluator'
        }
        
        # Save snapshot
        snapshot_path = self.snapshots_dir / f"{snapshot_id}.json"
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot_data, f, indent=2)
        
        self.logger.info(f"Dataset frozen as snapshot: {snapshot_id}")
        return snapshot_id
    
    def load_dataset(self, name: str, dataset_type: str = "clean") -> Optional[EvaluationDataset]:
        """
        Load dataset by name and type.
        
        Args:
            name: Dataset name
            dataset_type: Type ('clean', 'noisy', 'synthetic')
            
        Returns:
            Loaded dataset or None if not found
        """
        type_dirs = {
            'clean': self.clean_dir,
            'noisy': self.noisy_dir,
            'synthetic': self.synthetic_dir
        }
        
        dataset_dir = type_dirs.get(dataset_type)
        if not dataset_dir:
            self.logger.error(f"Unknown dataset type: {dataset_type}")
            return None
        
        # Find dataset file
        dataset_path = dataset_dir / f"{name}.json"
        if not dataset_path.exists():
            self.logger.warning(f"Dataset not found: {dataset_path}")
            return None
        
        try:
            with open(dataset_path) as f:
                data = json.load(f)
            
            # Convert back to dataclass objects
            return self._deserialize_dataset(data)
            
        except Exception as e:
            self.logger.error(f"Error loading dataset {name}: {str(e)}")
            return None
    
    def list_datasets(self) -> Dict[str, List[str]]:
        """List all available datasets by type."""
        datasets = {'clean': [], 'noisy': [], 'synthetic': []}
        
        for dataset_type, directory in [('clean', self.clean_dir), ('noisy', self.noisy_dir), ('synthetic', self.synthetic_dir)]:
            for file_path in directory.glob("*.json"):
                datasets[dataset_type].append(file_path.stem)
        
        return datasets
    
    def _save_dataset(self, dataset: EvaluationDataset, directory: Path):
        """Save dataset to specified directory."""
        file_path = directory / f"{dataset.name}.json"
        
        with open(file_path, 'w') as f:
            json.dump(asdict(dataset), f, indent=2)
        
        self.logger.info(f"Dataset saved: {file_path}")
    
    def _deserialize_dataset(self, data: Dict[str, Any]) -> EvaluationDataset:
        """Convert JSON data back to EvaluationDataset object."""
        # Convert queries
        queries = []
        for q_data in data['queries']:
            queries.append(QueryData(**q_data))
        
        # Convert documents
        documents = []
        for d_data in data['documents']:
            documents.append(DocumentData(**d_data))
        
        # Create dataset
        return EvaluationDataset(
            name=data['name'],
            version=data['version'],
            description=data['description'],
            queries=queries,
            documents=documents,
            metadata=data['metadata'],
            created_at=data['created_at'],
            checksum=data.get('checksum')
        )