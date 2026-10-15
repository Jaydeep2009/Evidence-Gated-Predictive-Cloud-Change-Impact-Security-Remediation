# task.md — Work Breakdown for the 4-Member Team

**Project:** Evidence-Gated Predictive Cloud Change Impact & Security Remediation
**Status:** FINAL DRAFT v1.0 · **Read together with:** `implementation.md` (all technical specs, contracts, algorithms — section numbers below like §7.4 refer to it)

---

## 1. How to use this file

* Each member owns **one Part** (P1–P4). Parts communicate **only** through the frozen contracts (`implementation.md` §5) and the golden fixtures (§5.9), so nobody waits for another Part's real code.
* Give your IDE agent: this file + `implementation.md` + the kickoff prompt for your Part (§8 below). Tasks are listed in the order they should be done. A task is **done** only when its *Acceptance* line passes in CI (`make test`) and the PR is reviewed by a member of a different Part.
* Task IDs: `C0` (bootstrap), `P1-R*`, `P2-*`, `P3-*`, `P4-*`. Effort is in ideal person-days (`d`).

## 2. Findings from reviewing the repository (they shape this plan)

Details and decisions are in `implementation.md` §1 (D1–D12). The ones that matter most:

1. **Label leakage (D1):** the Milestone-3 plan would use the *post-change* (policy active) JSON as runtime evidence. Prediction must use **baseline-only** evidence; post-change data is ground truth.
2. **Frontend→Backend "success" is a false positive (D8):** `curl -s …/api/health` hits nginx, which has no `/api/` route and returns `index.html` with HTTP 200; `curl -s` ignores status. The ground truth for that edge is therefore unreliable until fixed. New probes check status **and** body.
3. **App extractor must match the real code (D2):** backend uses `psycopg2.connect(host=DATABASE_CONFIG["host"])` fed by `DATABASE_HOST`, not `create_engine`/`requests`.
4. **Graph and conflict model fixes (D3, D4, D5):** `MultiDiGraph`; conflict = same claim + same snapshot + opposite polarity; noisy-OR confidence instead of `max + 0.1`.
5. **One scenario cannot support a paper (D10):** plan for **≥ 40 scenarios**, including SAFE cases, traps and conditional dependencies, and measured ground truth.
6. **IAM scope (D12):** proposed as Kubernetes RBAC (real enforcement in Kind) + optional static AWS-IAM-JSON. **Confirm with your guide in week 1.**

## 3. Parts and ownership

| Part | Theme | Owner (assign) | Effort | New work? |
|------|-------|----------------|--------|-----------|
| **P1** | Testbed & ground-truth foundation | *the member who built M1–M2* | ≈ 2 d remaining | **Existing work + 3 small closing tasks** |
| **P2** | Evidence extraction + change semantics (infra/app/runtime extractors, telemetry, workload, NetworkPolicy/RBAC semantics engines, change parser, OpenTofu) | member 2 | ≈ 36 d | all new |
| **P3** | Core engine + interfaces (contracts steward, graph, belief, prediction, evidence gate, pipeline, CLI, API, report, CI) | member 3 | ≈ 35 d | all new |
| **P4** | Remediation + scenarios + ground-truth runner + evaluation + paper assembly | member 4 | ≈ 39 d | all new |

Dependency rule: *no Part blocks another for more than 2 days* because of the stubs/fixtures listed in §6. P4 is the heaviest; the **cut-lines in §9** say what to drop first. The P1 owner is the natural **reviewer/integration QA and paper editor** (suggested, not required).

### Ownership of directories (full tree in `implementation.md` §3)

| Part | Owns |
|------|------|
| P1 | `services/{frontend,backend}` existing files, `kubernetes/` baseline manifests, `scripts/` existing, `docs/` existing, `fixtures/ground_truth/` |
| P2 | `src/evgate/{evidence,semantics,change,workload}`, `telemetry/`, `config/sinks.yaml`, `services/backend/Dockerfile.otel`, `infrastructure/opentofu/modules/` |
| P3 | `pyproject.toml`, `Makefile`, CI, `CODEOWNERS`, `src/evgate/{contracts,graph,prediction,gate,common,report,api}`, `pipeline.py`, `cli.py`, `config/analysis.yaml`, `fixtures/golden/` |
| P4 | `src/evgate/{remediation,scenarios,evaluation}`, `scenarios/`, `experiments/`, `paper/`, `infrastructure/opentofu/scenarios/`, new files under `services/backend/app/routes_*.py`, `services/audit-service/`, `kubernetes/overlays/` |

