# Milestone 2: Test 3 - Conservative Final Version

## Principle
Socket timeout is **consistent with** NetworkPolicy packet dropping, but does not **prove** NetworkPolicy is the cause. Report the observation and let the combination of all evidence support (or refute) the hypothesis.

---

## Final Test 3 Code

```bash
# Test 3: Backend → Database (network-level connectivity test using Python socket)
echo "Test 3: Backend → Database connectivity (network-level)"
BACKEND_TO_DB_SOCKET_CODE="unknown"
BACKEND_TO_DB_SOCKET_ERROR="unknown"
BACKEND_TO_DB_STATUS="unknown"

if [ -n "$BACKEND_POD" ]; then
    # Use Python socket test from inside Backend pod - capture connect_ex result and error interpretation
    SOCKET_TEST_OUTPUT=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import socket
import sys

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('database-service', 5432))
    sock.close()
    
    # Map common error codes to descriptions
    error_map = {
        0: 'connected',
        110: 'connection_timeout',
        111: 'connection_refused',
        113: 'no_route_to_host',
        101: 'network_unreachable'
    }
    error_desc = error_map.get(result, f'error_{result}')
    
    print(f'{result}:{error_desc}')
    sys.exit(0)
except Exception as e:
    print('exception:test_error')
    sys.exit(1)
" 2>/dev/null)

    # Parse result
    if [[ "$SOCKET_TEST_OUTPUT" =~ ^([0-9]+):(.+)$ ]]; then
        BACKEND_TO_DB_SOCKET_CODE="${BASH_REMATCH[1]}"
        BACKEND_TO_DB_SOCKET_ERROR="${BASH_REMATCH[2]}"
    elif [[ "$SOCKET_TEST_OUTPUT" =~ ^exception:(.+)$ ]]; then
        BACKEND_TO_DB_SOCKET_CODE="exception"
        BACKEND_TO_DB_SOCKET_ERROR="${BASH_REMATCH[1]}"
    else
        BACKEND_TO_DB_SOCKET_CODE="error"
        BACKEND_TO_DB_SOCKET_ERROR="unknown"
    fi
    
    # Classify result conservatively
    if [ "$BACKEND_TO_DB_SOCKET_CODE" = "0" ]; then
        # Successful connection
        BACKEND_TO_DB_STATUS="connected"
        echo "❌ Backend → Database connected (code 0: success)"
        echo "   Unexpected: NetworkPolicy should prevent this connection"
    elif [ "$BACKEND_TO_DB_SOCKET_ERROR" = "connection_timeout" ]; then
        # Timeout - consistent with packet drop but not definitive proof
        BACKEND_TO_DB_STATUS="connection_timeout"
        echo "⚠️  Backend → Database connection timeout (code $BACKEND_TO_DB_SOCKET_CODE)"
        echo "   Consistent with NetworkPolicy dropping packets (supporting evidence)"
    elif [ "$BACKEND_TO_DB_SOCKET_ERROR" = "connection_refused" ]; then
        # Connection refused - ambiguous cause
        BACKEND_TO_DB_STATUS="connection_refused"
        echo "⚠️  Backend → Database connection refused (code $BACKEND_TO_DB_SOCKET_CODE)"
        echo "   Ambiguous: could be NetworkPolicy or service unavailable"
    elif [ "$BACKEND_TO_DB_SOCKET_CODE" = "exception" ] || [ "$BACKEND_TO_DB_SOCKET_CODE" = "error" ]; then
        # Test execution failed
        BACKEND_TO_DB_STATUS="test_error"
        echo "⚠️  Backend → Database connectivity test error"
    else
        # Other error codes
        BACKEND_TO_DB_STATUS="connection_error"
        echo "⚠️  Backend → Database connection error: $BACKEND_TO_DB_SOCKET_ERROR (code $BACKEND_TO_DB_SOCKET_CODE)"
    fi
else
    echo "⚠️  Backend pod not found, skipping connectivity test"
fi
echo ""
```

**Key aspects:**
- Preserves actual socket code and error
- Timeout classified as `connection_timeout` (not `blocked`)
- Describes timeout as "consistent with" and "supporting evidence" (not proof)
- Other failures classified appropriately
- No single test result claims definitive causation

---

## Final Hypothesis Logic

