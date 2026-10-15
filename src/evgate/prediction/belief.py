"""Belief, sufficiency, and confidence calculations per §8.2.

Implements the mathematical formulas for evidence aggregation:
- Noisy-OR within evidence types
- Reliability-weighted combination across types
- Absence informativeness
- Path and change sufficiency
- Final confidence scores
"""

from __future__ import annotations

from typing import Any

from evgate.contracts import EvidenceType, StaticCompleteness


def compute_belief(
    conf_by_type: dict[str, float],
    reliability: dict[str, float],
    mask: set[EvidenceType],
    contradicting_by_type: dict[str, float] | None = None,
) -> float:
    """Compute belief that a dependency exists using noisy-OR and reliability weights.

    Formula per §8.2:
    - Per type t: c_t already computed as noisy-OR of top-k evidence
    - belief(s,d) = 1 - Π_t (1 - r_t · c_t) over types in mask
    - If contradicting evidence: belief ← belief · (1 - r_t · k_t)

    Args:
        conf_by_type: Confidence per evidence type (already noisy-OR aggregated)
        reliability: Reliability weights per type (from config)
        mask: Set of evidence types to consider
        contradicting_by_type: Strength of contradicting evidence per type (optional)

    Returns:
        Belief score (0.0-1.0) that the dependency exists

    Example:
        conf_by_type = {"infrastructure": 0.5, "application": 0.85}
        reliability = {"infrastructure": 0.6, "application": 0.8}
        mask = {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION}

        belief = 1 - (1 - 0.6*0.5) * (1 - 0.8*0.85)
               = 1 - (1 - 0.3) * (1 - 0.68)
               = 1 - 0.7 * 0.32
               = 1 - 0.224
               = 0.776
    """
    # Compute product term: Π_t (1 - r_t · c_t)
    product = 1.0

    for etype in mask:
        etype_str = etype.value if isinstance(etype, EvidenceType) else etype
        conf = conf_by_type.get(etype_str, 0.0)
        rel = reliability.get(etype_str, 0.0)

        # Contribution of this type to belief
        product *= 1.0 - (rel * conf)

    # Belief is complement of the product
    belief = 1.0 - product

    # Apply contradicting evidence if present
    if contradicting_by_type:
        for etype_str, strength in contradicting_by_type.items():
            rel = reliability.get(etype_str, 0.0)
            belief *= 1.0 - (rel * strength)

    return belief


def compute_absence_informativeness(
    static_completeness: StaticCompleteness | None,
    runtime_coverage: float | None,
    reliability: dict[str, float],
    mask: set[EvidenceType],
) -> float:
    """Compute how informative the absence of evidence is.

    Formula per §8.2:
    neg(s,d) = 1 - (1 - a)(1 - b) where:
    - a = static_score · r_app (if application in mask and completeness available)
    - b = coverage · r_runtime (if runtime in mask and coverage available)

    Infrastructure alone CANNOT establish absence of a dependency.

    Args:
        static_completeness: Static analysis completeness for subject component
        runtime_coverage: Endpoint coverage from runtime observation
        reliability: Reliability weights per type
        mask: Set of evidence types being considered

    Returns:
        Absence informativeness score (0.0-1.0)

    Example:
        static_completeness.score = 1.0 (fully resolved)
        runtime_coverage = 0.8
        reliability = {"application": 0.8, "runtime": 0.9}
        mask includes both

        a = 1.0 * 0.8 = 0.8
        b = 0.8 * 0.9 = 0.72
        neg = 1 - (1-0.8)(1-0.72) = 1 - 0.2*0.28 = 1 - 0.056 = 0.944
    """
    a = 0.0
    b = 0.0

    # Application contribution
    if EvidenceType.APPLICATION in mask and static_completeness is not None:
        static_score = static_completeness.score
        r_app = reliability.get("application", 0.0)
        a = static_score * r_app

    # Runtime contribution
    if EvidenceType.RUNTIME in mask and runtime_coverage is not None:
        r_runtime = reliability.get("runtime", 0.0)
        b = runtime_coverage * r_runtime

    # Combine: either source can establish absence, both strengthen it
    neg = 1.0 - (1.0 - a) * (1.0 - b)

    return neg


