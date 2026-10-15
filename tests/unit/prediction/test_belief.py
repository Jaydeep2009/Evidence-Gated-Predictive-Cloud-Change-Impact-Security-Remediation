"""Unit tests for belief/sufficiency/confidence calculations.

Tests use hand-computed examples from §8.2 specification to verify formulas.
"""

import pytest

from evgate.contracts import EvidenceType, StaticCompleteness
from evgate.prediction.belief import (
    aggregate_evidence_noisy_or,
    compute_absence_informativeness,
    compute_belief,
    compute_change_sufficiency,
    compute_confidence,
    compute_path_sufficiency,
)


@pytest.mark.unit
def test_noisy_or_single_evidence():
    """Test noisy-OR with single evidence item."""
    result = aggregate_evidence_noisy_or([0.8])
    assert result == pytest.approx(0.8)


@pytest.mark.unit
def test_noisy_or_two_evidence():
    """Test noisy-OR with two evidence items.

    Formula: 1 - (1-0.8)(1-0.7) = 1 - 0.2*0.3 = 1 - 0.06 = 0.94
    """
    result = aggregate_evidence_noisy_or([0.8, 0.7])
    assert result == pytest.approx(0.94)


@pytest.mark.unit
def test_noisy_or_three_evidence():
    """Test noisy-OR with three evidence items.

    Formula: 1 - (1-0.8)(1-0.7)(1-0.6) = 1 - 0.2*0.3*0.4 = 1 - 0.024 = 0.976
    """
    result = aggregate_evidence_noisy_or([0.8, 0.7, 0.6])
    assert result == pytest.approx(0.976)


@pytest.mark.unit
def test_noisy_or_top_k_limit():
    """Test that top_k limits evidence aggregation.

    With top_k=3, only top 3 items are used.
    """
    # Should take [0.8, 0.7, 0.6] and ignore 0.5
    result = aggregate_evidence_noisy_or([0.8, 0.7, 0.6, 0.5], top_k=3)
    expected = aggregate_evidence_noisy_or([0.8, 0.7, 0.6])
    assert result == pytest.approx(expected)


