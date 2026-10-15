# Milestone 2: Kubernetes NetworkPolicy Security-Change Experiment

## Document Information

- **Milestone:** 2
- **Status:** Draft - Ready for Review
- **Created:** 2026-10-07
- **Purpose:** Introduce controlled Kubernetes NetworkPolicy to block Backend → PostgreSQL communication for security-change impact experiment

---

## 1. Objective

Implement a reproducible **security-change experiment** using Kubernetes NetworkPolicy that:

1. Restricts Backend → PostgreSQL network communication
2. Causes Backend database connectivity to fail naturally
3. Verifies the operational impact of the security restriction
4. Preserves the ability to rollback and restore baseline functionality
5. Records experimental results for future research evaluation

**This milestone does NOT implement:**
- Evidence collection framework
- Evidence/dependency graph
- Impact prediction engine
- Evidence Gate
- Confidence scoring
- Remediation engine
- ML/prediction models
- OpenTelemetry/Jaeger (deferred to Milestone 3)

---

## 2. Baseline Status (Milestone 1)

### Verified Working State

From `baseline-verification.json`:

```json
{
  "timestamp": "2026-10-07T07:02:39.383Z",
  "milestone": "1",
  "verification": {
    "frontend_accessible": true,
    "frontend_to_backend": "success",
    "backend_to_database": "success",
    "database_query": "success",
    "end_to_end": "success"
  },
  "communication_paths": {
    "user_to_frontend": "✅ working",
    "frontend_to_backend": "✅ working",
    "backend_to_database": "✅ working"
  }
}
```

### Current Architecture

```
User (localhost:30080)
    ↓
Frontend (NodePort 30080)
    ↓ HTTP
Backend (ClusterIP 8000)
    ↓ PostgreSQL protocol
PostgreSQL (ClusterIP 5432)
```

### Pod Labels (from Milestone 1)

**Backend pods:**
- `app: backend`
- `tier: application`

**Database pods:**
- `app: database`
- `tier: data`

**Frontend pods:**
- `app: frontend`
- `tier: presentation`

---

## 3. NetworkPolicy Design

### Policy Name

`isolate-database`

### Policy Location

`kubernetes/policies/isolate-database.yaml`

### Target

**Apply to:** PostgreSQL database pods  
**Selector:** `app: database`

**Effect:** Isolate PostgreSQL pods from ALL ingress traffic (not Backend-specific)

### Policy Specification

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-database
  namespace: poc-app
  labels:
    milestone: "2"
    purpose: security-experiment
spec:
  podSelector:
    matchLabels:
      app: database
  policyTypes:
  - Ingress
  ingress: []  # Empty ingress rules = deny all ingress
