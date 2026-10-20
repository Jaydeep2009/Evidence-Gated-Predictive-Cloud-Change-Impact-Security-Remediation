# Milestone 2: Verification Script - Final Approved Changes

## Scope
- **Modify:** `scripts/verify-network-policy.sh` only
- **Do NOT modify:** NetworkPolicy YAML, application code, Kubernetes manifests, baseline tests, Tests 1-3

---

## Change 1: Test 3 - Backend → Database Connectivity

**Current Test 3 (lines ~104-124):**
```bash
# Test 3: Backend → Database (network-level connectivity test using Python socket)
echo "Test 3: Backend → Database connectivity (network-level)"
if [ -n "$BACKEND_POD" ]; then
    # Use Python socket test from inside Backend pod
    if kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import socket
import sys
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('database-service', 5432))
    sock.close()
    sys.exit(0 if result == 0 else 1)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
        echo "❌ Backend → Database NOT blocked (unexpected)"
    else
        BACKEND_TO_DB_BLOCKED=true
        echo "✅ Backend → Database BLOCKED (expected)"
    fi
else
    echo "⚠️  Backend pod not found, skipping connectivity test"
fi
echo ""
```

**REPLACE WITH:**
```bash
# Test 3: Backend → Database (network-level connectivity test using Python socket)
echo "Test 3: Backend → Database connectivity (network-level)"
BACKEND_TO_DB_RESULT="unknown"

if [ -n "$BACKEND_POD" ]; then
    # Use Python socket test from inside Backend pod - capture actual connect_ex result
    BACKEND_TO_DB_RESULT=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import socket
import sys
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('database-service', 5432))
    sock.close()
    print(result)  # 0 = connected, non-zero = connection failed
    sys.exit(0)
except Exception as e:
    print('error')
    sys.exit(1)
" 2>/dev/null)

    if [ "$BACKEND_TO_DB_RESULT" = "0" ]; then
        echo "❌ Backend → Database connected (unexpected after policy)"
        BACKEND_TO_DB_BLOCKED=false
    elif [ "$BACKEND_TO_DB_RESULT" != "error" ] && [ -n "$BACKEND_TO_DB_RESULT" ]; then
        # Non-zero result code = connection blocked/refused
        BACKEND_TO_DB_BLOCKED=true
        echo "✅ Backend → Database BLOCKED (connect_ex returned $BACKEND_TO_DB_RESULT)"
    else
        # Error executing test
        BACKEND_TO_DB_BLOCKED=false
        echo "⚠️  Backend → Database test inconclusive (error: $BACKEND_TO_DB_RESULT)"
    fi
else
    echo "⚠️  Backend pod not found, skipping connectivity test"
fi
echo ""
```

**Rationale:**
- Explicitly captures `socket.connect_ex()` return value
- 0 = connection succeeded (NOT blocked)
- Non-zero = connection failed (blocked)
- "error" = test execution failed (inconclusive)
- Does not rely on Python exit code alone

---

## Change 2: Test 4 - Backend Health and Readiness

**Current Test 4 (lines ~126-185):**
```bash
# Test 4: Backend health and readiness (application-level)
echo "Test 4: Backend health and readiness (application-level)"
BACKEND_HTTP_STATUS="unknown"
BACKEND_READINESS="unknown"
BACKEND_LIVENESS="unknown"
BACKEND_RESTARTS="unknown"

if [ -n "$BACKEND_POD" ]; then
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
    
    # Check liveness by verifying /live endpoint using Python
    LIVE_CHECK=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "import urllib.request; import sys; urllib.request.urlopen('http://localhost:8000/live', timeout=5); sys.exit(0)" 2>/dev/null && echo "200" || echo "error")
    
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

**REPLACE WITH:**
```bash
# Test 4: Backend health and readiness (application-level)
echo "Test 4: Backend health and readiness (application-level)"
BACKEND_PHASE="unknown"
BACKEND_READINESS="unknown"
BACKEND_LIVENESS="unknown"
BACKEND_RESTARTS="unknown"

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
    
    # Check liveness by verifying /live endpoint using Python - capture actual HTTP status
    LIVE_HTTP_STATUS=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import urllib.request
