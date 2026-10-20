# Milestone 2: Script Modification Summary

## File Modified

**File:** `scripts/verify-network-policy.sh`

**Reason:** The original script did not handle HTTP 503 responses correctly. Python's `urllib.request.urlopen()` raises an `HTTPError` exception for non-2xx status codes, including HTTP 503, which is the expected application-level failure indicator when the Backend cannot connect to PostgreSQL.

---

## What Changed

### Problem

The original script caught all exceptions generically:

```python
try:
    response = urllib.request.urlopen('http://localhost:8000/health', timeout=5)
    data = json.loads(response.read().decode())
    print(json.dumps(data))
except Exception as e:
    print(json.dumps({'error': str(e)}))
```

**Result:** HTTP 503 was caught as a generic exception, preventing the script from:
1. Reading the response body (which contains `"database.connected": false`)
2. Recording the actual HTTP status code
3. Determining that the Backend health check failed as expected

### Solution

Modified the script to handle HTTP status codes explicitly:

```python
try:
    response = urllib.request.urlopen('http://localhost:8000/health', timeout=5)
    # HTTP 200 - healthy response
    data = json.loads(response.read().decode())
    print(json.dumps({
        'http_status': response.getcode(),
        'body': data
    }))
except urllib.error.HTTPError as e:
    # HTTP error (e.g., 503) - read error response if available
    try:
        error_body = json.loads(e.read().decode())
        print(json.dumps({
            'http_status': e.code,
            'body': error_body
        }))
    except:
        print(json.dumps({
            'http_status': e.code,
            'body': {'error': 'HTTP error without body'}
        }))
except urllib.error.URLError as e:
    # Connection failure
    print(json.dumps({
        'http_status': 0,
        'body': {'error': f'Connection failure: {str(e)}'}
    }))
except Exception as e:
    # Unexpected error
    print(json.dumps({
        'http_status': -1,
        'body': {'error': f'Unexpected error: {str(e)}'}
    }))
```

---

## Key Changes

### 1. Explicit HTTP Status Handling

**Added:**
- `urllib.error.HTTPError` exception handling to capture HTTP error responses (503, 404, etc.)
- `urllib.error.URLError` exception handling for connection failures
- Structured output format: `{'http_status': <code>, 'body': <response>}`

**HTTP Status Codes:**
- `200` → Backend healthy
- `503` → Backend unhealthy (expected after NetworkPolicy applied)
- `0` → Connection failure (timeout/refused)
- `-1` → Unexpected error

### 2. HTTP Status Variable

**Added:**
```bash
BACKEND_HTTP_STATUS="unknown"
```

This variable stores the actual HTTP status code observed during the health check.

### 3. State Determination Logic

**Replaced generic check with explicit status handling:**

```bash
# Determine backend health state based on HTTP status
if [ "$BACKEND_HTTP_STATUS" = "200" ]; then
    if [ "$DB_CONNECTED" = "true" ]; then
        echo "❌ Backend health: HTTP 200, database connected (unexpected after policy)"
    else
        echo "⚠️  Backend health: HTTP 200 but database shows disconnected (unusual)"
    fi
elif [ "$BACKEND_HTTP_STATUS" = "503" ]; then
    BACKEND_HEALTH_FAILED=true
    echo "✅ Backend health: HTTP 503, unhealthy (expected after policy)"
elif [ "$BACKEND_HTTP_STATUS" = "0" ]; then
    echo "⚠️  Backend health: Connection failure (timeout or refused)"
elif [ "$BACKEND_HTTP_STATUS" = "-1" ]; then
    echo "⚠️  Backend health: Unexpected error"
else
    echo "⚠️  Backend health: HTTP $BACKEND_HTTP_STATUS (unexpected status)"
fi
```

**Key behavior:**
- HTTP 503 → Sets `BACKEND_HEALTH_FAILED=true` (expected unhealthy state)
- HTTP 200 with `database.connected=true` → Unexpected (policy should have blocked this)
- HTTP 200 with `database.connected=false` → Unusual edge case
- Connection failure → Network-level issue (different from HTTP 503)

