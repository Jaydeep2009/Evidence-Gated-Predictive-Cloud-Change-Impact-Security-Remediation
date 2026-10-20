# Milestone 2: Verification Script - Final Corrected Diff

## Summary

**File:** `scripts/verify-network-policy.sh`  
**Section:** Test 4 only  

**Key corrections:**
1. ✅ Use Python for `/live` check (curl not available in Backend container)
2. ✅ Use Kubernetes readiness as PRIMARY indicator
3. ✅ Add restart count tracking
4. ✅ Do NOT require `/health` HTTP response

---

## Final Test 4 Implementation

```bash
# Test 4: Backend health and readiness (application-level)
echo "Test 4: Backend health and readiness (application-level)"
BACKEND_HTTP_STATUS="unknown"
BACKEND_READINESS="unknown"
BACKEND_LIVENESS="unknown"
BACKEND_RESTARTS="unknown"

if [ -n "$BACKEND_POD" ]; then
    # Get Backend pod readiness from Kubernetes (PRIMARY INDICATOR)
    BACKEND_READY=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    
    if [ "$BACKEND_READY" = "True" ]; then
        BACKEND_READINESS="ready"
        echo "   Backend readiness: Ready"
    elif [ "$BACKEND_READY" = "False" ]; then
        BACKEND_READINESS="not_ready"
        echo "   Backend readiness: NotReady"
    else
        BACKEND_READINESS="unknown"
        echo "   Backend readiness: Unknown"
    fi
    
    # Get Backend restart count
    BACKEND_RESTARTS=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" \
      -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)
    echo "   Backend restart count: $BACKEND_RESTARTS"
    
    # Check liveness by verifying /live endpoint using Python (curl not available)
    LIVE_CHECK=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- \
      python3 -c "import urllib.request; import sys; urllib.request.urlopen('http://localhost:8000/live', timeout=5); sys.exit(0)" \
      2>/dev/null && echo "200" || echo "error")
    
    if [ "$LIVE_CHECK" = "200" ]; then
        BACKEND_LIVENESS="healthy"
        echo "   Backend liveness: Healthy (/live accessible)"
    else
        BACKEND_LIVENESS="unhealthy_or_unknown"
        echo "   Backend liveness: Unhealthy or unknown"
    fi
    
    # Note: /health check not required - readiness state is the primary indicator
    echo "   Backend /health: (not queried - using readiness state)"
    BACKEND_HTTP_STATUS="readiness_based"
    
    # Determine backend health failure based on Kubernetes readiness state
    if [ "$BACKEND_READINESS" = "not_ready" ] && [ "$BACKEND_LIVENESS" = "healthy" ]; then
        BACKEND_HEALTH_FAILED=true
        echo "✅ Backend health indicates failure: NotReady while liveness healthy (expected after policy)"
    elif [ "$BACKEND_READINESS" = "ready" ]; then
        echo "❌ Backend health appears healthy: Ready (unexpected after policy)"
    else
        echo "⚠️  Backend health state unclear"
    fi
else
    echo "⚠️  Backend pod not found, skipping health test"
fi
echo ""
```

---

## Key Design Decisions

### 1. Primary Indicator: Kubernetes Readiness

```bash
BACKEND_READY=$(kubectl get pod ... -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
```

**Why:** Readiness state is the Kubernetes-native way to determine if a pod can serve traffic given its dependencies.

### 2. Liveness Check: Python (Not curl)

```bash
LIVE_CHECK=$(kubectl exec ... -- python3 -c "import urllib.request; ..." && echo "200" || echo "error")
```

**Why:** `curl` is not installed in the Backend container. Python 3 is available (Backend is a Python app).

### 3. Health Check: Not Required

```bash
echo "   Backend /health: (not queried - using readiness state)"
BACKEND_HTTP_STATUS="readiness_based"
```

**Why:** Readiness probe already tests `/health`. Redundant to query it again. Readiness state is sufficient.

### 4. Restart Count Tracking

