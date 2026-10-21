"""Evaluation framework: metrics, statistics, baselines, perturbation (Part 4)."""

from .baselines import BaselineComparator
from .metrics import MetricsCalculator
from .orchestrator import EvaluationOrchestrator
from .perturb import EvidencePerturber
from .stats import StatisticalAnalyzer

__all__ = [
    "MetricsCalculator",
    "StatisticalAnalyzer",
    "BaselineComparator",
    "EvidencePerturber",
    "EvaluationOrchestrator",
]
