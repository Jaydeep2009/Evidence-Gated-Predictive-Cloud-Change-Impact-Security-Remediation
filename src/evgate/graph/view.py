"""Dependency view and analysis for the evidence graph.

Provides higher-level views of the graph focused on dependency relationships.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from evgate.contracts import NodeId, Relationship

# Relationships that indicate dependency evidence
DEPENDENCY_RELATIONSHIPS = {
    Relationship.DEPENDS_ON,
    Relationship.CALLS,
    Relationship.CONNECTS_TO,
    Relationship.READINESS_COUPLED,
}


@dataclass
class DependencyRecord:
    """Record of dependency evidence between two components.

    Attributes:
        belief: Aggregated belief that the dependency exists (0.0-1.0)
        conf_by_type: Confidence scores by evidence type
        relationships: List of relationships found between the components
        has_conflict: Whether conflicting evidence was found
        already_failing: Whether FAILED_TO_CONNECT evidence exists in baseline
        evidence_ids: All evidence IDs supporting this dependency
    """

    belief: float
    conf_by_type: dict[str, float]
    relationships: list[Relationship]
    has_conflict: bool
    already_failing: bool
    evidence_ids: list[str]


def dependency_view(
    G: nx.MultiDiGraph,
) -> dict[tuple[NodeId, NodeId], DependencyRecord]:
    """Create a dependency-focused view of the evidence graph.

    Aggregates all dependency-indicating relationships between component pairs
    into a single DependencyRecord per pair.

    Args:
        G: Evidence graph from build_graph()

    Returns:
        Dictionary mapping (source, destination) pairs to DependencyRecords.
        Only includes pairs with at least one dependency relationship.

    Note:
        FAILED_TO_CONNECT in baseline indicates the dependency is already broken.
        This lowers belief and sets already_failing flag.
    """
    dependencies: dict[tuple[NodeId, NodeId], dict[str, Any]] = {}

    for src, dst, _key, data in G.edges(keys=True, data=True):
        relationship = data.get("relationship")
        if relationship is None:
            continue

        pair = (src, dst)

        # Initialize record for this pair if not exists
        if pair not in dependencies:
            dependencies[pair] = {
                "relationships": [],
                "conf_by_type_all": {},
                "has_conflict": False,
                "already_failing": False,
                "evidence_ids": [],
            }

        dep = dependencies[pair]

        # Check if this is a dependency relationship
        if relationship in DEPENDENCY_RELATIONSHIPS:
            dep["relationships"].append(relationship)
            dep["has_conflict"] = dep["has_conflict"] or data.get("conflicted", False)
            dep["evidence_ids"].extend(data.get("evidence_ids", []))

            # Merge conf_by_type
            for etype, conf in data.get("conf_by_type", {}).items():
                if etype not in dep["conf_by_type_all"]:
                    dep["conf_by_type_all"][etype] = []
                dep["conf_by_type_all"][etype].append(conf)

        # Check for FAILED_TO_CONNECT
        if relationship == Relationship.FAILED_TO_CONNECT:
            dep["already_failing"] = True
            # FAILED_TO_CONNECT refutes the dependency
            # We track this separately for belief computation

    # Compute belief for each pair and create DependencyRecords
    result: dict[tuple[NodeId, NodeId], DependencyRecord] = {}

    for pair, dep in dependencies.items():
        if not dep["relationships"]:
            # No dependency relationships found
            continue

        # Aggregate confidence by type using noisy-OR
        conf_by_type = {}
        for etype, confs in dep["conf_by_type_all"].items():
            conf_by_type[etype] = 1.0 - _product(1.0 - c for c in confs)

        # Simple belief: average of confidence by type
        # (More sophisticated belief computation happens in prediction/belief.py)
        if conf_by_type:
            belief = sum(conf_by_type.values()) / len(conf_by_type)
        else:
            belief = 0.0

        # Lower belief if already failing
        if dep["already_failing"]:
            belief *= 0.5

        result[pair] = DependencyRecord(
            belief=belief,
            conf_by_type=conf_by_type,
            relationships=dep["relationships"],
            has_conflict=dep["has_conflict"],
            already_failing=dep["already_failing"],
            evidence_ids=dep["evidence_ids"],
        )

    return result


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
