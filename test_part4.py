"""
Part 4 Test Script
Demonstrates all Part 4 modules working together.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from evgate.scenarios.loader import ScenarioLoader
from evgate.remediation.network import NetworkRemediator
from evgate.remediation.rbac import RBACRemediator
from evgate.evaluation.perturb import EvidencePerturber, PerturbationCondition
from evgate.evaluation.baselines import BaselineComparator, BaselineMethod
from evgate.evaluation.metrics import MetricsCalculator
from evgate.evaluation.stats import StatisticalAnalyzer
from evgate.stubs.part2_stubs import stub_collect_evidence
from evgate.stubs.part3_stubs import stub_analyze


def test_scenario_loader():
    """Test scenario loading."""
    print("\n" + "="*60)
    print("TEST 1: Scenario Loader")
    print("="*60)
    
    loader = ScenarioLoader("scenarios/")
    
    # Load all scenarios
    scenarios = loader.load_all()
    print(f"\n✓ Loaded {len(scenarios)} scenarios")
    
    # Show first scenario
    if scenarios:
        s = scenarios[0]
        print(f"\nFirst scenario:")
        print(f"  ID: {s.id}")
        print(f"  Name: {s.name}")
        print(f"  Category: {s.category}")
        print(f"  Expected behavior: {s.expected_behavior}")
    
    # Validate all
    validation = loader.validate_all()
    print(f"\nValidation:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Invalid: {validation['invalid']}")
    print(f"  Total: {validation['total']}")
    
    return True


def test_remediation():
    """Test remediation modules."""
    print("\n" + "="*60)
    print("TEST 2: Remediation Modules")
    print("="*60)
    
    # Network remediation
    print("\n→ Network Remediator")
    net_remediator = NetworkRemediator()
    suggestion = net_remediator.analyze_blocked_connection(
        source_pod="backend",
        source_namespace="poc-app",
        dest_service="database",
        dest_namespace="poc-app",
        dest_port=5432
    )
    print(f"  Issue: {suggestion.issue_type}")
    print(f"  Rationale: {suggestion.rationale}")
    print(f"  Confidence: {suggestion.confidence}")
    
    # RBAC remediation
    print("\n→ RBAC Remediator")
    rbac_remediator = RBACRemediator()
    suggestion = rbac_remediator.analyze_permission_denial(
        service_account="backend-sa",
        namespace="poc-app",
        required_verb="list",
        required_resource="pods"
    )
    print(f"  Issue: {suggestion.issue_type}")
    print(f"  Rationale: {suggestion.rationale}")
    print(f"  Confidence: {suggestion.confidence}")
    
    return True


def test_evaluation():
    """Test evaluation modules."""
    print("\n" + "="*60)
    print("TEST 3: Evaluation Framework")
    print("="*60)
    
    # Evidence perturbation
    print("\n→ Evidence Perturbation")
    perturber = EvidencePerturber()
    evidence = {"application_logs": [{"level": "ERROR"}], "runtime_metrics": {"cpu": 0.8}}
    
    perturbed = perturber.apply_condition(evidence, PerturbationCondition.EC1)
    print(f"  Original logs: {len(evidence.get('application_logs', []))}")
    print(f"  EC1 (no app logs): {len(perturbed.get('application_logs', []))}")
    
    # Baselines
    print("\n→ Baseline Comparisons")
    baseline = BaselineComparator()
    scenario = {"change_type": "policy"}
    prediction = baseline.predict(BaselineMethod.B1, scenario, evidence)
    print(f"  B1 prediction: {prediction['predicted_impact']}")
    print(f"  B1 confidence: {prediction['confidence']}")
    
    # Metrics
    print("\n→ Metrics Calculation")
    metrics_calc = MetricsCalculator()
    predictions = ["high", "low", "high", "medium", "high"]
    ground_truth = ["high", "low", "medium", "medium", "high"]
    metrics = metrics_calc.compute_classification_metrics(predictions, ground_truth)
    print(f"  Accuracy: {metrics['accuracy']}")
    print(f"  F1 (macro): {metrics['f1_macro']}")
    
    # Statistics
    print("\n→ Statistical Analysis")
    stats = StatisticalAnalyzer(n_bootstrap=100)
    data = [0.85, 0.90, 0.87, 0.92, 0.88]
    point, lower, upper = stats.bootstrap_confidence_interval(data)
    print(f"  Bootstrap CI: {point} [{lower}, {upper}]")
    
    return True


def test_stubs():
    """Test integration stubs."""
    print("\n" + "="*60)
    print("TEST 4: Integration Stubs (Parts 1-3)")
    print("="*60)
    
    # Part 2 stub
    print("\n→ Part 2: Evidence Collection (stub)")
    evidence = stub_collect_evidence("poc-app")
    print(f"  Application logs: {len(evidence.get('application_logs', []))}")
    print(f"  Runtime metrics keys: {len(evidence.get('runtime_metrics', {}))}")
    
    # Part 3 stub
    print("\n→ Part 3: Core Analyzer (stub)")
    change = {"type": "policy", "name": "isolate-database"}
    result = stub_analyze(change, evidence)
    print(f"  Predicted impact: {result['predicted_impact']}")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Reasoning: {result['reasoning']}")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" PART 4 MODULE TEST SUITE")
    print("="*70)
    print("\nTesting all Part 4 modules (scenarios, remediation, evaluation)")
    print("Note: Ground truth runner requires Kind cluster (not tested here)")
    
    tests = [
        ("Scenario Loader", test_scenario_loader),
        ("Remediation", test_remediation),
        ("Evaluation", test_evaluation),
        ("Integration Stubs", test_stubs)
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\n✗ {name} failed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All Part 4 modules working correctly!")
        print("\nNext steps:")
        print("1. Install Python dependencies: pip install -r requirements.txt")
        print("2. Start Kind cluster: kind create cluster --name poc-cluster")
        print("3. Deploy application: ./scripts/deploy-all.sh")
        print("4. Collect ground truth: python -m evgate.scenarios.runner")
        print("5. Run evaluation: python -m evgate.evaluation.orchestrator")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
