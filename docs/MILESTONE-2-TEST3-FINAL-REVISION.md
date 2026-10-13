# Milestone 2: Test 3 Final Revision - Socket Connectivity Interpretation

## Issue
Current proposal sets `BACKEND_TO_DB_BLOCKED=true` for any non-zero `socket.connect_ex()` result. This is too broad - error codes like 111 (connection refused) are not conclusive proof of NetworkPolicy drops.

## Revised Test 3

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
import errno
import sys

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('database-service', 5432))
    sock.close()
    
    # Map common error codes to descriptions
    error_map = {
        0: 'connected',
        111: 'connection_refused',
        110: 'connection_timeout',
        113: 'no_route_to_host',
        101: 'network_unreachable'
    }
    error_desc = error_map.get(result, f'error_{result}')
    
    print(f'{result}:{error_desc}')
    sys.exit(0)
except Exception as e:
    print('error:exception')
    sys.exit(1)
" 2>/dev/null)

    # Parse result
    if [[ "$SOCKET_TEST_OUTPUT" =~ ^([0-9]+):(.+)$ ]]; then
        BACKEND_TO_DB_SOCKET_CODE="${BASH_REMATCH[1]}"
        BACKEND_TO_DB_SOCKET_ERROR="${BASH_REMATCH[2]}"
    else
        BACKEND_TO_DB_SOCKET_CODE="error"
        BACKEND_TO_DB_SOCKET_ERROR="$SOCKET_TEST_OUTPUT"
    fi
    
    # Interpret result
    if [ "$BACKEND_TO_DB_SOCKET_CODE" = "0" ]; then
        BACKEND_TO_DB_STATUS="connected"
        echo "❌ Backend → Database connected (unexpected after policy)"
    elif [ "$BACKEND_TO_DB_SOCKET_ERROR" = "connection_timeout" ]; then
        # Timeout is consistent with dropped packets (NetworkPolicy behavior)
        BACKEND_TO_DB_STATUS="blocked"
        echo "✅ Backend → Database BLOCKED (connection timeout - consistent with NetworkPolicy drop)"
    elif [ "$BACKEND_TO_DB_SOCKET_ERROR" = "connection_refused" ]; then
        # Connection refused could be NetworkPolicy or could be service/port issue
        BACKEND_TO_DB_STATUS="connection_failed"
        echo "⚠️  Backend → Database connection failed (refused - code $BACKEND_TO_DB_SOCKET_CODE)"
        echo "   Note: Connection refused is not conclusive proof of NetworkPolicy drop"
    elif [ "$BACKEND_TO_DB_SOCKET_CODE" = "error" ]; then
        BACKEND_TO_DB_STATUS="test_error"
        echo "⚠️  Backend → Database connectivity test error"
    else
        # Other error codes
        BACKEND_TO_DB_STATUS="connection_failed"
        echo "⚠️  Backend → Database connection failed (error: $BACKEND_TO_DB_SOCKET_ERROR, code: $BACKEND_TO_DB_SOCKET_CODE)"
    fi
else
    echo "⚠️  Backend pod not found, skipping connectivity test"
fi
echo ""
```

## Key Changes

### Variables
- `BACKEND_TO_DB_SOCKET_CODE` - Actual integer return code from connect_ex()
- `BACKEND_TO_DB_SOCKET_ERROR` - Human-readable error description
- `BACKEND_TO_DB_STATUS` - Interpreted status: "connected", "blocked", "connection_failed", "test_error"

### Interpretation Logic

**Connected (code 0):**
- Status: `connected`
- Means: Connection succeeded
- Hypothesis: NOT confirmed (policy not blocking)

**Connection timeout (code 110):**
- Status: `blocked`
- Means: Packets dropped, consistent with NetworkPolicy behavior
- Hypothesis: Can contribute to confirmation

**Connection refused (code 111):**
- Status: `connection_failed`
- Means: Connection actively refused (could be policy, could be service issue)
- Hypothesis: NOT conclusive - insufficient evidence

**Other error codes:**
- Status: `connection_failed`
- Means: Network error of some kind
- Hypothesis: NOT conclusive

**Test execution error:**
- Status: `test_error`
- Means: Could not execute test
- Hypothesis: NOT conclusive

---

## Revised Hypothesis Logic

```bash
# Determine hypothesis confirmation
echo "Experiment Analysis:"
echo "-------------------"
# Hypothesis: NetworkPolicy isolates PostgreSQL, blocking Backend→DB, causing Backend readiness to fail
#             while liveness remains healthy and pod continues running
if [ "$POLICY_EXISTS" = true ] && \
   [ "$BACKEND_TO_DB_STATUS" = "blocked" ] && \
   [ "$BACKEND_READINESS" = "not_ready" ] && \
   [ "$BACKEND_LIVENESS" = "healthy" ] && \
   [ "$BACKEND_PHASE" = "Running" ] && \
   [ "$DB_STATUS" = "Running" ]; then
    HYPOTHESIS_CONFIRMED=true
    echo "✅ Hypothesis CONFIRMED"
    echo "   - NetworkPolicy exists and is active"
    echo "   - Backend → PostgreSQL blocked (socket timeout - code $BACKEND_TO_DB_SOCKET_CODE)"
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
    if [ "$BACKEND_TO_DB_STATUS" != "blocked" ]; then
        echo "   ✗ Backend → Database not demonstrably blocked (status: $BACKEND_TO_DB_STATUS, code: $BACKEND_TO_DB_SOCKET_CODE)"
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

