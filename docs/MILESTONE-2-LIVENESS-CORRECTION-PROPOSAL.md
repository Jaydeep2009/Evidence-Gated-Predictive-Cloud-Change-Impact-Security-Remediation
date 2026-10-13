# Milestone 2: Liveness Probe Correction Proposal

## Issue Discovered During Milestone 2 Execution

### Observed Behavior

When NetworkPolicy `isolate-database` is applied:

1. ✅ Backend → PostgreSQL is blocked (network-level, as intended)
2. ✅ Backend `/health` returns HTTP 503 (application-level failure, as intended)
3. ✅ PostgreSQL pod remains Running (expected)
4. ❌ Kubernetes repeatedly restarts Backend pod (unintended)

### Root Cause

**Current probe configuration (Milestone 1 design):**
- Liveness probe: `/health`
- Readiness probe: `/health`

**Problem:**
- `/health` endpoint checks PostgreSQL connectivity
- NetworkPolicy blocks Backend → PostgreSQL
- `/health` returns HTTP 503
- **Liveness probe fails** → Kubernetes interprets this as "application process crashed"
- Kubernetes restarts Backend pod repeatedly

### Evidence

```
Readiness probe failed: HTTP probe failed with statuscode: 503
Liveness probe failed
Container backend failed liveness probe, will be restarted
```

PostgreSQL pod remains Running throughout.

---

## Conceptual Issue

**Liveness vs Readiness semantics:**

- **Liveness:** "Is the application process alive and responsive?"
  - Should answer: Can the process receive HTTP requests?
  - Should NOT depend on external dependencies like databases
  - Failure → Restart the container

- **Readiness:** "Is the application ready to serve traffic?"
  - Should answer: Can the application fulfill requests given current dependency state?
  - Should include database connectivity, cache availability, etc.
  - Failure → Stop routing traffic, but don't restart

**Current Milestone 1 design flaw:**
- Uses dependency-sensitive `/health` for BOTH probes
- Database unavailability triggers restarts (inappropriate)
- Makes controlled failure experiments unstable

---

## Research Impact

**Without correction:**
- Backend pod restart loop makes experiment observation difficult
- Pod restarts introduce timing variability
- Hypothesis confirmation becomes unclear (is failure due to policy or restart loop?)
- Reproducibility compromised

**With correction:**
- Backend pod remains stable during NetworkPolicy experiment
- `/health` continues to report HTTP 503 (as intended)
- Readiness probe removes pod from service (appropriate)
- Liveness probe keeps pod running (appropriate)
- Clean observation of NetworkPolicy impact

---

## Proposed Minimal Correction

### 1. Add `/live` Endpoint to Backend

**File:** `services/backend/app/main.py`

**Add this endpoint (after `/health`, before `/`):**

```python
@app.get("/live")
async def liveness_check():
    """
    Liveness check endpoint - verifies application process is alive.
    
    Returns HTTP 200 if FastAPI application is responsive.
    Does NOT check database or external dependencies.
    
    Used by Kubernetes liveness probe to determine if container should be restarted.
    """
    return {
        "status": "alive",
        "application": {
            "name": "poc-backend",
            "version": "1.0.0"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

**Characteristics:**
- ✅ Returns HTTP 200 unconditionally (if FastAPI is running)
- ✅ Does NOT query PostgreSQL
- ✅ Does NOT check external dependencies
- ✅ Minimal response time
- ✅ Suitable for liveness probe

---

### 2. Update Kubernetes Liveness Probe

**File:** `kubernetes/backend/deployment.yaml`

**Change this section:**

```yaml
# BEFORE (current)
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 30
          timeoutSeconds: 5
```

**To:**

```yaml
# AFTER (corrected)
        livenessProbe:
          httpGet:
            path: /live
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 30
          timeoutSeconds: 5
