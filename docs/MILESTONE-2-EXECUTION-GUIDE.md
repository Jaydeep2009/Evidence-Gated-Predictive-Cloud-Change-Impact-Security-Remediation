# Milestone 2: Execution Guide

## Quick Start

### Prerequisites

1. Milestone 1 baseline verified and working
2. Kind cluster running (`kind-poc-cluster`)
3. All pods in `poc-app` namespace are Running
4. `baseline-verification.json` exists and shows all paths working

---

## Execution Steps

### Step 1: Apply NetworkPolicy

```bash
./scripts/apply-network-policy.sh
```

**Expected output:**
- ✅ Cluster running
- ✅ Policy applied: `isolate-database`
- Warning about expected operational impact

**Duration:** ~5 seconds (includes policy propagation wait)

---

### Step 2: Verify Impact

```bash
./scripts/verify-network-policy.sh
```

**Expected results:**
- ✅ Cluster running
- ✅ NetworkPolicy exists
- ✅ All pods Running (including PostgreSQL)
- ✅ Frontend accessible
- ✅ Frontend → Backend working
- ✅ Backend → PostgreSQL BLOCKED (expected)
- ✅ Backend health indicates failure (expected)
- ✅ Hypothesis CONFIRMED

**Output file:** `network-policy-verification.json`

**Duration:** ~30-60 seconds

---

### Step 3: Review Results

```bash
cat network-policy-verification.json
```

**Check these fields:**
- `observed_behavior` - Should match `expected_behavior`
- `hypothesis_confirmed` - Should be `true`
- `verification_results` - All should align with hypothesis

---

### Step 4: Test in Browser (Optional)

```bash
# Open browser to:
http://localhost:30080
```

**Expected:**
- Frontend loads
- Shows "Database Connected: false"
- Shows "Status: unhealthy"

---

### Step 5: Check Backend Logs (Optional)

```bash
kubectl logs -n poc-app -l app=backend --tail=20
```

**Expected:**
- Connection timeout or refused errors
- PostgreSQL OperationalError messages

---

### Step 6: Remove Policy

```bash
./scripts/remove-network-policy.sh
```

**Expected output:**
- ✅ NetworkPolicy deleted
- ✅ Backend → PostgreSQL connectivity restored
- ✅ Backend health: healthy

**Duration:** ~10 seconds (includes recovery wait)

---

### Step 7: Verify Baseline Restored

```bash
./scripts/verify-baseline.sh
```

**Expected:**
- All checks pass
- Database connectivity working
- Matches original baseline

---

## Troubleshooting

### NetworkPolicy Not Blocking

**Symptom:** Backend → PostgreSQL still works after applying policy

**Possible causes:**
1. CNI plugin doesn't support NetworkPolicy
2. Policy hasn't propagated yet (wait 10-30 seconds)
3. Policy selector doesn't match database pods

**Check:**
```bash
kubectl get networkpolicy -n poc-app isolate-database -o yaml
kubectl get pods -n poc-app -l app=database --show-labels
```

---

### Backend Pod Crashes

**Symptom:** Backend pod status is not "Running"

**This is unexpected** - the policy should block connections, not crash the pod.

**Check:**
```bash
kubectl logs -n poc-app -l app=backend --tail=50
kubectl describe pod -n poc-app -l app=backend
```

---

### Policy Won't Delete

**Symptom:** `remove-network-policy.sh` fails

**Try manual removal:**
```bash
kubectl delete networkpolicy isolate-database -n poc-app
```

**Force delete if needed:**
```bash
kubectl delete networkpolicy isolate-database -n poc-app --force --grace-period=0
```

---

### Baseline Doesn't Restore

**Symptom:** After removing policy, Backend still can't connect to PostgreSQL

**Wait longer:**
```bash
# Wait 30 seconds, then test again
sleep 30
kubectl exec -n poc-app $(kubectl get pod -n poc-app -l app=backend -o jsonpath='{.items[0].metadata.name}') -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
```

**Restart Backend if needed:**
```bash
kubectl rollout restart deployment backend -n poc-app
```

---

## Expected Timeline

| Step | Duration | Cumulative |
|------|----------|------------|
| Apply policy | ~5s | 5s |
| Verify impact | ~30-60s | 35-65s |
| Review results | ~1-2min | 3-5min |
| Browser test | ~1min | 4-6min |
| Remove policy | ~10s | 5-7min |
| Verify baseline | ~30s | 5-8min |

**Total:** 5-8 minutes for complete experiment cycle

---

## Research Notes Template

After execution, document:

```markdown
## Milestone 2 Execution Notes

**Date:** YYYY-MM-DD
**Time:** HH:MM

### Expected Behavior
- Backend → PostgreSQL blocked
- Backend health fails
- PostgreSQL pod remains running

### Observed Behavior
- [Fill in actual observations]

### Match
- [ ] Expected and observed matched
- [ ] Hypothesis confirmed
- [ ] Any discrepancies: [describe]

### Issues Encountered
- [None / describe any issues]

### Recovery
- [ ] Policy removed successfully
- [ ] Baseline restored
- [ ] All checks pass

### Files Generated
- network-policy-verification.json (timestamp: ...)

### Next Steps
- [ ] Archive results
- [ ] Update research log
- [ ] Prepare for Milestone 3
```

---

## Success Criteria Checklist

### Pre-Execution
- [ ] Milestone 1 baseline verified
- [ ] Cluster running
- [ ] All pods Running
- [ ] `baseline-verification.json` exists

### Post-Policy Application
- [ ] NetworkPolicy exists
- [ ] Backend → PostgreSQL blocked (network-level)
- [ ] Backend health reports failure (application-level)
- [ ] PostgreSQL pod still Running
- [ ] Frontend → Backend still works
- [ ] Hypothesis confirmed

### Post-Policy Removal
- [ ] NetworkPolicy deleted
- [ ] Backend → PostgreSQL restored
- [ ] Backend health restored
- [ ] Baseline verification passes

### Documentation
- [ ] `network-policy-verification.json` generated
- [ ] Observed behavior populated
- [ ] Hypothesis confirmation recorded
- [ ] Any deviations documented

---

## File Locations

```
Final-Year-Project/
├── kubernetes/policies/isolate-database.yaml
├── scripts/
│   ├── apply-network-policy.sh
│   ├── verify-network-policy.sh
│   └── remove-network-policy.sh
├── network-policy-verification.json (generated)
└── MILESTONE-2-SUMMARY.md
```

---

## Commands Reference

```bash
# Apply policy
./scripts/apply-network-policy.sh

# Verify impact
./scripts/verify-network-policy.sh

# Check results
cat network-policy-verification.json

# Test in browser
xdg-open http://localhost:30080  # Linux
open http://localhost:30080      # macOS
start http://localhost:30080     # Windows

# Check logs
kubectl logs -n poc-app -l app=backend --tail=20

# Remove policy
./scripts/remove-network-policy.sh

# Verify baseline
./scripts/verify-baseline.sh

# Manual checks
kubectl get networkpolicy -n poc-app
kubectl get pods -n poc-app
kubectl exec -n poc-app <backend-pod> -- python3 -c "import socket; sock = socket.socket(); sock.settimeout(5); print(sock.connect_ex(('database-service', 5432)))"
```

---

**End of Execution Guide**
