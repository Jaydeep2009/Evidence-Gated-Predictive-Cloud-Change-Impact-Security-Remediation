# Milestone 1 Testing Checklist

This document provides a comprehensive testing checklist to verify Milestone 1 implementation.

## Pre-Deployment Tests

### ✅ File Structure Verification

```bash
cd /mnt/c/Users/sai/Desktop/Final-Year-Project

# Check directory structure
tree -L 3

# Expected structure:
# .
# ├── .kiro/
# │   ├── specs/
# │   └── steering/
# ├── services/
# │   ├── frontend/
# │   ├── backend/
# │   └── database/
# ├── kubernetes/
# │   ├── frontend/
# │   ├── backend/
# │   └── database/
# ├── scripts/
# └── docs/
```

### ✅ Backend Code Verification

```bash
# Check Backend main.py exists
test -f services/backend/app/main.py && echo "✅ Backend main.py exists" || echo "❌ Missing"

# Check requirements.txt
test -f services/backend/requirements.txt && echo "✅ requirements.txt exists" || echo "❌ Missing"

# Check Dockerfile
test -f services/backend/Dockerfile && echo "✅ Backend Dockerfile exists" || echo "❌ Missing"
```

### ✅ Frontend Code Verification

```bash
# Check Frontend index.html
test -f services/frontend/static/index.html && echo "✅ Frontend index.html exists" || echo "❌ Missing"

# Check nginx.conf
test -f services/frontend/nginx.conf && echo "✅ nginx.conf exists" || echo "❌ Missing"

# Check Dockerfile
test -f services/frontend/Dockerfile && echo "✅ Frontend Dockerfile exists" || echo "❌ Missing"
```

### ✅ Kubernetes Manifests Verification

```bash
# Check all manifests exist
for file in namespace.yaml \
            frontend/deployment.yaml frontend/service.yaml \
            backend/deployment.yaml backend/service.yaml \
            database/deployment.yaml database/service.yaml; do
    test -f kubernetes/$file && echo "✅ $file exists" || echo "❌ Missing: $file"
done
```

### ✅ Scripts Verification

```bash
# Check all scripts exist and are executable
for script in setup-cluster.sh build-images.sh deploy-all.sh verify-baseline.sh cleanup.sh; do
    if [ -x scripts/$script ]; then
        echo "✅ $script is executable"
    else
        echo "❌ $script missing or not executable"
    fi
done
```

---

## Deployment Tests

### Test 1: Cluster Creation

```bash
./scripts/setup-cluster.sh
```

**Expected Output:**
- ✅ Creating cluster "poc-cluster"
- ✅ Cluster configuration applied
- ✅ Control plane node ready

**Verification:**
```bash
kind get clusters
# Should show: poc-cluster

kubectl cluster-info --context kind-poc-cluster
# Should show: Kubernetes control plane is running
```

**Acceptance Criteria:**
- [ ] Cluster named "poc-cluster" exists
- [ ] Cluster control plane is running
- [ ] kubectl can communicate with cluster

---

### Test 2: Image Building

```bash
./scripts/build-images.sh
```

**Expected Output:**
- ✅ Building Backend image
- ✅ Building Frontend image  
- ✅ Loading Backend image into Kind
- ✅ Loading Frontend image into Kind

**Verification:**
```bash
docker images | grep poc

# Should show:
# poc-backend     latest    [IMAGE_ID]    [TIME]    [SIZE]
# poc-frontend    latest    [IMAGE_ID]    [TIME]    [SIZE]

# Verify images in Kind
docker exec -it poc-cluster-control-plane crictl images | grep poc
```

**Acceptance Criteria:**
- [ ] poc-backend:latest image exists
- [ ] poc-frontend:latest image exists
- [ ] Both images loaded into Kind cluster

---

### Test 3: Application Deployment

```bash
./scripts/deploy-all.sh
```

**Expected Output:**
- ✅ Namespace created
- ✅ Database deployed
- ✅ Backend deployed
- ✅ Frontend deployed
- ✅ All pods ready within 2 minutes

**Verification:**
```bash
# Check namespace
kubectl get ns poc-app
# Should show: poc-app   Active

# Check all resources
kubectl get all -n poc-app

# Check pod status
kubectl get pods -n poc-app

# Expected:
# NAME                                   READY   STATUS    RESTARTS   AGE
# backend-deployment-xxxxx               1/1     Running   0          1m
# database-deployment-xxxxx              1/1     Running   0          1m
# frontend-deployment-xxxxx              1/1     Running   0          1m
```

**Acceptance Criteria:**
- [ ] Namespace poc-app exists
- [ ] All 3 pods Running
- [ ] All pods show READY 1/1
- [ ] No pods in CrashLoopBackOff or Error state

---

### Test 4: Service Verification

```bash
kubectl get svc -n poc-app
```

