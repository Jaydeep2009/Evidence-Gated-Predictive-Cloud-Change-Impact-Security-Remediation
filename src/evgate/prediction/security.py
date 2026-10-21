"""Security impact analysis for proposed changes.

Implements §8.3 security impact calculation:
- Path exposure analysis (attack surface)
- Permission weight analysis (privilege scope)
- Independent of operational impact
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import networkx as nx

from evgate.contracts import ChangeSpec, PathEffect, PermissionEffect


class SecurityImpact(StrEnum):
    """Security impact classification for a change."""

    IMPROVES = "improves"
    NEUTRAL = "neutral"
    DEGRADES = "degrades"


def is_sensitive_component(graph: nx.MultiDiGraph, component: str) -> bool:
    """Check if a component is marked as sensitive.

    Per §8.3: Sensitive = label tier=data OR holds credentials

    Args:
        graph: Dependency graph with node attributes
        component: Component identifier

    Returns:
        True if component is sensitive
    """
    if not graph.has_node(component):
        return False

    node_data = graph.nodes[component]
    labels = node_data.get("labels", {})

    # Check tier=data label
    if labels.get("tier") == "data":
        return True

    # Check if component holds credentials (could be in tags/metadata)
    tags = node_data.get("tags", [])
    if "credentials" in tags or "secrets" in tags:
        return True

    return False


def compute_path_exposure(
    graph: nx.MultiDiGraph,
    path_effects: list[PathEffect],
    state: str,
) -> int:
    """Compute path exposure for sensitive components.

    Per §8.3:
    exposure = Σ over sensitive components c of
               #(src,port) pairs that can reach c

    Args:
        graph: Dependency graph
        path_effects: List of path effects from change
        state: "before" or "after" - which state to compute

    Returns:
        Exposure count (number of (src,port) pairs reaching sensitive components)
    """
    exposure = 0

    # Find all sensitive components
    sensitive = {node for node in graph.nodes() if is_sensitive_component(graph, node)}

    if not sensitive:
        return 0

    # For each sensitive component, count incoming paths
    for component in sensitive:
        # Track unique (src, port) pairs
        incoming_pairs: set[tuple[str, int | None]] = set()

        # Check what can reach this component based on effects
        for effect in path_effects:
            if effect.dst == component:
                # Check if this path is allowed in the given state
                if state == "before":
                    allowed = effect.before == "allowed"
                elif state == "after":
                    allowed = effect.after == "allowed"
                else:
                    continue

                if allowed:
                    # Add this (src, port) pair
                    incoming_pairs.add((effect.src, effect.port))

        exposure += len(incoming_pairs)

    return exposure


def compute_exposure_delta(
    exposure_before: int,
    exposure_after: int,
) -> tuple[float, SecurityImpact]:
    """Compute exposure delta and classify security impact.

    Per §8.3:
    delta = (exposure_after - exposure_before) / max(1, exposure_before)
    - improves if delta ≤ -0.1
    - degrades if delta ≥ +0.1
    - neutral otherwise

    Args:
        exposure_before: Exposure count before change
        exposure_after: Exposure count after change

    Returns:
        Tuple of (delta, SecurityImpact)

    Example:
        Before: 10 pairs can reach database
        After: 2 pairs can reach database
        delta = (2-10)/10 = -0.8 → IMPROVES
    """
    # Prevent division by zero
    denominator = max(1, exposure_before)
    delta = (exposure_after - exposure_before) / denominator

    # Classify based on thresholds
    if delta <= -0.1:
        impact = SecurityImpact.IMPROVES
    elif delta >= 0.1:
        impact = SecurityImpact.DEGRADES
    else:
        impact = SecurityImpact.NEUTRAL

    return delta, impact


def get_permission_weight(
    verb: str,
    resource: str,
    api_group: str = "",
) -> int:
    """Get security weight for a permission.

    Per §8.3 weights:
    - wildcard '*' = 5
    - secrets / pods/exec / escalate|bind|impersonate = 4
    - write verbs on workloads = 3
    - list/watch on secrets = 3
    - other write = 2
    - read = 1

    Args:
        verb: Kubernetes verb (get, list, create, delete, *, etc.)
        resource: Kubernetes resource (pods, secrets, configmaps, etc.)
        api_group: API group (optional)

    Returns:
        Weight score (1-5)
    """
    # Wildcard gets highest weight
    if verb == "*" or resource == "*":
        return 5

    # High-risk resources/verbs
    if resource == "secrets":
        if verb in ("list", "watch"):
            return 3
        return 4  # Any other verb on secrets is high-risk

    # Pod exec and privilege escalation verbs
    if resource == "pods/exec" or verb in ("escalate", "bind", "impersonate"):
        return 4

    # Write verbs on workload resources
    workload_resources = {"pods", "deployments", "statefulsets", "daemonsets", "jobs"}
    write_verbs = {"create", "update", "patch", "delete", "deletecollection"}

    if resource in workload_resources and verb in write_verbs:
        return 3

    # Other write verbs
    if verb in write_verbs:
        return 2

    # Read verbs (get, list, watch)
    read_verbs = {"get", "list", "watch"}
    if verb in read_verbs:
        return 1

    # Default for unknown verbs
    return 1


def compute_permission_delta(
    permission_effects: list[PermissionEffect],
) -> tuple[float, SecurityImpact]:
    """Compute permission delta from weighted changes.

    Per §8.3:
    delta = normalized change in Σ weights of granted permissions per principal

    Args:
        permission_effects: List of permission effects

    Returns:
        Tuple of (delta, SecurityImpact)

    Example:
        Before: principal has 'get pods' (weight 1)
        After: principal has 'get pods' + '* secrets' (weight 1 + 5 = 6)
        delta = (6-1)/1 = 5.0 → DEGRADES
    """
    if not permission_effects:
        return 0.0, SecurityImpact.NEUTRAL

    # Track weights per principal
    weights_before: dict[str, int] = {}
    weights_after: dict[str, int] = {}

    for effect in permission_effects:
        principal = effect.principal
        weight = get_permission_weight(effect.verb, effect.resource, effect.api_group)

        # Initialize if needed
        if principal not in weights_before:
            weights_before[principal] = 0
            weights_after[principal] = 0

        # Add weight based on state
        if effect.before == "granted":
            weights_before[principal] += weight
        if effect.after == "granted":
            weights_after[principal] += weight

    # Compute total delta across all principals
    total_before = sum(weights_before.values())
    total_after = sum(weights_after.values())

    # Normalize
    denominator = max(1, total_before)
    delta = (total_after - total_before) / denominator

    # Classify
    if delta <= -0.1:
        impact = SecurityImpact.IMPROVES
    elif delta >= 0.1:
        impact = SecurityImpact.DEGRADES
    else:
        impact = SecurityImpact.NEUTRAL

    return delta, impact


def compute_security_impact(
    change: ChangeSpec,
    graph: nx.MultiDiGraph,
) -> tuple[SecurityImpact, float, dict[str, Any]]:
    """Compute overall security impact of a change.

    Per §8.3: Security impact is independent of operational impact.
    A change can improve security AND be operationally risky.

    Args:
        change: Change specification
        graph: Dependency graph with component metadata

    Returns:
        Tuple of (SecurityImpact, delta, details_dict)

    Example (M2 scenario):
        NetworkPolicy blocks backend→database
        → Reduces exposure to database
        → SecurityImpact.IMPROVES, delta=-0.8
    """
    # Separate path and permission effects
    path_effects = [e for e in change.effects if e.kind == "path"]
    permission_effects = [e for e in change.effects if e.kind == "permission"]

    details: dict[str, Any] = {
        "path_effects_count": len(path_effects),
        "permission_effects_count": len(permission_effects),
    }

    # Compute path impact if any
    path_delta = 0.0
    path_impact = SecurityImpact.NEUTRAL

    if path_effects:
        exposure_before = compute_path_exposure(graph, path_effects, "before")
        exposure_after = compute_path_exposure(graph, path_effects, "after")
        path_delta, path_impact = compute_exposure_delta(
            exposure_before, exposure_after
        )

        details["exposure_before"] = exposure_before
        details["exposure_after"] = exposure_after
        details["path_delta"] = path_delta
        details["path_impact"] = path_impact.value

    # Compute permission impact if any
    permission_delta = 0.0
    permission_impact = SecurityImpact.NEUTRAL

    if permission_effects:
        permission_delta, permission_impact = compute_permission_delta(
            permission_effects
        )

        details["permission_delta"] = permission_delta
        details["permission_impact"] = permission_impact.value

    # Overall impact: worst of the two
    # Rationale: If either aspect degrades, the change degrades security
    if (
        path_impact == SecurityImpact.DEGRADES
        or permission_impact == SecurityImpact.DEGRADES
    ):
        overall_impact = SecurityImpact.DEGRADES
        # Use the larger degradation delta
        overall_delta = max(path_delta, permission_delta)
    elif (
        path_impact == SecurityImpact.IMPROVES
        or permission_impact == SecurityImpact.IMPROVES
    ):
        # If one improves and the other is neutral, overall improves
        # If both improve, definitely improves
        overall_impact = SecurityImpact.IMPROVES
        # Use the more negative delta (larger improvement)
        overall_delta = min(path_delta, permission_delta)
    else:
        overall_impact = SecurityImpact.NEUTRAL
        overall_delta = 0.0

    details["overall_delta"] = overall_delta

    return overall_impact, overall_delta, details
