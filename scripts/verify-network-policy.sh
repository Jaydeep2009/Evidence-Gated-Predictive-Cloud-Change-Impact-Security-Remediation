#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
OUTPUT_FILE="$PROJECT_ROOT/network-policy-verification-${OUTPUT_TIMESTAMP}.json"
NAMESPACE="poc-app"
POLICY_NAME="isolate-database"

echo "=================================================="
echo "Milestone 2: Verify NetworkPolicy Impact"
echo "=================================================="
echo ""

# Initialize test results
CLUSTER_OK=false
POLICY_EXISTS=false
PODS_RUNNING=false
FRONTEND_OK=false
FRONTEND_TO_BACKEND_OK=false
BACKEND_TO_DB_BLOCKED=false
BACKEND_HEALTH_FAILED=false
DB_POD_RUNNING=false
HYPOTHESIS_CONFIRMED=false

# Get timestamp
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")

echo "Checking cluster..."
if kubectl cluster-info --context kind-poc-cluster &>/dev/null; then
    CLUSTER_OK=true
    echo "✅ Cluster running"
else
    echo "❌ Cluster not running"
fi
echo ""

# Check NetworkPolicy exists
echo "Checking NetworkPolicy..."
if kubectl get networkpolicy "$POLICY_NAME" -n "$NAMESPACE" &>/dev/null; then
    POLICY_EXISTS=true
    echo "✅ NetworkPolicy exists: $POLICY_NAME"
else
    echo "❌ NetworkPolicy not found: $POLICY_NAME"
fi
echo ""

