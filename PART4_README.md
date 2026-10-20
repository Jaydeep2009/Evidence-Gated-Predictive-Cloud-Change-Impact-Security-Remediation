# Part 4: Scenarios, Remediation, Ground Truth, and Evaluation

## Overview

Part 4 implements the **experiment framework** for evaluating the Evidence-Gated system:

- **P4-01**: Scenario loader and validation
- **P4-02**: Application variants (for different experiment conditions)
- **P4-03**: Ground truth runner (collects actual system behavior)
- **P4-05/06/07**: Remediation generators (Network, RBAC, Tofu)
- **P4-09**: Evidence perturbation (systematic degradation)
- **P4-10**: Baseline comparisons (B1-B6)
- **P4-11**: Metrics calculation (classification, component, calibration)
- **P4-12**: Statistical analysis (bootstrap, McNemar, Wilcoxon)
- **P4-13**: Evaluation orchestrator (runs full grid)

## Directory Structure

```
src/evgate/
├── scenarios/        # Scenario loading and ground truth collection
│   ├── loader.py     # YAML scenario loader with validation
│   └── runner.py     # Ground truth runner (executes scenarios)
├── remediation/      # Remediation generators
│   ├── network.py    # NetworkPolicy fixes
│   ├── rbac.py       # Role/RoleBinding fixes
│   └── tofu.py       # OpenTofu/Terraform fixes
├── evaluation/       # Evaluation framework
│   ├── perturb.py    # Evidence perturbation (EC0-EC5)
│   ├── baselines.py  # Baseline methods (B1-B6)
│   ├── metrics.py    # Metrics calculation
│   ├── stats.py      # Statistical analysis
│   └── orchestrator.py  # Evaluation grid runner
├── stubs/            # Integration stubs (replace with Parts 1-3)
│   ├── part2_stubs.py  # Evidence collection stubs
│   └── part3_stubs.py  # Core analyzer stubs
├── contracts/        # Data contracts
└── common/           # Common utilities
    └── kube_guard.py # Safety guards

scenarios/            # 40 experiment scenarios (YAML)
├── N01-isolate-database-m2.yaml
├── N02-isolate-backend.yaml
├── N03-allow-backend-to-db.yaml
├── R01-restrict-pod-list.yaml
└── M01-network-and-rbac.yaml

kubernetes/policies/  # Policy manifests for scenarios
├── isolate-database.yaml (existing from Milestone 2)
├── isolate-backend.yaml
├── allow-backend-to-database.yaml
└── backend-role-restricted.yaml

fixtures/ground_truth/  # Ground truth JSON files (generated)
results/
├── raw/              # Raw evaluation results (JSON)
├── tables/           # LaTeX/CSV tables for paper
└── figures/          # Charts and plots

tests/                # Unit tests
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Requirements:**
- Python 3.11+
- pydantic, PyYAML, requests
- numpy, scipy (for metrics/stats)

### 2. Test Part 4 Modules

```bash
python test_part4.py
```

This tests all modules **without** requiring a Kubernetes cluster (uses stubs).

**Expected output:**
```
✓ PASS: Scenario Loader
✓ PASS: Remediation
✓ PASS: Evaluation
✓ PASS: Integration Stubs

