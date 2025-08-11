"""
Configuration Management for Phase 4.2 Evaluation System

Handles loading and validation of evaluation configurations from YAML files,
providing structured access to evaluation parameters, thresholds, and scenarios.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class StabilityThresholds:
    """Thresholds for determining evaluation stability."""
    
    max_p1_drift: float = 0.02
    max_ndcg_drift: float = 0.02
    max_latency_drift_pct: float = 10.0
    max_error_rate_pct: float = 0.5
    stable_cycles_required: int = 5


@dataclass
class EvalConfigData:
    """Individual evaluation configuration."""
    
    name: str
    description: str
    k_values: List[int] = field(default_factory=lambda: [1, 3, 5, 10])
    calculate_ndcg: bool = True
    calculate_mrr: bool = True
    test_paraphrase_robustness: bool = False
    test_narrative_coherence: bool = False
    test_chunk_drift: bool = False
    max_queries: Optional[int] = None
    timeout_seconds: int = 30
    expected_p1_min: Optional[float] = None
    expected_ndcg10_min: Optional[float] = None
    expected_p95_latency_max_ms: Optional[float] = None
    corpus_scale_factor: Optional[int] = None


@dataclass
class DatasetConfig:
    """Dataset configuration."""
    
    name: str
    type: str  # clean, noisy, synthetic
    description: str
    size: Optional[str] = None
    query_count: Optional[int] = None
    document_count: Optional[int] = None
    noise_type: Optional[str] = None
    base_dataset: Optional[str] = None


@dataclass
class AblationConfig:
    """Ablation study configuration."""
    
    name: str
    description: str
    configurations: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ConcurrencyConfig:
    """Concurrency testing configuration."""
    
    name: str
    description: str
    target_qps: int
    duration_minutes: int
    concurrent_users: int
    enable_rolling_redeploy: bool = False
    redeploy_interval_minutes: Optional[int] = None


class EvaluationConfigManager:
    """Manages evaluation configurations and provides structured access."""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (defaults to standard location)
        """
        if config_path is None:
            # Default config path relative to this file
            config_path = Path(__file__).parent.parent.parent / "configs" / "eval_configs.yaml"
        
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        
        self.load_config()
        
    def load_config(self):
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file not found: {self.config_path}")
                self.config_data = self._get_default_config()
                return
            
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)
            
            logger.info(f"Loaded evaluation config from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            logger.info("Using default configuration")
            self.config_data = self._get_default_config()
    
    def get_base_config(self) -> Dict[str, Any]:
        """Get base evaluation configuration."""
        return self.config_data.get("base_config", {
            "k_values": [1, 3, 5, 10],
            "timeout_seconds": 30,
            "calculate_ndcg": True,
            "calculate_mrr": True,
            "max_queries": None
        })
    
    def get_stability_thresholds(self) -> StabilityThresholds:
        """Get stability assessment thresholds."""
        thresholds_data = self.config_data.get("stability_thresholds", {})
        return StabilityThresholds(**thresholds_data)
    
    def get_evaluation_config(self, name: str) -> Optional[EvalConfigData]:
        """
        Get specific evaluation configuration by name.
        
        Args:
            name: Name of evaluation configuration
            
        Returns:
            Evaluation configuration or None if not found
        """
        evaluations = self.config_data.get("evaluations", {})
        eval_data = evaluations.get(name)
        
        if not eval_data:
            logger.warning(f"Evaluation config '{name}' not found")
            return None
        
        # Merge with base config
        base_config = self.get_base_config()
        merged_config = {**base_config, **eval_data}
        
        return EvalConfigData(**merged_config)
    
    def list_evaluation_configs(self) -> List[str]:
        """Get list of available evaluation configuration names."""
        return list(self.config_data.get("evaluations", {}).keys())
    
    def get_dataset_config(self, name: str) -> Optional[DatasetConfig]:
        """
        Get dataset configuration by name.
        
        Args:
            name: Dataset configuration name
            
        Returns:
            Dataset configuration or None if not found
        """
        datasets = self.config_data.get("datasets", {})
        dataset_data = datasets.get(name)
        
        if not dataset_data:
            logger.warning(f"Dataset config '{name}' not found")
            return None
        
        return DatasetConfig(**dataset_data)
    
    def list_dataset_configs(self) -> List[str]:
        """Get list of available dataset configurations."""
        return list(self.config_data.get("datasets", {}).keys())
    
    def get_ablation_study(self, name: str) -> Optional[AblationConfig]:
        """
        Get ablation study configuration.
        
        Args:
            name: Ablation study name
            
        Returns:
            Ablation configuration or None if not found
        """
        ablations = self.config_data.get("ablation_studies", {})
        ablation_data = ablations.get(name)
        
        if not ablation_data:
            logger.warning(f"Ablation study '{name}' not found")
            return None
        
        return AblationConfig(**ablation_data)
    
    def list_ablation_studies(self) -> List[str]:
        """Get list of available ablation studies."""
        return list(self.config_data.get("ablation_studies", {}).keys())
    
    def get_concurrency_config(self, name: str) -> Optional[ConcurrencyConfig]:
        """
        Get concurrency testing configuration.
        
        Args:
            name: Concurrency configuration name
            
        Returns:
            Concurrency configuration or None if not found
        """
        concurrency_configs = self.config_data.get("concurrency_testing", {})
        concurrency_data = concurrency_configs.get(name)
        
        if not concurrency_data:
            logger.warning(f"Concurrency config '{name}' not found")
            return None
        
        return ConcurrencyConfig(**concurrency_data)
    
    def list_concurrency_configs(self) -> List[str]:
        """Get list of available concurrency configurations."""
        return list(self.config_data.get("concurrency_testing", {}).keys())
    
    def get_scale_testing_configs(self) -> List[EvalConfigData]:
        """Get all scale testing configurations."""
        scale_configs = []
        evaluations = self.config_data.get("evaluations", {})
        
        for name, config_data in evaluations.items():
            if name.startswith("scale_") and "corpus_scale_factor" in config_data:
                base_config = self.get_base_config()
                merged_config = {**base_config, **config_data}
                scale_configs.append(EvalConfigData(**merged_config))
        
        # Sort by scale factor
        scale_configs.sort(key=lambda x: x.corpus_scale_factor or 1)
        return scale_configs
    
    def get_cold_warm_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get cold vs warm testing configurations."""
        return self.config_data.get("cold_warm_testing", {})
    
    def get_advanced_scenario_config(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """
        Get advanced evaluation scenario configuration.
        
        Args:
            scenario_name: Name of advanced scenario
            
        Returns:
            Scenario configuration or None if not found
        """
        scenarios = self.config_data.get("advanced_scenarios", {})
        return scenarios.get(scenario_name)
    
    def get_reporting_config(self) -> Dict[str, Any]:
        """Get reporting and output configuration."""
        return self.config_data.get("reporting", {
            "output_formats": ["json"],
            "include_per_query_results": True,
            "include_trace_details": True,
            "include_performance_breakdown": True
        })
    
    def get_environment_config(self, environment: str = "development") -> Dict[str, Any]:
        """
        Get environment-specific configuration overrides.
        
        Args:
            environment: Environment name (development, staging, production)
            
        Returns:
            Environment configuration
        """
        environments = self.config_data.get("environments", {})
        return environments.get(environment, {})
    
    def create_evaluation_config_from_template(
        self, 
        template_name: str, 
        overrides: Optional[Dict[str, Any]] = None
    ) -> Optional[EvalConfigData]:
        """
        Create evaluation configuration from template with optional overrides.
        
        Args:
            template_name: Name of template configuration
            overrides: Optional parameter overrides
            
        Returns:
            New evaluation configuration
        """
        template = self.get_evaluation_config(template_name)
        if not template:
            return None
        
        if overrides:
            # Apply overrides
            for key, value in overrides.items():
                if hasattr(template, key):
                    setattr(template, key, value)
        
        return template
    
    def validate_config(self) -> List[str]:
        """
        Validate loaded configuration for consistency and completeness.
        
        Returns:
            List of validation warnings/errors
        """
        issues = []
        
        # Check required sections
        required_sections = ["base_config", "evaluations", "datasets"]
        for section in required_sections:
            if section not in self.config_data:
                issues.append(f"Missing required section: {section}")
        
        # Validate evaluation configs
        evaluations = self.config_data.get("evaluations", {})
        for name, config in evaluations.items():
            if "name" not in config:
                config["name"] = name  # Set default name
            if "description" not in config:
                issues.append(f"Evaluation '{name}' missing description")
            
            # Validate k_values
            k_values = config.get("k_values", [])
            if not k_values or not all(isinstance(k, int) and k > 0 for k in k_values):
                issues.append(f"Evaluation '{name}' has invalid k_values")
        
        # Validate dataset configs
        datasets = self.config_data.get("datasets", {})
        for name, config in datasets.items():
            if "type" not in config:
                issues.append(f"Dataset '{name}' missing type")
            
            # Check for circular references in noisy datasets
            if config.get("type") == "noisy" and config.get("base_dataset"):
                base = config["base_dataset"]
                if base not in datasets:
                    issues.append(f"Dataset '{name}' references unknown base dataset '{base}'")
        
        # Validate ablation studies
        ablations = self.config_data.get("ablation_studies", {})
        for name, study in ablations.items():
            if "configurations" not in study:
                issues.append(f"Ablation study '{name}' missing configurations")
        
        return issues
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when file is not available."""
        return {
            "base_config": {
                "k_values": [1, 3, 5, 10],
                "timeout_seconds": 30,
                "calculate_ndcg": True,
                "calculate_mrr": True,
                "max_queries": None
            },
            "stability_thresholds": {
                "max_p1_drift": 0.02,
                "max_ndcg_drift": 0.02,
                "max_latency_drift_pct": 10,
                "max_error_rate_pct": 0.5,
                "stable_cycles_required": 5
            },
            "evaluations": {
                "baseline": {
                    "name": "baseline",
                    "description": "Default baseline evaluation",
                    "max_queries": 100,
                    "expected_p1_min": 0.7
                }
            },
            "datasets": {
                "default": {
                    "name": "default",
                    "type": "clean",
                    "description": "Default test dataset",
                    "query_count": 50,
                    "document_count": 500
                }
            }
        }


# Global config manager instance
_config_manager: Optional[EvaluationConfigManager] = None


def get_config_manager(config_path: Optional[Union[str, Path]] = None) -> EvaluationConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None or config_path is not None:
        _config_manager = EvaluationConfigManager(config_path)
    return _config_manager


def load_evaluation_config(name: str, config_path: Optional[Union[str, Path]] = None) -> Optional[EvalConfigData]:
    """
    Convenience function to load evaluation configuration by name.
    
    Args:
        name: Configuration name
        config_path: Optional config file path
        
    Returns:
        Evaluation configuration or None
    """
    config_manager = get_config_manager(config_path)
    return config_manager.get_evaluation_config(name)