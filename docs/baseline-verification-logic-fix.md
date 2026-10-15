# Baseline Verification Logic Fix

## Problem Identified

The baseline verification script had **contradictory outputs**:

**Terminal Output:**
```
Backend → Database: failed
Database query: failed
```

**JSON Output:**
```json
{
  "verification": {
    "backend_to_database": "failed",
    "database_query": "failed"
  },
  "communication_paths": {
    "backend_to_database": "✅ working"
  },
  "notes": "Baseline established. All communication paths verified working."
}
```

The terminal correctly reported failures, but the JSON hardcoded success regardless of test results.

---

## Root Cause Analysis

### Issue 1: Unreliable grep-based JSON Parsing

**Previous Logic (Lines 78-79):**
```bash
if echo "${HEALTH_RESPONSE}" | grep -q '"connected": true'; then
    BACKEND_TO_DATABASE="success"
```

**Problem:**
- `grep -q '"connected": true'` is unreliable for JSON
- Whitespace, newlines, and formatting variations break pattern matching
- Doesn't verify `status == "healthy"` requirement
- Doesn't properly parse nested JSON structure

**Actual /health Response:**
```json
{
  "status": "healthy",
  "application": {...},
  "database": {
    "connected": true,
    "version": "PostgreSQL 15.19 on x86_64-pc-linux-musl...",
    "test_query": "SELECT 1 AS result",
    "query_result": 1,
    "response_time_ms": 9.63
  }
}
```

The grep failed because of JSON formatting.

---

### Issue 2: Hardcoded Success in JSON Output

**Previous Logic (Lines 122-126):**
```bash
"backend": {
  "status": "healthy",
  "database_connected": true,
  "query_response_time_ms": ${DB_RESPONSE_TIME:-0}
},
...
"communication_paths": {
  "user_to_frontend": "✅ working",
  "frontend_to_backend": "✅ working",
  "backend_to_database": "✅ working"
},
"notes": "Baseline established. All communication paths verified working."
```

**Problem:**
- `"status": "healthy"` was hardcoded
- `"database_connected": true` was hardcoded
- Communication paths were hardcoded as `"✅ working"`
- Notes always said "All communication paths verified working"
- **None of these reflected actual test results**

This created the contradiction: terminal showed failures, JSON showed success.

---

### Issue 3: Incorrect response_time_ms Extraction

**Previous Logic:**
```bash
DB_RESPONSE_TIME=$(echo "${HEALTH_RESPONSE}" | grep -o '"response_time_ms": [0-9.]*' | cut -d':' -f2 | tr -d ' ')
```

**Problem:**
- Failed for decimal values like `9.63`
- Defaulted to `0` when extraction failed: `${DB_RESPONSE_TIME:-0}`

---

## Solution Implemented

### Fix 1: Proper JSON Parsing with Python

**Step 5 - Backend → Database Check:**

**New Logic:**
```bash
# Parse JSON response properly using Python
# Check: status == "healthy" AND database.connected == true
HEALTH_STATUS=$(echo "${HEALTH_RESPONSE}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('status') == 'healthy' and data.get('database', {}).get('connected') == True:
        print('healthy')
    else:
        print('unhealthy')
except:
    print('parse_error')
" 2>/dev/null)

if [ "${HEALTH_STATUS}" = "healthy" ]; then
    BACKEND_TO_DATABASE="success"
    echo "   ✅ Backend can reach Database"
else
    BACKEND_TO_DATABASE="failed"
    echo "   ❌ Backend cannot reach Database (status: ${HEALTH_STATUS})"
fi
```

**Requirements Met:**
✅ Parses actual JSON structure  
✅ Verifies `status == "healthy"`  
✅ Verifies `database.connected == true`  
✅ Handles parse errors gracefully  
✅ Reports actual status to terminal  

---

**Step 6 - Database Query Check:**

**New Logic:**
```bash
# Parse JSON to verify: test_query == "SELECT 1 AS result" AND query_result == 1
QUERY_VERIFICATION=$(echo "${HEALTH_RESPONSE}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    db = data.get('database', {})
    test_query = db.get('test_query', '')
    query_result = db.get('query_result', None)
    
    if test_query == 'SELECT 1 AS result' and query_result == 1:
        print('success')
    else:
        print('failed')
except:
    print('parse_error')
" 2>/dev/null)

if [ "${QUERY_VERIFICATION}" = "success" ]; then
    DATABASE_QUERY="success"
    echo "   ✅ Database query executed successfully"
else
    DATABASE_QUERY="failed"
    echo "   ❌ Database query failed (verification: ${QUERY_VERIFICATION})"
fi
```

