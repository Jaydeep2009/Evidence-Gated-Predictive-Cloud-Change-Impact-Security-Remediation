"""Graph export functions for JSON and DOT formats.

Supports exporting the evidence graph for visualization and analysis.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx


def export_json(G: nx.MultiDiGraph, output_path: str | Path) -> None:
    """Export graph to JSON format using NetworkX node-link format.

    Args:
        G: Evidence graph to export
        output_path: Path to output JSON file

    The output uses NetworkX's node_link_data format which preserves
    all node and edge attributes.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to node-link format
    data = nx.node_link_data(G, edges="edges")

    # Write to file
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=_json_serializer)


def export_dot(G: nx.MultiDiGraph, output_path: str | Path) -> None:
    """Export graph to DOT format for Graphviz rendering.

    Args:
        G: Evidence graph to export
        output_path: Path to output .dot file

    The DOT file can be rendered with:
        dot -Tpng graph.dot -o graph.png
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create simplified graph for visualization (combine parallel edges)
    simplified = _simplify_for_visualization(G)

    # Write DOT file
    nx.drawing.nx_pydot.write_dot(simplified, output_path)


def _simplify_for_visualization(G: nx.MultiDiGraph) -> nx.DiGraph:
    """Simplify MultiDiGraph for visualization by combining parallel edges.

    Args:
        G: Original MultiDiGraph

    Returns:
        Simplified DiGraph with combined edge labels
    """
    simple = nx.DiGraph()

    # Copy nodes
    for node, attrs in G.nodes(data=True):
        # Create label from node_id
        label = _format_node_label(node, attrs)
        simple.add_node(node, label=label, **attrs)

    # Combine parallel edges
    for src, dst in G.edges():
        if simple.has_edge(src, dst):
            continue

        # Get all relationships between this pair
        relationships = []
        all_evidence = []
        max_conf = 0.0

        for _key, data in G[src][dst].items():
            rel = data.get("relationship")
            if rel:
                relationships.append(rel.value)
            all_evidence.extend(data.get("evidence_ids", []))
            for conf in data.get("conf_by_type", {}).values():
                max_conf = max(max_conf, conf)

        # Create combined label
        edge_label = ", ".join(relationships) if relationships else "edge"
        edge_label += f"\\n({len(all_evidence)} evidence)"

        simple.add_edge(
            src,
            dst,
            label=edge_label,
            weight=max_conf,
            penwidth=1 + max_conf * 2,  # Visual weight
        )

    return simple


def _format_node_label(node_id: str, attrs: dict[str, Any]) -> str:
    """Format node label for visualization.

    Args:
        node_id: Node identifier
        attrs: Node attributes

    Returns:
        Formatted label string
    """
    # Extract component name from node_id
    if ":" in node_id:
        parts = node_id.split(":", 1)
        if "/" in parts[1]:
            name = parts[1].split("/")[-1]
        else:
            name = parts[1]
    else:
        name = node_id

    # Add namespace if present
    namespace = attrs.get("namespace")
    if namespace:
        return f"{name}\\n({namespace})"

    return name


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types.

    Args:
        obj: Object to serialize

    Returns:
        Serializable representation

    Raises:
        TypeError: If object cannot be serialized
    """
    # Handle Enum types (Relationship, EvidenceType, etc.)
    if hasattr(obj, "value"):
        return obj.value

    # Handle sets
    if isinstance(obj, set):
        return sorted(obj)

    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
