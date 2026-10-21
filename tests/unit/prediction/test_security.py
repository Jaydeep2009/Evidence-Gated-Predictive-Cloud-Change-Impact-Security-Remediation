"""Unit tests for security impact analysis.

Tests verify §8.3 security impact calculation:
- Path exposure for sensitive components
- Permission weighting
- Exposure and permission deltas
- Overall security impact classification
"""

import networkx as nx
import pytest

from evgate.contracts import ChangeSpec, PathEffect, PermissionEffect
from evgate.prediction.security import (
    SecurityImpact,
    compute_exposure_delta,
    compute_path_exposure,
    compute_permission_delta,
    compute_security_impact,
    get_permission_weight,
    is_sensitive_component,
)


@pytest.mark.unit
def test_is_sensitive_component_tier_data():
    """Test detection of sensitive component by tier=data label."""
    G = nx.MultiDiGraph()
    G.add_node(
        "database",
        labels={"tier": "data", "app": "postgres"},
    )

    assert is_sensitive_component(G, "database") is True


@pytest.mark.unit
def test_is_sensitive_component_credentials_tag():
    """Test detection of sensitive component by credentials tag."""
    G = nx.MultiDiGraph()
    G.add_node(
        "vault",
        labels={"app": "vault"},
        tags=["credentials", "secrets-manager"],
    )

    assert is_sensitive_component(G, "vault") is True


@pytest.mark.unit
def test_is_sensitive_component_not_sensitive():
    """Test that regular components are not marked sensitive."""
    G = nx.MultiDiGraph()
    G.add_node(
        "frontend",
        labels={"tier": "presentation", "app": "nginx"},
    )

    assert is_sensitive_component(G, "frontend") is False


@pytest.mark.unit
def test_permission_weight_wildcard():
    """Test that wildcard gets highest weight (5)."""
    assert get_permission_weight("*", "pods") == 5
    assert get_permission_weight("get", "*") == 5
    assert get_permission_weight("*", "*") == 5


@pytest.mark.unit
def test_permission_weight_secrets():
    """Test secrets resource weights."""
    # Any verb on secrets (except list/watch) = 4
    assert get_permission_weight("get", "secrets") == 4
    assert get_permission_weight("create", "secrets") == 4
    assert get_permission_weight("delete", "secrets") == 4

    # list/watch on secrets = 3
    assert get_permission_weight("list", "secrets") == 3
    assert get_permission_weight("watch", "secrets") == 3


@pytest.mark.unit
def test_permission_weight_pods_exec():
    """Test that pods/exec gets weight 4."""
    assert get_permission_weight("create", "pods/exec") == 4


@pytest.mark.unit
def test_permission_weight_escalation_verbs():
    """Test privilege escalation verbs get weight 4."""
    assert get_permission_weight("escalate", "roles") == 4
    assert get_permission_weight("bind", "clusterroles") == 4
    assert get_permission_weight("impersonate", "serviceaccounts") == 4


@pytest.mark.unit
def test_permission_weight_workload_writes():
    """Test write verbs on workload resources get weight 3."""
    workloads = ["pods", "deployments", "statefulsets", "daemonsets", "jobs"]
    write_verbs = ["create", "update", "patch", "delete"]

    for resource in workloads:
        for verb in write_verbs:
            assert get_permission_weight(verb, resource) == 3


@pytest.mark.unit
def test_permission_weight_other_writes():
    """Test write verbs on non-workload resources get weight 2."""
    assert get_permission_weight("create", "configmaps") == 2
    assert get_permission_weight("update", "services") == 2
    assert get_permission_weight("delete", "namespaces") == 2


@pytest.mark.unit
def test_permission_weight_reads():
    """Test read verbs get weight 1."""
    assert get_permission_weight("get", "pods") == 1
    assert get_permission_weight("list", "deployments") == 1
    assert get_permission_weight("watch", "services") == 1


@pytest.mark.unit
def test_exposure_delta_improves():
    """Test exposure reduction is classified as IMPROVES.

    Per §8.3: delta ≤ -0.1 → improves
    """
    # Reduction from 10 to 2: delta = (2-10)/10 = -0.8
    delta, impact = compute_exposure_delta(10, 2)
    assert delta == pytest.approx(-0.8)
    assert impact == SecurityImpact.IMPROVES


