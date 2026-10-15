#!/bin/bash
set -e

NAMESPACE="poc-app"
POLICY_NAME="isolate-database"

echo "=================================================="
echo "Milestone 2: Remove NetworkPolicy"
echo "=================================================="
echo ""

# Check cluster
echo "Checking cluster status..."
if ! kubectl cluster-info --context kind-poc-cluster &>/dev/null; then
    echo "❌ Cluster not running"
    exit 1
fi
echo ""

# Check if policy exists
if ! kubectl get networkpolicy "$POLICY_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo "⚠️  NetworkPolicy not found: $POLICY_NAME"
    echo "   (Already removed or never applied)"
    exit 0
fi

# Delete policy
echo "Removing NetworkPolicy: $POLICY_NAME"
kubectl delete networkpolicy "$POLICY_NAME" -n "$NAMESPACE"

echo "✅ NetworkPolicy deleted"
echo ""

# Wait for propagation and backend recovery
echo "Waiting for policy propagation and Backend recovery..."
sleep 10

# Test Backend → PostgreSQL connectivity
BACKEND_POD=$(kubectl get pod -n "$NAMESPACE" -l app=backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$BACKEND_POD" ]; then
    echo ""
    echo "Testing Backend → PostgreSQL connectivity..."
    
    # Check health endpoint
    HEALTH_RESPONSE=$(kubectl exec "$BACKEND_POD" -n "$NAMESPACE" -- python3 -c "
import urllib.request
import json
try:
    response = urllib.request.urlopen('http://localhost:8000/health', timeout=5)
    data = json.loads(response.read().decode())
    print(json.dumps(data))
except Exception as e:
    print(json.dumps({'error': str(e)}))
" 2>/dev/null)

    DB_CONNECTED=$(echo "$HEALTH_RESPONSE" | python3 -c "
import sys
import json
try:
    data = json.load(sys.stdin)
    if 'database' in data and 'connected' in data['database']:
        print('true' if data['database']['connected'] else 'false')
    else:
        print('unknown')
except:
    print('unknown')
" 2>/dev/null)

    if [ "$DB_CONNECTED" = "true" ]; then
        echo "✅ Backend → PostgreSQL connectivity restored"
        echo "✅ Backend health: healthy"
    else
        echo "⚠️  Backend → PostgreSQL connectivity not yet restored"
        echo "   Wait a few more seconds and check manually"
    fi
else
    echo "⚠️  Backend pod not found"
fi

echo ""
echo "=================================================="
echo "NetworkPolicy removed"
echo "=================================================="
echo ""
echo "To verify baseline fully restored:"
echo "  ./scripts/verify-baseline.sh"