```

**Keep readiness probe unchanged:**

```yaml
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
```

---

## What Does NOT Change

✅ `/health` endpoint semantics - still checks PostgreSQL  
✅ `/health` HTTP 200 when database reachable  
✅ `/health` HTTP 503 when database unreachable  
✅ Readiness probe still uses `/health`  
✅ Frontend still calls `/health` for status display  
✅ Verification scripts still check `/health`  
✅ NetworkPolicy configuration  
✅ PostgreSQL deployment  
✅ Frontend deployment  
✅ Any other Milestone 1 or 2 components  

---

## Files to Modify

### 1. `services/backend/app/main.py`

**Location:** Line ~133 (after `@app.get("/health")` function, before `@app.get("/")`)

**Addition:**

```python
@app.get("/live")
async def liveness_check():
    """
    Liveness check endpoint - verifies application process is alive.
    
    Returns HTTP 200 if FastAPI application is responsive.
    Does NOT check database or external dependencies.
    
    Used by Kubernetes liveness probe to determine if container should be restarted.
    """
    return {
        "status": "alive",
        "application": {
            "name": "poc-backend",
            "version": "1.0.0"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

**Lines added:** ~13
**Complexity:** Minimal (simple HTTP 200 response)

---

### 2. `kubernetes/backend/deployment.yaml`

**Location:** Line ~52 (livenessProbe path)

**Change:**

```yaml
# Line 52: Change from
            path: /health
# To
            path: /live
```

**Lines changed:** 1
**Impact:** Liveness probe behavior only

---

## Verification After Correction

### Expected Behavior WITHOUT NetworkPolicy (Baseline)

```bash
# Both probes should succeed
curl http://localhost:30080/api/live   # HTTP 200
curl http://localhost:30080/api/health # HTTP 200

# Pod status
kubectl get pod -n poc-app -l app=backend  # Running, Ready 1/1
```

**Liveness probe:** Pass (application alive)  
**Readiness probe:** Pass (database reachable)  
**Result:** Pod Running and Ready

---

### Expected Behavior WITH NetworkPolicy Applied

```bash
# Liveness should succeed, health should fail
curl http://localhost:30080/api/live   # HTTP 200
curl http://localhost:30080/api/health # HTTP 503

# Pod status
kubectl get pod -n poc-app -l app=backend  # Running, Ready 0/1
```

**Liveness probe:** Pass (application alive)  
**Readiness probe:** Fail (database unreachable)  
**Result:** Pod Running but NOT Ready (no traffic routed)

**Key improvement:** Pod remains Running (not restarted)

---

## Re-execution Plan

After implementing this correction:

1. Rebuild Backend image:
   ```bash
   docker build -t poc-backend:latest services/backend/
   kind load docker-image poc-backend:latest --name poc-cluster
   ```

2. Apply updated Kubernetes deployment:
   ```bash
   kubectl apply -f kubernetes/backend/deployment.yaml
   kubectl rollout status deployment backend-deployment -n poc-app
   ```

3. Verify baseline (without NetworkPolicy):
   ```bash
   ./scripts/verify-baseline.sh
   ```

4. Re-run Milestone 2 experiment:
   ```bash
   ./scripts/apply-network-policy.sh
   ./scripts/verify-network-policy.sh
   cat network-policy-verification.json
   ./scripts/remove-network-policy.sh
   ```

---

## Documentation Updates Required

After implementing correction:

1. Update `MILESTONE-1-SUMMARY.md`:
   - Document `/live` endpoint addition
   - Note liveness/readiness probe distinction
   - Mark as "corrected during Milestone 2"

2. Update `MILESTONE-2-SUMMARY.md`:
   - Document liveness probe restart loop issue
   - Note correction applied
   - Reference this proposal document

3. Create `docs/MILESTONE-2-LIVENESS-CORRECTION.md`:
   - Final record of what was changed
   - Before/after comparison
   - Lessons learned

---

## Research Integrity Notes

### Why This Correction Is Valid

1. ✅ **Fixes a Milestone 1 design flaw** - Not changing experiment, fixing infrastructure
2. ✅ **Discovered through actual execution** - Real experimental observation
3. ✅ **Does not fabricate results** - Makes observation cleaner, doesn't change phenomenon
4. ✅ **Improves reproducibility** - Removes restart loop variability
5. ✅ **Aligns with Kubernetes best practices** - Correct liveness vs readiness semantics
6. ✅ **Minimal change** - Single endpoint, single probe path change
7. ✅ **Preserves experimental semantics** - `/health` still checks database, NetworkPolicy still blocks

### What This Is NOT

❌ **Not hiding the failure** - `/health` still returns 503  
❌ **Not weakening the experiment** - NetworkPolicy impact still observable  
❌ **Not implementing prediction** - Still just controlled observation  
❌ **Not changing NetworkPolicy** - Policy isolation behavior unchanged  
❌ **Not modifying database** - PostgreSQL configuration unchanged  

### Analogy

This is like fixing a measurement instrument's side effect:

- **Before:** Temperature probe that also vibrates the sample (restart loop)
- **After:** Temperature probe that doesn't disturb the sample
- **Result:** Same phenomenon, cleaner measurement

---

## Comparison: Before vs After Correction

### Pod Lifecycle WITHOUT NetworkPolicy

**Before correction:**
```
Backend pod: Running, Ready 1/1
Liveness: Pass (/health → HTTP 200)
Readiness: Pass (/health → HTTP 200)
```

**After correction:**
```
Backend pod: Running, Ready 1/1
Liveness: Pass (/live → HTTP 200)
Readiness: Pass (/health → HTTP 200)
```

**Result:** Same (baseline unchanged)

---

### Pod Lifecycle WITH NetworkPolicy

**Before correction:**
```
Backend pod: CrashLoopBackOff or Restart loop
Liveness: Fail (/health → HTTP 503)
Readiness: Fail (/health → HTTP 503)
Pod restarts repeatedly
```

**After correction:**
```
Backend pod: Running, Ready 0/1
Liveness: Pass (/live → HTTP 200)
Readiness: Fail (/health → HTTP 503)
Pod remains stable (not restarted)
```

**Result:** Hypothesis observation becomes clear and stable

---

## Summary of Changes

| Component | File | Change | Lines | Impact |
|-----------|------|--------|-------|--------|
| Backend | `services/backend/app/main.py` | Add `/live` endpoint | +13 | New liveness endpoint |
| Kubernetes | `kubernetes/backend/deployment.yaml` | Change liveness path | 1 | Use `/live` for liveness |

**Total:** 2 files, ~14 lines

---

## Risks and Mitigation

### Risk 1: `/live` endpoint fails to respond

**Likelihood:** Very low (simple unconditional response)  
**Impact:** Pod would restart (same as before)  
**Mitigation:** Test `/live` endpoint before applying to cluster

### Risk 2: Readiness probe still causes instability

**Likelihood:** Low (readiness doesn't trigger restarts)  
**Impact:** Pod marked NotReady but not restarted  
**Mitigation:** This is desired behavior (pod shouldn't serve traffic when database unavailable)

### Risk 3: Introduces new baseline failure

**Likelihood:** Very low (baseline database connectivity unchanged)  
**Impact:** Would be detected by baseline verification  
**Mitigation:** Run `verify-baseline.sh` after applying correction

---

## Approval Checklist

Before implementing, confirm:

- [ ] Proposal reviewed and approved
- [ ] Rationale understood (liveness ≠ readiness)
- [ ] Only 2 files will be modified
- [ ] `/health` semantics preserved
- [ ] NetworkPolicy unchanged
- [ ] No prediction/evidence/graph/ML introduced
- [ ] Documentation plan clear
- [ ] Re-execution plan clear

---

## End of Proposal

**Status:** Ready for review  
**Date:** 2026-10-07  
**Purpose:** Correct Milestone 1 probe design to enable stable Milestone 2 experiment

---
