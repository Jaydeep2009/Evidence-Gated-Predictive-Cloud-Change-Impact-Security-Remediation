# implementation.md — Evidence-Gated Predictive Cloud Change Impact & Security Remediation

**Status:** FINAL DRAFT v1.0 · **Audience:** AI IDE agents + the 4 team members · **Companion file:** `task.md` (who does what, in what order)

> **How an AI IDE must use this file**
> 1. Read §0–§5 completely (they are shared). Then read **only your Part's section** in §6–§9.
> 2. Contracts in §5 are **frozen**. Never change them inside a feature PR; open a PR labelled `contracts-change` and tag all four owners.
> 3. Never edit files owned by another Part (ownership table in §3). Shared files: follow the protocol in §3.
> 4. Write the test first, using the fixtures in §5.9. Every task is "done" only when its acceptance criteria in `task.md` pass in CI.
> 5. Do not add technologies outside §4. If you truly need one, justify it in the PR description.
> 6. Everything must be deterministic: seeded RNG, sorted outputs, no wall-clock in IDs.

---

## 0. Project in one paragraph

Given a **proposed cloud-security change** (Kubernetes NetworkPolicy, Kubernetes RBAC / IAM-style permission change, or an OpenTofu-managed network/access rule), the system collects **infrastructure + application + runtime evidence** from a *baseline* (pre-change) snapshot, builds a **unified evidence/dependency graph**, **predicts** security impact, operational risk, affected components and confidence, passes the prediction through an **evidence gate** (`SAFE` / `RISKY` / `INSUFFICIENT_EVIDENCE`), proposes a **minimal safer alternative** when risky, then **applies change and remediation in a local Kind cluster** to measure actual behaviour and compare it with the prediction. Four evidence configurations (A infra-only, B infra+app, C infra+runtime, D all+gate+remediation) are compared on a reproducible scenario set with measured ground truth.

**Conservative claim language (paper + README):** individual techniques (IaC analysis, dependency graphs, runtime monitoring, change-impact analysis, abstention, remediation) are *not* claimed novel. Use "Based on the literature reviewed…" and "this work investigates their integration…". Never write "no existing system…".

---

## 1. Design decisions that differ from the earlier milestone specs (and why)

These come from reviewing the repository as of Milestone 2. They are binding for this plan.

| ID | Earlier spec / state | Problem | Decision |
|----|---------------------|---------|----------|
| D1 | M3 spec feeds the **stage-2 (policy active)** verification JSON into the evidence pipeline as runtime evidence | **Label leakage**: the predictor would see the outcome it must predict | Prediction uses **only pre-change (baseline) evidence**. Post-change data is **ground truth only**. Enforced by `EvidenceBundle.phase == "pre_change"` + `assert_no_leakage()` (§5.4) |
| D2 | M3 AST patterns: `create_engine(DATABASE_URL)`, `requests.get(...)` | The real backend uses `psycopg2.connect(host=DATABASE_CONFIG["host"], …)` where the value comes from `os.getenv("DATABASE_HOST","database-service")` and is overridden by the Deployment env | App extractor needs **constant propagation + env resolution + cross-reference with Deployment env** (§7.4) |
| D3 | `nx.DiGraph` with "both" `CONNECTS_TO` and `FAILED_TO_CONNECT` edges | A `DiGraph` allows one edge per ordered pair | Use **`nx.MultiDiGraph`** with `key=relationship` (§8.1) |
| D4 | Conflict = `DEPENDS_ON` vs `FAILED_TO_CONNECT` | That is *not* a contradiction (a dependency can exist and be broken) | Conflict = **same claim, same snapshot, opposite polarity**, or *config says allowed* vs *runtime observed blocked* in the same snapshot (§7.7) |
| D5 | Confidence = `max + 0.1 / 0.2` for 2/3 sources | Ad-hoc; ignores that sources are correlated (env var and code often derive from the same config) | **Noisy-OR within a type, reliability-weighted across types, tuned on dev split, calibrated** (§8.2) |
| D6 | Evidence IDs = random `uuid4` | Non-reproducible | **Deterministic hash IDs** (§5.3) |
| D7 | Analyzer planned under `backend/app/...` (steering/architecture.md) | Collides with `services/backend` (the POC workload) | Analyzer package lives in **`src/evgate/`**. Update steering doc in bootstrap PR |
| D8 | `verify-network-policy.sh` Test 2 uses `curl -s http://localhost:30080/api/health` | nginx has **no `/api/` route** (`try_files … /index.html` returns 200) and `curl -s` ignores HTTP status, so "Frontend→Backend: success" is true **regardless of backend state**. The UI JS also calls `http://backend-service:8000/health` from the *browser*, which cannot resolve cluster DNS | Add nginx reverse proxy `location /api/ → backend-service:8000`, use `curl -sf` and check the JSON body. All new probes must assert on **content + status** (§6.2) |
| D9 | Socket codes: spec says 110 = timeout, evidence shows `11` (EAGAIN after 5 s) | Mapping drift | Extractor treats `{11,110}` as `timeout`; `111` refused; `113` host-unreachable; `101` net-unreachable |
| D10 | One scenario (database isolation) | Cannot support statistics or an ablation | **≥ 40 scenarios**, with SAFE cases, traps, conditional dependencies, RBAC and OpenTofu cases (§9.2) |
| D11 | Unpinned images (`poc-*:latest`, `postgres:15-alpine`) and 2 s/15–20 s sleeps for convergence | Reproducibility, flakiness | Pin tags + record digests; **poll-until-stable** instead of sleeps (§6.3, §9.3) |
| D12 | "IAM" requires a cloud account | Core must run locally | IAM-class changes = **Kubernetes RBAC (real enforcement in Kind)** as primary; AWS-style IAM JSON policies = static-only extension (§7.8). **Confirm with guide.** |

---

## 2. Scope

**In scope (v1):** three change categories — (1) **iam** → K8s RBAC/ServiceAccount permissions (+ IAM-JSON static extension), (2) **network** → network/security rules expressed as K8s NetworkPolicy and as OpenTofu resources applied to Kind, (3) **kubernetes** → NetworkPolicy/RBAC/ServiceAccount changes authored directly as YAML. Rule-based, explainable prediction. Local Kind only.

**Out of scope:** AWS/Azure/GCP, Neo4j, Kafka/Redis/Spark/Airflow/Elasticsearch, service mesh/Cilium-Hubble (future work), ML models beyond an optional isotonic/Platt calibrator, auto-applying changes to anything other than the local Kind context.

**Safety guard (mandatory):** every code path that runs `kubectl apply|delete|exec` or `tofu apply` must call `assert_local_kind_context()` which aborts unless `kubectl config current-context` starts with `kind-`.

---

## 3. Repository layout and ownership

```
.
├── pyproject.toml                  # P3 (bootstrap)   package: evgate (src layout)
├── Makefile                        # P3 owns; others append targets in own section
├── .github/workflows/ci.yml        # P3
├── CODEOWNERS                      # P3 (bootstrap)
├── config/
│   ├── analysis.yaml               # P3   thresholds, reliability weights
│   └── sinks.yaml                  # P2   outbound-call sink table for AST extractor
├── src/evgate/
│   ├── contracts/                  # FROZEN §5 (bootstrap by P3)
│   ├── evidence/                   # P2   infra.py app.py runtime.py normalize.py inventory.py
│   ├── semantics/                  # P2   network.py rbac.py
│   ├── change/                     # P2   parser.py k8s.py tofu.py
│   ├── workload/                   # P2   generator.py profiles/*.yaml
│   ├── graph/                      # P3   builder.py view.py export.py
│   ├── prediction/                 # P3   propagate.py security.py operational.py belief.py calibrate.py
│   ├── gate/                       # P3   gate.py
│   ├── pipeline.py                 # P3   analyze()
│   ├── cli.py  api/                # P3   argparse CLI + FastAPI
│   ├── report/                     # P3   report.py templates
│   ├── remediation/                # P4   network.py rbac.py tofu.py validate.py requests.py
│   ├── evaluation/                 # P4   baselines.py metrics.py stats.py perturb.py plots.py
│   ├── scenarios/                  # P4   loader.py runner.py groundtruth.py
│   └── common/                     # P3   ids.py kube_guard.py io.py
├── tests/
│   ├── unit/  integration/  cluster/  fixtures/      # each Part adds under own subfolder
├── fixtures/                       # §5.9 golden data. contracts+golden: P3 · ground_truth/m2: P1
├── testbed/                        # P1 (alias of existing layout, see below)
├── services/{frontend,backend}/    # P1 (existing). P4 may ADD new files only (§3 protocol)
├── kubernetes/{namespace.yaml,frontend,backend,database,policies}/   # P1 (existing)
├── telemetry/                      # P2   otel-collector/ jaeger/ prometheus/ (optional)
├── infrastructure/opentofu/        # P2 (modules) + P4 (scenario variants)
├── scenarios/                      # P4   *.yaml scenario specs + app variants
├── experiments/                    # P4   results/ (JSONL, committed) figures/ configs/
├── scripts/                        # P1 (existing). New scripts: owner's prefix (p2-*, p4-*)
├── docs/                           # each Part writes docs/<part>/…; existing docs/ stays
└── paper/                          # P4 assembles; every Part writes own section
```

