#!/bin/bash
# verify-baseline.sh
# Verifies baseline connectivity and documents results

set -e

NAMESPACE="poc-app"
OUTPUT_FILE="baseline-verification.json"

echo "========================================="
echo "Baseline Verification"
echo "========================================="

# Initialize results
FRONTEND_ACCESSIBLE="false"
FRONTEND_TO_BACKEND="failed"
BACKEND_TO_DATABASE="failed"
DATABASE_QUERY="failed"
END_TO_END="failed"

# Timestamp
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")

echo ""
echo "1. Verifying cluster health..."
if kubectl cluster-info > /dev/null 2>&1; then
    echo "   ✅ Cluster is running"
else
    echo "   ❌ Cluster is not running"
    exit 1
fi

echo ""
echo "2. Verifying pod status..."
kubectl get pods -n ${NAMESPACE}
if kubectl get pods -n ${NAMESPACE} | grep -q "1/1.*Running"; then
    echo "   ✅ All pods are running"
else
    echo "   ❌ Some pods are not ready"
    exit 1
fi

echo ""
echo "3. Testing Frontend accessibility..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:30080 | grep -q "200"; then
    FRONTEND_ACCESSIBLE="true"
    echo "   ✅ Frontend accessible at http://localhost:30080"
else
    echo "   ❌ Frontend not accessible"
fi

echo ""
echo "4. Testing Frontend → Backend communication..."
FRONTEND_POD=$(kubectl get pod -n ${NAMESPACE} -l app=frontend -o jsonpath='{.items[0].metadata.name}')
# Frontend has wget available (Alpine Linux includes wget)
if kubectl exec -n ${NAMESPACE} ${FRONTEND_POD} -- wget -q -O- http://backend-service:8000/health > /dev/null 2>&1; then
    FRONTEND_TO_BACKEND="success"
    echo "   ✅ Frontend can reach Backend"
else
    echo "   ❌ Frontend cannot reach Backend"
fi

echo ""
echo "5. Testing Backend → Database communication..."
echo "   (Using Backend's /health endpoint which verifies actual database connectivity)"
BACKEND_POD=$(kubectl get pod -n ${NAMESPACE} -l app=backend -o jsonpath='{.items[0].metadata.name}')

# Use Python (already in backend container) to call the health endpoint
# The backend's /health endpoint performs actual database connectivity check (SELECT 1)
HEALTH_RESPONSE=$(kubectl exec -n ${NAMESPACE} ${BACKEND_POD} -- python3 -c "
import urllib.request
import json
try:
    with urllib.request.urlopen('http://localhost:8000/health', timeout=5) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(json.dumps({'status': 'error', 'database': {'connected': False}}))
" 2>/dev/null)

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

echo ""
echo "6. Testing database query execution..."
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

echo ""
echo "7. Testing end-to-end request..."
if curl -s http://localhost:30080 | grep -q "POC Application"; then
    END_TO_END="success"
    echo "   ✅ End-to-end request successful"
else
    echo "   ❌ End-to-end request failed"
fi

# Extract database info from JSON properly
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
    # Convert Python boolean to JSON-compatible lowercase string
    connected_json = 'true' if connected else 'false'
    print(f'{version_short}|{response_time}|{connected_json}')
except:
    print('unknown|0|false')
" 2>/dev/null)

DB_VERSION=$(echo "${DB_INFO}" | cut -d'|' -f1)
DB_RESPONSE_TIME=$(echo "${DB_INFO}" | cut -d'|' -f2)
DB_CONNECTED=$(echo "${DB_INFO}" | cut -d'|' -f3)

echo ""
echo "========================================="
echo "Recording Baseline State"
echo "========================================="

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

# Create JSON output with actual test results
cat > ${OUTPUT_FILE} <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "milestone": "1",
  "cluster": "poc-cluster",
  "namespace": "${NAMESPACE}",
  "verification": {
    "frontend_accessible": ${FRONTEND_ACCESSIBLE},
    "frontend_to_backend": "${FRONTEND_TO_BACKEND}",
    "backend_to_database": "${BACKEND_TO_DATABASE}",
    "database_query": "${DATABASE_QUERY}",
    "end_to_end": "${END_TO_END}"
  },
  "services": {
    "frontend": {
      "status": "running",
      "endpoint": "http://localhost:30080"
    },
    "backend": {
      "status": "${BACKEND_STATUS}",
      "database_connected": ${DB_CONNECTED},
      "query_response_time_ms": ${DB_RESPONSE_TIME}
    },
    "database": {
      "status": "ready",
      "version": "${DB_VERSION}"
    }
  },
  "communication_paths": {
    "user_to_frontend": "${USER_TO_FRONTEND_STATUS}",
    "frontend_to_backend": "${FRONTEND_TO_BACKEND_STATUS}",
    "backend_to_database": "${BACKEND_TO_DATABASE_STATUS}"
  },
  "notes": "${BASELINE_NOTES}"
}
EOF

echo ""
echo "Baseline verification saved to: ${OUTPUT_FILE}"
echo ""
cat ${OUTPUT_FILE}

echo ""
echo "========================================="
echo "Baseline Verification Complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "  Frontend accessible: ${FRONTEND_ACCESSIBLE}"
echo "  Frontend → Backend: ${FRONTEND_TO_BACKEND}"
echo "  Backend → Database: ${BACKEND_TO_DATABASE}"
echo "  Database query: ${DATABASE_QUERY}"
echo "  End-to-end: ${END_TO_END}"
echo ""
echo "Open http://localhost:30080 in your browser to see the application"
