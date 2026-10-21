"""Operational impact propagation through dependency graph.

Implements the propagation algorithm from §8.3:
1. Direct impacts from newly-denied paths
2. Readiness-coupled cascades
3. Fixpoint propagation through K8s service endpoints
"""

from __future__ import annotations

import networkx as nx

from evgate.contracts import ChangeSpec, PathEffect, PermissionEffect
from evgate.prediction.belief import compute_belief
from evgate.prediction.operational import (
    ComponentImpact,
    ImpactMechanism,
    OperationalStatus,
)


def tightens_access(effect: PathEffect | PermissionEffect) -> bool:
    """Check if an effect tightens access (denies path or removes permission).

    Args:
        effect: Change effect to check

    Returns:
        True if effect transitions from allowed/granted to denied
    """
    return (effect.before == "allowed" and effect.after == "denied") or (
        effect.before == "granted" and effect.after == "denied"
    )


def get_direct_impacts(
    change: ChangeSpec,
    graph: nx.MultiDiGraph,
    reliability: dict[str, float],
    mask: set[str],
    tau_pos: float,
) -> tuple[list[ComponentImpact], set[str]]:
    """Identify components directly impacted by newly-denied paths.

    Per §8.3:
    - For each effect that tightens access
    - Check belief(src, dst) or belief(src NEEDS_PERMISSION)
    - If belief >= tau_pos:
      * src becomes unavailable if READINESS_COUPLED, else degraded
      * dst becomes degraded (affected-as-target)

    Args:
        change: Change specification with effects
        graph: Dependency graph
        reliability: Reliability weights per evidence type
        mask: Set of evidence types to consider
        tau_pos: Positive belief threshold

    Returns:
        Tuple of (list of direct component impacts, set of not_ready components)
    """
    impacts: list[ComponentImpact] = []
    not_ready_components: set[str] = set()

    # Find effects that tighten access
    direct_effects = [e for e in change.effects if tightens_access(e)]

    for effect in direct_effects:
        # Extract src and dst based on effect type
        if effect.kind == "path":
            src = effect.src
            dst = effect.dst
        elif effect.kind == "permission":
            # For permissions: principal needs permission on resource
            src = effect.principal
            dst = f"{effect.resource}:{effect.verb}"  # Synthetic node
        else:
            continue

        # Get belief in this dependency/permission
        belief = get_belief_for_effect(graph, src, dst, reliability, mask)

        # Only high-belief paths contribute to risk
        if belief >= tau_pos:
            # Check if source is readiness-coupled to destination
            is_readiness_coupled = check_readiness_coupling(graph, src, dst)

            # Source impact
            if is_readiness_coupled:
                impacts.append(
                    ComponentImpact(
                        component=src,
                        status=OperationalStatus.UNAVAILABLE,
                        mechanism=ImpactMechanism.READINESS_COUPLED,
                        probability=belief,
                        caused_by=dst,
                        belief=belief,
                    )
                )
                not_ready_components.add(src)
            else:
                # Hard dependency without readiness coupling
                impacts.append(
                    ComponentImpact(
                        component=src,
                        status=OperationalStatus.DEGRADED,
                        mechanism=ImpactMechanism.DIRECT_PATH_BLOCKED,
                        probability=belief,
                        caused_by=dst,
                        belief=belief,
                    )
                )

            # Destination impact (affected as target - ingress blocked)
            # Only for path effects (not permissions)
            if effect.kind == "path":
                impacts.append(
                    ComponentImpact(
                        component=dst,
                        status=OperationalStatus.DEGRADED,
                        mechanism=ImpactMechanism.DIRECT_PATH_BLOCKED,
                        probability=belief,
                        caused_by=src,
                        belief=belief,
                    )
                )

    return impacts, not_ready_components


def check_readiness_coupling(graph: nx.MultiDiGraph, src: str, dst: str) -> bool:
    """Check if source component is readiness-coupled to destination.

    Per §8.3: A component is readiness-coupled if it has a READINESS_COUPLED edge.

    Args:
        graph: Dependency graph
        src: Source component
        dst: Destination component

    Returns:
        True if src is readiness-coupled to dst
    """
    if not graph.has_node(src) or not graph.has_node(dst):
        return False

    # Check for READINESS_COUPLED relationship
    if graph.has_edge(src, dst):
        for key in graph[src][dst]:
            edge_data = graph[src][dst][key]
            if edge_data.get("relationship") == "READINESS_COUPLED":
                return True

    return False


def get_belief_for_effect(
    graph: nx.MultiDiGraph,
    src: str,
    dst: str,
    reliability: dict[str, float],
    mask: set[str],
) -> float:
    """Get belief in dependency for a change effect.

    Args:
        graph: Dependency graph
        src: Source component
        dst: Destination component
        reliability: Reliability weights
        mask: Evidence types to consider

    Returns:
        Belief score (0.0-1.0)
    """
    if not graph.has_node(src) or not graph.has_node(dst):
        return 0.0

    # Find edges between src and dst
    if not graph.has_edge(src, dst):
        return 0.0

    # Get aggregated confidence from any edge (they're pre-aggregated in builder)
    max_belief = 0.0
    for key in graph[src][dst]:
        edge_data = graph[src][dst][key]
        conf_by_type = edge_data.get("conf_by_type", {})

        # Filter by mask and compute belief
        from evgate.contracts import EvidenceType

        mask_as_enum = {EvidenceType(t) if isinstance(t, str) else t for t in mask}
        belief = compute_belief(conf_by_type, reliability, mask_as_enum)
        max_belief = max(max_belief, belief)

    return max_belief