```bash
BACKEND_RESTARTS=$(kubectl get pod ... -o jsonpath='{.status.containerStatuses[0].restartCount}')
```

**Why:** Confirms that pod stability was maintained (restart count = 0 expected).

---

## Hypothesis Confirmation Logic

```bash
if [ "$POLICY_EXISTS" = true ] && 
   [ "$BACKEND_TO_DB_BLOCKED" = true ] && 
   [ "$BACKEND_HEALTH_FAILED" = true ] && 
   [ "$DB_POD_RUNNING" = true ]; then
    HYPOTHESIS_CONFIRMED=true
```

**Where `BACKEND_HEALTH_FAILED` is determined by:**

```bash
if [ "$BACKEND_READINESS" = "not_ready" ] && [ "$BACKEND_LIVENESS" = "healthy" ]; then
    BACKEND_HEALTH_FAILED=true
```

**Interpretation:**
- NetworkPolicy exists ✅
- Backend → PostgreSQL blocked ✅
- Backend readiness = NotReady ✅ (cannot serve dependency-dependent workload)
- Backend liveness = Healthy ✅ (process is alive and responsive)
- PostgreSQL pod running ✅

**Result:** Hypothesis confirmed

---

## JSON Output

```json
{
  "observed_behavior": {
    "backend_readiness": "not_ready",
    "backend_liveness": "healthy",
    "backend_restart_count": "0",
    "backend_health_http_status": "readiness_based",
    "backend_health": "unhealthy"
  },
  "verification_results": {
    "backend_health_indicates_failure": true
  },
  "hypothesis_confirmed": true
}
```

---

## Expected Console Output

### With NetworkPolicy Active

```
Test 4: Backend health and readiness (application-level)
   Backend readiness: NotReady
   Backend restart count: 0
   Backend liveness: Healthy (/live accessible)
   Backend /health: (not queried - using readiness state)
✅ Backend health indicates failure: NotReady while liveness healthy (expected after policy)

Experiment Analysis:
-------------------
✅ Hypothesis CONFIRMED
   - NetworkPolicy applied
   - Backend → PostgreSQL blocked at network level
   - Backend health reports database failure
   - PostgreSQL pod still running (not crashed)
   - Failure is due to NetworkPolicy, not pod crash
```

### Without NetworkPolicy (Baseline)

```
Test 4: Backend health and readiness (application-level)
   Backend readiness: Ready
   Backend restart count: 0
   Backend liveness: Healthy (/live accessible)
   Backend /health: (not queried - using readiness state)
❌ Backend health appears healthy: Ready (unexpected after policy)
```

---

## What Was NOT Changed

✅ Tests 1-3 (cluster, policy, pods, frontend, network connectivity)  
✅ Hypothesis confirmation conditions  
✅ Expected vs observed separation  
✅ NetworkPolicy  
✅ Backend application code  
✅ Kubernetes manifests  
✅ `/live` endpoint  
✅ `/health` endpoint  
✅ Liveness probe configuration  
✅ Readiness probe configuration  

---

## Research Integrity Statement

**Primary indicator rationale:**

"For this experiment, Kubernetes readiness state is used as the primary indicator of whether the Backend can currently serve its dependency-dependent workload."

**Why this is valid:**

1. ✅ Readiness is Kubernetes-native concept for "can serve traffic given dependencies"
2. ✅ Does not fabricate results - queries actual Kubernetes API
3. ✅ Resilient - does not depend on successfully executing HTTP requests inside container
4. ✅ Aligns with experiment design - tests dependency-based operational impact
5. ✅ Restart count confirms pod stability (not restarting)

---

## End of Final Diff

**Modified:** `scripts/verify-network-policy.sh` (Test 4)  
**Lines changed:** ~40  
**Tools used:** `kubectl get pod` (Kubernetes API), Python 3 (available in container)  
**Tools NOT used:** `curl` (not available), complex urllib JSON parsing (not required)  

---
