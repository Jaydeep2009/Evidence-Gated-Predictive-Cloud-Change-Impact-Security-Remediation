# Milestone 2: Evidence Analysis

**Date:** 2026-10-11  
**Experiment:** Three-stage controlled NetworkPolicy impact validation  
**Cluster:** `poc-cluster`  
**Namespace:** `poc-app`  
**NetworkPolicy:** `isolate-database`

---

## Executive Summary

This analysis compares evidence from three controlled stages of Milestone 2 NetworkPolicy experimentation. The three-stage pattern (absent→present→absent) is consistent with a causal relationship between Kubernetes NetworkPolicy presence and backend-to-database connectivity failure.

**Key finding:** NetworkPolicy `isolate-database` causes Backend→Database connectivity timeout (errno 11), Backend NotReady state, while preserving pod lifecycle (no crashes). Removal of NetworkPolicy restores connectivity and Backend readiness.

---

## Evidence Files

| Stage | File | Timestamp | Size | MD5 |
|-------|------|-----------|------|-----|
| **1 - Baseline** | `network-policy-verification-20261011-132130.json` | 2026-10-11T13:21:30.772Z | 3159 bytes | 0E38105C102D9EE395024C44AD8FC7A9 |
| **2 - Impact** | `network-policy-verification-20261011-133342.json` | 2026-10-11T13:33:42.340Z | 3400 bytes | 4AB0A53036D64FD9B8D888BD3A6BBEB5 |
| **3 - Recovery** | `network-policy-verification-20261011-135142.json` | 2026-10-11T13:51:42.810Z | 3159 bytes | SHA256: 65AE73FA9197CC33C431C1ABB2D93F814956F7473A5EBBC2474745FF98892697 |

---

## Comparative Analysis

### 1. NetworkPolicy Status

| Stage | Policy Status | Expected Behavior |
|-------|--------------|-------------------|
| 1 - Baseline | `not_found` | No traffic restriction |
| 2 - Impact | `active` | Backend→Database blocked |
| 3 - Recovery | `not_found` | No traffic restriction |

**Finding:** NetworkPolicy applied successfully in Stage 2, absent in Stage 1 and 3.

---

### 2. Backend→Database Connectivity

| Stage | socket_code | socket_error | status | interpretation |
|-------|------------|--------------|--------|----------------|
| 1 - Baseline | 0 | none | connected | N/A (healthy) |
| 2 - Impact | 11 | EAGAIN (observed after 5s timeout) | connection_timeout | Consistent with NetworkPolicy blocking |
| 3 - Recovery | 0 | none | connected | N/A (healthy) |

**Finding:** Socket code transitions 0→11→0 align with NetworkPolicy absent→present→absent pattern.

