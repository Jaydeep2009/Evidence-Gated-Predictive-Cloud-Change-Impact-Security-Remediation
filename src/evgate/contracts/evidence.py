"""Evidence models: provenance, coverage, and evidence items."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .vocab import Classification, EvidenceType, NodeId, Relationship


class Provenance(BaseModel):
    """Detailed provenance information for an evidence item."""

    source_type: Literal[
        "file", "cluster", "trace", "log", "probe", "audit", "iac_plan", "manual"
    ]
    source_path: str  # repo-relative path or logical id (never absolute)
    line_number: int | None = None
    locator: str | None = None  # JSONPath / span id / k8s ref
    content_sha256: str | None = None
    extractor: str  # e.g. "infra.networkpolicy"
    extractor_version: str = "1.0.0"
    extracted_at: datetime


class RuntimeCoverage(BaseModel):
    """What the runtime observation window actually exercised.

    Needed to interpret ABSENCE of evidence - absence of observation
    is only meaningful if the window covered the relevant workload.
    """

    window_start: datetime
    window_end: datetime
    workload_id: str
    requests_total: int
    endpoints_exercised: list[str] = Field(
        default_factory=list
    )  # "backend:GET /health"
    endpoints_known: list[str] = Field(default_factory=list)  # from app evidence
    components_observed: list[str] = Field(default_factory=list)
    spans_total: int = 0

    @property
    def endpoint_coverage(self) -> float:
        """Fraction of known endpoints that were exercised."""
        k = set(self.endpoints_known)
        if not k:
            return 1.0
        return len(k & set(self.endpoints_exercised)) / len(k)


class StaticCompleteness(BaseModel):
    """How trustworthy 'no call found in code' is for one component.

    Used to assess whether absence of application evidence is informative.
    """

    component: str
    files_analyzed: list[str] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)
    unresolved_dynamic_calls: int = 0

    @property
    def score(self) -> float:
        """Completeness score: 1.0 = fully resolved, 0.0 = unreliable."""
        if self.parse_errors or not self.files_analyzed:
            return 0.0
        return 1.0 / (1.0 + self.unresolved_dynamic_calls)


class Evidence(BaseModel):
    """A single piece of evidence about a relationship between nodes."""

    evidence_id: str  # deterministic, see make_evidence_id()
    evidence_type: EvidenceType
    source: str  # "kubernetes-networkpolicy" | "python-ast" | "jaeger-trace" | ...
    subject: NodeId
    relationship: Relationship
    object: NodeId
    polarity: Literal["supports", "refutes"] = "supports"  # claim holds / does not hold
    classification: Classification
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime  # when the fact was true / observed
    snapshot_id: str  # system state this fact belongs to, e.g. "baseline@<git-sha>"
    provenance: Provenance
    metadata: dict[str, Any] = Field(default_factory=dict)


def make_evidence_id(e: Evidence) -> str:
    """Generate a deterministic evidence ID from key fields.

    The ID is based on the claim (type, source, triple, polarity, snapshot)
    plus an optional disambiguating key from metadata. Timestamps are NOT
    included to ensure reproducibility.
    """
    key_data = [
        e.evidence_type.value,
        e.source,
        e.subject,
        e.relationship.value,
        e.object,
        e.polarity,
        e.snapshot_id,
        e.metadata.get("key", ""),
    ]
    key = json.dumps(key_data, sort_keys=True)
    hash_digest = hashlib.sha1(key.encode()).hexdigest()[:12]
    return f"E-{hash_digest}"