---

## 4. PART 1 — Testbed & Ground-Truth Foundation (existing implementation)

### 4.1 Already done (nothing to implement)

| Item | Evidence in repo |
|------|------------------|
| Kind cluster setup with NodePort 30080 | `scripts/setup-cluster.sh` |
| 3-tier app Frontend (nginx) → Backend (FastAPI, real `SELECT 1` health) → PostgreSQL 15 | `services/`, `kubernetes/` |
| Readiness (`/health`, DB-coupled) and liveness (`/live`) probes | `kubernetes/backend/deployment.yaml` |
| Baseline verification + JSON | `scripts/verify-baseline.sh`, `baseline-verification.json` |
| NetworkPolicy `isolate-database` experiment (absent → present → absent) with causation check | `kubernetes/policies/`, `scripts/{apply,remove,verify}-network-policy.sh`, `network-policy-verification-20261011-*.json`, `docs/milestone-2-completion.md` |
| Documentation of setup, testing, fixes and corrections | `README.md`, `MILESTONE-{1,2}-SUMMARY.md`, `docs/` |
| Steering/spec documents for the AI IDE (Kiro) | `.kiro/` |

Canonical ground-truth files (per `docs/milestone-2-completion.md`): Stage 1 `…132130.json`, Stage 2 `…133342.json`, Stage 3 `…135142.json`.

### 4.2 Closing tasks (small; only these remain for P1)

| ID | Task | Acceptance | Effort |
|----|------|------------|--------|
| **P1-R1** | Copy (do **not** move/edit) the 3 canonical JSONs + `baseline-verification.json` to `fixtures/ground_truth/m2/` with a `README.md` giving stage, timestamp, SHA-256 (use `docs/milestone-2-evidence-hashes.txt`). Add `testbed/README.md` pointing to the existing directories (documentation alias only). | Files present; hashes in README match `sha256sum` | 0.25 d |
| **P1-R2** | Fix D8: add `location /api/ { proxy_pass http://backend-service:8000/; }` to `services/frontend/nginx.conf`; UI fetches `/api/health`; change Test 2 in both verify scripts to `curl -sf … \| grep -q '"status"'`; rerun Stage 1–3 once; store new outputs in `fixtures/ground_truth/m2_v2/` (keep old evidence untouched; note the change in `docs/`). Expected: Stage 2 now reports Frontend→Backend **failed/degraded** because backend is NotReady. | Stage-2 JSON shows `frontend_to_backend: failed`; Stage 1/3 `success` | 1 d |
| **P1-R3** | Pin versions: `scripts/versions.env` (kind, kubectl, node image, `postgres:15.x-alpine`, python base); `build-images.sh` also tags with git short SHA; `scripts/print-env.sh` emits an `EnvironmentFingerprint` JSON (§5.7 of implementation.md). | `bash scripts/print-env.sh` prints valid JSON incl. image digests | 0.5 d |

*If you want P1 to do literally nothing new:* P4 can take P1-R2 and P1-R3 (their runner does not depend on R2 — it uses its own content-checked probes). R1 is needed by everyone, takes minutes.

---

## 5. Work packages for P2, P3, P4

### C0 — Bootstrap (owner **P3**, day 1–2; everybody else starts on fixtures-independent tasks meanwhile)

| Step | Output |
|------|--------|
| `pyproject.toml` (src layout, package `evgate`), `requirements.lock`, `Makefile` (`test lint schemas demo reproduce`), `.github/workflows/ci.yml`, `CODEOWNERS`, pre-commit (black, ruff) | CI green on empty tests |
| Create `src/evgate/contracts/` exactly as `implementation.md` §5.1–5.7; export JSON Schemas (`make schemas`) | `mypy --strict src/evgate/contracts` passes |
| Hand-author golden fixtures G1–G4, `change_M2.json`, `gt_M2_label.json` in `fixtures/golden/` (§5.9) from the repo files | Fixtures validate against schemas |
| `analyze_stub()` returning canned `AnalysisResult` for `change_M2.json`; same for `collect_evidence_stub()` | P4 can code against it from day 2 |
| Update `.kiro/steering/architecture.md` (analyzer lives in `src/evgate/`, D7) | merged |

