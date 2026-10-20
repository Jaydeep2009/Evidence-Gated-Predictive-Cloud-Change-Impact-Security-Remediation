# Milestone 2: Verification Script Final Implementation

**Date:** 2026-10-06  
**Status:** Implemented, awaiting user review and execution

---

## Summary

Implemented the final conservative version of Test 3 and hypothesis logic in `scripts/verify-network-policy.sh` with two critical safeguards:

1. **Robust error handling** that distinguishes kubectl failures from Python exceptions
2. **Strict hypothesis confirmation** requiring `connection_timeout` specifically (not refused/error)

---

## Key Safeguards Implemented

### 1. Python Exception vs kubectl Failure Distinction

```bash
# Execute socket test and capture exit status
SOCKET_TEST_OUTPUT=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import socket
import sys
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    result = s.connect_ex(('database-service', 5432))
    s.close()
    print(result)
    sys.exit(0)
except Exception as e:
    print('PYTHON_EXCEPTION', file=sys.stderr)
    sys.exit(1)
" 2>&1)
SOCKET_TEST_EXIT=$?

# Validate execution
if [ $SOCKET_TEST_EXIT -ne 0 ]; then
    if echo "$SOCKET_TEST_OUTPUT" | grep -q "PYTHON_EXCEPTION"; then
        BACKEND_TO_DB_SOCKET_ERROR="python_exception"
    else
        BACKEND_TO_DB_SOCKET_ERROR="kubectl_exec_failed"
    fi
elif [ -z "$SOCKET_TEST_OUTPUT" ]; then
    BACKEND_TO_DB_SOCKET_ERROR="empty_output"
elif ! [[ "$SOCKET_TEST_OUTPUT" =~ ^[0-9]+$ ]]; then
    BACKEND_TO_DB_SOCKET_ERROR="malformed_output"
fi
```

**Result:** Neither Python exceptions nor kubectl failures can be misclassified as `connection_timeout`.

### 2. Linux-Specific Socket Code Interpretation

```bash
# Classify the result conservatively (Linux-specific interpretation)
if [ "$SOCKET_TEST_OUTPUT" = "0" ]; then
    BACKEND_TO_DB_STATUS="connected"
elif [ "$SOCKET_TEST_OUTPUT" = "110" ]; then
    BACKEND_TO_DB_STATUS="connection_timeout"
    BACKEND_TO_DB_SOCKET_ERROR="ETIMEDOUT"
elif [ "$SOCKET_TEST_OUTPUT" = "111" ]; then
    BACKEND_TO_DB_STATUS="connection_refused"
    BACKEND_TO_DB_SOCKET_ERROR="ECONNREFUSED"
# ... other codes
```

**Result:** Error code 110 is explicitly documented as Linux-specific ETIMEDOUT interpretation.

---

## Test 3 Implementation

### Variables Set

- `BACKEND_TO_DB_SOCKET_CODE` - Raw numeric code or "error"/"unknown"/"malformed"
- `BACKEND_TO_DB_STATUS` - Classification: "connected", "connection_timeout", "connection_refused", "connection_error", "test_error"
- `BACKEND_TO_DB_SOCKET_ERROR` - Human-readable error or error type

### Conservative Language

```
Connection timeout observed. This result is consistent with NetworkPolicy blocking traffic,
but does not definitively prove causation without corroborating evidence from pod state.
```

---

## Test 4 Implementation

### Variables Set

- `BACKEND_PHASE` - Kubernetes pod phase
- `BACKEND_READINESS` - "ready", "not_ready", or "unknown"
- `BACKEND_LIVENESS` - "healthy" or "unhealthy" (from /live endpoint)
- `BACKEND_RESTARTS` - Restart count

### Liveness Check

```bash
LIVE_CHECK=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import urllib.request
import sys
try:
    response = urllib.request.urlopen('http://localhost:8000/live', timeout=5)
    sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null && echo "healthy" || echo "unhealthy")
```

---

## Hypothesis Logic Implementation

### Six Required Conditions

```bash
if [ "$POLICY_EXISTS" = true ] && \
   [ "$BACKEND_TO_DB_STATUS" = "connection_timeout" ] && \
   [ "$BACKEND_READINESS" = "not_ready" ] && \
   [ "$BACKEND_LIVENESS" = "healthy" ] && \
   [ "$BACKEND_PHASE" = "Running" ] && \
   [ "$DB_STATUS" = "Running" ]; then
    HYPOTHESIS_CONFIRMED=true
```

### Key Points

1. **Requires `connection_timeout` specifically** - connection refused and generic errors do NOT confirm
2. **All six conditions must be true** - any failure results in hypothesis NOT confirmed
3. **Conservative reasoning text** - "consistent with" not "proves"

### Confirmed Reasoning

```
All six conditions met: NetworkPolicy exists, Backend→Database connection timeout observed
(socket code 110), Backend readiness not_ready, Backend liveness healthy, Backend phase
Running, PostgreSQL phase Running. The observed behavior is consistent with NetworkPolicy
blocking required communication. This does not constitute definitive proof of causation,
but represents strong supporting evidence when all conditions align.
```