```

**What This Policy Actually Does:**

This policy **isolates PostgreSQL pods from ALL ingress traffic**.

- Applies to: Database pods (`app: database`)
- Effect: Denies ALL incoming connections to PostgreSQL
- Empty `ingress: []` = no ingress allowed from any source

**Important Clarification:**

This is NOT a source-specific "deny Backend only" policy.

This policy denies:
- ✅ Backend → PostgreSQL
- ✅ ANY other pod → PostgreSQL
- ✅ ALL ingress to PostgreSQL pods

This policy does NOT affect:
- ❌ User → Frontend
- ❌ Frontend → Backend
- ❌ DNS queries (egress)
- ❌ Egress from database pods
- ❌ Traffic to non-database pods

### Why This Design for the Experiment

**In the current application:**
- Backend → PostgreSQL is the ONLY required communication path to the database
- No other pods need database access

**Therefore:**
- Isolating PostgreSQL from all ingress = removing the required Backend → PostgreSQL path
- The experiment demonstrates: **restricting a required path causes operational failure**

**This is intentional for research purposes.**

A production policy would explicitly allow Backend → PostgreSQL while denying others. This experiment intentionally uses a restrictive policy to create the failure scenario.

### NetworkPolicy Scope

- **Namespace:** `poc-app` only
- **Additive:** Does not interfere with other policies
- **Reversible:** Can be deleted to restore baseline

---

## 4. Security Intent

### Primary Goal

**Network isolation:** Demonstrate that Kubernetes NetworkPolicy can restrict network communication between application tiers.

### Security Benefits (Qualified)

1. **Reduces attack surface:** If Backend is compromised, attacker cannot directly access database
2. **Enforces least-privilege networking:** Only explicitly allowed connections permitted
3. **Demonstrates policy enforcement:** Verifies CNI plugin enforces NetworkPolicy

### Important Qualifications

⚠️ **Security restriction and operational safety are separate properties**

- This policy improves network isolation (security benefit)
- This policy breaks required application functionality (operational failure)
- These are independent characteristics, not contradictory
- A change can simultaneously improve security and cause operational risk

⚠️ **This policy blocks a REQUIRED communication path**

- Backend legitimately needs PostgreSQL access
- Blocking this path causes operational failure
- This is intentional for research purposes

⚠️ **This is NOT a production-ready configuration**

- The baseline allows Backend → PostgreSQL for good reason
- A production policy would allow necessary traffic while denying others
- This restrictive policy demonstrates impact, not best practice

⚠️ **This experiment does NOT prove prediction capability**

- Milestone 2 only creates the failure scenario
- Prediction capability is future research work
- The goal is to establish a reproducible test case, not to claim prediction success

### Research Purpose

This policy creates a controlled failure scenario to study:

1. How security changes affect application behavior
2. Whether operational impact can be predicted (future work)
3. How evidence sources reveal dependencies (future work)
4. Whether safe remediation is possible (future work)

**This milestone focuses on: Creating the failure scenario**  
**Future milestones will focus on: Predicting and remediating it**

---

## 5. Expected Operational Impact

### Hypothesis

After applying `deny-backend-to-database` NetworkPolicy:

**Expected behavior:**

1. ✅ Frontend remains accessible (localhost:30080)
2. ✅ Frontend → Backend HTTP connectivity works
3. ✅ PostgreSQL pod remains Running
4. ❌ Backend → PostgreSQL connection **FAILS**
5. ❌ Backend `/health` reports database connectivity failure
6. ❌ Database-dependent backend requests fail
7. ❌ End-to-end application functionality broken

### Failure Mechanism

1. Backend application attempts to connect to `database-service:5432`
2. Kubernetes DNS resolves to database pod IP
3. Backend initiates TCP connection to port 5432
4. **CNI plugin drops packets** due to NetworkPolicy
5. Connection times out or refused
6. Python `psycopg2` connection raises `OperationalError`
7. Backend `/health` endpoint catches error, returns `"connected": false`
8. HTTP 503 response returned

### What Should NOT Fail

- Frontend pod accessibility
- Frontend → Backend network path
- Backend HTTP server (FastAPI should remain running)
- PostgreSQL pod itself (should remain healthy)
- Kubernetes DNS resolution

### Observable Symptoms

**Backend logs should show:**
```
OperationalError: could not connect to server: Connection timed out
```

**Backend `/health` should return:**
```json
{
  "status": "unhealthy",
  "application": {
    "status": "running"
  },
  "database": {
    "connected": false,
    "error": "could not connect to server..."
  }
}
```

**Frontend UI should show:**
- ❌ Database Connected: false
- ❌ Overall Status: unhealthy

---

## 6. Verification Methodology

### Script: `scripts/verify-network-policy.sh`

**Purpose:** Verify post-policy behavioral state

**Checks:**

1. **Cluster health** - Control plane running
2. **Pod status** - All pods Running (including database)
3. **Frontend accessible** - HTTP 200 from localhost:30080
4. **Frontend → Backend** - Network connectivity verified
5. **Backend → Database BLOCKED** - Connection fails as expected
6. **Backend health indicates failure** - `/health` returns 503 and `"connected": false`
7. **Database pod healthy** - PostgreSQL itself is running
8. **Failure attribution** - Failure is due to NetworkPolicy, not pod crash

### Verification Approach

**Establish behavioral sequence:**

**BEFORE applying policy:**
- Backend → PostgreSQL = working
- Backend `/health` = healthy, `"database.connected": true`
- End-to-end = working

**AFTER applying policy:**
- NetworkPolicy object exists
- PostgreSQL pod = Running (not crashed)
- Frontend → Backend = still working
- **Backend → PostgreSQL = BLOCKED** (network-level)
- Backend `/health` = unhealthy, `"database.connected": false`
- Database-dependent functionality = failing

**AFTER removing policy:**
- NetworkPolicy deleted
- Backend → PostgreSQL = working again
- Backend `/health` = healthy again
- End-to-end = restored

**Verification methodology:**

1. **Network-level connectivity test:**
   ```bash
   kubectl exec backend-pod -- nc -zv database-service 5432
   # OR
   kubectl exec backend-pod -- timeout 5 bash -c 'cat < /dev/null > /dev/tcp/database-service/5432'
   ```
   Expected after policy: Connection refused or timeout

2. **Application-level evidence:**
   ```bash
   kubectl exec backend-pod -- python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
   ```
   Expected: `"status": "unhealthy"`, `"database.connected": false`

3. **Pod status verification:**
   ```bash
   kubectl get pod -l app=database  # Should show Running
   kubectl get pod -l app=backend   # Should show Running
   ```

**Key distinctions:**
- Do NOT determine failure by checking NetworkPolicy object exists
- Test actual behavioral impact at network and application levels
- Verify failure is network connectivity, not pod crash
- Distinguish expected from observed results

---

## 7. Implementation Files

### New Files

```
kubernetes/policies/
└── isolate-database.yaml               # NEW