**Key change:** Requires `BACKEND_TO_DB_STATUS = "blocked"` (not just any connection failure)

---

## Revised JSON Output - Connectivity Section

```json
"observed_behavior": {
    ...
    "backend_to_database": "$(
        case "$BACKEND_TO_DB_STATUS" in
            blocked) echo "blocked" ;;
            connected) echo "connected" ;;
            connection_failed) echo "connection_failed" ;;
            test_error) echo "test_error" ;;
            *) echo "unknown" ;;
        esac
    )",
    "backend_to_database_socket_code": "$BACKEND_TO_DB_SOCKET_CODE",
    "backend_to_database_socket_error": "$BACKEND_TO_DB_SOCKET_ERROR",
    ...
}
```

```json
"verification_results": {
    "policy_exists": $([ "$POLICY_EXISTS" = true ] && echo "true" || echo "false"),
    "backend_to_database_blocked": $([ "$BACKEND_TO_DB_STATUS" = "blocked" ] && echo "true" || echo "false"),
    ...
}
```

---

## Error Code Interpretation Reference

### Common socket.connect_ex() codes:

| Code | errno constant | Description | Interpretation |
|------|----------------|-------------|----------------|
| 0 | - | Success | Connected |
| 110 | ETIMEDOUT | Connection timeout | **Blocked (NetworkPolicy drops packets)** |
| 111 | ECONNREFUSED | Connection refused | Connection failed (not conclusive) |
| 113 | EHOSTUNREACH | No route to host | Connection failed |
| 101 | ENETUNREACH | Network unreachable | Connection failed |

**Why timeout is more conclusive:**
- NetworkPolicy drops packets silently
- Client waits until timeout
- No active refusal, just silence
- Connection refused (111) could be: service not listening, wrong port, or NetworkPolicy

**Conservative approach:**
- Only classify as "blocked" when evidence strongly suggests NetworkPolicy behavior
- Preserve actual error codes for analysis
- Don't claim NetworkPolicy caused failure without sufficient evidence

---

## Summary

### Changes from Previous Version

1. **Added error code mapping** - Interprets common socket error codes
2. **Distinguish blocked vs failed** - "blocked" requires strong evidence (timeout)
3. **Connection refused = inconclusive** - Does not confirm hypothesis
4. **Preserve raw data** - Socket code and error description both recorded
5. **Hypothesis requires "blocked"** - Not just any connection failure

### What This Addresses

✅ Does not claim NetworkPolicy caused failure based on ambiguous error  
✅ Connection timeout (packet drop) is interpreted as blocked  
✅ Connection refused is not conclusive  
✅ Actual socket code preserved in JSON  
✅ Expected vs observed separated  
✅ Hypothesis requires demonstrable blocking  

---

## Ready for Final Review

**Changes affect:**
- Test 3 socket connectivity interpretation
- Hypothesis confirmation logic
- JSON `observed_behavior.backend_to_database*` fields
- JSON `verification_results.backend_to_database_blocked`

**Does NOT change:**
- NetworkPolicy
- Application code
- Kubernetes manifests
- Tests 1, 2, 4
- Baseline results

---