### 5.1 PART 2 — Evidence & Change Semantics

| ID | Task | Spec | Depends on (before real code exists) | Acceptance | Effort |
|----|------|------|--------------------------------------|------------|--------|
| P2-01 | Component inventory + alias/entity resolution | §7.1 | repo manifests | `inventory` of the repo = {frontend, backend, database}; aliases for `database-service[.poc-app[.svc[.cluster.local]]]` resolve | 1.5 d |
| P2-02 | NetworkPolicy **semantics engine** (`ReachabilityEngine`) | §7.3 | inventory | ≥ 25 truth-table tests incl. empty-`from`, `ingress: []`, AND/OR selectors, egress+ingress both ends, kubelet/NodePort pseudo-source | 3 d |
| P2-03 | RBAC **semantics engine** (`PermissionEngine`) | §7.3 | — | ≥ 15 tests incl. wildcards, aggregation, `resourceNames`, subresources | 2 d |
| P2-04 | Infra extractors (Deployment/Service/env refs, NP, SA/Role/RoleBinding) emitting contract evidence | §7.2 | P2-01..03 | G1 infra evidence reproduced; env-ref evidence is `inferred` 0.5 | 3 d |
| P2-05 | App extractor — routes, constant propagation, sink table, env + Deployment resolution | §7.4 | P2-01 | Real `main.py` ⇒ `backend DEPENDS_ON database` at the `psycopg2.connect` line, `unresolved_dynamic_calls=0`; unresolved-env case lowers confidence | 3 d |
| P2-06 | App extractor — readiness coupling (bounded call graph), K8s-API→permission map, config/Dockerfile/requirements capability evidence | §7.4 | P2-05 | `backend READINESS_COUPLED database`; capability evidence never alone sufficient (unit test) | 2 d |
| P2-07 | Runtime extractor — verification/probe JSON (baseline-only; socket-code map; leakage guard) | §7.5.1, D9 | fixtures `m2/` | Stage-1 ⇒ `CONNECTS_TO`; Stage-2 file rejected in pre-change mode | 1 d |
| P2-08 | Telemetry stack (Collector → Jaeger + file archive), `Dockerfile.otel`, overlay `kubernetes/overlays/otel/`, `make telemetry-up/down` | §7.6 | cluster | Trace `backend→database` visible in Jaeger after `/api/health`; archived OTLP JSON saved as fixture | 3 d |
| P2-09 | Workload generator + profiles (`full/short/partial/idle`) + `RuntimeCoverage` computation | §7.6, §7.5.5 | P2-05 (routes) | Coverage numbers match profile (`short` ≈ 0.2) | 2 d |
| P2-10 | Runtime extractor — traces (Jaeger JSON/API) | §7.5.2 | P2-08 | Confidence formula test; `CALLS` from parent/child spans | 2 d |
| P2-11 | Runtime extractor — logs (uvicorn, nginx log_format overlay, psycopg2 errors) with pod-IP→component map | §7.5.3 | P2-08 | Fixture logs ⇒ expected `OBSERVED_COMMUNICATION` and `FAILED_TO_CONNECT` | 2 d |
| P2-12 | Kubernetes audit-log capture (Kind audit policy) + extractor | §7.5.4 | cluster | SA call to ConfigMap API appears as `NEEDS_PERMISSION` (403 ⇒ refutes) | 2 d |
| P2-13 | Normalizer (validate, dedupe, conflict D4, staleness, deterministic order, leakage rejection) | §7.7 | contracts | Unit tests incl. G3 conflict detected, `backend DEPENDS_ON`+`FAILED_TO_CONNECT` **not** a conflict | 2 d |
| P2-14 | `collect_evidence()` + `evgate collect` CLI hook; **contract test reproduces G1** | §5.8, §7.9 | P2-04..13 | Contract test green; deterministic output | 1.5 d |
| P2-15 | Change parser for NetworkPolicy + RBAC YAML (effects from full engine diff; direction; objective) | §7.8 | P2-02, P2-03 | Reproduces `change_M2.json`; unsupported kind ⇒ `supported=false` | 2.5 d |
| P2-16 | OpenTofu modules (`network_policy`, `rbac`) + `scripts/p2-tofu-plan.sh` + plan-JSON parser | §7.8.6 | P2-15 | Same ChangeSpec from `.tfvars` variant as from YAML variant | 3 d |
| P2-17 | **Semantics validation doc** (engine vs measured cluster matrices on ≥ 10 policies, ≥ 10 role sets; consumes P4 runner) | §7.3 | P4-03 | `docs/p2/semantics-validation.md` with agreement table + documented disagreements | 1.5 d |
| P2-18 | *(stretch)* IAM-JSON static parser/evaluator | §7.8.7 | P2-15 | Unit tests for Deny precedence + wildcard | 2 d |
| P2-19 | Docs `docs/p2/README.md`, sink-table guide | §10 | — | reviewed | 0.5 d |

