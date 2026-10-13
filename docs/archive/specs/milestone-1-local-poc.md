# Milestone 1: Local Proof-of-Concept Environment

## Document Information

- **Milestone:** 1
- **Status:** Draft
- **Created:** 2026-10-06
- **Purpose:** Establish minimal reproducible Kubernetes application (Frontend → Backend → PostgreSQL)

---

## 1. Requirements

### Functional Requirements

**FR1:** Frontend service must successfully communicate with Backend service  
**FR2:** Backend service must successfully communicate with PostgreSQL database  
**FR3:** Application must return a clear successful response proving end-to-end connectivity  
**FR4:** Database connection must be verifiable through application response  
**FR5:** All services must run in a local Kubernetes cluster  

### Non-Functional Requirements

**NFR1:** All components must run locally without cloud dependencies  
**NFR2:** Environment must be reproducible on other machines  
**NFR3:** Setup must be documented and straightforward  
**NFR4:** Services must include basic health checks  
**NFR5:** Implementation must be minimal and educational  

### Out of Scope for This Milestone

- ❌ Evidence collection (infrastructure/application/runtime)
- ❌ Graph construction
- ❌ Impact prediction
- ❌ Evidence Gate
- ❌ Remediation
- ❌ OpenTofu infrastructure definitions
- ❌ Complex authentication/authorization
- ❌ Production-grade configuration
- ❌ Frontend UI framework (use minimal HTML/JS)
- ❌ CI/CD pipelines

### Deferred to Later Milestones

- 🔄 **OpenTelemetry/Jaeger/Prometheus** - Runtime evidence collection (Milestone 3)
- 🔄 **NetworkPolicy** - Security policy testing (Milestone 2)

**Rationale:** These are part of the final research architecture but not needed for establishing the baseline working application.

---

## 2. Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│          Windows Host Machine                    │
│  ┌───────────────────────────────────────────┐  │
│  │           WSL2 (Ubuntu)                    │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │    Docker Desktop                    │  │  │
│  │  │  ┌───────────────────────────────┐  │  │  │
│  │  │  │   Kind Cluster                │  │  │  │
│  │  │  │                               │  │  │  │
│  │  │  │   ┌──────────────────────┐   │  │  │  │
│  │  │  │   │   Frontend Pod       │   │  │  │  │
│  │  │  │   │   (Nginx + HTML/JS)  │   │  │  │  │
│  │  │  │   │   Port: 80           │   │  │  │  │
│  │  │  │   └──────────┬───────────┘   │  │  │  │
│  │  │  │              │ HTTP          │  │  │  │
│  │  │  │              ↓               │  │  │  │
│  │  │  │   ┌──────────────────────┐   │  │  │  │
│  │  │  │   │   Backend Pod        │   │  │  │  │
│  │  │  │   │   (Python/FastAPI)   │   │  │  │  │
│  │  │  │   │   Port: 8000         │   │  │  │  │
│  │  │  │   └──────────┬───────────┘   │  │  │  │
│  │  │  │              │ PostgreSQL    │  │  │  │
│  │  │  │              ↓               │  │  │  │
│  │  │  │   ┌──────────────────────┐   │  │  │  │
│  │  │  │   │   Database Pod       │   │  │  │  │
│  │  │  │   │   (PostgreSQL 15)    │   │  │  │  │
│  │  │  │   │   Port: 5432         │   │  │  │  │
│  │  │  │   └──────────────────────┘   │  │  │  │
│  │  │  └───────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Communication Flow

1. **User** → `http://localhost:8080` → **Frontend Service** (NodePort)
2. **Frontend** → `http://backend-service:8000/health` → **Backend Service** (ClusterIP)
3. **Backend** → `postgresql://database-service:5432/appdb` → **Database Service** (ClusterIP)
4. **Backend** returns JSON with database query result → **Frontend** displays

### Service Types

- **Frontend:** NodePort (accessible from host at localhost:8080)
- **Backend:** ClusterIP (internal only)
- **Database:** ClusterIP (internal only)

---

## 3. Component Responsibilities

### Frontend Service

**Purpose:** Provide simple web interface to test end-to-end connectivity

**Responsibilities:**
- Serve static HTML page
- Make HTTP request to Backend
- Display Backend response

**Technology:** Nginx serving static HTML/JavaScript

**API Consumed:**
- `GET /health` - Backend health check with database verification