```bash
# Determine hypothesis confirmation
echo "Experiment Analysis:"
echo "-------------------"
# Hypothesis: NetworkPolicy isolates PostgreSQL, affecting Backend→DB connectivity,
#             causing Backend readiness to fail while liveness remains healthy
echo "Required observations for hypothesis confirmation:"
echo "  1. NetworkPolicy exists"
echo "  2. Backend → Database connectivity affected (timeout or failure)"
echo "  3. Backend readiness is NotReady"
echo "  4. Backend liveness is healthy"
echo "  5. Backend pod phase is Running"
echo "  6. PostgreSQL pod phase is Running"
echo ""

# Check if all conditions are met
CONNECTIVITY_AFFECTED=false
if [ "$BACKEND_TO_DB_STATUS" = "connection_timeout" ] || \
   [ "$BACKEND_TO_DB_STATUS" = "connection_refused" ] || \
   [ "$BACKEND_TO_DB_STATUS" = "connection_error" ]; then
    CONNECTIVITY_AFFECTED=true
fi

if [ "$POLICY_EXISTS" = true ] && \
   [ "$CONNECTIVITY_AFFECTED" = true ] && \
   [ "$BACKEND_READINESS" = "not_ready" ] && \
   [ "$BACKEND_LIVENESS" = "healthy" ] && \
   [ "$BACKEND_PHASE" = "Running" ] && \
   [ "$DB_STATUS" = "Running" ]; then
    HYPOTHESIS_CONFIRMED=true
    echo "✅ Hypothesis CONFIRMED"
    echo ""
    echo "Supporting evidence:"
    echo "  ✓ NetworkPolicy '$POLICY_NAME' is active"
    echo "  ✓ Backend → PostgreSQL connectivity affected (status: $BACKEND_TO_DB_STATUS, code: $BACKEND_TO_DB_SOCKET_CODE)"
    echo "  ✓ Backend readiness is NotReady (cannot serve dependency-dependent workload)"
    echo "  ✓ Backend liveness is healthy (process alive, /live returns HTTP 200)"
    echo "  ✓ Backend pod phase is Running (not crashed, restart count: $BACKEND_RESTARTS)"
    echo "  ✓ PostgreSQL pod phase is Running (database operational)"
    echo ""
    echo "Interpretation:"
    echo "  The combination of NetworkPolicy presence, connectivity disruption, and readiness"
    echo "  failure (while liveness remains healthy) is consistent with the hypothesis that"
    echo "  NetworkPolicy isolation caused operational impact on the Backend."
else
    echo "❌ Hypothesis NOT confirmed"
    echo ""
    echo "Condition assessment:"
    if [ "$POLICY_EXISTS" = false ]; then
        echo "  ✗ NetworkPolicy not found"
    else
        echo "  ✓ NetworkPolicy exists"
    fi
    
    if [ "$CONNECTIVITY_AFFECTED" = false ]; then
        echo "  ✗ Backend → Database connectivity not affected (status: $BACKEND_TO_DB_STATUS)"
    else
        echo "  ✓ Backend → Database connectivity affected (status: $BACKEND_TO_DB_STATUS, code: $BACKEND_TO_DB_SOCKET_CODE)"
    fi
    
    if [ "$BACKEND_READINESS" != "not_ready" ]; then
        echo "  ✗ Backend readiness is not 'not_ready' (actual: $BACKEND_READINESS)"
    else
        echo "  ✓ Backend readiness is not_ready"
    fi
    
    if [ "$BACKEND_LIVENESS" != "healthy" ]; then
        echo "  ✗ Backend liveness is not 'healthy' (actual: $BACKEND_LIVENESS)"
    else
        echo "  ✓ Backend liveness is healthy"
    fi
    
    if [ "$BACKEND_PHASE" != "Running" ]; then
        echo "  ✗ Backend pod phase is not 'Running' (actual: $BACKEND_PHASE)"
    else
        echo "  ✓ Backend pod phase is Running"
    fi
    
    if [ "$DB_STATUS" != "Running" ]; then
        echo "  ✗ PostgreSQL pod phase is not 'Running' (actual: $DB_STATUS)"
    else
        echo "  ✓ PostgreSQL pod phase is Running"
    fi
fi
echo ""
```

**Key aspects:**
- `CONNECTIVITY_AFFECTED` is true for timeout, refused, or other errors
- Does not claim definitive causation
- Describes result as "consistent with the hypothesis"
- Uses "combination of evidence" rather than single proof
- All six conditions required
- Clear diagnostic output

