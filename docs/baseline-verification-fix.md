# Baseline Verification Script Fix

## Issue Encountered

During deployment testing, the baseline verification script (`scripts/verify-baseline.sh`) failed at **Step 5: Testing Backend → Database communication** with the error:

```
error: exec: "wget": executable file not found in $PATH
```

## Root Cause

The original script used `kubectl exec` to run `wget` inside the backend container to call the `/health` endpoint:

```bash
kubectl exec -n ${NAMESPACE} ${BACKEND_POD} -- wget -q -O- http://localhost:8000/health
```

However, the backend Docker image (`python:3.11-slim`) does not include `wget` or `curl` utilities.

## Why NOT Install wget in Backend Image

**Rejected approach:** Adding `wget` or `curl` to the backend Dockerfile

**Rationale:**
1. **Production image principle:** Don't add debugging tools to production images just for testing
2. **Minimal dependencies:** Keep Docker images lean
3. **Security:** Fewer utilities = smaller attack surface
4. **Research integrity:** Use application's existing mechanisms, not workarounds

## Solution Implemented

### Changed Approach

Use **Python's built-in `urllib.request`** module (already available in the backend container) to call the health endpoint internally.

### Key Changes

**Before (Step 5):**
```bash
HEALTH_RESPONSE=$(kubectl exec -n ${NAMESPACE} ${BACKEND_POD} -- \
    wget -q -O- http://localhost:8000/health)
```

**After (Step 5):**
```bash
HEALTH_RESPONSE=$(kubectl exec -n ${NAMESPACE} ${BACKEND_POD} -- python3 -c "
import urllib.request
import json
try:
    with urllib.request.urlopen('http://localhost:8000/health', timeout=5) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(json.dumps({'error': str(e), 'database': {'connected': False}}))
" 2>/dev/null)
```

### What This Does

1. **Executes Python code** inside the backend container (Python is already there)
2. **Calls localhost:8000/health** using Python's standard library
3. **The /health endpoint itself** performs the actual database connectivity check:
   - Connects to PostgreSQL
   - Executes `SELECT 1 AS result`
   - Returns JSON with database status
4. **Returns the JSON response** to the bash script for verification
5. **Handles errors gracefully** if the health endpoint fails

### Why This Approach is Correct

✅ **No new dependencies:** Uses Python already in the image  
✅ **Tests actual functionality:** The `/health` endpoint verifies real database connectivity  
✅ **Genuine verification:** Not just checking if pods are running  
✅ **Research integrity:** Tests the application's actual health check mechanism  
✅ **Production-appropriate:** No debugging utilities added  

## Other Checks Unchanged

### Step 4: Frontend → Backend

**Unchanged** - Frontend container (Nginx Alpine) has `wget` built-in:
```bash
kubectl exec -n ${NAMESPACE} ${FRONTEND_POD} -- \
    wget -q -O- http://backend-service:8000/health
```

This correctly tests that Frontend can reach Backend service through Kubernetes DNS.

### Step 6: Database Query Execution

**Unchanged** - Uses the same `HEALTH_RESPONSE` from Step 5:
```bash
if echo "${HEALTH_RESPONSE}" | grep -q '"query_result": 1'; then
    DATABASE_QUERY="success"
fi
```

This verifies that the backend actually executed `SELECT 1 AS result` against PostgreSQL.

## What This Verifies

The modified Step 5 genuinely verifies:

1. ✅ **Backend application is running** (FastAPI/Uvicorn process alive)
2. ✅ **Backend can reach database service** (DNS resolution works)
3. ✅ **Backend can connect to PostgreSQL** (TCP connection succeeds)
4. ✅ **Backend can authenticate** (PostgreSQL accepts credentials)
5. ✅ **Backend can execute queries** (SELECT 1 returns result)
6. ✅ **Response time measured** (included in JSON response)

This is **more comprehensive** than just checking if the database pod is Running.

## Verification Flow

```
┌─────────────────────────────────────────────────┐
│  Host Machine (bash script)                     │
│  ┌─────────────────────────────────────────┐   │
│  │ kubectl exec backend-pod -- python3     │   │
│  │   ↓                                      │   │
│  │ urllib.request.urlopen(localhost:8000)  │   │
│  │   ↓                                      │   │
│  │ Backend /health endpoint                │   │
│  │   ↓                                      │   │
│  │ psycopg2.connect(database-service:5432) │   │
│  │   ↓                                      │   │
│  │ cursor.execute("SELECT 1 AS result")    │   │
│  │   ↓                                      │   │
│  │ Return JSON response                    │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## JSON Output Structure

**Preserved** - The `baseline-verification.json` structure remains the same:

```json
{
  "timestamp": "2026-10-06T...",
  "milestone": "1",
  "cluster": "poc-cluster",
  "namespace": "poc-app",
  "verification": {
    "frontend_accessible": true,
    "frontend_to_backend": "success",
    "backend_to_database": "success",
    "database_query": "success",
    "end_to_end": "success"
  },
  "services": {
    "backend": {
      "status": "healthy",
      "database_connected": true,
      "query_response_time_ms": 12.34
    },
    "database": {
      "status": "ready",
      "version": "PostgreSQL 15.x"
    }
  },
  "communication_paths": {
    "user_to_frontend": "✅ working",
    "frontend_to_backend": "✅ working",
    "backend_to_database": "✅ working"
  }
}
```

## Error Handling

If the health endpoint fails, the Python code returns:
```json
{"error": "connection refused", "database": {"connected": false}}
```

The bash script will then:
1. Mark `BACKEND_TO_DATABASE="failed"`
2. Print `❌ Backend cannot reach Database`
3. Show the error response for debugging

## Testing the Fix

Run the corrected verification:

```bash
cd /mnt/c/Users/sai/Desktop/Final-Year-Project
./scripts/verify-baseline.sh
```

**Expected output:**
```
5. Testing Backend → Database communication...
   (Using Backend's /health endpoint which verifies actual database connectivity)
   ✅ Backend can reach Database

6. Testing database query execution...
   ✅ Database query executed successfully
```

## Files Modified

- ✅ `scripts/verify-baseline.sh` - Steps 5 and 6 updated
- ❌ No Docker images modified
- ❌ No application code modified
- ❌ No Kubernetes manifests modified

## Alignment with Research Principles

This fix aligns with the project's research integrity principles:

1. **Actual execution required:** Uses real application health check, not simulated
2. **Evidence-based:** Tests actual database connectivity, not assumptions
3. **Reproducible:** Works on any machine with kubectl access
4. **Educational:** Demonstrates proper testing methodology for viva
5. **Production-appropriate:** No debugging utilities in production images

## Summary

**Problem:** `wget` not available in backend container  
**Solution:** Use Python's `urllib.request` (already in container)  
**Verification:** Backend's `/health` endpoint performs actual database query  
**Result:** Genuine Backend → Database connectivity verification  
**Impact:** No changes to application code or Docker images  
**Status:** Ready for re-testing  