**Expected Output:**
```
NAME               TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
backend-service    ClusterIP   10.96.xxx.xxx   <none>        8000/TCP       2m
database-service   ClusterIP   10.96.xxx.xxx   <none>        5432/TCP       2m
frontend-service   NodePort    10.96.xxx.xxx   <none>        80:30080/TCP   2m
```

**Verification:**
```bash
# Check services have endpoints
kubectl get endpoints -n poc-app

# All services should have IP:PORT listed
```

**Acceptance Criteria:**
- [ ] frontend-service is NodePort type
- [ ] frontend-service NodePort is 30080
- [ ] backend-service is ClusterIP type
- [ ] database-service is ClusterIP type
- [ ] All services have endpoints assigned

---

### Test 5: Frontend Accessibility

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:30080
# Should return: 200

curl -s http://localhost:30080 | grep "POC Application"
# Should match HTML title
```

**Browser Test:**
1. Open: http://localhost:30080
2. Page should load without errors

**Acceptance Criteria:**
- [ ] HTTP 200 response from localhost:30080
- [ ] HTML page loads in browser
- [ ] No JavaScript errors in browser console

---

### Test 6: Backend Health Endpoint

```bash
# Test from outside cluster (via frontend)
curl -s http://localhost:30080 | grep "healthy"

# Test from within cluster
kubectl exec -n poc-app deployment/backend-deployment -- \
    curl -s http://localhost:8000/health | jq '.'
```

**Expected Response:**
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
    "version": "PostgreSQL 15.x ...",
    "test_query": "SELECT 1 AS result",
    "query_result": 1,
    "response_time_ms": 10-50
  },
  "timestamp": "2026-10-06T..."
}
```

**Acceptance Criteria:**
- [ ] HTTP 200 status code
- [ ] "status": "healthy"
- [ ] "application.status": "running"
- [ ] "database.connected": true
- [ ] "database.query_result": 1

---

### Test 7: Frontend → Backend Communication

```bash
FRONTEND_POD=$(kubectl get pod -n poc-app -l app=frontend -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n poc-app ${FRONTEND_POD} -- \
    wget -q -O- http://backend-service:8000/health | grep "healthy"
```

**Expected Output:**
- Should contain: "status":"healthy"

**Acceptance Criteria:**
- [ ] Frontend pod can resolve backend-service DNS name
- [ ] Frontend pod can connect to backend-service:8000
- [ ] Backend returns healthy response

---

### Test 8: Backend → Database Communication

```bash
BACKEND_POD=$(kubectl get pod -n poc-app -l app=backend -o jsonpath='{.items[0].metadata.name}')

# Check database connectivity from backend
kubectl exec -n poc-app ${BACKEND_POD} -- \
    wget -q -O- http://localhost:8000/health | grep '"connected": true'

# Direct database test
kubectl exec -n poc-app ${BACKEND_POD} -- \
    nc -zv database-service 5432
```

**Expected Output:**
- Health check shows: "connected": true
- nc test shows: Connection to database-service 5432 port [tcp/postgresql] succeeded!

**Acceptance Criteria:**
- [ ] Backend can resolve database-service DNS name
- [ ] Backend can connect to database-service:5432
- [ ] Backend can execute SQL query (SELECT 1)
- [ ] Query returns result: 1

---

### Test 9: Database Query Execution

```bash
# From backend health endpoint
kubectl exec -n poc-app deployment/backend-deployment -- \
    curl -s http://localhost:8000/health | jq '.database'
```

**Expected Output:**
```json
{
  "connected": true,
  "version": "PostgreSQL 15.x on x86_64-pc-linux-musl, compiled by gcc ...",
  "test_query": "SELECT 1 AS result",
  "query_result": 1,
  "response_time_ms": 12.34
}
```

**Acceptance Criteria:**
- [ ] query_result equals 1
- [ ] version contains "PostgreSQL 15"
- [ ] response_time_ms is a number < 1000

---

### Test 10: Health Probes

```bash
# Check liveness and readiness probe status
kubectl get pods -n poc-app -o wide

# Describe pods to see probe results
kubectl describe pod -n poc-app -l app=backend | grep -A 5 "Liveness\|Readiness"
kubectl describe pod -n poc-app -l app=frontend | grep -A 5 "Liveness\|Readiness"
kubectl describe pod -n poc-app -l app=database | grep -A 5 "Liveness\|Readiness"
```

**Expected Output:**
- All probes should show "... delay=Xs timeout=Xs ..." (no failures)

**Acceptance Criteria:**
- [ ] Backend liveness probe succeeding
- [ ] Backend readiness probe succeeding
- [ ] Frontend liveness probe succeeding
- [ ] Frontend readiness probe succeeding
- [ ] Database liveness probe succeeding
- [ ] Database readiness probe succeeding

---

### Test 11: End-to-End Request