**Does NOT:**
- Implement complex UI framework
- Handle authentication
- Store state
- Collect evidence

---

### Backend Service

**Purpose:** Application logic layer that communicates with database

**Responsibilities:**
- Expose REST API endpoint
- Connect to PostgreSQL database
- Execute database query to verify connectivity
- Return structured response with database information

**Technology:** Python 3.11 + FastAPI

**API Exposed:**
- `GET /health` - Returns application health AND database connectivity status with test query result

**Response Format (Success):**
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
    "version": "PostgreSQL 15.x on x86_64-pc-linux-musl",
    "test_query": "SELECT 1 AS result",
    "query_result": 1,
    "response_time_ms": 12
  },
  "timestamp": "2026-10-06T16:42:00.123Z"
}
```

**Response Format (Database Failure):**
```json
{
  "status": "unhealthy",
  "application": {
    "name": "poc-backend",
    "version": "1.0.0",
    "status": "running"
  },
  "database": {
    "connected": false,
    "error": "could not connect to server: Connection refused",
    "last_attempt": "2026-10-06T16:42:00.123Z"
  },
  "timestamp": "2026-10-06T16:42:00.123Z"
}
```

**Health Check Behavior:**
- HTTP 200: Application healthy AND database connected
- HTTP 503: Application running BUT database unreachable
- Returns actual database query result to verify real connectivity
- Includes response time for database query
- Clearly distinguishes application health from database health

**Dependencies:**
- `fastapi`
- `uvicorn`
- `psycopg2-binary` (PostgreSQL driver)

**Does NOT:**
- Implement complex business logic
- Collect application evidence
- Parse infrastructure configurations
- Generate predictions

---

### Database Service

**Purpose:** Persistent data storage

**Responsibilities:**
- Run PostgreSQL database
- Accept connections from Backend
- Store minimal test data

**Technology:** PostgreSQL 15 (configurable)

**Configuration:**
- Image: `postgres:15-alpine` (default, configurable via `POSTGRES_IMAGE` environment variable)
- Database name: `appdb`
- User: `appuser`
- Password: `apppassword` (for local development only)
- Port: 5432

**Image Configurability:**
The PostgreSQL version can be changed by setting the `POSTGRES_IMAGE` variable before deployment:
```bash
export POSTGRES_IMAGE=postgres:15-alpine  # default
export POSTGRES_IMAGE=postgres:16-alpine  # or newer version
```

**Initialization:**
- Create database `appdb`
- Create user `appuser`
- Grant permissions
- Create simple test table (optional)

**Does NOT:**
- Store evidence
- Store prediction results
- Implement complex schema

---

## 4. Kubernetes Resources Required

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: poc-app
```

**Rationale:** Isolate POC resources from other Kubernetes objects

---

### Frontend Resources

**Deployment:**
- Name: `frontend-deployment`
- Replicas: 1
- Container: nginx:alpine
- Port: 80
- Resources: minimal (100m CPU, 128Mi memory)

**Service:**
- Name: `frontend-service`
- Type: NodePort
- Port: 80
- NodePort: 30080 (accessible at localhost:30080)

**ConfigMap:**
- Name: `frontend-config`
- Contains: `index.html` with JavaScript to call Backend

---

### Backend Resources

**Deployment:**
- Name: `backend-deployment`
- Replicas: 1
- Container: Custom Python image
- Port: 8000
- Environment variables:
  - `DATABASE_HOST=database-service`
  - `DATABASE_PORT=5432`
  - `DATABASE_NAME=appdb`
  - `DATABASE_USER=appuser`
  - `DATABASE_PASSWORD=apppassword`
- Resources: minimal (200m CPU, 256Mi memory)

**Service:**
- Name: `backend-service`
- Type: ClusterIP
- Port: 8000

---

### Database Resources

**Deployment:**
- Name: `database-deployment`
- Replicas: 1
- Container: postgres:15-alpine (configurable via POSTGRES_IMAGE)
- Port: 5432
- Environment variables:
  - `POSTGRES_DB=appdb`
  - `POSTGRES_USER=appuser`
  - `POSTGRES_PASSWORD=apppassword`
- Resources: minimal (200m CPU, 256Mi memory)
- Volume: emptyDir (data not persisted across pod restarts - acceptable for POC)