*Existing files are not moved.* `testbed/` is only a documentation alias (see `task.md` P1-R1); do not relocate `services/`, `kubernetes/`, `scripts/`.

**Shared-file protocol.** Only these cross-part edits are allowed, each via a small PR reviewed by the file's owner:
| File | Owner | Allowed external change |
|------|-------|--------------------------|
| `services/backend/app/main.py` | P1 | P4: add **one line** `app.include_router(...)` per extended route module placed in new files `services/backend/app/routes_*.py` |
| `services/backend/Dockerfile` | P1 | **Do not edit.** P2 adds `services/backend/Dockerfile.otel` (new file) for the instrumented image |
| `kubernetes/*/deployment.yaml` | P1 | P2/P4 add **overlays** under `kubernetes/overlays/<name>/` (Kustomize, built into kubectl) — never edit baseline manifests |
| `src/evgate/contracts/*` | P3 | `contracts-change` PR only |
| `Makefile` | P3 | append targets under your own `# --- Part N ---` banner |

---

## 4. Tech stack (all open source)

| Layer | Tool | Notes |
|-------|------|-------|
| OS/dev | Windows → WSL2 Ubuntu, Docker, Git, GitHub | existing |
| Cluster | **Kind**, **kubectl** | pin Kind node image (`kindest/node:vX.Y.Z`) in `scripts/versions.env` (P1-R3) |
| IaC | **OpenTofu** (`tofu`) with `hashicorp/kubernetes` provider against Kind | consume `tofu show -json <plan>`; no HCL parser needed |
| Language | **Python 3.11** | analyzer env separate from the POC backend env |
| Models | **Pydantic v2** | contracts |
| Graph | **NetworkX ≥ 3** (`MultiDiGraph`) | no Neo4j |
| Parsing | **PyYAML**, stdlib `ast`, stdlib `json` | |
| Data/stats | **pandas**, **numpy**, **scipy** (McNemar via exact binomial, Wilcoxon, bootstrap), **matplotlib** | scipy/numpy/matplotlib are for evaluation only |
| API/CLI | **FastAPI** + uvicorn, stdlib **argparse** | |
| Telemetry | **OpenTelemetry** (Python auto-instrumentation + Collector), **Jaeger** (v2 image; verify tag), Prometheus + Grafana = *optional stretch* | |
| Tests | **pytest**; markers `unit`, `integration`, `cluster` (cluster tests are local-only) | |
| Quality | `black` (88 cols), `ruff`, type hints everywhere, `mypy --strict` on `contracts/` | |
| CI | GitHub Actions: lint + unit + integration (no cluster) | |
| Optional late | scikit-learn (isotonic/Platt calibrator only) | |

Pin exact versions in `requirements.lock` (generated with `pip-compile` or `uv pip compile`) at bootstrap; record tool versions in `experiments/environment.json` for every experiment run.

---

## 5. FROZEN CONTRACTS (v1.0)

Create these exactly (bootstrap PR, task `C0`). Add `schema_version = "1.0"` constant in `contracts/__init__.py`. JSON Schemas are exported by `make schemas` to `contracts/schemas/*.json`.

### 5.1 IDs and vocabularies

```python
# contracts/vocab.py
from enum import Enum

NodeId = str
# "<kind>:<namespace>/<name>"  (cluster-scoped: "<kind>:/<name>")
# kinds: component | workload | k8s-service | policy | principal | role | config | iac | external
# examples: component:poc-app/backend   k8s-service:poc-app/backend-service
#           policy:poc-app/isolate-database   principal:poc-app/backend-sa
#           permission:get:/configmaps   external:/node   external:/internet
# A *component* is the logical unit = Deployment pod-template label `app` (backend, database, frontend…).

class Relationship(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"                # app-level need: A needs B to function
    CALLS = "CALLS"                          # code/trace-level call A -> B
    CONNECTS_TO = "CONNECTS_TO"              # observed successful connection
    FAILED_TO_CONNECT = "FAILED_TO_CONNECT"  # observed failed connection (timeout/refused/unreachable)
    READINESS_COUPLED = "READINESS_COUPLED"  # A's readiness probe transitively exercises B
    ALLOWS = "ALLOWS"                        # config/effective policy allows path A -> B (port in metadata)
    DENIES = "DENIES"                        # config/effective policy denies path A -> B
    SELECTS = "SELECTS"                      # policy -> component
    EXPOSES = "EXPOSES"                      # k8s-service -> component
    DEPLOYED_AS = "DEPLOYED_AS"              # component -> workload
    CONFIGURED_BY = "CONFIGURED_BY"          # component/workload -> config/iac item
    RUNS_AS = "RUNS_AS"                      # component -> principal
    HAS_PERMISSION = "HAS_PERMISSION"        # principal -> permission:<verb>:<group>/<resource>
    NEEDS_PERMISSION = "NEEDS_PERMISSION"    # component -> permission (from code or audit log)
    OBSERVED_COMMUNICATION = "OBSERVED_COMMUNICATION"  # generic runtime link (log/flow)

class EvidenceType(str, Enum):
    INFRASTRUCTURE = "infrastructure"; APPLICATION = "application"; RUNTIME = "runtime"

class Classification(str, Enum):
    OBSERVED = "observed"; INFERRED = "inferred"; VERIFIED = "verified"

class Decision(str, Enum):
    SAFE = "SAFE"; RISKY = "RISKY"; INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
```

### 5.2 Provenance, coverage

```python
# contracts/evidence.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

class Provenance(BaseModel):
    source_type: Literal["file", "cluster", "trace", "log", "probe", "audit", "iac_plan", "manual"]
    source_path: str                  # repo-relative path or logical id (never absolute)
    line_number: int | None = None
    locator: str | None = None        # JSONPath / span id / k8s ref
    content_sha256: str | None = None
    extractor: str                    # e.g. "infra.networkpolicy"
    extractor_version: str = "1.0.0"
    extracted_at: datetime

class RuntimeCoverage(BaseModel):
    """What the runtime observation window actually exercised (needed to interpret ABSENCE)."""
    window_start: datetime
    window_end: datetime
    workload_id: str
    requests_total: int
    endpoints_exercised: list[str] = []     # "backend:GET /health"
    endpoints_known: list[str] = []         # from app evidence (route inventory)
    components_observed: list[str] = []
    spans_total: int = 0

    @property
    def endpoint_coverage(self) -> float:
        k = set(self.endpoints_known)
        return 1.0 if not k else len(k & set(self.endpoints_exercised)) / len(k)

class StaticCompleteness(BaseModel):
    """How trustworthy 'no call found in code' is for one component."""
    component: str
    files_analyzed: list[str] = []
    parse_errors: list[str] = []
    unresolved_dynamic_calls: int = 0
    @property
    def score(self) -> float:        # 1.0 = fully resolved
        if self.parse_errors or not self.files_analyzed:
            return 0.0
        return 1.0 / (1.0 + self.unresolved_dynamic_calls)
```

### 5.3 Evidence

```python
class Evidence(BaseModel):
    evidence_id: str                      # deterministic, see make_evidence_id()
    evidence_type: EvidenceType
    source: str                           # "kubernetes-networkpolicy" | "python-ast" | "jaeger-trace" | ...
    subject: NodeId
    relationship: Relationship
    object: NodeId
    polarity: Literal["supports", "refutes"] = "supports"   # a claim that the relationship holds / does not hold
    classification: Classification
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime                 # when the fact was true / observed
    snapshot_id: str                      # system state this fact belongs to, e.g. "baseline@<git-sha>"
    provenance: Provenance
    metadata: dict[str, Any] = {}

def make_evidence_id(e: "Evidence") -> str:
    import hashlib, json
    key = json.dumps([e.evidence_type.value, e.source, e.subject, e.relationship.value, e.object,
                      e.polarity, e.snapshot_id, e.metadata.get("key", "")], sort_keys=True)
    return "E-" + hashlib.sha1(key.encode()).hexdigest()[:12]
```
`metadata["key"]` = a short string disambiguating multiple facts with the same triple (e.g. `"port=5432"`). Timestamps are **not** hashed.

### 5.4 EvidenceBundle (the unit passed between Part 2 and Part 3)