```bash
# Complete end-to-end test
curl -s http://localhost:30080 | grep -o "Database Connected.*true"

# Browser test
echo "Open http://localhost:30080 in browser"
echo "Expected: Green checkmarks for all statuses"
```

**Browser Verification:**
1. Overall Status: healthy ✅
2. Application Status: running ✅
3. Database Connected: true ✅
4. Database Version: PostgreSQL 15.x ✅
5. Test Query Result: 1 ✅
6. Response Time: [number] ms ✅

**Acceptance Criteria:**
- [ ] Frontend page loads successfully
- [ ] Frontend displays backend response
- [ ] All status indicators show success (green)
- [ ] Database query result displayed correctly

---

### Test 12: Baseline Verification

```bash
./scripts/verify-baseline.sh
```

**Expected Output:**
```
=========================================
Baseline Verification
=========================================

1. Verifying cluster health...
   ✅ Cluster is running

2. Verifying pod status...
   ✅ All pods are running

3. Testing Frontend accessibility...
   ✅ Frontend accessible at http://localhost:30080

4. Testing Frontend → Backend communication...
   ✅ Frontend can reach Backend

5. Testing Backend → Database communication...
   ✅ Backend can reach Database

6. Testing database query execution...
   ✅ Database query executed successfully

7. Testing end-to-end request...
   ✅ End-to-end request successful

=========================================
Recording Baseline State
=========================================

Baseline verification saved to: baseline-verification.json

{
  "timestamp": "2026-10-06T...",
  "milestone": "1",
  ...
  "communication_paths": {
    "user_to_frontend": "✅ working",
    "frontend_to_backend": "✅ working",
    "backend_to_database": "✅ working"
  }
}

=========================================
Baseline Verification Complete!
=========================================
```

**Verification:**
```bash
# Check baseline file exists
test -f baseline-verification.json && echo "✅ Baseline file created" || echo "❌ File missing"

# View baseline
cat baseline-verification.json | jq '.'
```

**Acceptance Criteria:**
- [ ] baseline-verification.json file created
- [ ] All verification checks passed
- [ ] All communication paths marked as "working"
- [ ] File contains timestamp and service status
- [ ] JSON is valid and parseable

---

## Log Verification

```bash
# Check logs have no errors
echo "=== Frontend Logs ===" && kubectl logs -n poc-app -l app=frontend --tail=20
echo "=== Backend Logs ===" && kubectl logs -n poc-app -l app=backend --tail=20
echo "=== Database Logs ===" && kubectl logs -n poc-app -l app=database --tail=20
```

**Look for:**
- ❌ No error messages
- ❌ No connection refused messages
- ❌ No authentication failures
- ✅ Backend should show successful database connections
- ✅ Database should show accepted connections

---

## Final Acceptance Checklist

### Must Have (Blocking) - All must pass ✅

- [ ] **AC1:** Kind cluster created successfully
- [ ] **AC2:** All three services deployed
- [ ] **AC3:** All pods Running within 2 minutes
- [ ] **AC4:** Frontend accessible at http://localhost:30080
- [ ] **AC5:** Backend /health returns HTTP 200
- [ ] **AC6:** Backend /health returns HTTP 503 when DB unavailable (testable by stopping DB pod)
- [ ] **AC7:** Backend successfully connects to PostgreSQL
- [ ] **AC8:** Backend /health response distinguishes app vs DB health
- [ ] **AC9:** Frontend displays backend response
- [ ] **AC10:** All health checks passing
- [ ] **AC11:** Documentation complete

### Baseline Acceptance Criteria - All must pass ✅

- [ ] **BC1:** Frontend → Backend communication succeeds
- [ ] **BC2:** Backend → PostgreSQL communication succeeds
- [ ] **BC3:** Backend executes database query successfully
- [ ] **BC4:** End-to-end application request succeeds
- [ ] **BC5:** Baseline documented in baseline-verification.json
- [ ] **BC6:** Baseline verification script re-runnable
- [ ] **BC7:** All communication paths documented

---

## Troubleshooting Tests

### Test Backend Failure Scenario

```bash
# Stop database pod
kubectl delete pod -n poc-app -l app=database

# Immediately check backend health (should return 503)
kubectl exec -n poc-app deployment/backend-deployment -- \
    curl -s -w "\nHTTP Code: %{http_code}\n" http://localhost:8000/health

# Expected: HTTP Code: 503
# Expected: "status": "unhealthy", "database.connected": false

# Database pod should auto-recreate
kubectl get pods -n poc-app -l app=database --watch
```

---

## Success Criteria Summary

Milestone 1 is **COMPLETE** when:

✅ All 11 Must Have acceptance criteria passed  
✅ All 7 Baseline acceptance criteria passed  
✅ baseline-verification.json generated and valid  
✅ Application accessible in browser with all green checkmarks  
✅ All tests in this checklist passed  
✅ Student can explain each component's purpose  

**Next Step:** Ready for Milestone 2 (NetworkPolicy introduction)