### NOT Confirmed Reasoning

```
Hypothesis NOT confirmed. Required conditions:
[1. Policy exists: true/false]
[2. Connection timeout: true (code 110) / false (connection_refused)]
[3. Backend readiness not_ready: true / false (ready)]
[4. Backend liveness healthy: true / false (unhealthy)]
[5. Backend Running: true / false (Pending)]
[6. PostgreSQL Running: true / false (CrashLoopBackOff)]
```

---

## JSON Output Structure

### Backend to Database Section

```json
"backend_to_database": {
  "socket_code": "110",
  "socket_error": "ETIMEDOUT",
  "status": "connection_timeout",
  "interpretation": "Socket result is consistent with NetworkPolicy blocking traffic when status is connection_timeout and corroborating evidence from pod state is present. Does not definitively prove causation."
}
```

### Backend Health Section

```json
"backend_health": {
  "phase": "Running",
  "readiness": "not_ready",
  "liveness": "healthy",
  "restart_count": "0"
}
```

### Hypothesis Section

```json
"hypothesis": {
  "statement": "Applying NetworkPolicy that isolates PostgreSQL will block required Backend → PostgreSQL communication, causing application failure while PostgreSQL pod remains running",
  "confirmed": true,
  "reasoning": "All six conditions met: ...",
  "conditions_checked": [
    "NetworkPolicy exists",
    "Backend→Database connection timeout (socket code 110)",
    "Backend readiness not_ready",
    "Backend liveness healthy",
    "Backend phase Running",
    "PostgreSQL phase Running"
  ]
}
```

### Verification Method Section

```json
"verification_method": {
  "network_connectivity_test": "Python socket.connect_ex() from backend pod to database-service:5432, with explicit kubectl exec status validation",
  "socket_code_interpretation": "Linux-specific error code mapping (0=connected, 110=ETIMEDOUT, 111=ECONNREFUSED, 113=EHOSTUNREACH, 101=ENETUNREACH)",
  "application_health_test": "Kubernetes readiness state (primary) and /live endpoint liveness check",
  "pod_status_test": "kubectl get pods with phase and condition inspection"
}
```

---

## Files Modified

1. `scripts/verify-network-policy.sh` - Complete Test 3, Test 4, hypothesis, and JSON sections
2. `services/backend/app/main.py` - Fixed trailing whitespace in `/live` endpoint docstring

---

## Git Status

```
 M kubernetes/backend/deployment.yaml  (liveness probe path changed in earlier iteration)
 M services/backend/app/main.py        (liveness endpoint added, whitespace fixed)
?? scripts/verify-network-policy.sh    (new file, untracked)
```

**Note:** `verify-network-policy.sh` shows as untracked because it has not been committed yet.

---

## Verification

### Git Diff Check

✅ **No whitespace errors**

```
Exit Code: 0
```

### Conservative Interpretation Confirmed

- ✅ Socket code 110 classified as `connection_timeout` (not `blocked`)
- ✅ Python exception cannot be classified as timeout
- ✅ kubectl failure cannot be classified as timeout
- ✅ Empty output cannot be classified as timeout
- ✅ Malformed output cannot be classified as timeout
- ✅ Connection refused does NOT confirm hypothesis
- ✅ Generic connection error does NOT confirm hypothesis
- ✅ Only timeout + five other conditions confirms hypothesis

---

## Next Steps

**User will:**
1. Review the updated Test 3 section (lines 95-188)
2. Review the updated hypothesis logic (lines 251-269)
3. Review the updated JSON generation (lines 287-361)
4. Review git status output
5. Authorize execution of `./scripts/verify-network-policy.sh`

**Agent will NOT:**
- Execute the verification script automatically
- Modify any other files
- Change NetworkPolicy YAML
- Change application code beyond whitespace fix
- Change Kubernetes manifests
- Change baseline tests

---

## Research Integrity Notes

This implementation reflects conservative research methodology:

1. **No automatic causation claims** - timeout is "consistent with" not "proves"
2. **Multiple evidence sources required** - six conditions must align
3. **Explicit error handling** - test failures are classified correctly
4. **Transparent interpretation** - socket codes documented as Linux-specific
5. **Verification over assertion** - hypothesis requires actual observations
6. **Accurate reporting** - JSON contains actual execution values

---

## Expected Experiment Outcome

When NetworkPolicy is active and Backend cannot reach PostgreSQL:

**Expected socket code:** 110 (ETIMEDOUT)  
**Expected Backend phase:** Running  
**Expected Backend readiness:** not_ready  
**Expected Backend liveness:** healthy  
**Expected Backend restarts:** 0  
**Expected PostgreSQL phase:** Running  
**Expected hypothesis:** CONFIRMED

**Conservative interpretation:** "The observed behavior is consistent with NetworkPolicy blocking required communication. This does not constitute definitive proof of causation, but represents strong supporting evidence when all conditions align."

