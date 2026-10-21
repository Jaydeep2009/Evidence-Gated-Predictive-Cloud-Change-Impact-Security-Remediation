"""Unit tests for evidence gate decision logic.

Tests verify §8.4 gate algorithm:
- Unsupported changes
- Positive evidence with sufficient/insufficient evidence
- Security degradation
- Absence well-supported
- Conflicts
- No runtime evidence
- Forced decision mode
"""

from datetime import datetime

import networkx as nx
import pytest

from evgate.contracts import (
    ChangeSpec,
    Decision,
    EvidenceBundle,
    EvidenceType,
    PathEffect,
    PermissionEffect,
    ReasonCode,
)
from evgate.gate import apply_evidence_gate, forced_decision
from evgate.prediction.security import SecurityImpact


def make_test_bundle() -> EvidenceBundle:
    """Create a minimal test bundle with all required fields."""
    return EvidenceBundle(
        bundle_id="test-bundle-001",
        snapshot_id="test",
        collected_at=datetime(2026, 10, 15, 12, 0, 0),
        config_fingerprint="abc123",
        inventory=[],
        evidence=[],
    )


@pytest.mark.unit
def test_unsupported_change():
    """Test that unsupported changes return INSUFFICIENT."""
    G = nx.MultiDiGraph()
    bundle = make_test_bundle()

    # Unsupported change
    change = ChangeSpec(
        change_id="UNSUPPORTED-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Unsupported",
        after_ref="/test",
        supported=False,  # Not supported
        effects=[],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.8,
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="none",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.INFRASTRUCTURE},
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert ReasonCode.UNSUPPORTED_CHANGE in decision.reasons


@pytest.mark.unit
def test_positive_dependency_high_sufficiency():
    """Test RISKY decision for positive dependency with high sufficiency.

    Scenario: High-belief dependency + high sufficiency → RISKY
    """
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")

    # Add edge with high confidence
    G.add_edge(
        "backend",
        "database",
        key=0,
        relationship="DEPENDS_ON",
        conf_by_type={"application": 0.9, "runtime": 1.0},
        conflicted=False,
    )

    bundle = make_test_bundle()

    # Change blocks backend → database
    change = ChangeSpec(
        change_id="M2",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Block backend→database",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="backend",
                dst="database",
                port=5432,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.85,  # High sufficiency
        security_impact=SecurityImpact.IMPROVES,
        operational_label="high",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.APPLICATION, EvidenceType.RUNTIME},
    )

    assert decision.decision == Decision.RISKY
    assert ReasonCode.POSITIVE_DEPENDENCY_SUPPORTED in decision.reasons


@pytest.mark.unit
def test_positive_dependency_low_sufficiency():
    """Test INSUFFICIENT for positive dependency with low sufficiency."""
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")

    # Add edge with moderate confidence
    G.add_edge(
        "backend",
        "database",
        key=0,
        relationship="DEPENDS_ON",
        conf_by_type={"infrastructure": 0.6},  # Only infrastructure
        conflicted=False,
    )

    bundle = make_test_bundle()

    change = ChangeSpec(
        change_id="TEST-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Block backend→database",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="backend",
                dst="database",
                port=5432,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.4,  # Low sufficiency
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="low",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.INFRASTRUCTURE},
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert ReasonCode.LOW_SUFFICIENCY in decision.reasons


@pytest.mark.unit
def test_conflicting_evidence():
    """Test INSUFFICIENT when conflicts detected.

    Scenario: Positive dependency + conflicts → INSUFFICIENT
    """
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")

    # Add edge with CONFLICT
    G.add_edge(
        "backend",
        "database",
        key=0,
        relationship="DEPENDS_ON",
        conf_by_type={"application": 0.9},
        conflicted=True,  # Conflicting evidence!
    )

    bundle = make_test_bundle()

    change = ChangeSpec(
        change_id="G3",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Block with conflict",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="backend",
                dst="database",
                port=5432,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.85,  # High sufficiency but conflicts
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="low",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.APPLICATION},
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert ReasonCode.CONFLICTING_EVIDENCE in decision.reasons