```python
class ComponentInfo(BaseModel):
    node_id: NodeId
    labels: dict[str, str]
    aliases: list[str]                    # DNS forms, service names, deployment name, trace service.name
    namespace: str
    ports: list[int] = []
    readiness_path: str | None = None

class EvidenceBundle(BaseModel):
    schema_version: str = "1.0"
    bundle_id: str
    snapshot_id: str
    phase: Literal["pre_change"] = "pre_change"      # post-change bundles are rejected by the pipeline
    collected_at: datetime
    config_fingerprint: str                # sha256 of sorted manifest contents at snapshot time
    inventory: list[ComponentInfo]
    evidence: list[Evidence]
    coverage: RuntimeCoverage | None = None          # None == no runtime telemetry available
    static_completeness: list[StaticCompleteness] = []
    warnings: list[str] = []

    def assert_no_leakage(self) -> None:
        # reject any evidence whose snapshot_id differs from bundle.snapshot_id or whose provenance
        # path matches r"(post[-_]?change|stage[-_]?2|impact)" or whose metadata has "policy_active": true
        ...
```

### 5.5 ChangeSpec (output of Part 2 change parser, input to Part 3)

```python
# contracts/change.py
class Selector(BaseModel):
    components: list[NodeId]               # resolved against inventory (may be several)
    raw: dict[str, Any] = {}               # original selector for explanation

class PathEffect(BaseModel):
    kind: Literal["path"] = "path"
    src: NodeId
    dst: NodeId
    port: int | None
    protocol: Literal["TCP", "UDP", "SCTP"] = "TCP"
    before: Literal["allowed", "denied"]
    after: Literal["allowed", "denied"]

class PermissionEffect(BaseModel):
    kind: Literal["permission"] = "permission"
    principal: NodeId
    verb: str
    api_group: str
    resource: str
    resource_name: str | None = None
    namespace: str | None = None
    before: Literal["granted", "denied"]
    after: Literal["granted", "denied"]

class SecurityObjective(BaseModel):
    description: str
    kind: Literal["restrict_ingress", "restrict_egress", "least_privilege", "remove_wildcard", "custom"]
    target: NodeId | None = None

class ChangeSpec(BaseModel):
    schema_version: str = "1.0"
    change_id: str
    category: Literal["iam", "network", "kubernetes"]
    kind: Literal["k8s_networkpolicy", "k8s_rbac", "tofu_plan"]
    operation: Literal["add", "modify", "delete"]
    summary: str
    before_ref: str | None                 # path/dir of baseline manifests (or None for add)
    after_ref: str                         # path/dir/plan.json of proposed state
    effects: list[PathEffect | PermissionEffect]      # computed by semantics diff over the whole inventory
    direction: Literal["tightens", "loosens", "mixed", "neutral"]
    objective: SecurityObjective | None = None
    supported: bool = True
    parse_warnings: list[str] = []
```

### 5.6 Prediction, gate, remediation

```python
# contracts/prediction.py
class ComponentImpact(BaseModel):
    component: NodeId
    impact: Literal["unavailable", "degraded", "unaffected"]
    mechanism: Literal["direct_path_blocked", "readiness_coupled", "upstream_cascade", "permission_removed", "none"]
    probability: float
    evidence_ids: list[str]

class Prediction(BaseModel):
    security_impact: Literal["improves", "neutral", "degrades", "unknown"]
    security_delta: float                 # signed, see §8.3
    operational_risk: float               # 0..1
    operational_label: Literal["none", "low", "high", "unknown"]
    affected_components: list[ComponentImpact]
    belief: float                         # P(a required path/permission is removed)  (§8.2)
    sufficiency: float                    # 0..1 evidence sufficiency (§8.2)
    confidence: float                     # 0..1 P(decision correct) estimate
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    rationale: list[str]                  # human-readable, each cites evidence ids

# contracts/gate.py
class ReasonCode(str, Enum):
    POSITIVE_DEPENDENCY_SUPPORTED = "POSITIVE_DEPENDENCY_SUPPORTED"
    ABSENCE_WELL_SUPPORTED = "ABSENCE_WELL_SUPPORTED"
    LOW_SUFFICIENCY = "LOW_SUFFICIENCY"
    ABSENCE_NOT_INFORMATIVE = "ABSENCE_NOT_INFORMATIVE"   # low static completeness or low runtime coverage
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    NO_RUNTIME_EVIDENCE = "NO_RUNTIME_EVIDENCE"
    UNSUPPORTED_CHANGE = "UNSUPPORTED_CHANGE"
    SECURITY_DEGRADES = "SECURITY_DEGRADES"

class EvidenceRequest(BaseModel):
    action: Literal["run_workload", "exercise_endpoint", "provide_source", "refresh_snapshot", "resolve_conflict"]
    target: str
    why: str

class GateDecision(BaseModel):
    decision: Decision
    reasons: list[ReasonCode]
    thresholds_used: dict[str, float]
    evidence_requests: list[EvidenceRequest] = []

# contracts/remediation.py
class PathSpec(BaseModel):
    src: NodeId; dst: NodeId; port: int | None; protocol: str = "TCP"

class ManifestPatch(BaseModel):
    target_ref: str                       # file path or k8s ref
    format: Literal["yaml", "tofu_json"]
    content: str                          # full replacement document(s)

class StaticValidation(BaseModel):
    preserves_required: bool
    keeps_objective: bool
    introduces_wildcard: bool
    checked_with: Literal["semantics_engine"] = "semantics_engine"
    details: list[str] = []

class Minimality(BaseModel):
    allowed_pairs: int                    # (src,dst,port) pairs allowed by remediation among candidates
    required_pairs: int
    excess_pairs: int                     # allowed - required
    ratio: float                          # allowed/required (1.0 optimal)

class Remediation(BaseModel):
    remediation_id: str
    strategy: Literal["narrow_allow", "scope_down_permission", "retain_required_paths"]
    patches: list[ManifestPatch]
    preserves: list[PathSpec]
    keeps_denied: list[PathSpec]
    static_validation: StaticValidation
    minimality: Minimality
    rationale: list[str]

class AnalysisResult(BaseModel):
    schema_version: str = "1.0"
    change_id: str
    evidence_config: Literal["A", "B", "C", "D", "D_NOGATE"]
    gate_enabled: bool
    prediction: Prediction
    gate: GateDecision
    graph_ref: str | None                 # path to exported graph json
    remediation: Remediation | None = None
    versions: dict[str, str] = {}         # code git sha, config hash, schema_version
```

### 5.7 Ground truth and experiment records

```python
# contracts/groundtruth.py
class ProbeSpec(BaseModel):
    probe_id: str
    kind: Literal["http", "tcp", "k8s_auth"]
    via: Literal["host_nodeport", "pod_exec", "port_forward"]
    target: str                            # URL / host:port / "<sa> <verb> <resource>"
    expect_status: int | None = None
    expect_body_contains: str | None = None   # content check (see D8)
    touches: list[NodeId]                  # components this probe exercises
    required: bool = True                  # a failing required probe == operational failure

class ProbeResult(BaseModel):
    probe_id: str; passed: bool; observed: str; attempts: int; latency_ms: float | None = None

class ComponentState(BaseModel):
    ready: bool; phase: str; restart_count: int

class EnvironmentFingerprint(BaseModel):
    kind: str; kubectl: str; tofu: str | None; docker: str
    node_image: str; image_digests: dict[str, str]; git_sha: str; manifests_sha256: str

class GroundTruthRun(BaseModel):
    scenario_id: str; run_index: int
    phase: Literal["baseline", "post_change", "post_remediation", "recovered"]
    started_at: datetime; stable_after_s: float
    probes: list[ProbeResult]
    components: dict[NodeId, ComponentState]
    reachability: dict[str, bool]          # "src->dst:port" -> reachable, measured by pod_exec TCP connect
    permissions: dict[str, bool]           # "<sa>|verb|resource" -> allowed, via `kubectl auth can-i`
    env: EnvironmentFingerprint

class GroundTruthLabel(BaseModel):
    scenario_id: str
    operational_failure: bool
    affected_components: list[NodeId]
    security_effect: Literal["improves", "neutral", "degrades"]
    risky_label: bool                      # operational_failure or security_effect == "degrades"
    stable: bool                           # all R runs agree
    runs: int
    remediation_restores_function: bool | None = None
    remediation_keeps_objective: bool | None = None

# contracts/experiment.py
class ExperimentRecord(BaseModel):
    experiment_id: str                     # deterministic: sha1(scenario|config|condition|code_sha)
    scenario_id: str
    split: Literal["dev", "test"]
    evidence_config: Literal["A", "B", "C", "D", "D_NOGATE"]
    evidence_condition: Literal["EC0", "EC1", "EC2", "EC3", "EC4", "EC5"]
    gate_enabled: bool
    result: AnalysisResult
    label: GroundTruthLabel
    correct_operational: bool | None       # None if abstained
    abstained: bool
    set_precision: float; set_recall: float
    notes: str = ""
```

### 5.8 Public function interfaces between Parts (also frozen)

