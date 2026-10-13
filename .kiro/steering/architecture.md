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

```
src/
└── evgate/
    ├── main.py
    │
    ├── api/
    │   ├── changes.py
    │   ├── evidence.py
    │   ├── prediction.py
    │   ├── verification.py
    │   └── reports.py
    │
    ├── change_parser/
    │   ├── parser.py
    │   ├── iam.py
    │   ├── network.py
    │   └── kubernetes.py
    │
    ├── evidence/
    │   ├── infrastructure.py
    │   ├── application.py
    │   ├── runtime.py
    │   └── normalization.py
    │
    ├── graph/
    │   ├── builder.py
    │   ├── nodes.py
    │   └── edges.py
    │
    ├── prediction/
    │   ├── security.py
    │   ├── operational.py
    │   ├── impact.py
    │   └── confidence.py
    │
    ├── gate/
    │   └── evidence_gate.py
    │
    ├── remediation/
    │   └── minimal_remediation.py
    │
    ├── verification/
    │   ├── executor.py
    │   ├── telemetry.py
    │   └── comparator.py
    │
    ├── evaluation/
    │   ├── metrics.py
    │   ├── baselines.py
    │   └── experiments.py
    │
    ├── models/
    │   ├── change.py
    │   ├── evidence.py
    │   ├── prediction.py
    │   └── result.py
    │
    └── tests/
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