scripts/
├── apply-network-policy.sh             # NEW
├── verify-network-policy.sh            # NEW
└── remove-network-policy.sh            # NEW

network-policy-verification.json        # NEW (generated)
MILESTONE-2-SUMMARY.md                  # NEW
```

### Modified Files

**None** - Milestone 1 baseline remains unchanged

---

## 8. Helper Scripts Design

### `scripts/apply-network-policy.sh`

**Purpose:** Apply NetworkPolicy to poc-app namespace

**Steps:**
1. Verify cluster is running
2. Verify Milestone 1 baseline exists
3. Apply NetworkPolicy manifest
4. Wait for policy to propagate (~5 seconds)
5. Verify policy exists
6. Display warning about expected failure

**Output:**
```
Applying NetworkPolicy: isolate-database
⚠️  This will isolate PostgreSQL pods from ALL ingress traffic
⚠️  Backend → PostgreSQL is the required application communication path
⚠️  This will cause Backend database connectivity to fail
NetworkPolicy applied: isolate-database
Waiting for policy to propagate...
✅ Policy active

Expected operational impact:
  - Backend → PostgreSQL: BLOCKED
  - Backend health: will report database failure
  - Application functionality: will fail

Run: ./scripts/verify-network-policy.sh
```

---

### `scripts/verify-network-policy.sh`

**Purpose:** Verify post-policy behavioral state

**Checks:**

1. Cluster health
2. All pods Running
3. NetworkPolicy exists
4. Frontend accessible
5. Frontend → Backend network works
6. Backend → Database BLOCKED (expected failure)
7. Backend health indicates database failure
8. PostgreSQL pod itself is healthy
9. Failure is network-level, not crash

**Outputs:** `network-policy-verification.json`

**Structure:**
```json
{
  "timestamp": "...",
  "milestone": "2",
  "cluster": "poc-cluster",
  "namespace": "poc-app",
  "policy": {
    "name": "isolate-database",
    "status": "active",
    "description": "Isolate PostgreSQL pods from all ingress traffic"
  },
  "expected_behavior": {
    "frontend_accessible": true,
    "frontend_to_backend": "success",
    "backend_to_database": "blocked",
    "backend_health": "unhealthy",
    "database_pod": "running",
    "end_to_end": "failed"
  },
  "observed_behavior": {
    "frontend_accessible": null,
    "frontend_to_backend": null,
    "backend_to_database": null,
    "backend_health": null,
    "database_pod": null,
    "end_to_end": null
  },
  "verification_method": {
    "network_connectivity_test": "nc -zv database-service 5432",
    "application_health_test": "/health endpoint",
    "pod_status_test": "kubectl get pods"
  },
  "verification_results": {
    "policy_exists": null,
    "network_connectivity_blocked": null,
    "backend_health_indicates_failure": null,
    "postgres_pod_still_running": null
  },
  "experiment_hypothesis": "Applying NetworkPolicy that isolates PostgreSQL will block required Backend → PostgreSQL communication, causing application failure",
  "hypothesis_confirmed": null,
  "notes": "null fields to be populated after actual execution"
}
```

**Key changes:**
- Separate `expected_behavior` and `observed_behavior` fields
- `observed_behavior` starts as `null` (not populated until execution)
- `hypothesis_confirmed` starts as `null` (determined after execution)
- Includes `verification_method` documenting how tests were conducted
- Clear distinction: expected vs observed vs hypothesis confirmation

---

### `scripts/remove-network-policy.sh`

**Purpose:** Remove NetworkPolicy and restore baseline

**Steps:**
1. Delete NetworkPolicy
2. Wait for propagation (~5 seconds)
3. Verify policy removed
4. Wait for Backend to recover (~10 seconds)
5. Check Backend health
6. Verify baseline restored

**Output:**
```
Removing NetworkPolicy: isolate-database
NetworkPolicy deleted
Waiting for policy propagation and Backend recovery...
Testing Backend → PostgreSQL connectivity...
✅ Backend → PostgreSQL connectivity restored
✅ Backend health: healthy

