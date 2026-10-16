"""Evidence gate decision logic per §8.4.

Implements the gate algorithm that decides SAFE/RISKY/INSUFFICIENT based on:
- Evidence sufficiency
- Belief in dependencies
- Conflicts
- Security impact
- Operational risk
"""

from __future__ import annotations

import networkx as nx

from evgate.contracts import (
    ChangeSpec,
    Decision,
    EvidenceBundle,
    EvidenceRequest,
    EvidenceType,
    GateDecision,
    ReasonCode,
)
from evgate.prediction.security import SecurityImpact


def check_conflicts_on_paths(
    graph: nx.MultiDiGraph,
    change: ChangeSpec,
) -> bool:
    """Check if any newly-removed paths have conflicting evidence.

    Per §8.4: conflicts = any(edge.conflicted for edges on newly-removed paths)

    Args:
        graph: Dependency graph
        change: Change specification

    Returns:
        True if conflicts detected on affected paths
    """
    has_conflicts = False

    # Check path effects
    for effect in change.effects:
        if effect.kind == "path" and effect.before == "allowed" and effect.after == "denied":
            src = effect.src
            dst = effect.dst

            # Check if edge exists and is conflicted
            if graph.has_edge(src, dst):
                for key in graph[src][dst]:
                    edge_data = graph[src][dst][key]
                    if edge_data.get("conflicted", False):
                        has_conflicts = True
                        break

    return has_conflicts


def check_positive_evidence(
    graph: nx.MultiDiGraph,
    change: ChangeSpec,
    tau_pos: float,
) -> bool:
    """Check if any newly-removed path has high-belief positive evidence.

    Per §8.4: pos = any(b >= tau_pos for newly-removed paths)

    Args:
        graph: Dependency graph
        change: Change specification
        tau_pos: Positive belief threshold

    Returns:
        True if any removed path has belief >= tau_pos
    """
    # Check path effects that deny access
    for effect in change.effects:
        if effect.kind == "path" and effect.before == "allowed" and effect.after == "denied":
            src = effect.src
            dst = effect.dst

            # Get belief from edge
            if graph.has_edge(src, dst):
                for key in graph[src][dst]:
                    edge_data = graph[src][dst][key]

                    # Check aggregated belief (already computed in builder)
                    # For simplicity, we check if conf_by_type exists and has high confidence
                    conf_by_type = edge_data.get("conf_by_type", {})

                    # Simple check: if any type has high confidence, consider it positive
                    # (In full pipeline, this would use compute_belief with mask)
                    for conf in conf_by_type.values():
                        if conf >= tau_pos:
                            return True

    return False


def generate_evidence_requests(
    reasons: list[str],
    bundle: EvidenceBundle,
    change: ChangeSpec,
    mask: set[EvidenceType],
) -> list[EvidenceRequest]:
    """Generate evidence requests based on insufficiency reasons.

    Per §8.4 examples:
    - run_workload with profile full
    - exercise_endpoint component:METHOD /path
    - provide_source component
    - resolve_conflict evidence_ids

    Args:
        reasons: List of reason codes
        bundle: Evidence bundle
        change: Change specification
        mask: Evidence types in mask

    Returns:
        List of evidence requests
    """
    requests: list[EvidenceRequest] = []

    # If no runtime evidence when runtime in mask
    if ReasonCode.NO_RUNTIME_EVIDENCE in reasons:
        requests.append(
            EvidenceRequest(
                action="run_workload",
                target="full",
                why="Execute comprehensive workload to observe runtime behavior",
            )
        )

    # If conflicting evidence
    if ReasonCode.CONFLICTING_EVIDENCE in reasons:
        requests.append(
            EvidenceRequest(
                action="resolve_conflict",
                target="all",
                why="Investigate and resolve conflicting evidence sources",
            )
        )

    # If low sufficiency, might need more evidence
    if ReasonCode.LOW_SUFFICIENCY in reasons:
        # Check what types are missing
        if EvidenceType.APPLICATION not in mask:
            requests.append(
                EvidenceRequest(
                    action="provide_source",
                    target="application",
                    why="Provide application source code for static analysis",
                )
            )

    # If absence not informative
    if ReasonCode.ABSENCE_NOT_INFORMATIVE in reasons:
        coverage_score = (
            bundle.coverage.endpoint_coverage if bundle.coverage else 0.0
        )
        if coverage_score < 0.8:
            requests.append(
                EvidenceRequest(
                    action="run_workload",
                    target="full",
                    why="Run more comprehensive workload to improve coverage",
                )
            )

    return requests