**Requirements Met:**
✅ Verifies `test_query == "SELECT 1 AS result"`  
✅ Verifies `query_result == 1`  
✅ Handles missing fields  
✅ Reports actual result  

---

### Fix 2: Extract Database Info from JSON

**New Logic:**
```bash
DB_INFO=$(echo "${HEALTH_RESPONSE}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    db = data.get('database', {})
    version = db.get('version', 'unknown')
    response_time = db.get('response_time_ms', 0)
    connected = db.get('connected', False)
    # Extract short version (first 2 words)
    version_short = ' '.join(version.split()[:2]) if version != 'unknown' else 'unknown'
    print(f'{version_short}|{response_time}|{connected}')
except:
    print('unknown|0|false')
" 2>/dev/null)

DB_VERSION=$(echo "${DB_INFO}" | cut -d'|' -f1)
DB_RESPONSE_TIME=$(echo "${DB_INFO}" | cut -d'|' -f2)
DB_CONNECTED=$(echo "${DB_INFO}" | cut -d'|' -f3)
```

**Improvements:**
✅ Extracts actual `response_time_ms` value (e.g., `9.63`)  
✅ Extracts `connected` boolean as string (`true`/`false`)  
✅ Extracts version properly from nested JSON  
✅ Handles parse errors with defaults  

---

### Fix 3: Derive JSON Output from Test Results

**New Logic:**
```bash
# Determine communication path statuses based on actual test results
USER_TO_FRONTEND_STATUS="❌ failed"
if [ "${FRONTEND_ACCESSIBLE}" = "true" ]; then
    USER_TO_FRONTEND_STATUS="✅ working"
fi

FRONTEND_TO_BACKEND_STATUS="❌ failed"
if [ "${FRONTEND_TO_BACKEND}" = "success" ]; then
    FRONTEND_TO_BACKEND_STATUS="✅ working"
fi

BACKEND_TO_DATABASE_STATUS="❌ failed"
if [ "${BACKEND_TO_DATABASE}" = "success" ]; then
    BACKEND_TO_DATABASE_STATUS="✅ working"
fi

# Determine backend status based on health check
BACKEND_STATUS="unhealthy"
if [ "${HEALTH_STATUS}" = "healthy" ]; then
    BACKEND_STATUS="healthy"
fi

# Determine overall baseline status
ALL_PASSED="true"
if [ "${FRONTEND_ACCESSIBLE}" != "true" ] || \
   [ "${FRONTEND_TO_BACKEND}" != "success" ] || \
   [ "${BACKEND_TO_DATABASE}" != "success" ] || \
   [ "${DATABASE_QUERY}" != "success" ] || \
   [ "${END_TO_END}" != "success" ]; then
    ALL_PASSED="false"
fi

# Set notes based on actual results
if [ "${ALL_PASSED}" = "true" ]; then
    BASELINE_NOTES="Baseline established. All communication paths verified working. Ready for Milestone 2 (NetworkPolicy introduction)."
else
    BASELINE_NOTES="Baseline verification incomplete. Some checks failed. Review verification results before proceeding to Milestone 2."
fi
```

**JSON Output Now Uses Variables:**
```bash
{
  "services": {
    "backend": {
      "status": "${BACKEND_STATUS}",
      "database_connected": ${DB_CONNECTED},
      "query_response_time_ms": ${DB_RESPONSE_TIME}
    }
  },
  "communication_paths": {
    "user_to_frontend": "${USER_TO_FRONTEND_STATUS}",
    "frontend_to_backend": "${FRONTEND_TO_BACKEND_STATUS}",
    "backend_to_database": "${BACKEND_TO_DATABASE_STATUS}"
  },
  "notes": "${BASELINE_NOTES}"
}
```

**Result:**
✅ JSON output matches terminal output  
✅ No hardcoded success values  
✅ Notes reflect actual test status  
✅ Communication paths derived from test results  

---

## Comparison: Before vs After

### Before (Incorrect)

**Terminal:**
```
5. Testing Backend → Database communication...
   ❌ Backend cannot reach Database

6. Testing database query execution...
   ❌ Database query failed
```

**JSON:**
```json
{
  "verification": {
    "backend_to_database": "failed",
    "database_query": "failed"
  },
  "backend": {
    "status": "healthy",
    "database_connected": true
  },
  "communication_paths": {
    "backend_to_database": "✅ working"
  },
  "notes": "Baseline established. All communication paths verified working."
}
```

**Contradiction:** Terminal says failed, JSON says working.

---

### After (Correct)

**Terminal (when actually healthy):**
```
5. Testing Backend → Database communication...
   (Using Backend's /health endpoint which verifies actual database connectivity)
   ✅ Backend can reach Database

6. Testing database query execution...
   ✅ Database query executed successfully
```

