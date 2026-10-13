# Milestone 2: Verification Script Fix #3 - Exact Diff

## Summary of Change

**File:** `scripts/verify-network-policy.sh`  
**Section:** Test 4 only  
**Lines:** ~60 lines replaced  

**Old approach:** Python urllib inside container with complex exception handling  
**New approach:** Kubernetes readiness state + simple curl for HTTP status

---

## Complete Diff

### BEFORE (Old Test 4)

```bash
# Test 4: Backend health endpoint
echo "Test 4: Backend /health endpoint (application-level)"
BACKEND_HTTP_STATUS="unknown"
if [ -n "$BACKEND_POD" ]; then
    # Get HTTP status and response body, handling 503 explicitly
    HEALTH_RESULT=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 << 'PYTHON_EOF'
import urllib.request
import json
import sys

try:
    response = urllib.request.urlopen("http://localhost:8000/health", timeout=5)
    data = json.loads(response.read().decode())
    print(json.dumps({"http_status": response.getcode(), "body": data}))
except urllib.error.HTTPError as e:
    try:
        error_body = json.loads(e.read().decode())
        print(json.dumps({"http_status": e.code, "body": error_body}))
    except:
        print(json.dumps({"http_status": e.code, "body": {"error": "HTTP error without body"}}))
except urllib.error.URLError as e:
    print(json.dumps({"http_status": 0, "body": {"error": "Connection failure"}}))
except Exception as e:
    print(json.dumps({"http_status": -1, "body": {"error": "Unexpected error"}}))
PYTHON_EOF
)

    # Parse HTTP status and determine health state
    BACKEND_HTTP_STATUS=$(echo "$HEALTH_RESULT" | python3 -c "
import sys
import json
try:
    data = json.load(sys.stdin)
    print(data.get('http_status', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)

    DB_CONNECTED=$(echo "$HEALTH_RESULT" | python3 -c "
import sys
import json
try:
    data = json.load(sys.stdin)
    body = data.get('body', {})
    if 'database' in body and 'connected' in body['database']:
        print('true' if body['database']['connected'] else 'false')
    else:
        print('unknown')
except:
    print('unknown')
" 2>/dev/null)

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
else
    echo "⚠️  Backend pod not found, skipping health test"
fi
echo ""
```

---

### AFTER (New Test 4)

```bash
# Test 4: Backend health and readiness (application-level)
echo "Test 4: Backend health and readiness (application-level)"
BACKEND_HTTP_STATUS="unknown"
BACKEND_READINESS="unknown"
BACKEND_LIVENESS="unknown"

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
    
    # Check liveness by verifying /live endpoint
    LIVE_STATUS=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/live 2>/dev/null || echo "error")
    
    if [ "$LIVE_STATUS" = "200" ]; then
        BACKEND_LIVENESS="healthy"
        echo "   Backend liveness: Healthy (/live returns 200)"
    else
        BACKEND_LIVENESS="unhealthy_or_unknown"
        echo "   Backend liveness: $LIVE_STATUS"
    fi
    
    # Attempt to get /health status (may fail, which is expected)
    HEALTH_STATUS=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "error")
    
    if [ "$HEALTH_STATUS" = "200" ]; then
        BACKEND_HTTP_STATUS="200"
        echo "   Backend /health: HTTP 200"
    elif [ "$HEALTH_STATUS" = "503" ]; then
        BACKEND_HTTP_STATUS="503"
        echo "   Backend /health: HTTP 503"
    else
        BACKEND_HTTP_STATUS="$HEALTH_STATUS"
        echo "   Backend /health: $HEALTH_STATUS"
    fi
    
    # Determine backend health failure based on Kubernetes readiness state
    if [ "$BACKEND_READINESS" = "not_ready" ] && [ "$BACKEND_LIVENESS" = "healthy" ]; then
        BACKEND_HEALTH_FAILED=true
        echo "✅ Backend health indicates failure: NotReady while liveness healthy (expected after policy)"
    elif [ "$BACKEND_HTTP_STATUS" = "503" ]; then
        BACKEND_HEALTH_FAILED=true
        echo "✅ Backend health indicates failure: HTTP 503 (expected after policy)"
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

## Key Differences

### 1. Primary Failure Indicator

**Before:**
```bash
elif [ "$BACKEND_HTTP_STATUS" = "503" ]; then
    BACKEND_HEALTH_FAILED=true
