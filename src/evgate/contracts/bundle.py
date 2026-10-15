"""Evidence bundles: the unit of evidence passed between Parts 2 and 3."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .evidence import Evidence, RuntimeCoverage, StaticCompleteness
from .vocab import NodeId


class ComponentInfo(BaseModel):
    """Information about a component in the system inventory."""

    node_id: NodeId
    labels: dict[str, str] = Field(default_factory=dict)
    aliases: list[str] = Field(
        default_factory=list
    )  # DNS forms, service names, trace service.name
    namespace: str
    ports: list[int] = Field(default_factory=list)
    readiness_path: str | None = None


class EvidenceBundle(BaseModel):
    """A complete bundle of evidence from a snapshot.

    This is the contract between Part 2 (evidence collection) and Part 3 (analysis).
    All evidence must be from the pre-change (baseline) phase to avoid label leakage.
    """

    schema_version: str = "1.0"
    bundle_id: str
    snapshot_id: str
    phase: Literal["pre_change"] = "pre_change"  # post-change bundles are rejected
    collected_at: datetime
    config_fingerprint: str  # sha256 of sorted manifest contents at snapshot time
    inventory: list[ComponentInfo]
    evidence: list[Evidence]
    coverage: RuntimeCoverage | None = None  # None == no runtime telemetry available
    static_completeness: list[StaticCompleteness] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def assert_no_leakage(self) -> None:
        """Verify that this bundle contains no post-change evidence.

        Decision D1: Prediction must use only pre-change (baseline) evidence.
        Post-change data is ground truth only, never input to prediction.

        Raises:
            ValueError: If any evidence appears to be from post-change phase.
        """
        # Check bundle phase
        if self.phase != "pre_change":
            raise ValueError(
                f"Bundle phase is '{self.phase}', expected 'pre_change'. "
                "Post-change evidence must not be used for prediction (D1)."
            )

        # Check evidence snapshot consistency
        for ev in self.evidence:
            if ev.snapshot_id != self.snapshot_id:
                raise ValueError(
                    f"Evidence {ev.evidence_id} has snapshot_id '{ev.snapshot_id}' "
                    f"but bundle has '{self.snapshot_id}'. Mixed snapshots not allowed."
                )

            # Check for suspicious provenance paths
            suspicious_patterns = [
                r"post[-_]?change",
                r"stage[-_]?2",
                r"impact",
                r"after[-_]?policy",
            ]
            path_lower = ev.provenance.source_path.lower()
            for pattern in suspicious_patterns:
                if re.search(pattern, path_lower):
                    raise ValueError(
                        f"Evidence {ev.evidence_id} has suspicious provenance path "
                        f"'{ev.provenance.source_path}' matching pattern '{pattern}'. "
                        "This may indicate post-change evidence (D1)."
                    )

            # Check for policy_active flag in metadata
            if ev.metadata.get("policy_active") is True:
                raise ValueError(
                    f"Evidence {ev.evidence_id} has metadata.policy_active=true. "
                    "This indicates the policy was active during observation, "
                    "which makes it post-change evidence (D1)."
                )
