"""Generate a visual graph image from the evidence graph."""

import json
from pathlib import Path

import networkx as nx

from evgate.contracts import EvidenceBundle, EvidenceType
from evgate.graph import build_graph

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("matplotlib not available, will generate DOT file only")

# Load G1 bundle
print("Loading G1 bundle...")
with open("fixtures/golden/G1_bundle_full.json") as f:
    data = json.load(f)
bundle = EvidenceBundle(**data)

# Build graph
print("Building graph...")
G = build_graph(bundle, mask=None)

output_dir = Path("test_output")
output_dir.mkdir(exist_ok=True)

# Export DOT file (always works)
print("\nGenerating DOT file...")
dot_file = output_dir / "graph_g1.dot"

# Create a simplified version for visualization
simple_G = nx.DiGraph()

# Add nodes with labels
for node, attrs in G.nodes(data=True):
    # Simplify node names
    if "component:" in node:
        label = node.split("/")[-1]
    elif "k8s-service:" in node:
        label = node.split("/")[-1] + "\n(service)"
    elif "config:" in node:
        label = "config:\nDATABASE_HOST"
    else:
        label = node
    
    simple_G.add_node(node, label=label)

# Add edges with combined labels
edge_summary = {}
for src, dst, key, data in G.edges(keys=True, data=True):
    edge_key = (src, dst)
    if edge_key not in edge_summary:
        edge_summary[edge_key] = []
    
    relationship = key
    conf_summary = ", ".join(f"{k}:{v:.2f}" for k, v in data.get("conf_by_type", {}).items())
    edge_summary[edge_key].append(f"{relationship}\n({conf_summary})")

for (src, dst), labels in edge_summary.items():
    combined_label = "\n".join(labels)
    simple_G.add_edge(src, dst, label=combined_label)

# Write DOT file
nx.drawing.nx_pydot.write_dot(simple_G, dot_file)
print(f"✅ DOT file saved to: {dot_file}")
print(f"   Render with: dot -Tpng {dot_file} -o graph.png")

# Try to generate image if matplotlib is available
if HAS_MATPLOTLIB:
    print("\nGenerating PNG image...")
    try:
        plt.figure(figsize=(14, 10))
        
        # Use hierarchical layout
        pos = nx.spring_layout(simple_G, k=2, iterations=50, seed=42)
        
        # Separate node types by color
        node_colors = []
        for node in simple_G.nodes():
            if "component:" in node:
                node_colors.append("#87CEEB")  # Sky blue for components
            elif "k8s-service:" in node:
                node_colors.append("#90EE90")  # Light green for services
            elif "config:" in node:
                node_colors.append("#FFD700")  # Gold for config
            else:
                node_colors.append("#D3D3D3")  # Gray for other
        
        # Draw nodes
        nx.draw_networkx_nodes(
            simple_G, pos,
            node_color=node_colors,
            node_size=3000,
            alpha=0.9
        )
        
        # Draw edges
        nx.draw_networkx_edges(
            simple_G, pos,
            width=2,
            alpha=0.6,
            arrows=True,
            arrowsize=20,
            arrowstyle="->"
        )
        
        # Draw labels
        labels = nx.get_node_attributes(simple_G, "label")
        nx.draw_networkx_labels(
            simple_G, pos,
            labels,
            font_size=9,
            font_weight="bold"
        )
        
        # Draw edge labels
        edge_labels = nx.get_edge_attributes(simple_G, "label")
        nx.draw_networkx_edge_labels(
            simple_G, pos,
            edge_labels,
            font_size=7,
            font_color="red"
        )
        
        plt.title("Evidence Graph - G1 Bundle (baseline@m2)", fontsize=16, fontweight="bold")
        plt.axis("off")
        plt.tight_layout()
        
        png_file = output_dir / "graph_g1.png"
        plt.savefig(png_file, dpi=150, bbox_inches="tight")
        print(f"✅ PNG image saved to: {png_file}")
        
    except Exception as e:
        print(f"⚠️  Could not generate PNG: {e}")
        print("   Use the DOT file instead")

print("\n" + "="*60)
print("VISUALIZATION FILES GENERATED")
print("="*60)
print(f"\n📄 Graph structure: {output_dir / 'graph_g1.json'}")
print(f"📄 DOT file: {output_dir / 'graph_g1.dot'}")
if HAS_MATPLOTLIB and (output_dir / "graph_g1.png").exists():
    print(f"🖼️  PNG image: {output_dir / 'graph_g1.png'}")
print(f"📄 Detailed analysis: {output_dir / 'GRAPH_VISUALIZATION.md'}")

print("\n✅ Visualization complete!")