### 5.2 PART 3 — Core Engine, Graph, Prediction, Gate, Interfaces

| ID | Task | Spec | Develops against | Acceptance | Effort |
|----|------|------|------------------|------------|--------|
| **C0** | Bootstrap (see above) | §5 | — | see C0 table | 2 d |
| P3-01 | Graph builder (`MultiDiGraph`, one edge per `(s,d,relationship)`), evidence mask A/B/C/D, JSON/DOT export | §8.1 | G1 | Node/edge counts for G1 per mask are as hand-computed; `by_type` and `conf_by_type` present | 2.5 d |
| P3-02 | Dependency view + belief / absence-informativeness / sufficiency / confidence math | §8.2 | G1–G4 | Hand-computed examples in tests (noisy-OR, reliability, weakest-link) | 3 d |
| P3-03 | Operational propagation (direct, readiness-coupled, cascade through K8s-service endpoints, depth limit) | §8.3 | G1 + `change_M2.json` | M2 ⇒ backend `unavailable`, database `degraded`, frontend `unavailable` via `upstream_cascade` iff belief(frontend→backend) ≥ τ; no cascade when below τ | 3 d |
| P3-04 | Security-impact analyzer (exposure delta for paths; weighted permission delta) | §8.3 | change fixtures | M2 ⇒ `improves`; a wildcard-grant fixture ⇒ `degrades` | 2 d |
| P3-05 | Evidence gate + reason codes + `evidence_requests`; forced-decision mode | §8.4 | G1–G4 | Truth-table: G1→RISKY; G3→INSUFFICIENT(CONFLICT); G4+unexercised endpoint→INSUFFICIENT; no-runtime & no-app absence → INSUFFICIENT, never SAFE | 3 d |
| P3-06 | `analyze()` pipeline, leakage guard, config loader, versions block, determinism | §8.5 | all above | Same inputs ⇒ byte-identical JSON; stage-2 bundle rejected | 2 d |
| P3-07 | CLI (`collect, parse-change, analyze, report, graph, schemas, run-scenario`) | §8.5 | stubs | `evgate analyze …` on fixtures produces `AnalysisResult` | 1.5 d |
| P3-08 | Report generator (MD/HTML): evidence table with provenance, graph figure, prediction, gate reasons, remediation, **prediction-vs-reality** table | §8.5 | fixtures | Report for M2 contains all sections; links to file:line | 3 d |
| P3-09 | FastAPI service (`/changes /analyze /results /reports /healthz`) | §8.5 | pipeline | API tests via `TestClient` | 1.5 d |
| P3-10 | Explanation quality: every rationale line cites evidence IDs; human-readable text templates | §8.3 | — | Test: no rationale line without an evidence id | 1.5 d |
| P3-11 | Optional calibrator (isotonic/Platt on dev) behind a flag; sensitivity hooks (override reliabilities/thresholds per call) for P4's sensitivity analysis | §8.2 | P4 records | Flag off ⇒ identical results | 2 d |
| P3-12 | Graph figure for paper (`make graph-figure`), CI hardening (coverage ≥ 85 % on non-cluster code), `docs/p3/README.md` | §8.1 | — | CI green; figure in `paper/figures/` | 2 d |
| P3-13 | Integration owner duty: run **I1–I4** checkpoints (§6), keep `make demo` working | §11 | all | `make demo` passes at each checkpoint | 3 d (spread) |

