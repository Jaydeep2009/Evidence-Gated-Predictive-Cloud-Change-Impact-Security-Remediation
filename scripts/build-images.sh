#!/bin/bash
# build-images.sh
# Builds Docker images and loads them into Kind cluster

set -e

CLUSTER_NAME="poc-cluster"
BACKEND_IMAGE="poc-backend:latest"
FRONTEND_IMAGE="poc-frontend:latest"

echo "========================================="
echo "Building Docker Images"
echo "========================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    exit 1
fi

# Build Backend image
echo ""
echo "Building Backend image..."
docker build -t ${BACKEND_IMAGE} ./services/backend

# Build Frontend image
echo ""
echo "Building Frontend image..."
docker build -t ${FRONTEND_IMAGE} ./services/frontend

echo ""
echo "✅ Images built successfully"

# Load images into Kind cluster
echo ""
echo "========================================="
echo "Loading Images into Kind Cluster"
echo "========================================="

# Check if cluster exists
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "❌ Error: Cluster '${CLUSTER_NAME}' does not exist"
    echo "Run ./scripts/setup-cluster.sh first"
    exit 1
fi

echo "Loading Backend image..."
kind load docker-image ${BACKEND_IMAGE} --name ${CLUSTER_NAME}

echo "Loading Frontend image..."
kind load docker-image ${FRONTEND_IMAGE} --name ${CLUSTER_NAME}

echo ""
echo "✅ Images loaded into Kind cluster"

echo ""
echo "Built images:"
docker images | grep "poc-"

echo ""
echo "========================================="
echo "Build Complete!"
echo "========================================="
