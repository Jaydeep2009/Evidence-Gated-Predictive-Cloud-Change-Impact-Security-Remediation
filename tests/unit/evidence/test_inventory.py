"""Tests for P2-01: Component inventory and entity resolution.

Covers implementation.md §7.1 acceptance criteria:
  - inventory of the repo = {frontend, backend, database}
  - aliases for database-service[.poc-app[.svc[.cluster.local]]] resolve
  - deterministic node_id format
  - labels, ports, readiness_path from Deployment pod-template
  - Deployment name, Service DNS aliases, app-label alias all registered
  - alias collisions → warning + confidence factor 0.7
  - unresolved tokens → None + warning (no fabricated edges)
  - multi-document YAML loading
  - G1 golden fixture inventory matches build_inventory() output
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from evgate.contracts.bundle import ComponentInfo
from evgate.evidence.inventory import (
    _COLLISION_CONFIDENCE_FACTOR,
    ComponentInventory,
    build_inventory,
    load_manifests,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[3]
K8S_DIR = REPO_ROOT / "kubernetes"
FIXTURES_DIR = REPO_ROOT / "fixtures" / "golden"


def _write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    """Write YAML text to tmp_path/<name> and return the path."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Acceptance criterion: repo inventory = {frontend, backend, database}
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inventory_from_repo_manifests_has_three_components() -> None:
    """build_inventory on kubernetes/ yields exactly 3 components."""
    inv = build_inventory(K8S_DIR)
    node_ids = {c.node_id for c in inv.components}
    assert node_ids == {
        "component:poc-app/frontend",
        "component:poc-app/backend",
        "component:poc-app/database",
    }


# ---------------------------------------------------------------------------
# node_id format and namespace
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_component_node_id_format() -> None:
    """node_id must follow 'component:<namespace>/<app>' format."""
    inv = build_inventory(K8S_DIR)
    for comp in inv.components:
        assert comp.node_id.startswith("component:poc-app/"), comp.node_id
        assert comp.node_id.count("/") == 1
        assert comp.node_id.count(":") == 1


@pytest.mark.unit
def test_component_namespace_is_poc_app() -> None:
    """All repo components are in the poc-app namespace."""
    inv = build_inventory(K8S_DIR)
    for comp in inv.components:
        assert comp.namespace == "poc-app"


# ---------------------------------------------------------------------------
# Labels (from pod-template)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_labels() -> None:
    """backend labels contain app=backend and tier=application."""
    inv = build_inventory(K8S_DIR)
    backend = next(c for c in inv.components if c.node_id == "component:poc-app/backend")
    assert backend.labels.get("app") == "backend"
    assert backend.labels.get("tier") == "application"


@pytest.mark.unit
def test_database_labels() -> None:
    """database labels contain app=database and tier=data."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert db.labels.get("app") == "database"
    assert db.labels.get("tier") == "data"


@pytest.mark.unit
def test_frontend_labels() -> None:
    """frontend labels contain app=frontend and tier=presentation."""
    inv = build_inventory(K8S_DIR)
    fe = next(c for c in inv.components if c.node_id == "component:poc-app/frontend")
    assert fe.labels.get("app") == "frontend"
    assert fe.labels.get("tier") == "presentation"


# ---------------------------------------------------------------------------
# Ports (from container ports in Deployment)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_port_8000() -> None:
    inv = build_inventory(K8S_DIR)
    backend = next(c for c in inv.components if c.node_id == "component:poc-app/backend")
    assert 8000 in backend.ports


@pytest.mark.unit
def test_frontend_port_80() -> None:
    inv = build_inventory(K8S_DIR)
    fe = next(c for c in inv.components if c.node_id == "component:poc-app/frontend")
    assert 80 in fe.ports


@pytest.mark.unit
def test_database_port_5432() -> None:
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert 5432 in db.ports


# ---------------------------------------------------------------------------
# Readiness path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_readiness_path() -> None:
    """backend readiness path is /health (httpGet)."""
    inv = build_inventory(K8S_DIR)
    backend = next(c for c in inv.components if c.node_id == "component:poc-app/backend")
    assert backend.readiness_path == "/health"


@pytest.mark.unit
def test_frontend_readiness_path() -> None:
    """frontend has readinessProbe.httpGet.path=/health; inventory extracts it.

    Note: G1_bundle_full.json records readiness_path=null for frontend.
    That fixture was hand-authored by P3 with null, likely because nginx has
    no Python AST to trace.  The implementation correctly extracts the value
    from the manifest per §7.1 item 2.  See test_g1_fixture_inventory_*
    for the golden comparison; readiness_path is noted as a known deviation.
    """
    inv = build_inventory(K8S_DIR)
    fe = next(c for c in inv.components if c.node_id == "component:poc-app/frontend")
    # The frontend deployment has readinessProbe.httpGet.path = /health.
    assert fe.readiness_path == "/health"


@pytest.mark.unit
def test_database_readiness_path_none() -> None:
    """database uses exec probe (pg_isready), no httpGet → readiness_path=None."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert db.readiness_path is None