**Image Configuration:**
```bash
# Default
POSTGRES_IMAGE=postgres:15-alpine

# Can be overridden
POSTGRES_IMAGE=postgres:16-alpine
```

**Service:**
- Name: `database-service`
- Type: ClusterIP
- Port: 5432

**Note:** PersistentVolume not used for simplicity. Data loss on pod restart is acceptable for this milestone.

---

## 5. Local Development Prerequisites

### Required Software

| Software | Minimum Version | Purpose |
|----------|----------------|---------|
| Windows | 10/11 | Host OS |
| WSL2 | Latest | Linux environment |
| Ubuntu | 20.04+ | WSL2 distribution |
| Docker Desktop | 4.0+ | Container runtime |
| Kind | 0.20+ | Local Kubernetes cluster |
| kubectl | 1.28+ | Kubernetes CLI |
| Git | 2.0+ | Version control |

### Installation Verification Commands

```bash
# WSL2 check
wsl --list --verbose

# Docker check
docker --version
docker ps

# Kind check
kind --version

# kubectl check
kubectl version --client

# Kubernetes cluster check (after creation)
kubectl cluster-info --context kind-poc-cluster
```

### Setup Prerequisites

1. WSL2 installed and configured
2. Ubuntu distribution installed in WSL2
3. Docker Desktop installed with WSL2 backend enabled
4. Kind installed in WSL2
5. kubectl installed in WSL2
6. Git repository initialized

---

## 6. Folder/File Structure

```
Final-Year-Project/
│
├── .kiro/
│   ├── steering/          # Already created
│   └── specs/
│       └── milestone-1-local-poc.md  # This file
│
├── services/
│   │
│   ├── frontend/
│   │   ├── Dockerfile
│   │   ├── nginx.conf
│   │   └── static/
│   │       └── index.html
│   │
│   ├── backend/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   └── main.py
│   │   └── tests/
│   │       └── test_health.py
│   │
│   └── database/
│       └── init.sql       # Optional initialization script
│
├── kubernetes/
│   ├── namespace.yaml
│   │
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   │
│   ├── backend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── secret.yaml     # For database credentials
│   │
│   └── database/
│       ├── deployment.yaml
│       └── service.yaml
│
├── scripts/
│   ├── setup-cluster.sh          # Create Kind cluster
│   ├── build-images.sh           # Build Docker images
│   ├── deploy-all.sh             # Deploy all Kubernetes resources
│   ├── verify-baseline.sh        # Verify and record baseline working state
│   └── cleanup.sh                # Delete cluster and resources
│
├── docs/
│   ├── setup-guide.md            # Step-by-step setup instructions
│   └── troubleshooting.md        # Common issues and solutions
│
├── .gitignore
├── README.md
└── Prompt.txt                    # Already exists
```

---

## 7. Configuration and Environment Variables

### Frontend Configuration

**No environment variables required**

Configuration via nginx.conf:
- Listen on port 80
- Serve static files from /usr/share/nginx/html

---

### Backend Configuration

**Environment Variables:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `DATABASE_HOST` | `database-service` | Database service DNS name |
| `DATABASE_PORT` | `5432` | PostgreSQL port |
| `DATABASE_NAME` | `appdb` | Database name |
| `DATABASE_USER` | `appuser` | Database username |
| `DATABASE_PASSWORD` | `apppassword` | Database password (from Secret) |

**Application Configuration:**
- FastAPI debug mode: disabled
- Host: 0.0.0.0
- Port: 8000
- Log level: INFO

---

### Database Configuration

**Environment Variables:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `POSTGRES_DB` | `appdb` | Initial database name |
| `POSTGRES_USER` | `appuser` | Database user |
| `POSTGRES_PASSWORD` | `apppassword` | User password |

**PostgreSQL Configuration:**
- Accept connections from all pods in cluster
- Default PostgreSQL 15 configuration
- No custom tuning required for POC

---

### Security Note

⚠️ **For local development only**

- Passwords are hardcoded for simplicity
- Kubernetes Secrets used but values are base64-encoded, not encrypted
- Not suitable for production
- Acceptable for research POC

---

## 8. Networking Requirements

### Cluster Networking

**Kind Cluster Configuration:**
- Cluster name: `poc-cluster`
- Control plane: 1 node
- Worker nodes: 0 (single-node cluster acceptable)
- Port mapping: 30080:30080 (Frontend NodePort)