```python
# P2 -> P3/P4
def collect_evidence(manifests_dir: Path, source_dirs: list[Path], runtime_dir: Path | None,
                     snapshot_id: str, *, max_runtime_age_s: int | None = None) -> EvidenceBundle: ...
def parse_change(kind: str, before: Path | None, after: Path, bundle: EvidenceBundle) -> ChangeSpec: ...
class ReachabilityEngine:                # semantics.network
    def __init__(self, inventory: list[ComponentInfo], policies: list[dict]): ...
    def allowed(self, src: NodeId, dst: NodeId, port: int, protocol: str = "TCP") -> bool: ...
    def matrix(self, ports: dict[NodeId, list[int]]) -> dict[tuple[NodeId, NodeId, int], bool]: ...
class PermissionEngine:                  # semantics.rbac
    def __init__(self, docs: list[dict]): ...
    def can(self, principal: NodeId, verb: str, api_group: str, resource: str,
            namespace: str | None = None, name: str | None = None) -> bool: ...

# P3 -> P4
def analyze(change: ChangeSpec, bundle: EvidenceBundle, *, evidence_config: str = "D",
            gate_enabled: bool = True, config_path: Path = Path("config/analysis.yaml")) -> AnalysisResult: ...

# P4 -> internal / P3 report
def remediate(result: AnalysisResult, change: ChangeSpec, bundle: EvidenceBundle) -> Remediation | None: ...
def run_scenario(spec_path: Path, runs: int = 3) -> tuple[list[GroundTruthRun], GroundTruthLabel]: ...
```

### 5.9 Golden fixtures (created in bootstrap, task `C0`; used by every part)

Created by **P3** from the Milestone-1/2 repo, stored under `fixtures/golden/`. P2's extractors must **reproduce G1 (modulo ids/timestamps)**; P3 develops against G1–G3 before P2 finishes; P4 develops against G1 + `ChangeSpec M2`.

| Fixture | Content |
|---------|---------|
| `G1_bundle_full.json` | Pre-change bundle for the M2 app (snapshot `baseline@m2`): infra (`isolate-database` absent in baseline; Service→component EXPOSES; ports; Deployment env `DATABASE_HOST=database-service`; backend readiness path `/health`), app (`backend DEPENDS_ON database` via `psycopg2.connect` at `main.py:41`, env key `DATABASE_HOST`; `backend READINESS_COUPLED database`; routes `/health /live /`), runtime (baseline JSON `…132130.json`: `CONNECTS_TO backend→database`, readiness ready; coverage full) |
| `G2_bundle_no_runtime.json` | G1 without runtime evidence, `coverage=None` |
| `G3_bundle_conflict.json` | G1 + infra `DENIES backend→database` in same snapshot vs runtime `CONNECTS_TO` (config drift) |
| `G4_bundle_low_coverage.json` | G1 but coverage `endpoint_coverage = 0.2` and an endpoint known from AST not exercised |
| `change_M2.json` | ChangeSpec for `kubernetes/policies/isolate-database.yaml` (add; tightens; effects: `backend→database:5432 allowed→denied`; `frontend→database` already denied-by-nothing? list all inventory pairs); objective: restrict_ingress on database |
| `gt_M2_label.json` | `GroundTruthLabel`: operational_failure=true; affected={backend, database, frontend (if proxied)}; security improves |
| `ground_truth/m2/*.json` | **Copies** (not moves) of the three canonical runs `…132130` (baseline), `…133342` (impact), `…135142` (recovered). P1 owns |

---

## 6. PART 1 — Testbed & Ground-Truth Foundation (EXISTING WORK)

**Owner:** the member who built Milestones 1–2. **No new implementation is required beyond §6.4.**

### 6.1 What exists (do not rewrite)

* Kind cluster `poc-cluster`, namespace `poc-app`, NodePort 30080.
* `services/frontend` (nginx + static HTML), `services/backend` (FastAPI `/health` doing a real `SELECT 1`, `/live`, `/`), PostgreSQL 15-alpine deployment.
* Manifests under `kubernetes/{namespace.yaml,frontend,backend,database}`; readiness probe = `/health` (DB-coupled), liveness = `/live`.
* Experiment policy `kubernetes/policies/isolate-database.yaml` (`ingress: []` on `app=database`).
* Scripts: `setup-cluster.sh build-images.sh deploy-all.sh verify-baseline.sh apply-network-policy.sh remove-network-policy.sh verify-network-policy.sh cleanup.sh`.
* Evidence of the 3-stage experiment (absent → present → absent) with JSON outputs; docs in `docs/`.

### 6.2 Contract this Part exposes to others (already satisfied)

* A reproducible cluster in ≤ 10 commands (`README.md`).
* Ground-truth JSON for M2 (three canonical files).
* Stable component names: `frontend`, `backend`, `database` (label `app`).

### 6.3 Known issues others will work around (documented, not blocking)

* D8: Frontend→Backend probe is a false positive until the nginx proxy fix (P1-R2). **P4's runner uses its own content-checked probes**, so the experiments do not depend on this fix; the fix only makes the demo and README truthful.
* D11: sleeps instead of poll-until-stable. P4's runner implements polling.

### 6.4 Closing tasks (small; see `task.md` P1-R1…R3)

1. **R1 Fixtures:** copy the three canonical JSON files + `baseline-verification.json` into `fixtures/ground_truth/m2/` with a `README.md` stating which stage each file is and its SHA-256 (use `docs/milestone-2-evidence-hashes.txt`; originals stay untouched).
2. **R2 Frontend→Backend path:** add to `services/frontend/nginx.conf`
   ```nginx
   location /api/ {
       proxy_pass http://backend-service:8000/;
       proxy_connect_timeout 3s; proxy_read_timeout 5s;
   }
   ```
   change the UI to fetch `/api/health`, and change Test 2 in both verify scripts to `curl -sf http://localhost:30080/api/health | grep -q '"status"'` (assert status code and body). Re-run Stage 1–3 once; commit new outputs under `fixtures/ground_truth/m2_v2/` (do not overwrite old evidence).
3. **R3 Pin versions:** create `scripts/versions.env` (kind, kubectl, node image tag, `postgres:15.x-alpine`, python base tag) and make `build-images.sh` tag images with the git short SHA in addition to `latest`; write `scripts/print-env.sh` that emits an `EnvironmentFingerprint` JSON (§5.7) including image digests.

---

## 7. PART 2 — Evidence & Change Semantics

Packages: `evgate.evidence`, `evgate.semantics`, `evgate.change`, `evgate.workload`; also `telemetry/`, `services/backend/Dockerfile.otel`, `infrastructure/opentofu/modules/`.

### 7.1 Inventory and entity resolution (`evidence/inventory.py`)

1. Load every Kubernetes YAML under `manifests_dir` (multi-doc supported). Kinds: Namespace, Deployment, Service, NetworkPolicy, ServiceAccount, Role, ClusterRole, RoleBinding, ClusterRoleBinding, ConfigMap.
2. **Component** = distinct `spec.template.metadata.labels.app` of each Deployment. `node_id = component:<ns>/<app>`. `labels` = pod-template labels. `ports` = container ports. `readiness_path` from `readinessProbe.httpGet.path`.
3. **Aliases** for resolving tokens (DNS names, trace `service.name`, env values) to a component: Deployment name; each Service whose `spec.selector ⊆ labels` gives `svc`, `svc.ns`, `svc.ns.svc`, `svc.ns.svc.cluster.local`; the `app` label. Alias collisions → warning + confidence × 0.7.
4. `resolve(token) -> NodeId | None` is used by every extractor; unresolved tokens create **no** edge but increment a warning.

### 7.2 Infrastructure extractors (`evidence/infra.py`, one function per kind; each returns `list[Evidence]`)

| Input | Evidence emitted (infrastructure type) |
|-------|----------------------------------------|
| Deployment | `component DEPLOYED_AS workload` (1.0, observed); `component CONFIGURED_BY config:<ns>/Deployment/<n>#env.<KEY>` per env var; **env values that resolve to a component alias → `component DEPENDS_ON target`**, confidence **0.5**, classification `inferred`, `metadata.key="env:<KEY>"` (this is the *only* dependency signal available to baseline A) |
| Service | `k8s-service EXPOSES component` (port, targetPort) |
| NetworkPolicy | `policy SELECTS component`; and, via `ReachabilityEngine`, effective `ALLOWS`/`DENIES` evidence for **all** ordered component pairs and their ports (metadata `port`, `policy_names`), confidence 1.0 observed |
| ServiceAccount/Role/RoleBinding | `component RUNS_AS principal`; `principal HAS_PERMISSION permission:<verb>:<group>/<resource>` expanded per verb/resource (wildcards kept as `*` plus flag `metadata.wildcard=true`) |
| OpenTofu plan JSON | see §7.8 — produces the same evidence kinds plus `component CONFIGURED_BY iac:<address>` |

Policies in the **baseline** are included; the **proposed** change is not evidence (it is the `ChangeSpec`).

### 7.3 Policy semantics engine (`semantics/network.py`, `semantics/rbac.py`)