Baseline appears restored.
Run: ./scripts/verify-baseline.sh (to confirm full baseline)
```

---

## 9. Experiment Record Format

### File: `network-policy-verification.json`

**Purpose:** Machine-readable experiment result

**Required Fields:**

- `timestamp` - When experiment was run
- `milestone` - "2"
- `cluster` - "poc-cluster"
- `namespace` - "poc-app"
- `policy.name` - NetworkPolicy name
- `policy.intent` - Security goal
- `expected_impact` - What should happen
- `verification` - Test results
- `observed_behavior` - Actual behavior
- `experiment_result` - Hypothesis vs observed

**Key distinction:**
- `expected_impact` - What we designed the policy to do
- `observed_behavior` - What actually happened
- `experiment_result.match` - Whether they agree

### Generation

Script `verify-network-policy.sh` generates this file automatically.

**Do NOT manually create** with fabricated results.

---

## 10. Documentation Requirements

### File: `MILESTONE-2-SUMMARY.md`

**Sections:**

1. **Overview** - Milestone 2 purpose
2. **Changes from Milestone 1** - What was added
3. **NetworkPolicy Explanation** - What it is, how it works
4. **Policy Design** - Specific policy used
5. **Security Intent** - Why this restriction
6. **Expected Operational Impact** - Predicted failure
7. **Verification Methodology** - How to test
8. **Actual Results** - What happened (after execution)
9. **Rollback Procedure** - How to restore baseline
10. **Research Implications** - Why this matters
11. **Limitations** - What this does NOT demonstrate
12. **Next Steps** - Milestone 3 preview

**Critical sections:**

**Security vs Operational Safety:**
> "This policy demonstrates an important research principle: security improvements do not necessarily mean operational safety. While restricting Backend → PostgreSQL reduces attack surface, it also breaks required application functionality. This trade-off is the core research question."

**Expected vs Observed:**
> "Expected: Backend → PostgreSQL blocked, database connectivity fails.  
> Observed: [To be filled after actual execution]  
> Match: [Yes/No after execution]"

---

## 11. Testing Procedure

### Pre-conditions

1. Milestone 1 baseline verified and working
2. `baseline-verification.json` shows all paths working
3. Kind cluster running
4. All pods Running

### Test Execution

```bash
# 1. Apply NetworkPolicy
./scripts/apply-network-policy.sh