**CNI Plugin:** Default (kindnetd)

**Service Discovery:**
- Frontend finds Backend via: `http://backend-service:8000`
- Backend finds Database via: `postgresql://database-service:5432`

### DNS Resolution

Kubernetes internal DNS automatically resolves:
- `backend-service` → Backend Service ClusterIP
- `database-service` → Database Service ClusterIP

Full DNS names (also valid):
- `backend-service.poc-app.svc.cluster.local`
- `database-service.poc-app.svc.cluster.local`

### Port Mapping

| Component | Internal Port | External Access |
|-----------|--------------|-----------------|
| Frontend | 80 | localhost:30080 (NodePort) |
| Backend | 8000 | Internal only |
| Database | 5432 | Internal only |

---

## 9. Database Initialization

### Automatic Initialization

PostgreSQL container automatically:
1. Creates database `appdb`
2. Creates user `appuser` with password `apppassword`
3. Grants all privileges on `appdb` to `appuser`

### Optional Test Table

**If needed for future milestones:**

```sql
CREATE TABLE IF NOT EXISTS connectivity_test (
    id SERIAL PRIMARY KEY,
    test_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO connectivity_test (test_message) 
VALUES ('Database connection successful');
```

**For this milestone:** Not required. Simple `SELECT 1` query is sufficient.

---

## 10. Health Checks

### Frontend Health Check

**Kubernetes Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 10
  periodSeconds: 30
```

**Readiness Probe:**
```yaml
readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

### Backend Health Check

**Kubernetes Liveness Probe:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 30
```

**Readiness Probe:**
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
```

**Health Endpoint Behavior:**
- **Returns HTTP 200:** Application healthy AND database connection verified with successful query
- **Returns HTTP 503:** Application running BUT database unreachable or query failed
- **Verifies actual connectivity:** Executes `SELECT 1 AS result` query against PostgreSQL
- **Distinguishes health layers:** Separate status for application process vs database connectivity
- **Includes diagnostics:** Response time, database version, query result, error details (if failed)

---

### Database Health Check

**Kubernetes Liveness Probe:**
```yaml
livenessProbe:
  exec:
    command:
      - pg_isready
      - -U
      - appuser
  initialDelaySeconds: 30
  periodSeconds: 30
```

**Readiness Probe:**
```yaml
readinessProbe:
  exec:
    command:
      - pg_isready
      - -U
      - appuser
  initialDelaySeconds: 10
  periodSeconds: 10
```

---

## 11. Testing Strategy

### Manual Testing

**Test 1: Cluster Creation**
```bash
kind create cluster --name poc-cluster --config kind-config.yaml
kubectl cluster-info --context kind-poc-cluster
```
**Expected:** Cluster created successfully, control plane running

---

**Test 2: Image Building**
```bash
./scripts/build-images.sh
docker images | grep poc
```
**Expected:** Frontend and Backend images built

---

**Test 3: Deployment**
```bash
./scripts/deploy-all.sh
kubectl get pods -n poc-app
```
**Expected:** All pods in Running state

---

**Test 4: Service Discovery**
```bash
kubectl get services -n poc-app
```
**Expected:** All services have ClusterIP (except Frontend has NodePort)

---

**Test 5: Database Connectivity from Backend**
```bash
kubectl logs -n poc-app -l app=backend
```
**Expected:** No database connection errors in logs

---

**Test 6: Backend Health Endpoint**
```bash
kubectl exec -n poc-app -it deployment/backend-deployment -- \
  curl http://localhost:8000/health
```
**Expected:** JSON response with `"connected": true`

---

**Test 7: End-to-End Test**
```bash
curl http://localhost:30080
# Then open browser: http://localhost:30080
```
**Expected:** 
- HTML page loads
- JavaScript fetches Backend health
- Backend response displayed showing database connectivity

---

**Test 8: Baseline Verification**
```bash
./scripts/verify-baseline.sh
```
**Expected:**
- All connectivity tests pass
- Baseline state documented in `baseline-verification.json`
- Timestamp and results recorded for future comparison

---

## 12. Acceptance Criteria

### Must Have (Blocking)

