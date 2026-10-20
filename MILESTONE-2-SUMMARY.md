# Milestone 2: Kubernetes NetworkPolicy Security-Change Experiment

## Overview

Milestone 2 introduces a controlled security-change experiment using Kubernetes NetworkPolicy to demonstrate:

1. How security restrictions can affect application behavior
2. The operational impact of removing required communication paths
3. A reproducible failure scenario for future prediction research

**Milestone Status:** Implementation complete, ready for execution

**Date:** 2026-10-07

---

## What Changed from Milestone 1

### New Components

**Kubernetes NetworkPolicy:**
- Policy name: `isolate-database`
- Location: `kubernetes/policies/isolate-database.yaml`
- Effect: Isolates PostgreSQL pods from ALL ingress traffic

**Helper Scripts:**
- `scripts/apply-network-policy.sh` - Apply the policy
- `scripts/verify-network-policy.sh` - Verify behavioral impact
- `scripts/remove-network-policy.sh` - Rollback to baseline

**Documentation:**
- This summary document
- Experiment result: `network-policy-verification.json` (generated after execution)

### What Remained Unchanged

- Frontend application
- Backend application
- PostgreSQL database
- All Milestone 1 baseline components

---

## NetworkPolicy Explanation

### What is a Kubernetes NetworkPolicy?

A NetworkPolicy is a Kubernetes resource that controls network communication between pods.

**Key concepts:**
- **Pod selector:** Which pods the policy applies to
- **Policy types:** Ingress (incoming), Egress (outgoing), or both
- **Ingress/Egress rules:** Which traffic is allowed
- **Default behavior:** If no rules match, traffic is denied

