"""Graph builder for evidence-gated system.

Builds a unified evidence/dependency graph from evidence bundles with support
for evidence type masking (infrastructure, application, runtime).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import networkx as nx

from evgate.contracts import EvidenceBundle, EvidenceType, NodeId, Relationship


def build_graph(
    bundle: EvidenceBundle, mask: set[EvidenceType] | None = None
) -> nx.MultiDiGraph:
    """Build a unified evidence/dependency graph from an evidence bundle.

    Creates one edge per (subject, object, relationship) triple, aggregating
    evidence of that relationship. Nodes are created from inventory plus all
    subject/object node_ids in evidence.

    Args:
        bundle: Evidence bundle containing inventory and evidence items
        mask: Optional set of evidence types to include. If None, includes all.
              Common masks: {infrastructure}, {infrastructure, application},
              {infrastructure, runtime}, {infrastructure, application, runtime}

    Returns:
        NetworkX MultiDiGraph with:
        - Nodes: node_id, kind, namespace, labels attrs
        - Edges: keyed by relationship, with evidence_ids, by_type,
                 conf_by_type, polarity_counts, conflicted, snapshot_id, sources

    The graph uses MultiDiGraph to support multiple edge types between nodes
    (e.g., both DEPENDS_ON and READINESS_COUPLED).
    """
    if mask is None:
        mask = {
            EvidenceType.INFRASTRUCTURE,
            EvidenceType.APPLICATION,
            EvidenceType.RUNTIME,
        }

    G = nx.MultiDiGraph()

    # Add nodes from inventory
    for comp in bundle.inventory:
        _add_node(G, comp.node_id, comp.namespace, comp.labels or {})

    # Filter evidence by mask
    filtered_evidence = [e for e in bundle.evidence if e.evidence_type in mask]

    # Group evidence by (subject, object, relationship)
    edges: dict[tuple[NodeId, NodeId, Relationship], list[Any]] = defaultdict(list)
    for evidence in filtered_evidence:
        key = (evidence.subject, evidence.object, evidence.relationship)
        edges[key].append(evidence)

    # Create edges with aggregated evidence
    for (subject, obj, relationship), evidence_list in edges.items():
        # Ensure nodes exist (some may not be in inventory)
        if subject not in G:
            _add_node(G, subject, namespace=None, labels={})
        if obj not in G:
            _add_node(G, obj, namespace=None, labels={})

        # Aggregate evidence by type
        by_type: dict[str, list[str]] = defaultdict(list)
        conf_by_type: dict[str, list[float]] = defaultdict(list)
        polarity_counts: dict[str, int] = defaultdict(int)
        sources: list[str] = []

        for e in evidence_list:
            etype = e.evidence_type.value
            by_type[etype].append(e.evidence_id)
            conf_by_type[etype].append(e.confidence)
            polarity_counts[e.polarity] += 1
            if e.source not in sources:
                sources.append(e.source)

        # Compute noisy-OR confidence per type
        conf_by_type_aggregated = {}
        for etype, confs in conf_by_type.items():
            # Noisy-OR: 1 - Π(1 - c_i)
            conf_by_type_aggregated[etype] = 1.0 - _product(1.0 - c for c in confs)

        # Check for conflicts (same claim, opposite polarity)
        conflicted = (
            polarity_counts.get("supports", 0) > 0
            and polarity_counts.get("refutes", 0) > 0
        )

        # Add edge with aggregated attributes
        G.add_edge(
            subject,
            obj,
            key=relationship.value,
            evidence_ids=[e.evidence_id for e in evidence_list],
            by_type=dict(by_type),
            conf_by_type=conf_by_type_aggregated,
            polarity_counts=dict(polarity_counts),
            conflicted=conflicted,
            snapshot_id=bundle.snapshot_id,
            sources=sources,
            relationship=relationship,
        )

    return G


def _add_node(
    G: nx.MultiDiGraph, node_id: NodeId, namespace: str | None, labels: dict[str, str]
) -> None:
    """Add a node to the graph with standardized attributes.

    Args:
        G: Graph to add node to
        node_id: Node identifier
        namespace: Kubernetes namespace (may be None for non-k8s nodes)
        labels: Label dictionary
    """
    if node_id in G:
        return

    # Determine node kind from node_id prefix
    kind = _infer_kind(node_id)

    G.add_node(
        node_id,
        kind=kind,
        namespace=namespace,
        labels=labels,
    )


def _infer_kind(node_id: NodeId) -> str:
    """Infer node kind from node_id prefix.

    Args:
        node_id: Node identifier

    Returns:
        Kind string (component, k8s-service, config, etc.)
    """
    if ":" not in node_id:
        return "unknown"

    prefix = node_id.split(":", 1)[0]
    return prefix


def _product(values: Any) -> float:
    """Compute product of values.

    Args:
        values: Iterable of numeric values

    Returns:
        Product of all values, or 1.0 if empty
    """
    result = 1.0
    for v in values:
        result *= v
    return result