Total: 4/4 tests passed
```

### 3. Validate Scenarios

```bash
python -c "
from src.evgate.scenarios.loader import ScenarioLoader
loader = ScenarioLoader('scenarios/')
report = loader.validate_all()
print(f\"Valid: {report['valid']}, Invalid: {report['invalid']}\")
"
```

### 4. Collect Ground Truth (Requires Kind Cluster)

**Prerequisites:**
- Kind cluster running (`kind create cluster --name poc-cluster`)
- Application deployed (`./scripts/deploy-all.sh`)

```bash
python -c "
import sys
sys.path.insert(0, 'src')
from evgate.scenarios.loader import ScenarioLoader
from evgate.scenarios.runner import ScenarioRunner
from pathlib import Path

loader = ScenarioLoader('scenarios/')
runner = ScenarioRunner(namespace='poc-app')

scenario = loader.load_scenario('N01-isolate-database-m2.yaml')
result = runner.run_scenario(scenario)
result.save_json(Path('fixtures/ground_truth/N01.json'))
"
```

### 5. Run Evaluation Grid

```bash
python -c "
import sys
sys.path.insert(0, 'src')
from evgate.evaluation.orchestrator import EvaluationOrchestrator

orchestrator = EvaluationOrchestrator(
    scenarios_dir='scenarios/',
    output_dir='results/'
)

# Run grid: scenarios × configs × perturbation conditions
orchestrator.run_grid(collect_ground_truth=False)  # Set True to collect GT
"
```

## Scenarios

### Categories

1. **Network (N01-N10)**: NetworkPolicy changes
   - N01: Isolate database (Milestone 2 reproduction)
   - N02: Isolate backend
   - N03: Allow backend→database (remediation)

2. **RBAC (R01-R10)**: Role/RoleBinding changes
   - R01: Restrict pod list permission

3. **Mixed (M01-M10)**: Combined network + RBAC
   - M01: Network policy + RBAC restriction

4. **Typo (T01-T10)**: Label/selector mismatches

### Scenario Format

Each scenario is a YAML file:

```yaml
id: N01
name: Isolate Database
category: network
description: Apply NetworkPolicy blocking backend→database
change_type: policy
expected_behavior: high_impact

probes:
  - url: http://localhost:30080
    method: GET
    expected_status: 503
    expected_content: "database"

policy_files:
  - kubernetes/policies/isolate-database.yaml
```

## Remediation

### Network Remediator

```python
from evgate.remediation.network import NetworkRemediator

remediator = NetworkRemediator()
suggestion = remediator.analyze_blocked_connection(
    source_pod="backend",
    source_namespace="poc-app",
    dest_service="database",
    dest_namespace="poc-app",
    dest_port=5432
)

print(suggestion.rationale)
print(suggestion.suggested_policy)
```

### RBAC Remediator

```python
from evgate.remediation.rbac import RBACRemediator

remediator = RBACRemediator()
suggestion = remediator.analyze_permission_denial(
    service_account="backend-sa",
    namespace="poc-app",
    required_verb="list",
    required_resource="pods"
)

print(suggestion.suggested_role)
print(suggestion.suggested_binding)
```

## Evaluation

### Perturbation Conditions

- **EC0**: Full evidence (baseline)
- **EC1**: No application logs
- **EC2**: No runtime metrics
- **EC3**: No infrastructure data
- **EC4**: 50% of each type
- **EC5**: All evidence + 20% noise

### Baseline Methods

- **B1**: Static analysis only
- **B2**: Infrastructure only
- **B3**: Random predictor
- **B4**: Always high impact
- **B5**: Always low impact
- **B6**: Simple rule-based

### Metrics

```python
from evgate.evaluation.metrics import MetricsCalculator

calc = MetricsCalculator()
metrics = calc.compute_classification_metrics(
    predictions=["high", "low", "high"],
    ground_truth=["high", "low", "medium"]
)

print(f"Accuracy: {metrics['accuracy']}")
print(f"F1 (macro): {metrics['f1_macro']}")
```

### Statistics

```python
from evgate.evaluation.stats import StatisticalAnalyzer

analyzer = StatisticalAnalyzer()

# Bootstrap CI
point, lower, upper = analyzer.bootstrap_confidence_interval(
    data=[0.85, 0.90, 0.87, 0.92, 0.88]
)
print(f"Mean: {point} [{lower}, {upper}]")

# McNemar's test
result = analyzer.mcnemar_test(
    method1_correct=[True, False, True, True],
    method2_correct=[True, True, True, False]
)
print(result['interpretation'])
```

## Integration with Parts 1-3

### Current: Stubs

Part 4 uses **stubs** for Parts 1-3:

```python
# Part 2: Evidence Collection (stub)
from evgate.stubs.part2_stubs import stub_collect_evidence
evidence = stub_collect_evidence("poc-app")

# Part 3: Core Analyzer (stub)
from evgate.stubs.part3_stubs import stub_analyze
result = stub_analyze(change_config, evidence)
```

### Future: Real Integration

Replace stubs with teammates' implementations:

```python
# Part 2: Real evidence collector
from evgate.evidence.collector import EvidenceCollector
collector = EvidenceCollector(namespace="poc-app")
evidence = collector.collect_all()

# Part 3: Real analyzer
from evgate.core.analyzer import analyze_change
result = analyze_change(change_config, evidence)
```

**Files to replace:**
- `src/evgate/stubs/part2_stubs.py` → teammates' Part 2 code
- `src/evgate/stubs/part3_stubs.py` → teammates' Part 3 code

## Safety Guards

**KubeGuard prevents accidental production execution:**

```python
from evgate.common.kube_guard import assert_local_kind_context

# Raises error if not in Kind cluster
assert_local_kind_context()
```

All ground truth collection and scenario execution automatically checks this.

## Results

### Raw Results

JSON files in `results/raw/` containing:
- All predictions (scenarios × configs × conditions)
- Classification metrics per config
- Statistical test results

### Paper Tables

Export to `results/tables/` for LaTeX:
- Classification metrics comparison
- Component metrics
- Statistical significance tests

### Figures

Generate in `results/figures/`:
- Precision-recall curves
- Calibration plots
- Bar charts comparing methods

## Current Status

✅ **Complete (100%)**:
- Scenario loader with validation
- Ground truth runner with probes
- Network, RBAC, Tofu remediators
- Evidence perturbation (EC0-EC5)
- Baseline methods (B1-B6)
- Metrics calculation
- Statistical analysis
- Evaluation orchestrator

📋 **5 scenarios authored** (N01-N03, R01, M01)
📋 **35 scenarios remaining** (N04-N10, R02-R10, M02-M10, T01-T10)

🔌 **Integration stubs** for Parts 1-3 (replace when teammates' code available)

## Next Steps

1. **Add more scenarios**: Create remaining 35 scenarios
2. **Test in Kind**: Run ground truth collection with real cluster
3. **Integrate Parts 1-3**: Replace stubs with teammates' implementations
4. **Run evaluation grid**: Execute full experiments
5. **Generate paper results**: Create tables and figures

## Contact

Part 4 Owner: [Your Name]
Teammates: Parts 1, 2, 3 available at https://github.com/Jaydeep2009/Evidence-Gated-Predictive-Cloud-Change-Impact-Security-Remediation
