#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
POLICY_FILE="$PROJECT_ROOT/kubernetes/policies/isolate-database.yaml"
NAMESPACE="poc-app"
POLICY_NAME="isolate-database"

echo "=================================================="
echo "Milestone 2: Apply NetworkPolicy"
echo "=================================================="
echo ""

# Check cluster
echo "Checking cluster status..."
if ! kubectl cluster-info --context kind-poc-cluster &>/dev/null; then
    echo "❌ Cluster not running"
    exit 1
fi
echo "✅ Cluster running"
echo ""

# Check baseline exists
echo "Verifying Milestone 1 baseline..."
if [ ! -f "$PROJECT_ROOT/baseline-verification.json" ]; then
    echo "⚠️  Warning: baseline-verification.json not found"
    echo "   Run: ./scripts/verify-baseline.sh first"
fi
echo ""

# Apply policy
echo "Applying NetworkPolicy: $POLICY_NAME"
echo "⚠️  This will isolate PostgreSQL pods from ALL ingress traffic"
echo "⚠️  Backend → PostgreSQL is the required application communication path"
echo "⚠️  This will cause Backend database connectivity to fail"
echo ""

kubectl apply -f "$POLICY_FILE"

# Wait for propagation
echo ""
echo "Waiting for policy to propagate..."
sleep 5

# Verify policy exists
if kubectl get networkpolicy "$POLICY_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo "✅ Policy active: $POLICY_NAME"
else
    echo "❌ Policy not found"
    exit 1
fi

echo ""
echo "=================================================="
echo "Expected operational impact:"
echo "  - Frontend → Backend: STILL WORKING"
echo "  - Backend → PostgreSQL: BLOCKED"
echo "  - Backend health: will report database failure"
echo "  - Application functionality: will fail"
echo "=================================================="
echo ""
echo "Next step: ./scripts/verify-network-policy.sh"