# Check pods
echo "Checking pod status..."
BACKEND_POD=$(kubectl get pod -n "$NAMESPACE" -l app=backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
DB_POD=$(kubectl get pod -n "$NAMESPACE" -l app=database -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
FRONTEND_POD=$(kubectl get pod -n "$NAMESPACE" -l app=frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$BACKEND_POD" ] && [ -n "$DB_POD" ] && [ -n "$FRONTEND_POD" ]; then
    BACKEND_STATUS=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
    DB_STATUS=$(kubectl get pod "$DB_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
    FRONTEND_STATUS=$(kubectl get pod "$FRONTEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
    
    if [ "$BACKEND_STATUS" = "Running" ] && [ "$DB_STATUS" = "Running" ] && [ "$FRONTEND_STATUS" = "Running" ]; then
        PODS_RUNNING=true
        echo "✅ All pods Running"
    else
        echo "❌ Not all pods Running"
        echo "   Backend: $BACKEND_STATUS"
        echo "   Database: $DB_STATUS"
        echo "   Frontend: $FRONTEND_STATUS"
    fi
    
    # Check DB pod specifically
    if [ "$DB_STATUS" = "Running" ]; then
        DB_POD_RUNNING=true
    fi
else
    echo "❌ Could not find all pods"
fi
echo ""

# Test 1: Frontend accessible
echo "Test 1: Frontend accessible from localhost:30080"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:30080 | grep -q "200"; then
    FRONTEND_OK=true
    echo "✅ Frontend accessible"
else
    echo "❌ Frontend not accessible"
fi
echo ""

# Test 2: Frontend → Backend
echo "Test 2: Frontend → Backend connectivity"
if curl -s http://localhost:30080/api/health &>/dev/null; then
    FRONTEND_TO_BACKEND_OK=true
    echo "✅ Frontend → Backend working"
else
    echo "❌ Frontend → Backend failed"
fi
echo ""

# Test 3: Backend → Database (network-level connectivity test using Python socket)
echo ""
echo "=== Test 3: Backend to Database Socket Connection ==="

BACKEND_TO_DB_SOCKET_CODE="unknown"
BACKEND_TO_DB_STATUS="test_error"
BACKEND_TO_DB_SOCKET_ERROR="not_executed"

if [ -n "$BACKEND_POD" ]; then
    # Execute socket test from Backend pod and capture exit status
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
    
    # Validate socket test execution
    if [ $SOCKET_TEST_EXIT -ne 0 ]; then
        # kubectl exec or Python failed
        if echo "$SOCKET_TEST_OUTPUT" | grep -q "PYTHON_EXCEPTION"; then
            BACKEND_TO_DB_SOCKET_CODE="error"
            BACKEND_TO_DB_STATUS="test_error"
            BACKEND_TO_DB_SOCKET_ERROR="python_exception"
            echo "Socket test failed: Python exception during execution"
        else
            BACKEND_TO_DB_SOCKET_CODE="error"
            BACKEND_TO_DB_STATUS="test_error"
            BACKEND_TO_DB_SOCKET_ERROR="kubectl_exec_failed"
            echo "Socket test failed: kubectl exec failed (exit code: $SOCKET_TEST_EXIT)"
        fi
    elif [ -z "$SOCKET_TEST_OUTPUT" ]; then
        BACKEND_TO_DB_SOCKET_CODE="unknown"
        BACKEND_TO_DB_STATUS="test_error"
        BACKEND_TO_DB_SOCKET_ERROR="empty_output"
        echo "Socket test failed: empty output from kubectl exec"
    elif ! [[ "$SOCKET_TEST_OUTPUT" =~ ^[0-9]+$ ]]; then
        BACKEND_TO_DB_SOCKET_CODE="malformed"
        BACKEND_TO_DB_STATUS="test_error"
        BACKEND_TO_DB_SOCKET_ERROR="malformed_output"
        echo "Socket test failed: malformed output: $SOCKET_TEST_OUTPUT"
    else
        # Valid numeric socket return code
        BACKEND_TO_DB_SOCKET_CODE="$SOCKET_TEST_OUTPUT"
        
        # Classify the result conservatively (Linux-specific interpretation)
        if [ "$SOCKET_TEST_OUTPUT" = "0" ]; then
            BACKEND_TO_DB_STATUS="connected"
            BACKEND_TO_DB_SOCKET_ERROR="none"
        elif [ "$SOCKET_TEST_OUTPUT" = "11" ]; then
            BACKEND_TO_DB_STATUS="connection_timeout"
            BACKEND_TO_DB_SOCKET_ERROR="EAGAIN (observed after 5s timeout in this environment)"
        elif [ "$SOCKET_TEST_OUTPUT" = "110" ]; then
            BACKEND_TO_DB_STATUS="connection_timeout"
            BACKEND_TO_DB_SOCKET_ERROR="ETIMEDOUT"
        elif [ "$SOCKET_TEST_OUTPUT" = "111" ]; then
            BACKEND_TO_DB_STATUS="connection_refused"
            BACKEND_TO_DB_SOCKET_ERROR="ECONNREFUSED"
        elif [ "$SOCKET_TEST_OUTPUT" = "113" ]; then
            BACKEND_TO_DB_STATUS="connection_error"
            BACKEND_TO_DB_SOCKET_ERROR="EHOSTUNREACH"
        elif [ "$SOCKET_TEST_OUTPUT" = "101" ]; then
            BACKEND_TO_DB_STATUS="connection_error"
            BACKEND_TO_DB_SOCKET_ERROR="ENETUNREACH"
        else
            BACKEND_TO_DB_STATUS="connection_error"
            BACKEND_TO_DB_SOCKET_ERROR="unknown_code_${SOCKET_TEST_OUTPUT}"
        fi
        
        echo "Socket connection result: $BACKEND_TO_DB_STATUS (code: $BACKEND_TO_DB_SOCKET_CODE, error: $BACKEND_TO_DB_SOCKET_ERROR)"
    fi
    
    if [ "$BACKEND_TO_DB_STATUS" = "connection_timeout" ]; then
        echo "Connection timeout observed. This result is consistent with NetworkPolicy blocking traffic,"
        echo "but does not definitively prove causation without corroborating evidence from pod state."
    fi
else
    echo "⚠️  Backend pod not found, skipping connectivity test"
fi
echo ""

# Set legacy variable for backward compatibility with existing logic
BACKEND_TO_DB_BLOCKED=false
if [ "$BACKEND_TO_DB_STATUS" = "connection_timeout" ] || \
   [ "$BACKEND_TO_DB_STATUS" = "connection_refused" ] || \
   [ "$BACKEND_TO_DB_STATUS" = "connection_error" ]; then
    BACKEND_TO_DB_BLOCKED=true
fi

# Test 4: Backend health and readiness (application-level)
echo ""
echo "=== Test 4: Backend Health and Readiness ==="

BACKEND_PHASE="unknown"
BACKEND_READINESS="unknown"
BACKEND_LIVENESS="unknown"
BACKEND_RESTARTS="unknown"
BACKEND_HEALTH_FAILED=false

if [ -n "$BACKEND_POD" ]; then
    # Get Backend pod phase
    BACKEND_PHASE=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
    echo "Backend phase: $BACKEND_PHASE"
    
    # Get Backend pod readiness from Kubernetes
    BACKEND_READY=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    
    if [ "$BACKEND_READY" = "True" ]; then
        BACKEND_READINESS="ready"
        echo "Backend readiness: Ready"
    elif [ "$BACKEND_READY" = "False" ]; then
        BACKEND_READINESS="not_ready"
        echo "Backend readiness: NotReady"
    else
        BACKEND_READINESS="unknown"
        echo "Backend readiness: Unknown"
    fi
    
    # Get Backend restart count
    BACKEND_RESTARTS=$(kubectl get pod "$BACKEND_POD" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)
    echo "Backend restart count: $BACKEND_RESTARTS"
    
    # Check liveness by verifying /live endpoint using Python
    LIVE_CHECK=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import urllib.request
import sys
try:
    response = urllib.request.urlopen('http://localhost:8000/live', timeout=5)
    sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null && echo "healthy" || echo "unhealthy")
    
    BACKEND_LIVENESS="$LIVE_CHECK"
    echo "Backend liveness: $BACKEND_LIVENESS (/live endpoint)"
    
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

# Determine hypothesis confirmation
echo ""
echo "=== Hypothesis: NetworkPolicy Blocks Backend→Database ==="

# Six-condition hypothesis check - requires connection_timeout specifically
if [ "$POLICY_EXISTS" = true ] && \
   [ "$BACKEND_TO_DB_STATUS" = "connection_timeout" ] && \
   [ "$BACKEND_READINESS" = "not_ready" ] && \
   [ "$BACKEND_LIVENESS" = "healthy" ] && \
   [ "$BACKEND_PHASE" = "Running" ] && \
   [ "$DB_STATUS" = "Running" ]; then
    HYPOTHESIS_CONFIRMED=true
    HYPOTHESIS_REASONING="All six conditions met: NetworkPolicy exists, Backend→Database connection timeout observed (socket code $BACKEND_TO_DB_SOCKET_CODE), Backend readiness not_ready, Backend liveness healthy, Backend phase Running, PostgreSQL phase Running. The observed behavior is consistent with NetworkPolicy blocking required communication. This does not constitute definitive proof of causation, but represents strong supporting evidence when all conditions align."
    echo "✅ Hypothesis CONFIRMED"
    echo "   $HYPOTHESIS_REASONING"
else
    HYPOTHESIS_CONFIRMED=false
    
    # Build detailed reasoning
    HYPOTHESIS_REASONING="Hypothesis NOT confirmed. Required conditions:"
    HYPOTHESIS_REASONING="${HYPOTHESIS_REASONING} [1. Policy exists: $POLICY_EXISTS]"
    HYPOTHESIS_REASONING="${HYPOTHESIS_REASONING} [2. Connection timeout: $([ "$BACKEND_TO_DB_STATUS" = "connection_timeout" ] && echo "true (code $BACKEND_TO_DB_SOCKET_CODE)" || echo "false ($BACKEND_TO_DB_STATUS)")]"
    HYPOTHESIS_REASONING="${HYPOTHESIS_REASONING} [3. Backend readiness not_ready: $([ "$BACKEND_READINESS" = "not_ready" ] && echo "true" || echo "false ($BACKEND_READINESS)")]"
    HYPOTHESIS_REASONING="${HYPOTHESIS_REASONING} [4. Backend liveness healthy: $([ "$BACKEND_LIVENESS" = "healthy" ] && echo "true" || echo "false ($BACKEND_LIVENESS)")]"
    HYPOTHESIS_REASONING="${HYPOTHESIS_REASONING} [5. Backend Running: $([ "$BACKEND_PHASE" = "Running" ] && echo "true" || echo "false ($BACKEND_PHASE)")]"
    HYPOTHESIS_REASONING="${HYPOTHESIS_REASONING} [6. PostgreSQL Running: $([ "$DB_STATUS" = "Running" ] && echo "true" || echo "false ($DB_STATUS)")]"
    
    echo "❌ Hypothesis NOT confirmed"
    echo "   $HYPOTHESIS_REASONING"
fi
echo ""

# Generate JSON output using Python for safe serialization
echo "Writing results to: $OUTPUT_FILE"

# Export shell variables as environment variables for Python
export JSON_TIMESTAMP="$TIMESTAMP"
export JSON_NAMESPACE="$NAMESPACE"
export JSON_POLICY_NAME="$POLICY_NAME"
export JSON_POLICY_STATUS="$([ "$POLICY_EXISTS" = true ] && echo "active" || echo "not_found")"
export JSON_FRONTEND_OK="$([ "$FRONTEND_OK" = true ] && echo "true" || echo "false")"
export JSON_FRONTEND_TO_BACKEND="$([ "$FRONTEND_TO_BACKEND_OK" = true ] && echo "success" || echo "failed")"
export JSON_SOCKET_CODE="$BACKEND_TO_DB_SOCKET_CODE"
export JSON_SOCKET_ERROR="$BACKEND_TO_DB_SOCKET_ERROR"
export JSON_SOCKET_STATUS="$BACKEND_TO_DB_STATUS"
export JSON_BACKEND_PHASE="$BACKEND_PHASE"
export JSON_BACKEND_READINESS="$BACKEND_READINESS"
export JSON_BACKEND_LIVENESS="$BACKEND_LIVENESS"
export JSON_BACKEND_RESTARTS="$BACKEND_RESTARTS"
export JSON_DATABASE_POD="$([ "$DB_POD_RUNNING" = true ] && echo "running" || echo "not_running")"
export JSON_POLICY_EXISTS="$([ "$POLICY_EXISTS" = true ] && echo "true" || echo "false")"
export JSON_BACKEND_HEALTH_FAILED="$([ "$BACKEND_HEALTH_FAILED" = true ] && echo "true" || echo "false")"
export JSON_DB_POD_RUNNING="$([ "$DB_POD_RUNNING" = true ] && echo "true" || echo "false")"
export JSON_HYPOTHESIS_CONFIRMED="$([ "$HYPOTHESIS_CONFIRMED" = true ] && echo "true" || echo "false")"
export JSON_HYPOTHESIS_REASONING="$HYPOTHESIS_REASONING"

python3 << 'PYTHON_EOF' > "$OUTPUT_FILE"
import json
import os

# Convert string to boolean
def to_bool(value):
    return value == "true"

# Convert restart count to int if numeric, else keep as string
def to_restart_count(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return value

# Read all values from environment variables
data = {
    "timestamp": os.environ.get("JSON_TIMESTAMP", ""),
    "milestone": "2",
    "cluster": "poc-cluster",
    "namespace": os.environ.get("JSON_NAMESPACE", ""),
    "policy": {
        "name": os.environ.get("JSON_POLICY_NAME", ""),
        "status": os.environ.get("JSON_POLICY_STATUS", ""),
        "description": "Isolate PostgreSQL pods from all ingress traffic"
    },
    "expected_behavior": {
        "frontend_accessible": True,
        "frontend_to_backend": "success",
        "backend_to_database": "connectivity affected when NetworkPolicy active",
        "backend_health": "readiness not_ready, liveness healthy, phase Running when database unreachable",
        "database_pod": "running",
        "end_to_end": "not_tested"
    },
    "observed_behavior": {
        "frontend_accessible": to_bool(os.environ.get("JSON_FRONTEND_OK", "false")),
        "frontend_to_backend": os.environ.get("JSON_FRONTEND_TO_BACKEND", "failed"),
        "backend_to_database": {
            "socket_code": os.environ.get("JSON_SOCKET_CODE", "unknown"),
            "socket_error": os.environ.get("JSON_SOCKET_ERROR", "unknown"),
            "status": os.environ.get("JSON_SOCKET_STATUS", "test_error"),
            "interpretation": "Socket result is consistent with NetworkPolicy blocking traffic when status is connection_timeout and corroborating evidence from pod state is present. Does not definitively prove causation."
        },
        "backend_health": {
            "phase": os.environ.get("JSON_BACKEND_PHASE", "unknown"),
            "readiness": os.environ.get("JSON_BACKEND_READINESS", "unknown"),
            "liveness": os.environ.get("JSON_BACKEND_LIVENESS", "unknown"),
            "restart_count": to_restart_count(os.environ.get("JSON_BACKEND_RESTARTS", "unknown"))
        },
        "database_pod": os.environ.get("JSON_DATABASE_POD", "not_running"),
        "end_to_end": "not_verified"
    },
    "verification_method": {
        "network_connectivity_test": "Python socket.connect_ex() from backend pod to database-service:5432, with explicit kubectl exec status validation",
        "socket_code_interpretation": "Linux-specific error code mapping (0=connected, 110=ETIMEDOUT, 111=ECONNREFUSED, 113=EHOSTUNREACH, 101=ENETUNREACH)",
        "application_health_test": "Kubernetes readiness state (primary) and /live endpoint liveness check",
        "pod_status_test": "kubectl get pods with phase and condition inspection"
    },
    "verification_results": {
        "policy_exists": to_bool(os.environ.get("JSON_POLICY_EXISTS", "false")),
        "backend_to_database_status": os.environ.get("JSON_SOCKET_STATUS", "test_error"),
        "backend_health_indicates_failure": to_bool(os.environ.get("JSON_BACKEND_HEALTH_FAILED", "false")),
        "postgres_pod_still_running": to_bool(os.environ.get("JSON_DB_POD_RUNNING", "false"))
    },
    "hypothesis": {
        "statement": "Applying NetworkPolicy that isolates PostgreSQL will block required Backend → PostgreSQL communication, causing application failure while PostgreSQL pod remains running",
        "conditions_met": to_bool(os.environ.get("JSON_HYPOTHESIS_CONFIRMED", "false")),
        "reasoning": os.environ.get("JSON_HYPOTHESIS_REASONING", ""),
        "conditions_checked": [
            "NetworkPolicy exists",
            "Backend→Database connection timeout (socket code 110)",
            "Backend readiness not_ready",
            "Backend liveness healthy",
            "Backend phase Running",
            "PostgreSQL phase Running"
        ],
        "interpretation": "conditions_met indicates all six conditions aligned, consistent with NetworkPolicy enforcement. This does not constitute definitive proof of causation."
    },
    "notes": "Conservative interpretation: Connection timeout alone does not prove NetworkPolicy causation. Hypothesis confirmation requires all six conditions. Socket error codes interpreted as Linux-specific errno values."
}

print(json.dumps(data, indent=2))
PYTHON_EOF

echo "✅ Verification complete"
echo ""
echo "EVIDENCE_FILE: $OUTPUT_FILE"
echo ""
echo "=================================================="
echo "Summary:"
echo "  Cluster: $([ "$CLUSTER_OK" = true ] && echo "✅" || echo "❌")"
echo "  NetworkPolicy: $([ "$POLICY_EXISTS" = true ] && echo "✅" || echo "❌")"
echo "  Pods Running: $([ "$PODS_RUNNING" = true ] && echo "✅" || echo "❌")"
echo "  Frontend OK: $([ "$FRONTEND_OK" = true ] && echo "✅" || echo "❌")"
echo "  Frontend→Backend: $([ "$FRONTEND_TO_BACKEND_OK" = true ] && echo "✅" || echo "❌")"
echo "  Backend→DB Status: $BACKEND_TO_DB_STATUS"
echo "  Backend Health Failed: $([ "$BACKEND_HEALTH_FAILED" = true ] && echo "✅" || echo "❌")"
echo "  DB Pod Running: $([ "$DB_POD_RUNNING" = true ] && echo "✅" || echo "❌")"
echo "  Hypothesis: $([ "$HYPOTHESIS_CONFIRMED" = true ] && echo "✅ CONFIRMED" || echo "❌ NOT CONFIRMED")"
echo "=================================================="
echo ""
echo "Results saved to: $OUTPUT_FILE"
echo ""
echo "To rollback: ./scripts/remove-network-policy.sh"
