"""Frozen contracts v1.0 for evidence-gated system.

This module contains all Pydantic models that define the interfaces between Parts.
These contracts are FROZEN - any change requires a contracts-change PR approved by
all four part owners.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bundle import ComponentInfo, EvidenceBundle
from .change import (
    ChangeSpec,
    PathEffect,
    PermissionEffect,
    SecurityObjective,
    Selector,
)
from .evidence import Evidence, Provenance, RuntimeCoverage, StaticCompleteness
from .evidence import make_evidence_id
from .experiment import ExperimentRecord
from .gate import EvidenceRequest, GateDecision, ReasonCode
from .groundtruth import (
    ComponentState,
    EnvironmentFingerprint,
    GroundTruthLabel,
    GroundTruthRun,
    ProbeResult,
    ProbeSpec,
)
from .prediction import ComponentImpact, Prediction
from .remediation import (
    AnalysisResult,
    ManifestPatch,
    Minimality,
    PathSpec,
    Remediation,
    StaticValidation,
)
from .vocab import Classification, Decision, EvidenceType, NodeId, Relationship

__all__ = [
    # Version
    "schema_version",
    # Vocabulary
    "NodeId",
    "Relationship",
    "EvidenceType",
    "Classification",
    "Decision",
    # Evidence
    "Evidence",
    "make_evidence_id",
    "Provenance",
    "RuntimeCoverage",
    "StaticCompleteness",
    # Bundle
    "ComponentInfo",
    "EvidenceBundle",
    # Change
    "ChangeSpec",
    "PathEffect",
    "PermissionEffect",
    "SecurityObjective",
    "Selector",
    # Prediction
    "Prediction",
    "ComponentImpact",
    # Gate
    "GateDecision",
    "ReasonCode",
    "EvidenceRequest",
    # Remediation
    "AnalysisResult",
    "Remediation",
    "PathSpec",
    "ManifestPatch",
    "StaticValidation",
    "Minimality",
    # Ground Truth
    "GroundTruthRun",
    "GroundTruthLabel",
    "ProbeSpec",
    "ProbeResult",
    "ComponentState",
    "EnvironmentFingerprint",
    # Experiment
    "ExperimentRecord",
    # Utilities
    "export_schemas",
]

schema_version = "1.0"


def export_schemas(output_dir: str | Path = "contracts/schemas") -> None:
    """Export JSON Schemas for all contract models.

    Called by: make schemas

    Args:
        output_dir: Directory to write schema files to
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Models to export
    models: dict[str, type[Any]] = {
        "Evidence": Evidence,
        "Provenance": Provenance,
        "RuntimeCoverage": RuntimeCoverage,
        "StaticCompleteness": StaticCompleteness,
        "ComponentInfo": ComponentInfo,
        "EvidenceBundle": EvidenceBundle,
        "ChangeSpec": ChangeSpec,
        "PathEffect": PathEffect,
        "PermissionEffect": PermissionEffect,
        "SecurityObjective": SecurityObjective,
        "Prediction": Prediction,
        "ComponentImpact": ComponentImpact,
        "GateDecision": GateDecision,
        "EvidenceRequest": EvidenceRequest,
        "AnalysisResult": AnalysisResult,
        "Remediation": Remediation,
        "PathSpec": PathSpec,
        "ManifestPatch": ManifestPatch,
        "StaticValidation": StaticValidation,
        "Minimality": Minimality,
        "GroundTruthRun": GroundTruthRun,
        "GroundTruthLabel": GroundTruthLabel,
        "ProbeSpec": ProbeSpec,
        "ProbeResult": ProbeResult,
        "ComponentState": ComponentState,
        "EnvironmentFingerprint": EnvironmentFingerprint,
        "ExperimentRecord": ExperimentRecord,
    }

    for name, model in models.items():
        schema = model.model_json_schema()
        schema_file = output_path / f"{name}.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated {schema_file}")

    print(f"\nExported {len(models)} schemas to {output_path}")