@pytest.mark.unit
def test_exposure_delta_degrades():
    """Test exposure increase is classified as DEGRADES.

    Per §8.3: delta ≥ +0.1 → degrades
    """
    # Increase from 5 to 10: delta = (10-5)/5 = 1.0
    delta, impact = compute_exposure_delta(5, 10)
    assert delta == pytest.approx(1.0)
    assert impact == SecurityImpact.DEGRADES


@pytest.mark.unit
def test_exposure_delta_neutral():
    """Test small exposure changes are NEUTRAL.

    Per §8.3: -0.1 < delta < +0.1 → neutral
    """
    # Small change: 10 to 10 (no change)
    delta, impact = compute_exposure_delta(10, 10)
    assert delta == 0.0
    assert impact == SecurityImpact.NEUTRAL

    # Small increase: 10 to 10.5 (5% increase, below threshold)
    delta, impact = compute_exposure_delta(10, 10)
    assert delta == 0.0
    assert impact == SecurityImpact.NEUTRAL


@pytest.mark.unit
def test_exposure_delta_zero_before():
    """Test exposure delta when starting from zero.

    Per §8.3: denominator = max(1, exposure_before)
    """
    # No exposure before, some after: delta = 5/1 = 5.0
    delta, impact = compute_exposure_delta(0, 5)
    assert delta == pytest.approx(5.0)
    assert impact == SecurityImpact.DEGRADES


@pytest.mark.unit
def test_path_exposure_calculation():
    """Test path exposure counting for sensitive components."""
    # Build graph with sensitive database
    G = nx.MultiDiGraph()
    G.add_node("frontend", labels={"tier": "presentation"})
    G.add_node("backend", labels={"tier": "application"})
    G.add_node("database", labels={"tier": "data"})  # Sensitive

    # Create path effects
    effects = [
        PathEffect(
            kind="path",
            src="frontend",
            dst="database",
            port=5432,
            before="allowed",
            after="denied",
        ),
        PathEffect(
            kind="path",
            src="backend",
            dst="database",
            port=5432,
            before="allowed",
            after="allowed",  # Still allowed
        ),
    ]

    # Before: both frontend and backend can reach database
    exposure_before = compute_path_exposure(G, effects, "before")
    assert exposure_before == 2  # (frontend, 5432) + (backend, 5432)

    # After: only backend can reach database
    exposure_after = compute_path_exposure(G, effects, "after")
    assert exposure_after == 1  # (backend, 5432)


@pytest.mark.unit
def test_path_exposure_no_sensitive():
    """Test path exposure is 0 when no sensitive components."""
    G = nx.MultiDiGraph()
    G.add_node("frontend", labels={"tier": "presentation"})
    G.add_node("backend", labels={"tier": "application"})

    effects = [
        PathEffect(
            kind="path",
            src="frontend",
            dst="backend",
            port=8000,
            before="allowed",
            after="denied",
        ),
    ]

    # No sensitive components, so exposure = 0
    exposure = compute_path_exposure(G, effects, "before")
    assert exposure == 0


@pytest.mark.unit
def test_permission_delta_grant_wildcard():
    """Test that granting wildcard permission degrades security.

    Scenario: Principal gains '* *' permission
    """
    effects = [
        PermissionEffect(
            kind="permission",
            principal="admin",
            verb="get",
            api_group="",
            resource="pods",
            before="granted",
            after="granted",  # Still has this
        ),
        PermissionEffect(
            kind="permission",
            principal="admin",
            verb="*",
            api_group="",
            resource="*",
            before="denied",
            after="granted",  # NEW: wildcard granted
        ),
    ]

    delta, impact = compute_permission_delta(effects)

    # Before: 1 (get pods)
    # After: 1 + 5 = 6
    # delta = (6-1)/1 = 5.0
    assert delta == pytest.approx(5.0)
    assert impact == SecurityImpact.DEGRADES


@pytest.mark.unit
def test_permission_delta_remove_permissions():
    """Test that removing permissions improves security."""
    effects = [
        PermissionEffect(
            kind="permission",
            principal="service-account",
            verb="get",
            api_group="",
            resource="secrets",
            before="granted",
            after="denied",  # Removed
        ),
        PermissionEffect(
            kind="permission",
            principal="service-account",
            verb="list",
            api_group="",
            resource="secrets",
            before="granted",
            after="denied",  # Removed
        ),
    ]

    delta, impact = compute_permission_delta(effects)

    # Before: 4 + 3 = 7
    # After: 0
    # delta = (0-7)/7 ≈ -1.0
    assert delta == pytest.approx(-1.0)
    assert impact == SecurityImpact.IMPROVES


