"""Unit tests for graph builder."""

import json
from pathlib import Path

import pytest

from evgate.contracts import EvidenceBundle, EvidenceType
from evgate.graph import build_graph, dependency_view


@pytest.fixture
def g1_bundle():
    """Load G1 golden fixture."""
    fixture_path = Path("fixtures/golden/G1_bundle_full.json")
    with open(fixture_path) as f:
        data = json.load(f)
    return EvidenceBundle(**data)


@pytest.mark.unit
def test_graph_build_with_all_evidence(g1_bundle):
    """Test building graph with all evidence types (mask D)."""
    G = build_graph(g1_bundle, mask=None)

    # Check nodes
    # 3 from inventory + 3 additional (config, 2 k8s-services)
    assert G.number_of_nodes() >= 3, "Should have at least inventory nodes"

    # Verify inventory nodes present
    assert "component:poc-app/frontend" in G.nodes()
    assert "component:poc-app/backend" in G.nodes()
    assert "component:poc-app/database" in G.nodes()

    # Check node attributes
    backend_attrs = G.nodes["component:poc-app/backend"]
    assert backend_attrs["kind"] == "component"
    assert backend_attrs["namespace"] == "poc-app"
    assert "app" in backend_attrs["labels"]


@pytest.mark.unit
def test_graph_edges_aggregation(g1_bundle):
    """Test that edges aggregate evidence correctly."""
    G = build_graph(g1_bundle, mask=None)

    # backend → database should have multiple relationship types
    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    # Get all edges between backend and database
    edges = list(G[backend][database].items())
    assert len(edges) >= 3, "Should have DEPENDS_ON, READINESS_COUPLED, CONNECTS_TO"

    # Find DEPENDS_ON edge
    depends_on_edge = None
    for key, data in edges:
        if key == "DEPENDS_ON":
            depends_on_edge = data
            break

    assert depends_on_edge is not None, "Should have DEPENDS_ON edge"

    # Check aggregated attributes
    assert "evidence_ids" in depends_on_edge
    assert "by_type" in depends_on_edge
    assert "conf_by_type" in depends_on_edge
    assert "conflicted" in depends_on_edge
    assert "snapshot_id" in depends_on_edge

    # DEPENDS_ON has both infra (E-infra-002) and app (E-app-001) evidence
    assert "infrastructure" in depends_on_edge["by_type"]
    assert "application" in depends_on_edge["by_type"]
    assert "E-infra-002" in depends_on_edge["evidence_ids"]
    assert "E-app-001" in depends_on_edge["evidence_ids"]


@pytest.mark.unit
def test_graph_mask_infrastructure_only(g1_bundle):
    """Test mask A: infrastructure only."""
    mask_a = {EvidenceType.INFRASTRUCTURE}
    G = build_graph(g1_bundle, mask=mask_a)

    # Should have nodes from inventory
    assert G.number_of_nodes() >= 3

    # backend → database DEPENDS_ON should have only infrastructure evidence
    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    if database in G[backend]:
        for key, data in G[backend][database].items():
            if key == "DEPENDS_ON":
                assert "infrastructure" in data["by_type"]
                assert "application" not in data["by_type"]
                assert "runtime" not in data["by_type"]

        # READINESS_COUPLED (app-only) should not exist
        assert "READINESS_COUPLED" not in G[backend][database]

        # CONNECTS_TO (runtime-only) should not exist
        assert "CONNECTS_TO" not in G[backend][database]


@pytest.mark.unit
def test_graph_mask_infrastructure_application(g1_bundle):
    """Test mask B: infrastructure + application."""
    mask_b = {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION}
    G = build_graph(g1_bundle, mask=mask_b)

    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    # backend → database should have DEPENDS_ON with both types
    if database in G[backend]:
        depends_on_data = G[backend][database].get("DEPENDS_ON")
        if depends_on_data:
            assert "infrastructure" in depends_on_data["by_type"]
            assert "application" in depends_on_data["by_type"]
            assert "runtime" not in depends_on_data["by_type"]

        # READINESS_COUPLED (app) should exist
        assert "READINESS_COUPLED" in G[backend][database]

        # CONNECTS_TO (runtime-only) should NOT exist
        assert "CONNECTS_TO" not in G[backend][database]


@pytest.mark.unit
def test_graph_mask_infrastructure_runtime(g1_bundle):
    """Test mask C: infrastructure + runtime."""
    mask_c = {EvidenceType.INFRASTRUCTURE, EvidenceType.RUNTIME}
    G = build_graph(g1_bundle, mask=mask_c)

    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    if database in G[backend]:
        # DEPENDS_ON should have only infrastructure (app filtered out)
        depends_on_data = G[backend][database].get("DEPENDS_ON")
        if depends_on_data:
            assert "infrastructure" in depends_on_data["by_type"]
            assert "application" not in depends_on_data["by_type"]
            assert "runtime" not in depends_on_data["by_type"]

        # CONNECTS_TO (runtime) should exist
        assert "CONNECTS_TO" in G[backend][database]

        # READINESS_COUPLED (app-only) should NOT exist
        assert "READINESS_COUPLED" not in G[backend][database]


