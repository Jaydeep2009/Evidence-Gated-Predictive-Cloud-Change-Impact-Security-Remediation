"""Remediation models: minimal safer alternatives for risky changes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .vocab import NodeId


class PathSpec(BaseModel):
    """Specification of a network path."""

    src: NodeId
    dst: NodeId
    port: int | None = None
    protocol: str = "TCP"


class ManifestPatch(BaseModel):
    """A patch to a manifest file."""

    target_ref: str  # file path or k8s ref
    format: Literal["yaml", "tofu_json"]
    content: str  # full replacement document(s)


class StaticValidation(BaseModel):
    """Static validation results for a remediation."""

    preserves_required: bool
    keeps_objective: bool
    introduces_wildcard: bool
    checked_with: Literal["semantics_engine"] = "semantics_engine"
    details: list[str] = Field(default_factory=list)


class Minimality(BaseModel):
    """Minimality metrics for a remediation."""

    allowed_pairs: int  # (src,dst,port) pairs allowed among candidates
    required_pairs: int
    excess_pairs: int  # allowed - required
    ratio: float  # allowed/required (1.0 optimal)


class Remediation(BaseModel):
    """A minimal remediation that preserves function while keeping security objective."""

    remediation_id: str
    strategy: Literal[
        "narrow_allow", "scope_down_permission", "retain_required_paths"
    ]
    patches: list[ManifestPatch] = Field(default_factory=list)
    preserves: list[PathSpec] = Field(default_factory=list)
    keeps_denied: list[PathSpec] = Field(default_factory=list)
    static_validation: StaticValidation
    minimality: Minimality
    rationale: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Complete analysis result including prediction, gate decision, and optional remediation.

    This is the primary output of the analyze() pipeline.
    """

    schema_version: str = "1.0"
    change_id: str
    evidence_config: Literal["A", "B", "C", "D", "D_NOGATE"]
    gate_enabled: bool
    prediction: Prediction  # forward reference
    gate: GateDecision  # forward reference
    graph_ref: str | None = None  # path to exported graph json
    remediation: Remediation | None = None
    versions: dict[str, str] = Field(default_factory=dict)  # code sha, config hash, etc


# Import Prediction and GateDecision to resolve forward references
from .gate import GateDecision  # noqa: E402
from .prediction import Prediction  # noqa: E402

AnalysisResult.model_rebuild()