---

## JSON Output - Connectivity Fields

```json
"observed_behavior": {
    ...
    "backend_to_database_status": "$BACKEND_TO_DB_STATUS",
    "backend_to_database_socket_code": "$BACKEND_TO_DB_SOCKET_CODE",
    "backend_to_database_socket_error": "$BACKEND_TO_DB_SOCKET_ERROR",
    ...
}
```

```json
"verification_results": {
    "policy_exists": $([ "$POLICY_EXISTS" = true ] && echo "true" || echo "false"),
    "backend_to_database_connectivity_affected": $([ "$CONNECTIVITY_AFFECTED" = true ] && echo "true" || echo "false"),
    "backend_readiness_not_ready": $([ "$BACKEND_READINESS" = "not_ready" ] && echo "true" || echo "false"),
    "backend_liveness_healthy": $([ "$BACKEND_LIVENESS" = "healthy" ] && echo "true" || echo "false"),
    "backend_phase_running": $([ "$BACKEND_PHASE" = "Running" ] && echo "true" || echo "false"),
    "postgres_pod_phase_running": $([ "$DB_STATUS" = "Running" ] && echo "true" || echo "false")
}
```

```json
"experiment_hypothesis": "Applying NetworkPolicy that isolates PostgreSQL will affect Backend → PostgreSQL connectivity, causing Backend readiness to become NotReady while liveness remains healthy and the pod continues running",
```

**Key aspects:**
- Records actual socket code and error from test execution
- `connectivity_affected` rather than `blocked` (more accurate)
- Hypothesis wording uses "affect" not "block" (more conservative)
- JSON values come from actual variables (no hardcoded examples)

---

## Status Classification

| Status | Meaning | Evidence Quality |
|--------|---------|------------------|
| `connected` | Socket succeeded (code 0) | ❌ Hypothesis NOT supported |
| `connection_timeout` | Timeout (code 110) | ⚠️ Supporting evidence (consistent with packet drop) |
| `connection_refused` | Refused (code 111) | ⚠️ Ambiguous (could be multiple causes) |
| `connection_error` | Other error codes | ⚠️ Supporting evidence (connectivity disrupted) |
| `test_error` | Test failed to execute | ❌ No evidence |

**Hypothesis confirmation:**
- Requires `connectivity_affected = true` (timeout, refused, or error)
- Plus all other conditions (readiness, liveness, phases)
- Interprets combination as "consistent with" NetworkPolicy impact
- Does not claim single test proves causation

---

## Conservative Language

### In Console Output

**Before (too strong):**
> "✅ Backend → Database BLOCKED (NetworkPolicy drop)"

**After (conservative):**
> "⚠️ Backend → Database connection timeout (code 110)"  
> "Consistent with NetworkPolicy dropping packets (supporting evidence)"

### In Hypothesis Confirmation

**Before (too strong):**
> "Backend → PostgreSQL blocked by NetworkPolicy"

**After (conservative):**
> "The combination of NetworkPolicy presence, connectivity disruption, and readiness  
> failure (while liveness remains healthy) is consistent with the hypothesis that  
> NetworkPolicy isolation caused operational impact on the Backend."

---

## Summary

### What This Achieves

✅ Preserves actual socket code and error  
✅ Does not claim timeout proves NetworkPolicy causation  
✅ Timeout described as "consistent with" and "supporting evidence"  
✅ Hypothesis requires combination of six conditions  
✅ Conservative language: "consistent with" not "proves"  
✅ `connectivity_affected` instead of `blocked`  
✅ JSON values from actual execution (no hardcoded examples)  

### What Was NOT Changed

✅ NetworkPolicy YAML  
✅ Application code  
✅ Kubernetes manifests  
✅ Tests 1, 2, 4  
✅ Baseline results  

---

## Ready for Final Approval

**Please review:**

1. **Test 3 classification:**
   - `connection_timeout` (not `blocked`)
   - Described as "supporting evidence"
   - Does not claim definitive proof

2. **Hypothesis condition:**
   - `CONNECTIVITY_AFFECTED = true` (timeout, refused, or error)
   - Requires all six conditions
   - Language: "consistent with hypothesis"

3. **JSON fields:**
   - `backend_to_database_status`
   - `backend_to_database_socket_code`
   - `backend_to_database_socket_error`
   - `connectivity_affected` (not `blocked`)

**Awaiting approval to implement these final conservative changes.**

