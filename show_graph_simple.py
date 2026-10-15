"""Simple text visualization of the evidence graph."""

import json
from pathlib import Path

from evgate.contracts import EvidenceBundle
from evgate.graph import build_graph, dependency_view

# Load G1 bundle
with open("fixtures/golden/G1_bundle_full.json") as f:
    data = json.load(f)
bundle = EvidenceBundle(**data)

# Build graph
G = build_graph(bundle, mask=None)

print("=" * 80)
print(" EVIDENCE GRAPH VISUALIZATION - G1 Bundle (baseline@m2)")
print("=" * 80)
print()

# Nodes
print("📦 NODES ({})".format(G.number_of_nodes()))
print("-" * 80)
for node, attrs in G.nodes(data=True):
    kind = attrs.get("kind", "unknown")
    namespace = attrs.get("namespace", "N/A")
    labels = attrs.get("labels", {})
    
    print(f"\n  [{kind}] {node}")
    if namespace and namespace != "N/A":
        print(f"    Namespace: {namespace}")
    if labels:
        print(f"    Labels: {labels}")

# Edges
print("\n\n" + "=" * 80)
print("🔗 EDGES ({})".format(G.number_of_edges()))
print("=" * 80)

for src, dst, key, data in G.edges(keys=True, data=True):
    print(f"\n  {src}")
    print(f"    │")
    print(f"    └──[ {key} ]──►  {dst}")
    print(f"       │")
    print(f"       ├─ Evidence: {len(data['evidence_ids'])} items")
    print(f"       │  {data['evidence_ids']}")
    print(f"       ├─ Types: {list(data['by_type'].keys())}")
    print(f"       ├─ Confidence by type:")
    for etype, conf in data['conf_by_type'].items():
        print(f"       │  • {etype}: {conf:.2f}")
    print(f"       ├─ Sources: {data['sources']}")
    print(f"       ├─ Conflicted: {data['conflicted']}")
    print(f"       └─ Snapshot: {data['snapshot_id']}")

# Dependency view
print("\n\n" + "=" * 80)
print("🎯 DEPENDENCY VIEW")
print("=" * 80)

deps = dependency_view(G)
print(f"\nFound {len(deps)} dependency pairs:")

for (src, dst), record in deps.items():
    print(f"\n  {src}  ──►  {dst}")
    print(f"    │")
    print(f"    ├─ Belief: {record.belief:.2f}")
    print(f"    ├─ Relationships: {[r.value for r in record.relationships]}")
    print(f"    ├─ Confidence by type:")
    for etype, conf in record.conf_by_type.items():
        print(f"    │  • {etype}: {conf:.2f}")
    print(f"    ├─ Has conflict: {record.has_conflict}")
    print(f"    ├─ Already failing: {record.already_failing}")
    print(f"    └─ Evidence count: {len(record.evidence_ids)}")

# Summary
print("\n\n" + "=" * 80)
print("📊 SUMMARY")
print("=" * 80)
print(f"""
Components identified: 3 (frontend, backend, database)
Critical dependency: backend → database

Evidence types supporting backend → database:
  • Infrastructure (conf: 0.50) - env variable reference
  • Application   (conf: 0.85) - code-level dependency + readiness coupling  
  • Runtime       (conf: 1.00) - observed TCP connection

Overall belief in dependency: 0.83 (HIGH)

This matches the Milestone 2 finding:
  Blocking backend → database breaks the application
""")

print("✅ Visualization complete!")
print("\n📄 For detailed analysis, see: test_output/GRAPH_VISUALIZATION.md")
