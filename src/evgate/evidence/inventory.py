"""Component inventory and entity resolution for the evgate system.

Implements P2-01: loads multi-document Kubernetes YAML, identifies logical
components from Deployment pod-template labels, builds deterministic
ComponentInfo objects with aliases, and resolves DNS/service/app tokens to
canonical component NodeIds.

Specification: implementation.md §7.1
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import yaml

from evgate.contracts.bundle import ComponentInfo
from evgate.contracts.vocab import NodeId

logger = logging.getLogger(__name__)

# Resource kinds consumed by the inventory loader (§7.1 item 1).
# Others are loaded but not used for component identification here.
_INVENTORY_KINDS = frozenset(
    {
        "Namespace",
        "Deployment",
        "Service",
        "NetworkPolicy",
        "ServiceAccount",
        "Role",
        "ClusterRole",
        "RoleBinding",
        "ClusterRoleBinding",
        "ConfigMap",
    }
)

# Confidence multiplier applied when an alias is claimed by more than one
# component (§7.1 item 3 – alias collision).
_COLLISION_CONFIDENCE_FACTOR = 0.7


def _iter_yaml_docs(path: Path) -> Iterator[dict]:
    """Yield every non-null document from a (possibly multi-document) YAML file."""
    with open(path, encoding="utf-8") as fh:
        for doc in yaml.safe_load_all(fh):
            if doc is not None:
                yield doc


def load_manifests(manifests_dir: Path | str) -> list[dict]:
    """Load all Kubernetes YAML documents under *manifests_dir* (recursive).

    Returns a flat list of parsed document dicts.  Non-YAML files and
    documents without a ``kind`` field are skipped silently.

    Args:
        manifests_dir: Root directory containing ``*.yaml`` / ``*.yml`` files.

    Returns:
        List of raw manifest dicts.
    """
    root = Path(manifests_dir)
    docs: list[dict] = []
    for yaml_file in sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml")):
        try:
            for doc in _iter_yaml_docs(yaml_file):
                if isinstance(doc, dict) and "kind" in doc:
                    docs.append(doc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not parse %s: %s", yaml_file, exc)
    return docs


class ComponentInventory:
    """Resolved inventory of logical components derived from Kubernetes manifests.

    Build via :func:`build_inventory`.  The primary entry point for all
    extractors is :meth:`resolve`.

    Attributes:
        components: Canonical :class:`ComponentInfo` list, one per logical
            component (i.e. per distinct ``app`` label in Deployment
            pod-template labels).
        warnings: Accumulated warning strings (alias collisions, unresolved
            tokens, etc.).
        collision_aliases: Set of aliases claimed by more than one component;
            callers should multiply their confidence by
            ``_COLLISION_CONFIDENCE_FACTOR`` when using these.
    """

    def __init__(
        self,
        components: list[ComponentInfo],
        warnings: list[str],
        collision_aliases: set[str],
    ) -> None:
        self.components: list[ComponentInfo] = components
        self.warnings: list[str] = warnings
        self.collision_aliases: set[str] = collision_aliases

        # Build the alias → node_id lookup table.
        # Keys are lower-cased for case-insensitive resolution.
        self._alias_map: dict[str, NodeId] = {}
        for comp in components:
            for alias in comp.aliases:
                self._alias_map[alias.lower()] = comp.node_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, token: str) -> NodeId | None:
        """Resolve an alias or app-label token to a canonical component NodeId.

        Returns ``None`` and records a warning if the token cannot be matched.
        Unresolved tokens must *not* create fabricated dependency edges (§7.1
        item 4).

        Args:
            token: A DNS name, service name, app label, or any registered alias.

        Returns:
            The ``component:<namespace>/<name>`` NodeId, or ``None``.
        """
        result = self._alias_map.get(token.lower())
        if result is None:
            warning = f"Unresolved alias token: '{token}'"
            self.warnings.append(warning)
            logger.warning(warning)
        return result

    def collision_factor(self, alias: str) -> float:
        """Return the confidence factor for *alias*.

        Returns ``_COLLISION_CONFIDENCE_FACTOR`` (0.7) if the alias is shared
        by multiple components, otherwise 1.0.
        """
        return (
            _COLLISION_CONFIDENCE_FACTOR
            if alias.lower() in {a.lower() for a in self.collision_aliases}
            else 1.0
        )

    def get_component(self, node_id: NodeId) -> ComponentInfo | None:
        """Return the :class:`ComponentInfo` for *node_id*, or ``None``."""
        for comp in self.components:
            if comp.node_id == node_id:
                return comp
        return None


def build_inventory(
    manifests_dir: Path | str,
    extra_docs: list[dict] | None = None,
) -> ComponentInventory:
    """Build a :class:`ComponentInventory` from Kubernetes manifests.

    Algorithm (§7.1):

    1. Load every ``*.yaml``/``*.yml`` under *manifests_dir* (multi-doc
       supported).
    2. A **component** = distinct ``spec.template.metadata.labels.app`` value
       in a Deployment.  ``node_id = component:<namespace>/<app>``.
    3. **Aliases** registered for each component:

       - The Deployment's ``metadata.name``.
       - For each Service whose ``spec.selector`` is a subset of the
         component's pod-template labels: four DNS forms
         ``svc``, ``svc.ns``, ``svc.ns.svc``, ``svc.ns.svc.cluster.local``
         plus just ``svc`` (short name).
       - The ``app`` label value itself.

    4. Alias collisions → both components get a warning; the alias is added to
       ``collision_aliases`` so callers can apply the 0.7 confidence factor.

    Args:
        manifests_dir: Root directory of Kubernetes manifests.
        extra_docs: Optional additional manifest dicts to consider (e.g.
            loaded from overlays), already parsed.

    Returns:
        A populated :class:`ComponentInventory`.
    """
    docs = load_manifests(Path(manifests_dir))
    if extra_docs:
        docs.extend(extra_docs)

    warnings: list[str] = []

    # ---- Step 1: collect Deployments -----------------------------------
    # Each Deployment whose pod-template has an "app" label becomes one
    # logical component.
    deployments = [d for d in docs if d.get("kind") == "Deployment"]

    # Map  app_label → list[(namespace, deployment_name, pod_template_labels,
    #                         container_ports, readiness_path)]
    # There may be multiple Deployments with the same app label across
    # different namespaces.
    # (namespace, app_label) tuple used as the key for each component.
    _CompKey = tuple[str, str]
    comp_data: dict[_CompKey, dict] = {}

    for dep in deployments:
        meta = dep.get("metadata", {})
        ns = meta.get("namespace", "default")
        dep_name = meta.get("name", "")
        spec = dep.get("spec", {})
        template = spec.get("template", {})
        tmpl_meta = template.get("metadata", {})
        pod_labels: dict[str, str] = tmpl_meta.get("labels", {})
        app_label = pod_labels.get("app", "")
        if not app_label:
            continue

        key: _CompKey = (ns, app_label)
        if key in comp_data:
            # Duplicate Deployment for same (ns, app) — warn but keep first.
            warnings.append(
                f"Duplicate Deployment app='{app_label}' in namespace '{ns}'; "
                f"keeping first, ignoring '{dep_name}'."
            )
            continue

        # Collect container ports.
        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        ports: list[int] = []
        for container in containers:
            for port_entry in container.get("ports", []):
                cp = port_entry.get("containerPort")
                if cp is not None:
                    ports.append(int(cp))

        # Readiness path (httpGet only).
        readiness_path: str | None = None
        for container in containers:
            rp = container.get("readinessProbe", {})
            http_get = rp.get("httpGet", {})
            if http_get.get("path"):
                readiness_path = http_get["path"]
                break

        comp_data[key] = {
            "namespace": ns,
            "app_label": app_label,
            "deployment_name": dep_name,
            "pod_labels": pod_labels,
            "ports": ports,
            "readiness_path": readiness_path,
        }

    # ---- Step 2: match Services to components --------------------------
    services = [d for d in docs if d.get("kind") == "Service"]

    # service_aliases: _CompKey → list[str]
    service_aliases: dict[_CompKey, list[str]] = {k: [] for k in comp_data}

    for svc in services:
        meta = svc.get("metadata", {})
        svc_ns = meta.get("namespace", "default")
        svc_name = meta.get("name", "")
        selector: dict[str, str] = svc.get("spec", {}).get("selector", {})
        if not selector:
            continue

        # A Service matches a component when its selector is a subset of the
        # component's pod-template labels (§7.1 item 3).
        for key, data in comp_data.items():
            ns, _app = key
            if ns != svc_ns:
                continue
            pod_labels = data["pod_labels"]
            if all(pod_labels.get(k) == v for k, v in selector.items()):
                # Build the four DNS forms.
                dns_forms = [
                    svc_name,
                    f"{svc_name}.{svc_ns}",
                    f"{svc_name}.{svc_ns}.svc",
                    f"{svc_name}.{svc_ns}.svc.cluster.local",
                ]
                service_aliases[key].extend(dns_forms)

    # ---- Step 3: assemble ComponentInfo and detect collisions ----------
    # alias → list[_CompKey]  (to detect collisions)
    alias_owners: dict[str, list[_CompKey]] = {}

    raw_components: dict[_CompKey, ComponentInfo] = {}
    for key, data in comp_data.items():
        ns, app_label = key
        node_id: NodeId = f"component:{ns}/{app_label}"

        aliases: list[str] = []
        # Deployment name alias.
        aliases.append(data["deployment_name"])
        # Service DNS aliases.
        aliases.extend(service_aliases.get(key, []))
        # Short app-label alias.
        if app_label not in aliases:
            aliases.append(app_label)

        # Deduplicate while preserving order.
        seen: set[str] = set()
        deduped: list[str] = []
        for a in aliases:
            if a not in seen:
                seen.add(a)
                deduped.append(a)

        for alias in deduped:
            alias_owners.setdefault(alias.lower(), []).append(key)

        raw_components[key] = ComponentInfo(
            node_id=node_id,
            labels=data["pod_labels"],
            aliases=deduped,
            namespace=ns,
            ports=sorted(set(data["ports"])),
            readiness_path=data["readiness_path"],
        )

    # Detect collisions.
    collision_aliases: set[str] = set()
    for alias_lower, owners in alias_owners.items():
        if len(owners) > 1:
            collision_aliases.add(alias_lower)
            owner_ids = [f"component:{ns}/{app}" for ns, app in owners]
            msg = (
                f"Alias collision: '{alias_lower}' is claimed by "
                f"{owner_ids}. Confidence reduced to "
                f"{_COLLISION_CONFIDENCE_FACTOR} for evidence using this alias."
            )
            warnings.append(msg)
            logger.warning(msg)

    # Sort components deterministically by node_id for reproducibility (§10).
    sorted_components = sorted(raw_components.values(), key=lambda c: c.node_id)

    return ComponentInventory(
        components=sorted_components,
        warnings=warnings,
        collision_aliases=collision_aliases,
    )
