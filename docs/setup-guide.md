# Setup Guide - Milestone 1

## Overview

This guide walks through setting up the Milestone 1 baseline application step-by-step.

## Prerequisites

### Windows Host

- Windows 10/11
- WSL2 installed and configured
- Ubuntu distribution installed in WSL2

### WSL2 Environment

Open Ubuntu in WSL2 and verify:

```bash
# Check WSL version
wsl -l -v

# Should show Ubuntu with VERSION 2
```

### Install Docker Desktop

1. Download Docker Desktop for Windows
2. Install with WSL2 backend enabled
3. Open Docker Desktop settings
4. Enable "Use the WSL 2 based engine"
5. Under Resources → WSL Integration, enable Ubuntu

Verify in WSL2:
```bash
docker --version
docker ps
```

### Install Kind

```bash
# Download Kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64

# Make executable
chmod +x ./kind

# Move to PATH
sudo mv ./kind /usr/local/bin/kind

# Verify
kind --version
```

### Install kubectl

```bash
# Download kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Make executable
chmod +x kubectl

# Move to PATH
sudo mv kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

## Setup Steps

### Step 1: Navigate to Project Directory

```bash
cd /mnt/c/Users/sai/Desktop/Final-Year-Project
```

### Step 2: Make Scripts Executable

```bash
chmod +x scripts/*.sh
```

### Step 3: Create Kind Cluster

```bash
./scripts/setup-cluster.sh
```

**Expected output:**
- Creating cluster "poc-cluster"
- Cluster configuration
- Node status

**Verify:**
```bash
kind get clusters
# Should show: poc-cluster

kubectl cluster-info --context kind-poc-cluster
# Should show control plane running
```

### Step 4: Build Docker Images

```bash
./scripts/build-images.sh
```

**Expected output:**
- Building Backend image
- Building Frontend image
- Loading images into Kind

**Verify:**
```bash
docker images | grep poc
# Should show:
#   poc-backend    latest
#   poc-frontend   latest
```

### Step 5: Deploy Application

```bash
./scripts/deploy-all.sh
```

**Expected output:**
- Creating namespace
- Deploying database
- Deploying backend
- Deploying frontend
- Waiting for pods (1-2 minutes)
- All pods ready

**Verify:**
```bash
kubectl get pods -n poc-app
# Should show all pods with STATUS Running and READY 1/1
```

### Step 6: Verify Baseline

```bash
./scripts/verify-baseline.sh
```

**Expected output:**
- ✅ Cluster is running
- ✅ All pods are running
- ✅ Frontend accessible
- ✅ Frontend can reach Backend
- ✅ Backend can reach Database
- ✅ Database query executed successfully
- ✅ End-to-end request successful
- Baseline verification saved to baseline-verification.json

### Step 7: Test in Browser

Open: http://localhost:30080

**Expected to see:**
- System Status card showing "healthy"
- Database Connectivity card with all green checkmarks
- Database version
- Query result: 1
- Response time in milliseconds

## Verification Checklist

- [ ] Kind cluster created
- [ ] Docker images built
- [ ] All pods Running (1/1)
- [ ] All services have endpoints
- [ ] Frontend accessible at localhost:30080
- [ ] Backend health endpoint returns 200
- [ ] Database query executes successfully
- [ ] baseline-verification.json created
- [ ] Browser shows green checkmarks

## Common Issues

### Docker not running

**Symptom:** `Cannot connect to the Docker daemon`

**Solution:**
1. Open Docker Desktop
2. Wait for it to start
3. Retry command

### Kind cluster creation fails

**Symptom:** `failed to create cluster`

**Solution:**
```bash
# Check Docker is running
docker ps

# Delete any existing cluster
kind delete cluster --name poc-cluster

# Retry
./scripts/setup-cluster.sh
```

### Pods stuck in ImagePullBackOff

**Symptom:** `kubectl get pods` shows ImagePullBackOff

**Solution:**
```bash
# Rebuild and reload images
./scripts/build-images.sh
```

### Backend cannot connect to database

**Symptom:** `/health` returns "connected": false

**Solution:**
```bash
# Check database pod
kubectl get pods -n poc-app -l app=database
kubectl logs -n poc-app -l app=database

# Wait for database to be ready
kubectl wait --for=condition=ready pod -l app=database -n poc-app --timeout=120s
```

### Port 30080 not accessible

**Symptom:** `curl http://localhost:30080` fails

**Solution:**
```bash
# Check port mapping
docker ps | grep poc-cluster

# Recreate cluster with correct config
./scripts/cleanup.sh
./scripts/setup-cluster.sh
./scripts/build-images.sh
./scripts/deploy-all.sh
```

## Next Steps

After successful setup:

1. Explore the application in browser
2. Review `baseline-verification.json`
3. Understand each component's role
4. Review Kubernetes resources: `kubectl get all -n poc-app`
5. Check logs: `kubectl logs -n poc-app -l app=backend`

This baseline is now ready for Milestone 2 (NetworkPolicy introduction).