**NetworkPolicy semantics (implement exactly):**
* Pod is *ingress-isolated* iff ≥1 policy in its namespace selects it (`podSelector` matches, empty selector = all pods) and `policyTypes` contains `Ingress` (if `policyTypes` absent: Ingress is implied; Egress implied only if `egress` key present). Same for egress.
* Isolated for ingress ⇒ only traffic matched by the **union** of `ingress` rules is allowed. `ingress: []` or no matching rule ⇒ deny all. A rule with omitted/empty `from` ⇒ all sources; omitted `ports` ⇒ all ports.
* `from[].podSelector` (same namespace), `namespaceSelector`, combined selectors (AND semantics when in the same `from` item), `ipBlock` (treat as `external:/internet`).
* A path src→dst:port is allowed iff (src not egress-isolated OR some egress rule allows) **and** (dst not ingress-isolated OR some ingress rule allows).
* Always-allowed pseudo-sources: `external:/node` for kubelet probes (probes **do not** traverse policies), NodePort traffic is treated as source `external:/node` to the target pod.
* Policies are additive; there is no deny rule.

**RBAC semantics:** aggregate Roles/ClusterRoles (including `aggregationRule` by label selector), bindings to ServiceAccount subjects (and groups `system:serviceaccounts[:ns]`), wildcards in `verbs/resources/apiGroups`, `resourceNames`, subresources (`pods/exec`). `can()` must equal `kubectl auth can-i` for the cluster default behaviour (no admission/impersonation).

**Cross-check tests (cluster marker, local):** for ≥10 policies and ≥10 role sets, engine output must equal the measured matrices from P4's `groundtruth` module. Any disagreement is a bug in the engine **or** a documented limitation (e.g. CNI behaviour), recorded in `docs/p2/semantics-validation.md`. This addresses the literature point that *policy present ≠ policy enforced / scanner pass ≠ semantic correctness*.

### 7.4 Application extractor (`evidence/app.py`) — AST + config

Input: service source dir(s) + `manifests_dir` (for env resolution). Pure static analysis, never executes code.

**Algorithm**
1. Parse every `*.py` with `ast`; collect parse errors → `StaticCompleteness.parse_errors`.
2. **Route inventory:** functions decorated with `@app.get|post|put|delete|patch|router.*("<path>")` → `endpoints_known = ["<component>:<METHOD> <path>"]`.
3. **Constant environment per module:** record assignments of literals, dict literals, `os.getenv(K, default)` / `os.environ.get(K, default)` / `os.environ[K]` as `EnvRef(key=K, default=default)`; support subscript `DICT["k"]` resolution and f-strings of resolved parts; one level of local function return propagation.
4. **Sink table** `config/sinks.yaml` (editable data, not code):
   ```yaml
   sinks:
     - match: "psycopg2.connect"   ; kind: postgres  ; host_arg: host ; port_arg: port ; default_port: 5432
     - match: "sqlalchemy.create_engine" ; kind: sqlalchemy ; url_arg: 0
     - match: "requests.(get|post|put|delete|request)" ; kind: http ; url_arg: 0
     - match: "httpx.(get|post|Client|AsyncClient)" ; kind: http ; url_arg: 0
     - match: "kubernetes.client.*Api.*" ; kind: k8s_api ; maps_to_permission: true
   ```
   For each call matching a sink: resolve the host/URL argument with step 3. If it resolves to a string → apply `inventory.resolve(host)`. If it is an `EnvRef` → look up the **Deployment env** of this component in `manifests_dir` (value overrides default); if not set use default. Unresolved → `unresolved_dynamic_calls += 1`, emit evidence with confidence 0.3 and `metadata.unresolved=true` only if the target is guessable (default exists), otherwise no edge.
5. **Evidence emitted:** `component DEPENDS_ON target` (application, `inferred`, confidence 0.85 if resolved via env+manifest, 0.7 if default only, 0.3 if unresolved-default), `provenance.line_number` = call site, `metadata = {sink, env_key, resolved_via, port}`.
6. **Readiness coupling:** read the component's `readinessProbe.httpGet.path`; find the handler for that path; compute a **bounded call graph (depth ≤ 3, same module + imported project modules)** from the handler; if it reaches a sink call → `component READINESS_COUPLED target` (application, inferred, 0.85). This is what lets the predictor explain *why a blocked DB path makes the backend NotReady*.
7. **K8s API calls:** `kubernetes` client calls map via a small table (`read_namespaced_config_map → get configmaps`, `list_namespaced_secret → list secrets`, …) to `component NEEDS_PERMISSION permission:<verb>:<group>/<resource>` (application, inferred, 0.8).
8. **Config files:** `.env`, `*.yaml|yml|json|toml|ini` in the service dir, `Dockerfile` (`EXPOSE`, `ENV`), `requirements.txt|pyproject.toml`. Emit weak *capability* evidence (`library psycopg2 present → possible postgres client`, confidence 0.4, classification `inferred`, `metadata.capability=true`). Capability evidence **never** alone creates RISKY.
9. `StaticCompleteness` per component as in §5.2.

**Golden check:** on `services/backend/app/main.py` + `kubernetes/backend/deployment.yaml` the extractor must yield exactly: `backend DEPENDS_ON database` (line of `psycopg2.connect`, resolved via env `DATABASE_HOST=database-service`, port 5432), `backend READINESS_COUPLED database`, endpoints `/health /live /`, `unresolved_dynamic_calls=0`.

### 7.5 Runtime extractors (`evidence/runtime.py`)

All runtime evidence is `evidence_type=runtime`. **Use only baseline-phase inputs** when building a pre-change bundle (the caller passes a directory of baseline captures).

1. **Verification/probe JSON (Milestone-2 format):** mapping `socket_code` `0→CONNECTS_TO` (verified, 1.0); `11|110→FAILED_TO_CONNECT(reason=timeout)`; `111→refused`; `113→host_unreachable`; `101→net_unreachable`; `backend_health.readiness` → `ComponentState` metadata (not an edge). Reject files whose `policy.status == "active"` in pre-change mode (D1).
2. **Traces (OTel → Jaeger JSON):** parse `data[].spans[]` + `processes`. A client span with `db.system`, `peer.service`, `server.address`, `net.peer.name` or `http.url` host → resolve via inventory → `component CONNECTS_TO target` (observed, confidence `min(0.95, 0.6 + 0.35·(1-exp(-n/5)))` where `n` = span count; metadata: count, p50/p95 latency, operations). Cross-service parent/child references → `CALLS`. Support reading either the Jaeger HTTP API (`/api/traces?service=…`) or archived JSON files (tests use files).
3. **Logs:** `logs/<component>.log` captured with `kubectl logs --timestamps`. Parsers: uvicorn access log, nginx access log (format `$remote_addr … $upstream_addr`; P2 supplies a `log_format` ConfigMap overlay), psycopg2 error lines. Map pod IP → component through `kubectl get pods -o json` captured at snapshot time. Emit `OBSERVED_COMMUNICATION` (0.7) and `FAILED_TO_CONNECT` (0.8) when errors appear.
4. **Kubernetes audit log (RBAC scenarios):** Kind config with audit policy (`kubeadmConfigPatches` + mounted `audit-policy.yaml`, level `Metadata`). Parse JSON lines → `user.username = system:serviceaccount:<ns>:<sa>`, `verb`, `objectRef.resource`, `responseStatus.code` → `component NEEDS_PERMISSION permission:<verb>:<group>/<resource>` (observed, 0.9; 403 results become `polarity=refutes` on `HAS_PERMISSION`).
5. **Coverage:** `RuntimeCoverage` computed from the workload profile that ran (requests, endpoints exercised = (component, method, path) triples seen in traces/logs) vs `endpoints_known` from §7.4. **If no telemetry is present, `coverage=None`.**
6. **Absence is never emitted as refutation.** There is no evidence object for "not observed"; the gate reads `coverage` instead (§8.2).

### 7.6 Telemetry stack and workload generator

* `telemetry/otel-collector/` (OTLP receiver → Jaeger exporter + file exporter that archives OTLP JSON for fixtures), `telemetry/jaeger/` (all-in-one, in-memory), optional `telemetry/prometheus/`. `make telemetry-up|down`.
* `services/backend/Dockerfile.otel`: same base as Part 1's Dockerfile plus `opentelemetry-distro`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-{fastapi,psycopg2,requests}`; started with `opentelemetry-instrument uvicorn …`; env `OTEL_SERVICE_NAME=backend`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.telemetry:4317`. Deployed through overlay `kubernetes/overlays/otel/`.
* **Workload generator** `evgate.workload.generator`: input `WorkloadProfile` YAML (`id, duration_s, rate_rps, seed, requests: [{method, path, weight}]`); runs from the host against the NodePort (or in-cluster Job); writes `workload_run.json` (counts per endpoint). Provided profiles: `full` (every known endpoint), `short` (only `/api/health` for 5 s), `partial` (50 % of endpoints), `idle` (none).