@pytest.mark.unit
def test_confidence_aggregation_noisy_or(g1_bundle):
    """Test noisy-OR confidence aggregation within evidence types."""
    G = build_graph(g1_bundle, mask=None)

    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    # Get DEPENDS_ON edge
    depends_on_data = G[backend][database].get("DEPENDS_ON")
    assert depends_on_data is not None

    # Check conf_by_type
    assert "infrastructure" in depends_on_data["conf_by_type"]
    assert "application" in depends_on_data["conf_by_type"]

    # Infrastructure has 1 evidence with conf 0.5
    # conf = 1 - (1 - 0.5) = 0.5
    assert depends_on_data["conf_by_type"]["infrastructure"] == pytest.approx(0.5)

    # Application has 1 evidence with conf 0.85
    # conf = 1 - (1 - 0.85) = 0.85
    assert depends_on_data["conf_by_type"]["application"] == pytest.approx(0.85)


@pytest.mark.unit
def test_no_conflicts_in_g1(g1_bundle):
    """Test that G1 has no conflicting evidence."""
    G = build_graph(g1_bundle, mask=None)

    # Check all edges for conflicts
    for src, dst, key, data in G.edges(keys=True, data=True):
        assert (
            data.get("conflicted") is False
        ), f"G1 should have no conflicts: {src} -> {dst} ({key})"


@pytest.mark.unit
def test_dependency_view(g1_bundle):
    """Test dependency view extraction."""
    G = build_graph(g1_bundle, mask=None)
    deps = dependency_view(G)

    # backend → database should be in dependency view
    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    assert (backend, database) in deps

    dep_record = deps[(backend, database)]

    # Check DependencyRecord attributes
    assert dep_record.belief > 0.0
    assert (
        len(dep_record.relationships) >= 3
    )  # DEPENDS_ON, READINESS_COUPLED, CONNECTS_TO
    assert dep_record.has_conflict is False
    assert dep_record.already_failing is False
    assert len(dep_record.evidence_ids) >= 3

    # Check conf_by_type
    assert "infrastructure" in dep_record.conf_by_type
    assert "application" in dep_record.conf_by_type
    assert "runtime" in dep_record.conf_by_type


@pytest.mark.unit
def test_dependency_view_with_mask(g1_bundle):
    """Test dependency view with different evidence masks."""
    # Mask A: infrastructure only
    G_a = build_graph(g1_bundle, mask={EvidenceType.INFRASTRUCTURE})
    deps_a = dependency_view(G_a)

    backend = "component:poc-app/backend"
    database = "component:poc-app/database"

    if (backend, database) in deps_a:
        dep_a = deps_a[(backend, database)]
        # Should only have infrastructure conf
        assert "infrastructure" in dep_a.conf_by_type
        assert "application" not in dep_a.conf_by_type
        assert "runtime" not in dep_a.conf_by_type


@pytest.mark.unit
def test_node_counts_by_mask(g1_bundle):
    """Test node counts are consistent across masks."""
    G_a = build_graph(g1_bundle, mask={EvidenceType.INFRASTRUCTURE})
    G_b = build_graph(
        g1_bundle, mask={EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION}
    )
    G_c = build_graph(
        g1_bundle, mask={EvidenceType.INFRASTRUCTURE, EvidenceType.RUNTIME}
    )
    G_d = build_graph(g1_bundle, mask=None)  # All

    # Node counts should be the same (mask doesn't affect nodes, only edges)
    assert G_a.number_of_nodes() == G_b.number_of_nodes()
    assert G_b.number_of_nodes() == G_c.number_of_nodes()
    assert G_c.number_of_nodes() == G_d.number_of_nodes()


@pytest.mark.unit
def test_edge_counts_increase_with_mask(g1_bundle):
    """Test edge counts increase as more evidence types are included."""
    G_a = build_graph(g1_bundle, mask={EvidenceType.INFRASTRUCTURE})
    G_d = build_graph(g1_bundle, mask=None)  # All

    # D (all evidence) should have more edges than A (infra only)
    assert G_d.number_of_edges() >= G_a.number_of_edges()


@pytest.mark.unit
def test_graph_deterministic(g1_bundle):
    """Test that graph building is deterministic."""
    G1 = build_graph(g1_bundle, mask=None)
    G2 = build_graph(g1_bundle, mask=None)

    # Same number of nodes and edges
    assert G1.number_of_nodes() == G2.number_of_nodes()
    assert G1.number_of_edges() == G2.number_of_edges()

    # Same node IDs
    assert set(G1.nodes()) == set(G2.nodes())

    # Same edge keys
    edges1 = {(s, d, k) for s, d, k in G1.edges(keys=True)}
    edges2 = {(s, d, k) for s, d, k in G2.edges(keys=True)}
    assert edges1 == edges2
