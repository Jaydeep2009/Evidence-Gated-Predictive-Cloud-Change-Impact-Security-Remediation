#!/bin/bash
# setup-cluster.sh
# Creates Kind cluster for POC application

set -e

CLUSTER_NAME="poc-cluster"

echo "========================================="
echo "Setting up Kind Cluster"
echo "========================================="

# Check if Kind is installed
if ! command -v kind &> /dev/null; then
    echo "❌ Error: Kind is not installed"
    echo "Install from: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
    exit 1
fi

# Check if cluster already exists
if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "⚠️  Cluster '${CLUSTER_NAME}' already exists"
    read -p "Do you want to delete and recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing cluster..."
        kind delete cluster --name ${CLUSTER_NAME}
    else
        echo "Using existing cluster"
        exit 0
    fi
fi

# Create Kind cluster with port mapping for NodePort
echo "Creating Kind cluster..."
cat <<EOF | kind create cluster --name ${CLUSTER_NAME} --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080
    hostPort: 30080
    protocol: TCP
EOF

# Verify cluster is running
echo ""
echo "Verifying cluster..."
kubectl cluster-info --context kind-${CLUSTER_NAME}

echo ""
echo "✅ Kind cluster '${CLUSTER_NAME}' created successfully"
echo ""
echo "Cluster nodes:"
kubectl get nodes

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