def propagate_cascades(
    graph: nx.MultiDiGraph,
    not_ready_components: set[str],
    initial_impacts: list[ComponentImpact],
    reliability: dict[str, float],
    mask: set[str],
    tau_pos: float,
    max_depth: int = 4,
) -> list[ComponentImpact]:
    """Propagate unavailability through upstream dependencies.

    Per §8.3 fixpoint algorithm:
    - Components marked not_ready cause their K8s service endpoints to disappear
    - For every component y with DEPENDS_ON|CALLS|CONNECTS_TO → not_ready component x:
      * If belief(y,x) >= tau_pos: y becomes unavailable
      * Else: y becomes degraded
      * probability = belief(y,x) * probability(x)

    Uses depth limit (default 4) and visited set to prevent infinite loops.

    Args:
        graph: Dependency graph
        not_ready_components: Components marked as not ready
        initial_impacts: Direct impacts already computed
        reliability: Reliability weights
        mask: Evidence types to consider
        tau_pos: Positive belief threshold
        max_depth: Maximum cascade depth

    Returns:
        List of cascade impacts
    """
    cascade_impacts: list[ComponentImpact] = []
    visited: set[tuple[str, str]] = set()  # (component, caused_by) pairs

    # Build impact lookup for probability calculation
    impact_map: dict[str, ComponentImpact] = {}
    for impact in initial_impacts:
        if impact.component not in impact_map:
            impact_map[impact.component] = impact
        elif impact.status == OperationalStatus.UNAVAILABLE:
            # Prefer unavailable over degraded
            impact_map[impact.component] = impact

    # Fixpoint iteration with depth limit
    for _depth in range(max_depth):
        new_not_ready: set[str] = set()

        # Find components that depend on not_ready components
        for not_ready_comp in not_ready_components:
            # Find predecessors (components that depend on not_ready_comp)
            for dependent in graph.predecessors(not_ready_comp):
                # Skip if already processed this pair
                if (dependent, not_ready_comp) in visited:
                    continue

                # Check for dependency relationships
                has_dependency = False
                for key in graph[dependent][not_ready_comp]:
                    edge_data = graph[dependent][not_ready_comp][key]
                    rel = edge_data.get("relationship", "")
                    if rel in ("DEPENDS_ON", "CALLS", "CONNECTS_TO"):
                        has_dependency = True
                        break

                if not has_dependency:
                    continue

                # Get belief in this dependency
                belief = get_belief_for_effect(
                    graph, dependent, not_ready_comp, reliability, mask
                )

                # Only propagate if belief meets threshold or is non-zero
                if belief > 0.0:
                    visited.add((dependent, not_ready_comp))

                    # Get probability of cause component
                    cause_prob = (
                        impact_map[not_ready_comp].probability
                        if not_ready_comp in impact_map
                        else 1.0
                    )

                    # Cascade probability = belief * cause_probability
                    cascade_prob = belief * cause_prob

                    # Determine status
                    if belief >= tau_pos:
                        status = OperationalStatus.UNAVAILABLE
                        new_not_ready.add(dependent)
                    else:
                        status = OperationalStatus.DEGRADED

                    impact = ComponentImpact(
                        component=dependent,
                        status=status,
                        mechanism=ImpactMechanism.UPSTREAM_CASCADE,
                        probability=cascade_prob,
                        caused_by=not_ready_comp,
                        belief=belief,
                    )

                    cascade_impacts.append(impact)
                    impact_map[dependent] = impact

        # No new not_ready components found - fixpoint reached
        if not new_not_ready:
            break

        # Add new not_ready components for next iteration
        not_ready_components = not_ready_components | new_not_ready

    return cascade_impacts


def propagate_operational_impact(
    change: ChangeSpec,
    graph: nx.MultiDiGraph,
    reliability: dict[str, float],
    mask: set[str],
    tau_pos: float,
) -> list[ComponentImpact]:
    """Compute operational impact propagation for a change.

    Implements §8.3 algorithm:
    1. Identify direct impacts from newly-denied paths
    2. Mark readiness-coupled components as not_ready
    3. Propagate cascades through dependency graph with fixpoint

    Args:
        change: Change specification
        graph: Dependency graph
        reliability: Reliability weights per evidence type
        mask: Set of evidence types to consider
        tau_pos: Positive belief threshold

    Returns:
        List of all component impacts (direct + cascaded)
    """
    # Step 1: Direct impacts
    direct_impacts, not_ready = get_direct_impacts(
        change, graph, reliability, mask, tau_pos
    )

    # Step 2: Cascade propagation
    cascade_impacts = propagate_cascades(
        graph, not_ready, direct_impacts, reliability, mask, tau_pos
    )

    # Combine and deduplicate (prefer unavailable over degraded for same component)
    all_impacts = direct_impacts + cascade_impacts

    # Deduplicate: keep highest severity for each component
    final_impacts: dict[str, ComponentImpact] = {}
    for impact in all_impacts:
        comp = impact.component
        if comp not in final_impacts:
            final_impacts[comp] = impact
        else:
            # Prefer unavailable over degraded
            if impact.status == OperationalStatus.UNAVAILABLE:
                final_impacts[comp] = impact
            elif (
                impact.status == OperationalStatus.DEGRADED
                and final_impacts[comp].status != OperationalStatus.UNAVAILABLE
            ):
                # Keep higher probability degraded
                if impact.probability > final_impacts[comp].probability:
                    final_impacts[comp] = impact

    return list(final_impacts.values())