### 5.3 PART 4 — Remediation, Scenarios, Ground Truth, Evaluation, Paper

| ID | Task | Spec | Develops against | Acceptance | Effort |
|----|------|------|------------------|------------|--------|
| P4-01 | Scenario schema, loader, validator, **dry-run mode** (mock kubectl) | §9.2 | contracts | 3 sample specs validate; CI runs dry-run | 2 d |
| P4-02 | App variants: `routes_ext.py` (`/config`, `/reports`), `services/audit-service/`, overlays `ext_conditional`, `ext_rbac` (new files only; 1-line include in `main.py` via PR to P1) | §9.2 | existing cluster | Variants deploy; `/reports` triggers a call to audit-service only on that route | 3 d |
| P4-03 | **Ground-truth runner**: Kind guard, reset-to-baseline, poll-until-stable, content-checked probes, reachability + permission matrices, revert + recovered check, ×R runs, label function | §9.3 | M2 scenario | M2 run reproduces the known result (`operational_failure=true`, security improves); label stable over 3 runs | 6 d |
| P4-04 | Scenario authoring — first 10 (M2 + obvious N-block/N-safe) → feeds I2 | §9.2 | P4-03 | 10 specs run unattended, labels stable | 3 d |
| P4-05 | Remediation (network): candidate generation, static validation with `ReachabilityEngine`, minimality metric | §9.1 | engine interface (P2-02; until then a 30-line stub allowing 'app→pod' rules) | M2 ⇒ allow-only-backend:5432 patch; wildcard candidates rejected | 4 d |
| P4-06 | Remediation dynamic validation in Kind + `revert`/`allow_all` baselines | §9.1 | P4-03 | M2 remediation restores probes **and** keeps database isolated from frontend (measured) | 3 d |
| P4-07 | Remediation (RBAC + OpenTofu tfvars) | §9.1 | P2-03, P2-16 | RBAC scenario patch validated statically + dynamically | 3 d |
| P4-08 | Scenario authoring — remaining ≥ 30 (traps, hidden/conditional, RBAC, Tofu, loosening) + dev/test split + ≥ 4 held-out families | §9.2 | P4-02..03 | 40 specs; ground truth stable (or flagged `unstable`) | 6 d |
| P4-09 | Evidence snapshot cache + condition perturbations EC0–EC5 | §9.4 | G1–G4, P2-14 | Deterministic; EC1 equals bundle without runtime | 2.5 d |
| P4-10 | Evaluation orchestrator (grid: scenarios × {A,B,C,D,D_NOGATE} × EC) → `ExperimentRecord` JSONL | §9.4 | `analyze()` (stub→real) | Grid runs offline from recorded data | 2.5 d |
| P4-11 | Metrics, statistics (bootstrap, McNemar, Wilcoxon), calibration, risk–coverage, plots, mismatch taxonomy sheet | §9.5 | synthetic records | Tests vs hand-computed values | 4 d |
| P4-12 | Threshold tuning on **dev only**, sensitivity analysis, freeze (`analysis.frozen.yaml`, `experiments/FROZEN`) | §9.4 | P4-10/11 | Freeze file committed before any test-split run | 2 d |
| P4-13 | Final test run, `make reproduce` / `reproduce-full`, `environment.json`, dataset card | §9.5 | all | Reproduce regenerates tables bit-for-bit | 2 d |
| P4-14 | Paper assembly: IEEE template, results sections, figures/tables from `experiments/results`; collect sections from P1–P3 | §9.6 | — | Compiles; every number traceable to a results file | 5 d (spread) |

---

## 6. Dependency map, stubs and integration checkpoints

### 6.1 What each Part can start on day 1

| Part | Starts immediately with | Real inputs arrive |
|------|-------------------------|--------------------|
| P1 | R1 (copy fixtures) — unblocks everyone | — |
| P2 | P2-01, P2-02, P2-03 (pure functions over repo YAML) | contracts at C0 (day 2) |
| P3 | C0, then P3-01..05 on golden fixtures G1–G4 | real bundles from P2-14 (≈ week 4) |
| P4 | P4-01 (schema/loader), P4-02 (app variants), P4-03 (runner) against the existing cluster | `analyze()` stub from C0; real `analyze()` ≈ week 4; real engine from P2-02 ≈ week 3 |