# ---------------------------------------------------------------------------
# Aliases: Deployment name
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_deployment_name_alias() -> None:
    """backend-deployment is an alias for component:poc-app/backend."""
    inv = build_inventory(K8S_DIR)
    backend = next(c for c in inv.components if c.node_id == "component:poc-app/backend")
    assert "backend-deployment" in backend.aliases


@pytest.mark.unit
def test_database_deployment_name_alias() -> None:
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert "database-deployment" in db.aliases


# ---------------------------------------------------------------------------
# Aliases: Service DNS forms (acceptance criterion)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_database_service_alias_short() -> None:
    """database-service resolves to component:poc-app/database."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert "database-service" in db.aliases


@pytest.mark.unit
def test_database_service_alias_with_namespace() -> None:
    """database-service.poc-app is an alias (§7.1 acceptance criterion)."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert "database-service.poc-app" in db.aliases


@pytest.mark.unit
def test_database_service_alias_with_svc() -> None:
    """database-service.poc-app.svc is an alias."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert "database-service.poc-app.svc" in db.aliases


@pytest.mark.unit
def test_database_service_alias_fqdn() -> None:
    """database-service.poc-app.svc.cluster.local is an alias."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert "database-service.poc-app.svc.cluster.local" in db.aliases


@pytest.mark.unit
def test_backend_service_all_four_dns_forms() -> None:
    """All four DNS forms are registered for backend-service."""
    inv = build_inventory(K8S_DIR)
    backend = next(c for c in inv.components if c.node_id == "component:poc-app/backend")
    for form in [
        "backend-service",
        "backend-service.poc-app",
        "backend-service.poc-app.svc",
        "backend-service.poc-app.svc.cluster.local",
    ]:
        assert form in backend.aliases, f"Missing alias: {form}"


# ---------------------------------------------------------------------------
# Aliases: app-label short name
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_app_label_alias_database() -> None:
    """Short 'database' alias is registered."""
    inv = build_inventory(K8S_DIR)
    db = next(c for c in inv.components if c.node_id == "component:poc-app/database")
    assert "database" in db.aliases


@pytest.mark.unit
def test_app_label_alias_backend() -> None:
    inv = build_inventory(K8S_DIR)
    backend = next(c for c in inv.components if c.node_id == "component:poc-app/backend")
    assert "backend" in backend.aliases


@pytest.mark.unit
def test_app_label_alias_frontend() -> None:
    inv = build_inventory(K8S_DIR)
    fe = next(c for c in inv.components if c.node_id == "component:poc-app/frontend")
    assert "frontend" in fe.aliases


# ---------------------------------------------------------------------------
# resolve() — positive cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_short_service_name() -> None:
    """resolve('database-service') → component:poc-app/database."""
    inv = build_inventory(K8S_DIR)
    result = inv.resolve("database-service")
    assert result == "component:poc-app/database"


@pytest.mark.unit
def test_resolve_fqdn() -> None:
    """resolve(FQDN) → correct node_id."""
    inv = build_inventory(K8S_DIR)
    result = inv.resolve("database-service.poc-app.svc.cluster.local")
    assert result == "component:poc-app/database"