```

**After:**
```bash
if [ "$BACKEND_READINESS" = "not_ready" ] && [ "$BACKEND_LIVENESS" = "healthy" ]; then
    BACKEND_HEALTH_FAILED=true  # Primary
elif [ "$BACKEND_HTTP_STATUS" = "503" ]; then
    BACKEND_HEALTH_FAILED=true  # Secondary
```

### 2. Data Collection Method

**Before:**
- Python urllib with complex exception handling
- JSON parsing of response body
- Heredoc with multi-line Python script

**After:**
- `kubectl get pod` for readiness status (Kubernetes-native)
- Simple `curl -w "%{http_code}"` for HTTP status
- No JSON parsing required

### 3. New Variables

**Added:**
- `BACKEND_READINESS` - "ready" | "not_ready" | "unknown"
- `BACKEND_LIVENESS` - "healthy" | "unhealthy_or_unknown"

**Existing:**
- `BACKEND_HTTP_STATUS` - now set via curl instead of urllib

### 4. JSON Output Change

**Before:**
```json
"observed_behavior": {
  "backend_health_http_status": "$BACKEND_HTTP_STATUS"
}
```

**After:**
```json
"observed_behavior": {
  "backend_readiness": "$BACKEND_READINESS",
  "backend_liveness": "$BACKEND_LIVENESS",
  "backend_health_http_status": "$BACKEND_HTTP_STATUS"
}
```

---

## Why This Is Better

| Aspect | Before | After |
|--------|--------|-------|
| **Primary indicator** | HTTP response parsing | Kubernetes readiness state |
| **Execution method** | Python urllib in heredoc | kubectl + curl |
| **Complexity** | High (exception handling, JSON) | Low (status checks) |
| **Reliability** | Fragile (exec environment) | Robust (Kubernetes API) |
| **Error handling** | Complex try/except | Simple status codes |
| **Alignment** | Indirect (HTTP → health) | Direct (readiness IS health) |

---

## Testing the Change

### With NetworkPolicy Active

**Expected console output:**
```
Test 4: Backend health and readiness (application-level)
   Backend readiness: NotReady
   Backend liveness: Healthy (/live returns 200)
   Backend /health: HTTP 503
✅ Backend health indicates failure: NotReady while liveness healthy (expected after policy)
```

**Expected JSON:**
```json
{
  "observed_behavior": {
    "backend_readiness": "not_ready",
    "backend_liveness": "healthy",
    "backend_health_http_status": "503",
    "backend_health": "unhealthy"
  },
  "verification_results": {
    "backend_health_indicates_failure": true
  },
  "hypothesis_confirmed": true
}
```

### Without NetworkPolicy (Baseline)

**Expected console output:**
```
Test 4: Backend health and readiness (application-level)
   Backend readiness: Ready
   Backend liveness: Healthy (/live returns 200)
   Backend /health: HTTP 200
❌ Backend health appears healthy: Ready (unexpected after policy)
```

**Expected JSON:**
```json
{
  "observed_behavior": {
    "backend_readiness": "ready",
    "backend_liveness": "healthy",
    "backend_health_http_status": "200",
    "backend_health": "healthy_or_unknown"
  },
  "verification_results": {
    "backend_health_indicates_failure": false
  }
}
```

---

## End of Diff Document

**Modified:** Test 4 only (lines ~124-180)  
**Impact:** Robust Kubernetes-native health detection  
**Complexity:** Reduced (simpler = more reliable)  

---
