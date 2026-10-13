# Milestone 2: Verification Script Corrections

## Proposed Changes to `scripts/verify-network-policy.sh`

### 1. Test 4 - Corrected Liveness Check

**Replace lines ~148-159 with:**

```bash
# Test 4: Backend health and readiness (application-level)
echo "Test 4: Backend health and readiness (application-level)"
BACKEND_HTTP_STATUS="unknown"
BACKEND_READINESS="unknown"
BACKEND_LIVENESS="unknown"
BACKEND_RESTARTS="unknown"
BACKEND_PHASE="unknown"

if [ -n "$BACKEND_POD" ]; then
    # Get Backend pod phase
    BACKEND_PHASE=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
    echo "   Backend phase: $BACKEND_PHASE"
    
    # Get Backend pod readiness from Kubernetes
    BACKEND_READY=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    
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
    BACKEND_RESTARTS=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)
    echo "   Backend restart count: $BACKEND_RESTARTS"
    
    # Check liveness by verifying /live endpoint using Python - get actual HTTP status
    LIVE_HTTP_CODE=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import urllib.request
import sys
try:
    response = urllib.request.urlopen('http://localhost:8000/live', timeout=5)
    print(response.getcode())
    sys.exit(0)
except urllib.error.HTTPError as e:
    print(e.code)
    sys.exit(1)
except Exception:
    print('error')
    sys.exit(1)
" 2>/dev/null)
    
    if [ "$LIVE_HTTP_CODE" = "200" ]; then
        BACKEND_LIVENESS="healthy"
        echo "   Backend liveness: Healthy (/live returns HTTP 200)"
    else
        BACKEND_LIVENESS="unhealthy_or_unknown"
        echo "   Backend liveness: Unhealthy or unknown (HTTP status: $LIVE_HTTP_CODE)"
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

**Key changes:**
1. Added `BACKEND_PHASE` variable
2. Liveness check now explicitly reads HTTP status code (200 = healthy, anything else = unhealthy_or_unknown)
3. Handles HTTPError explicitly to capture non-200 status codes
4. Prints actual HTTP status in output for debugging

---

### 2. Hypothesis Confirmation Logic

**Replace lines ~186-206 with:**

```bash
# Determine hypothesis confirmation
echo "Experiment Analysis:"
echo "-------------------"
# Hypothesis requires: NetworkPolicy exists, Backend→DB blocked, Backend not ready, Backend liveness healthy, Backend phase Running, DB pod Running
if [ "$POLICY_EXISTS" = true ] && \
   [ "$BACKEND_TO_DB_BLOCKED" = true ] && \
   [ "$BACKEND_READINESS" = "not_ready" ] && \
   [ "$BACKEND_LIVENESS" = "healthy" ] && \
   [ "$BACKEND_PHASE" = "Running" ] && \
   [ "$DB_POD_RUNNING" = true ]; then
    HYPOTHESIS_CONFIRMED=true
    echo "✅ Hypothesis CONFIRMED"
    echo "   - NetworkPolicy applied"
    echo "   - Backend → PostgreSQL blocked at network level"
    echo "   - Backend readiness is NotReady (cannot serve dependency-dependent workload)"
    echo "   - Backend liveness is healthy (process is alive and responsive)"
    echo "   - Backend pod phase is Running (not crashing)"
    echo "   - PostgreSQL pod still running (not crashed)"
    echo "   - Failure is due to NetworkPolicy isolating required dependency"
else
    echo "❌ Hypothesis NOT confirmed or inconclusive"
    if [ "$POLICY_EXISTS" = false ]; then
        echo "   - NetworkPolicy not found"
    fi
    if [ "$BACKEND_TO_DB_BLOCKED" = false ]; then
        echo "   - Backend → Database not blocked"
    fi
    if [ "$BACKEND_READINESS" != "not_ready" ]; then
        echo "   - Backend readiness is not 'not_ready' (is: $BACKEND_READINESS)"
    fi
    if [ "$BACKEND_LIVENESS" != "healthy" ]; then
        echo "   - Backend liveness is not 'healthy' (is: $BACKEND_LIVENESS)"
    fi
    if [ "$BACKEND_PHASE" != "Running" ]; then
        echo "   - Backend pod phase is not 'Running' (is: $BACKEND_PHASE)"
    fi
    if [ "$DB_POD_RUNNING" = false ]; then
        echo "   - Database pod not running"
    fi