### 6.2 Cross-part hand-offs (the only ones)

| From → To | Artifact | Needed by |
|-----------|----------|-----------|
| P1 → all | `fixtures/ground_truth/m2/` | day 1 |
| P3 → all | contracts, golden fixtures, stubs (C0) | day 2 |
| P2 → P3 | `collect_evidence()`, `parse_change()` real | week 4 (I1) |
| P2 → P4 | `ReachabilityEngine`, `PermissionEngine` | week 3 |
| P3 → P4 | real `analyze()` | week 4 (I1) |
| P4 → P2 | runner matrices for semantics validation (P2-17) | week 6 |
| P4 → P3 | frozen thresholds → `config/analysis.frozen.yaml` | week 8 |
| P2 → P4 | OpenTofu modules (for T-scenarios) | week 6 |

### 6.3 Timeline (10 weeks — shift to your real deadline; keep the order)

| Week | P1 | P2 | P3 | P4 | Checkpoint |
|------|----|----|----|----|-----------|
| 1 | R1–R3 | P2-01..03 | **C0**, P3-01 | P4-01, P4-02 | **I0:** contracts + fixtures merged |
| 2 | review/QA | P2-03, P2-04, P2-05 | P3-02, P3-03 | P4-03 | |
| 3 | review/QA | P2-05, P2-06, P2-07, P2-13 | P3-04, P3-05 | P4-03, P4-05 | engines available to P4 |
| 4 | paper: testbed + related work | P2-08, P2-09, P2-14, P2-15 | P3-06, P3-07 | P4-04, P4-05 | **I1:** `make demo` — M2 end-to-end (collect → analyze → report → ground truth), configs A–D |
| 5 | paper | P2-10, P2-11, P2-12 | P3-08, P3-10 | P4-06, P4-09, P4-10 | |
| 6 | paper | P2-16, P2-17 | P3-09, P3-11 | P4-07, P4-08 | **I2:** remediation validated in cluster on M2; 10 scenarios run; A–D table v0 |
| 7 | paper | P2-18 (stretch), docs | P3-12 | P4-08, P4-11 | |
| 8 | QA | bug-fix on extractors | threshold-config hooks | P4-12 | **I3:** 40 scenarios; EC0–EC5 grid on dev; **thresholds frozen** |
| 9 | QA | support | support | P4-13 | **I4:** one-shot test-split run; results frozen; tag `v1.0-paper-candidate` |
| 10 | paper polish | paper §Approach-evidence | paper §Approach-reasoning | P4-14 | submission-ready draft + release |

### 6.4 Integration checkpoints (owner P3; each is a PR "Integration Ix")

* **I0** – `make test` green; schemas exported; G1–G4 validate.
* **I1** – `make demo`: extractors → bundle (contract test equals G1) → `analyze` D → RISKY + prediction → report → Kind run → "prediction vs reality" for M2.
* **I2** – Remediation: RISKY → minimal allow-only-backend policy → dynamic validation passes; A/B/C/D first comparison on ≥ 10 scenarios; leakage test enforced.
* **I3** – All 40 scenarios, EC grid, thresholds frozen; no `test`-split result seen before freeze.
* **I4** – Frozen run; `make reproduce` reproduces; release checklist.

---

## 7. Quality gates (apply to every PR)

1. `black`, `ruff`, type hints; `mypy --strict` for `contracts/`.
2. New code has unit tests; extractors have valid / malformed / empty / missing-file cases.
3. No `datetime.now()` in IDs; outputs sorted; results deterministic (two runs ⇒ identical JSON).
4. No outcome hard-coded anywhere: no `if policy == isolate-database → predict failure`. Scenario `expected_hypothesis` text is never read by code.
5. Every claim in prediction/report cites evidence IDs.
6. Cluster-touching code calls `assert_local_kind_context()`.
7. Contracts only change through a `contracts-change` PR approved by all four owners.
8. Research integrity: report all runs; negative results go in the paper; test split touched once, after freeze.

---

## 8. Kickoff prompts for the AI IDE (paste one per member)