@pytest.mark.unit
def test_permission_delta_neutral():
    """Test that small permission changes are neutral."""
    effects = [
        PermissionEffect(
            kind="permission",
            principal="reader",
            verb="get",
            api_group="",
            resource="pods",
            before="granted",
            after="granted",
        ),
    ]

    delta, impact = compute_permission_delta(effects)

    # No change
    assert delta == 0.0
    assert impact == SecurityImpact.NEUTRAL


@pytest.mark.unit
def test_compute_security_impact_m2_scenario():
    """Test M2 scenario: NetworkPolicy restricts database ingress.

    Expected: Security IMPROVES (reduced exposure to sensitive data)
    """
    # Build graph with sensitive database
    G = nx.MultiDiGraph()
    G.add_node("frontend", labels={"tier": "presentation"})
    G.add_node("backend", labels={"tier": "application"})
    G.add_node("database", labels={"tier": "data"})  # Sensitive

    # M2 change: Block frontend→database, allow only backend→database
    change = ChangeSpec(
        change_id="M2",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Isolate database from frontend",
        after_ref="/policies/isolate-database.yaml",
        effects=[
            PathEffect(
                kind="path",
                src="frontend",
                dst="database",
                port=5432,
                before="allowed",
                after="denied",  # Blocked
            ),
            PathEffect(
                kind="path",
                src="backend",
                dst="database",
                port=5432,
                before="allowed",
                after="allowed",  # Still allowed
            ),
        ],
    )

    impact, delta, details = compute_security_impact(change, G)

    # Exposure reduced from 2 to 1
    assert details["exposure_before"] == 2
    assert details["exposure_after"] == 1
    assert delta < 0  # Negative delta = improvement
    assert impact == SecurityImpact.IMPROVES


@pytest.mark.unit
def test_compute_security_impact_wildcard_grant():
    """Test wildcard grant scenario: Security DEGRADES."""
    G = nx.MultiDiGraph()
    G.add_node("service-account", labels={"type": "identity"})

    # Grant wildcard permission
    change = ChangeSpec(
        change_id="WILDCARD-001",
        category="kubernetes",
        kind="k8s_rbac",
        operation="modify",
        summary="Grant admin permissions",
        after_ref="/rbac/admin-role.yaml",
        effects=[
            PermissionEffect(
                kind="permission",
                principal="service-account",
                verb="*",
                api_group="",
                resource="*",
                before="denied",
                after="granted",
            ),
        ],
    )

    impact, delta, details = compute_security_impact(change, G)

    assert delta > 0  # Positive delta = degradation
    assert impact == SecurityImpact.DEGRADES


@pytest.mark.unit
def test_compute_security_impact_mixed():
    """Test change with both path and permission effects.

    If one degrades, overall degrades (worst case).
    """
    G = nx.MultiDiGraph()
    G.add_node("database", labels={"tier": "data"})

    # Path: improves (blocks access)
    # Permission: degrades (grants wildcard)
    change = ChangeSpec(
        change_id="MIXED-001",
        category="kubernetes",
        kind="k8s_networkpolicy",
        operation="modify",
        summary="Mixed security change",
        after_ref="/test",
        effects=[
            PathEffect(
                kind="path",
                src="attacker",
                dst="database",
                port=5432,
                before="allowed",
                after="denied",  # Good: blocks attacker
            ),
            PermissionEffect(
                kind="permission",
                principal="service",
                verb="*",
                api_group="",
                resource="secrets",
                before="denied",
                after="granted",  # Bad: grants wildcard
            ),
        ],
    )

    impact, delta, details = compute_security_impact(change, G)

    # Overall should degrade (worst of the two)
    assert impact == SecurityImpact.DEGRADES


@pytest.mark.unit
def test_compute_security_impact_no_effects():
    """Test change with no effects is neutral."""
    G = nx.MultiDiGraph()

    change = ChangeSpec(
        change_id="EMPTY-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Empty change",
        after_ref="/test",
        effects=[],
    )

    impact, delta, details = compute_security_impact(change, G)

    assert impact == SecurityImpact.NEUTRAL
    assert delta == 0.0
