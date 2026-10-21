"""Command-line interface for evidence-gated impact analysis.

Part 3 - Task P3-07: CLI Interface

Usage:
    evgate analyze --change scenarios/N01-isolate-database-m2.yaml
    evgate show results/analysis-001.json
    evgate graph --bundle fixtures/golden/G1_bundle_full.json --export png
    evgate report --analysis analysis-001 --format markdown
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

from evgate.contracts import AnalysisResult, ChangeSpec, EvidenceBundle, GateDecision
from evgate.pipeline import analyze


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run impact analysis on a proposed change."""
    print(f"🔍 Analyzing change: {args.change}")
    print(f"Evidence configuration: {args.evidence_config}")

    try:
        # Load change spec
        change_path = Path(args.change)
        if not change_path.exists():
            print(f"❌ Error: Change file not found: {change_path}", file=sys.stderr)
            return 1

        # For now, use golden fixtures since Part 2 extractors aren't ready
        # This demonstrates the working pipeline with synthetic data
        if args.bundle:
            bundle_path = Path(args.bundle)
            if not bundle_path.exists():
                print(f"❌ Error: Bundle file not found: {bundle_path}", file=sys.stderr)
                return 1
            
            with open(bundle_path) as f:
                bundle_data = json.load(f)
                bundle = EvidenceBundle(**bundle_data)
        else:
            print("⚠️  No evidence bundle provided, using golden fixture G4")
            bundle_path = Path("fixtures/golden/g4-complete.json")
            if bundle_path.exists():
                with open(bundle_path) as f:
                    bundle_data = json.load(f)
                    bundle = EvidenceBundle(**bundle_data)
            else:
                print("❌ Error: Golden fixture not found. Part 2 extractors needed.", file=sys.stderr)
                return 1

        # Load change
        with open(change_path) as f:
            change_data = json.load(f)
            change_spec = ChangeSpec(**change_data)

        # Run analysis
        print(f"\n⚙️  Running analysis...")
        result = analyze(
            bundle=bundle,
            change=change_spec,
            evidence_config=args.evidence_config,
        )

        # Display results
        print("\n" + "=" * 80)
        print("📊 ANALYSIS RESULTS")
        print("=" * 80)
        
        decision = result.gate
        print(f"\n🚦 DECISION: {decision.decision}")
        
        if decision.decision == "SAFE":
            print("✅ This change is predicted to be safe")
        elif decision.decision == "RISKY":
            print("⚠️  This change may cause issues")
        else:
            print("❓ Insufficient evidence to make confident prediction")

        print(f"\n📈 Security Impact: {result.prediction.security_impact}")
        print(f"⚡ Operational Risk: {result.prediction.operational_label}")
        print(f"🎯 Confidence: {result.prediction.confidence:.2f}")
        print(f"📊 Belief: {result.prediction.belief:.2f}")
        print(f"📋 Sufficiency: {result.prediction.sufficiency:.2f}")

        print(f"\n🎯 Affected Components ({len(result.prediction.affected_components)}):")
        for comp in result.prediction.affected_components:
            icon = {"unavailable": "❌", "degraded": "⚠️", "isolated": "🔒", "none": "✅"}.get(comp.impact, "❔")
            print(f"  {icon} {comp.component}: {comp.impact} (probability: {comp.probability:.2f})")
            if hasattr(comp, 'reason') and comp.reason:
                print(f"     Reason: {comp.reason}")

        if hasattr(decision, 'reasoning') and decision.reasoning:
            print(f"\n💡 Reasoning:\n{decision.reasoning}")

        if hasattr(decision, 'reasons') and decision.reasons:
            print(f"\n🏷️  Reasons: {', '.join(str(r) for r in decision.reasons)}")

        # Save result
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        analysis_id = f"analysis-{change_spec.change_id}"
        output_file = output_dir / f"{analysis_id}.json"
        
        with open(output_file, "w") as f:
            json.dump(result.model_dump(), f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        return 0

    except Exception as e:
        print(f"\n❌ Error during analysis: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    """Display analysis results from a JSON file."""
    result_path = Path(args.result_file)
    
    if not result_path.exists():
        print(f"❌ Error: Result file not found: {result_path}", file=sys.stderr)
        return 1

    try:
        with open(result_path) as f:
            result_data = json.load(f)
            result = AnalysisResult(**result_data)

        print("\n" + "=" * 80)
        print("📊 ANALYSIS RESULTS")
        print("=" * 80)
        
        decision = result.gate
        print(f"\n🚦 DECISION: {decision.decision}")
        print(f"📈 Security Impact: {result.prediction.security_impact}")
        print(f"⚡ Operational Risk: {result.prediction.operational_label}")
        print(f"🎯 Confidence: {result.prediction.confidence:.2f}")

        print(f"\n🎯 Affected Components ({len(result.prediction.affected_components)}):")
        for comp in result.prediction.affected_components:
            icon = {"unavailable": "❌", "degraded": "⚠️", "isolated": "🔒", "none": "✅"}.get(comp.impact, "❔")
            print(f"  {icon} {comp.component}: {comp.impact}")

        if hasattr(decision, 'reasoning') and decision.reasoning:
            print(f"\n💡 {decision.reasoning}")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


def cmd_graph(args: argparse.Namespace) -> int:
    """Visualize evidence/dependency graph."""
    bundle_path = Path(args.bundle)
    
    if not bundle_path.exists():
        print(f"❌ Error: Bundle file not found: {bundle_path}", file=sys.stderr)
        return 1

    try:
        from evgate.graph.builder import build_graph
        
        with open(bundle_path) as f:
            bundle_data = json.load(f)
            bundle = EvidenceBundle(**bundle_data)

        print(f"📊 Building graph from {len(bundle.evidence)} evidence records...")
        graph = build_graph(bundle)
        
        print(f"✅ Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        
        if args.export:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if args.export == "png":
                # PNG export requires matplotlib
                try:
                    from evgate.graph.export import export_graph_png
                    export_graph_png(graph, str(output_path))
                    print(f"💾 Graph exported to: {output_path}")
                except ImportError:
                    print("⚠️  PNG export requires matplotlib. Installing...")
                    print("   Run: pip install matplotlib")
                    return 1
            elif args.export == "json":
                from networkx.readwrite import json_graph
                graph_data = json_graph.node_link_data(graph)
                with open(output_path, "w") as f:
                    json.dump(graph_data, f, indent=2)
                print(f"💾 Graph JSON exported to: {output_path}")
            else:
                print(f"❌ Unsupported export format: {args.export}", file=sys.stderr)
                return 1
        
        return 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_report(args: argparse.Namespace) -> int:
    """Generate analysis report."""
    print(f"📄 Report generation not yet implemented (Task P3-08)")
    print(f"   Analysis ID: {args.analysis}")
    print(f"   Format: {args.format}")
    return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Evidence-Gated Cloud Change Impact Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a change with golden fixture
  evgate analyze --change fixtures/golden/change-m2.json --bundle fixtures/golden/g4-complete.json

  # Show previous results
  evgate show results/analysis-001.json

  # Export graph visualization
  evgate graph --bundle fixtures/golden/g4-complete.json --export png --output graph.png

  # Generate markdown report (coming soon)
  evgate report --analysis analysis-001 --format markdown
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a proposed change")
    analyze_parser.add_argument(
        "--change",
        required=True,
        help="Path to change specification JSON file",
    )
    analyze_parser.add_argument(
        "--bundle",
        help="Path to evidence bundle JSON (optional, defaults to G4 fixture)",
    )
    analyze_parser.add_argument(
        "--evidence-config",
        default="D",
        choices=["A", "B", "C", "D"],
        help="Evidence configuration: A=infra only, B=infra+app, C=infra+runtime, D=all (default: D)",
    )
    analyze_parser.add_argument(
        "--output",
        default="results",
        help="Output directory for analysis results (default: results/)",
    )

    # show command
    show_parser = subparsers.add_parser("show", help="Display analysis results")
    show_parser.add_argument("result_file", help="Path to analysis result JSON file")

    # graph command
    graph_parser = subparsers.add_parser("graph", help="Visualize evidence graph")
    graph_parser.add_argument(
        "--bundle",
        required=True,
        help="Path to evidence bundle JSON file",
    )
    graph_parser.add_argument(
        "--export",
        choices=["png", "json", "dot"],
        help="Export format (optional)",
    )
    graph_parser.add_argument(
        "--output",
        default="graph.png",
        help="Output file path (default: graph.png)",
    )

    # report command
    report_parser = subparsers.add_parser("report", help="Generate analysis report")
    report_parser.add_argument(
        "--analysis",
        required=True,
        help="Analysis ID or result file path",
    )
    report_parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "html", "pdf"],
        help="Report format (default: markdown)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handlers
    if args.command == "analyze":
        return cmd_analyze(args)
    elif args.command == "show":
        return cmd_show(args)
    elif args.command == "graph":
        return cmd_graph(args)
    elif args.command == "report":
        return cmd_report(args)
    else:
        print(f"❌ Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