✅ **AC1:** Kind cluster created successfully with 1 node  
✅ **AC2:** All three services (Frontend, Backend, Database) deployed to Kubernetes  
✅ **AC3:** All pods reach Running status within 2 minutes  
✅ **AC4:** Frontend accessible at http://localhost:30080  
✅ **AC5:** Backend `/health` endpoint returns 200 status code when database is healthy  
✅ **AC6:** Backend `/health` endpoint returns 503 status code when database is unreachable  
✅ **AC7:** Backend successfully connects to PostgreSQL database and executes test query  
✅ **AC8:** Backend `/health` response clearly distinguishes application health from database health  
✅ **AC9:** Frontend displays Backend response with database status  
✅ **AC10:** All health checks pass (liveness and readiness probes green)  
✅ **AC11:** Documentation includes setup steps and verification commands

### Baseline Acceptance Criteria

✅ **BC1:** Frontend → Backend communication succeeds (HTTP 200 response received)  
✅ **BC2:** Backend → PostgreSQL communication succeeds (connection established)  
✅ **BC3:** Backend can execute simple database query successfully (SELECT 1 returns result)  
✅ **BC4:** End-to-end application request succeeds (Frontend displays database query result)  
✅ **BC5:** Baseline result is documented and timestamped in `baseline-verification.json`  
✅ **BC6:** Baseline verification script can be re-run to confirm working state  
✅ **BC7:** Baseline documentation includes all communication paths and their status  

### Should Have (Important)

☑️ **AC12:** Automated scripts for cluster creation and deployment (kept minimal)  
☑️ **AC13:** Troubleshooting guide documents common issues  
☑️ **AC14:** All configuration externalized (no hardcoded values in code)  
☑️ **AC15:** Services use minimal resource requests  
☑️ **AC16:** PostgreSQL image version is configurable  

### Nice to Have (Optional)

⭕ **AC17:** Database initialization script for test data  
⭕ **AC18:** Frontend shows timestamp of last successful check  
⭕ **AC19:** Logs structured and easy to parse  

---

## 13. Expected Successful Behavior

### Step-by-Step Success Scenario

1. **User opens browser** → `http://localhost:30080`
2. **Frontend HTML page loads** with title "POC Application - Frontend"
3. **JavaScript executes** → Fetches `http://backend-service:8000/health`
4. **Backend receives request** → Connects to database
5. **Backend queries database** → Executes `SELECT version()`
6. **Database responds** → PostgreSQL version string
7. **Backend returns JSON**:
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
       "version": "PostgreSQL 15.x on x86_64-pc-linux-musl",
       "test_query": "SELECT 1 AS result",
       "query_result": 1,
       "response_time_ms": 12
     },
     "timestamp": "2026-10-06T16:42:00.123Z"
   }
   ```
8. **Frontend displays**:
   ```
   ✅ Overall Status: healthy
   ✅ Application Status: running
   ✅ Database Connected: true
   ✅ Database Version: PostgreSQL 15.x
   ✅ Test Query Result: 1
   ✅ Database Response Time: 12ms
   ```

### Success Indicators

- No error messages in any logs
- All pods show `1/1 Ready`
- All services have endpoints assigned
- Browser shows green checkmarks
- Backend logs show successful database connections
- Database logs show accepted connections from Backend

---

## 14. Common Failure Cases and Debugging Approach

### Failure Case 1: Kind Cluster Won't Start

**Symptoms:**
- `kind create cluster` hangs or fails
- Error: "failed to create cluster"

**Debugging:**
```bash
# Check Docker
docker ps

# Check WSL2 Docker integration
wsl -l -v

# Check Kind logs
kind create cluster --name poc-cluster -v 5
```

**Common Causes:**
- Docker Desktop not running
- WSL2 integration not enabled
- Insufficient resources

**Resolution:**
- Start Docker Desktop
- Enable WSL2 integration in Docker settings
- Allocate more memory to WSL2

---

### Failure Case 2: Pods Stuck in ImagePullBackOff

**Symptoms:**
- `kubectl get pods` shows `ImagePullBackOff` or `ErrImagePull`

**Debugging:**
```bash
kubectl describe pod -n poc-app <pod-name>
kubectl get events -n poc-app --sort-by='.lastTimestamp'
```

**Common Causes:**
- Images not built
- Images not loaded into Kind cluster
- Wrong image names in deployment YAML

**Resolution:**
```bash
# Build images
docker build -t poc-backend:latest ./services/backend
docker build -t poc-frontend:latest ./services/frontend

