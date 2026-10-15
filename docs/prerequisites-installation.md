# Prerequisites Installation Guide

This guide provides detailed instructions for installing all required software for Milestone 1.

## Table of Contents

1. [WSL2 Setup](#wsl2-setup)
2. [Docker Desktop Installation](#docker-desktop-installation)
3. [Kind Installation](#kind-installation)
4. [kubectl Installation](#kubectl-installation)
5. [Verification](#verification)

---

## 1. WSL2 Setup

### Check if WSL2 is Installed

Open PowerShell as Administrator and run:

```powershell
wsl --list --verbose
```

**Expected output:**
```
  NAME              STATE           VERSION
* Ubuntu            Running         2
```

If VERSION is 1, upgrade to WSL2:

```powershell
wsl --set-version Ubuntu 2
```

### Install Ubuntu (if not already installed)

```powershell
wsl --install -d Ubuntu
```

After installation, launch Ubuntu and create a user account.

---

## 2. Docker Desktop Installation

### Download and Install

1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop
2. Run the installer
3. **Important:** During installation, ensure "Use WSL 2 instead of Hyper-V" is checked

### Configure WSL2 Integration

After installation:

1. Open Docker Desktop
2. Go to Settings → General
3. Ensure "Use the WSL 2 based engine" is **checked**
4. Go to Settings → Resources → WSL Integration
5. Enable integration with Ubuntu distribution
6. Click "Apply & Restart"

### Verify Docker in WSL2

Open Ubuntu in WSL2:

```bash
docker --version
```

**Expected output:**
```
Docker version 24.0.x, build xxxxx
```

Test Docker:

```bash
docker run hello-world
```

**Expected output:**
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

---

## 3. Kind Installation

### Install Kind in WSL2

Open Ubuntu in WSL2 and run:

```bash
# Download Kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64

# Make executable
chmod +x ./kind

# Move to PATH
sudo mv ./kind /usr/local/bin/kind

# Verify installation
kind --version
```

**Expected output:**
```
kind version 0.20.0
```

---

## 4. kubectl Installation

### Install kubectl in WSL2

```bash
# Download kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Make executable
chmod +x kubectl

# Move to PATH
sudo mv kubectl /usr/local/bin/kubectl

# Verify installation
kubectl version --client
```

**Expected output:**
```
Client Version: v1.28.x
```

---

## 5. Verification

### Complete Verification Checklist

Run these commands in WSL2 Ubuntu:

```bash
# 1. Check WSL version (from PowerShell)
wsl --list --verbose
# Expected: Ubuntu with VERSION 2

# 2. Check Docker
docker --version
docker ps
# Expected: Version shown, no error connecting to daemon

# 3. Check Kind
kind --version
# Expected: kind version 0.20.0

# 4. Check kubectl
kubectl version --client
# Expected: Client Version shown

# 5. Navigate to project
cd /mnt/c/Users/sai/Desktop/Final-Year-Project
pwd
# Expected: /mnt/c/Users/sai/Desktop/Final-Year-Project

# 6. Verify scripts are executable
ls -l scripts/
# Expected: All .sh files should have executable permissions (x)
```

### Test Docker Access

```bash
# Test Docker can pull images
docker pull nginx:alpine

# Should download successfully
```

---

## Common Issues

### Issue: "Docker is not running"

**Solution:**
1. Open Docker Desktop application
2. Wait for "Docker Desktop is running" indicator
3. Retry command

### Issue: "Cannot connect to Docker daemon"

**Solution:**
1. Check Docker Desktop WSL2 integration (Settings → Resources → WSL Integration)
2. Ensure Ubuntu is enabled
3. Restart Docker Desktop
4. Restart WSL2: `wsl --shutdown` then reopen Ubuntu

### Issue: "kind command not found"

**Solution:**
```bash
# Check if kind is in PATH
which kind

# If not found, verify installation location
ls /usr/local/bin/kind

# If missing, reinstall following step 3
```

### Issue: "kubectl command not found"

**Solution:**
```bash
# Check if kubectl is in PATH
which kubectl

# If not found, reinstall following step 4
```

### Issue: Permission denied when moving to /usr/local/bin

**Solution:**
```bash
# Use sudo
sudo mv ./kind /usr/local/bin/kind
sudo mv ./kubectl /usr/local/bin/kubectl
```

---

## Next Steps

After all prerequisites are installed and verified:

1. Navigate to project directory:
   ```bash
   cd /mnt/c/Users/sai/Desktop/Final-Year-Project
   ```

2. Follow the main setup guide:
   ```bash
   cat docs/setup-guide.md
   ```

3. Run setup scripts:
   ```bash
   ./scripts/setup-cluster.sh
   ./scripts/build-images.sh
   ./scripts/deploy-all.sh
   ./scripts/verify-baseline.sh
   ```

4. Access application: http://localhost:30080

---

## System Requirements

- **OS:** Windows 10/11 with WSL2
- **RAM:** Minimum 8GB (16GB recommended)
- **Disk Space:** 20GB free
- **CPU:** 4 cores recommended
- **Internet:** Required for downloading images and tools

---

## Installation Time Estimate

- WSL2 setup: 10-15 minutes
- Docker Desktop: 10-15 minutes  
- Kind + kubectl: 5 minutes
- **Total: ~30-35 minutes**

Once installed, these prerequisites don't need to be reinstalled for future milestones.
