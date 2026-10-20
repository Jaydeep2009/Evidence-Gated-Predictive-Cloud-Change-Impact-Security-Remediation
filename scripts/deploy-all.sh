#!/bin/bash
# deploy-all.sh
# Deploys all Kubernetes resources

set -e

CLUSTER_NAME="poc-cluster"
NAMESPACE="poc-app"

echo "========================================="
echo "Deploying Application to Kubernetes"
echo "========================================="

# Check if cluster exists
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "❌ Error: Cluster '${CLUSTER_NAME}' does not exist"
    echo "Run ./scripts/setup-cluster.sh first"
    exit 1
fi

# Set kubectl context
kubectl config use-context kind-${CLUSTER_NAME}

# Create namespace
echo ""
echo "Creating namespace..."
kubectl apply -f kubernetes/namespace.yaml

# Deploy database
echo ""
echo "Deploying database..."
kubectl apply -f kubernetes/database/

# Deploy backend
echo ""
echo "Deploying backend..."
kubectl apply -f kubernetes/backend/

# Deploy frontend
echo ""
echo "Deploying frontend..."
kubectl apply -f kubernetes/frontend/

echo ""
echo "Waiting for pods to be ready (this may take 1-2 minutes)..."
echo ""

# Wait for database
echo "Waiting for database..."
kubectl wait --for=condition=ready pod -l app=database -n ${NAMESPACE} --timeout=120s

# Wait for backend
echo "Waiting for backend..."
kubectl wait --for=condition=ready pod -l app=backend -n ${NAMESPACE} --timeout=120s

# Wait for frontend
echo "Waiting for frontend..."
kubectl wait --for=condition=ready pod -l app=frontend -n ${NAMESPACE} --timeout=120s

echo ""
echo "✅ All pods are ready"

echo ""
echo "========================================="
echo "Deployment Status"
echo "========================================="
echo ""
kubectl get all -n ${NAMESPACE}

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Frontend URL: http://localhost:30080"
echo ""
echo "To check logs:"
echo "  kubectl logs -n ${NAMESPACE} -l app=frontend"
echo "  kubectl logs -n ${NAMESPACE} -l app=backend"
echo "  kubectl logs -n ${NAMESPACE} -l app=database"