@pytest.mark.unit
def test_resolve_app_label_token() -> None:
    """resolve('backend') → component:poc-app/backend."""
    inv = build_inventory(K8S_DIR)
    result = inv.resolve("backend")
    assert result == "component:poc-app/backend"


@pytest.mark.unit
def test_resolve_deployment_name() -> None:
    """resolve(Deployment name) → correct node_id."""
    inv = build_inventory(K8S_DIR)
    result = inv.resolve("frontend-deployment")
    assert result == "component:poc-app/frontend"


@pytest.mark.unit
def test_resolve_namespace_qualified_service() -> None:
    """resolve('backend-service.poc-app') → component:poc-app/backend."""
    inv = build_inventory(K8S_DIR)
    assert inv.resolve("backend-service.poc-app") == "component:poc-app/backend"


# ---------------------------------------------------------------------------
# resolve() — negative / warning cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_unknown_returns_none() -> None:
    """resolve(unknown) → None."""
    inv = build_inventory(K8S_DIR)
    result = inv.resolve("nonexistent-service")
    assert result is None


@pytest.mark.unit
def test_resolve_unknown_adds_warning() -> None:
    """resolve(unknown) records a warning (§7.1 item 4)."""
    inv = build_inventory(K8S_DIR)
    before = len(inv.warnings)
    inv.resolve("totally-unknown-host")
    assert len(inv.warnings) > before
    assert any("totally-unknown-host" in w for w in inv.warnings)


@pytest.mark.unit
def test_resolve_case_insensitive() -> None:
    """resolve() is case-insensitive (DNS names are case-insensitive)."""
    inv = build_inventory(K8S_DIR)
    assert inv.resolve("Database-Service") == "component:poc-app/database"


# ---------------------------------------------------------------------------
# Alias collision handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_alias_collision_produces_warning(tmp_path: Path) -> None:
    """Two components sharing an alias → collision warning (§7.1 item 3)."""
    # Two Deployments that would both match a Service named 'shared-svc'
    # because both have app=alpha or app=beta but same svc name — we simulate
    # a collision by giving two components the same app label (which triggers
    # the duplicate-deployment guard and a warning).  The more realistic
    # collision test below uses two Services pointing at the same component.
    #
    # Simpler: put a Service in ns A and a Deployment in ns B with the same
    # app label and same service name in different namespaces — the alias
    # 'shared' would only collide if both are in the same namespace.
    # The cleanest test: create two Deployments in different namespaces with
    # the same service name via the inventory (both svc.ns1 and svc.ns2 differ,
    # so no actual collision) — instead, test the real collision path by
    # patching alias_owners in the builder output.
    #
    # Real collision: a Service whose selector matches TWO components
    # (impossible in the normal Kubernetes model but can happen in test data).
    # We achieve it by giving two Deployments the same pod-template label
    # sub-set that a Service selects.
    yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alpha-deployment
  namespace: test-ns
spec:
  template:
    metadata:
      labels:
        app: alpha
        shared-label: "yes"
    spec:
      containers:
      - name: alpha
        ports:
        - containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: beta-deployment
  namespace: test-ns
spec:
  template:
    metadata:
      labels:
        app: beta
        shared-label: "yes"
    spec:
      containers:
      - name: beta
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: shared-svc
  namespace: test-ns
spec:
  selector:
    shared-label: "yes"
  ports:
  - port: 80