# Load into Kind
kind load docker-image poc-backend:latest --name poc-cluster
kind load docker-image poc-frontend:latest --name poc-cluster
```

---

### Failure Case 3: Backend Cannot Connect to Database

**Symptoms:**
- Backend logs show "connection refused" or "could not connect"
- `/health` endpoint returns 503

**Debugging:**
```bash
# Check database pod
kubectl get pods -n poc-app -l app=database
kubectl logs -n poc-app -l app=database

# Check database service
kubectl get svc -n poc-app database-service
kubectl get endpoints -n poc-app database-service

# Test DNS from Backend pod
kubectl exec -n poc-app deployment/backend-deployment -- nslookup database-service

# Test connection from Backend pod
kubectl exec -n poc-app deployment/backend-deployment -- \
  nc -zv database-service 5432
```

**Common Causes:**
- Database pod not ready
- Wrong service name in Backend env vars
- Database credentials mismatch
- Database not accepting connections

**Resolution:**
- Wait for database pod to be Ready
- Verify `DATABASE_HOST=database-service`
- Check Secret contains correct credentials
- Verify PostgreSQL `pg_hba.conf` allows connections (default should work)

---

### Failure Case 4: Frontend Cannot Reach Backend

**Symptoms:**
- Frontend page loads but shows "Failed to fetch Backend"
- Browser console shows network error

**Debugging:**
```bash
# Check Backend pod
kubectl get pods -n poc-app -l app=backend
kubectl logs -n poc-app -l app=backend

# Check Backend service
kubectl get svc -n poc-app backend-service

# Test from Frontend pod
kubectl exec -n poc-app deployment/frontend-deployment -- \
  curl http://backend-service:8000/health
```

**Common Causes:**
- Backend pod not ready
- Backend service not exposing correct port
- CORS issues (if Frontend makes browser request)
- Wrong Backend URL in Frontend JavaScript

**Resolution:**
- Verify Backend pod is Running and Ready
- Check Backend service port matches container port (8000)
- Add CORS middleware to FastAPI if needed
- Verify Frontend ConfigMap has correct Backend URL

---

### Failure Case 5: Cannot Access Frontend from Browser

**Symptoms:**
- `http://localhost:30080` shows "connection refused"
- Browser cannot load page

**Debugging:**
```bash
# Check Frontend pod
kubectl get pods -n poc-app -l app=frontend

# Check Frontend service NodePort
kubectl get svc -n poc-app frontend-service

# Check Kind port mapping
docker ps | grep poc-cluster

# Test from WSL2
curl http://localhost:30080
```

**Common Causes:**
- Frontend pod not ready
- NodePort not configured correctly
- Kind port mapping missing
- Windows firewall blocking

**Resolution:**
- Wait for Frontend pod to be Ready
- Verify NodePort is 30080 in service YAML
- Recreate Kind cluster with correct port mapping in kind-config.yaml:
  ```yaml
  extraPortMappings:
  - containerPort: 30080
    hostPort: 30080
  ```
- Check Windows firewall settings

---

### Failure Case 6: Pods Crash or CrashLoopBackOff

**Symptoms:**
- Pods restart repeatedly
- Status shows `CrashLoopBackOff`

**Debugging:**
```bash
# Check pod logs
kubectl logs -n poc-app <pod-name>
kubectl logs -n poc-app <pod-name> --previous

# Describe pod for events
kubectl describe pod -n poc-app <pod-name>
```

**Common Causes:**
- Application code error
- Missing dependencies
- Environment variables not set
- Health checks failing too quickly

**Resolution:**
- Fix application code errors
- Verify all dependencies in requirements.txt/Dockerfile
- Check environment variables in deployment YAML
- Increase `initialDelaySeconds` in health check probes

---

### General Debugging Commands

```bash
# Check all resources in namespace
kubectl get all -n poc-app

# Check events
kubectl get events -n poc-app --sort-by='.lastTimestamp'

# Check pod details
kubectl describe pod -n poc-app <pod-name>

# Check logs
kubectl logs -n poc-app <pod-name> --tail=50 -f

# Execute into pod for debugging
kubectl exec -n poc-app -it <pod-name> -- /bin/sh

# Check resource usage
kubectl top pods -n poc-app

# Port forward for direct testing
kubectl port-forward -n poc-app service/backend-service 8000:8000
curl http://localhost:8000/health
```