@pytest.mark.unit
def test_belief_single_type():
    """Test belief computation with single evidence type.

    Example from spec comment:
    conf = {"infrastructure": 0.5}
    reliability = {"infrastructure": 0.6}
    belief = 1 - (1 - 0.6*0.5) = 1 - 0.7 = 0.3
    """
    conf_by_type = {"infrastructure": 0.5}
    reliability = {"infrastructure": 0.6, "application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.INFRASTRUCTURE}

    belief = compute_belief(conf_by_type, reliability, mask)
    assert belief == pytest.approx(0.3)


@pytest.mark.unit
def test_belief_two_types():
    """Test belief computation with two evidence types.

    Example from spec docstring:
    conf = {"infrastructure": 0.5, "application": 0.85}
    reliability = {"infrastructure": 0.6, "application": 0.8}

    belief = 1 - (1 - 0.6*0.5)(1 - 0.8*0.85)
           = 1 - (1 - 0.3)(1 - 0.68)
           = 1 - 0.7*0.32
           = 1 - 0.224
           = 0.776
    """
    conf_by_type = {"infrastructure": 0.5, "application": 0.85}
    reliability = {"infrastructure": 0.6, "application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION}

    belief = compute_belief(conf_by_type, reliability, mask)
    assert belief == pytest.approx(0.776)


@pytest.mark.unit
def test_belief_all_three_types():
    """Test belief with all three evidence types."""
    conf_by_type = {"infrastructure": 0.5, "application": 0.85, "runtime": 1.0}
    reliability = {"infrastructure": 0.6, "application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION, EvidenceType.RUNTIME}

    # belief = 1 - (1 - 0.6*0.5)(1 - 0.8*0.85)(1 - 0.9*1.0)
    #        = 1 - 0.7 * 0.32 * 0.1
    #        = 1 - 0.0224
    #        = 0.9776
    belief = compute_belief(conf_by_type, reliability, mask)
    assert belief == pytest.approx(0.9776)


@pytest.mark.unit
def test_belief_with_contradiction():
    """Test belief reduction from contradicting evidence."""
    conf_by_type = {"infrastructure": 0.5}
    reliability = {"infrastructure": 0.6, "runtime": 0.9}
    mask = {EvidenceType.INFRASTRUCTURE}
    contradicting = {"infrastructure": 0.4}  # Contradicting infra evidence

    # Base belief = 0.3 (from test_belief_single_type)
    # With contradiction: belief *= (1 - 0.6*0.4) = 0.3 * (1 - 0.24) = 0.3 * 0.76 = 0.228
    belief = compute_belief(conf_by_type, reliability, mask, contradicting)
    assert belief == pytest.approx(0.228)


@pytest.mark.unit
def test_absence_informativeness_app_only():
    """Test absence informativeness with only application evidence.

    Example from spec:
    static_score = 1.0, r_app = 0.8
    a = 1.0 * 0.8 = 0.8
    b = 0
    neg = 1 - (1-0.8)(1-0) = 1 - 0.2*1.0 = 0.8
    """
    completeness = StaticCompleteness(
        component="backend", files_analyzed=["main.py"], unresolved_dynamic_calls=0
    )
    reliability = {"application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.APPLICATION}

    neg = compute_absence_informativeness(completeness, None, reliability, mask)
    assert neg == pytest.approx(0.8)


@pytest.mark.unit
def test_absence_informativeness_runtime_only():
    """Test absence informativeness with only runtime evidence."""
    reliability = {"application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.RUNTIME}
    coverage = 0.8

    # a = 0, b = 0.8 * 0.9 = 0.72
    # neg = 1 - (1-0)(1-0.72) = 1 - 0.28 = 0.72
    neg = compute_absence_informativeness(None, coverage, reliability, mask)
    assert neg == pytest.approx(0.72)


@pytest.mark.unit
def test_absence_informativeness_both():
    """Test absence informativeness with both app and runtime.

    Example from spec docstring:
    static_score = 1.0, coverage = 0.8
    r_app = 0.8, r_runtime = 0.9

    a = 1.0 * 0.8 = 0.8
    b = 0.8 * 0.9 = 0.72
    neg = 1 - (1-0.8)(1-0.72) = 1 - 0.2*0.28 = 1 - 0.056 = 0.944
    """
    completeness = StaticCompleteness(
        component="backend", files_analyzed=["main.py"], unresolved_dynamic_calls=0
    )
    reliability = {"application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.APPLICATION, EvidenceType.RUNTIME}
    coverage = 0.8

    neg = compute_absence_informativeness(completeness, coverage, reliability, mask)
    assert neg == pytest.approx(0.944)


@pytest.mark.unit
def test_absence_informativeness_infrastructure_only():
    """Test that infrastructure alone cannot establish absence."""
    reliability = {"infrastructure": 0.6}
    mask = {EvidenceType.INFRASTRUCTURE}

    # Infrastructure contributes 0 to absence informativeness
    neg = compute_absence_informativeness(None, None, reliability, mask)
    assert neg == pytest.approx(0.0)


@pytest.mark.unit
def test_path_sufficiency_positive_single_type():
    """Test path sufficiency with single evidence type.

    type_factor = min(1, 1/2) = 0.5
    mean_conf = 0.85
    S = 0.5 * 0.85 = 0.425
    """
    conf_by_type = {"application": 0.85}
    suff = compute_path_sufficiency(conf_by_type, n_types_supporting=1)
    assert suff == pytest.approx(0.425)


@pytest.mark.unit
def test_path_sufficiency_positive_two_types():
    """Test path sufficiency with two evidence types.

    type_factor = min(1, 2/2) = 1.0
    mean_conf = (0.5 + 0.85) / 2 = 0.675
    S = 1.0 * 0.675 = 0.675
    """
    conf_by_type = {"infrastructure": 0.5, "application": 0.85}
    suff = compute_path_sufficiency(conf_by_type, n_types_supporting=2)
    assert suff == pytest.approx(0.675)


@pytest.mark.unit
def test_path_sufficiency_positive_three_types():
    """Test path sufficiency with three evidence types.

    Example from spec docstring:
    type_factor = min(1, 3/2) = 1.0
    mean_conf = (0.5 + 0.85 + 1.0) / 3 = 0.783
    S = 1.0 * 0.783 = 0.783
    """
    conf_by_type = {"infrastructure": 0.5, "application": 0.85, "runtime": 1.0}
    suff = compute_path_sufficiency(conf_by_type, n_types_supporting=3)
    assert suff == pytest.approx(0.783, abs=0.001)


@pytest.mark.unit
def test_path_sufficiency_absence():
    """Test path sufficiency for absence case.

    S_neg = neg(s,d) directly
    """
    absence_info = 0.944
    suff = compute_path_sufficiency({}, 0, absence_informativeness=absence_info)
    assert suff == pytest.approx(0.944)


@pytest.mark.unit
def test_change_sufficiency_single_path():
    """Test change sufficiency with single affected path."""
    suff = compute_change_sufficiency([0.85])
    assert suff == pytest.approx(0.85)


@pytest.mark.unit
def test_change_sufficiency_weakest_link():
    """Test change sufficiency as weakest link.

    Example from spec docstring:
    paths = [0.85, 0.90, 0.65]
    S_change = min(paths) = 0.65
    """
    suff = compute_change_sufficiency([0.85, 0.90, 0.65])
    assert suff == pytest.approx(0.65)


@pytest.mark.unit
def test_change_sufficiency_empty():
    """Test change sufficiency with no paths."""
    suff = compute_change_sufficiency([])
    assert suff == pytest.approx(0.0)


@pytest.mark.unit
def test_confidence_risky():
    """Test confidence for RISKY decision.

    Example from spec docstring:
    S = 0.85, belief = 0.776
    confidence = 0.85 * 0.776 = 0.6596
    """
    conf = compute_confidence(sufficiency=0.85, belief=0.776, decision="RISKY")
    assert conf == pytest.approx(0.6596)


@pytest.mark.unit
def test_confidence_safe():
    """Test confidence for SAFE decision.

    Example from spec docstring:
    S = 0.90, belief = 0.1
    confidence = 0.90 * (1 - 0.1) = 0.81
    """
    conf = compute_confidence(sufficiency=0.90, belief=0.1, decision="SAFE")
    assert conf == pytest.approx(0.81)


@pytest.mark.unit
def test_confidence_insufficient():
    """Test confidence for INSUFFICIENT decision.

    Reports sufficiency directly.
    """
    conf = compute_confidence(sufficiency=0.45, belief=0.5, decision="INSUFFICIENT")
    assert conf == pytest.approx(0.45)


@pytest.mark.unit
def test_full_pipeline_example():
    """Test a complete belief→sufficiency→confidence pipeline.

    Scenario: backend → database dependency with all three evidence types
    """
    # Step 1: Aggregate evidence within types (noisy-OR)
    infra_confs = [0.5]  # Single env reference
    app_confs = [0.85, 0.85]  # DEPENDS_ON + READINESS_COUPLED
    runtime_confs = [1.0]  # Observed connection

    conf_by_type = {
        "infrastructure": aggregate_evidence_noisy_or(infra_confs, top_k=3),
        "application": aggregate_evidence_noisy_or(app_confs, top_k=3),
        "runtime": aggregate_evidence_noisy_or(runtime_confs, top_k=3),
    }

    # Expected: infra=0.5, app=0.9775, runtime=1.0

    # Step 2: Compute belief
    reliability = {"infrastructure": 0.6, "application": 0.8, "runtime": 0.9}
    mask = {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION, EvidenceType.RUNTIME}

    belief = compute_belief(conf_by_type, reliability, mask)
    # Expected: high belief (>0.9)
    assert belief > 0.9

    # Step 3: Compute path sufficiency
    n_types = len([v for v in conf_by_type.values() if v > 0])
    suff = compute_path_sufficiency(conf_by_type, n_types)
    # Expected: high sufficiency (all 3 types present)
    assert suff > 0.75

    # Step 4: Compute confidence for RISKY decision
    confidence = compute_confidence(suff, belief, "RISKY")
    # Expected: high confidence (both belief and sufficiency high)
    assert confidence > 0.7