**Common preamble (all Parts):**
> You are implementing Part {N} of the project described in `implementation.md` and `task.md` (both in the repo root). Read `implementation.md` §0–§5 fully, then only the section for Part {N}. Implement tasks in the listed order. Before coding each task: write the tests described in its Acceptance column using the fixtures in `fixtures/`. Never change files owned by other Parts (see ownership table) and never change `src/evgate/contracts`. Do not add dependencies beyond `implementation.md` §4. Keep everything deterministic and typed. After each task: run `make test lint`, then summarize what you changed and any deviation from the spec.

**P1:** "Part 1. Do only P1-R1, P1-R2, P1-R3 from `task.md` §4. Do not refactor existing scripts beyond the described change. Preserve old evidence files byte-for-byte."
**P2:** "Part 2 (`implementation.md` §7). Start with inventory and the two semantics engines because other Parts depend on them. The app extractor must work on the real `services/backend/app/main.py` and resolve `DATABASE_HOST` via `kubernetes/backend/deployment.yaml`. Your `collect_evidence()` output must reproduce `fixtures/golden/G1_bundle_full.json`."
**P3:** "Part 3 (`implementation.md` §8 and bootstrap C0). First do C0 exactly as specified so the others are unblocked, including stubs. Implement the belief/sufficiency math and gate pseudocode literally; every decision must be explainable by evidence IDs."
**P4:** "Part 4 (`implementation.md` §9). The runner must use content-checked probes, poll-until-stable, revert and verify recovery, and refuse to run unless the kube context starts with `kind-`. Never tune on the test split. Scenario `expected_hypothesis` is documentation only."

---

## 9. Risks, cut-lines and decisions needed

### 9.1 Decisions to confirm in week 1

| # | Question | Default if no answer |
|---|----------|----------------------|
| Q1 | IAM scope = K8s RBAC (+ static IAM-JSON optional)? | yes |
| Q2 | Target venue and deadline (drives week plan and paper length) | IEEE conference, 6–8 pages |
| Q3 | License (Apache-2.0 vs MIT) | Apache-2.0 |
| Q4 | Allowed to add `scipy/numpy/matplotlib` for evaluation only? | yes |
| Q5 | Extend the POC app with `audit-service` and `/config`/`/reports` routes (needed for hidden-dependency and RBAC scenarios)? | yes |

### 9.2 Risks

| Risk | Mitigation |
|------|------------|
| Ground truth flaky (convergence, kindnet behaviour) | poll-until-stable, R=3 runs, `stable` flag, report unstable scenarios separately |
| Ablation shows no benefit | still publishable: report honestly; scenario design (N-hidden) is what makes evidence types matter; include sensitivity analysis |
| Too few scenarios for statistics | ≥ 40 base scenarios, bootstrap CIs, McNemar; state small-n limitation |
| P4 overload | cut-lines below |
| Time to stand up telemetry | file-based OTLP archive fallback; logs + probes can carry runtime evidence if tracing slips |
| Evidence definitions disputed (what counts as "infrastructure" for baseline A) | frozen definition in `implementation.md` §9.4, copied into paper |

### 9.3 Cut-lines (drop in this order if time runs out)

1. P2-18 IAM-JSON static extension → 2. Prometheus/Grafana → 3. OpenTofu scenarios (T-family) and P4-07 tofu part → 4. Calibrator (P3-11) → 5. FastAPI (P3-09; keep CLI) → 6. Audit-log extractor and RBAC family down to 4 scenarios → 7. Scenario count to 30 (never below 30).
**Never cut:** leakage guard, poll-until-stable runner, dev/test freeze, gate, minimal remediation with dynamic validation, A–D ablation.

---

## 10. Paper work split

| Section | Writes | Source |
|---------|--------|--------|
| Introduction, Related Work (28-paper survey, six areas) | P1 (+P4 edits) | literature survey, `.kiro/steering/research-integrity.md` |
| Testbed & ground truth | P1 + P4 | §6, §9.3 |
| Evidence model, extractors, semantics | P2 | §5, §7 |
| Graph, prediction, gate | P3 | §8 |
| Remediation, scenarios, metrics, results, threats to validity | P4 | §9 |
| Abstract/Conclusion, final edit | all, P1 editor | |

Conservative wording only ("based on the literature reviewed", "suggests", "indicates"); no "first" or "no existing system" claims.
