"""
Phase 4.2 Evaluation Infrastructure

This module provides comprehensive evaluation capabilities for the veris-memory
context store, including metrics calculation, dataset management, and 
performance testing for eval integrity and scaling validation.

Core Components:
- EvaluationMetrics: P@1, NDCG, MRR implementations
- Evaluator: Main evaluation orchestrator
- DatasetManager: Dataset loading and management
- PerformanceTester: Scale and latency testing
"""

from .metrics import EvaluationMetrics
from .evaluator import Evaluator

__version__ = "0.1.0"
__all__ = ["EvaluationMetrics", "Evaluator"]