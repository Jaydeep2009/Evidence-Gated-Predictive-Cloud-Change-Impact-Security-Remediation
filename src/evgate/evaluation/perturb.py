"""
P4-09: Evidence Perturbation
Systematically degrades evidence to test robustness.
"""

from typing import Dict, Any, List
from enum import Enum
import copy
import random


class PerturbationCondition(Enum):
    """Evidence perturbation conditions for evaluation."""
    EC0 = "full"           # Complete evidence (baseline)
    EC1 = "no_app"         # No application logs
    EC2 = "no_runtime"     # No runtime metrics
    EC3 = "no_infra"       # No infrastructure data
    EC4 = "partial_all"    # 50% of each type
    EC5 = "noisy"          # All evidence + 20% random noise


class EvidencePerturber:
    """
    Perturbs evidence to test analyzer robustness.
    
    Implements systematic evidence degradation conditions (EC0-EC5)
    for evaluating how well the analyzer handles incomplete/noisy data.
    """
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
    
    def apply_condition(
        self,
        evidence: Dict[str, Any],
        condition: PerturbationCondition
    ) -> Dict[str, Any]:
        """
        Apply perturbation condition to evidence.
        
        Args:
            evidence: Original complete evidence
            condition: Perturbation condition to apply
        
        Returns:
            Perturbed evidence
        """
        
        if condition == PerturbationCondition.EC0:
            return copy.deepcopy(evidence)
        
        elif condition == PerturbationCondition.EC1:
            return self._remove_app_logs(evidence)
        
        elif condition == PerturbationCondition.EC2:
            return self._remove_runtime_metrics(evidence)
        
        elif condition == PerturbationCondition.EC3:
            return self._remove_infra_data(evidence)
        
        elif condition == PerturbationCondition.EC4:
            return self._partial_all(evidence)
        
        elif condition == PerturbationCondition.EC5:
            return self._add_noise(evidence)
        
        return evidence
    
    def _remove_app_logs(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """EC1: Remove application logs."""
        perturbed = copy.deepcopy(evidence)
        perturbed["application_logs"] = []
        return perturbed
    
    def _remove_runtime_metrics(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """EC2: Remove runtime metrics."""
        perturbed = copy.deepcopy(evidence)
        perturbed["runtime_metrics"] = {}
        return perturbed
    
    def _remove_infra_data(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """EC3: Remove infrastructure data."""
        perturbed = copy.deepcopy(evidence)
        perturbed["infrastructure"] = {}
        return perturbed
    
    def _partial_all(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """EC4: Keep only 50% of each evidence type."""
        perturbed = copy.deepcopy(evidence)
        
        # Reduce application logs to 50%
        if "application_logs" in perturbed and isinstance(perturbed["application_logs"], list):
            n = len(perturbed["application_logs"])
            perturbed["application_logs"] = random.sample(perturbed["application_logs"], n // 2)
        
        # Reduce runtime metrics to 50%
        if "runtime_metrics" in perturbed and isinstance(perturbed["runtime_metrics"], dict):
            keys = list(perturbed["runtime_metrics"].keys())
            keep_keys = random.sample(keys, len(keys) // 2)
            perturbed["runtime_metrics"] = {
                k: v for k, v in perturbed["runtime_metrics"].items() if k in keep_keys
            }
        
        return perturbed
    
    def _add_noise(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """EC5: Add 20% random noise to all evidence."""
        perturbed = copy.deepcopy(evidence)
        
        # Add noise to logs
        if "application_logs" in perturbed and isinstance(perturbed["application_logs"], list):
            noise_count = max(1, len(perturbed["application_logs"]) // 5)
            for _ in range(noise_count):
                perturbed["application_logs"].append({
                    "timestamp": "2026-10-19T00:00:00Z",
                    "level": "DEBUG",
                    "message": f"NOISE_{random.randint(1000, 9999)}"
                })
        
        # Add noise to metrics
        if "runtime_metrics" in perturbed and isinstance(perturbed["runtime_metrics"], dict):
            perturbed["runtime_metrics"]["noise_metric"] = random.random()
        
        return perturbed
    
    def generate_all_conditions(
        self,
        evidence: Dict[str, Any]
    ) -> Dict[PerturbationCondition, Dict[str, Any]]:
        """
        Generate evidence under all perturbation conditions.
        
        Args:
            evidence: Original complete evidence
        
        Returns:
            Dict mapping each condition to perturbed evidence
        """
        return {
            condition: self.apply_condition(evidence, condition)
            for condition in PerturbationCondition
        }