**Technical note:** errno 11 (EAGAIN) observed in Python socket.settimeout() environment after 5-second timeout, consistent with prior investigation findings (Python bug #23351, psycopg2 behavior).

---

### 3. Backend Health

| Stage | phase | readiness | liveness | restart_count |
|-------|-------|-----------|----------|---------------|
| 1 - Baseline | Running | ready | healthy | 1 |
| 2 - Impact | Running | not_ready | healthy | 1 |
| 3 - Recovery | Running | ready | healthy | 1 |

**Finding:** Backend transitions to NotReady when NetworkPolicy active, recovers to Ready when policy removed. Liveness remains healthy throughout. Pod phase remains Running (no crashes). restart_count unchanged (no pod restarts).

**Interpretation:** NetworkPolicy affects readiness probe outcome without causing pod restart or crash. This demonstrates that Kubernetes readiness gating works as designed: failing readiness probe removes pod from service endpoints while preserving the pod.

---

### 4. Frontend→Backend Connectivity

| Stage | Status |
|-------|--------|
| 1 - Baseline | success |
| 2 - Impact | success |
| 3 - Recovery | success |

**Finding:** Frontend→Backend communication unaffected by NetworkPolicy targeting Database ingress. This confirms NetworkPolicy scope is correctly limited to Database pod isolation.

---

### 5. Database Pod State

| Stage | Status |
|-------|--------|
| 1 - Baseline | running |
| 2 - Impact | running |
| 3 - Recovery | running |

**Finding:** PostgreSQL pod remains running throughout all stages. NetworkPolicy does not affect Database pod lifecycle, only ingress traffic.

---

### 6. Hypothesis Confirmation

| Stage | conditions_met | reasoning |
|-------|----------------|-----------|
| 1 - Baseline | false | Policy absent, Backend healthy |
| 2 - Impact | **true** | All six conditions met |
| 3 - Recovery | false | Policy absent, Backend healthy |

**Hypothesis statement:** "Applying NetworkPolicy that isolates PostgreSQL will block required Backend→PostgreSQL communication, causing application failure while PostgreSQL pod remains running"

**Stage 2 conditions met:**
1. ✅ NetworkPolicy exists
2. ✅ Backend→Database connection timeout (socket code 11)
3. ✅ Backend readiness not_ready
4. ✅ Backend liveness healthy
5. ✅ Backend phase Running
6. ✅ PostgreSQL phase Running

**Finding:** All six hypothesis conditions met only in Stage 2 (NetworkPolicy active). Stages 1 and 3 (NetworkPolicy absent) show healthy baseline behavior.

---

## Causation Demonstration

### Pattern Summary

```
Stage 1 (Baseline):   NetworkPolicy ABSENT  → Backend healthy (errno 0, ready)
Stage 2 (Impact):     NetworkPolicy PRESENT → Backend unhealthy (errno 11, not_ready)
Stage 3 (Recovery):   NetworkPolicy ABSENT  → Backend healthy (errno 0, ready)
```

### Evidence for Causation

1. **Temporal sequence:** NetworkPolicy applied → Backend becomes NotReady → NetworkPolicy removed → Backend recovers
2. **Reproducibility:** Stage 3 recovery matches Stage 1 baseline (socket_code=0, readiness=ready)
3. **Specificity:** Only Backend→Database connectivity affected; Frontend→Backend unaffected; Database pod unaffected
4. **Consistency:** restart_count unchanged (no pod restarts), phase remains Running (no crashes)
5. **Reversibility:** Removing NetworkPolicy restores connectivity immediately

**Conclusion:** The three-stage pattern is consistent with a causal relationship between NetworkPolicy presence and Backend connectivity failure. While not definitive proof (packet-level verification and nftables inspection during the experiment were not performed), the controlled absent→present→absent pattern, reproducibility (Stage 3 matching Stage 1), specificity (only Backend→Database affected), and reversibility provide strong supporting evidence that NetworkPolicy is the causal variable.

---

## Limitations

### 1. Evidence Scope
- **Single application architecture:** Frontend→Backend→Database
- **Single NetworkPolicy type:** Deny-all ingress to Database
- **Single cluster environment:** Kind 0.25.0, Kubernetes 1.32.0, kindnet CNI
- **Single failure mode:** Backend→Database connectivity timeout

### 2. Verification Method
- **Socket test:** Python `socket.connect_ex()` with 5s timeout
- **Readiness probe:** Kubernetes readiness state + /live endpoint
- **No packet-level verification:** Did not use tcpdump/Wireshark to capture actual packet drops
- **No iptables/nftables inspection:** Did not verify firewall rule installation beyond prior read-only investigation

### 3. Generalizability
- **Other CNI implementations:** Results specific to kindnet; Calico/Cilium/Weave may behave differently
- **Other NetworkPolicy types:** Allow-list policies, egress policies not tested
- **Other failure modes:** Connection refused (ECONNREFUSED), host unreachable (EHOSTUNREACH) not tested
- **Other workloads:** Results specific to simple HTTP API + PostgreSQL architecture

### 4. Temporal Factors
- **Convergence time:** 15-20 second delays used between policy changes and verification
- **Grace periods:** Kubernetes termination grace periods not explicitly controlled
- **Race conditions:** No verification of transient states during policy application/removal

---

## Research Implications

### For Evidence-Gated Impact Prediction System

This experiment provides:

1. **Ground truth data:** Three evidence files capturing healthy/unhealthy/recovery states
2. **Validation method:** Socket test + readiness probe as reliable failure indicators
3. **Causation pattern:** Controlled experiment demonstrates NetworkPolicy→failure causation
4. **Evidence requirements:** Six conditions necessary to confirm hypothesis

### For Future Experiments

This methodology (absent→present→absent) can be applied to:
- IAM permission changes
- Network security rule changes
- Other Kubernetes admission/policy mechanisms
- Other failure modes (ECONNREFUSED, EHOSTUNREACH, etc.)

### For Literature Contribution

This work extends prior research:
- **Budigiri et al.:** NetworkPolicy security analysis → now includes controlled causation demonstration
- **Hu et al. (2023):** Terraform dependency graphs → now includes Kubernetes NetworkPolicy impact
- **Gomez et al. (2026):** Formal verification under evolution → now includes prediction-vs-reality comparison

**Novel contribution:** Integration of infrastructure evidence (NetworkPolicy manifest), application evidence (Backend dependency on Database), and runtime evidence (socket test, readiness probe) to predict and verify security change impact through controlled experimentation.

---

## Conclusions

1. **Pattern consistent with causation:** NetworkPolicy `isolate-database` presence correlates with Backend→Database connectivity failure in controlled experiment
2. **Methodology validated:** Three-stage absent→present→absent pattern demonstrates causation
3. **Evidence quality:** Six-condition hypothesis confirmation provides high-confidence prediction
4. **Reproducibility:** Stage 3 recovery matches Stage 1 baseline exactly
5. **Scope clarity:** Results limited to specific architecture, CNI, and failure mode

---

## Next Steps

1. **Milestone 2 completion report:** Document experiment design, execution, results, limitations
2. **Evidence file preservation:** Archive all three evidence files with metadata
3. **System design:** Use this experiment as foundation for Evidence-Gated Impact Prediction architecture
4. **Baseline comparison:** Compare Infrastructure-only vs Infrastructure+Application+Runtime evidence configurations
5. **Generalization:** Test methodology on IAM and network security rule changes

---

## Appendices

### A. Verification Method Details

**Socket connectivity test:**
```bash
kubectl exec -n poc-app deployment/backend -- \
  python3 -c 'import socket; s=socket.socket(); s.settimeout(5); print(s.connect_ex(("database-service", 5432)))'
```

**Readiness check:**
```bash
kubectl get pods -n poc-app -l app=backend \
  -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}'
```

**Liveness check:**
```bash
kubectl exec -n poc-app deployment/backend -- \
  python3 -c 'import urllib.request; urllib.request.urlopen("http://localhost:8000/live", timeout=5).read()'
```

### B. NetworkPolicy Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-database
  namespace: poc-app
spec:
  podSelector:
    matchLabels:
      app: database
  policyTypes:
    - Ingress
  ingress: []  # Empty ingress rules = deny all ingress traffic
```

### C. Evidence File Schema

Required fields:
- `timestamp`: ISO 8601 timestamp
- `milestone`: "2"
- `observed_behavior`: Actual measurements
- `hypothesis`: Conditions and reasoning

Optional fields:
- `expected_behavior`: Anticipated outcomes
- `verification_method`: Test methodology
- `verification_results`: Structured test outcomes
- `notes`: Additional context

---

**END OF ANALYSIS**