**Important:** NetworkPolicy requires CNI plugin support (Kind's default CNI supports it).

### The `isolate-database` Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-database
  namespace: poc-app
spec:
  podSelector:
    matchLabels:
      app: database
  policyTypes:
  - Ingress
  ingress: []
```

**What it does:**

- **Targets:** All pods with label `app: database` (PostgreSQL pods)
- **Policy type:** Ingress (controls incoming connections)
- **Ingress rules:** Empty list `[]` = deny ALL ingress
- **Effect:** PostgreSQL pods cannot receive connections from ANY source

**Scope:**
- Namespace: `poc-app` only
- Does not affect egress (outgoing) from PostgreSQL
- Does not affect other pods (Frontend, Backend)

---

## Policy Design: Why This Specific Policy?

### Isolation vs Source-Specific Denial

**This policy:**
- Isolates PostgreSQL from ALL ingress traffic
- Not source-specific (doesn't name Backend)

**Why?**
- Simpler policy design
- In current architecture, Backend → PostgreSQL is the only required ingress path
- Effect is the same: removes required communication path

**A production policy would:**
- Explicitly allow Backend → PostgreSQL
- Deny all other sources

### Required Communication Path

**Current architecture requires:**
```
Backend → PostgreSQL
```

**After policy applied:**
```
Backend -X→ PostgreSQL  (blocked)
```

**Result:** Backend database connectivity fails

---

## Security Intent

### Primary Goal

Demonstrate network isolation using Kubernetes NetworkPolicy.

### Security Benefits

1. **Reduces attack surface**
   - If Backend is compromised, attacker cannot directly access database
   
2. **Enforces least-privilege networking**
   - Only explicitly allowed connections permitted
   
3. **Demonstrates policy enforcement**
   - Verifies CNI plugin enforces NetworkPolicy

### Important Qualifications

⚠️ **Security restriction and operational safety are separate properties**

- This policy improves network isolation (security benefit)
- This policy breaks required application functionality (operational failure)
- These are independent characteristics, not contradictory
- A change can simultaneously improve security and cause operational risk

⚠️ **This policy blocks REQUIRED communication**

- Backend legitimately needs PostgreSQL access
- This is intentional for research purposes
- Production would allow necessary traffic

⚠️ **This is NOT production-ready**

- Baseline allows Backend → PostgreSQL for good reason
- Production policy would allow necessary traffic while denying others
- This demonstrates impact, not best practice

⚠️ **This experiment does NOT prove prediction capability**

- Milestone 2 only creates the failure scenario
- Prediction capability is future research work
- Goal: establish reproducible test case

---

## Expected Operational Impact

### Hypothesis

After applying `isolate-database` NetworkPolicy:

**Expected to WORK:**
- ✅ Frontend accessible (localhost:30080)
- ✅ Frontend → Backend HTTP connectivity
- ✅ PostgreSQL pod remains Running

**Expected to FAIL:**
- ❌ Backend → PostgreSQL connection blocked
- ❌ Backend `/health` reports database failure
- ❌ Database-dependent functionality broken
- ❌ End-to-end application broken

### Failure Mechanism

1. Backend attempts connection to `database-service:5432`
2. Kubernetes DNS resolves to database pod IP
3. Backend initiates TCP connection
4. **CNI plugin drops packets** (NetworkPolicy enforcement)
5. Connection times out
6. Python `psycopg2` raises `OperationalError`
7. Backend `/health` returns 503 with `"connected": false`

### Observable Symptoms

**Backend logs:**
```
OperationalError: could not connect to server: Connection timed out
```

**Backend `/health` response:**
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

---

## Verification Methodology

### Behavioral Sequence Testing

**BEFORE applying policy:**
- Backend → PostgreSQL = working
- Backend `/health` = healthy

**AFTER applying policy:**
- NetworkPolicy exists
- PostgreSQL pod = Running (not crashed)
- Backend → PostgreSQL = BLOCKED (network-level)
- Backend `/health` = unhealthy

**AFTER removing policy:**
- NetworkPolicy deleted
- Backend → PostgreSQL = restored
- Backend `/health` = healthy

### Verification Methods

**1. Network-level connectivity test:**
```bash
kubectl exec backend-pod -- python3 -c "
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
result = sock.connect_ex(('database-service', 5432))
sock.close()
exit(0 if result == 0 else 1)
"
```
Expected after policy: Exit code 1 (connection blocked)

**2. Application-level evidence:**
```bash
kubectl exec backend-pod -- python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
```
Expected: `"status": "unhealthy"`, `"database.connected": false`

**3. Pod status verification:**
```bash
kubectl get pod -l app=database  # Should show Running
kubectl get pod -l app=backend   # Should show Running
```

**Key point:** Do NOT determine failure merely by checking NetworkPolicy object exists. Test actual behavioral impact.

---

## Actual Results

**Status:** Not yet executed

**Expected vs Observed:**

Expected: Backend → PostgreSQL blocked, database connectivity fails

Observed: [To be filled after execution]

Match: [To be determined after execution]

---

## Experiment Record

### File: `network-policy-verification.json`

Generated by `scripts/verify-network-policy.sh`

**Key fields:**
- `expected_behavior` - What should happen
- `observed_behavior` - What actually happened (populated after execution)
- `verification_method` - How tests were conducted
- `hypothesis_confirmed` - Whether prediction matched observation (determined after execution)

**Important:** `observed_behavior` and `hypothesis_confirmed` remain null until actual execution.

---

## Rollback Procedure

### To Remove Policy and Restore Baseline

```bash
./scripts/remove-network-policy.sh
```

**What it does:**
1. Deletes NetworkPolicy
2. Waits for propagation
3. Tests Backend → PostgreSQL connectivity
4. Verifies Backend health restored

**Verify full baseline restored:**
```bash
./scripts/verify-baseline.sh
```

Expected: All checks pass, matching original `baseline-verification.json`

---

## Testing Procedure

### Execution Steps

```bash
# 1. Apply NetworkPolicy
./scripts/apply-network-policy.sh

# 2. Verify impact
./scripts/verify-network-policy.sh

# 3. Review results
cat network-policy-verification.json

# 4. Test in browser
# Open: http://localhost:30080
# Expected: Database connection error

# 5. Check logs (optional)
kubectl logs -n poc-app -l app=backend --tail=20

# 6. Remove policy
./scripts/remove-network-policy.sh

# 7. Verify baseline restored
./scripts/verify-baseline.sh
```

---

## Research Implications

### What This Demonstrates

✅ Kubernetes NetworkPolicy can restrict network communication  
✅ Security restrictions can cause operational failures  
✅ Failure can be detected via application health checks  
✅ Experiment is reproducible and reversible  

### What This Does NOT Demonstrate

❌ How to predict failure before applying policy  
❌ How to extract evidence from infrastructure/application/runtime  
❌ How to build a dependency graph  
❌ How to generate remediation  
❌ Whether heterogeneous evidence improves prediction  

**These are future research questions.**

### Research Progression

1. ✅ **Milestone 1:** Baseline working application
2. ✅ **Milestone 2:** Security change causes reproducible failure
3. 🔄 **Future:** Predict failure BEFORE applying (using evidence graph)
4. 🔄 **Future:** Generate safe remediation (allow Backend → PostgreSQL, deny others)
5. 🔄 **Future:** Validate prediction vs reality
6. 🔄 **Future:** Compare evidence configurations (A/B/C/D)

---

## Limitations

### Scope

- **Single change type:** NetworkPolicy only (IAM, network rules deferred)
- **No prediction:** Milestone 2 creates scenario, doesn't predict it
- **No evidence extraction:** Infrastructure/application/runtime evidence deferred
- **No graph:** Dependency graph construction deferred
- **No remediation:** Minimal safe remediation deferred

### Edge Cases

1. **CNI plugin dependency:** Requires CNI with NetworkPolicy support
2. **Policy propagation delay:** Takes ~5-10 seconds to take effect
3. **Existing connections:** Active connections may not be immediately dropped
4. **DNS not blocked:** DNS queries still work, only TCP connection blocked

---

## Next Steps

### Immediate (Post-Execution)

- Execute experiment
- Populate `observed_behavior` in verification JSON
- Document any discrepancies between expected and observed
- Confirm rollback restores baseline

### Milestone 3+ (Future)

- Add OpenTelemetry/Jaeger (runtime evidence)
- Extract evidence from infrastructure configurations
- Extract evidence from application code
- Build unified evidence/dependency graph
- Implement impact prediction engine
- Implement evidence gate
- Compare evidence configurations (A/B/C/D)
- Generate and validate remediation

---

## File Structure Summary

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
├── network-policy-verification.json            # NEW (generated)
├── MILESTONE-2-SUMMARY.md                      # NEW (this file)
└── baseline-verification.json                  # UNCHANGED (Milestone 1)
```

---

## Success Criteria

### Implementation

- [x] NetworkPolicy manifest created
- [x] Apply script created
- [x] Verification script created
- [x] Remove script created
- [x] Summary documentation created

### Execution (After Running)

- [ ] Policy applied successfully
- [ ] Backend → PostgreSQL blocked at network level
- [ ] Backend health reports database failure
- [ ] PostgreSQL pod remains Running (not crashed)
- [ ] Frontend → Backend still works
- [ ] Verification JSON generated with actual observations
- [ ] Policy removal restores baseline

---

## Questions or Issues

If the experiment does NOT behave as expected:

1. **NetworkPolicy not blocking:** Check CNI plugin support
2. **Policy propagation:** Wait longer (up to 30 seconds)
3. **Backend crash instead of connectivity failure:** Check application logs
4. **DNS resolution failing:** Check CoreDNS status

**Report unexpected behavior honestly** - negative results are valuable research data.

---

## End of Summary

**Status:** Implementation complete, ready for execution

**Estimated execution time:** 10-15 minutes

**Risk:** Low - well-defined Kubernetes feature, easily reversible

---
