"""Evaluation framework: metrics, statistics, baselines, perturbation (Part 4)."""

from .metrics import MetricsCalculator
from .stats import StatisticalAnalyzer
from .baselines import BaselineComparator
from .perturb import EvidencePerturber
from .orchestrator import EvaluationOrchestrator

__all__ = [
    "MetricsCalculator",
    "StatisticalAnalyzer",
    "BaselineComparator",
    "EvidencePerturber",
    "EvaluationOrchestrator",
]
