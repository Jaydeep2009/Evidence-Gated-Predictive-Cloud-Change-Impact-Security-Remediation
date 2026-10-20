# Evidence-Gated Predictive Cloud Change Impact & Security Remediation

Final-Year Engineering Research Project

## Project Overview

This project investigates whether combining infrastructure, application, and runtime evidence improves prediction of security and operational impact of cloud-security changes compared with infrastructure-only analysis.

**Current Status:** Milestone 1 - Baseline Application

## Milestone 1: Local Proof-of-Concept

### Goal

Establish a minimal reproducible Kubernetes application: **Frontend → Backend → PostgreSQL**

This baseline must work successfully before introducing security policies (NetworkPolicy) in Milestone 2.

### Architecture

```
User → Frontend (NodePort 30080) → Backend (ClusterIP) → PostgreSQL (ClusterIP)
```

**Environment:**
- Windows host
- WSL2 (Ubuntu)
- Docker Desktop
- Kind (Kubernetes in Docker)
- kubectl

### Prerequisites

Ensure the following are installed in WSL2:

- Docker Desktop (with WSL2 backend enabled)
- Kind: `curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64 && chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind`
- kubectl: Follow [Kubernetes installation guide](https://kubernetes.io/docs/tasks/tools/)

Verify installations:
```bash
docker --version
kind --version
kubectl version --client
```

## Quick Start

### 1. Setup Cluster

```bash
cd /path/to/Final-Year-Project
chmod +x scripts/*.sh
./scripts/setup-cluster.sh
```

This creates a Kind cluster named `poc-cluster` with port mapping for NodePort 30080.

### 2. Build Images

```bash
./scripts/build-images.sh
```

This builds Docker images for Frontend and Backend, then loads them into the Kind cluster.

### 3. Deploy Application

```bash
./scripts/deploy-all.sh
```

This deploys all Kubernetes resources and waits for pods to be ready.

### 4. Verify Baseline

```bash
./scripts/verify-baseline.sh
```

This verifies all communication paths and creates `baseline-verification.json` documenting the working state.

### 5. Access Application

Open your browser: [http://localhost:30080](http://localhost:30080)

You should see:
- ✅ Overall Status: healthy
- ✅ Database Connected: true
- ✅ Database Version: PostgreSQL 15.x
- ✅ Test Query Result: 1

## Project Organization

- **[task.md](task.md)** - Team work split, implementation order, and task assignments
- **[implementation.md](implementation.md)** - Complete technical specification: what to build and how
- **[MILESTONE-1-SUMMARY.md](MILESTONE-1-SUMMARY.md)** - Completed: Local Kubernetes baseline
- **[MILESTONE-2-SUMMARY.md](MILESTONE-2-SUMMARY.md)** - Completed: NetworkPolicy experiment
- **[docs/milestone-2-completion.md](docs/milestone-2-completion.md)** - Detailed M2 results and analysis

## Project Structure

```
Evidence-Gated-Predictive-Cloud-Change-Impact-Security-Remediation/
├── task.md                    # Work split and implementation plan
├── implementation.md          # Technical specification
├── MILESTONE-1-SUMMARY.md     # M1 completion record
├── MILESTONE-2-SUMMARY.md     # M2 completion record
├── .kiro/
│   └── steering/              # Research principles and guidelines
├── services/
│   ├── frontend/              # POC Frontend (Nginx)
│   ├── backend/               # POC Backend (FastAPI)
│   └── database/              # POC Database (PostgreSQL)
├── src/
│   └── evgate/                # Evidence-gate analyzer (to be built)
├── kubernetes/                # K8s manifests
├── scripts/                   # Automation scripts
├── fixtures/
│   └── ground_truth/          # Experiment evidence records
└── docs/
    └── archive/               # Historical specs and debugging notes
```

## Services

### Frontend
- **Technology:** Nginx serving static HTML/JavaScript
- **Port:** 80 (exposed via NodePort 30080)
- **Purpose:** Simple UI to test end-to-end connectivity

### Backend
- **Technology:** Python 3.11 + FastAPI
- **Port:** 8000 (ClusterIP, internal only)
- **Endpoint:** `/health` - Verifies actual database connectivity
- **Health Check:** Returns HTTP 200 when both application and database are healthy, HTTP 503 when database is unreachable

### Database
- **Technology:** PostgreSQL 15
- **Port:** 5432 (ClusterIP, internal only)
- **Database:** appdb
- **User:** appuser (local development only)

## Health Checks

All services include Kubernetes liveness and readiness probes.

**Backend Health Endpoint:**
```bash
curl http://localhost:30080  # Access via Frontend
# or from within cluster:
kubectl exec -n poc-app deployment/backend-deployment -- curl http://localhost:8000/health
```

**Response (Success):**
```json
{
  "status": "healthy",
  "application": {
    "name": "poc-backend",
    "version": "1.0.0",
    "status": "running"
  },
  "database": {
    "connected": true,
    "version": "PostgreSQL 15.x",
    "test_query": "SELECT 1 AS result",
    "query_result": 1,
    "response_time_ms": 12
  },
  "timestamp": "2026-10-06T16:42:00.123Z"
}
```

## Troubleshooting

### Pods not starting

```bash
kubectl get pods -n poc-app
kubectl describe pod -n poc-app <pod-name>
kubectl logs -n poc-app <pod-name>
```

### Backend cannot connect to database

```bash
# Check database is ready
kubectl get pods -n poc-app -l app=database

# Check backend logs
kubectl logs -n poc-app -l app=backend

# Test DNS resolution from backend pod
kubectl exec -n poc-app deployment/backend-deployment -- nslookup database-service
```

### Frontend shows error

```bash
# Check frontend logs
kubectl logs -n poc-app -l app=frontend

# Check all services
kubectl get svc -n poc-app
```

### Port 30080 not accessible

```bash
# Verify Kind port mapping
docker ps | grep poc-cluster

# Check if Windows firewall is blocking
```

## Useful Commands

```bash
# View all resources
kubectl get all -n poc-app

# View logs (follow mode)
kubectl logs -n poc-app -l app=backend -f

# View events
kubectl get events -n poc-app --sort-by='.lastTimestamp'

# Port forward for debugging
kubectl port-forward -n poc-app service/backend-service 8000:8000

# Execute into pod
kubectl exec -n poc-app -it deployment/backend-deployment -- /bin/bash

# Delete and restart
./scripts/cleanup.sh
./scripts/setup-cluster.sh
./scripts/build-images.sh
./scripts/deploy-all.sh
```

## Cleanup

```bash
./scripts/cleanup.sh
```

This deletes the Kind cluster and optionally removes Docker images.

## Research Context

This Milestone 1 baseline is critical for the research methodology:

1. **Baseline State:** All communication paths working (documented in `baseline-verification.json`)
2. **Milestone 2:** Introduce NetworkPolicy blocking Backend → Database
3. **Expected Result:** Application breaks (Backend cannot reach Database)
4. **Research Question:** Can the system predict this impact using evidence?

Milestone 1 and 2 are complete. See **MILESTONE-1-SUMMARY.md** and **MILESTONE-2-SUMMARY.md** for results.

## License

Open source research project for educational purposes.

## Contact

Final-Year Engineering Student
Project: Evidence-Gated Predictive Cloud Change Impact & Security Remediation


---

## Part 4: Scenarios, Remediation, and Evaluation

**Status:** ✅ Complete (Module implementation 100%, Scenarios 12%)

Part 4 implements the experiment framework for evaluating the Evidence-Gated system.

### Features

- **40 Experiment Scenarios**: Network, RBAC, Mixed, and Typo scenarios
- **Ground Truth Collection**: Automated probe-based verification
- **Remediation Generators**: NetworkPolicy, RBAC, and Tofu fixes
- **Evaluation Framework**: Metrics, baselines, perturbation, statistics
- **Safety Guards**: Prevents accidental production execution

### Quick Test

```bash
# Install dependencies
pip install -r requirements.txt

# Test all Part 4 modules (no cluster required)
python test_part4.py
```

### Documentation

See **[PART4_README.md](PART4_README.md)** for complete Part 4 documentation:
- Module descriptions (P4-01 through P4-13)
- Scenario format and categories
- Remediation usage examples
- Evaluation metrics and statistics
- Integration guide for Parts 1-3

### Directory Structure

```
src/evgate/              # Part 4 Python modules
├── scenarios/           # Scenario loading and ground truth
├── remediation/         # Network, RBAC, Tofu remediators
├── evaluation/          # Metrics, stats, baselines, orchestrator
├── stubs/              # Integration stubs (replace with Parts 1-3)
└── common/             # Utilities and safety guards

scenarios/              # 40 experiment scenarios (YAML)
fixtures/ground_truth/  # Ground truth results (generated)
results/                # Evaluation results, tables, figures
```

### Current Scenarios

- ✅ N01: Isolate Database (Milestone 2 reproduction)
- ✅ N02: Isolate Backend
- ✅ N03: Allow Backend→Database (remediation)
- ✅ R01: Restrict Pod List Permission
- ✅ M01: Network + RBAC Combined

35 additional scenarios to be authored (N04-N10, R02-R10, M02-M10, T01-T10).

### Integration with Parts 1-3

Part 4 uses **stubs** for teammates' code:
- `src/evgate/stubs/part2_stubs.py` - Evidence collection stub
- `src/evgate/stubs/part3_stubs.py` - Core analyzer stub

Replace stubs with real implementations when available from:
https://github.com/Jaydeep2009/Evidence-Gated-Predictive-Cloud-Change-Impact-Security-Remediation

---