def compute_path_sufficiency(
    conf_by_type: dict[str, float],
    n_types_supporting: int,
    absence_informativeness: float | None = None,
) -> float:
    """Compute path sufficiency for positive or absence evidence.

    Formula per §8.2:
    - Positive case: S_pos = min(1, n_types_supporting / 2) · mean(conf_by_type)
    - Absence case: S_neg = neg(s,d)

    Args:
        conf_by_type: Confidence per evidence type
        n_types_supporting: Number of evidence types supporting the claim
        absence_informativeness: For absence case, pass neg(s,d)

    Returns:
        Sufficiency score (0.0-1.0)

    Example (positive):
        conf_by_type = {"infrastructure": 0.5, "application": 0.85, "runtime": 1.0}
        n_types_supporting = 3

        type_factor = min(1, 3/2) = 1.0
        mean_conf = (0.5 + 0.85 + 1.0) / 3 = 0.783
        S_pos = 1.0 * 0.783 = 0.783

    Example (absence):
        absence_informativeness = 0.944
        S_neg = 0.944
    """
    # Absence case
    if absence_informativeness is not None:
        return absence_informativeness

    # Positive case
    if not conf_by_type or n_types_supporting == 0:
        return 0.0

    # Type diversity factor: reward having multiple types
    type_factor = min(1.0, n_types_supporting / 2.0)

    # Mean confidence across types
    mean_conf = sum(conf_by_type.values()) / len(conf_by_type)

    return type_factor * mean_conf


def compute_change_sufficiency(
    path_sufficiencies: list[float],
) -> float:
    """Compute change sufficiency as weakest link over newly-denied paths.

    Formula per §8.2:
    S_change = min(path_sufficiencies)

    The change is only as well-supported as its weakest affected path.

    Args:
        path_sufficiencies: Sufficiency scores for each affected path

    Returns:
        Minimum sufficiency (weakest link)

    Example:
        paths = [0.85, 0.90, 0.65]
        S_change = 0.65  (weakest link)
    """
    if not path_sufficiencies:
        return 0.0

    return min(path_sufficiencies)


def compute_confidence(
    sufficiency: float,
    belief: float,
    decision: str,
) -> float:
    """Compute final confidence score for a decision.

    Formula per §8.2:
    - RISKY: confidence = S · belief (evidence that it breaks)
    - SAFE: confidence = S · (1 - belief) (evidence that it's safe)
    - INSUFFICIENT: report S as the confidence

    Args:
        sufficiency: Change sufficiency (S)
        belief: Belief in the dependency/risk
        decision: "RISKY", "SAFE", or "INSUFFICIENT"

    Returns:
        Confidence score (0.0-1.0)

    Example (RISKY):
        S = 0.85, belief = 0.776
        confidence = 0.85 * 0.776 = 0.659

    Example (SAFE):
        S = 0.90, belief = 0.1
        confidence = 0.90 * (1 - 0.1) = 0.90 * 0.9 = 0.81
    """
    if decision == "RISKY":
        return sufficiency * belief
    elif decision == "SAFE":
        return sufficiency * (1.0 - belief)
    else:  # INSUFFICIENT
        return sufficiency


def aggregate_evidence_noisy_or(
    confidences: list[float],
    top_k: int = 3,
) -> float:
    """Aggregate multiple evidence items using noisy-OR.

    Formula per §8.2:
    c_t = 1 - Π_{i in top_k} (1 - conf_i)

    Top-k limits double-counting of correlated evidence.

    Args:
        confidences: List of confidence scores
        top_k: Maximum number of items to consider (default: 3)

    Returns:
        Aggregated confidence (0.0-1.0)

    Example:
        confidences = [0.8, 0.7, 0.6, 0.5]
        top_k = 3
        # Take top 3: [0.8, 0.7, 0.6]
        c = 1 - (1-0.8)*(1-0.7)*(1-0.6)
          = 1 - 0.2*0.3*0.4
          = 1 - 0.024
          = 0.976
    """
    if not confidences:
        return 0.0

    # Sort descending and take top k
    sorted_confs = sorted(confidences, reverse=True)[:top_k]

    # Compute noisy-OR: 1 - Π(1 - c_i)
    product = 1.0
    for conf in sorted_confs:
        product *= 1.0 - conf

    return 1.0 - product


def compute_belief_from_graph_edge(
    edge_data: dict[str, Any],
    reliability: dict[str, float],
    mask: set[EvidenceType],
    top_k: int = 3,
) -> float:
    """Compute belief for a dependency from graph edge data.

    This is a convenience function that:
    1. Aggregates evidence within each type using noisy-OR
    2. Combines across types using reliability weights

    Args:
        edge_data: Graph edge attributes (from build_graph)
        reliability: Reliability weights per type
        mask: Set of evidence types to consider
        top_k: Maximum evidence items per type

    Returns:
        Belief score (0.0-1.0)
    """
    # Already computed in builder, but we could recompute for flexibility
    conf_by_type_computed = edge_data.get("conf_by_type", {})

    # Use pre-computed if available
    if conf_by_type_computed:
        return compute_belief(conf_by_type_computed, reliability, mask)

    # Otherwise compute from scratch (placeholder - would need actual evidence items)
    conf_by_type: dict[str, float] = {}
    # Would need access to actual evidence items to get confidences
    # For now, this path is not used since builder always computes conf_by_type

    return compute_belief(conf_by_type, reliability, mask)