@pytest.mark.unit
def test_security_degrades_triggers_risky():
    """Test RISKY when security degrades, even without operational impact.

    Per §8.4: security degradation in loosening change → RISKY
    """
    G = nx.MultiDiGraph()
    bundle = make_test_bundle()

    # Loosening change (grants wildcard permission)
    change = ChangeSpec(
        change_id="WILDCARD-001",
        category="kubernetes",
        kind="k8s_rbac",
        operation="modify",
        summary="Grant wildcard",
        after_ref="/test",
        direction="loosens",
        effects=[
            PermissionEffect(
                kind="permission",
                principal="service-account",
                verb="*",
                api_group="",
                resource="*",
                before="denied",
                after="granted",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.5,
        security_impact=SecurityImpact.DEGRADES,  # Security degrades!
        operational_label="none",  # No operational impact
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.INFRASTRUCTURE},
    )

    assert decision.decision == Decision.RISKY
    assert ReasonCode.SECURITY_DEGRADES in decision.reasons


@pytest.mark.unit
def test_absence_well_supported():
    """Test SAFE when absence is well-supported.

    Scenario: No high-belief dependencies + high sufficiency → SAFE
    """
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("cache")

    # Add edge with LOW confidence (no strong dependency)
    G.add_edge(
        "backend",
        "cache",
        key=0,
        relationship="DEPENDS_ON",
        conf_by_type={"infrastructure": 0.2},  # Low confidence
        conflicted=False,
    )

    bundle = make_test_bundle()
    # Add coverage information
    from evgate.contracts.evidence import RuntimeCoverage

    bundle.coverage = RuntimeCoverage(
        window_start=datetime(2026, 10, 15, 12, 0, 0),
        window_end=datetime(2026, 10, 15, 12, 5, 0),
        workload_id="test-workload",
        requests_total=100,
        endpoints_known=["backend:/health", "backend:/api"],
        endpoints_exercised=["backend:/health", "backend:/api"],
        components_observed=["backend", "cache"],
        spans_total=50,
    )

    change = ChangeSpec(
        change_id="SAFE-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Block low-confidence path",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="backend",
                dst="cache",
                port=6379,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.85,  # High sufficiency for absence
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="none",
        tau_pos=0.5,  # 0.2 < 0.5, so no positive evidence
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.INFRASTRUCTURE, EvidenceType.RUNTIME},
    )

    assert decision.decision == Decision.SAFE
    assert ReasonCode.ABSENCE_WELL_SUPPORTED in decision.reasons


@pytest.mark.unit
def test_no_runtime_evidence():
    """Test INSUFFICIENT when no runtime evidence but runtime in mask.

    Per §8.4: absence of runtime never produces SAFE without coverage
    """
    G = nx.MultiDiGraph()
    bundle = make_test_bundle()
    # coverage is None by default (no runtime)

    change = ChangeSpec(
        change_id="NO-RUNTIME-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="No runtime evidence",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="unknown",
                dst="service",
                port=8000,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.5,
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="none",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.RUNTIME},  # Runtime in mask but no evidence
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert ReasonCode.NO_RUNTIME_EVIDENCE in decision.reasons
    assert len(decision.evidence_requests) > 0


@pytest.mark.unit
def test_absence_not_informative():
    """Test INSUFFICIENT when absence not informative (low sufficiency)."""
    G = nx.MultiDiGraph()
    bundle = make_test_bundle()

    change = ChangeSpec(
        change_id="LOW-SUFF-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Low sufficiency for absence",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="component",
                dst="service",
                port=8000,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.3,  # Low sufficiency
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="none",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,  # 0.3 < 0.7, so absence not well-supported
        mask={EvidenceType.INFRASTRUCTURE},
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert ReasonCode.ABSENCE_NOT_INFORMATIVE in decision.reasons


@pytest.mark.unit
def test_forced_decision_risky_operational():
    """Test forced decision mode: RISKY when operational high."""
    decision = forced_decision(
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="high",
    )

    assert decision.decision == Decision.RISKY
    assert ReasonCode.FORCED_DECISION in decision.reasons


@pytest.mark.unit
def test_forced_decision_risky_security():
    """Test forced decision mode: RISKY when security degrades."""
    decision = forced_decision(
        security_impact=SecurityImpact.DEGRADES,
        operational_label="none",
    )

    assert decision.decision == Decision.RISKY
    assert ReasonCode.FORCED_DECISION in decision.reasons


@pytest.mark.unit
def test_forced_decision_safe():
    """Test forced decision mode: SAFE when both low risk."""
    decision = forced_decision(
        security_impact=SecurityImpact.IMPROVES,
        operational_label="low",
    )

    assert decision.decision == Decision.SAFE
    assert ReasonCode.FORCED_DECISION in decision.reasons


@pytest.mark.unit
def test_evidence_requests_generation():
    """Test that evidence requests are generated appropriately."""
    G = nx.MultiDiGraph()
    bundle = make_test_bundle()
    # coverage is None (no runtime)

    change = ChangeSpec(
        change_id="REQUEST-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Test evidence requests",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="component",
                dst="service",
                port=8000,
                before="allowed",
                after="denied",
            )
        ],
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.3,
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="none",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.RUNTIME},  # Runtime in mask but no coverage
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert len(decision.evidence_requests) > 0

    # Should request runtime workload
    actions = [req.action for req in decision.evidence_requests]
    assert "run_workload" in actions


@pytest.mark.unit
def test_no_effects():
    """Test that change with no effects is INSUFFICIENT."""
    G = nx.MultiDiGraph()
    bundle = make_test_bundle()

    change = ChangeSpec(
        change_id="NO-EFFECTS-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="No effects",
        after_ref="/test",
        effects=[],  # No effects
    )

    decision = apply_evidence_gate(
        change=change,
        graph=G,
        bundle=bundle,
        sufficiency=0.8,
        security_impact=SecurityImpact.NEUTRAL,
        operational_label="none",
        tau_pos=0.5,
        tau_suff_pos=0.6,
        tau_suff_neg=0.7,
        mask={EvidenceType.INFRASTRUCTURE},
    )

    assert decision.decision == Decision.INSUFFICIENT_EVIDENCE
    assert ReasonCode.UNSUPPORTED_CHANGE in decision.reasons