import urllib.error
import sys

try:
    response = urllib.request.urlopen('http://localhost:8000/live', timeout=5)
    print(response.getcode())
    sys.exit(0)
except urllib.error.HTTPError as e:
    # HTTP error (non-2xx status)
    print(e.code)
    sys.exit(1)
except urllib.error.URLError as e:
    # Connection error or timeout
    print('connection_error')
    sys.exit(1)
except Exception as e:
    # Unexpected error
    print('error')
    sys.exit(1)
" 2>/dev/null)
    
    if [ "$LIVE_HTTP_STATUS" = "200" ]; then
        BACKEND_LIVENESS="healthy"
        echo "   Backend liveness: Healthy (/live returns HTTP 200)"
    else
        BACKEND_LIVENESS="unhealthy_or_unknown"
        echo "   Backend liveness: Unhealthy or unknown (status: $LIVE_HTTP_STATUS)"
    fi
    
    echo "   Backend /health: (not queried by script - Kubernetes readiness probe tests this)"
else
    echo "⚠️  Backend pod not found, skipping health test"
fi
echo ""
```

**Rationale:**
- Added `BACKEND_PHASE` to capture pod phase separately
- Removed `BACKEND_HTTP_STATUS` (not used)
- Removed `BACKEND_HEALTH_FAILED` (derived flag - use explicit conditions)
- Liveness check explicitly imports `urllib.error`, handles HTTPError, URLError, and Exception
- Returns actual HTTP status code (200 = healthy, anything else = unhealthy)
- Does not query `/health` - clarified that Kubernetes readiness probe tests it

---

## Change 3: Hypothesis Confirmation Logic

**Current logic (lines ~187-206):**
```bash
# Determine hypothesis confirmation
echo "Experiment Analysis:"
echo "-------------------"
if [ "$POLICY_EXISTS" = true ] && [ "$BACKEND_TO_DB_BLOCKED" = true ] && [ "$BACKEND_HEALTH_FAILED" = true ] && [ "$DB_POD_RUNNING" = true ]; then
    HYPOTHESIS_CONFIRMED=true
    echo "✅ Hypothesis CONFIRMED"
    echo "   - NetworkPolicy applied"
    echo "   - Backend → PostgreSQL blocked at network level"
    echo "   - Backend health reports database failure"
    echo "   - PostgreSQL pod still running (not crashed)"
    echo "   - Failure is due to NetworkPolicy, not pod crash"
else
    echo "❌ Hypothesis NOT confirmed or inconclusive"
    if [ "$POLICY_EXISTS" = false ]; then
        echo "   - NetworkPolicy not found"
    fi
    if [ "$BACKEND_TO_DB_BLOCKED" = false ]; then
        echo "   - Backend → Database not blocked"
    fi
    if [ "$BACKEND_HEALTH_FAILED" = false ]; then
        echo "   - Backend health not indicating failure"
    fi
    if [ "$DB_POD_RUNNING" = false ]; then
        echo "   - Database pod not running"
    fi
fi
echo ""
```

**REPLACE WITH:**
```bash
# Determine hypothesis confirmation
echo "Experiment Analysis:"
echo "-------------------"
# Hypothesis: NetworkPolicy isolates PostgreSQL, blocking Backend→DB, causing Backend readiness to fail
#             while liveness remains healthy and pod continues running
if [ "$POLICY_EXISTS" = true ] && \
   [ "$BACKEND_TO_DB_BLOCKED" = true ] && \
   [ "$BACKEND_READINESS" = "not_ready" ] && \
   [ "$BACKEND_LIVENESS" = "healthy" ] && \
   [ "$BACKEND_PHASE" = "Running" ] && \
   [ "$DB_STATUS" = "Running" ]; then
    HYPOTHESIS_CONFIRMED=true
    echo "✅ Hypothesis CONFIRMED"
    echo "   - NetworkPolicy exists and is active"
    echo "   - Backend → PostgreSQL demonstrably blocked (socket connect_ex non-zero)"
    echo "   - Backend readiness is NotReady (cannot serve dependency-dependent workload)"
    echo "   - Backend liveness is healthy (process alive and /live returns HTTP 200)"
    echo "   - Backend pod phase is Running (not crashing, restart count: $BACKEND_RESTARTS)"
    echo "   - PostgreSQL pod phase is Running (database not crashed)"
    echo "   - Operational impact is due to NetworkPolicy isolating required dependency"
