"""
P4-13: Evaluation Orchestrator
Coordinates full evaluation grid: scenarios × configs × conditions.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import itertools

from ..scenarios.loader import ScenarioLoader, Scenario
from ..scenarios.runner import ScenarioRunner
from .perturb import EvidencePerturber, PerturbationCondition
from .baselines import BaselineComparator, BaselineMethod
from .metrics import MetricsCalculator
from .stats import StatisticalAnalyzer


class EvaluationConfig:
    """Configuration for an evaluation run."""
    
    def __init__(
        self,
        name: str,
        analyzer_name: str,  # "evgate", "B1", "B2", etc.
        use_app_logs: bool = True,
        use_runtime_metrics: bool = True,
        use_infra_data: bool = True
    ):
        self.name = name
        self.analyzer_name = analyzer_name
        self.use_app_logs = use_app_logs
        self.use_runtime_metrics = use_runtime_metrics
        self.use_infra_data = use_infra_data


class EvaluationOrchestrator:
    """
    Orchestrates full evaluation grid.
    
    Runs: scenarios × configs × perturbation_conditions
    
    Workflow:
    1. Load scenarios
    2. For each scenario:
       a. Collect ground truth (if not cached)
       b. For each config:
          i. For each perturbation condition:
             - Apply condition to evidence
             - Run analyzer
             - Record prediction
    3. Compute metrics
    4. Run statistical tests
    5. Generate results
    
    Usage:
        orchestrator = EvaluationOrchestrator(
            scenarios_dir="scenarios/",
            output_dir="results/"
        )
        orchestrator.run_grid()
    """
    
    def __init__(
        self,
        scenarios_dir: Path | str,
        output_dir: Path | str,
        ground_truth_dir: Path | str = None,
        namespace: str = "poc-app"
    ):
        self.scenarios_dir = Path(scenarios_dir)
        self.output_dir = Path(output_dir)
        self.ground_truth_dir = Path(ground_truth_dir) if ground_truth_dir else Path("fixtures/ground_truth")
        self.namespace = namespace
        
        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "raw").mkdir(exist_ok=True)
        (self.output_dir / "tables").mkdir(exist_ok=True)
        (self.output_dir / "figures").mkdir(exist_ok=True)
        
        # Initialize components
        self.scenario_loader = ScenarioLoader(self.scenarios_dir)
        self.scenario_runner = ScenarioRunner(namespace=self.namespace)
        self.perturber = EvidencePerturber()
        self.baseline_comparator = BaselineComparator()
        self.metrics_calculator = MetricsCalculator()
        self.stats_analyzer = StatisticalAnalyzer()
    
    def run_grid(
        self,
        scenarios: List[Scenario] = None,
        configs: List[EvaluationConfig] = None,
        conditions: List[PerturbationCondition] = None,
        collect_ground_truth: bool = False
    ) -> Dict[str, Any]:
        """
        Run full evaluation grid.
        
        Args:
            scenarios: List of scenarios to evaluate (default: all)
            configs: List of configs to test (default: all baselines + evgate)
            conditions: List of perturbation conditions (default: all EC0-EC5)
            collect_ground_truth: Whether to collect new ground truth
        
        Returns:
            Dict with all results
        """
        
        print("\n" + "="*60)
        print("EVALUATION GRID EXECUTION")
        print("="*60)
        
        # Load scenarios
        if scenarios is None:
            scenarios = self.scenario_loader.load_all()
        print(f"\nScenarios: {len(scenarios)}")
        
        # Default configs: all baselines + evgate
        if configs is None:
            configs = [
                EvaluationConfig("B1-static", "B1"),
                EvaluationConfig("B2-infra", "B2"),
                EvaluationConfig("B3-random", "B3"),
                EvaluationConfig("B4-always-high", "B4"),
                EvaluationConfig("B5-always-low", "B5"),
                EvaluationConfig("B6-rule-based", "B6"),
                EvaluationConfig("evgate-full", "evgate", True, True, True)
            ]
        print(f"Configs: {len(configs)}")
        
        # Default conditions: all EC0-EC5
        if conditions is None:
            conditions = list(PerturbationCondition)
        print(f"Conditions: {len(conditions)}")
        
        total_runs = len(scenarios) * len(configs) * len(conditions)
        print(f"\nTotal evaluation runs: {total_runs}")
        print("="*60)
        
        # Step 1: Collect ground truth
        if collect_ground_truth:
            print("\n→ Collecting ground truth...")
            self._collect_ground_truth_for_scenarios(scenarios)
        
        # Step 2: Run grid
        print("\n→ Running evaluation grid...")
        results = []
        
        run_id = 0
        for scenario in scenarios:
            print(f"\n[Scenario {scenario.id}] {scenario.name}")
            
            # Load ground truth
            ground_truth = self._load_ground_truth(scenario.id)
            if not ground_truth:
                print(f"  ⚠️  No ground truth found, skipping")
                continue
            
            # Extract evidence from ground truth (simplified)
            evidence = self._extract_evidence(ground_truth)
            
            for config in configs:
                for condition in conditions:
                    run_id += 1
                    
                    # Apply perturbation
                    perturbed_evidence = self.perturber.apply_condition(evidence, condition)
                    
                    # Run analyzer
                    prediction = self._run_analyzer(config, scenario, perturbed_evidence)
                    
                    # Record result
                    result = {
                        "run_id": run_id,
                        "scenario_id": scenario.id,
                        "config": config.name,
                        "condition": condition.name,
                        "prediction": prediction,
                        "ground_truth": scenario.expected_behavior
                    }
                    results.append(result)
                    
                    print(f"  [{run_id}/{total_runs}] {config.name} + {condition.name}: "
                          f"{prediction.get('predicted_impact', 'N/A')}")
        
        # Step 3: Compute metrics
        print("\n→ Computing metrics...")
        metrics_report = self._compute_metrics_for_results(results)
        
        # Step 4: Statistical tests
        print("\n→ Running statistical tests...")
        stats_report = self._run_statistical_tests(results)
        
        # Step 5: Save results
        output_file = self.output_dir / "raw" / f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        final_report = {
            "metadata": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "n_scenarios": len(scenarios),
                "n_configs": len(configs),
                "n_conditions": len(conditions),
                "total_runs": total_runs
            },
            "results": results,
            "metrics": metrics_report,
            "statistical_tests": stats_report
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2)
        
        print(f"\n✓ Results saved: {output_file}")
        print("\nEvaluation complete!")
        
        return final_report
    
    def _collect_ground_truth_for_scenarios(self, scenarios: List[Scenario]):
        """Collect ground truth for all scenarios."""
        for i, scenario in enumerate(scenarios, 1):
            print(f"  [{i}/{len(scenarios)}] {scenario.id}")
            
            # Check if already collected
            gt_file = self.ground_truth_dir / f"{scenario.id}.json"
            if gt_file.exists():
                print(f"    ✓ Already collected, skipping")
                continue
            
            # Run scenario
            try:
                result = self.scenario_runner.run_scenario(scenario)
                result.save_json(gt_file)
            except Exception as e:
                print(f"    ✗ Failed: {e}")
    
    def _load_ground_truth(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Load ground truth from file."""
        gt_file = self.ground_truth_dir / f"{scenario_id}.json"
        
        if not gt_file.exists():
            return None
        
        with open(gt_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _extract_evidence(self, ground_truth: Dict[str, Any]) -> Dict[str, Any]:
        """Extract evidence from ground truth result."""
        # Simplified: in real implementation, parse from ground_truth
        return {
            "application_logs": [],
            "runtime_metrics": {},
            "infrastructure": ground_truth.get("pod_status", {})
        }
    
    def _run_analyzer(
        self,
        config: EvaluationConfig,
        scenario: Dict[str, Any],
        evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run analyzer with given config."""
        
        # If baseline, use baseline comparator
        if config.analyzer_name.startswith("B"):
            method = BaselineMethod[config.analyzer_name]
            return self.baseline_comparator.predict(method, scenario, evidence)
        
        # Otherwise, use evgate analyzer (stub for now)
        return self._stub_evgate_predict(scenario, evidence)
    
    def _stub_evgate_predict(
        self,
        scenario: Dict[str, Any],
        evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stub for evgate analyzer (replace with real implementation)."""
        # This is where you'll integrate Parts 1-3 code
        return {
            "predicted_impact": "medium",
            "confidence": 0.75,
            "method": "evgate",
            "reasoning": "Stub prediction"
        }
    
    def _compute_metrics_for_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute metrics across all results."""
        # Group by config
        by_config = {}
        for result in results:
            config = result["config"]
            if config not in by_config:
                by_config[config] = []
            by_config[config].append(result)
        
        # Compute metrics per config
        metrics = {}
        for config, config_results in by_config.items():
            # Extract predictions and ground truth
            # (Simplified: in real implementation, map expected_behavior to impact labels)
            predictions = [r["prediction"].get("predicted_impact", "unknown") for r in config_results]
            ground_truth = ["high" for _ in config_results]  # Stub
            
            config_metrics = self.metrics_calculator.compute_classification_metrics(
                predictions, ground_truth
            )
            metrics[config] = config_metrics
        
        return metrics
    
    def _run_statistical_tests(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run statistical significance tests."""
        # Compare evgate vs baselines
        # (Simplified implementation)
        return {
            "note": "Statistical tests would go here",
            "comparisons": []
        }
