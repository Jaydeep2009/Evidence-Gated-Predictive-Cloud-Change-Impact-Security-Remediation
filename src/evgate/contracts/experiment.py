"""Experiment record models: evaluation results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .groundtruth import GroundTruthLabel
from .remediation import AnalysisResult


class ExperimentRecord(BaseModel):
    """A single experiment record: prediction + ground truth + metrics."""

    experiment_id: str  # deterministic: sha1(scenario|config|condition|code_sha)
    scenario_id: str
    split: Literal["dev", "test"]
    evidence_config: Literal["A", "B", "C", "D", "D_NOGATE"]
    evidence_condition: Literal["EC0", "EC1", "EC2", "EC3", "EC4", "EC5"]
    gate_enabled: bool
    result: AnalysisResult
    label: GroundTruthLabel
    correct_operational: bool | None = None  # None if abstained
    abstained: bool
    set_precision: float  # for affected components
    set_recall: float  # for affected components
    notes: str = ""