else
    echo "❌ Hypothesis NOT confirmed"
    if [ "$POLICY_EXISTS" = false ]; then
        echo "   ✗ NetworkPolicy not found"
    else
        echo "   ✓ NetworkPolicy exists"
    fi
    if [ "$BACKEND_TO_DB_BLOCKED" = false ]; then
        echo "   ✗ Backend → Database not demonstrably blocked"
    else
        echo "   ✓ Backend → Database blocked"
    fi
    if [ "$BACKEND_READINESS" != "not_ready" ]; then
        echo "   ✗ Backend readiness is not 'not_ready' (actual: $BACKEND_READINESS)"
    else
        echo "   ✓ Backend readiness is not_ready"
    fi
    if [ "$BACKEND_LIVENESS" != "healthy" ]; then
        echo "   ✗ Backend liveness is not 'healthy' (actual: $BACKEND_LIVENESS)"
    else
        echo "   ✓ Backend liveness is healthy"
    fi
    if [ "$BACKEND_PHASE" != "Running" ]; then
        echo "   ✗ Backend pod phase is not 'Running' (actual: $BACKEND_PHASE)"
    else
        echo "   ✓ Backend pod phase is Running"
    fi
    if [ "$DB_STATUS" != "Running" ]; then
        echo "   ✗ Database pod phase is not 'Running' (actual: $DB_STATUS)"
    else
        echo "   ✓ Database pod phase is Running"
    fi
