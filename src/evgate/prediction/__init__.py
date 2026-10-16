"""Prediction module for evidence-gated system.

This module implements the belief, sufficiency, confidence calculations,
operational propagation, and security impact analysis per §8.2 and §8.3.
"""

from __future__ import annotations

from .belief import (
    aggregate_evidence_noisy_or,
    compute_absence_informativeness,
    compute_belief,
    compute_belief_from_graph_edge,
    compute_change_sufficiency,
    compute_confidence,
    compute_path_sufficiency,
)
from .operational import (
    ComponentImpact,
    ImpactMechanism,
    OperationalStatus,
    apply_risk_threshold,
    compute_operational_risk,
)
from .propagate import (
    check_readiness_coupling,
    get_belief_for_effect,
    get_direct_impacts,
    propagate_cascades,
    propagate_operational_impact,
    tightens_access,
)
from .security import (
    SecurityImpact,
    compute_exposure_delta,
    compute_path_exposure,
    compute_permission_delta,
    compute_security_impact,
    get_permission_weight,
    is_sensitive_component,
)

__all__ = [
    # Belief/sufficiency
    "aggregate_evidence_noisy_or",
    "compute_absence_informativeness",
    "compute_belief",
    "compute_belief_from_graph_edge",
    "compute_change_sufficiency",
    "compute_confidence",
    "compute_path_sufficiency",
    # Operational
    "ComponentImpact",
    "ImpactMechanism",
    "OperationalStatus",
    "apply_risk_threshold",
    "compute_operational_risk",
    # Propagation
    "check_readiness_coupling",
    "get_belief_for_effect",
    "get_direct_impacts",
    "propagate_cascades",
    "propagate_operational_impact",
    "tightens_access",
    # Security
    "SecurityImpact",
    "compute_exposure_delta",
    "compute_path_exposure",
    "compute_permission_delta",
    "compute_security_impact",
    "get_permission_weight",
    "is_sensitive_component",
]
