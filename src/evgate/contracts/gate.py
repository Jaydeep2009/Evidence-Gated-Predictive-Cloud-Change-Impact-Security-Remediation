"""Evidence gate models: decision logic and reason codes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .vocab import Decision


class ReasonCode(str):
    """Reason codes explaining gate decisions."""

    # Reasons for SAFE
    POSITIVE_DEPENDENCY_SUPPORTED = "POSITIVE_DEPENDENCY_SUPPORTED"
    ABSENCE_WELL_SUPPORTED = "ABSENCE_WELL_SUPPORTED"

    # Reasons for RISKY
    # (POSITIVE_DEPENDENCY_SUPPORTED also applies)
    SECURITY_DEGRADES = "SECURITY_DEGRADES"

    # Reasons for INSUFFICIENT_EVIDENCE
    LOW_SUFFICIENCY = "LOW_SUFFICIENCY"
    ABSENCE_NOT_INFORMATIVE = "ABSENCE_NOT_INFORMATIVE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    NO_RUNTIME_EVIDENCE = "NO_RUNTIME_EVIDENCE"
    UNSUPPORTED_CHANGE = "UNSUPPORTED_CHANGE"


class EvidenceRequest(BaseModel):
    """A request for additional evidence to improve decision confidence."""

    action: Literal[
        "run_workload",
        "exercise_endpoint",
        "provide_source",
        "refresh_snapshot",
        "resolve_conflict",
    ]
    target: str
    why: str


class GateDecision(BaseModel):
    """Evidence gate decision with reasoning."""

    decision: Decision
    reasons: list[str] = Field(default_factory=list)  # ReasonCode values
    thresholds_used: dict[str, float] = Field(default_factory=dict)
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list)