fi
echo ""
```

**Rationale:**
- Uses `DB_STATUS` (already captured) instead of `DB_POD_RUNNING` flag
- Checks explicit conditions, not derived flags
- Requires:
  - `POLICY_EXISTS = true`
  - `BACKEND_TO_DB_BLOCKED = true` (from socket test)
  - `BACKEND_READINESS = "not_ready"`
  - `BACKEND_LIVENESS = "healthy"`
  - `BACKEND_PHASE = "Running"`
  - `DB_STATUS = "Running"`
- Clearer diagnostic output showing which conditions passed/failed
- Does not hard-code result

---

## Change 4: JSON Output

**Current JSON section (lines ~208-260):**
(Full current section too long to show here)

**REPLACE WITH:**
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
    "backend_restart_count": 0,
    "database_pod_phase": "running",
    "end_to_end": "not_verified"
  },
  "observed_behavior": {
    "frontend_accessible": $([ "$FRONTEND_OK" = true ] && echo "true" || echo "false"),
    "frontend_to_backend": "$([ "$FRONTEND_TO_BACKEND_OK" = true ] && echo "success" || echo "failed")",
    "backend_to_database": "$([ "$BACKEND_TO_DB_BLOCKED" = true ] && echo "blocked" || echo "not_blocked")",
    "backend_to_database_socket_result": "$BACKEND_TO_DB_RESULT",
    "backend_readiness": "$BACKEND_READINESS",
    "backend_liveness": "$BACKEND_LIVENESS",
    "backend_liveness_http_status": "$LIVE_HTTP_STATUS",
    "backend_phase": "$(echo $BACKEND_PHASE | tr '[:upper:]' '[:lower:]')",
    "backend_restart_count": "$BACKEND_RESTARTS",
    "database_pod_phase": "$(echo $DB_STATUS | tr '[:upper:]' '[:lower:]')",
    "end_to_end": "not_verified",
    "dependency_availability": "$([ "$BACKEND_READINESS" = "not_ready" ] && echo "unavailable" || echo "unknown")"
  },
  "verification_method": {
    "network_connectivity_test": "Python socket.connect_ex() from backend pod to database-service:5432",
    "application_health_test": "Kubernetes readiness state (primary) and /live endpoint HTTP status (liveness)",
    "pod_status_test": "kubectl get pod for phase and conditions"
  },
  "verification_results": {
    "policy_exists": $([ "$POLICY_EXISTS" = true ] && echo "true" || echo "false"),
    "network_connectivity_blocked": $([ "$BACKEND_TO_DB_BLOCKED" = true ] && echo "true" || echo "false"),
    "backend_readiness_not_ready": $([ "$BACKEND_READINESS" = "not_ready" ] && echo "true" || echo "false"),
    "backend_liveness_healthy": $([ "$BACKEND_LIVENESS" = "healthy" ] && echo "true" || echo "false"),
    "backend_phase_running": $([ "$BACKEND_PHASE" = "Running" ] && echo "true" || echo "false"),
    "postgres_pod_phase_running": $([ "$DB_STATUS" = "Running" ] && echo "true" || echo "false")
  },
  "experiment_hypothesis": "Applying NetworkPolicy that isolates PostgreSQL will block required Backend → PostgreSQL communication, causing Backend readiness to become NotReady while liveness remains healthy and the pod continues running",
  "hypothesis_confirmed": $([ "$HYPOTHESIS_CONFIRMED" = true ] && echo "true" || echo "false"),
  "notes": "Results from actual Kubernetes state at $TIMESTAMP. Restart count: $BACKEND_RESTARTS. Socket test result: $BACKEND_TO_DB_RESULT. Liveness HTTP status: $LIVE_HTTP_STATUS."
}
EOF
```

**Rationale:**
- `expected_behavior` includes all relevant fields with accurate expected values
- `observed_behavior` captures actual observations:
  - `backend_to_database_socket_result` shows actual socket test result
  - `backend_liveness_http_status` shows actual HTTP status from /live
  - `backend_phase` and `database_pod_phase` from Kubernetes
  - `backend_restart_count` preserved (not assumed to be zero)
  - `end_to_end` = "not_verified" (script doesn't test end-to-end)
  - `dependency_availability` = "unavailable" when readiness not_ready
- `verification_method.application_health_test` accurately describes approach
- `verification_results` matches hypothesis conditions
- `experiment_hypothesis` accurately describes what is tested
- `notes` includes actual observed values for traceability

---

## Summary of All Changes

### Variables Added
- `BACKEND_PHASE` - Pod phase from Kubernetes
- `BACKEND_TO_DB_RESULT` - Socket connect_ex result
- `LIVE_HTTP_STATUS` - HTTP status from /live

### Variables Removed
- `BACKEND_HTTP_STATUS` - Not used
- `BACKEND_HEALTH_FAILED` - Replaced with explicit conditions
- `DB_POD_RUNNING` - Use `DB_STATUS` directly

### Logic Changes
1. Test 3: Capture and evaluate socket.connect_ex() return value explicitly
2. Test 4: Explicit HTTP error handling, capture actual status code
3. Hypothesis: Check explicit conditions, not derived flags

### JSON Changes
1. `expected_behavior`: Added readiness, liveness, phases, restart count
2. `observed_behavior`: Added socket result, HTTP status, phases, dependency availability
3. `end_to_end`: "not_verified" (script doesn't test this)
4. `verification_method`: Accurate description
5. `verification_results`: Match hypothesis conditions

---

## What Was NOT Changed

✅ Tests 1-2 (cluster, policy, pods, frontend, frontend→backend)  
✅ NetworkPolicy YAML  
✅ Backend application code  
✅ Kubernetes manifests  
✅ Baseline verification  

---

**Ready for final review before implementation.**

