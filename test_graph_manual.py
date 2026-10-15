"""Manual test script to explore the graph builder."""

import json
from pathlib import Path

from evgate.contracts import EvidenceBundle, EvidenceType
from evgate.graph import build_graph, dependency_view, export_json

# Load G1 fixture
print("Loading G1 bundle...")
with open("fixtures/golden/G1_bundle_full.json") as f:
    data = json.load(f)
bundle = EvidenceBundle(**data)

print(f"Bundle: {bundle.bundle_id}")
print(f"Snapshot: {bundle.snapshot_id}")
print(f"Inventory: {len(bundle.inventory)} components")
print(f"Evidence: {len(bundle.evidence)} items")
print()

# Build graph with all evidence (mask D)
print("Building graph with all evidence (mask D)...")
G = build_graph(bundle, mask=None)
print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")
print()

# List nodes
print("Nodes:")
for node in G.nodes():
    print(f"  - {node}")
print()

# List edges with details
print("Edges:")
for src, dst, key, data in G.edges(keys=True, data=True):
    print(f"  {src} --[{key}]--> {dst}")
    print(f"    Evidence IDs: {len(data['evidence_ids'])}")
    print(f"    By type: {list(data['by_type'].keys())}")
    print(f"    Confidence by type: {data['conf_by_type']}")
    print(f"    Conflicted: {data['conflicted']}")
    print()

# Test different masks
print("\n" + "=" * 60)
print("Testing different evidence masks:")
print("=" * 60)

masks = {
    "A (infra only)": {EvidenceType.INFRASTRUCTURE},
    "B (infra+app)": {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION},
    "C (infra+runtime)": {EvidenceType.INFRASTRUCTURE, EvidenceType.RUNTIME},
    "D (all)": None,
}

for name, mask in masks.items():
    G = build_graph(bundle, mask=mask)
    print(f"\n{name}:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

# Test dependency view
print("\n" + "=" * 60)
print("Dependency View:")
print("=" * 60)

G = build_graph(bundle, mask=None)
deps = dependency_view(G)

print(f"\nFound {len(deps)} dependency pairs:")
for (src, dst), record in deps.items():
    print(f"\n{src} --> {dst}")
    print(f"  Belief: {record.belief:.2f}")
    print(f"  Relationships: {[r.value for r in record.relationships]}")
    print(f"  Evidence types: {list(record.conf_by_type.keys())}")
    print(f"  Has conflict: {record.has_conflict}")
    print(f"  Already failing: {record.already_failing}")

# Export graph
print("\n" + "=" * 60)
print("Exporting graph:")
print("=" * 60)

output_dir = Path("test_output")
output_dir.mkdir(exist_ok=True)

json_path = output_dir / "graph_g1.json"
export_json(G, json_path)
print(f"\nExported JSON to: {json_path}")
print("You can visualize this with NetworkX tools or upload to graph visualization tools")

print("\n✅ Manual test complete!")
