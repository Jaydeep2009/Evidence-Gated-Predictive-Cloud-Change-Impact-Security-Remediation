# Milestone 2: Liveness Correction - Implementation Summary

## Implementation Date
2026-10-07

## Issue
During Milestone 2 execution, applying NetworkPolicy `isolate-database` caused Backend pod restart loops because the liveness probe used `/health`, which checks PostgreSQL connectivity.

## Root Cause
Probe design issue: Using dependency-sensitive `/health` endpoint for BOTH liveness and readiness probes caused Kubernetes to restart the Backend pod when database became unreachable (inappropriate for liveness semantics).

## Correction Applied

### File 1: `services/backend/app/main.py`

**Change:** Added new `/live` endpoint

**Location:** After `/health` endpoint, before `/` root endpoint (line ~143)

**Code added:**
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

**Lines added:** 20 (including blank lines)

**Behavior:**
- ✅ Returns HTTP 200 unconditionally (if FastAPI is running)
- ✅ Does NOT query PostgreSQL
- ✅ Does NOT check external dependencies
- ✅ Minimal, fast response suitable for liveness probe

---

### File 2: `kubernetes/backend/deployment.yaml`

**Change:** Modified liveness probe path

**Location:** Line 47 (livenessProbe.httpGet.path)

**Code changed:**
```yaml
# BEFORE
            path: /health

# AFTER
            path: /live
```

**Lines changed:** 1

**Readiness probe UNCHANGED:**
```yaml
        readinessProbe:
          httpGet:
            path: /health    # Still uses /health
            port: 8000
```

---

## Git Diff Summary

```
Modified files: 2
  M kubernetes/backend/deployment.yaml  (1 line changed)
  M services/backend/app/main.py        (20 lines added)
```

**No other files modified.**

---

## What Was NOT Changed

✅ `/health` endpoint - still checks PostgreSQL connectivity  
✅ `/health` HTTP 200 behavior - when database reachable  
✅ `/health` HTTP 503 behavior - when database unreachable  
✅ Readiness probe - still uses `/health`  
✅ Frontend code  
✅ PostgreSQL deployment  
✅ NetworkPolicy manifest  
✅ Verification scripts  
✅ Any Milestone 1 baseline components  
✅ No prediction/evidence/graph/ML/remediation/telemetry  

---

## Expected Behavior After Deployment

### Baseline (WITHOUT NetworkPolicy)

**Liveness probe:** `/live` → HTTP 200 ✅ Pass  
**Readiness probe:** `/health` → HTTP 200 ✅ Pass  
**Pod status:** Running, Ready 1/1  
**Result:** Normal operation, both probes succeed  

### With NetworkPolicy Applied

**Liveness probe:** `/live` → HTTP 200 ✅ Pass  
**Readiness probe:** `/health` → HTTP 503 ❌ Fail  
**Pod status:** Running, Ready 0/1  
**Result:** Pod remains stable (not restarted), readiness failure expected behavior  

**Key improvement:** Backend pod will NOT restart during NetworkPolicy experiment.

---

## Next Steps

After this implementation:

1. ✅ **Implementation complete** - Files modified as approved
2. ⏳ **Rebuild Backend image** - Docker build required
3. ⏳ **Load image into Kind** - Make new image available
4. ⏳ **Apply updated deployment** - Roll out corrected probe configuration
5. ⏳ **Verify baseline** - Confirm both probes pass without NetworkPolicy
6. ⏳ **Re-run Milestone 2 experiment** - Verify pod stability with NetworkPolicy
7. ⏳ **Update documentation** - Record correction in Milestone summaries

---

## Verification Commands

### After deploying corrected Backend:

```bash
# Test /live endpoint
kubectl exec -n poc-app $(kubectl get pod -n poc-app -l app=backend -o jsonpath='{.items[0].metadata.name}') -- \
  curl -s http://localhost:8000/live

# Expected: {"status": "alive", ...}

# Test /health endpoint (should still check database)
kubectl exec -n poc-app $(kubectl get pod -n poc-app -l app=backend -o jsonpath='{.items[0].metadata.name}') -- \
  curl -s http://localhost:8000/health

# Expected: {"status": "healthy", "database": {"connected": true}, ...}

# Verify liveness probe configuration
kubectl describe pod -n poc-app -l app=backend | grep -A 3 "Liveness"

# Expected: Liveness: http-get http://:8000/live

# Verify readiness probe configuration
kubectl describe pod -n poc-app -l app=backend | grep -A 3 "Readiness"

# Expected: Readiness: http-get http://:8000/health
```

---

## Research Integrity Notes

### Why This Correction Is Valid

1. ✅ **Corrects a probe-design issue** discovered during Milestone 2 execution
2. ✅ **Does not modify experimental conditions** - NetworkPolicy, database, application semantics unchanged
3. ✅ **Improves observation quality** - Removes restart loop variability
4. ✅ **Aligns with Kubernetes best practices** - Proper liveness vs readiness semantics
5. ✅ **Minimal scope** - 2 files, ~21 lines total
6. ✅ **Preserves `/health` semantics** - Still checks database, still returns 503 on failure
7. ✅ **Does not fabricate results** - Makes measurement cleaner, doesn't change phenomenon

### What This Is NOT

❌ Hiding the database connectivity failure (still observable via `/health` and readiness)  
❌ Weakening the NetworkPolicy experiment (impact still fully observable)  
❌ Implementing prediction or evidence extraction  
❌ Modifying the NetworkPolicy or database  
❌ Changing application functionality  

### Documentation Language

**Preferred wording:**
- "Corrects a probe-design issue discovered during Milestone 2 execution"
- "Readiness failure expected Kubernetes behavior (to be verified)"

**Avoid:**
- "Fixes a Milestone 1 design flaw" (too strong)
- "No traffic routed" as observed fact (verify after deployment)

---

## Files Modified

| File | Type | Lines Changed | Purpose |
|------|------|---------------|---------|
| `services/backend/app/main.py` | Python | +20 | Add `/live` endpoint |
| `kubernetes/backend/deployment.yaml` | YAML | 1 | Use `/live` for liveness |

**Total:** 2 files, 21 lines

---

## Status

✅ **Implementation complete**  
⏳ **Deployment pending**  
⏳ **Verification pending**  
⏳ **Documentation updates pending**  

---

## End of Implementation Summary

**Implemented by:** Kiro (automated agent)  
**Approved by:** User  
**Date:** 2026-10-07  
**Purpose:** Enable stable Milestone 2 NetworkPolicy experiment observation

---