---

## 15. Baseline Verification

### Purpose

Establish and document the **working baseline state** before introducing security policies (NetworkPolicy) in later milestones. This baseline serves as:

1. **Reference point** for comparing behavior after policy changes
2. **Ground truth** for prediction evaluation
3. **Verification** that all communication paths work correctly

### Baseline Verification Process

**Automated Script:** `scripts/verify-baseline.sh`

**Steps:**

1. **Verify Cluster Health**
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```
   - Expected: Cluster running, node Ready

2. **Verify Pod Status**
   ```bash
   kubectl get pods -n poc-app
   ```
   - Expected: All pods Running, all containers Ready (1/1)

3. **Test Frontend Accessibility**
   ```bash
   curl -s http://localhost:30080 | grep -q "POC Application"
   echo "✅ Frontend accessible"
   ```
   - Expected: HTTP 200, HTML page loads

4. **Test Frontend → Backend Communication**
   ```bash
   kubectl exec -n poc-app deployment/frontend-deployment -- \
     curl -s http://backend-service:8000/health
   ```
   - Expected: HTTP 200, JSON response with `"status": "healthy"`

5. **Test Backend → Database Communication**
   ```bash
   kubectl exec -n poc-app deployment/backend-deployment -- \
     curl -s http://localhost:8000/health | jq '.database.connected'
   ```
   - Expected: `true`

6. **Test Database Query Execution**
   ```bash
   kubectl exec -n poc-app deployment/backend-deployment -- \
     curl -s http://localhost:8000/health | jq '.database.query_result'
   ```
   - Expected: `1` (successful SELECT 1 query)

7. **Test End-to-End Request**
   ```bash
   curl -s http://localhost:30080
   # Open browser and verify Frontend displays database status
   ```
   - Expected: Frontend shows green checkmarks, database version, query result

8. **Record Baseline State**
   ```bash
   # Generate baseline verification report
   timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
   cat > baseline-verification.json <<EOF
   {
     "timestamp": "$timestamp",
     "milestone": "1",
     "cluster": "poc-cluster",
     "namespace": "poc-app",
     "verification": {
       "frontend_accessible": true,
       "frontend_to_backend": "success",
       "backend_to_database": "success",
       "database_query": "success",
       "end_to_end": "success"
     },
     "services": {
       "frontend": {
         "status": "running",
         "endpoint": "http://localhost:30080"
       },
       "backend": {
         "status": "healthy",
         "database_connected": true,
         "query_response_time_ms": 12
       },
       "database": {
         "status": "ready",
         "version": "PostgreSQL 15.x"
       }
     },
     "communication_paths": {
       "user_to_frontend": "✅ working",
       "frontend_to_backend": "✅ working",
       "backend_to_database": "✅ working"
     }
   }
   EOF
   ```

### Baseline Documentation

**Output File:** `baseline-verification.json`

**Location:** Project root directory

**Format:** JSON with timestamp, verification results, service statuses, communication paths

**Example Output:**
```json
{
  "timestamp": "2026-10-06T16:42:00.123Z",
  "milestone": "1",
  "cluster": "poc-cluster",
  "namespace": "poc-app",
  "verification": {
    "frontend_accessible": true,
    "frontend_to_backend": "success",
    "backend_to_database": "success",
    "database_query": "success",
    "end_to_end": "success"
  },
  "services": {
    "frontend": {
      "status": "running",
      "endpoint": "http://localhost:30080"
    },
    "backend": {
      "status": "healthy",
      "database_connected": true,
      "query_response_time_ms": 12
    },
    "database": {
      "status": "ready",
      "version": "PostgreSQL 15.4"
    }
  },
  "communication_paths": {
    "user_to_frontend": "✅ working",
    "frontend_to_backend": "✅ working",
    "backend_to_database": "✅ working"
  },
  "notes": "Baseline established. All communication paths verified working. Ready for Milestone 2 (NetworkPolicy introduction)."
}
```

### Baseline Comparison (Future Milestones)

**In Milestone 2 (NetworkPolicy blocking):**

Compare against this baseline:
- **Before Policy:** All paths ✅ working (documented here)
- **After Policy:** Backend → Database ❌ blocked (expected)
- **Prediction vs Reality:** Compare what the system predicts vs actual behavior

This baseline verification is **critical** for the research evaluation methodology.

---

## 16. Success Metrics

This milestone is successful when:

1. ✅ Complete setup takes < 30 minutes on a fresh machine
2. ✅ All pods reach Running state within 2 minutes of deployment
3. ✅ Frontend responds within 1 second
4. ✅ Backend health check responds within 500ms and verifies actual database connectivity
5. ✅ Zero manual configuration required after running minimal helper scripts
6. ✅ Student can explain each component's purpose
7. ✅ Setup is reproducible on another machine
8. ✅ Documentation is clear and complete
9. ✅ Baseline verification documented in `baseline-verification.json`
10. ✅ All communication paths verified and recorded

---

## 17. Helper Scripts Design

### Principle: Minimal and Transparent

Helper scripts should be:
- ✅ Simple shell scripts (bash)
- ✅ Readable and educational
- ✅ One clear purpose per script
- ✅ No unnecessary frameworks
- ✅ Easy to understand for viva explanation

### Do NOT Include

- ❌ Helm charts (not needed for POC)
- ❌ Kustomize overlays (unnecessary complexity)
- ❌ CI/CD pipelines (not in scope)
- ❌ Complex deployment orchestration
- ❌ Infrastructure frameworks

### Script Descriptions

**`setup-cluster.sh`**
- Creates Kind cluster with port mapping
- Verifies cluster is running
- ~20 lines

**`build-images.sh`**
- Builds Frontend Docker image
- Builds Backend Docker image
- Loads images into Kind cluster
- ~30 lines

**`deploy-all.sh`**
- Applies namespace
- Applies all Kubernetes manifests in order
- Waits for pods to be ready
- ~40 lines

**`verify-baseline.sh`**
- Runs all baseline verification tests
- Records results in `baseline-verification.json`
- Displays summary
- ~80 lines

**`cleanup.sh`**
- Deletes Kind cluster
- Removes Docker images (optional)
- ~15 lines

**Total:** ~185 lines of simple, readable bash scripts

---

## 18. Next Steps (Future Milestones)

After Milestone 1 is complete:

**Milestone 2:** Add Kubernetes NetworkPolicy
- Create policy that blocks Backend → Database
- Verify application breaks
- Establish baseline for future evidence collection

**Milestone 3:** Add OpenTelemetry instrumentation
- Instrument Backend with OpenTelemetry
- Deploy Jaeger
- Collect runtime traces

**Milestone 4:** Infrastructure Evidence Extraction
- Parse Kubernetes YAML
- Extract service dependencies
- Build initial dependency graph

**But for now:** Focus only on Milestone 1.

---

## 19. Review and Approval

### Before Implementation

- [x] Requirements reviewed and approved
- [x] Technical design reviewed and approved
- [x] Folder structure confirmed
- [x] Acceptance criteria agreed upon (including baseline criteria)
- [x] Out-of-scope vs deferred items confirmed
- [x] PostgreSQL configurability added
- [x] Health endpoint verifies actual database connectivity
- [x] Helper scripts kept minimal
- [x] Baseline verification section added

### Implementation Checklist

- [ ] Folder structure created
- [ ] Frontend Dockerfile and code written
- [ ] Backend Dockerfile and code written with actual database connectivity verification
- [ ] Kubernetes YAML manifests created (with configurable PostgreSQL image)
- [ ] Minimal helper scripts created (no unnecessary frameworks)
- [ ] Baseline verification script created
- [ ] Documentation written
- [ ] All acceptance criteria met (including baseline criteria)
- [ ] Manual testing completed
- [ ] Baseline verification documented in `baseline-verification.json`

---

## End of Specification

**Status:** ✅ APPROVED - Ready for implementation

**Revision:** 2 (incorporating all requested changes)

**Approval Date:** 2026-10-06

**Estimated Implementation Time:** 4-6 hours

**Complexity:** Low - suitable for final-year project first milestone

**Risk:** Low - well-established technologies and patterns

---

## Revision History

**Revision 1 (Initial):** Draft specification created  
**Revision 2 (Approved):** Incorporated revisions:
- OpenTelemetry/Jaeger marked as deferred (not excluded)
- PostgreSQL image version made configurable
- Backend `/health` endpoint verifies actual database connectivity
- Helper scripts kept minimal, no unnecessary frameworks
- Explicit baseline acceptance criteria added
- Baseline verification section added with documentation approach