**JSON:**
```json
{
  "verification": {
    "backend_to_database": "success",
    "database_query": "success"
  },
  "backend": {
    "status": "healthy",
    "database_connected": true,
    "query_response_time_ms": 9.63
  },
  "communication_paths": {
    "backend_to_database": "✅ working"
  },
  "notes": "Baseline established. All communication paths verified working. Ready for Milestone 2."
}
```

**Consistency:** Terminal and JSON agree.

---

**Terminal (if database fails):**
```
5. Testing Backend → Database communication...
   ❌ Backend cannot reach Database (status: unhealthy)

6. Testing database query execution...
   ❌ Database query failed (verification: failed)
```

**JSON:**
```json
{
  "verification": {
    "backend_to_database": "failed",
    "database_query": "failed"
  },
  "backend": {
    "status": "unhealthy",
    "database_connected": false,
    "query_response_time_ms": 0
  },
  "communication_paths": {
    "backend_to_database": "❌ failed"
  },
  "notes": "Baseline verification incomplete. Some checks failed. Review verification results before proceeding to Milestone 2."
}
```

**Consistency:** Terminal and JSON agree on failure.

---

## Key Requirements Met

✅ **Parse actual JSON schema** - Uses Python JSON parser, not grep  
✅ **Backend → Database success only when:**
   - HTTP request succeeds
   - `status == "healthy"`
   - `database.connected == true`

✅ **Database query success only when:**
   - `test_query == "SELECT 1 AS result"`
   - `query_result == 1`

✅ **Extract actual response_time_ms** - Correctly extracts `9.63`  
✅ **Terminal and JSON agree** - No contradictions  
✅ **Failure handling** - Reports parse errors instead of assuming success  
✅ **Notes conditional** - Only says "baseline established" when ALL checks pass  
✅ **No image modifications** - Uses Python already in container  
✅ **JSON structure preserved** - Same format, actual values  

---

## Testing the Fix

Run the corrected script:

```bash
cd /mnt/c/Users/sai/Desktop/Final-Year-Project
./scripts/verify-baseline.sh
```

**Expected output (when healthy):**

```
========================================
Baseline Verification
========================================

1. Verifying cluster health...
   ✅ Cluster is running

2. Verifying pod status...
   ✅ All pods are running

3. Testing Frontend accessibility...
   ✅ Frontend accessible at http://localhost:30080

4. Testing Frontend → Backend communication...
   ✅ Frontend can reach Backend

5. Testing Backend → Database communication...
   (Using Backend's /health endpoint which verifies actual database connectivity)
   ✅ Backend can reach Database

6. Testing database query execution...
   ✅ Database query executed successfully

7. Testing end-to-end request...
   ✅ End-to-end request successful

=========================================
Recording Baseline State
=========================================

Baseline verification saved to: baseline-verification.json

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
    "frontend": {
      "status": "running",
      "endpoint": "http://localhost:30080"
    },
    "backend": {
      "status": "healthy",
      "database_connected": true,
      "query_response_time_ms": 9.63
    },
    "database": {
      "status": "ready",
      "version": "PostgreSQL 15.19"
    }
  },
  "communication_paths": {
    "user_to_frontend": "✅ working",
    "frontend_to_backend": "✅ working",
    "backend_to_database": "✅ working"
  },
  "notes": "Baseline established. All communication paths verified working. Ready for Milestone 2 (NetworkPolicy introduction)."
}

=========================================
Baseline Verification Complete!
=========================================

Summary:
  Frontend accessible: true
  Frontend → Backend: success
  Backend → Database: success
  Database query: success
  End-to-end: success

Open http://localhost:30080 in your browser to see the application
```

---

## Files Modified

- ✅ `scripts/verify-baseline.sh` - Steps 5, 6, database extraction, JSON output logic

**No changes to:**
- ❌ Docker images
- ❌ Application code
- ❌ Kubernetes manifests

---

## Research Integrity Maintained

✅ **Results from actual execution** - Parses real health endpoint response  
✅ **No false positives** - Doesn't assume success  
✅ **Genuine verification** - Tests actual database connectivity  
✅ **Transparent reporting** - Terminal and JSON consistent  
✅ **Failure detection** - Reports issues clearly  

---

## Summary

**Problem:** Contradictory outputs - terminal showed failure, JSON showed success  
**Root Cause:** Hardcoded success values in JSON, unreliable grep parsing  
**Solution:** Proper JSON parsing with Python, derive JSON from test results  
**Result:** Terminal and JSON outputs now agree exactly  
**Status:** Ready for re-testing  
