"""Simple unit tests for operational propagation core logic."""

import networkx as nx
import pytest

from evgate.contracts import PathEffect
from evgate.prediction.operational import (
    ComponentImpact,
    ImpactMechanism,
    OperationalStatus,
    compute_operational_risk,
)
from evgate.prediction.propagate import (
    check_readiness_coupling,
    get_belief_for_effect,
    tightens_access,
)


@pytest.mark.unit
def test_tightens_path_allowed_to_denied():
    """Test that allowed→denied is tightening."""
    effect = PathEffect(
        kind="path",
        src="backend",
        dst="database",
        before="allowed",
        after="denied",
    )
    assert tightens_access(effect) is True


@pytest.mark.unit
def test_tightens_path_denied_to_allowed():
    """Test that denied→allowed is NOT tightening."""
    effect = PathEffect(
        kind="path",
        src="backend",
        dst="database",
        before="denied",
        after="allowed",
    )
    assert tightens_access(effect) is False


@pytest.mark.unit
def test_check_readiness_coupling_exists():
    """Test detection of READINESS_COUPLED relationship."""
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")
    G.add_edge(
        "backend",
        "database",
        key=0,
        relationship="READINESS_COUPLED",
    )

    assert check_readiness_coupling(G, "backend", "database") is True


@pytest.mark.unit
def test_check_readiness_coupling_not_exists():
    """Test when only DEPENDS_ON exists, not READINESS_COUPLED."""
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")
    G.add_edge(
        "backend",
        "database",
        key=0,
        relationship="DEPENDS_ON",
    )

    assert check_readiness_coupling(G, "backend", "database") is False


@pytest.mark.unit
def test_get_belief_from_edge():
    """Test belief extraction from graph edge."""
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")
    G.add_edge(
        "backend",
        "database",
        key=0,
        relationship="DEPENDS_ON",
        conf_by_type={"application": 0.85, "runtime": 1.0},
    )

    reliability = {"application": 0.8, "runtime": 0.9}
    mask = {"application", "runtime"}

    belief = get_belief_for_effect(G, "backend", "database", reliability, mask)

    # Should compute from conf_by_type
    # belief = 1 - (1-0.8*0.85)(1-0.9*1.0) ≈ 0.932
    assert belief > 0.9


@pytest.mark.unit
def test_get_belief_no_edge():
    """Test belief is 0 when no edge exists."""
    G = nx.MultiDiGraph()
    G.add_node("backend")
    G.add_node("database")

    reliability = {"application": 0.8}
    mask = {"application"}

    belief = get_belief_for_effect(G, "backend", "database", reliability, mask)
    assert belief == 0.0


@pytest.mark.unit
def test_operational_risk_high():
    """Test operational risk with unavailable component."""
    impacts = [
        ComponentImpact(
            component="backend",
            status=OperationalStatus.UNAVAILABLE,
            mechanism=ImpactMechanism.READINESS_COUPLED,
            probability=0.9,
        ),
        ComponentImpact(
            component="database",
            status=OperationalStatus.DEGRADED,
            mechanism=ImpactMechanism.DIRECT_PATH_BLOCKED,
            probability=0.8,
        ),
    ]

    risk, label = compute_operational_risk(impacts)

    # backend: 0.9 * 1.0 = 0.9
    # database: 0.8 * 0.5 = 0.4
    # risk = 1 - (1-0.9)(1-0.4) = 1 - 0.1*0.6 = 0.94
    assert risk == pytest.approx(0.94)
    assert label in ("low", "high")


@pytest.mark.unit
def test_operational_risk_low():
    """Test operational risk with minor degradation."""
    impacts = [
        ComponentImpact(
            component="backend",
            status=OperationalStatus.DEGRADED,
            mechanism=ImpactMechanism.DIRECT_PATH_BLOCKED,
            probability=0.1,
        ),
    ]

    risk, label = compute_operational_risk(impacts)

    # 0.1 * 0.5 = 0.05
    # risk = 1 - (1-0.05) = 0.05
    assert risk == pytest.approx(0.05)
    assert label == "none"


@pytest.mark.unit
def test_operational_risk_none():
    """Test operational risk with no impacts."""
    impacts = []

    risk, label = compute_operational_risk(impacts)

    assert risk == 0.0
    assert label == "none"


@pytest.mark.unit
def test_component_impact_to_dict():
    """Test ComponentImpact serialization."""
    impact = ComponentImpact(
        component="backend",
        status=OperationalStatus.UNAVAILABLE,
        mechanism=ImpactMechanism.READINESS_COUPLED,
        probability=0.9,
        caused_by="database",
        belief=0.85,
    )

    data = impact.to_dict()

    assert data["component"] == "backend"
    assert data["status"] == "unavailable"
    assert data["mechanism"] == "readiness_coupled"
    assert data["probability"] == 0.9
    assert data["caused_by"] == "database"
    assert data["belief"] == 0.85