# 2. Verify impact
./scripts/verify-network-policy.sh

# 3. Review results
cat network-policy-verification.json

# 4. Test in browser
# Open: http://localhost:30080
# Expected: Database connection error displayed

# 5. Check logs
kubectl logs -n poc-app -l app=backend --tail=20

# 6. Remove policy
./scripts/remove-network-policy.sh

# 7. Verify baseline restored
./scripts/verify-baseline.sh
```

### Success Criteria

**Policy application:**
- ✅ NetworkPolicy created in poc-app namespace
- ✅ Policy applies to database pods

**Operational impact (after policy):**
- ✅ Frontend accessible
- ✅ Frontend → Backend works
- ✅ Backend → PostgreSQL BLOCKED
- ✅ Backend health shows database failure
- ✅ PostgreSQL pod still Running
- ✅ Failure is network-level, not crash

**Verification:**
- ✅ `network-policy-verification.json` generated
- ✅ Observed matches expected
- ✅ Experiment result confirms hypothesis

**Rollback:**
- ✅ NetworkPolicy removed
- ✅ Backend → PostgreSQL restored
- ✅ Baseline verification passes again

---

## 12. Research Integrity Requirements

### Do NOT

- ❌ Claim test passed without execution
- ❌ Fake NetworkPolicy blocking behavior
- ❌ Manually return failure responses
- ❌ Hardcode failure in application
- ❌ Report expected result as observed without verification
- ❌ Skip behavioral testing

### DO

- ✅ Execute actual Kubernetes NetworkPolicy
- ✅ Let CNI plugin naturally block traffic
- ✅ Test behavioral impact, not just manifest existence
- ✅ Distinguish expected from observed results
- ✅ Preserve timestamps
- ✅ Record actual error messages
- ✅ Verify rollback restores functionality

### Experimental Rigor

This is a **research project**, not just a demonstration.

The experiment must:
1. Be reproducible
2. Test actual NetworkPolicy enforcement
3. Distinguish hypothesis from observation
4. Record actual measurements
5. Support falsifiability

**If NetworkPolicy does NOT block traffic:**
- Report that observation
- Investigate why (CNI plugin support, policy syntax, etc.)
- Do NOT fabricate blocking behavior

---

## 13. Out of Scope for Milestone 2

### NOT Implemented

- ❌ Evidence extraction from Kubernetes YAML
- ❌ Evidence extraction from application code
- ❌ Evidence extraction from runtime (OpenTelemetry)
- ❌ Evidence/dependency graph construction
- ❌ NetworkX graph building
- ❌ Impact prediction engine
- ❌ Confidence scoring
- ❌ Evidence Gate (SAFE/RISKY/INSUFFICIENT)
- ❌ Remediation generation
- ❌ Remediation validation
- ❌ ML models
- ❌ Comparison with baselines (A/B/C/D)
- ❌ Dashboard

### Why Deferred

**Milestone 2 focus:** Create the experimental failure scenario

**Future milestones will:**
- Milestone 3: Add OpenTelemetry/Jaeger (runtime evidence)
- Milestone 4+: Build evidence graph, prediction, gate, remediation

**Research progression:**
1. ✅ Milestone 1: Baseline working
2. ⏳ Milestone 2: Security change causes failure
3. 🔄 Future: Predict failure before applying
4. 🔄 Future: Generate safe remediation

---

## 14. Acceptance Criteria

### Implementation Complete

- [ ] NetworkPolicy manifest created
- [ ] Policy uses existing pod labels correctly
- [ ] Policy targets only Backend → PostgreSQL
- [ ] `apply-network-policy.sh` script created
- [ ] `verify-network-policy.sh` script created
- [ ] `remove-network-policy.sh` script created
- [ ] Experiment result format defined
- [ ] `MILESTONE-2-SUMMARY.md` created

### Behavioral Verification (After Execution)

**Post-policy:**
- [ ] Frontend accessible
- [ ] Frontend → Backend works
- [ ] PostgreSQL pod Running
- [ ] Backend → PostgreSQL ACTUALLY blocked (not faked)
- [ ] Backend `/health` returns 503 and `"connected": false`
- [ ] Backend logs show connection error
- [ ] Failure is network-level (NetworkPolicy), not crash
- [ ] `network-policy-verification.json` generated
- [ ] Observed matches expected

**Post-rollback:**
- [ ] NetworkPolicy removed
- [ ] Backend → PostgreSQL restored
- [ ] Backend `/health` returns 200 and `"connected": true`
- [ ] End-to-end functionality restored
- [ ] `baseline-verification.sh` passes

### Research Integrity

- [ ] No prediction implemented yet
- [ ] No evidence graph implemented yet
- [ ] No ML implemented
- [ ] Expected and observed clearly separated
- [ ] No fabricated results
- [ ] Actual Kubernetes NetworkPolicy used
- [ ] Behavioral impact tested, not just manifest existence

---

## 15. Known Limitations

### What This Demonstrates

✅ Kubernetes NetworkPolicy can restrict network communication  
✅ Security restrictions can cause operational failures  
✅ Failure can be detected via application health checks  
✅ Experiment is reproducible and reversible  

### What This Does NOT Demonstrate

❌ How to predict the failure before applying the policy  
❌ How to extract evidence from infrastructure/application/runtime  
❌ How to build a dependency graph  
❌ How to generate remediation  
❌ Whether prediction is better than infrastructure-only analysis  

**These are future research questions.**

### Edge Cases

1. **CNI plugin dependency:** NetworkPolicy requires CNI plugin support (Kind default supports it)
2. **Policy propagation delay:** Takes ~5-10 seconds for policy to take effect
3. **Existing connections:** Active connections may not be immediately dropped
4. **DNS not blocked:** DNS queries still work, only TCP connection blocked

---

## 16. File Structure Summary

```
Final-Year-Project/
├── kubernetes/
│   └── policies/
│       └── isolate-database.yaml               # NEW
│
├── scripts/
│   ├── apply-network-policy.sh                 # NEW
│   ├── verify-network-policy.sh                # NEW
│   └── remove-network-policy.sh                # NEW
│
├── .kiro/specs/
│   └── milestone-2-network-policy.md           # NEW (this file)
│
├── network-policy-verification.json            # NEW (generated)
├── MILESTONE-2-SUMMARY.md                      # NEW
└── baseline-verification.json                  # UNCHANGED (Milestone 1)
```

---

## 17. Implementation Checklist

### Phase 1: Design (Complete)
- [x] Inspect Milestone 1 labels
- [x] Design NetworkPolicy
- [x] Define verification methodology
- [x] Define experiment record format
- [x] Create specification document

### Phase 2: Implementation (Pending Approval)
- [ ] Create NetworkPolicy manifest
- [ ] Create apply script
- [ ] Create verification script
- [ ] Create removal script
- [ ] Create summary documentation

### Phase 3: Testing (Pending Implementation)
- [ ] Apply policy
- [ ] Execute verification
- [ ] Confirm blocking behavior
- [ ] Generate experiment result
- [ ] Remove policy
- [ ] Verify baseline restored

### Phase 4: Documentation (Pending Results)
- [ ] Record actual observed behavior
- [ ] Compare expected vs observed
- [ ] Document any discrepancies
- [ ] Finalize summary document

---

## 18. Review and Approval

**Status:** Ready for Review

**Questions for Reviewer:**

1. Does the NetworkPolicy design correctly target Backend → PostgreSQL?
2. Are the pod label selectors consistent with Milestone 1?
3. Is the verification methodology sufficient?
4. Is the experiment record format appropriate?
5. Are research integrity constraints clear?
6. Should any additional checks be included?

**After approval, proceed with implementation.**

---

## End of Specification

**Estimated Implementation Time:** 2-3 hours

**Risk:** Low - well-defined Kubernetes feature with clear behavior

**Dependencies:** Milestone 1 baseline (complete)

**Blocks:** Milestone 3+ (requires this experimental scenario)
