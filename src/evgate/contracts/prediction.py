"""Prediction models: impact analysis results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .vocab import NodeId


class ComponentImpact(BaseModel):
    """Predicted impact on a single component."""

    component: NodeId
    impact: Literal["unavailable", "degraded", "unaffected"]
    mechanism: Literal[
        "direct_path_blocked",
        "readiness_coupled",
        "upstream_cascade",
        "permission_removed",
        "none",
    ]
    probability: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class Prediction(BaseModel):
    """Complete prediction of change impact.

    Includes both security impact and operational risk assessment.
    """

    security_impact: Literal["improves", "neutral", "degrades", "unknown"]
    security_delta: float  # signed, see §8.3
    operational_risk: float = Field(ge=0.0, le=1.0)
    operational_label: Literal["none", "low", "high", "unknown"]
    affected_components: list[ComponentImpact] = Field(default_factory=list)
    belief: float = Field(ge=0.0, le=1.0)  # P(a required path/permission is removed)
    sufficiency: float = Field(ge=0.0, le=1.0)  # evidence sufficiency
    confidence: float = Field(ge=0.0, le=1.0)  # P(decision correct) estimate
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(
        default_factory=list
    )  # human-readable, each cites evidence ids