fi
echo ""
```

**Key changes:**
1. Changed from `BACKEND_HEALTH_FAILED` to explicit readiness/liveness checks
2. Added `BACKEND_PHASE = "Running"` requirement
3. Clearer diagnostic output showing which conditions failed
4. Does not hard-code result - derives from actual observations

---

### 3. JSON Output

**Replace lines ~208-260 with:**

```bash
# Generate JSON output
echo "Writing results to: $OUTPUT_FILE"
cat > "$OUTPUT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "milestone": "2",
  "cluster": "poc-cluster",
  "namespace": "$NAMESPACE",
  "policy": {
    "name": "$POLICY_NAME",
    "status": "$([ "$POLICY_EXISTS" = true ] && echo "active" || echo "not_found")",
    "description": "Isolate PostgreSQL pods from all ingress traffic"
  },
  "expected_behavior": {
    "frontend_accessible": true,
    "frontend_to_backend": "success",
    "backend_to_database": "blocked",
    "backend_readiness": "not_ready",
    "backend_liveness": "healthy",
    "backend_phase": "running",
    "database_pod": "running",
    "end_to_end": "dependency_unavailable"
  },
  "observed_behavior": {
    "frontend_accessible": $([ "$FRONTEND_OK" = true ] && echo "true" || echo "false"),
    "frontend_to_backend": "$([ "$FRONTEND_TO_BACKEND_OK" = true ] && echo "success" || echo "failed")",
    "backend_to_database": "$([ "$BACKEND_TO_DB_BLOCKED" = true ] && echo "blocked" || echo "not_blocked")",
    "backend_readiness": "$BACKEND_READINESS",
    "backend_liveness": "$BACKEND_LIVENESS",
    "backend_phase": "$(echo $BACKEND_PHASE | tr '[:upper:]' '[:lower:]')",
    "backend_restart_count": "$BACKEND_RESTARTS",
    "backend_health_http_status": "$BACKEND_HTTP_STATUS",
    "database_pod": "$([ "$DB_POD_RUNNING" = true ] && echo "running" || echo "not_running")",
    "database_pod_phase": "$(echo $DB_STATUS | tr '[:upper:]' '[:lower:]')",
    "end_to_end": "$([ "$BACKEND_READINESS" = "not_ready" ] && echo "dependency_unavailable" || echo "not_verified")"
  },
  "verification_method": {
    "network_connectivity_test": "Python socket.connect_ex() from backend pod to database-service:5432",
    "application_health_test": "Kubernetes readiness state (primary indicator) and /live endpoint (liveness check)",
    "pod_status_test": "kubectl get pods"
  },
  "verification_results": {
    "policy_exists": $([ "$POLICY_EXISTS" = true ] && echo "true" || echo "false"),
    "network_connectivity_blocked": $([ "$BACKEND_TO_DB_BLOCKED" = true ] && echo "true" || echo "false"),
    "backend_readiness_not_ready": $([ "$BACKEND_READINESS" = "not_ready" ] && echo "true" || echo "false"),
    "backend_liveness_healthy": $([ "$BACKEND_LIVENESS" = "healthy" ] && echo "true" || echo "false"),
    "backend_phase_running": $([ "$BACKEND_PHASE" = "Running" ] && echo "true" || echo "false"),
    "postgres_pod_still_running": $([ "$DB_POD_RUNNING" = true ] && echo "true" || echo "false")
  },
  "experiment_hypothesis": "Applying NetworkPolicy that isolates PostgreSQL will block required Backend → PostgreSQL communication, causing Backend readiness to fail while liveness remains healthy and the pod continues running",
  "hypothesis_confirmed": $([ "$HYPOTHESIS_CONFIRMED" = true ] && echo "true" || echo "false"),
  "notes": "Results populated after actual execution at $TIMESTAMP"
}
EOF
```

**Key changes:**
1. Updated `expected_behavior` to include `backend_readiness`, `backend_liveness`, `backend_phase`
2. Changed `end_to_end` from "failed" to "dependency_unavailable" (more accurate)
3. Added `backend_phase` and `database_pod_phase` to `observed_behavior`
4. Updated `verification_method.application_health_test` to accurately describe the method
5. Updated `verification_results` to match new hypothesis conditions
6. Updated `experiment_hypothesis` to accurately describe what is being tested

---

## Summary of Changes

### Variables Added
- `BACKEND_PHASE` - captures `.status.phase` from Kubernetes

### Liveness Check Improved
- Now explicitly reads HTTP status code from `/live`
- Only sets `healthy` when status is exactly 200
- Handles HTTPError to capture non-200 responses
- Shows actual status in output

### Hypothesis Logic Updated
- Requires `BACKEND_READINESS = "not_ready"`
- Requires `BACKEND_LIVENESS = "healthy"`
- Requires `BACKEND_PHASE = "Running"`
- Requires `DB_POD_RUNNING = true`
- Does not use derived `BACKEND_HEALTH_FAILED` flag

### JSON Accuracy
- `expected_behavior` includes readiness/liveness/phase
- `end_to_end` uses "dependency_unavailable" instead of "failed"
- `backend_phase` and `database_pod_phase` included
- `verification_method` accurately describes approach
- `verification_results` matches hypothesis conditions

---

## What Was NOT Changed

✅ Tests 1-3 (cluster, policy, pods, frontend, network connectivity)  
✅ NetworkPolicy  
✅ Backend application  
✅ Kubernetes manifests  
✅ Baseline results  

---

**Ready for review. Do NOT implement yet.**

