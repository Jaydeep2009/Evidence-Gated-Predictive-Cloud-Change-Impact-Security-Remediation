# Milestone 2: Verification Script Final Review

**Date:** 2026-10-11  
**Status:** Pre-execution review complete

---

## Issue 1: JSON Injection Risk (CRITICAL)

### Problem
Line 340 interpolates `$HYPOTHESIS_REASONING` directly into JSON without escaping. This variable contains:
- Square brackets: `[1. Policy exists: true]`
- Parentheses with shell substitutions
- Potentially quotes from pod status output

**Risk:** Invalid JSON or syntax errors

### Proposed Fix

Add before line 287 (JSON generation start):

```bash
# Escape reasoning string for safe JSON insertion
HYPOTHESIS_REASONING_ESCAPED="${HYPOTHESIS_REASONING//\\/\\\\}"  # Escape backslashes first
HYPOTHESIS_REASONING_ESCAPED="${HYPOTHESIS_REASONING_ESCAPED//\"/\\\"}"  # Then escape quotes
```

Change line 340 from:
```bash
    "reasoning": "$HYPOTHESIS_REASONING",
```

To:
```bash
    "reasoning": "$HYPOTHESIS_REASONING_ESCAPED",
```

---

## Issue 2: Misleading Console Label

### Problem
Line 363: `Backend→DB Blocked: ✅` is misleading because:
- `BACKEND_TO_DB_BLOCKED=true` for timeout, refused, AND generic errors
- "Blocked" specifically implies policy enforcement
- Connection refused (111) is not "blocked by policy"
- Generic errors are not "blocked by policy"

### Proposed Fix

Change line 363 from:
```bash
echo "  Backend→DB Blocked: $([ "$BACKEND_TO_DB_BLOCKED" = true ] && echo "✅" || echo "❌")"
```

To:
```bash
echo "  Backend→DB Connectivity: $([ "$BACKEND_TO_DB_BLOCKED" = false ] && echo "✅ Connected" || echo "❌ Affected ($BACKEND_TO_DB_STATUS)")"
```

**Rationale:** More accurate, includes the actual status classification

---

## CNI and NetworkPolicy Enforcement

### Current Configuration

✅ **CNI:** kindnet v20260820-69b56db7 (Kind's default CNI)  
✅ **NetworkPolicy Support:** Yes, implemented via iptables  
✅ **Enforcement:** Enabled by default  
✅ **Active Policy:** `isolate-database` in namespace `poc-app`  
✅ **Policy Age:** 2 days 16 hours (created 2026-10-08T16:43:59Z)  
✅ **Policy Type:** Ingress deny-all (empty ingress rules)  
✅ **Pod Selector:** `app=database` (matches database-deployment pods)

### Verification

```bash
$ kubectl get pods -n poc-app -l app=database --show-labels
NAME                                  READY   STATUS    RESTARTS       AGE    LABELS
database-deployment-d7695bb98-dd6p7   1/1     Running   3 (115m ago)   4d2h   app=database,pod-template-hash=d7695bb98,tier=data
```

✅ Database pod has label `app=database`  
✅ NetworkPolicy `podSelector.matchLabels.app=database` matches

**Conclusion:** NetworkPolicy is correctly configured and actively enforced.

---

## Evidence for Policy-Enforced Timeout

### Six-Condition Evidence Chain

1. ✅ **NetworkPolicy exists** - policy `isolate-database` active for 2d16h
2. ✅ **Connection timeout (110)** - packets dropped at network layer (not refused/reset)
3. ✅ **Backend readiness not_ready** - application detects database failure
4. ✅ **Backend liveness healthy** - container process healthy
5. ✅ **Backend phase Running** - pod not crashing
6. ✅ **Database phase Running** - destination pod healthy

### Why This Distinguishes Policy Enforcement

**Ruled Out:**
- ❌ Database crashed → DB would not be Running
- ❌ Database refusing connections → Would return ECONNREFUSED (111), not ETIMEDOUT (110)
- ❌ Network infrastructure failure → Would affect all pods, not isolated to backend→database
- ❌ DNS failure → Would fail earlier with name resolution error
- ❌ Application bug → Would cause liveness failure or container restarts

**Supporting:**
- ✅ Connection timeout (110) indicates packets dropped at network layer (iptables)
- ✅ Isolated failure matches NetworkPolicy scope (backend→database only)
- ✅ Both pods healthy, only network path affected
- ✅ kindnet uses iptables DROP for denied traffic → timeout, not refused

### Additional Validation (Not Implemented Yet)

Could add:
- Check iptables rules on node (requires node access)
- Test from pod in different namespace (should succeed if policy is namespace-scoped)
- Test from pod with allowed label (if policy had ingress allow rules)

---

## Proposed Code Changes

### Change 1: Add JSON Escaping (After line 284)

```bash
# Generate JSON output
echo "Writing results to: $OUTPUT_FILE"

# Escape hypothesis reasoning for safe JSON insertion
HYPOTHESIS_REASONING_ESCAPED="${HYPOTHESIS_REASONING//\\/\\\\}"  # Escape backslashes first
HYPOTHESIS_REASONING_ESCAPED="${HYPOTHESIS_REASONING_ESCAPED//\"/\\\"}"  # Then escape quotes

cat > "$OUTPUT_FILE" << EOF
```

### Change 2: Update Console Label (Line 363)

```bash
echo "  Backend→DB Connectivity: $([ "$BACKEND_TO_DB_BLOCKED" = false ] && echo "✅ Connected" || echo "❌ Affected ($BACKEND_TO_DB_STATUS)")"
```

### Change 3: Update JSON reasoning reference (Line 340)

```bash
    "reasoning": "$HYPOTHESIS_REASONING_ESCAPED",
```

---

## Files to Modify

- `scripts/verify-network-policy.sh` only

**Lines to change:**
- After line 284: Add 4 lines (escaping logic)
- Line 340 (becomes 344): Change variable reference
- Line 363 (becomes 367): Change console label

**No other changes:**
- ✅ Preserve liveness probe changes
- ✅ Preserve `/live` endpoint
- ✅ Preserve Test 3 socket logic
- ✅ Preserve hypothesis six-condition check
- ✅ Preserve all other JSON fields

---

## Current Git Status

```
 M kubernetes/backend/deployment.yaml  (liveness probe path)
 M services/backend/app/main.py        (whitespace fix in /live endpoint)
?? scripts/verify-network-policy.sh    (new untracked file)
```

---

## Critical Finding: Experiment Already Running

**NetworkPolicy `isolate-database` has been active for 2 days 16 hours.**

The verification script will:
- Observe the current experiment state
- NOT apply a new NetworkPolicy (it's already applied)
- Validate whether the hypothesis holds under current conditions

**User should decide:**
1. Run verification script now to observe current state
2. Remove NetworkPolicy, verify baseline recovery, then reapply for fresh experiment
3. Proceed as-is (assumes current state is stable)

---

## Recommendation

**Apply proposed changes:**
1. Add JSON escaping (critical for validity)
2. Update console label (clarity and accuracy)

**Then:**
- User manually executes `./scripts/verify-network-policy.sh`
- Review generated JSON for validity
- Compare observed results with six-condition hypothesis

**Do NOT:**
- Execute script automatically
- Remove/reapply NetworkPolicy yet
- Restart pods
- Rebuild images