"""
    _write_yaml(tmp_path, "manifests.yaml", yaml_content)
    inv = build_inventory(tmp_path)
    # Both components matched; collision on 'shared-svc' and its DNS forms.
    assert any("collision" in w.lower() for w in inv.warnings)
    assert len(inv.collision_aliases) > 0


@pytest.mark.unit
def test_alias_collision_confidence_factor() -> None:
    """collision_factor() returns 0.7 for a colliding alias."""
    # Build a trivial inventory with known collision.
    comp_a = ComponentInfo(
        node_id="component:ns/a",
        labels={"app": "a"},
        aliases=["shared-svc", "a"],
        namespace="ns",
    )
    comp_b = ComponentInfo(
        node_id="component:ns/b",
        labels={"app": "b"},
        aliases=["shared-svc", "b"],
        namespace="ns",
    )
    inv = ComponentInventory(
        components=[comp_a, comp_b],
        warnings=["collision: shared-svc"],
        collision_aliases={"shared-svc"},
    )
    assert inv.collision_factor("shared-svc") == _COLLISION_CONFIDENCE_FACTOR
    assert inv.collision_factor("shared-svc") == 0.7
    assert inv.collision_factor("a") == 1.0


# ---------------------------------------------------------------------------
# Multi-document YAML
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_multidoc_yaml_loads_both_docs(tmp_path: Path) -> None:
    """Multi-document YAML (separated by ---) loads all documents."""
    yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: svc-a-deployment
  namespace: test-ns
spec:
  template:
    metadata:
      labels:
        app: svc-a
    spec:
      containers:
      - name: svc-a
        ports:
        - containerPort: 9000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: svc-b-deployment
  namespace: test-ns
spec:
  template:
    metadata:
      labels:
        app: svc-b
    spec:
      containers:
      - name: svc-b
        ports:
        - containerPort: 9001
"""
    _write_yaml(tmp_path, "multi.yaml", yaml_content)
    inv = build_inventory(tmp_path)
    node_ids = {c.node_id for c in inv.components}
    assert "component:test-ns/svc-a" in node_ids
    assert "component:test-ns/svc-b" in node_ids


# ---------------------------------------------------------------------------
# Edge cases and robustness
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_empty_manifests_dir_returns_empty_inventory(tmp_path: Path) -> None:
    """An empty directory yields an empty inventory without crashing."""
    inv = build_inventory(tmp_path)
    assert inv.components == []
    assert inv.warnings == []


@pytest.mark.unit
def test_namespace_resource_not_a_component(tmp_path: Path) -> None:
    """A Namespace document is not mistaken for a component."""
    yaml_content = """
apiVersion: v1
kind: Namespace
metadata:
  name: poc-app
  labels:
    name: poc-app
"""
    _write_yaml(tmp_path, "ns.yaml", yaml_content)
    inv = build_inventory(tmp_path)
    assert inv.components == []


@pytest.mark.unit
def test_service_without_matching_deployment_ignored(tmp_path: Path) -> None:
    """A Service with no matching Deployment does not create a phantom component."""
    yaml_content = """
apiVersion: v1
kind: Service
metadata:
  name: orphan-service
  namespace: test-ns
spec:
  selector:
    app: ghost
  ports:
  - port: 80
"""
    _write_yaml(tmp_path, "orphan.yaml", yaml_content)
    inv = build_inventory(tmp_path)
    assert inv.components == []


@pytest.mark.unit
def test_deployment_without_app_label_ignored(tmp_path: Path) -> None:
    """A Deployment with no 'app' pod-template label is skipped."""
    yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: no-app-label
  namespace: test-ns
spec:
  template:
    metadata:
      labels:
        name: something
    spec:
      containers:
      - name: x
"""
    _write_yaml(tmp_path, "nolabel.yaml", yaml_content)
    inv = build_inventory(tmp_path)
    assert inv.components == []


@pytest.mark.unit
def test_output_is_deterministically_sorted(tmp_path: Path) -> None:
    """build_inventory returns components sorted by node_id."""
    # Run twice; order must be identical.
    inv1 = build_inventory(K8S_DIR)
    inv2 = build_inventory(K8S_DIR)
    assert [c.node_id for c in inv1.components] == [c.node_id for c in inv2.components]
    # Also confirm they are lexicographically sorted.
    ids = [c.node_id for c in inv1.components]
    assert ids == sorted(ids)


@pytest.mark.unit
def test_no_duplicate_aliases_per_component() -> None:
    """Each component's alias list has no duplicates."""
    inv = build_inventory(K8S_DIR)
    for comp in inv.components:
        assert len(comp.aliases) == len(set(comp.aliases)), (
            f"Duplicate aliases on {comp.node_id}: {comp.aliases}"
        )


