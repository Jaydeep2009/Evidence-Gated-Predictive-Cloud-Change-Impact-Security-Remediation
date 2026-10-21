"""Operational risk computation and impact status tracking.

Defines operational impact states, probability calculation, and risk aggregation
per §8.3 specification.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class OperationalStatus(StrEnum):
    """Operational impact status for a component."""

    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNAFFECTED = "unaffected"


class ImpactMechanism(StrEnum):
    """Mechanism by which operational impact occurred."""

    DIRECT_PATH_BLOCKED = "direct_path_blocked"
    UPSTREAM_CASCADE = "upstream_cascade"
    READINESS_COUPLED = "readiness_coupled"
    PERMISSION_DENIED = "permission_denied"


class ComponentImpact:
    """Impact state for a single component."""

    def __init__(
        self,
        component: str,
        status: OperationalStatus,
        mechanism: ImpactMechanism,
        probability: float = 1.0,
        caused_by: str | None = None,
        belief: float | None = None,
    ):
        """Create component impact record.

        Args:
            component: Component identifier
            status: Operational status (unavailable/degraded/unaffected)
            mechanism: How the impact occurred
            probability: Probability of this impact (0.0-1.0)
            caused_by: Component that caused this impact (for cascades)
            belief: Belief in the dependency that caused this impact
        """
        self.component = component
        self.status = status
        self.mechanism = mechanism
        self.probability = probability
        self.caused_by = caused_by
        self.belief = belief

    def __repr__(self) -> str:
        parts = [f"{self.component}: {self.status.value}"]
        if self.caused_by:
            parts.append(f"(caused by {self.caused_by})")
        if self.probability < 1.0:
            parts.append(f"prob={self.probability:.3f}")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "component": self.component,
            "status": self.status.value,
            "mechanism": self.mechanism.value,
            "probability": self.probability,
        }
        if self.caused_by:
            result["caused_by"] = self.caused_by
        if self.belief is not None:
            result["belief"] = self.belief
        return result


def compute_operational_risk(impacts: list[ComponentImpact]) -> tuple[float, str]:
    """Compute overall operational risk from component impacts.

    Formula per §8.3:
    operational_risk = 1 - Π(1 - prob(component))
    where prob is weighted: unavailable=1.0, degraded=0.5

    Labels:
    - "none" if risk < 0.1
    - "low" if 0.1 ≤ risk < tau_risk
    - "high" if risk ≥ tau_risk
    - "unknown" if sufficiency < 0.2 (checked by caller)

    Args:
        impacts: List of component impacts

    Returns:
        Tuple of (risk_score, label)

    Example:
        impacts = [
            ComponentImpact("backend", UNAVAILABLE, ..., prob=0.9),
            ComponentImpact("database", DEGRADED, ..., prob=0.8)
        ]
        # backend: 0.9 * 1.0 = 0.9
        # database: 0.8 * 0.5 = 0.4
        # risk = 1 - (1-0.9)(1-0.4) = 1 - 0.1*0.6 = 1 - 0.06 = 0.94
    """
    # Weight by status: unavailable=1.0, degraded=0.5, unaffected=0.0
    status_weights = {
        OperationalStatus.UNAVAILABLE: 1.0,
        OperationalStatus.DEGRADED: 0.5,
        OperationalStatus.UNAFFECTED: 0.0,
    }

    # Compute weighted probabilities
    weighted_probs = []
    for impact in impacts:
        if impact.status in (OperationalStatus.UNAVAILABLE, OperationalStatus.DEGRADED):
            weight = status_weights[impact.status]
            weighted_probs.append(impact.probability * weight)

    # Aggregate using complement product: 1 - Π(1 - p_i)
    product = 1.0
    for prob in weighted_probs:
        product *= 1.0 - prob

    risk = 1.0 - product

    # Determine label (tau_risk will be checked by caller)
    if risk < 0.1:
        label = "none"
    else:
        # Caller will upgrade to "high" if risk >= tau_risk
        label = "low"

    return risk, label


def apply_risk_threshold(risk: float, label: str, tau_risk: float) -> str:
    """Apply tau_risk threshold to label.

    Args:
        risk: Computed risk score
        label: Current label ("none", "low", or "unknown")
        tau_risk: Risk threshold from config

    Returns:
        Final label: "none", "low", "high", or "unknown"
    """
    if label == "unknown":
        return "unknown"
    if risk >= tau_risk:
        return "high"
    return label
