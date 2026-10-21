"""Main analysis pipeline: analyze() function.

This is the primary entry point for Part 3 (Core Engine).
It coordinates graph building, prediction, and gate decision.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Literal

import yaml

from .contracts import (
    AnalysisResult,
    ChangeSpec,
    EvidenceBundle,
    EvidenceType,
    Prediction,
)
from .gate import apply_evidence_gate, forced_decision
from .graph import build_graph
from .prediction import (
    compute_change_sufficiency,
    compute_security_impact,
    propagate_operational_impact,
)


def get_git_sha() -> str:
    """Get current git commit SHA (short form).

    Returns:
        Short SHA (8 chars) or "unknown" if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return "unknown"


def load_config(config_path: Path) -> dict[str, Any]:
    """Load analysis configuration from YAML file.

    Args:
        config_path: Path to config YAML file

    Returns:
        Configuration dictionary with thresholds and reliability weights

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config: dict[str, Any] = yaml.safe_load(f)

    # Validate required keys
    required = ["reliability", "tau_pos", "tau_risk", "tau_suff_pos", "tau_suff_neg"]
    for key in required:
        if key not in config:
            raise ValueError(f"Config missing required key: {key}")

    return config


def get_evidence_mask(evidence_config: str) -> set[EvidenceType]:
    """Get evidence type mask for the given configuration.

    Configs (per §9.4):
    - A: infrastructure only
    - B: infrastructure + application
    - C: infrastructure + runtime
    - D: all three (infrastructure + application + runtime)

    Args:
        evidence_config: Evidence configuration code (A/B/C/D)

    Returns:
        Set of evidence types to include

    Raises:
        ValueError: If evidence_config is not recognized
    """
    masks = {
        "A": {EvidenceType.INFRASTRUCTURE},
        "B": {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION},
        "C": {EvidenceType.INFRASTRUCTURE, EvidenceType.RUNTIME},
        "D": {
            EvidenceType.INFRASTRUCTURE,
            EvidenceType.APPLICATION,
            EvidenceType.RUNTIME,
        },
        "D_NOGATE": {
            EvidenceType.INFRASTRUCTURE,
            EvidenceType.APPLICATION,
            EvidenceType.RUNTIME,
        },
    }

    if evidence_config not in masks:
        raise ValueError(
            f"Unknown evidence_config: {evidence_config}. "
            f"Must be one of: {list(masks.keys())}"
        )

    return masks[evidence_config]


def analyze(
    change: ChangeSpec,
    bundle: EvidenceBundle,
    *,
    evidence_config: Literal["A", "B", "C", "D", "D_NOGATE"] = "D",
    gate_enabled: bool = True,
    config_path: Path = Path("config/analysis.yaml"),
) -> AnalysisResult:
    """Analyze the impact of a proposed change using evidence.

    This is the main pipeline function that coordinates:
    1. Configuration loading
    2. Evidence leakage guard (D1: reject post-change evidence)
    3. Graph construction with evidence masking
    4. Belief and sufficiency calculation
    5. Operational impact propagation
    6. Security impact analysis
    7. Evidence gate decision
    8. Result packaging with versions

    Args:
        change: The proposed change specification
        bundle: Pre-change evidence bundle (baseline only)
        evidence_config: Evidence configuration (A/B/C/D/D_NOGATE)
        gate_enabled: Whether to apply evidence gate (default True)
        config_path: Path to analysis configuration file

    Returns:
        Complete analysis result with prediction and gate decision

    Raises:
        ValueError: If bundle contains post-change evidence (leakage)
        FileNotFoundError: If config file not found
    """
    # Step 1: Load configuration
    config = load_config(config_path)

    # Step 2: Leakage guard (D1: only pre-change evidence allowed)
    bundle.assert_no_leakage()

    # Step 3: Get evidence mask for this configuration
    mask = get_evidence_mask(evidence_config)

    # Step 4: Build graph with evidence masking
    graph = build_graph(bundle, mask=mask)

    # Step 5: Compute belief and sufficiency for affected paths
    # First, collect path sufficiencies for all affected paths
    from .prediction import compute_belief_from_graph_edge, compute_path_sufficiency

    path_sufficiencies: list[float] = []

    for effect in change.effects:
        if hasattr(effect, "subject") and hasattr(effect, "object"):
            # Check if edge exists in graph
            subject = effect.subject
            obj = effect.object

            if graph.has_edge(subject, obj):
                # Get all edges between these nodes (MultiDiGraph)
                for key in graph[subject][obj]:
                    edge_data = graph[subject][obj][key]

                    # Compute belief from edge
                    belief = compute_belief_from_graph_edge(
                        edge_data,
                        config["reliability"],
                        mask,
                        config.get("top_k_per_type", 3),
                    )

                    # Check if belief meets tau_pos threshold
                    if belief >= config["tau_pos"]:
                        # Get confidence by type
                        conf_by_type = edge_data.get("conf_by_type", {})
                        n_types = len([t for t in conf_by_type if conf_by_type[t] > 0])

                        # Compute path sufficiency for positive evidence
                        path_suff = compute_path_sufficiency(
                            conf_by_type, n_types, absence_informativeness=None
                        )
                        path_sufficiencies.append(path_suff)

    # Compute overall change sufficiency (weakest link)
    sufficiency = compute_change_sufficiency(path_sufficiencies)

    # Step 6: Operational impact propagation
    operational_impact_list = propagate_operational_impact(
        change=change,
        graph=graph,
        reliability=config["reliability"],
        mask=mask,  # type: ignore[arg-type]
        tau_pos=config["tau_pos"],
    )

    # Convert list to dict for prediction
    {imp.component: imp for imp in operational_impact_list}

    # Step 7: Security impact analysis
    security_impact, security_delta, security_details = compute_security_impact(
        change, graph
    )

    # Step 7.5: Compute operational risk and label
    from .prediction import apply_risk_threshold, compute_operational_risk

    operational_risk, operational_label = compute_operational_risk(
        operational_impact_list
    )
    operational_label = apply_risk_threshold(
        operational_risk, operational_label, config["tau_risk"]
    )

    # Step 8: Apply evidence gate or forced decision
    if gate_enabled:
        gate_decision = apply_evidence_gate(
            change=change,
            graph=graph,
            bundle=bundle,
            sufficiency=sufficiency,
            security_impact=security_impact,
            operational_label=operational_label,
            tau_pos=config["tau_pos"],
            tau_suff_pos=config["tau_suff_pos"],
            tau_suff_neg=config["tau_suff_neg"],
            mask=mask,
            gate_enabled=True,
        )
    else:
        # Forced decision mode for evaluation (D_NOGATE)
        gate_decision = forced_decision(
            security_impact=security_impact,
            operational_label=operational_label,
        )

    # Step 9: Create prediction
    # Sort component impacts for determinism
    sorted_impacts = sorted(operational_impact_list, key=lambda imp: imp.component)

    # Convert to contract ComponentImpact format
    from .contracts import ComponentImpact as ContractComponentImpact

    affected_components = [
        ContractComponentImpact(
            component=imp.component,
            impact=str(imp.status.value) if hasattr(imp.status, "value") else str(imp.status),  # type: ignore[arg-type]
            mechanism=str(imp.mechanism.value) if hasattr(imp.mechanism, "value") else str(imp.mechanism),  # type: ignore[arg-type]
            probability=imp.probability,
            evidence_ids=[],  # TODO: track evidence IDs through propagation
        )
        for imp in sorted_impacts
    ]

    # Compute belief and confidence
    from .prediction import compute_confidence

    # Average belief across affected paths (simplified)
    beliefs = []
    for effect in change.effects:
        if hasattr(effect, "subject") and hasattr(effect, "object"):
            if graph.has_edge(effect.subject, effect.object):
                for key in graph[effect.subject][effect.object]:
                    edge_data = graph[effect.subject][effect.object][key]
                    belief = compute_belief_from_graph_edge(
                        edge_data,
                        config["reliability"],
                        mask,
                        config.get("top_k_per_type", 3),
                    )
                    beliefs.append(belief)

    avg_belief = sum(beliefs) / len(beliefs) if beliefs else 0.0

    # Compute confidence based on gate decision
    confidence = compute_confidence(
        sufficiency=sufficiency,
        belief=avg_belief,
        decision=gate_decision.decision.value,
    )

    # Security delta (from security_impact computation)
    # security_delta already computed above

    prediction = Prediction(
        security_impact=security_impact.value,
        security_delta=security_delta,
        operational_risk=operational_risk,
        operational_label=str(operational_label),  # type: ignore[arg-type]
        affected_components=affected_components,
        belief=avg_belief,
        sufficiency=sufficiency,
        confidence=confidence,
        supporting_evidence_ids=[],  # TODO: collect from graph
        contradicting_evidence_ids=[],  # TODO: collect from graph
        rationale=[],  # TODO: generate human-readable rationale
    )

    # Step 10: Package result with versions
    versions = {
        "git_sha": get_git_sha(),
        "evgate_version": "1.0.0",  # TODO: read from package
        "config_file": str(config_path),
    }

    result = AnalysisResult(
        change_id=change.change_id,
        evidence_config=evidence_config,
        gate_enabled=gate_enabled,
        prediction=prediction,
        gate=gate_decision,
        versions=versions,
    )

    return result