### 7.7 Normalizer (`evidence/normalize.py`)

1. **Validate** against contracts (confidence range, timestamps ≤ now, relationship in enum).
2. **Deduplicate** by `evidence_id`; keep the first, merge provenance list in `metadata.also_seen_in`.
3. **Conflict detection** (D4). Two evidence items conflict iff same `(subject, object, snapshot_id)` and either (a) same relationship, opposite polarity, or (b) infra `DENIES(a→b,port)` vs runtime `CONNECTS_TO(a→b)`, or infra `ALLOWS` vs runtime `FAILED_TO_CONNECT` **in the same snapshot**. Mark `metadata.conflicts_with=[ids]` on both; keep both.
4. **Staleness (replaces fixed 1 h):** runtime evidence with `observed_at < last_config_change_time` of the bundle (derived from `config_fingerprint` history, or `max_runtime_age_s` if given) → `metadata.stale=true`, `confidence = max(0.1, confidence − 0.3)`, add bundle warning.
5. Return deterministic ordering (sort by `evidence_type, subject, relationship, object, evidence_id`).

### 7.8 Change parser and OpenTofu (`change/`)

`parse_change(kind, before, after, bundle) -> ChangeSpec`:
1. Load baseline state (manifests in `before` or the bundle's policies) and proposed state (`after`).
2. Build engines for both states; compute `effects` as **all** inventory pairs/ports and all principal/verb/resource tuples whose result differs. Do not hard-code "database is blocked" anywhere.
3. `direction`: `tightens` if only allowed→denied / granted→denied, `loosens` if only the reverse, `mixed`, else `neutral`.
4. `objective` is read from an optional annotation `evgate.io/objective: restrict_ingress:database` on the changed resource, else inferred: NetworkPolicy ⇒ `restrict_ingress` on selected components; Role/RoleBinding removal ⇒ `least_privilege`; wildcard removal ⇒ `remove_wildcard`.
5. Unsupported resource kinds → `supported=False` + `parse_warnings` (gate returns `INSUFFICIENT_EVIDENCE/UNSUPPORTED_CHANGE`).
6. **OpenTofu:** `tofu init && tofu plan -out=plan.bin && tofu show -json plan.bin > plan.json` (via `scripts/p2-tofu-plan.sh`; no `apply` in the parser). Read `resource_changes[*]` for `kubernetes_network_policy_v1`, `kubernetes_role_v1`, `kubernetes_role_binding_v1` (names may vary with provider version — verify); convert `change.before/after` into manifest-shaped dicts, then reuse §7.3 engines. Evidence for baseline IaC: `component CONFIGURED_BY iac:<resource address>`.
   * Modules provided in `infrastructure/opentofu/modules/{network_policy,rbac}` with variables so P4's scenarios are parameter files (`*.tfvars`).
7. **IAM-JSON extension (optional, static only):** parse AWS-style policy JSON into `PermissionEffect` with an offline evaluator (wildcards, `Deny` precedence, no conditions); mark scenarios `ground_truth: none` — evaluate only prediction-vs-spec, not prediction-vs-runtime. Do not claim runtime validation for these.

### 7.9 Tests Part 2 must ship

* Unit: each extractor against fixtures (valid / malformed / empty / missing file), env-resolution cases (default vs manifest override vs unresolved), semantics truth-tables (≥ 25 NetworkPolicy cases incl. AND/OR selector semantics; ≥ 15 RBAC cases), normalizer (duplicate, conflict, stale, leakage rejection).
* Contract test: `collect_evidence()` over the repo reproduces `G1_bundle_full.json` (ignoring ids' timestamps).
* Property test: `ReachabilityEngine` with an empty policy list returns allowed for all pairs.

---

## 8. PART 3 — Core Engine, Graph, Prediction, Gate, Interfaces

Packages: `evgate.graph`, `evgate.prediction`, `evgate.gate`, `evgate.pipeline`, `evgate.cli`, `evgate.api`, `evgate.report`, `evgate.common`, `contracts/` (steward), CI, Makefile, `config/analysis.yaml`.

### 8.1 Graph (`graph/builder.py`, `view.py`, `export.py`)

* `build_graph(bundle, mask) -> nx.MultiDiGraph`. Nodes from `inventory` + every `subject/object` id, attrs `kind, namespace, labels`. For each evidence item `add_edge(subject, object, key=f"{relationship}:{evidence_id}")` is **too granular**; use **one edge per `(subject, object, relationship)`** with `key=relationship.value` and aggregated attrs:
  `evidence_ids[]`, `by_type = {infrastructure:[ids], application:[ids], runtime:[ids]}`, `conf_by_type = {type: noisy_or(confs)}`, `polarity_counts`, `conflicted: bool`, `snapshot_id`, `sources[]`.
* **Mask:** `mask ⊆ {infrastructure, application, runtime}` filters evidence *before* aggregation. A = {infra}, B = {infra, app}, C = {infra, runtime}, D = all.
* **Dependency view** `dependency_view(G) -> dict[(src,dst), DependencyRecord]` where `DependencyRecord{belief, conf_by_type, relationships[], has_conflict}`; counts as dependency evidence: `DEPENDS_ON, CALLS, CONNECTS_TO, READINESS_COUPLED` (supporting). `FAILED_TO_CONNECT` in the **baseline** means the dependency is already broken → lowers belief and marks `already_failing`.
* Export: `graph.json` (`nx.node_link_data(G, edges="edges")`), `graph.dot`; `make graph-figure` renders a PNG for the paper (matplotlib/networkx; dot optional).

### 8.2 Belief, sufficiency, confidence (`prediction/belief.py`) — reference formulas, implement exactly

Config (`config/analysis.yaml`, **initial guesses; tuned on dev split only, then frozen**):
```yaml
reliability: {infrastructure: 0.60, application: 0.80, runtime: 0.90}
tau_pos: 0.50              # belief >= tau_pos  => dependency considered present
tau_risk: 0.50             # operational_risk >= tau_risk => operational label high
tau_suff_pos: 0.60         # sufficiency needed to call RISKY from positive evidence
tau_suff_neg: 0.70         # sufficiency needed to call SAFE from absence
min_endpoint_coverage: 0.50
top_k_per_type: 3
```
For a pair `(s,d)`:
* Per type `t`: `c_t = 1 − Π_{i in top_k supports of type t} (1 − conf_i)` (noisy-OR within a type; top-k limits double-counting of correlated items).
* `belief(s,d) = 1 − Π_t (1 − r_t · c_t)` over the types in the mask. Contradicting evidence of type `t` with strength `k_t`: `belief ← belief · (1 − r_t · k_t)`. (Independence across types is an assumption; document it and include a sensitivity analysis in P4's experiments.)
* **Absence informativeness** (used only when `belief < tau_pos`):
  `neg(s,d) = static_completeness(s)[if application in mask else 0] · runtime_term` where `runtime_term = endpoint_coverage` if runtime in mask and `coverage` present, else 0; combine as `neg = 1 − (1 − a)(1 − b)` with `a = static_score·r_app`, `b = coverage·r_runtime` (so either source can establish informative absence, both strengthen it). Infrastructure alone can never establish absence of a *dependency* (it only sees declarations) → contributes 0.
* **Path sufficiency:** positive case `S_pos = min(1, n_types_supporting / 2) · mean(conf_by_type of supporting types)`; absence case `S_neg = neg(s,d)`.
* **Change sufficiency** `S = min over newly-denied/removed paths` (weakest link). **Belief of change** = max belief over newly-removed required paths.
* **Confidence** = `S · belief` for RISKY (evidence that it breaks), `S · (1 − belief)` for SAFE; INSUFFICIENT reports `S`. Optional `calibrate.py`: isotonic regression on dev (`confidence → correct`), disabled by default; rule-based stays primary.

### 8.3 Impact prediction (`prediction/propagate.py`, `security.py`, `operational.py`)

**Operational propagation**
```
direct = [e for e in change.effects if tightens(e)]           # newly denied path or removed permission
for e in direct:
    b = belief(e.src, e.dst)  (permission effects: belief that e.src NEEDS_PERMISSION)
    if b >= tau_pos:
        impact[e.src] = unavailable if READINESS_COUPLED(e.src,e.dst) or hard_dependency else degraded
        impact[e.dst] = affected-as-target (degraded, mechanism=direct_path_blocked)  # blocked ingress
        mark e.src.not_ready = READINESS_COUPLED(e.src,e.dst)
fixpoint:  for x with not_ready: its k8s-service endpoints disappear -> for every y with
           DEPENDS_ON|CALLS|CONNECTS_TO(y,x): impact[y] = unavailable if belief(y,x)>=tau_pos else degraded,
           mechanism=upstream_cascade, probability = belief(y,x) * prob(x)       (depth-limited 4, visited set)
operational_risk = 1 - Π(1 - prob(component)) over components with impact in {unavailable, degraded}
                   weighted 1.0/0.5; label: none(<0.1) low(<tau_risk) high(>=tau_risk); unknown if sufficiency<0.2
```
Only paths whose **belief ≥ tau_pos** contribute to risk; weak/unknown ones appear in `rationale` and lower sufficiency.

**Security impact**
* Paths: `exposure = Σ over components c with tag "sensitive" (label tier=data, or holds credentials) of #(src,port) pairs that can reach c`. Delta = `(exposure_after − exposure_before)/max(1, exposure_before)`; `improves` if delta ≤ −0.1, `degrades` if ≥ +0.1, else `neutral`.
* Permissions: weight `w(verb, resource)`: wildcard `*` = 5, `secrets`/`pods/exec`/`escalate|bind|impersonate` = 4, write verbs on workloads = 3, `list/watch` on secrets = 3, other write = 2, read = 1; delta = normalized change in Σ weights of granted permissions per principal.
* This is **independent of operational impact** (security ≠ "more restrictive is better"): a change can improve security *and* be RISKY.

### 8.4 Evidence gate (`gate/gate.py`)

```python
def decide(change, pred, G, bundle, cfg, mask) -> GateDecision:
    reasons = []
    if not change.supported or not change.effects:
        return INSUFFICIENT([UNSUPPORTED_CHANGE])
    conflicts = any(edge.conflicted for the edges on newly-removed paths)
    if conflicts: reasons.append(CONFLICTING_EVIDENCE)
    pos = any(b >= cfg.tau_pos for newly-removed paths)
    if pos:
        if S >= cfg.tau_suff_pos and not conflicts:
            return RISKY([POSITIVE_DEPENDENCY_SUPPORTED])          # positive evidence suffices (asymmetry)
        return INSUFFICIENT(reasons + [LOW_SUFFICIENCY], requests=[...])
    # no positive dependency found on any removed path
    if pred.security_impact == "degrades" and change.direction in {"loosens","mixed"}:
        return RISKY([SECURITY_DEGRADES])
    if S >= cfg.tau_suff_neg and not conflicts:
        return SAFE([ABSENCE_WELL_SUPPORTED])
    if bundle.coverage is None and runtime in mask: reasons.append(NO_RUNTIME_EVIDENCE)
    return INSUFFICIENT(reasons + [ABSENCE_NOT_INFORMATIVE], requests=...)
```
`evidence_requests` examples: `run_workload` with profile `full`; `exercise_endpoint backend:GET /reports` (known from AST but never exercised); `provide_source backend`; `resolve_conflict <ids>`.
* **Gate modes:** `gate_enabled=False` ⇒ forced decision: `RISKY` iff `operational_label=="high"` or security degrades, else `SAFE` (used for the "forced-decision" evaluation grid, §9.5).
* **Key principle encoded:** *absence of runtime observation never produces SAFE unless coverage or complete static analysis supports it.*

### 8.5 Pipeline, CLI, API, report

```python
# pipeline.analyze(): load cfg -> bundle.assert_no_leakage() -> mask by evidence_config ->
# build_graph -> propagate/security -> belief/sufficiency -> gate -> (remediation hook is called by P4 code via remediate()) -> AnalysisResult
```
* **CLI (`python -m evgate …`, argparse):**
  `collect --manifests DIR --src DIR [--runtime DIR] --snapshot ID -o bundle.json`
  `parse-change --kind k8s_networkpolicy --after FILE [--before DIR] --bundle bundle.json -o change.json`
  `analyze --change change.json --bundle bundle.json --config A|B|C|D|D_NOGATE -o result.json`
  `report --result result.json [--ground-truth gt.json] -o report.md|html`
  `graph --bundle bundle.json --config D -o graph.json`
  `run-scenario SCENARIO.yaml` (delegates to P4), `schemas`.
* **FastAPI:** `POST /changes` (upload/parse), `POST /analyze`, `GET /results/{id}`, `GET /reports/{id}`, `GET /healthz`. Stateless file store under `var/`. No auth (local research tool) — bind 127.0.0.1.
* **Report (`report/`):** Markdown/HTML decision report: change summary, evidence table (type/source/confidence/provenance link), graph figure, prediction, gate decision + reason codes + evidence requests, remediation (if any), and — when ground truth supplied — **prediction vs reality** table and mismatch root-cause hints.

### 8.6 Tests Part 3 must ship

Graph build/mask tests; belief math unit tests with hand-computed values; propagation tests (direct block, readiness coupling cascades to frontend, no cascade when belief < tau_pos); gate truth-table over G1–G4 (`G1→RISKY`, `G2→RISKY` for config D but lower sufficiency, `G3→INSUFFICIENT/CONFLICT`, `G4` + change on an unexercised endpoint → `INSUFFICIENT`); leakage test (stage-2 file rejected); determinism test (two runs ⇒ byte-identical JSON).

---

## 9. PART 4 — Remediation, Scenarios, Ground Truth, Evaluation, Paper

Packages: `evgate.remediation`, `evgate.scenarios`, `evgate.evaluation`; dirs `scenarios/`, `experiments/`, `paper/`, `infrastructure/opentofu/scenarios/`.

### 9.1 Minimal remediation (`remediation/`)

Trigger: `gate.decision == RISKY` **and** `sufficiency ≥ tau_suff_pos` **and** objective known. Never remediate on `INSUFFICIENT` (instead return `evidence_requests`).

**Network (`network.py`) algorithm**
1. `required = {(s,d,port) : newly-denied & belief ≥ tau_pos}` (from `AnalysisResult` + graph).
2. `objective_deny` = pairs the objective wants denied: for `restrict_ingress(target)` = *all* sources except `required` sources.
3. Build candidate policy set ordered by minimality: (a) allow only `required` sources at exact `port/protocol` using `podSelector` (same namespace) → 1 candidate per target; (b) if sources span namespaces, add `namespaceSelector` AND `podSelector`; (c) never use empty `from`, `ipBlock 0.0.0.0/0`, or omit ports (flag `introduces_wildcard`).
4. **Static validation** via `ReachabilityEngine`: all `required` allowed; all `objective_deny` still denied; no wildcard introduced. Choose the first passing candidate.
5. Emit `Remediation` + patched manifest (keep original policy name with suffix `-remediated`, add annotation `evgate.io/remediation-of`).

**RBAC (`rbac.py`):** `scope_down_permission`: keep Role, but replace the removed verb set with the minimal set the component `NEEDS_PERMISSION` (from app/audit evidence): specific verbs, `resourceNames` when evidence names a resource, never wildcard. Validate with `PermissionEngine`.
**Tofu (`tofu.py`):** produce a `tfvars` patch mapping the same decision onto module variables.
**Baselines for remediation evaluation:** `revert` (drop the change), `allow_all` (add broad allow). Remediation must beat both on the joint criterion *(function preserved) ∧ (objective kept)*; `revert` fails the objective by construction, `allow_all` fails minimality.

**Dynamic validation** (runner, §9.3) applies remediation in Kind, repeats probes + reachability/permission matrices, records `remediation_restores_function` and `remediation_keeps_objective`. **A static pass alone never counts as validated.**

### 9.2 Scenario library (`scenarios/*.yaml`, loader in `scenarios/loader.py`)

Scenario spec:
```yaml
id: N02-allow-wrong-label
split: dev|test
family: N02
category: network|kubernetes|iam
app_variant: base|ext_conditional|ext_rbac          # which manifests overlay is deployed
baseline_workload: full|short|partial
change: {kind: k8s_networkpolicy, operation: add, file: scenarios/N02/policy.yaml}
probes:                                            # content-checked (D8)
  - {probe_id: ui-health, kind: http, via: host_nodeport, target: "http://localhost:30080/api/health",
     expect_status: 200, expect_body_contains: '"status":"healthy"', touches: [component:poc-app/frontend, component:poc-app/backend, component:poc-app/database], required: true}
  - {probe_id: be-db, kind: tcp, via: pod_exec, target: "backend->database-service:5432", touches: [component:poc-app/backend, component:poc-app/database]}
expected_hypothesis: "Policy allows app=db-client, backend lacks that label -> backend cannot reach database"   # documentation only; NEVER used by predictor
```
**Target ≥ 40 base scenarios** (dev ≈ 40 %, test ≈ 60 %, split **by family variant**, with ≥ 4 families held out entirely for test):

| Family | Examples | Purpose |
|--------|----------|---------|
| N-block | deny-all ingress DB (M2); deny backend ingress from frontend; egress deny backend→DB; port-narrowing (5432 vs wrong 5433) | obvious breakages (all configs should catch) |
| N-safe | correct allow-from-backend; policy on unused component; additive allow; label-correct narrowing | SAFE cases — needed to measure false-RISKY |
| N-trap | wrong label selector (typo); namespaceSelector without podSelector; policy on Service port vs targetPort mismatch | semantics traps (static scanners pass) |
| N-hidden | **conditional dependency**: `/reports` endpoint calls `audit-service` only on that route (app variant `ext_conditional`); env var for `audit-service` exists but code never uses it (dead config); alias DNS vs label mismatch | where app/runtime evidence must change the answer; tests *absence ≠ absence* |
| R-rbac | remove `get configmaps` from backend SA (breaks `/config`); remove unused `list secrets` (SAFE); replace wildcard with specific verbs (SAFE); remove `watch` used by background thread | IAM-class |
| T-tofu | the same N/R changes expressed as OpenTofu `tfvars` applied via the kubernetes provider | IaC path |
| L-loosen | add broad allow / grant wildcard | `security degrades` labels (RISKY with no operational failure) |

**App variants (new files only, §3 protocol):** `services/backend/app/routes_ext.py` adding `GET /config` (reads a ConfigMap through the Kubernetes API using the pod's ServiceAccount), `GET /reports` (calls `audit-service` over HTTP), and a new tiny `services/audit-service/` (FastAPI) + manifests under `kubernetes/overlays/{ext_conditional,ext_rbac}/`. Keep each variant < 60 lines of Python.

### 9.3 Ground-truth runner (`scenarios/runner.py`, `groundtruth.py`)

```
for run in 1..R(=3):
    reset to baseline (kubectl delete -f scenario policies; kubectl rollout status) ; assert baseline probes pass
    [if baseline evidence snapshot not cached for (app_variant, workload profile): run workload, capture traces/logs/probes -> bundle]  # NOT repeated per run
    measure reachability matrix + permission matrix (BEFORE)
    apply change (kubectl apply | tofu apply)
    wait_until_stable(timeout=120 s): poll every 2 s; stable = pod readiness + probe results unchanged for 3 consecutive polls (10 s apart)
    run probes; measure reachability + permission matrices (AFTER); collect pod states
    -> GroundTruthRun(phase=post_change)
    if remediation: reset, apply remediation, same measurement -> phase=post_remediation
    revert; verify recovered -> phase=recovered   (fail the run if recovered != baseline)
label = f(runs): operational_failure = majority(any required probe failed) ; stable = all runs agree
affected_components = ∪ touches of failing probes ∪ components whose readiness changed
security_effect from measured matrices: exposure/permission weights as §8.3 computed on MEASURED data
```
Safety: `assert_local_kind_context()`. Namespaces per scenario not required (sequential). A full run is expected to take ~2–3 min; budget accordingly (40 scenarios × 3 runs ≈ 4–6 h, unattended; **cache baseline evidence**).

### 9.4 Evidence conditions and baselines (`evaluation/baselines.py`, `perturb.py`)

* **Configs:** `A={infra}`, `B={infra,app}`, `C={infra,runtime}`, `D=all`, plus `D_NOGATE` (= D with gate disabled) to isolate the gate's contribution. All use **identical** pipeline code; only mask and gate flag differ (fair comparison).
* **Fairness definition frozen before experiments:** *Infrastructure evidence* = declarative resources (Services, selectors, ports, policies, RBAC, IaC) **plus config references in manifests** (env values that resolve to a component). *Application evidence* = what source code/app config/Dockerfile/dependency manifests say the code does. *Runtime evidence* = traces, logs, probes, audit logs from the baseline snapshot. Put this paragraph in the paper.
* **Evidence conditions (offline perturbation of the recorded EC0 bundle — no re-running the cluster):** `EC0` complete; `EC1` no runtime telemetry; `EC2` short workload (coverage ≈ 20 %); `EC3` stale runtime (`observed_at` before last config change); `EC4` drift/conflict (inject infra evidence that contradicts runtime); `EC5` no source code. Main results use EC0; EC1–EC5 evaluate gate/abstention quality.
* **Grid:** scenarios × {A,B,C,D,D_NOGATE} × {EC0..EC5}; ground truth is run once per scenario (R repeats), the grid is computed offline → cheap.
* **Threshold tuning:** on `dev` only (grid search over §8.2 parameters, objective = maximize selective F1 subject to false-SAFE rate ≤ 5 %); write `config/analysis.frozen.yaml` with a SHA in `experiments/FROZEN`; **never tune on `test`.**

### 9.5 Metrics and statistics (`evaluation/metrics.py`, `stats.py`, `plots.py`)

Positive class = `risky_label`. Evaluate two grids: **forced-decision** (gate off for all configs; isolates the evidence effect) and **gated** (gate on; adds abstention).
* Classification: accuracy, precision, recall, F1, ROC-AUC on `operational_risk` score; **false-SAFE rate = P(SAFE ∧ risky_label)** (headline safety metric); false-RISKY rate.
* Affected components: set precision/recall/F1/Jaccard per scenario (micro and macro).
* Security impact: 3-class accuracy + macro-F1 vs measured effect.
* Gate: coverage (= 1 − abstention rate), selective accuracy, risk–coverage curve + AURC, abstention quality (share of abstentions on scenarios where D-with-full-evidence was wrong or evidence was perturbed).
* Calibration: ECE (10 equal-width bins), Brier, reliability diagram; accuracy by confidence bucket.
* Remediation: restores-function rate, objective-kept rate, minimality ratio, residual risk (post-remediation exposure − post-change exposure), compared with `revert` and `allow_all`.
* Prediction-vs-reality: agreement rate; mismatch taxonomy (`engine bug | missing evidence | wrong evidence | environment flake | label noise`) assigned manually for every disagreement (table in paper).
* Statistics: 10 000-sample seeded bootstrap 95 % CIs; paired comparison A vs D, B vs D, C vs D with **exact McNemar** on correct/incorrect and Wilcoxon signed-rank on per-scenario set-F1; report effect sizes; state small-n limitations; report **all** configs and scenarios (no cherry-picking), including negative results.
* Outputs: `experiments/results/<run_id>/records.jsonl` (`ExperimentRecord` per line), `metrics.json`, `tables/*.csv`, `figures/*.png`, `environment.json`, `FROZEN`. `make reproduce` regenerates metrics/figures from `records.jsonl` without a cluster; `make reproduce-full` re-runs scenarios.

### 9.6 Paper deliverables (`paper/`)

IEEE conference LaTeX template (or Overleaf); outline: Introduction · Related Work (28-paper survey; group by the six literature areas) · Problem & Threat Model · Approach (evidence model, graph, prediction, gate, remediation) · Experimental Setup (testbed, scenarios, ground truth, baselines definition, evidence conditions) · Results (RQ1 ablation, RQ2 gate/abstention, RQ3 remediation, RQ4 calibration) · Discussion & Threats to Validity (single app family, rule-based, Kind-only CNI, small n, label noise) · Conclusion. Research questions: **RQ1** does multi-source evidence improve prediction vs infra-only? **RQ2** does the gate reduce unsafe decisions under incomplete evidence? **RQ3** do minimal remediations preserve function while keeping the objective? **RQ4** is confidence calibrated?
Release checklist: tag `v1.0-paper`, Zenodo DOI, `LICENSE` (Apache-2.0 or MIT — team decision), `CITATION.cff`, dataset card for `scenarios/` + `records.jsonl`.

### 9.7 Tests Part 4 must ship

Remediation unit tests (static validator rejects wildcard/over-broad), scenario-loader schema validation (all 40 specs validate), metrics on synthetic records with hand-computed answers, stats functions vs known values, `perturb` determinism, runner dry-run mode (mock kubectl) in CI; `cluster` tests locally for the first five scenarios.

---

## 10. Cross-cutting rules

* **Determinism:** sorted collections, seeded RNG (`seed=1337` default), no `datetime.now()` inside evidence IDs; times injected via parameter for tests.
* **Provenance everywhere:** every graph edge and every prediction rationale line cites evidence IDs; reports link to file+line.
* **Security hygiene:** never `eval/exec` analyzed code; sanitize paths (`Path.resolve()` must stay under allowed roots); no secrets in repo (the POC's `apppassword` is a documented local-only placeholder); log security-relevant actions.
* **Docs:** each Part keeps `docs/<part>/README.md` (purpose, usage, limitations); research decisions recorded in `docs/decisions/NNNN-title.md` (ADR style).
* **Commits/branches:** `[component] message`; branches `feature|fix|experiment|docs/<part>-<topic>`; PRs need 1 review from a different Part.
* **Limitations to state honestly:** Kind default CNI behaviour; rule-based weights tuned on small dev set; independence assumption across evidence types; one application family; IAM = RBAC (+ static IAM-JSON); runtime evidence limited to traces/logs/probes/audit.

---

## 11. Definition of Done (project level)

1. `make demo` runs the M2 scenario end to end: collect → parse → analyze (config D) → report → apply in Kind → ground truth → comparison, in ≤ 15 min on a laptop.
2. ≥ 40 scenarios with stable ground truth; grid results regenerate with `make reproduce` bit-for-bit.
3. Frozen thresholds; test split touched once.
4. Paper draft with all tables/figures generated from `experiments/results/`.
5. Open-source release: README, LICENSE, CITATION, tagged release, environment fingerprint.
