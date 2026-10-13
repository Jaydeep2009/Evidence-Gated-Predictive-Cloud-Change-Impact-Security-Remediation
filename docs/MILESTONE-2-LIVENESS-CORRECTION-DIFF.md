# Milestone 2: Liveness Correction - Exact Code Changes

## File 1: `services/backend/app/main.py`

### Location of Change

After the `/health` endpoint (ends around line ~133)  
Before the `/` root endpoint (starts around line ~136)

### Code to Add

```python
@app.get("/live")
async def liveness_check():
    """
    Liveness check endpoint - verifies application process is alive.
    
    Returns HTTP 200 if FastAPI application is responsive.
    Does NOT check database or external dependencies.
    
    Used by Kubernetes liveness probe to determine if container should be restarted.
    """
    return {
        "status": "alive",
        "application": {
            "name": "poc-backend",
            "version": "1.0.0"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


```

### Context (Where to Insert)

```python
# ... existing /health endpoint ends here ...
    return {
        "status": overall_status,
        "application": application_status,
        "database": database_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# INSERT NEW /live ENDPOINT HERE


@app.get("/")
async def root():
    """Root endpoint - simple service identification"""
# ... rest of file continues ...
```

---

## File 2: `kubernetes/backend/deployment.yaml`

### Current Code (Lines 48-54)

```yaml
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 30
          timeoutSeconds: 5
```

### Changed Code

```yaml
        livenessProbe:
          httpGet:
            path: /live
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 30
          timeoutSeconds: 5
```

### Readiness Probe (UNCHANGED)

```yaml
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
```

---

## Complete Modified Sections

### services/backend/app/main.py (Lines ~133-155)

```python
@app.get("/health")
async def health_check(response: Response):
    """
    Health check endpoint that verifies both application and database health.
    
    Returns HTTP 200 only when BOTH application AND database are healthy.
    Returns HTTP 503 when database is unreachable.
    
    This endpoint is used by:
    - Kubernetes readiness probes
    - Frontend to display system status
    - Baseline verification script
    """
    # Check application health (if we're here, FastAPI is running)
    application_status = {
        "name": "poc-backend",
        "version": "1.0.0",
        "status": "running"
    }
    
    # Check database connectivity (actual query execution)
    database_status = check_database_connectivity()
    
    # Determine overall health status
    if database_status["connected"]:
        overall_status = "healthy"
        response.status_code = status.HTTP_200_OK
    else:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {
        "status": overall_status,
        "application": application_status,
        "database": database_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/live")
async def liveness_check():
    """
    Liveness check endpoint - verifies application process is alive.
    
    Returns HTTP 200 if FastAPI application is responsive.
    Does NOT check database or external dependencies.
    
    Used by Kubernetes liveness probe to determine if container should be restarted.
    """
    return {
        "status": "alive",
        "application": {
            "name": "poc-backend",
            "version": "1.0.0"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint - simple service identification"""
    return {
        "service": "poc-backend",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs"
        }
    }
```

---

### kubernetes/backend/deployment.yaml (Lines ~40-62)

```yaml
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /live
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 30
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
```

---

## Testing the Changes

### Test 1: Verify `/live` endpoint works

```bash
# After building image and deploying
kubectl exec -n poc-app $(kubectl get pod -n poc-app -l app=backend -o jsonpath='{.items[0].metadata.name}') -- \
  curl -s http://localhost:8000/live
```

**Expected output:**
```json
{
  "status": "alive",
  "application": {
    "name": "poc-backend",
    "version": "1.0.0"
  },
  "timestamp": "2026-10-07T..."
}
```

### Test 2: Verify `/health` still checks database

```bash
# Without NetworkPolicy
kubectl exec -n poc-app $(kubectl get pod -n poc-app -l app=backend -o jsonpath='{.items[0].metadata.name}') -- \
  curl -s http://localhost:8000/health
```

**Expected output (baseline):**
```json
{
  "status": "healthy",
  "application": {...},
  "database": {
    "connected": true,
    ...
  }
}
```

### Test 3: Verify liveness probe uses `/live`

```bash
kubectl describe pod -n poc-app -l app=backend | grep -A 3 "Liveness"
```

**Expected output:**
```
    Liveness:   http-get http://:8000/live delay=15s timeout=5s period=30s
```

### Test 4: Verify readiness probe still uses `/health`

```bash
kubectl describe pod -n poc-app -l app=backend | grep -A 3 "Readiness"
```

**Expected output:**
```
    Readiness:  http-get http://:8000/health delay=10s timeout=5s period=10s
```

---

## Validation Checklist

After implementing changes:

- [ ] Backend image rebuilt successfully
- [ ] Image loaded into Kind cluster
- [ ] Deployment applied successfully
- [ ] Pod started and Running
- [ ] `/live` returns HTTP 200
- [ ] `/health` returns HTTP 200 (baseline)
- [ ] Liveness probe shows path `/live`
- [ ] Readiness probe shows path `/health`
- [ ] Baseline verification passes
- [ ] NetworkPolicy experiment can be run
- [ ] Backend pod remains stable during NetworkPolicy experiment

---

## End of Diff

**Files modified:** 2  
**Lines added:** 13 (main.py)  
**Lines changed:** 1 (deployment.yaml)  
**Total impact:** Minimal, targeted correction

---