### 4. JSON Output Enhancement

**Added `backend_health_http_status` field:**

```json
"observed_behavior": {
  "frontend_accessible": true/false,
  "frontend_to_backend": "success"/"failed",
  "backend_to_database": "blocked"/"not_blocked",
  "backend_health": "unhealthy"/"healthy_or_unknown",
  "backend_health_http_status": "200"/"503"/"0"/"-1"/"unknown",
  "database_pod": "running"/"not_running",
  "end_to_end": "failed"/"unknown"
}
```

This records the actual HTTP status code observed, providing traceable experimental evidence.

---

## Verification Logic

### Hypothesis Confirmation Criteria

The script sets `hypothesis_confirmed=true` when ALL of these conditions are met:

1. ✅ `POLICY_EXISTS=true` - NetworkPolicy is active
2. ✅ `BACKEND_TO_DB_BLOCKED=true` - Network-level connectivity blocked
3. ✅ `BACKEND_HEALTH_FAILED=true` - Application-level health check failed (HTTP 503)
4. ✅ `DB_POD_RUNNING=true` - PostgreSQL pod remains Running

**Important:** `BACKEND_HEALTH_FAILED` is now set to `true` only when HTTP 503 is explicitly observed, not on generic exceptions.

---

## Expected Behavior After Fix

### With NetworkPolicy Applied

**Observation sequence:**

1. Network-level test: Backend → PostgreSQL connection blocked (socket timeout)
2. Application-level test: Backend `/health` returns HTTP 503
3. Response body contains: `{"database": {"connected": false, "error": "..."}}`
4. Script correctly records:
   - `backend_health: "unhealthy"`
   - `backend_health_http_status: "503"`
   - `backend_health_indicates_failure: true`
   - `hypothesis_confirmed: true`

### Without NetworkPolicy (Baseline)

1. Network-level test: Backend → PostgreSQL connection succeeds
2. Application-level test: Backend `/health` returns HTTP 200
3. Response body contains: `{"database": {"connected": true}}`
4. Script correctly records:
   - `backend_health: "healthy_or_unknown"`
   - `backend_health_http_status: "200"`
   - `backend_health_indicates_failure: false`

---

## What Was NOT Changed

✅ NetworkPolicy manifest (`kubernetes/policies/isolate-database.yaml`)  
✅ Backend application code (`services/backend/app/main.py`)  
✅ Kubernetes deployments  
✅ Apply script (`scripts/apply-network-policy.sh`)  
✅ Remove script (`scripts/remove-network-policy.sh`)  
✅ Any other project files  

**Only** `scripts/verify-network-policy.sh` was modified.

---

## Research Integrity Notes

### Why This Modification Is Valid

1. **Does not fabricate results** - Still records actual observed behavior
2. **Does not change the experiment** - Only fixes observation method
3. **Improves accuracy** - Correctly distinguishes HTTP status codes
4. **Preserves reproducibility** - Same experiment, better measurement
5. **Does not alter the system under test** - Backend, NetworkPolicy unchanged

### What This Demonstrates

The modification demonstrates an important research principle:

> **Measurement instrumentation must be accurate enough to capture the phenomenon under study.**

The original script's generic exception handling was insufficient instrumentation. The Backend application was correctly returning HTTP 503 (as verified by independent log inspection), but the verification script was not capturing that signal correctly.

This is analogous to using a properly calibrated measurement instrument in physical experiments.

---

## Validation

To validate the fix works correctly, the experiment should be re-run:

```bash
# Re-apply policy (if removed)
./scripts/apply-network-policy.sh

# Run modified verification script
./scripts/verify-network-policy.sh

# Check results
cat network-policy-verification.json
```

**Expected result:**
- `backend_health_http_status: "503"`
- `backend_health_indicates_failure: true`
- `hypothesis_confirmed: true`

---

## End of Modification Summary

**Date:** 2026-10-07  
**Modified by:** Kiro (automated agent)  
**Approved by:** User (pending re-execution validation)  
**Purpose:** Fix HTTP 503 handling to correctly record application-level failure state

---
