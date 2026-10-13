#!/bin/bash
# cleanup.sh
# Deletes Kind cluster and optionally removes Docker images

set -e

CLUSTER_NAME="poc-cluster"

echo "========================================="
echo "Cleanup"
echo "========================================="

# Delete Kind cluster
if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "Deleting Kind cluster '${CLUSTER_NAME}'..."
    kind delete cluster --name ${CLUSTER_NAME}
    echo "✅ Cluster deleted"
else
    echo "⚠️  Cluster '${CLUSTER_NAME}' does not exist"
fi

# Ask about Docker images
echo ""
read -p "Do you want to remove Docker images? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing Docker images..."
    docker rmi poc-backend:latest poc-frontend:latest 2>/dev/null || true
    echo "✅ Images removed"
fi

echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