def apply_evidence_gate(
    change: ChangeSpec,
    graph: nx.MultiDiGraph,
    bundle: EvidenceBundle,
    sufficiency: float,
    security_impact: SecurityImpact,
    operational_label: str,
    tau_pos: float,
    tau_suff_pos: float,
    tau_suff_neg: float,
    mask: set[EvidenceType],
    gate_enabled: bool = True,
) -> GateDecision:
    """Apply evidence gate to make SAFE/RISKY/INSUFFICIENT decision.

    Per §8.4 algorithm:
    1. Check if change is supported
    2. Check for conflicts
    3. Check for positive evidence (belief >= tau_pos)
       - If yes and S >= tau_suff_pos: RISKY
       - If yes and S < tau_suff_pos: INSUFFICIENT (low sufficiency)
    4. Check if security degrades and change loosens
       - If yes: RISKY
    5. Check if absence is well-supported (S >= tau_suff_neg, no conflicts)
       - If yes: SAFE
    6. Otherwise: INSUFFICIENT

    Args:
        change: Change specification
        graph: Dependency graph
        bundle: Evidence bundle
        sufficiency: Change sufficiency score
        security_impact: Security impact classification
        operational_label: Operational risk label (none/low/high)
        tau_pos: Positive belief threshold
        tau_suff_pos: Sufficiency threshold for positive evidence
        tau_suff_neg: Sufficiency threshold for absence evidence
        mask: Evidence types in mask
        gate_enabled: If False, use forced decision mode

    Returns:
        GateDecision with decision, reasons, and evidence requests
    """
    # Forced decision mode (for evaluation)
    if not gate_enabled:
        return forced_decision(security_impact, operational_label)

    reasons: list[str] = []

    # Step 1: Check if change is supported
    if not change.supported or not change.effects:
        return GateDecision(
            decision=Decision.INSUFFICIENT_EVIDENCE,
            reasons=[ReasonCode.UNSUPPORTED_CHANGE],
            thresholds_used={},
            evidence_requests=[],
        )

    # Step 2: Check for conflicts
    conflicts = check_conflicts_on_paths(graph, change)
    if conflicts:
        reasons.append(ReasonCode.CONFLICTING_EVIDENCE)

    # Step 3: Check for positive evidence
    pos = check_positive_evidence(graph, change, tau_pos)

    if pos:
        # Positive dependency found
        if sufficiency >= tau_suff_pos and not conflicts:
            # High sufficiency and no conflicts: RISKY
            return GateDecision(
                decision=Decision.RISKY,
                reasons=[ReasonCode.POSITIVE_DEPENDENCY_SUPPORTED],
                thresholds_used={
                    "sufficiency": sufficiency,
                    "tau_suff_pos": tau_suff_pos,
                },
                evidence_requests=[],
            )
        else:
            # Low sufficiency or conflicts: INSUFFICIENT
            if sufficiency < tau_suff_pos:
                reasons.append(ReasonCode.LOW_SUFFICIENCY)

            requests = generate_evidence_requests(reasons, bundle, change, mask)
            return GateDecision(
                decision=Decision.INSUFFICIENT_EVIDENCE,
                reasons=reasons,
                thresholds_used={
                    "sufficiency": sufficiency,
                    "tau_suff_pos": tau_suff_pos,
                },
                evidence_requests=requests,
            )

    # Step 4: No positive dependency found - check security impact
    if security_impact == SecurityImpact.DEGRADES and change.direction in ("loosens", "mixed"):
        return GateDecision(
            decision=Decision.RISKY,
            reasons=[ReasonCode.SECURITY_DEGRADES],
            thresholds_used={},
            evidence_requests=[],
        )

    # Step 5: Check if absence is well-supported
    if sufficiency >= tau_suff_neg and not conflicts:
        return GateDecision(
            decision=Decision.SAFE,
            reasons=[ReasonCode.ABSENCE_WELL_SUPPORTED],
            thresholds_used={
                "sufficiency": sufficiency,
                "tau_suff_neg": tau_suff_neg,
            },
            evidence_requests=[],
        )

    # Step 6: Otherwise INSUFFICIENT
    if bundle.coverage is None and EvidenceType.RUNTIME in mask:
        reasons.append(ReasonCode.NO_RUNTIME_EVIDENCE)

    if not reasons:
        reasons.append(ReasonCode.ABSENCE_NOT_INFORMATIVE)

    requests = generate_evidence_requests(reasons, bundle, change, mask)

    return GateDecision(
        decision=Decision.INSUFFICIENT_EVIDENCE,
        reasons=reasons,
        thresholds_used={
            "sufficiency": sufficiency,
            "tau_suff_neg": tau_suff_neg,
        },
        evidence_requests=requests,
    )


def forced_decision(
    security_impact: SecurityImpact,
    operational_label: str,
) -> GateDecision:
    """Make forced decision based only on impacts (gate disabled).

    Per §8.4: gate_enabled=False mode for evaluation
    RISKY iff operational_label=="high" OR security degrades
    Otherwise SAFE

    Args:
        security_impact: Security impact classification
        operational_label: Operational risk label

    Returns:
        GateDecision (RISKY or SAFE)
    """
    if operational_label == "high" or security_impact == SecurityImpact.DEGRADES:
        return GateDecision(
            decision=Decision.RISKY,
            reasons=[ReasonCode.FORCED_DECISION],
            thresholds_used={},
            evidence_requests=[],
        )
    else:
        return GateDecision(
            decision=Decision.SAFE,
            reasons=[ReasonCode.FORCED_DECISION],
            thresholds_used={},
            evidence_requests=[],
        )