@pytest.mark.unit
def test_load_manifests_skips_non_kind_documents(tmp_path: Path) -> None:
    """Documents without a 'kind' field are silently ignored."""
    yaml_content = """
just_a_key: value
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ok-deployment
  namespace: ns
spec:
  template:
    metadata:
      labels:
        app: ok
    spec:
      containers:
      - name: ok
"""
    _write_yaml(tmp_path, "mixed.yaml", yaml_content)
    docs = load_manifests(tmp_path)
    # Only the Deployment is returned.
    assert all("kind" in d for d in docs)
    assert any(d.get("kind") == "Deployment" for d in docs)


# ---------------------------------------------------------------------------
# Golden fixture contract test (G1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_g1_fixture_inventory_node_ids_match() -> None:
    """build_inventory node_ids must match G1_bundle_full.json inventory."""
    with open(FIXTURES_DIR / "G1_bundle_full.json", encoding="utf-8") as fh:
        g1 = json.load(fh)
    expected_ids = {c["node_id"] for c in g1["inventory"]}
    inv = build_inventory(K8S_DIR)
    actual_ids = {c.node_id for c in inv.components}
    assert actual_ids == expected_ids


@pytest.mark.unit
def test_g1_fixture_inventory_aliases_match() -> None:
    """build_inventory aliases must match G1_bundle_full.json for each component."""
    with open(FIXTURES_DIR / "G1_bundle_full.json", encoding="utf-8") as fh:
        g1 = json.load(fh)
    inv = build_inventory(K8S_DIR)
    actual_by_id = {c.node_id: c for c in inv.components}
    for expected in g1["inventory"]:
        node_id = expected["node_id"]
        assert node_id in actual_by_id, f"Missing component: {node_id}"
        actual_aliases = set(actual_by_id[node_id].aliases)
        expected_aliases = set(expected["aliases"])
        assert actual_aliases == expected_aliases, (
            f"Alias mismatch for {node_id}:\n"
            f"  expected: {sorted(expected_aliases)}\n"
            f"  actual:   {sorted(actual_aliases)}"
        )


@pytest.mark.unit
def test_g1_fixture_inventory_ports_match() -> None:
    """build_inventory ports must match G1_bundle_full.json."""
    with open(FIXTURES_DIR / "G1_bundle_full.json", encoding="utf-8") as fh:
        g1 = json.load(fh)
    inv = build_inventory(K8S_DIR)
    actual_by_id = {c.node_id: c for c in inv.components}
    for expected in g1["inventory"]:
        node_id = expected["node_id"]
        assert sorted(actual_by_id[node_id].ports) == sorted(expected["ports"]), (
            f"Port mismatch for {node_id}"
        )


@pytest.mark.unit
def test_g1_fixture_inventory_readiness_paths_match() -> None:
    """build_inventory readiness_path matches G1_bundle_full.json where unambiguous.

    Known deviation: G1 records readiness_path=null for frontend, but the actual
    frontend/deployment.yaml has readinessProbe.httpGet.path=/health.
    The implementation follows §7.1 item 2 (extract from manifest); the G1
    fixture was hand-authored with null. This deviation is documented here
    and in docs/p2/README.md. backend and database must match exactly.
    """
    with open(FIXTURES_DIR / "G1_bundle_full.json", encoding="utf-8") as fh:
        g1 = json.load(fh)
    inv = build_inventory(K8S_DIR)
    actual_by_id = {c.node_id: c for c in inv.components}

    # Known deviation components — skip strict check.
    known_deviations = {"component:poc-app/frontend"}

    for expected in g1["inventory"]:
        node_id = expected["node_id"]
        if node_id in known_deviations:
            continue
        assert actual_by_id[node_id].readiness_path == expected.get("readiness_path"), (
            f"readiness_path mismatch for {node_id}"
        )


@pytest.mark.unit
def test_g1_fixture_inventory_labels_match() -> None:
    """build_inventory labels must match G1_bundle_full.json."""
    with open(FIXTURES_DIR / "G1_bundle_full.json", encoding="utf-8") as fh:
        g1 = json.load(fh)
    inv = build_inventory(K8S_DIR)
    actual_by_id = {c.node_id: c for c in inv.components}
    for expected in g1["inventory"]:
        node_id = expected["node_id"]
        assert actual_by_id[node_id].labels == expected.get("labels", {}), (
            f"Labels mismatch for {node_id}"
        )
