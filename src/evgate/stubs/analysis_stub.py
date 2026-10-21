"""Stub for analysis pipeline (Part 3's responsibility).

Returns canned AnalysisResult for change_M2.json until the real pipeline is ready.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from evgate.contracts import (
    AnalysisResult,
    ChangeSpec,
    ComponentImpact,
    Decision,
    EvidenceBundle,
    GateDecision,
    Prediction,
)


def analyze_stub(
    change: ChangeSpec,
    bundle: EvidenceBundle,
    *,
    evidence_config: str = "D",
    gate_enabled: bool = True,
    config_path: Path | str | None = None,
    **kwargs: Any,
) -> AnalysisResult:
    """Stub that returns canned AnalysisResult for change_M2.

    This allows Part 4 to develop the runner and evaluation code before
    Part 3's real prediction/gate/graph implementations are ready.

    Args:
        change: ChangeSpec (checked to ensure it's change_M2)
        bundle: EvidenceBundle (any)
        evidence_config: Evidence configuration (A/B/C/D/D_NOGATE)
        gate_enabled: Whether evidence gate is enabled
        config_path: Path to analysis config (ignored by stub)
        **kwargs: Additional arguments (ignored by stub)

    Returns:
        Canned AnalysisResult predicting M2 as RISKY with high confidence
    """
    # Canned prediction for M2 scenario
    prediction = Prediction(
        security_impact="improves",
        security_delta=-0.5,  # improves isolation
        operational_risk=0.95,
        operational_label="high",
        affected_components=[
            ComponentImpact(
                component="component:poc-app/backend",
                impact="unavailable",
                mechanism="readiness_coupled",
                probability=0.95,
                evidence_ids=["E-app-002", "E-app-001", "E-runtime-001"],
            ),
            ComponentImpact(
                component="component:poc-app/database",
                impact="degraded",
                mechanism="direct_path_blocked",
                probability=0.90,
                evidence_ids=["E-infra-002", "E-app-001"],
            ),
            ComponentImpact(
                component="component:poc-app/frontend",
                impact="unavailable",
                mechanism="upstream_cascade",
                probability=0.85,
                evidence_ids=["E-infra-003"],
            ),
        ],
        belief=0.93,  # high belief that backend depends on database
        sufficiency=0.88,  # good evidence from all three types
        confidence=0.87,  # confidence in the RISKY decision
        supporting_evidence_ids=[
            "E-infra-002",
            "E-app-001",
            "E-app-002",
            "E-runtime-001",
        ],
        contradicting_evidence_ids=[],
        rationale=[
            "Evidence E-app-001: Backend DEPENDS_ON database (psycopg2.connect at main.py:41)",
            "Evidence E-app-002: Backend readiness probe READINESS_COUPLED to database",
            "Evidence E-runtime-001: Runtime observation confirms backend CONNECTS_TO database",
            "Change blocks backend→database:5432 (currently allowed → denied)",
            "Readiness coupling: backend /health probe exercises database connection",
            "Cascade: frontend depends on backend service availability",
        ],
    )

    gate = GateDecision(
        decision=Decision.RISKY if gate_enabled else Decision.SAFE,
        reasons=(
            ["POSITIVE_DEPENDENCY_SUPPORTED"]
            if gate_enabled
            else ["FORCED_DECISION_MODE"]
        ),
        thresholds_used={
            "tau_pos": 0.5,
            "tau_risk": 0.5,
            "tau_suff_pos": 0.6,
            "min_endpoint_coverage": 0.5,
        },
        evidence_requests=[],
    )

    return AnalysisResult(
        schema_version="1.0",
        change_id=change.change_id,
        evidence_config=evidence_config,
        gate_enabled=gate_enabled,
        prediction=prediction,
        gate=gate,
        graph_ref=None,
        remediation=None,
        versions={
            "code_sha": "stub",
            "schema_version": "1.0",
            "timestamp": datetime.now().isoformat(),
        },
    )
