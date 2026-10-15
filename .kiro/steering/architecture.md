# System Architecture

## Complete System Architecture

```
USER / RESEARCHER
        ↓
CHANGE SUBMISSION INTERFACE
(Web UI / CLI / REST API)
        ↓
CHANGE PARSER
        ↓
SUPPORTED CHANGE TYPES
 ├── IAM permission/access
 ├── Network/security rule
 └── Kubernetes NetworkPolicy/access
        ↓
EVIDENCE COLLECTION
 ├── Infrastructure Evidence
 │    ├── OpenTofu/Terraform
 │    ├── Kubernetes YAML
 │    ├── IAM/RBAC
 │    ├── Network rules
 │    └── NetworkPolicy
 │
 ├── Application Evidence
 │    ├── source code
 │    ├── configuration
 │    ├── environment variables
 │    ├── API calls
 │    ├── DB connections
 │    └── service/dependency definitions
 │
 └── Runtime Evidence
      ├── OpenTelemetry
      ├── Jaeger
      ├── logs
      ├── metrics
      └── observed service communication
        ↓
EVIDENCE NORMALIZATION
        ↓
UNIFIED EVIDENCE / DEPENDENCY GRAPH
        ↓
IMPACT PREDICTION
 ├── Security Impact Analyzer
 ├── Operational Risk Analyzer
 └── Affected Component Analysis
        ↓
PREDICTION OUTPUT
 ├── Security impact
 ├── Operational risk
 ├── Affected components
 ├── Confidence
 └── Explanation/supporting evidence
        ↓
EVIDENCE GATE
 ├── SAFE
 ├── RISKY
 └── INSUFFICIENT EVIDENCE
        ↓
IF RISKY:
MINIMAL SAFE REMEDIATION
        ↓
CONTROLLED VERIFICATION
        ↓
ACTUAL RUNTIME RESULT
        ↓
PREDICTION VS REALITY
        ↓
FINAL DECISION / RESEARCH REPORT
```

## Analyzer Structure

Per decision D7, the analyzer lives in `src/evgate/` to avoid namespace conflicts with `services/backend/`.

**UPDATED (C0 Bootstrap):** Reflects actual implementation structure per implementation.md §3.

```
src/
└── evgate/
    ├── __init__.py                # Package root
    ├── pipeline.py                # Part 3: Main analyze() function
    ├── cli.py                     # Part 3: CLI entry point
    │
    ├── contracts/                 # Part 3 (FROZEN): All Pydantic models
    │   ├── __init__.py           # Export schemas and version
    │   ├── vocab.py              # NodeId, Relationship, EvidenceType, etc.
    │   ├── evidence.py           # Evidence, Provenance, Coverage
    │   ├── bundle.py             # EvidenceBundle, ComponentInfo
    │   ├── change.py             # ChangeSpec, PathEffect, PermissionEffect
    │   ├── prediction.py         # Prediction, ComponentImpact
    │   ├── gate.py               # GateDecision, ReasonCode
    │   ├── remediation.py        # Remediation, AnalysisResult
    │   ├── groundtruth.py        # GroundTruthRun, GroundTruthLabel
    │   └── experiment.py         # ExperimentRecord
    │
    ├── stubs/                    # Part 3 (C0): Bootstrap stubs
    │   ├── __init__.py
    │   ├── evidence_stub.py      # collect_evidence_stub() -> G1
    │   └── analysis_stub.py      # analyze_stub() -> canned result
    │
    ├── change/                   # Part 2: Change parser
    │   ├── parser.py             # parse_change()
    │   ├── k8s.py                # Kubernetes YAML parser
    │   └── tofu.py               # OpenTofu plan parser
    │
    ├── evidence/                 # Part 2: Evidence extraction
    │   ├── infrastructure.py     # Deployments, Services, NetworkPolicy, RBAC
    │   ├── application.py        # Python AST, routes, readiness coupling
    │   ├── runtime.py            # Traces, logs, probes, audit
    │   ├── normalize.py          # Dedupe, conflict detection
    │   └── inventory.py          # Component discovery, alias resolution
    │
    ├── semantics/                # Part 2: Policy engines
    │   ├── network.py            # ReachabilityEngine for NetworkPolicy
    │   └── rbac.py               # PermissionEngine for RBAC
    │
    ├── workload/                 # Part 2: Workload generator
    │   ├── generator.py          # WorkloadProfile runner
    │   └── profiles/             # YAML profiles (full, short, partial)
    │
    ├── graph/                    # Part 3: Graph construction
    │   ├── builder.py            # build_graph(), dependency_view()
    │   ├── view.py               # Query/traversal utilities
    │   └── export.py             # JSON, DOT, PNG export
    │
    ├── prediction/               # Part 3: Impact prediction
    │   ├── propagate.py          # Operational propagation
    │   ├── security.py           # Security impact analyzer
    │   ├── operational.py        # Operational risk analyzer
    │   ├── belief.py             # Belief/sufficiency/confidence math
    │   └── calibrate.py          # Optional isotonic calibrator
    │
    ├── gate/                     # Part 3: Evidence gate
    │   └── gate.py               # decide() -> SAFE/RISKY/INSUFFICIENT
    │
    ├── report/                   # Part 3: Report generation
    │   ├── report.py             # Markdown/HTML reports
    │   └── templates/            # Report templates
    │
    ├── api/                      # Part 3: FastAPI endpoints
    │   └── ...                   # /changes /analyze /results /reports
    │
    ├── remediation/              # Part 4: Minimal remediation
    │   ├── network.py            # NetworkPolicy remediation
    │   ├── rbac.py               # RBAC remediation
    │   ├── tofu.py               # OpenTofu tfvars remediation
    │   ├── validate.py           # Static + dynamic validation
    │   └── requests.py           # EvidenceRequest generation
    │
    ├── scenarios/                # Part 4: Scenario management
    │   ├── loader.py             # Scenario spec loader
    │   ├── runner.py             # Ground-truth runner
    │   └── groundtruth.py        # Reachability/permission matrices
    │
    ├── evaluation/               # Part 4: Metrics and evaluation
    │   ├── baselines.py          # Evidence configs A/B/C/D
    │   ├── metrics.py            # Accuracy, precision, recall, etc.
    │   ├── stats.py              # Bootstrap, McNemar, Wilcoxon
    │   ├── perturb.py            # Evidence conditions EC0-EC5
    │   └── plots.py              # Matplotlib figures
    │
    └── common/                   # Part 3: Shared utilities
        ├── ids.py                # Deterministic ID generation
        ├── kube_guard.py         # assert_local_kind_context()
        └── io.py                 # File I/O utilities
```

## Infrastructure Structure

```
infrastructure/
└── opentofu/

kubernetes/
├── frontend/
├── backend/
├── database/
└── policies/

services/
├── frontend/
├── backend/
└── database/

telemetry/
├── opentelemetry/
├── jaeger/
└── prometheus/
```

## Evidence/Dependency Graph

**Graph Technology:** NetworkX (do NOT introduce Neo4j unless explicitly needed)

**Nodes represent:**
- services, pods, deployments
- databases, APIs
- network rules
- IAM identities, permissions
- infrastructure components

**Edges represent:**
- DEPENDS_ON
- CALLS
- CONNECTS_TO
- ALLOWED / DENIED
- HAS_PERMISSION
- DEPLOYED_AS
- OBSERVED_COMMUNICATION
- CONFIGURED_BY

**Edge attributes preserve:**
- evidence IDs
- source
- evidence type
- confidence
- provenance

**Graph purpose:**
- Dependency reasoning
- Affected-component identification
- Impact propagation
- Evidence aggregation
- Prediction
